import matplotlib.pyplot as plt
import pandas as pd

# Define the dataset cleanly with the specified prioritization hierarchies and score thresholds
data = {
    "Day": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "Morning": [
        "• 3x Pilotest Inverted\n• 3x Pilotest Slalom\n• 1x Pilotest Orientation",
        "Full COMPASS Simulation\n\n(Math, Physics, English, and\nall core test modules)",
        "• 2x Pilotest Slalom\n• 1x Pilotest Orientation",
        "• 3x Pilotest Inverted\n• 3x Pilotest Slalom\n• 1x Pilotest Orientation",
        "• 3x Pilotest Inverted\n• 3x Pilotest Slalom\n• 1x Pilotest Orientation",
        "Full COMPASS Simulation\n\n(Math, Physics, English, and\nall core test modules)",
        "Absolute Shutdown"
    ],
    "Mid-Day": [
        "• 3x LPJ Normal (Med)\n• 3x Pilotest Slalom\n• 1x LPJ Multitasking (Hard)",
        "Full COMPASS Simulation\n\n(Continuation and\nPerformance Review)",
        "• 1x LPJ Memory (Med)\n• 1x LPJ Multitasking (Hard)",
        "• 3x LPJ Inverted (Med)\n• 3x Pilotest Slalom\n• 1x LPJ Memory (Med)",
        "• 3x LPJ Normal (Med)\n• 3x Pilotest Slalom\n• 1x LPJ Memory (Med)",
        "Full COMPASS Simulation\n\n(Continuation and\nPerformance Review)",
        "No Practice Today"
    ],
    "Evening": [
        "• 3x Pilotest Normal\n• 3x Pilotest Slalom\n• 1x LPJ Memory (Med)",
        "• 3x Test Mode Control\n• 1x Pilotest Normal\n(Baseline Calibration Check)",
        "Operational Rest Window\nCrucial Recharge Period",
        "• 3x Pilotest Normal\n• 3x Pilotest Slalom\n• 1x LPJ Multitasking (Hard)",
        "• 3x Pilotest Normal\n• 3x Pilotest Slalom\n• 1x LPJ Multitasking (Hard)",
        "• 3x Test Mode Control\n• 1x Pilotest Normal\n(Baseline Calibration Check)",
        "Yes, Rest"
    ]
}

# Explicit platform and performance thresholds to anchor the footer metrics block
thresholds = [
    "Slalom (Pilotest): 75%+",
    "Orientation (Pilotest): 100%",
    "Multitasking (LPJ Hard): 100%",
    "Short Memory (LPJ Med): 90%+",
    "Flight Control (Pilotest & LPJ Med): 75%+",
    "Math (LPJ Med/Hard): 100%",
    "Physics (LPJ Easy/Med): 90%+",
    "Aviation English (LPJ): 70%+"
]

# Initialize canvas utilizing a dense, dark profile to ease eye strain during high-saturation reviews
fig = plt.figure(figsize=(15, 11), facecolor='#111111')
ax = fig.add_subplot(1, 1, 1, facecolor='#111111')
ax.axis('off')

# Build the structural matrix representation
df = pd.DataFrame(data)

# Render table parameters precisely to ensure sharp bounding edges and clean typography
table = ax.table(
    cellText=df.values,
    colLabels=df.columns,
    cellLoc='left',
    loc='upper center',
    colWidths=[0.12, 0.29, 0.29, 0.29]
)

table.auto_set_font_size(False)
table.set_fontsize(11)

# Color signature map mapping occupation logic directly to structural visual cues
day_themes = {
    "Monday": {"bg": "#1e1e1e", "text": "#d4d4d4", "day_fg": "#b5b5b5"},
    "Tuesday": {"bg": "#1a1510", "text": "#d4d4d4", "day_fg": "#ff9f43"},
    "Wednesday": {"bg": "#1a1010", "text": "#d4d4d4", "day_fg": "#ff4d4d"},
    "Thursday": {"bg": "#1e1e1e", "text": "#d4d4d4", "day_fg": "#b5b5b5"},
    "Friday": {"bg": "#1e1e1e", "text": "#d4d4d4", "day_fg": "#b5b5b5"},
    "Saturday": {"bg": "#1a1510", "text": "#d4d4d4", "day_fg": "#ff9f43"},
    "Sunday": {"bg": "#1a1010", "text": "#d4d4d4", "day_fg": "#ff4d4d"}
}

# Style the column index headers perfectly
for col_idx in range(len(df.columns)):
    cell = table[0, col_idx]
    cell.set_facecolor('#2d2d2d')
    cell.get_text().set_color('#ffffff')
    cell.get_text().set_weight('bold')
    cell.get_text().set_fontsize(13)
    cell.set_height(0.05)
    cell.set_edgecolor('#444444')

# Apply structural formatting down row matrices
for row_idx, day_name in enumerate(df['Day']):
    theme = day_themes[day_name]
    
    for col_idx in range(len(df.columns)):
        cell = table[row_idx + 1, col_idx]
        cell.set_facecolor(theme['bg'])
        cell.set_height(0.11)
        cell.set_edgecolor('#333333')
        
        text_obj = cell.get_text()
        text_obj.set_color(theme['text'])
        
        # Format the leading column explicitly with day identifiers
        if col_idx == 0:
            text_obj.set_color(theme['day_fg'])
            text_obj.set_weight('bold')
            text_obj.set_fontsize(14)
            cell.set_text_props(ha='center')

# Append clean footer markers summarizing absolute target requirements
footer_y = 0.12
ax.text(0.01, footer_y + 0.0, "TARGET PERFORMANCE METRICS:", color='#aaaaaa', fontsize=12, weight='bold')

col_split = 4
for idx, threshold in enumerate(thresholds):
    col = idx % col_split
    row = idx // col_split
    x_pos = 0.01 + (col * 0.25)
    y_pos = footer_y - (row * 0.04) - 0.04
    ax.text(x_pos, y_pos, f"• {threshold}", color='#00ffcc', fontsize=11, weight='medium')

# Flush and save pristine image asset
plt.tight_layout()
plt.savefig('CompassPrepSchedule.png', dpi=300, facecolor=fig.get_facecolor(), bbox_inches='tight')
plt.close()
