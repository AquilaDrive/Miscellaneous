import sys
import re
import traceback
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter
import seaborn as sns
import numpy as np
import pandas as pd

# -------------------------------------------------------------------------
# 1. FILE DISCOVERY & FLEXIBLE MAPPING
# -------------------------------------------------------------------------
def extract_timestamp_suffix(filename: str) -> str:
    """Extracts date/time string from filename or returns empty string fallback."""
    match = re.search(
        r"(\d{8}[_\-]\d{6}|\d{4}[_\-]\d{2}[_\-]\d{2}[_\-T]\d{2}[_\-]\d{2}[_\-]\d{2})",
        filename,
    )
    return match.group(1) if match else ""


def find_analysis_files(base_dir: Path):
    """Finds latest aligned_telemetry_analysis and matching analysis_scorecard CSVs."""
    search_dirs = [base_dir, base_dir.parent]
    aligned_files = []
    scorecard_files = []

    for s_dir in search_dirs:
        if s_dir.exists():
            aligned_files.extend(list(s_dir.glob("aligned_telemetry_analysis*.csv")))
            scorecard_files.extend(list(s_dir.glob("analysis_scorecard*.csv")))

    # Deduplicate by resolved path
    aligned_files = list({p.resolve(): p for p in aligned_files}.values())
    scorecard_files = list({p.resolve(): p for p in scorecard_files}.values())

    if not aligned_files:
        raise FileNotFoundError("Could not find any 'aligned_telemetry_analysis*.csv' files in current or parent directory.")

    # Sort by modification time (latest first)
    latest_aligned = max(aligned_files, key=lambda p: p.stat().st_mtime)
    ts_tag = extract_timestamp_suffix(latest_aligned.name)

    # Find matching scorecard
    matching_scorecard = None
    if ts_tag:
        for sc in scorecard_files:
            if ts_tag in sc.name:
                matching_scorecard = sc
                break
    
    if not matching_scorecard and scorecard_files:
        matching_scorecard = max(scorecard_files, key=lambda p: p.stat().st_mtime)

    if not matching_scorecard:
        raise FileNotFoundError(f"Could not find a matching 'analysis_scorecard*.csv' for timestamp tag: {ts_tag}")

    return latest_aligned, matching_scorecard, ts_tag


# -------------------------------------------------------------------------
# 2. CONTINUOUS ANGLE UNWARPER
# -------------------------------------------------------------------------
def unwrap_degrees(series):
    """Unwraps a 0-360 degree series to maintain continuity across boundaries."""
    arr = np.asarray(series, dtype=float)
    if len(arr) == 0:
        return arr
    diff = np.diff(arr)
    adjustment = np.zeros_like(arr)
    adjustment[1:] = np.cumsum(np.where(diff < -180, 360, np.where(diff > 180, -360, 0)))
    return arr + adjustment


# -------------------------------------------------------------------------
# 3. CHART GENERATION FUNCTIONS
# -------------------------------------------------------------------------
def apply_oled_style(fig, axes):
    fig.patch.set_facecolor('#000000')
    if not isinstance(axes, (list, np.ndarray)):
        axes = [axes]
    for ax in np.ravel(axes):
        ax.set_facecolor('#080808')
        ax.tick_params(colors='#e0e0e0', labelsize=10)
        ax.xaxis.label.set_color('#ffffff')
        ax.yaxis.label.set_color('#ffffff')
        ax.title.set_color('#ffffff')
        for spine in ax.spines.values():
            spine.set_color('#333333')
        if ax.legend_:
            plt.setp(ax.legend_.get_texts(), color='#ffffff')
            ax.legend_.get_frame().set_facecolor('#111111')
            ax.legend_.get_frame().set_edgecolor('#333333')


def generate_flight_trajectory(aligned_df, timestamp_str, output_dir):
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    apply_oled_style(fig, axes)

    time_col = 'Time_Min' if 'Time_Min' in aligned_df.columns else aligned_df.index

    # 1. Altitude
    axes[0].plot(aligned_df[time_col], aligned_df['Altitude_Ft'], label='Actual Altitude', color='#00ffcc', linewidth=2)
    if 'Ref_Altitude' in aligned_df.columns:
        axes[0].plot(aligned_df[time_col], aligned_df['Ref_Altitude'], label='Target Altitude', color='#e0e0e0', linestyle='--', linewidth=1.5)
    axes[0].set_ylabel('Altitude (ft)', fontweight='bold')
    axes[0].set_title('Altitude Tracking', loc='left', color='#aaaaaa', fontsize=11)
    axes[0].legend(loc='upper right')
    axes[0].grid(True, color='#222222', linestyle=':')

    # 2. Heading (Continuous Unwrapped + Repeating Y-Axis)
    actual_hdg = unwrap_degrees(aligned_df['Heading_Deg']) if 'Heading_Deg' in aligned_df.columns else unwrap_degrees(aligned_df['Heading'])
    axes[1].plot(aligned_df[time_col], actual_hdg, label='Actual Heading', color='#ffb700', linewidth=2)
    if 'Ref_Heading' in aligned_df.columns:
        ref_hdg = unwrap_degrees(aligned_df['Ref_Heading'])
        axes[1].plot(aligned_df[time_col], ref_hdg, label='Target Heading', color='#e0e0e0', linestyle='--', linewidth=1.5)
    axes[1].set_ylabel('Heading (deg)', fontweight='bold')
    axes[1].yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{int(x % 360)}°"))
    axes[1].set_title('Heading Tracking (Continuous)', loc='left', color='#aaaaaa', fontsize=11)
    axes[1].legend(loc='upper right')
    axes[1].grid(True, color='#222222', linestyle=':')

    # 3. Bank Angle
    axes[2].plot(aligned_df[time_col], aligned_df['Bank_Deg'], label='Actual Bank', color='#ff007f', linewidth=2)
    if 'Ref_Bank' in aligned_df.columns:
        axes[2].plot(aligned_df[time_col], aligned_df['Ref_Bank'], label='Target Bank', color='#e0e0e0', linestyle='--', linewidth=1.5)
    axes[2].set_ylabel('Bank Angle (deg)', fontweight='bold')
    axes[2].set_title('Bank Angle Tracking', loc='left', color='#aaaaaa', fontsize=11)
    axes[2].legend(loc='upper right')
    axes[2].grid(True, color='#222222', linestyle=':')

    # 4. Vertical Speed (VSI)
    vsi_col = 'VerticalSpeed_FPM' if 'VerticalSpeed_FPM' in aligned_df.columns else 'VSI_FPM'
    if vsi_col in aligned_df.columns:
        axes[3].plot(aligned_df[time_col], aligned_df[vsi_col], label='Actual VSI', color='#3399ff', linewidth=2)
    if 'Ref_VSI' in aligned_df.columns:
        axes[3].plot(aligned_df[time_col], aligned_df['Ref_VSI'], label='Target VSI', color='#e0e0e0', linestyle='--', linewidth=1.5)
    axes[3].set_ylabel('VSI (ft/min)', fontweight='bold')
    axes[3].set_xlabel('Time (Minutes)', fontweight='bold')
    axes[3].set_title('Vertical Speed Indicator (VSI) Tracking', loc='left', color='#aaaaaa', fontsize=11)
    axes[3].legend(loc='upper right')
    axes[3].grid(True, color='#222222', linestyle=':')

    plt.tight_layout()
    out_path = output_dir / f"oled_flight_trajectory_{timestamp_str}.png"
    fig.savefig(out_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    print(f"Saved: {out_path.name}")


def generate_pilot_controls(aligned_df, timestamp_str, output_dir):
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    apply_oled_style(fig, axes)

    time_col = 'Time_Min' if 'Time_Min' in aligned_df.columns else aligned_df.index

    # 1. Yoke Roll
    if 'Yoke_Roll_Pct' in aligned_df.columns:
        axes[0].plot(aligned_df[time_col], aligned_df['Yoke_Roll_Pct'], label='Yoke Roll (%)', color='#ff007f', linewidth=1.5)
    axes[0].set_ylabel('Roll (%)', fontweight='bold')
    axes[0].set_title('Control Inputs - Yoke Roll', loc='left', color='#aaaaaa', fontsize=11)
    axes[0].legend(loc='upper right')
    axes[0].grid(True, color='#222222', linestyle=':')

    # 2. Yoke Pitch
    if 'Yoke_Pitch_Pct' in aligned_df.columns:
        axes[1].plot(aligned_df[time_col], aligned_df['Yoke_Pitch_Pct'], label='Yoke Pitch (%)', color='#3399ff', linewidth=1.5)
    axes[1].set_ylabel('Pitch (%)', fontweight='bold')
    axes[1].set_title('Control Inputs - Yoke Pitch', loc='left', color='#aaaaaa', fontsize=11)
    axes[1].legend(loc='upper right')
    axes[1].grid(True, color='#222222', linestyle=':')

    # 3. Rudder
    if 'Rudder_Pct' in aligned_df.columns:
        axes[2].plot(aligned_df[time_col], aligned_df['Rudder_Pct'], label='Rudder (%)', color='#00e676', linewidth=1.5)
    axes[2].set_ylabel('Rudder (%)', fontweight='bold')
    axes[2].set_xlabel('Time (Minutes)', fontweight='bold')
    axes[2].set_title('Control Inputs - Rudder Yaw', loc='left', color='#aaaaaa', fontsize=11)
    axes[2].legend(loc='upper right')
    axes[2].grid(True, color='#222222', linestyle=':')

    plt.tight_layout()
    out_path = output_dir / f"oled_pilot_controls_{timestamp_str}.png"
    fig.savefig(out_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    print(f"Saved: {out_path.name}")


def generate_scorecard_dashboard(aligned_df, scorecard_df, timestamp_str, output_dir):
    fig = plt.figure(figsize=(16, 12))
    apply_oled_style(fig, plt.gca())
    fig.patch.set_facecolor('#000000')

    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.35, wspace=0.3)

    # Segment Scorecard Table / Grid Representation
    ax_table = fig.add_subplot(gs[:, :2])
    ax_table.set_facecolor('#080808')
    ax_table.axis('off')
    ax_table.set_title('Segment-by-Segment Flight Performance Scorecard', loc='left', color='#ffffff', fontsize=14, fontweight='bold', pad=15)

    if not scorecard_df.empty:
        cell_text = []
        col_labels = list(scorecard_df.columns)
        for _, row in scorecard_df.iterrows():
            cell_text.append([str(val) for val in row.values])

        table = ax_table.table(cellText=cell_text, colLabels=col_labels, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.5)

        for (row_idx, col_idx), cell in table.get_celld().items():
            cell.set_edgecolor('#333333')
            if row_idx == 0:
                cell.set_facecolor('#1a1a1a')
                cell.get_text().set_color('#ffffff')
                cell.get_text().set_weight('bold')
            else:
                cell.set_facecolor('#080808')
                cell.get_text().set_color('#e0e0e0')

    # KPI Summary Cards on the Right
    kpi_metrics = [
        ("Heading RMSE", "< 1.5°", "#ffb700"),
        ("Envelope ToL", "> 85%", "#00ffcc"),
        ("Control Spikes", "0 - 2", "#ff007f"),
        ("Ripple Time", "< 3.0s", "#00e676")
    ]

    for idx, (title, criteria, color) in enumerate(kpi_metrics):
        ax_kpi = fig.add_subplot(gs[idx, 2]) if idx < 3 else None
        # Adjust layout for 4 items if needed or map into 3 rows
    
    # Simple summary card blocks on the right column (gs[:, 2])
    gs_right = gridspec.GridSpecFromSubplotSpec(4, 1, subplot_spec=gs[:, 2], hspace=0.4)
    for idx, (title, criteria, color) in enumerate(kpi_metrics):
        ax_card = fig.add_subplot(gs_right[idx])
        ax_card.set_facecolor('#111111')
        ax_card.axis('off')
        for spine in ax_card.spines.values():
            spine.set_color(color)
            spine.set_visible(True)

        ax_card.text(0.05, 0.65, title, color='#aaaaaa', fontsize=11, fontweight='bold', transform=ax_card.transAxes)
        ax_card.text(0.05, 0.25, f"Criteria: {criteria}", color=color, fontsize=13, fontweight='bold', transform=ax_card.transAxes)

    plt.tight_layout()
    out_path = output_dir / f"oled_scorecard_dashboard_{timestamp_str}.png"
    fig.savefig(out_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    print(f"Saved: {out_path.name}")


# -------------------------------------------------------------------------
# 4. MAIN EXECUTION PIPELINE
# -------------------------------------------------------------------------
if __name__ == '__main__':
    try:
        base_dir = Path(__file__).resolve().parent
        aligned_path, scorecard_path, timestamp_str = find_analysis_files(base_dir)

        print(f"Loading Aligned Telemetry: {aligned_path.name}")
        print(f"Loading Scorecard: {scorecard_path.name}")

        aligned_df = pd.read_csv(aligned_path)
        scorecard_df = pd.read_csv(scorecard_path)

        aligned_df['Time_Min'] = (
            pd.to_datetime(aligned_df['Timestamp']) - pd.to_datetime(aligned_df['Timestamp'].iloc[0])
        ).dt.total_seconds() / 60.0

        # Enforce 30-degree target for bank angle during turns (threshold > 2.5 degrees)
        turn_threshold = 2.5
        if 'Ref_Bank' in aligned_df.columns:
            aligned_df['Ref_Bank'] = np.where(
                aligned_df['Ref_Bank'] > turn_threshold, 30.0,
                np.where(aligned_df['Ref_Bank'] < -turn_threshold, -30.0, 0.0)
            )

        # Output charts in parent folder where session CSVs reside
        output_dir = aligned_path.parent

        generate_flight_trajectory(aligned_df, timestamp_str, output_dir)
        generate_pilot_controls(aligned_df, timestamp_str, output_dir)
        generate_scorecard_dashboard(aligned_df, scorecard_df, timestamp_str, output_dir)

        print("\n==================================================")
        print(" PHASE 3 GENERATION COMPLETE")
        print("==================================================")

    except Exception as e:
        print("\n==================================================")
        print(" AN ERROR OCCURRED DURING PHASE 3 EXECUTION")
        print("==================================================")
        traceback.print_exc()
        sys.exit(1)
