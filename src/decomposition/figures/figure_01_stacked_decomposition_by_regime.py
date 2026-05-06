from __future__ import annotations

import pandas as pd

from common import (
    COLORS,
    FIGURE_DATA_DIR,
    FINAL_AGG_PATH,
    ensure_dirs,
    format_percent_axis,
    percent_label,
    save_matplotlib_variants,
)


FILENAME = "figure_01_stacked_decomposition_by_regime"
TITLE = "Registry impacts decompose into exit and re-labeling"


def build_figure_data() -> pd.DataFrame:
    aggregate = pd.read_parquet(FINAL_AGG_PATH)
    aggregate = aggregate[aggregate["aggregation_level"].isin(["strict", "hybrid"])].copy()
    aggregate["aggregation_level"] = pd.Categorical(
        aggregate["aggregation_level"],
        categories=["strict", "hybrid"],
        ordered=True,
    )
    aggregate = aggregate.sort_values("aggregation_level")

    rows = []
    for _, row in aggregate.iterrows():
        regime = str(row["aggregation_level"])
        exit_rate = float(row["national_exit_rate_2008"])
        relabel_rate = float(row["national_R_B_rate_2008"])
        total = exit_rate + relabel_rate
        rows.extend(
            [
                {
                    "regime": regime,
                    "component": "Exit",
                    "rate": exit_rate,
                    "total": total,
                },
                {
                    "regime": regime,
                    "component": "Re-labeling (Scenario B)",
                    "rate": relabel_rate,
                    "total": total,
                },
            ]
        )
    return pd.DataFrame(rows)


def plot(data: pd.DataFrame, fig, ax, title: str | None) -> None:
    regimes = ["strict", "hybrid"]
    labels = ["Strict", "Hybrid"]
    x = range(len(regimes))
    bottoms = [0.0, 0.0]
    components = [
        ("Exit", COLORS["exit"]),
        ("Re-labeling (Scenario B)", COLORS["relabel"]),
    ]

    for component, color in components:
        heights = [
            float(data.loc[(data["regime"].eq(regime)) & (data["component"].eq(component)), "rate"].iloc[0])
            for regime in regimes
        ]
        ax.bar(
            x,
            heights,
            bottom=bottoms,
            width=0.58,
            color=color,
            edgecolor="white",
            linewidth=0.7,
            label=component,
        )
        for xpos, bottom, height in zip(x, bottoms, heights):
            if height > 0.008:
                ax.text(
                    xpos,
                    bottom + height / 2,
                    percent_label(height),
                    ha="center",
                    va="center",
                    color="white" if component == "Exit" else "#3F2D16",
                    fontsize=10,
                    fontweight="bold",
                )
        bottoms = [bottom + height for bottom, height in zip(bottoms, heights)]

    totals = [float(data.loc[data["regime"].eq(regime), "total"].iloc[0]) for regime in regimes]
    for xpos, total in zip(x, totals):
        ax.text(
            xpos,
            total + 0.008,
            percent_label(total),
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color="#111827",
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Percent of 2008 treated baseline")
    ax.set_ylim(0, max(totals) * 1.22)
    format_percent_axis(ax, "y")
    ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1.02, 1.0))
    if title:
        ax.set_title(title, loc="left", pad=8)


def main() -> None:
    ensure_dirs()
    data = build_figure_data()
    data.to_parquet(FIGURE_DATA_DIR / "figure_01_data.parquet", index=False)
    save_matplotlib_variants(
        lambda fig, ax, title: plot(data, fig, ax, title),
        FILENAME,
        TITLE,
    )
    print(f"Saved {FILENAME} and figure_01_data.parquet")


if __name__ == "__main__":
    main()
