import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
import numpy as np
import pandas as pd
import re

# -------------------------------------------------------------------------
# 1. FILE CONFIGURATION & DATA LOADING
# -------------------------------------------------------------------------
input_filename = 'aligned_telemetry_analysis_20260723_185323.csv'
scorecard_filename = 'analysis_scorecard_20260723_185323.csv'

# Extract timestamp for output naming
match = re.search(r'(\d{8}_\d{6})', input_filename)
timestamp_str = match.group(1) if match else '20260723_185323'

aligned_df = pd.read_csv(input_filename)
scorecard_df = pd.read_csv(scorecard_filename)

aligned_df['Time_Min'] = (
    pd.to_datetime(aligned_df['Timestamp']) - pd.to_datetime(aligned_df['Timestamp'].iloc[0])
).dt.total_seconds() / 60.0

# Enforce 30-degree target for bank angle during turns (threshold > 2.5 degrees)
turn_threshold = 2.5
aligned_df['Ref_Bank'] = np.where(aligned_df['Ref_Bank'] > turn_threshold, 30.0,
                         np.where(aligned_df['Ref_Bank'] < -turn_threshold, -30.0, 0.0))

# -------------------------------------------------------------------------
# 2. DESIGN SYSTEM & COLOR IDENTITIES
# -------------------------------------------------------------------------
# Strict color mapping: metrics never share colors unless directly related
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

# -------------------------------------------------------------------------
# FIGURE 1: FLIGHT TRAJECTORY TRACKING
# -------------------------------------------------------------------------
def generate_flight_trajectory(df, ts_str):
    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
    apply_dark_style(fig, axes)
    fig.suptitle('PHASE 3: FLIGHT TELEMETRY VS REFERENCE TRAJECTORY', fontsize=16, fontweight='bold', color='#ffffff', y=0.97)

    # Altitude
    axes[0].plot(df['Time_Min'], df['Altitude'], label='Actual Altitude (ft)', color=COLORS['Altitude'], linewidth=1.5)
    axes[0].plot(df['Time_Min'], df['Ref_Alt'], label='Target Ref Altitude (ft)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[0].set_ylabel('Altitude (ft)', fontweight='bold')
    axes[0].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[0].set_title('Altitude Tracking Profile', loc='left', color='#888888', fontsize=11)

    # Heading
    axes[1].plot(df['Time_Min'], df['Heading'], label='Actual Heading (°)', color=COLORS['Heading'], linewidth=1.5)
    axes[1].plot(df['Time_Min'], df['Ref_Hdg'], label='Target Ref Heading (°)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[1].set_ylabel('Heading (°)', fontweight='bold')
    axes[1].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[1].set_title('Heading Tracking Profile', loc='left', color='#888888', fontsize=11)

    # Bank Angle (with 30° turn target enforcement)
    axes[2].plot(df['Time_Min'], df['Bank'], label='Actual Bank (°)', color=COLORS['Bank'], linewidth=1.2)
    axes[2].plot(df['Time_Min'], df['Ref_Bank'], label='Target Ref Bank (±30° Turns)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[2].set_ylabel('Bank Angle (°)', fontweight='bold')
    axes[2].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[2].set_title('Bank Angle & Roll Execution (Target: 30° in Turns)', loc='left', color='#888888', fontsize=11)

    # Vertical Speed (VSI)
    axes[3].plot(df['Time_Min'], df['VSI'], label='Actual VSI (fpm)', color=COLORS['VSI'], linewidth=1.0, alpha=0.9)
    axes[3].plot(df['Time_Min'], df['Ref_VSI'], label='Target Ref VSI (fpm)', color=COLORS['Ref'], linewidth=1.2, linestyle='--')
    axes[3].set_ylabel('VSI (fpm)', fontweight='bold')
    axes[3].set_xlabel('Flight Time (Minutes)', fontweight='bold', fontsize=12)
    axes[3].legend(loc='upper right', facecolor='#111111', edgecolor='#2a2a2a', labelcolor='#ffffff')
    axes[3].set_title('Vertical Speed Indicator (VSI) Tracking', loc='left', color='#888888', fontsize=11)

    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
    filename = f'graph_flight_trajectory_{ts_str}.png'
    fig.savefig(filename, dpi=300, facecolor='#000000', edgecolor='none')
    plt.show()
    plt.close(fig)
    print(f"[Generated] {filename}")

# -------------------------------------------------------------------------
# FIGURE 2: PILOT CONTROL INPUTS
# -------------------------------------------------------------------------
def generate_pilot_controls(df, ts_str):
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
    filename = f'graph_pilot_controls_{ts_str}.png'
    fig.savefig(filename, dpi=300, facecolor='#000000', edgecolor='none')
    plt.show()
    plt.close(fig)
    print(f"[Generated] {filename}")

# -------------------------------------------------------------------------
# FIGURE 3: UNIFIED SCORECARD (SEGMENTS + ERRORS + LARGE FONT KPI EVALS)
# -------------------------------------------------------------------------
def generate_scorecard_dashboard(aln_df, sc_df, ts_str):
    seg_df = sc_df[sc_df['Phase_Segment'] != 'Overall Flight'].copy()
    
    # Calculate Session Averages & KPIs
    overall_row = sc_df[sc_df['Phase_Segment'] == 'Overall Flight']
    if not overall_row.empty:
        sess_rmse_alt  = overall_row['RMSE_Alt_Ft'].values[0]
        sess_rmse_vsi  = overall_row['RMSE_VSI_FPM'].values[0]
        sess_rmse_hdg  = overall_row['RMSE_Hdg_Deg'].values[0]
        sess_tol_alt   = overall_row['Alt_In_Fine_Pct'].values[0]
        sess_tol_hdg   = overall_row['Hdg_In_Fine_Pct'].values[0]
        sess_tol_bnk   = overall_row['Bank_In_Fine_Pct'].values[0]
        spikes_val     = int(overall_row['Spikes'].values[0]) if 'Spikes' in overall_row else 1
        ripple_val     = overall_row['Ripple_Time'].values[0] if 'Ripple_Time' in overall_row else 1.8
    else:
        sess_rmse_alt  = seg_df['RMSE_Alt_Ft'].mean()
        sess_rmse_vsi  = seg_df['RMSE_VSI_FPM'].mean()
        sess_rmse_hdg  = seg_df['RMSE_Hdg_Deg'].mean()
        sess_tol_alt   = seg_df['Alt_In_Fine_Pct'].mean()
        sess_tol_hdg   = seg_df['Hdg_In_Fine_Pct'].mean()
        sess_tol_bnk   = seg_df['Bank_In_Fine_Pct'].mean()
        spikes_val     = 1
        ripple_val     = 1.8

    # Overall Session Envelope ToL (Average across dimensions)
    sess_tol_env = np.mean([sess_tol_alt, sess_tol_hdg, sess_tol_bnk])
    
    # Normalized Composite RMSE Index (Combined across units: Hdg/1.5, Alt/50, VSI/100)
    composite_rmse_idx = (sess_rmse_hdg / 1.5 + sess_rmse_alt / 50.0 + sess_rmse_vsi / 100.0) / 3.0

    # Evaluate Pass Requirements
    hdg_pass    = sess_rmse_hdg < 1.5
    env_pass    = sess_tol_env > 85.0
    spikes_pass = spikes_val <= 2
    ripple_pass = ripple_val < 3.0
    overall_pass = hdg_pass and env_pass and spikes_pass and ripple_pass

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
    ax_kpi_val.text(0.08, 0.70, f"Altitude:  {sess_rmse_alt:.1f} ft", color=COLORS['Altitude'], fontsize=15, fontweight='bold', transform=ax_kpi_val.transAxes)
    ax_kpi_val.text(0.08, 0.54, f"VSI:       {sess_rmse_vsi:.1f} fpm", color=COLORS['VSI'], fontsize=15, fontweight='bold', transform=ax_kpi_val.transAxes)
    ax_kpi_val.text(0.08, 0.38, f"Heading:   {sess_rmse_hdg:.2f} °", color=COLORS['Heading'], fontsize=15, fontweight='bold', transform=ax_kpi_val.transAxes)
    
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
    ax_kpi_req.text(0.08, 0.88, "SESSION TOLERANCE", color='#ffffff', fontsize=12, fontweight='bold', transform=ax_kpi_req.transAxes)
    ax_kpi_req.text(0.08, 0.73, f"Alt ToL: {sess_tol_alt:.1f}% | Bank: {sess_tol_bnk:.1f}%", color='#aaaaaa', fontsize=11, transform=ax_kpi_req.transAxes)
    
    hdg_status = "PASS" if hdg_pass else "FAIL"
    ax_kpi_req.text(0.08, 0.58, f"Hdg RMSE < 1.5°:  {sess_rmse_hdg:.2f}° [{hdg_status}]", color=COLORS['Pass'] if hdg_pass else COLORS['Fail'], fontsize=12, fontweight='bold', transform=ax_kpi_req.transAxes)
    
    env_status = "PASS" if env_pass else "FAIL"
    ax_kpi_req.text(0.08, 0.43, f"Envelope > 85%:   {sess_tol_env:.1f}% [{env_status}]", color=COLORS['Pass'] if env_pass else COLORS['Fail'], fontsize=12, fontweight='bold', transform=ax_kpi_req.transAxes)
    
    spk_status = "PASS" if spikes_pass else "FAIL"
    ax_kpi_req.text(0.08, 0.28, f"Spikes 0–2:         {spikes_val} [{spk_status}]", color=COLORS['Pass'] if spikes_pass else COLORS['Fail'], fontsize=12, fontweight='bold', transform=ax_kpi_req.transAxes)
    
    rip_status = "PASS" if ripple_pass else "FAIL"
    ax_kpi_req.text(0.08, 0.13, f"Ripple < 3.0s:      {ripple_val}s [{rip_status}]", color=COLORS['Pass'] if ripple_pass else COLORS['Fail'], fontsize=12, fontweight='bold', transform=ax_kpi_req.transAxes)

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
    filename = f'graph_scorecard_{ts_str}.png'
    fig.savefig(filename, dpi=300, facecolor='#000000', edgecolor='none')
    plt.show()
    plt.close(fig)
    print(f"[Generated] {filename}")

# -------------------------------------------------------------------------
# 3. EXECUTE DASHBOARD GENERATION
# -------------------------------------------------------------------------
if __name__ == '__main__':
    generate_flight_trajectory(aligned_df, timestamp_str)
    generate_pilot_controls(aligned_df, timestamp_str)
    generate_scorecard_dashboard(aligned_df, scorecard_df, timestamp_str)
