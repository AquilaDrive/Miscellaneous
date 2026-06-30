import matplotlib.pyplot as plt
import numpy as np
import scipy.special
from collections import defaultdict
from matplotlib.lines import Line2D

# Full dataset with new entries for Jun 23 and Jun 25
raw_data = [
    # Jun 7
    (7, 'Compass', 'PT', 'normal', [83, 80, 86], 'evening'),
    
    # Jun 8
    (8, 'Compass', 'PT', 'normal', [85, 89, 90], 'midday'),
    (8, 'Compass', 'PT', 'normal', [91, 91, 91], 'evening'),
    
    # Jun 9
    (9, 'Compass', 'PT', 'normal', [91, 91, 91], 'morning'),
    (9, 'Compass', 'PT', 'normal', [91, 92, 92], 'midday'),
    (9, 'Compass', 'PT', 'normal', [92, 91, 91], 'evening'),
    
    # Jun 10
    (10, 'Compass', 'PT', 'normal', [92], 'morning'),
    (10, 'Compass', 'PT', 'inverted', [80, 85, 84], 'midday'),
    (10, 'Compass', 'LPJ', 'normal', [74.5, 70, 77], 'midday'),
    (10, 'Compass', 'PT', 'normal', [91], 'evening'),
    
    # Jun 11
    (11, 'Compass', 'PT', 'normal', [89, 92], 'morning'),
    (11, 'Compass', 'LPJ', 'inverted', [69.5, 71.5], 'midday'),
    (11, 'Compass', 'PT', 'normal', [87, 91, 91], 'evening'),
    (11, 'Slalom', 'PT', 'normal', [56, 60, 54], 'evening'),
    
    # Jun 12
    (12, 'Compass', 'PT', 'inverted', [86, 84, 87], 'morning'),
    (12, 'Slalom', 'PT', 'normal', [51, 59, 53], 'morning'),
    (12, 'Compass', 'LPJ', 'normal', [71.5, 72.5, 79.5], 'midday'),
    (12, 'Slalom', 'PT', 'normal', [56, 60, 61], 'midday'),
    (12, 'Compass', 'PT', 'normal', [91, 92, 90], 'evening'),
    
    # Jun 13
    (13, 'Compass', 'LPJ', 'inverted', [73, 72.5, 80], 'morning'),
    (13, 'Compass', 'PT', 'normal', [88, 90], 'midday'),
    (13, 'Slalom', 'PT', 'normal', [62], 'midday'),
    
    # Jun 15
    (15, 'Compass', 'PT', 'inverted', [86, 90, 88], 'morning'),
    (15, 'Slalom', 'PT', 'normal', [65, 56, 61], 'morning'),
    (15, 'Compass', 'LPJ', 'normal', [75.5, 79, 74], 'midday'),
    (15, 'Slalom', 'PT', 'normal', [56, 59, 63], 'midday'),
    (15, 'Compass', 'PT', 'normal', [89, 92, 91], 'evening'),
    (15, 'Slalom', 'PT', 'normal', [63, 73, 61], 'evening'),

    # Jun 16
    (16, 'Compass', 'LPJ', 'normal', [76], 'morning'),
    (16, 'Slalom', 'PT', 'normal', [71], 'morning'),
    (16, 'Compass', 'LPJ', 'normal', [77.5, 82, 83], 'midday'),
    (16, 'Compass', 'PT', 'normal', [91, 93], 'evening'),
    
    # Jun 18
    (18, 'Compass', 'PT', 'inverted', [87, 89, 91], 'morning'),
    (18, 'Slalom', 'PT', 'normal', [63, 61, 59], 'morning'),
    (18, 'Compass', 'LPJ', 'inverted', [78.5, 79, 79], 'midday'),
    (18, 'Slalom', 'PT', 'normal', [67, 68, 67], 'midday'),
    
    # Jun 19
    (19, 'Compass', 'PT', 'inverted', [91], 'morning'),
    (19, 'Slalom', 'PT', 'normal', [68, 60], 'morning'),
    (19, 'Compass', 'LPJ', 'normal', [78], 'midday'),
    (19, 'Slalom', 'PT', 'normal', [68], 'midday'),
    (19, 'Compass', 'PT', 'normal', [91, 91], 'evening'),
    (19, 'Slalom', 'PT', 'normal', [63, 64, 64], 'evening'),

    # Jun 20
    (20, 'Compass', 'LPJ', 'inverted', [76, 82.5], 'midday'),
    (20, 'Compass', 'PT', 'normal', [92], 'evening'),
    (20, 'Slalom', 'PT', 'normal', [70], 'midday'),

    # Jun 22
    (22, 'Compass', 'PT', 'inverted', [88, 92, 91], 'morning'),
    (22, 'Slalom', 'PT', 'normal', [70, 72, 65], 'morning'),
    (22, 'Compass', 'LPJ', 'inverted', [80.5, 82, 81.5], 'midday'),
    (22, 'Slalom', 'PT', 'normal', [67, 74, 70], 'midday'),
    (22, 'Compass', 'PT', 'normal', [94, 93, 94], 'evening'),
    (22, 'Slalom', 'PT', 'normal', [69, 70, 72], 'evening'),

    # Jun 23
    (23, 'Compass', 'LPJ', 'normal', [80], 'morning'),
    (23, 'Slalom', 'PT', 'normal', [68], 'morning'),
    (23, 'Compass', 'LPJ', 'normal', [82, 82, 85], 'midday'),
    (23, 'Compass', 'PT', 'normal', [93], 'evening'),

    # Jun 25
    (25, 'Compass', 'PT', 'inverted', [89, 92, 92], 'morning'),
    (25, 'Slalom', 'PT', 'normal', [65, 66, 69], 'morning'),
    (25, 'Compass', 'LPJ', 'inverted', [82.5], 'midday'),
    (25, 'Slalom', 'PT', 'normal', [66, 75], 'midday'),
    (25, 'Compass', 'PT', 'normal', [91, 93, 93], 'evening'),
    (25, 'Slalom', 'PT', 'normal', [72, 66, 70], 'evening'),
]

def get_color(score):
    if score < 61: return '#E00A15'
    elif score < 67: return '#E35205'
    elif score < 76: return '#EA8A00'
    elif score < 82: return '#FFC20E'
    elif score < 86: return '#FFF200'
    elif score < 89: return '#C4D600'
    elif score < 91: return '#00B140'
    elif score < 92: return '#0085CA'
    else: return '#00386B'

time_offsets = {'morning': 0.25, 'midday': 0.50, 'evening': 0.75}

data_points = []
for day, section, platform, control, values, time_slot in raw_data:
    avg = np.mean(values)
    micro_offset = 0.0
    if section == 'Compass' and platform == 'LPJ':
        micro_offset = -0.04
    elif section == 'Compass' and control == 'inverted':
        micro_offset = 0.04
        
    x_pos = day + time_offsets[time_slot] + micro_offset
    
    data_points.append({
        'x': x_pos, 'y': avg, 'section': section,
        'platform': platform, 'control': control, 'day': day, 'values': values,
        'time_slot': time_slot  # Fixed: Added missing key here
    })

groups = defaultdict(list)

fig, ax = plt.subplots(figsize=(16, 9), facecolor='black')
ax.set_facecolor('black')

for pt in data_points:
    key = (pt['section'], pt['platform'], pt['control'])
    groups[key].append((pt['x'], pt['y']))
    color = get_color(pt['y'])
    
    if pt['section'] == 'Slalom':
        marker = '^'
    elif pt['platform'] == 'PT':
        marker = 'o'
    else:
        marker = 'D'
    
    if pt['control'] == 'normal':
        ax.scatter(pt['x'], pt['y'], color=color, marker=marker, s=150, zorder=4)
    else:
        ax.scatter(pt['x'], pt['y'], facecolors='none', edgecolors=color, marker=marker, s=150, linewidths=2, zorder=4)

def compute_bezier(points, num_points=200):
    n = len(points)
    if n < 2: return np.array([])
    t = np.linspace(0, 1, num_points)
    curve = np.zeros((num_points, 2))
    for i in range(n):
        binom = scipy.special.comb(n - 1, i)
        basis = binom * ((1 - t) ** (n - 1 - i)) * (t ** i)
        curve[:, 0] += basis * points[i][0]
        curve[:, 1] += basis * points[i][1]
    return curve

trend_styles = {
    ('Compass', 'PT', 'normal'): {'color': '#888888', 'ls': '-'},
    ('Compass', 'PT', 'inverted'): {'color': '#888888', 'ls': '--'},
    ('Compass', 'LPJ', 'normal'): {'color': '#555555', 'ls': '-'},
    ('Compass', 'LPJ', 'inverted'): {'color': '#555555', 'ls': '--'},
    ('Slalom', 'PT', 'normal'): {'color': '#AAAAAA', 'ls': ':'},
}

for key, pts in groups.items():
    if len(pts) > 1:
        pts.sort(key=lambda p: p[0])
        bezier_pts = compute_bezier(pts)
        style = trend_styles.get(key, {'color': '#444444', 'ls': '-'})
        ax.plot(bezier_pts[:, 0], bezier_pts[:, 1], color=style['color'], linestyle=style['ls'], linewidth=2, alpha=0.7, zorder=3)

ax.set_xlim(7, 26.5)
ax.set_ylim(50, 100)

for day in range(7, 27):
    ax.axvline(x=day, color='#2A2A2A', lw=1.5, zorder=1)
for pct in range(50, 101, 5):
    ax.axhline(y=pct, color='#2A2A2A', lw=1, zorder=1)

ax.spines['bottom'].set_color('#777777')
ax.spines['left'].set_color('#777777')
ax.spines['top'].set_color('none')
ax.spines['right'].set_color('none')
ax.tick_params(colors='#888888', labelsize=10)
ax.set_xticks(range(7, 27))
ax.set_xticklabels([f"Jun {d}" for d in range(7, 27)], rotation=45, ha='right')
ax.set_yticks(range(50, 101, 5))
ax.set_yticklabels([f"{pct}%" for pct in range(50, 101, 5)])

ax.set_title("COMPASS Prep Progress Log", color='#FFFFFF', fontsize=14, fontweight='bold', pad=20)

legend_elements = [
    Line2D([0], [0], marker='o', color='w', label='PT (Control)', mfc='#888888', ms=10, ls='None'),
    Line2D([0], [0], marker='D', color='w', label='LPJ (Control)', mfc='#888888', ms=9, ls='None'),
    Line2D([0], [0], marker='^', color='w', label='Slalom', mfc='#888888', ms=10, ls='None'),
    Line2D([0], [0], marker='s', color='w', label='Normal (Filled)', mfc='#888888', ms=10, ls='None'),
    Line2D([0], [0], marker='s', color='w', label='Inverted (Empty)', mfc='black', mec='#888888', ms=10, ls='None'),
    Line2D([0], [0], color='#888888', lw=2, ls='-', label='Trend (PT Normal)'),
    Line2D([0], [0], color='#888888', lw=2, ls='--', label='Trend (PT Inverted)'),
    Line2D([0], [0], color='#555555', lw=2, ls='-', label='Trend (LPJ Normal)'),
    Line2D([0], [0], color='#555555', lw=2, ls='--', label='Trend (LPJ Inverted)'),
    Line2D([0], [0], color='#AAAAAA', lw=2, ls=':', label='Trend (Slalom)')
]
leg = ax.legend(handles=legend_elements, facecolor='black', edgecolor='#2A2A2A', loc='lower right', ncol=2)
for text in leg.get_texts(): text.set_color('#FFFFFF')

plt.tight_layout()
plt.savefig("CompassProgress.png", dpi=300, facecolor='black')
plt.close()

print("Calculated averages for new data:")
for p in data_points:
    if p['day'] in [23, 25]:
        print(f"Day {p['day']} | {p['time_slot']} | {p['section']} {p['platform']} {p['control']} ({p['values']}) -> Mean: {p['y']:.2f}%")
