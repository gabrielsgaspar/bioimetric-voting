from __future__ import annotations

from pathlib import Path
import sys

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "src" / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from plot_style import apply_matplotlib_paper_style, save_pdf_png  # noqa: E402


CATEGORY_ORDER = ["Female", "White", "Married", "Low Education"]
BAR_POSITIONS = {
    "Female": (0, 1, 2),
    "White": (3, 4, 5),
    "Married": (6, 7, 8),
    "Low Education": (9, 10, 11),
}


def _prepare_pgf_backend() -> None:
    mpl.rcParams["pgf.texsystem"] = "pdflatex"
    mpl.rcParams["pgf.rcfonts"] = False


def _clean_stars(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text


def _build_plot_dataframe(interaction_effects: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for category in CATEGORY_ORDER:
        subset = interaction_effects.loc[interaction_effects["category"] == category].copy()
        base = subset.loc[subset["group_label"] == "No"].iloc[0]
        combo = subset.loc[subset["group_label"] == "Yes"].iloc[0]
        base_pos, combo_pos, diff_pos = BAR_POSITIONS[category]
        rows.extend(
            [
                {
                    "category": category,
                    "difference": 0,
                    "combo": 0,
                    "plot_x": base_pos,
                    "estimator": float(base["estimate"]),
                    "std_err": float(base["std_err"]),
                    "ci95_low": float(base["ci95_low"]),
                    "ci95_high": float(base["ci95_high"]),
                    "stars": _clean_stars(base["stars"]),
                },
                {
                    "category": category,
                    "difference": 0,
                    "combo": 1,
                    "plot_x": combo_pos,
                    "estimator": float(combo["estimate"]),
                    "std_err": float(combo["std_err"]),
                    "ci95_low": float(combo["ci95_low"]),
                    "ci95_high": float(combo["ci95_high"]),
                    "stars": _clean_stars(combo["stars"]),
                },
                {
                    "category": category,
                    "difference": 1,
                    "combo": 0,
                    "plot_x": diff_pos,
                    "estimator": float(base["difference"]),
                    "std_err": float(base["difference_std_err"]),
                    "ci95_low": float(base["difference_ci95_low"]),
                    "ci95_high": float(base["difference_ci95_high"]),
                    "stars": _clean_stars(base["stars"]),
                },
            ]
        )
    return pd.DataFrame(rows)


def plot_notebook_style_interaction_figure(
    interaction_effects: pd.DataFrame,
    *,
    output_base: str | Path,
    pgf_path: str | Path | None,
    color: str,
) -> None:
    apply_matplotlib_paper_style()
    df_plot = _build_plot_dataframe(interaction_effects)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.grid(True, linestyle="-", axis="y", color="lightgray", alpha=0.4, linewidth=2, zorder=-2)

    base_rows = df_plot.query("difference == 0 and combo == 0").copy()
    combo_rows = df_plot.query("difference == 0 and combo == 1").copy()

    bars_base = ax.bar(
        base_rows["plot_x"],
        base_rows["estimator"],
        facecolor=color,
        edgecolor="none",
        alpha=1,
        zorder=2,
    )
    bars_combo = ax.bar(
        combo_rows["plot_x"],
        combo_rows["estimator"],
        facecolor=color,
        hatch="//",
        edgecolor="black",
        alpha=1,
        zorder=2,
    )

    ax.scatter(base_rows["plot_x"], base_rows["estimator"], linewidth=2, color="black", zorder=2)
    ax.scatter(combo_rows["plot_x"], combo_rows["estimator"], linewidth=2, color="black", zorder=2)

    for category in CATEGORY_ORDER:
        subset = df_plot.query("category == @category and difference == 0").copy()
        barx: list[float] = []
        top = float(subset["ci95_high"].max())
        bary = [top + 0.04, top + 0.12, top + 0.12, top + 0.04]
        for xpos in subset["plot_x"]:
            barx.append(float(xpos))
            barx.append(float(xpos))
        ax.plot(barx, bary, c="black", linewidth=2)
        diff_row = df_plot.query("category == @category and difference == 1").iloc[0]
        diff_est = float(diff_row["estimator"])
        diff_std = float(diff_row["std_err"])
        diff_est_text = f"{diff_est:.3f}" if diff_est < 0 else f" {diff_est:.3f}"
        diff_std_text = f"({diff_std:.3f})"
        ax.text(
            ((barx[0] + barx[-1]) / 2) + 0.2,
            max(bary) + 0.05,
            f"{diff_est_text}{diff_row['stars']}\n{diff_std_text}",
            ha="center",
            va="bottom",
            multialignment="left",
            bbox=dict(facecolor="white", edgecolor="none", boxstyle="round,pad=0.5"),
        )

    for bar in bars_base:
        ax.bar(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            width=bar.get_width(),
            facecolor="none",
            edgecolor="black",
            linewidth=1.5,
            zorder=1,
        )
    for bar in bars_combo:
        ax.bar(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            width=bar.get_width(),
            facecolor="none",
            edgecolor="black",
            linewidth=1.5,
            zorder=1,
        )

    for row in base_rows.itertuples(index=False):
        ax.vlines(x=row.plot_x, ymin=row.ci95_low, ymax=row.ci95_high, color="black", alpha=1, linewidth=2, zorder=2)
    for row in combo_rows.itertuples(index=False):
        ax.vlines(x=row.plot_x, ymin=row.ci95_low, ymax=row.ci95_high, color="black", alpha=1, linewidth=2, zorder=2)

    ax.hlines(y=0, xmin=-20, xmax=20, color="black", alpha=1, linewidth=2, zorder=2)

    no_patch = mpatches.Patch(facecolor=color, label="No")
    yes_patch = mpatches.Patch(facecolor=color, edgecolor="black", label="Yes", hatch="///")
    ax.legend(
        handles=[no_patch, yes_patch],
        loc="upper left",
        bbox_to_anchor=(7.2, 0.78),
        bbox_transform=ax.transData,
        ncol=2,
        frameon=True,
        facecolor="white",
        edgecolor="black",
        framealpha=1,
        handlelength=1.0,
        handleheight=0.8,
        handletextpad=0.5,
        columnspacing=1.0,
        borderpad=0.3,
    )

    ax.set_yticks(np.arange(-0.4, 2, 0.2))
    ax.set_xticks([0.5, 3.5, 6.5, 9.5], ["Female", "White", "Married", "Low Education"])
    ax.set_xlim(-1, 11)
    ax.set_ylim(-0.2, 0.8)
    ax.set_xlabel("")
    ax.set_ylabel("")

    save_pdf_png(fig, ROOT / output_base if not isinstance(output_base, Path) else output_base)
    if pgf_path is not None:
        _prepare_pgf_backend()
        fig.savefig(ROOT / pgf_path if not isinstance(pgf_path, Path) else pgf_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    trust_path = ROOT / "resources" / "lapop" / "regressions" / "trust_interactions" / "interaction_effects.csv"
    democracy_path = ROOT / "resources" / "lapop" / "regressions" / "democracy_interactions" / "interaction_effects.csv"
    if not trust_path.exists() or not democracy_path.exists():
        raise FileNotFoundError("Main interaction effects CSVs are missing.")
    trust = pd.read_csv(trust_path)
    democracy = pd.read_csv(democracy_path)
    plot_notebook_style_interaction_figure(
        trust,
        output_base=ROOT / "resources" / "lapop" / "figures" / "trust_interactions_barplot",
        pgf_path=ROOT / "resources" / "figures" / "regressions" / "lapop_trust_by_cat.pgf",
        color="darkslategrey",
    )
    plot_notebook_style_interaction_figure(
        democracy,
        output_base=ROOT / "resources" / "lapop" / "figures" / "democracy_interactions_barplot",
        pgf_path=ROOT / "resources" / "figures" / "regressions" / "lapop_dem_by_cat.pgf",
        color="saddlebrown",
    )


if __name__ == "__main__":
    main()
