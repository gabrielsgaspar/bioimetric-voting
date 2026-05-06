from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from utils import repo_path


ANNO_OFFSET_SCALE = 0.08


def _load_plot_style():
    from sys import path as sys_path

    analysis_dir = repo_path("src/analysis")
    if str(analysis_dir) not in sys_path:
        sys_path.insert(0, str(analysis_dir))
    from plot_style import apply_matplotlib_paper_style, save_pdf_png  # type: ignore

    return apply_matplotlib_paper_style, save_pdf_png


def _category_order(df: pd.DataFrame) -> list[str]:
    return list(dict.fromkeys(df["category"].tolist()))


def _clean_stars(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = str(value)
    return "" if text.lower() == "nan" else text


def plot_interaction_bars(
    interaction_effects: pd.DataFrame,
    *,
    output_base: str | Path,
    colors: dict[str, str],
) -> None:
    apply_style, save_pdf_png = _load_plot_style()
    apply_style()

    categories = _category_order(interaction_effects)
    x_centers = np.arange(len(categories), dtype=float)
    bar_width = 0.34

    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="0.88", linewidth=0.8)
    ax.axhline(0.0, color="0.35", linewidth=1.2)

    all_y = []
    for shift, group_label in [(-bar_width / 2, "No"), (bar_width / 2, "Yes")]:
        subset = interaction_effects.loc[interaction_effects["group_label"] == group_label].copy()
        subset["category"] = pd.Categorical(subset["category"], categories=categories, ordered=True)
        subset = subset.sort_values("category")
        x_positions = x_centers + shift
        estimates = subset["estimate"].to_numpy()
        lower = estimates - subset["ci95_low"].to_numpy()
        upper = subset["ci95_high"].to_numpy() - estimates
        all_y.extend(subset["ci95_low"].tolist())
        all_y.extend(subset["ci95_high"].tolist())
        ax.bar(
            x_positions,
            estimates,
            width=bar_width,
            color=colors[group_label],
            edgecolor=colors[group_label],
            linewidth=1.2,
            label=group_label,
            zorder=3,
        )
        ax.errorbar(
            x_positions,
            estimates,
            yerr=np.vstack([lower, upper]),
            fmt="none",
            ecolor=colors[group_label],
            elinewidth=1.6,
            capsize=3,
            zorder=4,
        )

    y_span = max(all_y) - min(all_y) if all_y else 1.0
    offset = max(y_span * ANNO_OFFSET_SCALE, 0.03)
    annotation_tops = []
    for idx, category in enumerate(categories):
        subset = interaction_effects.loc[interaction_effects["category"] == category]
        top = float(subset["ci95_high"].max()) + offset
        diff = float(subset["interaction_difference"].iloc[0])
        diff_se = float(subset["interaction_difference_std_err"].iloc[0])
        stars = _clean_stars(subset["stars"].iloc[0])
        annotation = f"{diff:.3f}{stars}\n({diff_se:.3f})"
        ax.text(x_centers[idx], top, annotation, ha="center", va="bottom", fontsize=9)
        annotation_tops.append(top)

    y_min = min(all_y) - offset * 1.4 if all_y else -0.2
    y_max = max(annotation_tops) + offset * 1.6 if annotation_tops else 0.2
    ax.set_ylim(y_min, y_max)
    ax.set_xticks(x_centers)
    ax.set_xticklabels(categories)
    ax.set_xlabel("")
    ax.set_ylabel("")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.9)
        spine.set_color("0.2")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    fig.tight_layout()
    save_pdf_png(fig, repo_path(output_base))
    plt.close(fig)
