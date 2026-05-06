from __future__ import annotations

from pathlib import Path

import matplotlib as mpl


LATEX_PREAMBLE = r"\usepackage[T1]{fontenc}\usepackage{lmodern}\usepackage{amsmath}\usepackage{amssymb}"
PAPER_SERIF_FONTS = ["Latin Modern Roman", "LM Roman 10", "Computer Modern Roman"]
DEFAULT_FONT_SIZE = 11
DEFAULT_DPI = 320
DEFAULT_FIG_WIDTH = 8
DEFAULT_FIG_HEIGHT = 5
GRID_COLOR = "#D9D9D9"
BORDER_COLOR = "black"


def apply_matplotlib_paper_style() -> None:
    mpl.rcParams.update(
        {
            "text.usetex": True,
            "text.latex.preamble": LATEX_PREAMBLE,
            "font.family": "serif",
            "font.serif": PAPER_SERIF_FONTS,
            "font.size": DEFAULT_FONT_SIZE,
            "axes.labelsize": DEFAULT_FONT_SIZE,
            "axes.titlesize": DEFAULT_FONT_SIZE,
            "axes.edgecolor": BORDER_COLOR,
            "axes.linewidth": 0.6,
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.spines.top": True,
            "axes.spines.right": True,
            "grid.color": GRID_COLOR,
            "grid.linestyle": "-",
            "grid.linewidth": 0.8,
            "xtick.labelsize": DEFAULT_FONT_SIZE,
            "ytick.labelsize": DEFAULT_FONT_SIZE,
            "legend.fontsize": 10,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def apply_boxed_axis_style(ax) -> None:
    ax.grid(True, which="major", axis="both", color=GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ["top", "right", "bottom", "left"]:
        ax.spines[side].set_visible(True)
        ax.spines[side].set_linewidth(0.6)
        ax.spines[side].set_color(BORDER_COLOR)


def save_pdf_png(fig, output_base: Path, *, dpi: int = DEFAULT_DPI, bbox_inches: str | None = None) -> None:
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches=bbox_inches, facecolor="white")
    fig.savefig(output_base.with_suffix(".png"), dpi=dpi, bbox_inches=bbox_inches, facecolor="white")
