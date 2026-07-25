import re
import sys
import traceback
from pathlib import Path
import numpy as np
import pandas as pd


# ==========================================
# 1. FILE DISCOVERY & FLEXIBLE MAPPING
# ==========================================
def extract_timestamp_suffix(filename: str) -> str:
    match = re.search(
        r"(\d{8}[_\-]\d{6}|\d{4}[_\-]\d{2}[_\-]\d{2}[_\-T]\d{2}[_\-]\d{2}[_\-]\d{2})",
        filename,
    )
    return match.group(1) if match else ""


def find_matching_file_set(base_dir: Path):
    """Finds telemetry, ATC, and reference CSVs matching session tags."""
    telemetry_files = sorted(list(base_dir.glob("flight_telemetry*.csv")))
    atc_files = sorted(list(base_dir.glob("atc_events*.csv")))
    ref_files = sorted(
        list(base_dir.glob("ref_trajectory*.csv"))
        + list(base_dir.glob("generated_reference_trajectory*.csv"))
    )

    if not telemetry_files:
        raise FileNotFoundError(
            f"No 'flight_telemetry*.csv' found in {base_dir.resolve()}"
        )
    if not atc_files:
        raise FileNotFoundError(
            f"No 'atc_events*.csv' found in {base_dir.resolve()}"
        )
    if not ref_files:
        raise FileNotFoundError(
            f"No reference trajectory CSV found in {base_dir.resolve()}. Run Phase 1 script first."
        )

    target_tag = extract_timestamp_suffix(telemetry_files[0].name)

    def match_by_tag(file_list, tag):
        if not tag:
            return file_list[0]
        for f in file_list:
            if tag in f.name:
                return f
        return file_list[0]

    telem_path = match_by_tag(telemetry_files, target_tag)
    atc_path = match_by_tag(atc_files, target_tag)
    ref_path = match_by_tag(ref_files, target_tag)

    print("==================================================")
    print(" INGESTED SESSION DATASET")
    print("==================================================")
    print(f" Telemetry File : {telem_path.name}")
    print(f" ATC Events File: {atc_path.name}")
    print(f" Ref Trajectory : {ref_path.name}")
    print(
        f" Session Tag    : {target_tag if target_tag else 'Default (Untagged)'}"
    )

    return telem_path, atc_path, ref_path, target_tag


def normalize_telemetry_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Fuzzy-matches column names in flight_telemetry.csv to standard targets."""
    col_map = {}
    lower_cols = {str(col).lower().strip(): col for col in df.columns}

    candidates = {
        "Heading": [
            "heading",
            "heading_deg",
            "plane_heading",
            "plane_hdg",
            "hdg",
            "hdg_deg",
            "true_heading",
            "mag_heading",
        ],
        "Bank": [
            "bank",
            "bank_deg",
            "plane_bank",
            "bank_angle",
            "roll",
            "roll_deg",
            "plane_roll",
        ],
        "Altitude": [
            "altitude",
            "altitude_ft",
            "plane_alt",
            "plane_altitude",
            "alt",
            "alt_ft",
            "indicated_alt",
        ],
        "VSI": [
            "vsi",
            "plane_vsi",
            "vertical_speed",
            "verticalspeed",
            "verticalspeed_fpm",
            "vertical_speed_fpm",
            "vert_speed",
            "vsi_fpm",
        ],
    }

    for target, options in candidates.items():
        matched = False
        for opt in options:
            if opt in lower_cols:
                col_map[lower_cols[opt]] = target
                matched = True
                break
        if not matched and target not in df.columns:
            raise KeyError(
                f"Could not automatically map telemetry column for '{target}'. "
                f"Available columns: {list(df.columns)}"
            )

    return df.rename(columns=col_map)


# ==========================================
# 2. PERFORMANCE EVALUATION ENGINE
# ==========================================
class FlightPerformanceAnalyzer:

    def __init__(self):
        # Envelope Limits
        self.TOLERANCE_FINE = {
            "Hdg": 2.0,  # deg
            "Bank": 3.0,  # deg
            "Alt": 50.0,  # ft
            "VSI": 200.0,  # fpm
        }
        self.TOLERANCE_STANDARD = {
            "Hdg": 5.0,  # deg
            "Bank": 5.0,  # deg
            "Alt": 100.0,  # ft
            "VSI": 500.0,  # fpm
        }

    def process_and_align(
        self, telem_df: pd.DataFrame, ref_df: pd.DataFrame, atc_df: pd.DataFrame
    ) -> pd.DataFrame:
        # Standardize Telemetry Columns dynamically
        telem_df = normalize_telemetry_columns(telem_df)
        
        telem_df["Bank"] = -1.0 * telem_df["Bank"]

        telem_df["Timestamp"] = pd.to_datetime(telem_df["Timestamp"])
        ref_df["Timestamp"] = pd.to_datetime(ref_df["Timestamp"])
        atc_df["Timestamp"] = pd.to_datetime(atc_df["Timestamp"])

        # Omit Pause Periods (where state variables remain completely flat)
        telemetry_vars = ["Heading", "Bank", "Altitude", "VSI"]
        is_paused = (telem_df[telemetry_vars].diff().abs().sum(axis=1) == 0)
        telem_df = telem_df[~is_paused].reset_index(drop=True)

        # Short Tail Segment Trim (< 60 SECONDS)
        atc_df = atc_df.sort_values("Timestamp").reset_index(drop=True)
        
        while len(atc_df) > 0:
            last_seg_start = atc_df["Timestamp"].iloc[-1]
            telem_end = telem_df["Timestamp"].max()
            last_seg_duration = (telem_end - last_seg_start).total_seconds()

            if last_seg_duration < 60.0:
                # Discard last segment log entry
                atc_df = atc_df.iloc[:-1].reset_index(drop=True)
                # Cut telemetry and reference data prior to the dropped segment's start time
                telem_df = telem_df[telem_df["Timestamp"] < last_seg_start].reset_index(drop=True)
                ref_df = ref_df[ref_df["Timestamp"] < last_seg_start].reset_index(drop=True)
            else:
                break

        # Time-alignment via merge_asof
        merged = pd.merge_asof(
            telem_df.sort_values("Timestamp"),
            ref_df.sort_values("Timestamp"),
            on="Timestamp",
            direction="nearest",
        )

        # Calculate error metrics
        merged["Hdg_Err"] = (
            merged["Heading"] - merged["Ref_Hdg"] + 180
        ) % 360 - 180
        merged["Bank_Err"] = merged["Bank"] - merged["Ref_Bank"]
        merged["Alt_Err"] = merged["Altitude"] - merged["Ref_Alt"]
        merged["VSI_Err"] = merged["VSI"] - merged["Ref_VSI"]

        # Assign ATC Maneuver Segments
        atc_df = atc_df.sort_values("Timestamp").reset_index(drop=True)
        merged["Segment_ID"] = 0

        for idx in range(len(atc_df)):
            t_start = atc_df.loc[idx, "Timestamp"]
            t_end = (
                atc_df.loc[idx + 1, "Timestamp"]
                if idx + 1 < len(atc_df)
                else merged["Timestamp"].iloc[-1] + pd.Timedelta(seconds=1)
            )
            mask = (merged["Timestamp"] >= t_start) & (
                merged["Timestamp"] < t_end
            )
            merged.loc[mask, "Segment_ID"] = idx + 1

        return merged

    def compute_metrics(self, df: pd.DataFrame, label="Overall Flight"):
        n = len(df)
        if n == 0:
            return None

        # RMSE Metrics
        rmse_hdg = np.sqrt(np.mean(df["Hdg_Err"] ** 2))
        rmse_bank = np.sqrt(np.mean(df["Bank_Err"] ** 2))
        rmse_alt = np.sqrt(np.mean(df["Alt_Err"] ** 2))
        rmse_vsi = np.sqrt(np.mean(df["VSI_Err"] ** 2))

        # Percentage In-Envelope
        fine_hdg_pct = (
            np.abs(df["Hdg_Err"]) <= self.TOLERANCE_FINE["Hdg"]
        ).mean() * 100.0
        fine_alt_pct = (
            np.abs(df["Alt_Err"]) <= self.TOLERANCE_FINE["Alt"]
        ).mean() * 100.0
        fine_bank_pct = (
            np.abs(df["Bank_Err"]) <= self.TOLERANCE_FINE["Bank"]
        ).mean() * 100.0

        std_hdg_pct = (
            np.abs(df["Hdg_Err"]) <= self.TOLERANCE_STANDARD["Hdg"]
        ).mean() * 100.0
        std_alt_pct = (
            np.abs(df["Alt_Err"]) <= self.TOLERANCE_STANDARD["Alt"]
        ).mean() * 100.0
        std_bank_pct = (
            np.abs(df["Bank_Err"]) <= self.TOLERANCE_STANDARD["Bank"]
        ).mean() * 100.0

        # Oscillation Reversal Counts
        hdg_rate = np.diff(df["Hdg_Err"].values)
        bank_rate = np.diff(df["Bank_Err"].values)
        hdg_reversals = np.sum(np.diff(np.sign(hdg_rate[hdg_rate != 0])) != 0)
        bank_reversals = np.sum(
            np.diff(np.sign(bank_rate[bank_rate != 0])) != 0
        )

        # Time delta estimation
        dt = (
            (df["Timestamp"].iloc[-1] - df["Timestamp"].iloc[0]).total_seconds() / max(n - 1, 1)
            if n > 1 else 1.0
        )

        # 1. Spikes Count: Severe transient composite error excursions (>2x Standard Tolerance)
        norm_err = np.sqrt(
            (df["Hdg_Err"] / self.TOLERANCE_STANDARD["Hdg"]) ** 2
            + (df["Bank_Err"] / self.TOLERANCE_STANDARD["Bank"]) ** 2
            + (df["Alt_Err"] / self.TOLERANCE_STANDARD["Alt"]) ** 2
        )
        is_spike = norm_err > 2.0
        spike_events = int(np.sum(np.diff(is_spike.astype(int)) == 1))
        if len(is_spike) > 0 and is_spike.iloc[0]:
            spike_events += 1

        # 2. Ripple Time (Sec): Duration spent in rapid micro-oscillation corrections
        micro_reversals = np.zeros(n, dtype=bool)
        if n > 2:
            hdg_dir_change = np.pad(np.diff(np.sign(hdg_rate)) != 0, (2, 0), mode='constant', constant_values=False)
            bank_dir_change = np.pad(np.diff(np.sign(bank_rate)) != 0, (2, 0), mode='constant', constant_values=False)
            fine_band_active = (np.abs(df["Hdg_Err"]) <= self.TOLERANCE_STANDARD["Hdg"]) & \
                               (np.abs(df["Bank_Err"]) <= self.TOLERANCE_STANDARD["Bank"])
            micro_reversals = (hdg_dir_change | bank_dir_change) & fine_band_active

        ripple_time_sec = float(np.sum(micro_reversals) * dt)

        return {
            "Phase_Segment": label,
            "Duration_Sec": round(df["Timestamp"].diff().dt.total_seconds().clip(upper=1.0).sum(), 1),
            "RMSE_Hdg_Deg": round(rmse_hdg, 2),
            "RMSE_Bank_Deg": round(rmse_bank, 2),
            "RMSE_Alt_Ft": round(rmse_alt, 2),
            "RMSE_VSI_FPM": round(rmse_vsi, 2),
            "Hdg_In_Fine_Pct": round(fine_hdg_pct, 1),
            "Alt_In_Fine_Pct": round(fine_alt_pct, 1),
            "Bank_In_Fine_Pct": round(fine_bank_pct, 1),
            "Hdg_In_Std_Pct": round(std_hdg_pct, 1),
            "Alt_In_Std_Pct": round(std_alt_pct, 1),
            "Bank_In_Std_Pct": round(std_bank_pct, 1),
            "Hdg_Oscillations": int(hdg_reversals),
            "Bank_Oscillations": int(bank_reversals),
            "Spikes": spike_events,
            "Ripple_Time": round(ripple_time_sec, 2),
        }


# ==========================================
# 3. RUN PIPELINE & TERMINAL HOLD
# ==========================================
if __name__ == "__main__":
    try:
        work_dir = (
            Path(__file__).parent if "__file__" in locals() else Path.cwd()
        )

        # Step 1: Discover & Load
        telem_path, atc_path, ref_path, ts_tag = find_matching_file_set(
            work_dir
        )

        telem_df = pd.read_csv(telem_path)
        atc_df = pd.read_csv(atc_path)
        ref_df = pd.read_csv(ref_path)

        # Step 2: Align & Calculate
        analyzer = FlightPerformanceAnalyzer()
        aligned_df = analyzer.process_and_align(telem_df, ref_df, atc_df)

        # Step 3: Compute Scorecard
        scorecard_rows = []
        overall_metrics = analyzer.compute_metrics(
            aligned_df, label="Overall Flight"
        )
        scorecard_rows.append(overall_metrics)

        for seg_id, group in aligned_df.groupby("Segment_ID"):
            seg_metrics = analyzer.compute_metrics(
                group, label=f"ATC Segment {seg_id}"
            )
            if seg_metrics:
                scorecard_rows.append(seg_metrics)

        scorecard_df = pd.DataFrame(scorecard_rows)

        # Step 4: Display Output Summary Table
        print("\n==================================================")
        print(" PHASE 2 QUANTITATIVE SCORECARD SUMMARY")
        print("==================================================")
        print(
            scorecard_df[
                [
                    "Phase_Segment",
                    "Duration_Sec",
                    "RMSE_Hdg_Deg",
                    "RMSE_Alt_Ft",
                    "Hdg_In_Fine_Pct",
                    "Alt_In_Fine_Pct",
                    "Hdg_Oscillations",
                    "Spikes",
                    "Ripple_Time",
                ]
            ].to_string(index=False)
        )

        # Step 5: Save CSVs in Parent Directory
        parent_dir = telem_path.parent

        scorecard_filename = (
            f"analysis_scorecard_{ts_tag}.csv"
            if ts_tag
            else "analysis_scorecard.csv"
        )
        aligned_filename = (
            f"aligned_telemetry_analysis_{ts_tag}.csv"
            if ts_tag
            else "aligned_telemetry_analysis.csv"
        )

        scorecard_path = parent_dir / scorecard_filename
        aligned_path = parent_dir / aligned_filename

        scorecard_df.to_csv(scorecard_path, index=False)
        aligned_df.to_csv(
            aligned_path, index=False, date_format="%Y-%m-%d %H:%M:%S.%f"
        )

        print("\n==================================================")
        print(" OUTPUT FILES GENERATED IN PARENT FOLDER")
        print("==================================================")
        print(f" Performance Scorecard CSV : {scorecard_path.resolve()}")
        print(f" Aligned Time-Series Data   : {aligned_path.resolve()}")

    except Exception as e:
        print("\n==================================================")
        print(" AN ERROR OCCURRED DURING PHASE 2 EXECUTION")
        print("==================================================")
        traceback.print_exc()

    finally:
        print("\n" + "=" * 50)
        input("Press Enter to exit...")
