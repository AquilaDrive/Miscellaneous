import sys
import re
import traceback
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MultipleLocator, FuncFormatter
from matplotlib.patches import FancyBboxPatch
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
    """Finds latest aligned_telemetry, scorecard, and matching ap_speed_log CSVs."""
    search_dirs = [base_dir, base_dir.parent]
    aligned_files = []
    scorecard_files = []
    disruptor_files = []

    for s_dir in search_dirs:
        if s_dir.exists():
            aligned_files.extend(list(s_dir.glob("aligned_telemetry_analysis*.csv")))
            scorecard_files.extend(list(s_dir.glob("analysis_scorecard*.csv")))
            disruptor_files.extend(list(s_dir.glob("ap_speed_log*.csv")))

    # Deduplicate by resolved path
    aligned_files = list({p.resolve(): p for p in aligned_files}.values())
    scorecard_files = list({p.resolve(): p for p in scorecard_files}.values())
    disruptor_files = list({p.resolve(): p for p in disruptor_files}.values())

    if not aligned_files:
        raise FileNotFoundError(f"No 'aligned_telemetry_analysis*.csv' found.")
    if not scorecard_files:
        raise FileNotFoundError(f"No 'analysis_scorecard*.csv' found.")

    latest_aligned = sorted(aligned_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    ts_tag = extract_timestamp_suffix(latest_aligned.name)

    # Match scorecard and disruptor log with same timestamp tag if available
    matching_sc = [f for f in scorecard_files if ts_tag and ts_tag in f.name]
    scorecard_path = matching_sc[0] if matching_sc else sorted(scorecard_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    matching_dis = [f for f in disruptor_files if ts_tag and ts_tag in f.name]
    disruptor_path = matching_dis[0] if matching_dis else (sorted(disruptor_files, key=lambda p: p.stat().st_mtime, reverse=True)[0] if disruptor_files else None)

    return latest_aligned, scorecard_path, disruptor_path, ts_tag
    
# -------------------------------------------------------------------------
# 2. DESIGN SYSTEM & COLOR IDENTITIES
# -------------------------------------------------------------------------
COLORS = {
    'Altitude': '#00ffcc',   # Cyan / Blue-Green
    'Heading':  '#ffb700',   # Amber
    'Bank':     '#ff007f',   # Magenta / Pink
    'Roll':     '#ff007f',   # Magenta (matches Bank)
    'VSI':      '#3399ff',   # Azure Light Blue
    'Pitch':    '#3399ff',   # Blue (matches VSI)
    'Rudder':   '#00e676',   # Green
    'IAS':      '#7f33ff',   # Deep Electric Indigo (Altitude -> VSI -> Speed Gradient)
    'Ref':      '#a0a0a0',   # Toned-down Gray
    'Pass':     '#00ff66',   # Bright Green
    'Fail':     '#ff3333'    # Bright Red
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


# -------------------------------------------------------------------------
# FIGURE 1: FLIGHT TRAJECTORY TRACKING
# -------------------------------------------------------------------------
def unwrap_degrees(deg_series):
    """Unwraps degree series so transitions across 360->0 extend smoothly (e.g., 350 -> 390)."""
    arr = np.asarray(deg_series, dtype=float)
    if len(arr) == 0:
        return arr
    diff = np.diff(arr)
    diff = (diff + 180) % 360 - 180
    unwrapped = np.empty_like(arr)
    unwrapped[0] = arr[0]
    unwrapped[1:] = arr[0] + np.cumsum(diff)
    return unwrapped

def generate_flight_trajectory(df, ts_str, output_dir: Path):
    fig, axes = plt.subplots(5, 1, figsize=(15, 15), sharex=True)
    apply_dark_style(fig, axes)
    fig.suptitle('PHASE 3: FLIGHT TELEMETRY VS REFERENCE TRAJECTORY', fontsize=16, fontweight='bold', color='#ffffff', y=0.97)

    # 1. Altitude (P1 - Primary Focus)
    axes[0].plot(df['Time_Min'], df['Altitude'], label='Actual Altitude (ft)', color=COLORS['Altitude'], linewidth=1.5)
    axes[0].plot(df['Time_Min'], df['Ref_Alt'], label='Target Ref Altitude (ft)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[0].set_ylabel('Altitude (ft)', fontweight='bold')
    axes[0].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[0].set_title('Altitude Tracking Profile', loc='left', color='#888888', fontsize=11)

    # 2. Vertical Speed (VSI)
    axes[1].plot(df['Time_Min'], df['VSI'], label='Actual VSI (fpm)', color=COLORS['VSI'], linewidth=1.0, alpha=0.9)
    axes[1].plot(df['Time_Min'], df['Ref_VSI'], label='Target Ref VSI (fpm)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[1].set_ylabel('VSI (fpm)', fontweight='bold')
    axes[1].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[1].set_title('Vertical Speed Indicator (VSI) Tracking', loc='left', color='#888888', fontsize=11)

    # 3. Indicated Airspeed (IAS)
    ias_col = 'IAS' if 'IAS' in df.columns else 'Indicated_Airspeed_Kts'
    ref_ias_col = next((col for col in ['Ref_IAS', 'Ref_Speed', 'AP_Target_Speed_Kts', 'AP_Target_Speed'] if col in df.columns), None)

    axes[2].plot(df['Time_Min'], df[ias_col], label='Actual IAS (kts)', color=COLORS['IAS'], linewidth=1.5)
    if ref_ias_col:
        axes[2].plot(df['Time_Min'], df[ref_ias_col], label='AP Target Speed (kts)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[2].set_ylabel('IAS (kts)', fontweight='bold')
    axes[2].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[2].set_title('Airspeed Tracking Profile & AP Target Speed', loc='left', color='#888888', fontsize=11)

    # 4. Bank Angle
    axes[3].plot(df['Time_Min'], df['Bank'], label='Actual Bank (°)', color=COLORS['Bank'], linewidth=1.2)
    axes[3].plot(df['Time_Min'], df['Ref_Bank'], label='Target Ref Bank (±30° Turns)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[3].set_ylabel('Bank Angle (°)', fontweight='bold')
    axes[3].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[3].set_title('Bank Angle & Roll Execution (Target: 30° in Turns)', loc='left', color='#888888', fontsize=11)

    # 5. Heading (Continuous Angle Logic)
    unwrapped_hdg = unwrap_degrees(df['Heading'])
    unwrapped_ref_hdg = unwrap_degrees(df['Ref_Hdg'])

    if len(unwrapped_hdg) > 0 and len(unwrapped_ref_hdg) > 0:
        offset_360 = np.round(np.nanmean(unwrapped_hdg - unwrapped_ref_hdg) / 360.0) * 360.0
        unwrapped_hdg -= offset_360

    axes[4].plot(df['Time_Min'], unwrapped_hdg, label='Actual Heading (°)', color=COLORS['Heading'], linewidth=1.5)
    axes[4].plot(df['Time_Min'], unwrapped_ref_hdg, label='Target Ref Heading (°)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[4].set_ylabel('Heading (°)', fontweight='bold')
    axes[4].set_xlabel('Flight Time (Minutes)', fontweight='bold', fontsize=12)
    axes[4].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[4].set_title('Heading Tracking Profile (Continuous Angle Logic)', loc='left', color='#888888', fontsize=11)
    
    axes[4].yaxis.set_major_locator(MultipleLocator(90))
    axes[4].yaxis.set_major_formatter(
        FuncFormatter(
            lambda x, pos: (
                f"{int(x)}°"
                if (int(x) % 360 == 0 and x > 0)
                else f"{int(x % 360)}°"
            )
        )
    )

    plt.tight_layout()
    plt.subplots_adjust(top=0.94)
    out_filename = f'graph_flight_trajectory_{ts_str}.png' if ts_str else 'graph_flight_trajectory.png'
    out_path = output_dir / out_filename
    fig.savefig(out_path, dpi=300, facecolor='#000000', edgecolor='none')
    plt.show()
    plt.close(fig)
    print(f"[Generated] {out_path.resolve()}")

# -------------------------------------------------------------------------
# FIGURE 2: PILOT CONTROL INPUTS
# -------------------------------------------------------------------------
def generate_pilot_controls(df, ts_str, output_dir: Path):
    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True)
    apply_dark_style(fig, axes)
    fig.suptitle('PHASE 3: PILOT CONTROL INPUTS & WORKLOAD DYNAMICS', fontsize=16, fontweight='bold', color='#ffffff', y=0.97)

    # Aileron (Roll Pct - Matches Bank color)
    axes[0].plot(df['Time_Min'], df['Yoke_Roll_Pct'], color=COLORS['Roll'], linewidth=1.0)
    axes[0].set_ylabel('Yoke Roll (%)', fontweight='bold')
    axes[0].set_title('Aileron Control Input (Yoke Roll %)', loc='left', color='#888888', fontsize=11)
    axes[0].axhline(0, color='#444444', linestyle=':', linewidth=1)

    # Elevator (Pitch Pct - Matches VSI color)
    axes[1].plot(df['Time_Min'], df['Yoke_Pitch_Pct'], color=COLORS['Pitch'], linewidth=1.0)
    axes[1].set_ylabel('Yoke Pitch (%)', fontweight='bold')
    axes[1].set_title('Elevator Control Input (Yoke Pitch %)', loc='left', color='#888888', fontsize=11)
    axes[1].axhline(0, color='#444444', linestyle=':', linewidth=1)

    # Rudder (Yaw Pct - Unique Green)
    axes[2].plot(df['Time_Min'], df['Rudder_Pct'], color=COLORS['Rudder'], linewidth=1.0)
    axes[2].set_ylabel('Rudder (%)', fontweight='bold')
    axes[2].set_xlabel('Flight Time (Minutes)', fontweight='bold', fontsize=12)
    axes[2].set_title('Rudder Pedal Input (%)', loc='left', color='#888888', fontsize=11)
    axes[2].axhline(0, color='#444444', linestyle=':', linewidth=1)

    plt.tight_layout()
    plt.subplots_adjust(top=0.92)
    out_filename = f'graph_pilot_controls_{ts_str}.png' if ts_str else 'graph_pilot_controls.png'
    out_path = output_dir / out_filename
    fig.savefig(out_path, dpi=300, facecolor='#000000', edgecolor='none')
    plt.show()
    plt.close(fig)
    print(f"[Generated] {out_path.resolve()}")


# -------------------------------------------------------------------------
# FIGURE 3: UNIFIED SCORECARD (SEGMENTS + ERRORS + LARGE FONT KPI EVALS)
# -------------------------------------------------------------------------
def generate_scorecard_dashboard(aln_df, sc_df, ts_str, output_dir: Path):
    seg_df = sc_df[sc_df['Phase_Segment'] != 'Overall Flight'].copy()

    # Session RMSE and envelope tolerance (calculated directly from time-series)
    # Compute true pooled session RMSE directly across all aligned datapoints
    sess_rmse_alt = float(np.sqrt(np.mean(aln_df['Alt_Err'] ** 2)))
    sess_rmse_vsi = float(np.sqrt(np.mean(aln_df['VSI_Err'] ** 2)))
    sess_rmse_hdg = float(np.sqrt(np.mean(aln_df['Hdg_Err'] ** 2)))

    # Compute true pooled fine tolerance percentages across all datapoints
    TOL_FINE = {'Hdg': 2.0, 'Bank': 3.0, 'Alt': 50.0}
    sess_tol_alt = float((np.abs(aln_df['Alt_Err']) <= TOL_FINE['Alt']).mean() * 100.0)
    sess_tol_hdg = float((np.abs(aln_df['Hdg_Err']) <= TOL_FINE['Hdg']).mean() * 100.0)
    sess_tol_bnk = float((np.abs(aln_df['Bank_Err']) <= TOL_FINE['Bank']).mean() * 100.0)

    # Retrieve event-based indicators (Spikes & Ripple Time/Count) from overall scorecard row
    overall_row = sc_df[sc_df['Phase_Segment'] == 'Overall Flight']
    if not overall_row.empty:
        spikes_val = int(overall_row['Spikes'].values[0]) if 'Spikes' in overall_row else 0
        ripple_val = float(overall_row['Ripple_Time'].values[0]) if 'Ripple_Time' in overall_row else 0.0
        ripple_cnt = int(overall_row['Ripple_Count'].values[0]) if ('Ripple_Count' in overall_row and pd.notna(overall_row['Ripple_Count'].values[0])) else None
    else:
        spikes_val = 0
        ripple_val = 0.0
        ripple_cnt = None

    # Overall Session Envelope ToL (Average across dimensions)
    sess_tol_env = np.mean([sess_tol_alt, sess_tol_hdg, sess_tol_bnk])
    
    # Normalized Composite RMSE Index (Combined across units: Hdg/1.5, Alt/50, VSI/100)
    composite_rmse_idx = (sess_rmse_hdg / 1.5 + sess_rmse_alt / 50.0 + sess_rmse_vsi / 100.0) / 3.0

    # Evaluate Pass Requirements
    env_pass    = sess_tol_env > 85.0
    spikes_pass = spikes_val <= 2
    ripple_pass = ripple_val < 3.0

    # 3x3 Grid Layout Setup
    fig = plt.figure(figsize=(18, 13))
    gs = gridspec.GridSpec(3, 3, height_ratios=[1.2, 1.2, 1.0], width_ratios=[1.4, 1.4, 1.0])
    
    ax_rmse    = fig.add_subplot(gs[0, :2])
    ax_kpi_val = fig.add_subplot(gs[0, 2])
    ax_tol     = fig.add_subplot(gs[1, :2])
    ax_kpi_req = fig.add_subplot(gs[1, 2])
    ax_err_alt = fig.add_subplot(gs[2, 0])
    ax_err_hdg = fig.add_subplot(gs[2, 1])
    ax_err_bnk = fig.add_subplot(gs[2, 2])

    apply_dark_style(fig, [ax_rmse, ax_tol, ax_err_alt, ax_err_hdg, ax_err_bnk])
    for kpi_ax in [ax_kpi_val, ax_kpi_req]:
        kpi_ax.set_facecolor('#0d0d0d')
        for spine in kpi_ax.spines.values():
            spine.set_color('#333333')
        kpi_ax.set_xticks([])
        kpi_ax.set_yticks([])

    fig.suptitle('PHASE 3: PERFORMANCE SCORECARD & ERROR ANALYSIS', fontsize=16, fontweight='bold', color='#ffffff', y=0.97)

    # 1. Segment RMSE Bar Chart
    x = np.arange(len(seg_df))
    width = 0.25
    ax_rmse.bar(x - width, seg_df['RMSE_Alt_Ft'], width, label='Altitude RMSE (ft)', color=COLORS['Altitude'], alpha=0.9)
    ax_rmse.bar(x, seg_df['RMSE_VSI_FPM'], width, label='VSI RMSE (fpm)', color=COLORS['VSI'], alpha=0.9)
    ax_rmse.bar(x + width, seg_df['RMSE_Hdg_Deg'] * 10, width, label='Heading RMSE (° × 10)', color=COLORS['Heading'], alpha=0.9)
    ax_rmse.set_ylabel('RMSE Magnitude', fontweight='bold')
    ax_rmse.set_title('Root Mean Square Error by Segment (Heading Scaled 10x)', loc='left', color='#888888', fontsize=11)
    ax_rmse.set_xticks(x)
    ax_rmse.set_xticklabels(seg_df['Phase_Segment'], rotation=35, ha='right')
    ax_rmse.legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')

    # 2. Large Font Session RMSE & Composite KPI Card
    ax_kpi_val.text(0.08, 0.88, "SESSION RMSE EVALUATIONS", color='#ffffff', fontsize=12, fontweight='bold', transform=ax_kpi_val.transAxes)
    ax_kpi_val.text(0.08, 0.70, f"Altitude:  {sess_rmse_alt:.1f} ft  [< 50.0]", color=COLORS['Altitude'], fontsize=14, fontweight='bold', transform=ax_kpi_val.transAxes)
    ax_kpi_val.text(0.08, 0.54, f"VSI:       {sess_rmse_vsi:.1f} fpm  [< 100.0]", color=COLORS['VSI'], fontsize=14, fontweight='bold', transform=ax_kpi_val.transAxes)
    ax_kpi_val.text(0.08, 0.38, f"Heading:   {sess_rmse_hdg:.2f}°  [< 1.50]", color=COLORS['Heading'], fontsize=14, fontweight='bold', transform=ax_kpi_val.transAxes)
    
    comp_color = COLORS['Pass'] if composite_rmse_idx < 1.0 else COLORS['Fail']
    ax_kpi_val.text(0.08, 0.18, "COMPOSITE RMSE INDEX", color='#888888', fontsize=10, transform=ax_kpi_val.transAxes)
    ax_kpi_val.text(0.08, 0.05, f"{composite_rmse_idx:.2f}  [{'OPTIMAL' if composite_rmse_idx<1 else 'ELEVATED'}]", color=comp_color, fontsize=16, fontweight='bold', transform=ax_kpi_val.transAxes)

    # 3. Segment Fine Tolerance Line Chart
    ax_tol.plot(x, seg_df['Alt_In_Fine_Pct'], marker='s', linewidth=2.5, label='Altitude ToL (%)', color=COLORS['Altitude'])
    ax_tol.plot(x, seg_df['Hdg_In_Fine_Pct'], marker='o', linewidth=2.5, label='Heading ToL (%)', color=COLORS['Heading'])
    ax_tol.plot(x, seg_df['Bank_In_Fine_Pct'], marker='^', linewidth=2.5, label='Bank ToL (%)', color=COLORS['Bank'])
    ax_tol.set_ylabel('% Time in Fine Tolerance', fontweight='bold')
    ax_tol.set_title('Percentage of Segment Within Precision Tolerances', loc='left', color='#888888', fontsize=11)
    ax_tol.set_xticks(x)
    ax_tol.set_xticklabels(seg_df['Phase_Segment'], rotation=35, ha='right')
    ax_tol.legend(loc='lower right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    ax_tol.set_ylim(-5, 105)

    # 4. Large Font Session ToL & Pass/Fail Requirements Card
    ax_kpi_req.text(0.05, 0.91, "SESSION ENVELOPE TOLERANCE [>85%]", color='#ffffff', fontsize=11, fontweight='bold', transform=ax_kpi_req.transAxes)
    # Sub-tile positions: (x, y, title, val, color)
    tiles = [
        (0.05, 0.56, "ALT TOL", sess_tol_alt, COLORS['Altitude']),
        (0.52, 0.56, "HDG TOL", sess_tol_hdg, COLORS['Heading']),
        (0.05, 0.24, "BANK TOL", sess_tol_bnk, COLORS['Bank']),
        (0.52, 0.24, "COMBINED", sess_tol_env, COLORS['Pass'] if env_pass else COLORS['Fail'])
    ]
    for x_pos, y_pos, label, val, color in tiles:
        # Draw uniform background sub-tile box using FancyBboxPatch
        rect = FancyBboxPatch(
            (x_pos, y_pos), 0.43, 0.29,
            transform=ax_kpi_req.transAxes,
            facecolor='#141414',
            edgecolor='#2a2a2a',
            boxstyle='round,pad=0.0,rounding_size=0.02',
            clip_on=False
        )
        ax_kpi_req.add_patch(rect) 
        # Label Header
        ax_kpi_req.text(x_pos + 0.04, y_pos + 0.19, label, color='#888888', fontsize=9, fontweight='bold', transform=ax_kpi_req.transAxes)
        # Metric Percentage Value & Status
        status_txt = "PASS" if val >= 85.0 else "FAIL"
        ax_kpi_req.text(x_pos + 0.04, y_pos + 0.05, f"{val:.1f}% [{status_txt}]", color=color, fontsize=12, fontweight='bold', transform=ax_kpi_req.transAxes)
    # Status indicators & colors
    spk_status = "PASS" if spikes_pass else "FAIL"
    spk_color = COLORS['Pass'] if spikes_pass else COLORS['Fail']
    rip_status = "PASS" if ripple_pass else "FAIL"
    rip_color = COLORS['Pass'] if ripple_pass else COLORS['Fail']
    # Dedicated Line 1: Spikes with [0-2] Target
    ax_kpi_req.text(0.05, 0.13, f"Spikes [0–2]: {spikes_val}  [{spk_status}]", color=spk_color, fontsize=10.5, fontweight='bold', transform=ax_kpi_req.transAxes)
    # Dedicated Line 2: Ripple Metrics (Count prepended before combined time if available)
    if ripple_cnt is not None:
        ripple_str = f"Ripple [< 3.0s]: {ripple_cnt} cnt | {ripple_val:.1f}s  [{rip_status}]"
    else:
        ripple_str = f"Ripple [< 3.0s]: {ripple_val:.1f}s  [{rip_status}]"
    ax_kpi_req.text(0.05, 0.04, ripple_str, color=rip_color, fontsize=10.5, fontweight='bold', transform=ax_kpi_req.transAxes)

    # 5. Error Density Histograms (Bottom Row)
    sns.histplot(aln_df['Alt_Err'], kde=True, ax=ax_err_alt, color=COLORS['Altitude'], bins=35, edgecolor='#000000', alpha=0.7)
    ax_err_alt.set_title('Altitude Error (ft) Density', color='#888888', fontsize=10)
    ax_err_alt.set_xlabel('Error (ft)', fontweight='bold')
    ax_err_alt.set_ylabel('Frequency', fontweight='bold')
    ax_err_alt.axvline(0, color='#ffffff', linestyle='--', linewidth=1.2)

    sns.histplot(aln_df['Hdg_Err'], kde=True, ax=ax_err_hdg, color=COLORS['Heading'], bins=35, edgecolor='#000000', alpha=0.7)
    ax_err_hdg.set_title('Heading Error (°) Density', color='#888888', fontsize=10)
    ax_err_hdg.set_xlabel('Error (°)', fontweight='bold')
    ax_err_hdg.set_ylabel('')
    ax_err_hdg.axvline(0, color='#ffffff', linestyle='--', linewidth=1.2)

    sns.histplot(aln_df['Bank_Err'], kde=True, ax=ax_err_bnk, color=COLORS['Bank'], bins=35, edgecolor='#000000', alpha=0.7)
    ax_err_bnk.set_title('Bank Error (°) Density', color='#888888', fontsize=10)
    ax_err_bnk.set_xlabel('Error (°)', fontweight='bold')
    ax_err_bnk.set_ylabel('')
    ax_err_bnk.axvline(0, color='#ffffff', linestyle='--', linewidth=1.2)

    plt.tight_layout()
    plt.subplots_adjust(top=0.93, hspace=0.35, wspace=0.22)
    out_filename = f'graph_scorecard_{ts_str}.png' if ts_str else 'graph_scorecard.png'
    out_path = output_dir / out_filename
    fig.savefig(out_path, dpi=300, facecolor='#000000', edgecolor='none')
    plt.show()
    plt.close(fig)
    print(f"[Generated] {out_path.resolve()}")


# -------------------------------------------------------------------------
# 3. EXECUTE DASHBOARD GENERATION
# -------------------------------------------------------------------------
if __name__ == '__main__':
    try:
        work_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()

        aligned_path, scorecard_path, disruptor_path, timestamp_str = find_analysis_files(work_dir)

        print("==================================================")
        print(" PHASE 3: CHART GENERATION")
        print("==================================================")
        print(f" Aligned Telemetry File : {aligned_path.resolve()}")
        print(f" Performance Scorecard  : {scorecard_path.resolve()}")
        if disruptor_path:
            print(f" AP Disruptor Log File  : {disruptor_path.resolve()}")

        aligned_df = pd.read_csv(aligned_path)
        scorecard_df = pd.read_csv(scorecard_path)

        # Parse Timestamps
        aligned_df['Timestamp'] = pd.to_datetime(aligned_df['Timestamp'])

        default_ias_target = 300.0
        # Merge AP Speed Disruptor Target if log exists
        if disruptor_path and disruptor_path.exists():
            disruptor_df = pd.read_csv(disruptor_path)
            disruptor_df['Timestamp'] = pd.to_datetime(disruptor_df['Timestamp'])
            
            # Sort both DataFrames by timestamp before merge_asof
            aligned_df = aligned_df.sort_values('Timestamp')
            disruptor_df = disruptor_df.sort_values('Timestamp')
            
            # Stepwise backward fill AP Target Speed onto aligned telemetry timeline
            aligned_df = pd.merge_asof(
                aligned_df,
                disruptor_df[['Timestamp', 'AP_Target_Speed_Kts']],
                on='Timestamp',
                direction='backward'
            )
            # Fill records prior to the first log timestamp with Phase 1 default speed
            aligned_df['AP_Target_Speed_Kts'] = aligned_df['AP_Target_Speed_Kts'].fillna(default_ias_target)
        else:
            # Fallback for full duration if disruptor log is missing
            aligned_df['AP_Target_Speed_Kts'] = default_ias_target

        # Compute relative flight time in minutes
        aligned_df['Time_Min'] = (
            aligned_df['Timestamp'] - aligned_df['Timestamp'].iloc[0]
        ).dt.total_seconds() / 60.0

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
        print(f"Error Details: {e}")
        traceback.print_exc()
        sys.exit(1)
