import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd

# -------------------------------------------------------------------------
# 1. LOAD DATA & SETUP TIME
# -------------------------------------------------------------------------
aligned_df = pd.read_csv('aligned_telemetry_analysis_20260723_185323.csv')
scorecard_df = pd.read_csv('analysis_scorecard_20260723_185323.csv')

aligned_df['Time_Min'] = (
    pd.to_datetime(aligned_df['Timestamp']) - pd.to_datetime(aligned_df['Timestamp'].iloc[0])
).dt.total_seconds() / 60.0

# -------------------------------------------------------------------------
# 2. OLED STYLING HELPER
# -------------------------------------------------------------------------
def apply_oled_style(fig, axes):
    """Applies high-contrast dark OLED styling to figure and axes."""
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
        ax.grid(True, color='#1f1f1f', linestyle='--', alpha=0.8)

# Color Palette
c_actual = '#00ffcc'  # Bright Cyan
c_ref = '#ff007f'     # Bright Magenta

# -------------------------------------------------------------------------
# FIGURE 1: Flight Trajectory Tracking Dashboard (4 Subplots)
# -------------------------------------------------------------------------
fig1, axes1 = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
apply_oled_style(fig1, axes1)
fig1.suptitle('PHASE 3: FLIGHT TELEMETRY VS REFERENCE TRAJECTORY (OLED MODE)', fontsize=16, fontweight='bold', color='#00ffcc', y=0.97)

# Altitude
axes1[0].plot(aligned_df['Time_Min'], aligned_df['Altitude'], label='Actual Altitude (ft)', color=c_actual, linewidth=1.5)
axes1[0].plot(aligned_df['Time_Min'], aligned_df['Ref_Alt'], label='Target Ref Altitude (ft)', color=c_ref, linewidth=1.5, linestyle='--')
axes1[0].set_ylabel('Altitude (ft)', fontweight='bold')
axes1[0].legend(loc='upper right', facecolor='#111111', edgecolor='#333333', labelcolor='#ffffff')
axes1[0].set_title('Altitude Tracking Profile', loc='left', color='#aaaaaa', fontsize=11)

# Heading
axes1[1].plot(aligned_df['Time_Min'], aligned_df['Heading'], label='Actual Heading (°)', color=c_actual, linewidth=1.5)
axes1[1].plot(aligned_df['Time_Min'], aligned_df['Ref_Hdg'], label='Target Ref Heading (°)', color=c_ref, linewidth=1.5, linestyle='--')
axes1[1].set_ylabel('Heading (°)', fontweight='bold')
axes1[1].legend(loc='upper right', facecolor='#111111', edgecolor='#333333', labelcolor='#ffffff')
axes1[1].set_title('Heading Tracking Profile', loc='left', color='#aaaaaa', fontsize=11)

# Bank Angle
axes1[2].plot(aligned_df['Time_Min'], aligned_df['Bank'], label='Actual Bank (°)', color=c_actual, linewidth=1.2)
axes1[2].plot(aligned_df['Time_Min'], aligned_df['Ref_Bank'], label='Target Ref Bank (°)', color=c_ref, linewidth=1.5, linestyle='--')
axes1[2].set_ylabel('Bank Angle (°)', fontweight='bold')
axes1[2].legend(loc='upper right', facecolor='#111111', edgecolor='#333333', labelcolor='#ffffff')
axes1[2].set_title('Bank Angle & Roll Execution', loc='left', color='#aaaaaa', fontsize=11)

# Vertical Speed (VSI)
axes1[3].plot(aligned_df['Time_Min'], aligned_df['VSI'], label='Actual VSI (fpm)', color=c_actual, linewidth=1.0, alpha=0.85)
axes1[3].plot(aligned_df['Time_Min'], aligned_df['Ref_VSI'], label='Target Ref VSI (fpm)', color=c_ref, linewidth=1.5, linestyle='--')
axes1[3].set_ylabel('VSI (fpm)', fontweight='bold')
axes1[3].set_xlabel('Flight Time (Minutes)', fontweight='bold', fontsize=12)
axes1[3].legend(loc='upper right', facecolor='#111111', edgecolor='#333333', labelcolor='#ffffff')
axes1[3].set_title('Vertical Speed Indicator (VSI) Tracking', loc='left', color='#aaaaaa', fontsize=11)

plt.tight_layout()
plt.subplots_adjust(top=0.93)
fig1.savefig('oled_flight_trajectory.png', dpi=300, facecolor='#000000', edgecolor='none')
plt.show()
plt.close(fig1)
