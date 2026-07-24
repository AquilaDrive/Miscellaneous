import sys
import re
import traceback
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


# -------------------------------------------------------------------------
# 1. DYNAMIC FILE DISCOVERY
# -------------------------------------------------------------------------
def find_analysis_files(base_dir: Path):
    """Dynamically finds the latest aligned telemetry and scorecard CSV files

    in base_dir or its parent folder based on modification timestamp.
    """
    search_dirs = (
        [base_dir, base_dir.parent]
        if base_dir.parent != base_dir
        else [base_dir]
    )

    aligned_files = []
    scorecard_files = []

    for d in search_dirs:
        if d.exists():
            aligned_files.extend(list(d.glob("aligned_telemetry_analysis*.csv")))
            scorecard_files.extend(list(d.glob("analysis_scorecard*.csv")))

    if not aligned_files:
        raise FileNotFoundError(
            f"No 'aligned_telemetry_analysis*.csv' found in {base_dir.resolve()} or parent directory."
        )

    # Sort aligned telemetry files by modification time (latest first)
    aligned_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    latest_aligned = aligned_files[0]

    # Extract session timestamp string
    match = re.search(
        r"(\d{8}[_\-]\d{6}|\d{4}[_\-]\d{2}[_\-]\d{2}[_\-T]\d{2}[_\-]\d{2}[_\-]\d{2})",
        latest_aligned.name,
    )
    ts_tag = match.group(1) if match else ""

    # Match corresponding scorecard file
    matching_scorecard = None
    if ts_tag:
        for sc in scorecard_files:
            if ts_tag in sc.name:
                matching_scorecard = sc
                break

    if not matching_scorecard and scorecard_files:
        scorecard_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        matching_scorecard = scorecard_files[0]

    return latest_aligned, matching_scorecard, ts_tag


# -------------------------------------------------------------------------
# 2. OLED STYLING HELPER
# -------------------------------------------------------------------------
def apply_oled_style(fig, axes):
    """Applies high-contrast dark OLED styling to figure and axes."""
    fig.patch.set_facecolor("#000000")
    if not isinstance(axes, (list, np.ndarray)):
        axes = [axes]
    for ax in np.ravel(axes):
        ax.set_facecolor("#080808")
        ax.tick_params(colors="#e0e0e0", labelsize=10)
        ax.xaxis.label.set_color("#ffffff")
        ax.yaxis.label.set_color("#ffffff")
        ax.title.set_color("#ffffff")
        for spine in ax.spines.values():
            spine.set_color("#333333")
        ax.grid(True, color="#1f1f1f", linestyle="--", alpha=0.8)


# -------------------------------------------------------------------------
# 3. MAIN SCRIPT EXECUTION
# -------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        # Determine working directory
        work_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()

        # Discover latest session files
        aligned_path, scorecard_path, ts_tag = find_analysis_files(work_dir)
        print("==================================================")
        print(" LOADING SESSION DATA FOR OLED TRAJECTORY CHART")
        print("==================================================")
        print(f" Aligned Telemetry File : {aligned_path.resolve()}")
        if scorecard_path:
            print(f" Scorecard File         : {scorecard_path.resolve()}")
        print(f" Session Timestamp      : {ts_tag if ts_tag else 'N/A'}")

        # Load Data
        aligned_df = pd.read_csv(aligned_path)

        # Time Normalization
        aligned_df["Time_Min"] = (
            pd.to_datetime(aligned_df["Timestamp"])
            - pd.to_datetime(aligned_df["Timestamp"].iloc[0])
        ).dt.total_seconds() / 60.0

        # Metric-Specific OLED Color Scheme
        c_actual = "#00ffcc"  # Bright Cyan
        c_ref = "#ff007f"  # Bright Magenta

        # Metric-to-Color Identities (Optional standard assignment)
        colors = {
            "Altitude": "#00ffcc",  # Cyan
            "Heading": "#ffb700",   # Amber
            "Bank": "#ff007f",      # Magenta
            "VSI": "#3399ff",       # Blue
            "Ref": "#e0e0e0",       # Dashed Light Grey
        }

        # -------------------------------------------------------------------------
        # FIGURE 1: Flight Trajectory Tracking Dashboard (4 Subplots)
        # -------------------------------------------------------------------------
        fig1, axes1 = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
        apply_oled_style(fig1, axes1)
        fig1.suptitle(
            "PHASE 3: FLIGHT TELEMETRY VS REFERENCE TRAJECTORY (OLED MODE)",
            fontsize=16,
            fontweight="bold",
            color="#00ffcc",
            y=0.97,
        )

        # 1. Altitude
        axes1[0].plot(
            aligned_df["Time_Min"],
            aligned_df["Altitude"],
            label="Actual Altitude (ft)",
            color=c_actual,
            linewidth=1.5,
        )
        axes1[0].plot(
            aligned_df["Time_Min"],
            aligned_df["Ref_Alt"],
            label="Target Ref Altitude (ft)",
            color=c_ref,
            linewidth=1.5,
            linestyle="--",
        )
        axes1[0].set_ylabel("Altitude (ft)", fontweight="bold")
        axes1[0].legend(
            loc="upper right",
            facecolor="#111111",
            edgecolor="#333333",
            labelcolor="#ffffff",
        )
        axes1[0].set_title(
            "Altitude Tracking Profile", loc="left", color="#aaaaaa", fontsize=11
        )

        # 2. Heading
        axes1[1].plot(
            aligned_df["Time_Min"],
            aligned_df["Heading"],
            label="Actual Heading (°)",
            color=colors["Heading"],
            linewidth=1.5,
        )
        axes1[1].plot(
            aligned_df["Time_Min"],
            aligned_df["Ref_Hdg"],
            label="Target Ref Heading (°)",
            color=c_ref,
            linewidth=1.5,
            linestyle="--",
        )
        axes1[1].set_ylabel("Heading (°)", fontweight="bold")
        axes1[1].legend(
            loc="upper right",
            facecolor="#111111",
            edgecolor="#333333",
            labelcolor="#ffffff",
        )
        axes1[1].set_title(
            "Heading Tracking Profile", loc="left", color="#aaaaaa", fontsize=11
        )

        # 3. Bank Angle
        axes1[2].plot(
            aligned_df["Time_Min"],
            aligned_df["Bank"],
            label="Actual Bank (°)",
            color=colors["Bank"],
            linewidth=1.2,
        )
        axes1[2].plot(
            aligned_df["Time_Min"],
            aligned_df["Ref_Bank"],
            label="Target Ref Bank (°)",
            color=c_ref,
            linewidth=1.5,
            linestyle="--",
        )
        axes1[2].set_ylabel("Bank Angle (°)", fontweight="bold")
        axes1[2].legend(
            loc="upper right",
            facecolor="#111111",
            edgecolor="#333333",
            labelcolor="#ffffff",
        )
        axes1[2].set_title(
            "Bank Angle & Roll Execution", loc="left", color="#aaaaaa", fontsize=11
        )

        # 4. Vertical Speed (VSI)
        axes1[3].plot(
            aligned_df["Time_Min"],
            aligned_df["VSI"],
            label="Actual VSI (fpm)",
            color=colors["VSI"],
            linewidth=1.0,
            alpha=0.85,
        )
        axes1[3].plot(
            aligned_df["Time_Min"],
            aligned_df["Ref_VSI"],
            label="Target Ref VSI (fpm)",
            color=c_ref,
            linewidth=1.5,
            linestyle="--",
        )
        axes1[3].set_ylabel("VSI (fpm)", fontweight="bold")
        axes1[3].set_xlabel("Flight Time (Minutes)", fontweight="bold", fontsize=12)
        axes1[3].legend(
            loc="upper right",
            facecolor="#111111",
            edgecolor="#333333",
            labelcolor="#ffffff",
        )
        axes1[3].set_title(
            "Vertical Speed Indicator (VSI) Tracking",
            loc="left",
            color="#aaaaaa",
            fontsize=11,
        )

        plt.tight_layout()
        plt.subplots_adjust(top=0.93)

        # Save image with dynamic timestamp in source file's directory
        output_dir = aligned_path.parent
        out_filename = (
            f"oled_flight_trajectory_{ts_tag}.png"
            if ts_tag
            else "oled_flight_trajectory.png"
        )
        output_filepath = output_dir / out_filename

        fig1.savefig(
            output_filepath, dpi=300, facecolor="#000000", edgecolor="none"
        )
        plt.close(fig1)

        print("\n==================================================")
        print(" OLED TRAJECTORY CHART GENERATED SUCCESSFULLY")
        print("==================================================")
        print(f" Output Chart Path : {output_filepath.resolve()}")

    except Exception as e:
        print("\n==================================================")
        print(" AN ERROR OCCURRED DURING EXECUTION")
        print("==================================================")
        print(f" Error Type    : {type(e).__name__}")
        print(f" Error Details : {e}")
        print("\nFull Traceback:")
        traceback.print_exc()
        sys.exit(1)
