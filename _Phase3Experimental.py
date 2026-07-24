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
        raise FileNotFoundError(
            f"No 'aligned_telemetry_analysis*.csv' found in {base_dir.resolve()} or its parent directory."
        )
    if not scorecard_files:
        raise FileNotFoundError(
            f"No 'analysis_scorecard*.csv' found in {base_dir.resolve()} or its parent directory."
        )

    # Pick the most recently modified aligned telemetry analysis file
    latest_aligned = sorted(
        aligned_files, key=lambda p: p.stat().st_mtime, reverse=True
    )[0]
    ts_tag = extract_timestamp_suffix(latest_aligned.name)

    # Match corresponding scorecard with same timestamp tag if available
    matching_sc = [f for f in scorecard_files if ts_tag and ts_tag in f.name]
    scorecard_path = (
        matching_sc[0]
        if matching_sc
        else sorted(scorecard_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    )

    return latest_aligned, scorecard_path, ts_tag


# -------------------------------------------------------------------------
# 2. DESIGN SYSTEM & COLOR IDENTITIES
# -------------------------------------------------------------------------
COLORS = {
    'Altitude': '#00ffcc',   # Bright Cyan
    'Heading':  '#ffb700',   # Amber
    'Bank':     '#ff007f',   # Magenta / Pink
    'Roll':     '#ff007f',   # Magenta (matches Bank)
    'VSI':      '#3399ff',   # Blue
    'Pitch':    '#3399ff',   # Blue (matches Elevator/VSI)
    'Rudder':   '#00e676',   # Green (unique to Yaw)
    'Ref':      '#e0e0e0',   # Dashed Light Grey for target trajectory
    'Pass':     '#00ff66',   # Bright Green badge
    'Fail':     '#ff3333'    # Bright Red badge
}

def apply_dark_style(fig, axes):
    """Applies clean, high-contrast dark styling to figure and axes."""
    fig.patch.set_facecolor('#000000')
    if not isinstance(axes, (list, np.ndarray)):
        axes = [axes]
    for ax in np.ravel(axes):
        ax.set_facecolor('#080808')
        ax.tick_params(colors='#c0c0c0', labelsize=10)
        ax.xaxis.label.set_color('#ffffff')
        ax.yaxis.label.set_color('#ffffff')
        ax.title.set_color('#ffffff')
        for spine in ax.spines.values():
            spine.set_color('#2a2a2a')
        ax.grid(True, color='#181818', linestyle='--', alpha=0.8)


def unwrap_degrees(series):
    """Unwraps degree values to maintain continuity across 360->0 boundaries."""
    arr = np.asarray(series, dtype=float)
    if len(arr) == 0:
        return arr
    rad = np.radians(arr)
    unwrapped_rad = np.unwrap(rad)
    return np.degrees(unwrapped_rad)


# -------------------------------------------------------------------------
# FIGURE 1: FLIGHT TRAJECTORY TRACKING
# -------------------------------------------------------------------------
def generate_flight_trajectory(df, ts_str, output_dir: Path):
    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
    apply_dark_style(fig, axes)
    fig.suptitle('PHASE 3: FLIGHT TELEMETRY VS REFERENCE TRAJECTORY', fontsize=16, fontweight='bold', color='#ffffff', y=0.97)

    # Altitude
    axes[0].plot(df['Time_Min'], df['Altitude'], label='Actual Altitude (ft)', color=COLORS['Altitude'], linewidth=1.5)
    axes[0].plot(df['Time_Min'], df['Ref_Alt'], label='Target Ref Altitude (ft)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[0].set_ylabel('Altitude (ft)', fontweight='bold')
    axes[0].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[0].set_title('Altitude Tracking Profile', loc='left', color='#888888', fontsize=11)

    # Heading (Continuous angle unwrapping + repeating 0-360 legend axis)
    unwrapped_hdg = unwrap_degrees(df['Heading'])
    unwrapped_ref_hdg = unwrap_degrees(df['Ref_Hdg'])

    axes[1].plot(df['Time_Min'], unwrapped_hdg, label='Actual Heading (°)', color=COLORS['Heading'], linewidth=1.5)
    axes[1].plot(df['Time_Min'], unwrapped_ref_hdg, label='Target Ref Heading (°)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[1].set_ylabel('Heading (°)', fontweight='bold')

    def heading_formatter(x, pos):
        val = int(round(x)) % 360
        if val == 0 and x != 0 and x % 360 == 0:
            return '360°'
        return f"{val}°"

    axes[1].yaxis.set_major_formatter(FuncFormatter(heading_formatter))
    axes[1].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[1].set_title('Heading Tracking Profile (Continuous Unwrapped)', loc='left', color='#888888', fontsize=11)

    # Bank Angle (with 30° turn target enforcement)
    axes[2].plot(df['Time_Min'], df['Bank'], label='Actual Bank (°)', color=COLORS['Bank'], linewidth=1.2)
    axes[2].plot(df['Time_Min'], df['Ref_Bank'], label='Target Ref Bank (±30° Turns)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[2].set_ylabel('Bank Angle (°)', fontweight='bold')
    axes[2].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[2].set_title('Bank Angle & Roll Execution (Target: 30° in Turns)', loc='left', color='#888888', fontsize=11)

    # Vertical Speed (VSI)
    axes[3].plot(df['Time_Min'], df['VSI'], label='Actual VSI (fpm)', color=COLORS['VSI'], linewidth=1.5)
    axes[3].plot(df['Time_Min'], df['Ref_VSI'], label='Target Ref VSI (fpm)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[3].set_ylabel('Vertical Speed (fpm)', fontweight='bold')
    axes[3].set_xlabel('Time (Minutes)', fontweight='bold')
    axes[3].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[3].set_title('Vertical Speed Indicator (VSI) Tracking', loc='left', color='#888888', fontsize=11)

    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
    out_path = output_dir / f"oled_flight_trajectory_{ts_str}.png"
    fig.savefig(out_path, dpi=300, facecolor='#000000', edgecolor='none')
    plt.close(fig)
    print(f"[Saved] Flight Trajectory -> {out_path}")


# -------------------------------------------------------------------------
# FIGURE 2: PILOT CONTROL INPUTS
# -------------------------------------------------------------------------
def generate_pilot_controls(df, ts_str, output_dir: Path):
    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True)
    apply_dark_style(fig, axes)
    fig.suptitle('PHASE 3: PILOT CONTROL INPUTS & EXECUTION SMOOTHNESS', fontsize=16, fontweight='bold', color='#ffffff', y=0.96)

    # Yoke Roll (Aileron)
    if 'Yoke_Roll_Pct' in df.columns:
        axes[0].plot(df['Time_Min'], df['Yoke_Roll_Pct'], label='Yoke Roll (%)', color=COLORS['Roll'], linewidth=1.2)
        axes[0].set_ylabel('Roll Control (%)', fontweight='bold')
        axes[0].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
        axes[0].set_title('Aileron / Yoke Roll Deflection', loc='left', color='#888888', fontsize=11)

    # Yoke Pitch (Elevator)
    if 'Yoke_Pitch_Pct' in df.columns:
        axes[1].plot(df['Time_Min'], df['Yoke_Pitch_Pct'], label='Yoke Pitch (%)', color=COLORS['Pitch'], linewidth=1.2)
        axes[1].set_ylabel('Pitch Control (%)', fontweight='bold')
        axes[1].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
        axes[1].set_title('Elevator / Yoke Pitch Deflection', loc='left', color='#888888', fontsize=11)

    # Rudder (Yaw)
    if 'Rudder_Pct' in df.columns:
        axes[2].plot(df['Time_Min'], df['Rudder_Pct'], label='Rudder (%)', color=COLORS['Rudder'], linewidth=1.2)
        axes[2].set_ylabel('Rudder (%)', fontweight='bold')
        axes[2].set_xlabel('Time (Minutes)', fontweight='bold')
        axes[2].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
        axes[2].set_title('Rudder Pedal Coordination Deflection', loc='left', color='#888888', fontsize=11)

    plt.tight_layout()
    plt.subplots_adjust(top=0.91)
    out_path = output_dir / f"oled_pilot_controls_{ts_str}.png"
    fig.savefig(out_path, dpi=300, facecolor='#000000', edgecolor='none')
    plt.close(fig)
    print(f"[Saved] Pilot Controls -> {out_path}")


# -------------------------------------------------------------------------
# FIGURE 3: SCORECARD DASHBOARD
# -------------------------------------------------------------------------
def generate_scorecard_dashboard(aligned_df, scorecard_df, ts_str, output_dir: Path):
    fig = plt.figure(figsize=(16, 11))
    fig.patch.set_facecolor('#000000')

    gs = gridspec.GridSpec(3, 3, figure=fig, height_ratios=[1.2, 1.2, 1.0], width_ratios=[1.5, 1.5, 1.2])

    # 1. Segment Scorecard Table (Span top 2 columns, row 0-1)
    ax_table = fig.add_subplot(gs[0:2, 0:2])
    ax_table.set_facecolor('#080808')
    ax_table.axis('off')

    table_data = []
    columns = ['Segment', 'Alt RMSE', 'Hdg RMSE', 'VSI RMSE', 'Alt ToL %', 'Hdg ToL %']
    
    seg_df = scorecard_df[scorecard_df['Segment'] != 'Overall Flight'].copy()
    for _, row in seg_df.iterrows():
        table_data.append([
            row.get('Segment', 'N/A'),
            f"{row.get('RMSE_Alt_Ft', 0):.1f} ft",
            f"{row.get('RMSE_Hdg_Deg', 0):.2f}°",
            f"{row.get('RMSE_VSI_FPM', 0):.0f} fpm",
            f"{row.get('Alt_In_Fine_Pct', 0):.1f}%",
            f"{row.get('Hdg_In_Fine_Pct', 0):.1f}%"
        ])

    if table_data:
        table = ax_table.table(cellText=table_data, colLabels=columns, loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)

        for key, cell in table.get_celld().items():
            cell.set_facecolor('#121212' if key[0] > 0 else '#1f1f1f')
            cell.set_edgecolor('#2a2a2a')
            text = cell.get_text()
            text.set_color('#ffffff' if key[0] == 0 else '#cccccc')
            if key[0] == 0:
                text.set_weight('bold')

    ax_table.set_title('FLIGHT SEGMENT PERFORMANCE SCORECARD', loc='left', color='#ffffff', fontsize=12, fontweight='bold', pad=15)

    # 2. Error Distribution Bar / Line Chart (Row 2, cols 0-1)
    ax_err = fig.add_subplot(gs[2, 0:2])
    ax_err.set_facecolor('#080808')
    apply_dark_style(fig, ax_err)

    if not seg_df.empty and 'Phase_Segment' in seg_df.columns:
        x = np.arange(len(seg_df))
        ax_err.plot(x, seg_df['Alt_In_Fine_Pct'], marker='o', linewidth=2.5, label='Alt ToL (%)', color=COLORS['Altitude'])
        ax_err.plot(x, seg_df['Hdg_In_Fine_Pct'], marker='s', linewidth=2.5, label='Hdg ToL (%)', color=COLORS['Heading'])
        ax_err.plot(x, seg_df['Bank_In_Fine_Pct'], marker='^', linewidth=2.5, label='Bank ToL (%)', color=COLORS['Bank'])
        ax_err.set_ylabel('% Time in Fine Tolerance', fontweight='bold', color='#ffffff')
        ax_err.set_title('Percentage of Segment Within Precision Tolerances', loc='left', color='#888888', fontsize=11)
        ax_err.set_xticks(x)
        ax_err.set_xticklabels(seg_df['Phase_Segment'], rotation=25, ha='right', color='#cccccc')
        ax_err.legend(loc='lower right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
        ax_err.set_ylim(-5, 105)

    # 3. Overall Session RMSE & ToL Evaluations KPI Card (Column 2, rows 0-2)
    ax_kpi = fig.add_subplot(gs[:, 2])
    ax_kpi.set_facecolor('#080808')
    ax_kpi.axis('off')
    apply_dark_style(fig, ax_kpi)

    overall_row = scorecard_df[scorecard_df['Segment'] == 'Overall Flight']
    if not overall_row.empty:
        r_alt = overall_row['RMSE_Alt_Ft'].values[0]
        r_hdg = overall_row['RMSE_Hdg_Deg'].values[0]
        r_vsi = overall_row['RMSE_VSI_FPM'].values[0]
        tol_alt = overall_row['Alt_In_Fine_Pct'].values[0]
        tol_hdg = overall_row['Hdg_In_Fine_Pct'].values[0]
        tol_bnk = overall_row['Bank_In_Fine_Pct'].values[0]
        spikes = int(overall_row['Spikes'].values[0]) if 'Spikes' in overall_row.columns else 0
        ripple = overall_row['Ripple_Time'].values[0] if 'Ripple_Time' in overall_row.columns else 1.2
    else:
        r_alt, r_hdg, r_vsi = seg_df['RMSE_Alt_Ft'].mean(), seg_df['RMSE_Hdg_Deg'].mean(), seg_df['RMSE_VSI_FPM'].mean()
        tol_alt, tol_hdg, tol_bnk = seg_df['Alt_In_Fine_Pct'].mean(), seg_df['Hdg_In_Fine_Pct'].mean(), seg_df['Bank_In_Fine_Pct'].mean()
        spikes, ripple = 0, 1.2

    tol_env = np.mean([tol_alt, tol_hdg, tol_bnk])
    composite_idx = (r_hdg / 1.5 + r_alt / 50.0 + r_vsi / 100.0) / 3.0

    # Pass/Fail Criteria
    hdg_pass = r_hdg < 1.5
    env_pass = tol_env > 85.0
    spikes_pass = spikes <= 2
    ripple_pass = ripple < 3.0

    kpi_text = (
        "OVERALL SESSION EVALUATION\n"
        "----------------------------------------\n"
        f"• Altitude RMSE:   {r_alt:.1f} ft\n"
        f"• Heading RMSE:    {r_hdg:.2f}° {'[PASS]' if hdg_pass else '[FAIL]'}\n"
        f"• VSI RMSE:        {r_vsi:.0f} fpm\n"
        f"• Envelope ToL:    {tol_env:.1f}% {'[PASS]' if env_pass else '[FAIL]'}\n"
        f"• Control Spikes:  {spikes} {'[PASS]' if spikes_pass else '[FAIL]'}\n"
        f"• Ripple Time:     {ripple:.1f}s {'[PASS]' if ripple_pass else '[FAIL]'}\n"
        "----------------------------------------\n"
        f"Composite Error Index: {composite_idx:.2f}"
    )

    ax_kpi.text(0.05, 0.95, kpi_text, transform=ax_kpi.transAxes, fontsize=11, fontweight='bold',
                color='#ffffff', verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.8', facecolor='#121212', edgecolor='#2a2a2a', linewidth=1.5))

    plt.tight_layout()
    out_path = output_dir / f"oled_scorecard_dashboard_{ts_str}.png"
    fig.savefig(out_path, dpi=300, facecolor='#000000', edgecolor='none')
    plt.close(fig)
    print(f"[Saved] Scorecard Dashboard -> {out_path}")


# -------------------------------------------------------------------------
# MAIN EXECUTION ROUTINE
# -------------------------------------------------------------------------
if __name__ == '__main__':
    try:
        base_dir = Path(__file__).parent if '__file__' in locals() else Path.cwd()
        aligned_path, scorecard_path, timestamp_str = find_analysis_files(base_dir)

        print("==================================================")
        print(" PHASE 3 CHART GENERATOR (OLED THEME)")
        print(f" Loaded Telemetry : {aligned_path.name}")
        print(f" Loaded Scorecard : {scorecard_path.name}")
        print(f" Session Tag      : {timestamp_str}")
        print("==================================================")

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

        output_dir = aligned_path.parent

        generate_flight_trajectory(aligned_df, timestamp_str, output_dir)
        generate_pilot_controls(aligned_df, timestamp_str, output_dir)
        generate_scorecard_dashboard(aligned_df, scorecard_df, timestamp_str, output_dir)

        print("\n==================================================")
        print(" PHASE 3 GENERATION COMPLETE")
        print("==================================================")

    except Exception as e:
        print("\n==================================================")
        print(" AN ERROR OCCURRED DURING PHASE 3 GENERATION")
        print("==================================================")
        traceback.print_exc()
        sys.exit(1)
