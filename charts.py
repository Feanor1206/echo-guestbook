"""Create the required Matplotlib PNG graphs (including static/stats.png)."""
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

BG = '#12192c'
TEXT = '#e9ecff'
MUTED = '#8c9ab6'
PURPLE = '#ab94ff'
CYAN = '#7ae0d5'


def _style(ax, fig):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.tick_params(axis='both', length=0, colors=MUTED, labelsize=10)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis='y', color='#ffffff', alpha=.09, linewidth=.8)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))


def render_charts(stats: dict, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    leaders = stats['all_authors'][:8]
    fig, ax = plt.subplots(figsize=(10.5, 4.3), dpi=155)
    _style(ax, fig)
    if leaders:
        labels = [x['name'][:12] + ('…' if len(x['name']) > 12 else '') for x in leaders]
        values = [x['count'] for x in leaders]
        bars = ax.bar(range(len(leaders)), values, width=.56,
                      color=[PURPLE if i == 0 else '#6373ac' for i in range(len(leaders))],
                      edgecolor='none')
        ax.set_xticks(range(len(labels)), labels, rotation=12, ha='right')
        ax.set_ylim(0, max(values) * 1.3 + .2)
        for bar, num in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, num + .09, str(num),
                    color=TEXT, ha='center', va='bottom', fontsize=11, fontweight='bold')
    else:
        ax.text(.5, .5, 'Chưa có dữ liệu để hiển thị', transform=ax.transAxes,
                color=MUTED, fontsize=15, ha='center', va='center')
        ax.set_xticks([])
        ax.set_yticks([])
    fig.tight_layout(pad=2.0)
    fig.savefig(folder / 'stats.png', facecolor=BG, bbox_inches='tight', pad_inches=.28)
    plt.close(fig)

    daily = stats['daily']
    labels = [datetime.fromisoformat(x['date']).strftime('%d/%m') for x in daily]
    values = [x['count'] for x in daily]
    fig, ax = plt.subplots(figsize=(10.5, 3.5), dpi=155)
    _style(ax, fig)
    ax.plot(range(len(values)), values, color=CYAN, linewidth=2.7, marker='o', markersize=7,
            markerfacecolor=BG, markeredgewidth=2.7, markeredgecolor=CYAN)
    ax.fill_between(range(len(values)), values, color=CYAN, alpha=.11)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_ylim(bottom=0, top=max(max(values) * 1.22, 1.3))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    fig.tight_layout(pad=2)
    fig.savefig(folder / 'activity.png', facecolor=BG, bbox_inches='tight', pad_inches=.25)
    plt.close(fig)
