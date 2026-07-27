import re
import sys
import traceback
from pathlib import Path
import numpy as np
import pandas as pd


# ==========================================
# 1. FILE DISCOVERY & COLUMN NORMALIZATION
# ==========================================
def extract_timestamp_suffix(filename: str) -> str:
    """Extracts date/time string from filename or returns empty string fallback."""
    match = re.search(
        r"(\d{8}[_\-]\d{6}|\d{4}[_\-]\d{2}[_\-]\d{2}[_\-T]\d{2}[_\-]\d{2}[_\-]\d{2})",
        filename,
    )
    if match:
        return match.group(1)

    stem = Path(filename).stem
    for prefix in [
        "atc_events_",
        "atc_events",
        "flight_telemetry_",
        "flight_telemetry",
    ]:
        if stem.startswith(prefix):
            return stem[len(prefix) :].strip("_")
    return ""


def discover_input_files(base_dir: Path):
    """Finds ATC target files and optional matching telemetry files in base_dir."""
    atc_files = sorted(list(base_dir.glob("atc_events*.csv")))
    telem_files = sorted(list(base_dir.glob("flight_telemetry*.csv")))

    if not atc_files:
        raise FileNotFoundError(
            f"No 'atc_events*.csv' found in {base_dir.resolve()}"
        )

    atc_path = atc_files[0]
    ts_suffix = extract_timestamp_suffix(atc_path.name)

    telem_path = None
    if telem_files:
        if ts_suffix:
            matched = [f for f in telem_files if ts_suffix in f.name]
            telem_path = matched[0] if matched else telem_files[0]
        else:
            telem_path = telem_files[0]

    print(f" Found ATC File        : {atc_path.name}")
    if telem_path:
        print(f" Found Telemetry File  : {telem_path.name}")
    if ts_suffix:
        print(f" Detected Session Tag : {ts_suffix}")

    return atc_path, telem_path, ts_suffix


def normalize_atc_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Maps varied column names to standardized target names."""
    col_map = {}
    lower_cols = {str(col).lower().strip(): col for col in df.columns}

    candidates = {
        "Target_Hdg": [
            "target_hdg",
            "target_heading",
            "hdg_target",
            "target_hdg_deg",
            "heading",
        ],
        "Target_Alt_Ft": [
            "target_alt_ft",
            "target_alt",
            "target_altitude",
            "alt_target",
            "altitude",
        ],
        "Target_VSI_FPM": [
            "target_vsi_fpm",
            "target_vsi",
            "vsi_target",
            "target_vert_speed",
            "vsi",
        ],
    }

    for target, options in candidates.items():
        for opt in options:
            if opt in lower_cols:
                col_map[lower_cols[opt]] = target
                break

    return df.rename(columns=col_map)


# ==========================================
# 2. KINEMATIC REFERENCE TRAJECTORY GENERATOR
# ==========================================
class ReferenceTrajectoryGenerator:

    def __init__(
        self, max_bank=30.0, roll_rate=5.0, ias_target=300.0, vsi_ramp_time=4.0
    ):
        self.max_bank = max_bank  # deg
        self.roll_rate = roll_rate  # deg/s
        self.ias_target = ias_target  # kt target for A/THR
        self.vsi_ramp_time = vsi_ramp_time  # sec

    def calculate_turn_rate(self, current_alt_ft: float) -> float:
        """Approximates turn rate at 30 deg bank based on IAS target and initiation altitude rounded to 1000 ft."""
        alt_k = round(current_alt_ft / 1000.0)
        vtas = self.ias_target * (1.0 + 0.02 * alt_k)
        return 629.89 / vtas

    def _determine_turn_direction(
        self, telem_df: pd.DataFrame, t_start: pd.Timestamp, window_sec: float = 30.0
    ) -> str:
        """Analyzes pilot telemetry over a 30s window following an ATC command to infer intended turn direction."""
        if telem_df is None or telem_df.empty or "Timestamp" not in telem_df.columns:
            return "AUTO"

        bank_col = None
        lower_cols = {str(col).lower().strip(): col for col in telem_df.columns}
        for opt in ["bank", "bank_deg", "plane_bank", "bank_angle", "roll", "roll_deg", "plane_roll"]:
            if opt in lower_cols:
                bank_col = lower_cols[opt]
                break

        if not bank_col:
            return "AUTO"

        t_end = t_start + pd.Timedelta(seconds=window_sec)
        mask = (telem_df["Timestamp"] >= t_start) & (telem_df["Timestamp"] <= t_end)
        window = telem_df.loc[mask]

        if window.empty:
            return "AUTO"

        raw_bank = pd.to_numeric(window[bank_col], errors="coerce").dropna().values
        if len(raw_bank) == 0:
            return "AUTO"

        # Align raw telemetry bank sign (+ = Right bank, - = Left bank)
        aligned_bank = -1.0 * raw_bank if bank_col != "Bank" else raw_bank
        active_bank = aligned_bank[np.abs(aligned_bank) > 2.0]

        if len(active_bank) == 0:
            return "AUTO"

        mean_bank = np.mean(active_bank)
        if mean_bank > 1.5:
            return "RIGHT"
        elif mean_bank < -1.5:
            return "LEFT"

        return "AUTO"

    def generate_trajectory(
        self,
        atc_df: pd.DataFrame,
        telem_df: pd.DataFrame = None,
        dt=0.1,
        duration_extension=180,
    ) -> pd.DataFrame:
        atc_df = normalize_atc_columns(atc_df)
        atc_df = atc_df.sort_values("Timestamp").reset_index(drop=True)

        if telem_df is not None:
            telem_df = telem_df.copy()
            telem_df["Timestamp"] = pd.to_datetime(telem_df["Timestamp"])

        t_start = atc_df["Timestamp"].iloc[0]
        t_end = atc_df["Timestamp"].iloc[-1] + pd.Timedelta(
            seconds=duration_extension
        )

        timestamps = pd.date_range(
            start=t_start, end=t_end, freq=f"{int(dt * 1000)}ms"
        )
        n = len(timestamps)

        ref_hdg = np.zeros(n)
        ref_bank = np.zeros(n)
        ref_alt = np.zeros(n)
        ref_vsi = np.zeros(n)

        init_row = atc_df.iloc[0]
        curr_hdg = float(init_row["Target_Hdg"])
        curr_alt = float(init_row["Target_Alt_Ft"])
        curr_vsi = 0.0
        curr_bank = 0.0

        event_idx = 0
        num_events = len(atc_df)

        target_hdg = curr_hdg
        target_alt = curr_alt
        target_vsi = 0.0
        forced_turn_dir = "AUTO"
        active_turn_rate = self.calculate_turn_rate(curr_alt)  # Initial turn rate

        for i in range(n):
            t_curr = timestamps[i]

            while (
                event_idx < num_events
                and t_curr >= atc_df.loc[event_idx, "Timestamp"]
            ):
                ev = atc_df.loc[event_idx]
                if ev.get("Event_Type", "ATC_TARGET") in [
                    "INIT_STATE",
                    "ATC_TARGET",
                ]:
                    target_hdg = float(ev["Target_Hdg"])
                    target_alt = float(ev["Target_Alt_Ft"])
                    target_vsi = float(ev["Target_VSI_FPM"])
                    # Lock in dynamic turn rate at moment of turn vector initiation
                    active_turn_rate = self.calculate_turn_rate(curr_alt)
                    forced_turn_dir = self._determine_turn_direction(
                        telem_df, ev["Timestamp"], window_sec=30.0
                    )
                event_idx += 1

            # -------------------------------------------------------------
            # Bank & Heading Kinematics (Telemetry-Aware Direction Override)
            # -------------------------------------------------------------
            # Shortest angular distance (-180 to +180 deg)
            hdg_diff_shortest = (target_hdg - curr_hdg + 180) % 360 - 180

            # Override default shortest arc if pilot telemetry shows intentional long-way turn
            if (
                forced_turn_dir == "RIGHT"
                and hdg_diff_shortest < 0
                and abs(hdg_diff_shortest) > 90.0
            ):
                hdg_diff = (target_hdg - curr_hdg) % 360.0
            elif (
                forced_turn_dir == "LEFT"
                and hdg_diff_shortest > 0
                and abs(hdg_diff_shortest) > 90.0
            ):
                hdg_diff = -((curr_hdg - target_hdg) % 360.0)
            else:
                hdg_diff = hdg_diff_shortest

            if self.max_bank > 0 and abs(curr_bank) > 0.01:
                curr_turn_rate = active_turn_rate * (
                    np.tan(np.radians(curr_bank)) / np.tan(np.radians(self.max_bank))
                )
            else:
                curr_turn_rate = 0.0
            
            roll_time = (
                abs(curr_bank) / self.roll_rate if self.roll_rate > 0 else 0
            )
            lead_hdg_angle = 0.5 * abs(curr_turn_rate) * roll_time

            if abs(hdg_diff) <= 0.1 and abs(curr_bank) <= 0.1:
                curr_hdg = target_hdg
                desired_bank = 0.0
            # Check rollout condition: bank direction matches heading turn direction
            elif abs(hdg_diff) <= lead_hdg_angle + 0.2 and (
                (hdg_diff > 0 and curr_bank > 0)
                or (hdg_diff < 0 and curr_bank < 0)
            ):
                desired_bank = 0.0
            else:
                # Right Turn (hdg_diff > 0) -> Positive Bank (+max_bank)
                # Left Turn  (hdg_diff < 0) -> Negative Bank (-max_bank)
                bank_dir = np.sign(hdg_diff) if hdg_diff != 0 else 1.0
                desired_bank = bank_dir * self.max_bank

            # Smoothly transition current bank angle towards desired bank angle
            bank_err = desired_bank - curr_bank
            max_bank_change = self.roll_rate * dt
            curr_bank += np.clip(bank_err, -max_bank_change, max_bank_change)

            # Turn Rate Dynamics:
            if self.max_bank > 0 and abs(curr_bank) > 0.01:
                actual_turn_rate = active_turn_rate * (
                    np.tan(np.radians(curr_bank)) / np.tan(np.radians(self.max_bank))
                )
            else:
                actual_turn_rate = 0.0
            curr_hdg = (curr_hdg + actual_turn_rate * dt) % 360.0

            # -------------------------------------------------------------
            # VSI & Altitude Kinematics
            # -------------------------------------------------------------
            alt_diff = target_alt - curr_alt
            lead_alt = abs(0.5 * (curr_vsi / 60.0) * self.vsi_ramp_time)

            if abs(alt_diff) <= 0.1 and abs(curr_vsi) <= 10.0:
                curr_vsi = 0.0
                desired_vsi = 0.0
            elif abs(alt_diff) <= lead_alt + 5.0 and (alt_diff * curr_vsi > 0):
                # Smooth parabolic descent/climb ramp during altitude capture
                vsi_dir = np.sign(alt_diff)
                desired_vsi = vsi_dir * abs(target_vsi) * (abs(alt_diff) / max(lead_alt + 5.0, 1.0))
            else:
                vsi_dir = np.sign(alt_diff) if alt_diff != 0 else 0.0
                desired_vsi = vsi_dir * abs(target_vsi)

            vsi_err = desired_vsi - curr_vsi
            vsi_scale = max(abs(curr_vsi), abs(target_vsi), 1000.0)
            max_vsi_change = (
                vsi_scale / max(self.vsi_ramp_time, 0.1)
            ) * dt
            curr_vsi += np.clip(vsi_err, -max_vsi_change, max_vsi_change)

            curr_alt += (curr_vsi / 60.0) * dt

            ref_hdg[i] = curr_hdg
            ref_bank[i] = curr_bank
            ref_alt[i] = curr_alt
            ref_vsi[i] = curr_vsi

        return pd.DataFrame(
            {
                "Timestamp": timestamps,
                "Ref_Hdg": np.round(ref_hdg, 2),
                "Ref_Bank": np.round(ref_bank, 2),
                "Ref_Alt": np.round(ref_alt, 2),
                "Ref_VSI": np.round(ref_vsi, 2),
            }
        )


# ==========================================
# 3. RUN PIPELINE & TERMINAL HOLD
# ==========================================
if __name__ == "__main__":
    try:
        work_dir = (
            Path(__file__).parent if "__file__" in locals() else Path.cwd()
        )

        atc_path, telem_path, ts_suffix = discover_input_files(work_dir)

        atc_df = pd.read_csv(atc_path)
        atc_df["Timestamp"] = pd.to_datetime(atc_df["Timestamp"])

        telem_df = pd.read_csv(telem_path) if telem_path else None

        generator = ReferenceTrajectoryGenerator()
        ref_traj_df = generator.generate_trajectory(atc_df, telem_df=telem_df)

        # Save to parent directory matching input session timestamp
        parent_dir = atc_path.parent
        out_name = (
            f"ref_trajectory_{ts_suffix}.csv"
            if ts_suffix
            else "ref_trajectory.csv"
        )
        output_filepath = parent_dir / out_name

        ref_traj_df.to_csv(
            output_filepath, index=False, date_format="%Y-%m-%d %H:%M:%S.%f"
        )

        print("\n==================================================")
        print(" PHASE 1 GENERATION COMPLETE")
        print("==================================================")
        print(f" Reference Output File : {output_filepath.resolve()}")
        print(f" Total Samples         : {len(ref_traj_df)}")

    except Exception as e:
        print("\n==================================================")
        print(" AN ERROR OCCURRED DURING PHASE 1 EXECUTION")
        print("==================================================")
        traceback.print_exc()

    finally:
        print("\n" + "=" * 50)
        input("Press Enter to exit...")
