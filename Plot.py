import matplotlib.pyplot as plt
import numpy as np
import scipy.special
from collections import defaultdict
from matplotlib.lines import Line2D

# Define data: (day, section, platform, control, values)
raw_data = [
    # Jun 7
    (7, 'Compass', 'PT', 'normal', [83, 80, 86]),
    # Jun 8
    (8, 'Compass', 'PT', 'normal', [85, 89, 90]),
    (8, 'Compass', 'PT', 'normal', [91, 91, 91]),
    # Jun 9
    (9, 'Compass', 'PT', 'normal', [91, 91, 91]),
    (9, 'Compass', 'PT', 'normal', [91, 92, 92]),
    (9, 'Compass', 'PT', 'normal', [92, 91, 91]),
    # Jun 10
    (10, 'Compass', 'PT', 'normal', [92]),
    (10, 'Compass', 'PT', 'inverted', [80, 85, 84]),
    (10, 'Compass', 'LPJ', 'normal', [74.5, 70, 77]),
    (10, 'Compass', 'PT', 'normal', [91]),
    # Jun 11
    (11, 'Compass', 'PT', 'normal', [89, 92]),
    (11, 'Compass', 'LPJ', 'inverted', [69.5, 71.5]),
    (11, 'Compass', 'PT', 'normal', [87, 91, 91]),
    (11, 'Slalom', 'PT', 'normal', [56, 60, 54]),
    # Jun 12
    (12, 'Compass', 'PT', 'inverted', [86, 84, 87]),
    (12, 'Compass', 'LPJ', 'normal', [71.5, 72.5, 79.5]),
    (12, 'Compass', 'PT', 'normal', [91, 92, 90]),
    (12, 'Slalom', 'PT', 'normal', [51, 59, 53]),
    (12, 'Slalom', 'PT', 'normal', [56, 60, 61]),
    # Jun 13
    (13, 'Compass', 'LPJ', 'inverted', [73, 72.5, 80]),
    (13, 'Compass', 'PT', 'normal', [88, 90]),
    (13, 'Slalom', 'PT', 'normal', [62]),
    # Jun 15
    (15, 'Compass', 'PT', 'inverted', [86, 90, 88]),
    (15, 'Compass', 'LPJ', 'normal', [75.5, 79, 74]),
    (15, 'Slalom', 'PT', 'normal', [65, 56, 61]),
    (15, 'Slalom', 'PT', 'normal', [56, 59, 63]),
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

day_counts = defaultdict(int)
for day, _, _, _, _ in raw_data:
    day_counts[day] += 1

data_points = []
current_day_idx = defaultdict(int)

for day, section, platform, control, values in raw_data:
    avg = np.mean(values)
    total_sessions = day_counts[day]
    spacing = 1.0 / (total_sessions + 1)
    x_pos = day + (current_day_idx[day] + 1) * spacing
    
    data_points.append({
        'x': x_pos, 'y': avg, 'section': section,
        'platform': platform, 'control': control
    })
    current_day_idx[day] += 1

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
    Line2D([0], [0], color='#AAAAAA', lw=2, ls=':', label='Trend (Slalom)')
]
leg = ax.legend(handles=legend_elements, facecolor='black', edgecolor='#2A2A2A', loc='lower right', ncol=2)
for text in leg.get_texts(): text.set_color('#FFFFFF')

plt.tight_layout()
plt.savefig("CompassProgress.png", dpi=300, facecolor='black')
plt.close()
