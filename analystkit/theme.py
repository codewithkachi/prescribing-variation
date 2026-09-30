"""One visual system for all nine projects.

Palette is the validated default from the dataviz reference instance.
Categorical hues are assigned in FIXED SLOT ORDER and never cycled - if a chart
needs a ninth series, that is a signal to fold into "Other" or facet, not to
invent a colour.
"""
from __future__ import annotations
import matplotlib as mpl
import matplotlib.pyplot as plt
from pathlib import Path

# Categorical slots 1-8, light mode. Order is the CVD-safety mechanism.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
           "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

# Sequential (magnitude) - one hue, light to dark.
SEQ_BLUE = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
            "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
            "#184f95", "#104281", "#0d366b"]

# Diverging pair: blue <-> red with a NEUTRAL GREY midpoint (never a hue).
DIVERGING = ["#104281", "#2a78d6", "#86b6ef", "#f0efec", "#f0a3a2", "#e34948", "#a52322"]

# Status is reserved. Never reused as "series 4". Always shipped with a label.
STATUS = {"good": "#0ca30c", "warning": "#fab219",
          "serious": "#ec835a", "critical": "#d03b3b"}

INK = {
    "surface":   "#fcfcfb",
    "plane":     "#f9f9f7",
    "primary":   "#0b0b0b",
    "secondary": "#52514e",
    "muted":     "#898781",
    "grid":      "#e1e0d9",
    "baseline":  "#c3c2b7",
    "good_text": "#006300",
}


def apply_theme() -> None:
    """Recessive chrome, thin marks, no chartjunk. Call once per script."""
    mpl.rcParams.update({
        "figure.facecolor":  INK["surface"],
        "axes.facecolor":    INK["surface"],
        "savefig.facecolor": INK["surface"],
        "font.family":       "sans-serif",
        "font.sans-serif":   ["Segoe UI", "DejaVu Sans", "Arial"],
        "font.size":         10,
        "axes.titlesize":    12.5,
        "axes.titleweight":  "600",
        "axes.titlelocation": "left",
        "axes.titlepad":     14,
        "axes.labelsize":    9.5,
        "axes.labelcolor":   INK["secondary"],
        "axes.edgecolor":    INK["baseline"],
        "axes.linewidth":    0.9,
        "axes.grid":         True,
        "axes.axisbelow":    True,
        "grid.color":        INK["grid"],
        "grid.linewidth":    0.7,
        "xtick.color":       INK["muted"],
        "ytick.color":       INK["muted"],
        "xtick.labelsize":   9,
        "ytick.labelsize":   9,
        "xtick.major.size":  0,
        "ytick.major.size":  0,
        "legend.frameon":    False,
        "legend.fontsize":   9.5,
        "lines.linewidth":   2.0,
        "lines.markersize":  6,
        "figure.dpi":        110,
        "savefig.dpi":       160,
        "savefig.bbox":      "tight",
        "axes.prop_cycle":   mpl.cycler(color=PALETTE),
    })


def despine(ax, keep=("left", "bottom")):
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(side in keep)


def save_fig(fig, path: str | Path, caption: str | None = None) -> Path:
    """Write a chart and return its path. Caption goes under the plot."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if caption:
        fig.text(0.0, -0.02, caption, ha="left", va="top",
                 fontsize=8.2, color=INK["muted"], wrap=True)
    fig.savefig(path)
    plt.close(fig)
    return path


# --- formatting helpers: analysts write these once, not in every f-string ---
def fmt_gbp(v, dp=0):
    neg = v < 0
    v = abs(v)
    for cut, suf in ((1e9, "bn"), (1e6, "m"), (1e3, "k")):
        if v >= cut:
            s = f"GBP {v/cut:,.{1 if v/cut < 100 else 0}f}{suf}"
            return ("-" + s) if neg else s
    s = f"GBP {v:,.{dp}f}"
    return ("-" + s) if neg else s


def fmt_int(v):
    return f"{v:,.0f}"


def fmt_pct(v, dp=1):
    return f"{v:.{dp}f}%"
