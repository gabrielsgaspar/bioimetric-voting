from __future__ import annotations

import numpy as np
import pandas as pd

from common import (
    AGE_BAND_MAP,
    AGE_BANDS,
    COLORS,
    FIGURE_DATA_DIR,
    RELABEL_COHORT_PATH,
    ensure_dirs,
    format_percent_axis,
    percent_label,
    read_final_municipality,
    read_panel,
    save_matplotlib_variants,
)


FILENAME = "figure_05_share_by_age_band"
TITLE = "Exit and re-labeling concentrate in different age bands"


def build_population_reference(treated: pd.DataFrame) -> pd.DataFrame:
    panel = read_panel(["ibge_municipality_id", "year", "age_cohort", "num_voters"])
    baseline_years = treated[["ibge_municipality_id", "baseline_year_used"]].copy()
    panel = panel.merge(baseline_years, how="inner", on="ibge_municipality_id", validate="many_to_one")
    panel = panel[panel["year"].eq(panel["baseline_year_used"])].copy()
    panel["age_band"] = panel["age_cohort"].map(AGE_BAND_MAP)
    if panel["age_band"].isna().any():
        missing = sorted(panel.loc[panel["age_band"].isna(), "age_cohort"].unique())
        raise RuntimeError(f"Missing age-band mapping for cohorts: {missing}")
    reference = (
        panel.groupby("age_band", as_index=False)
        .agg(total_baseline_2008=("num_voters", "sum"))
        .set_index("age_band")
        .reindex(AGE_BANDS)
        .reset_index()
    )
    reference["total_pop_share"] = (
        reference["total_baseline_2008"] / reference["total_baseline_2008"].sum()
    )
    return reference[["age_band", "total_pop_share"]]


def build_figure_data() -> pd.DataFrame:
    treated = read_final_municipality()
    treated_ids = set(treated["ibge_municipality_id"])
    relabel = pd.read_parquet(RELABEL_COHORT_PATH)
    relabel = relabel.copy()
    relabel["ibge_municipality_id"] = relabel["ibge_municipality_id"].astype(str).str.zfill(7)
    relabel = relabel[relabel["ibge_municipality_id"].isin(treated_ids)].copy()
    relabel["age_band"] = relabel["age_cohort"].map(AGE_BAND_MAP)
    if relabel["age_band"].isna().any():
        missing = sorted(relabel.loc[relabel["age_band"].isna(), "age_cohort"].unique())
        raise RuntimeError(f"Missing age-band mapping for cohorts: {missing}")

    grouped = (
        relabel.groupby("age_band", as_index=False)
        .agg(
            exit_count=("exit_count", "sum"),
            R_B_count=("R_B_bounded", "sum"),
        )
        .set_index("age_band")
        .reindex(AGE_BANDS)
        .fillna(0)
        .reset_index()
    )
    grouped["exit_share"] = grouped["exit_count"] / grouped["exit_count"].sum()
    grouped["R_B_share"] = grouped["R_B_count"] / grouped["R_B_count"].sum()
    reference = build_population_reference(treated)
    out = reference.merge(grouped, how="left", on="age_band", validate="one_to_one")
    return out[["age_band", "total_pop_share", "exit_count", "exit_share", "R_B_count", "R_B_share"]]


def plot(data: pd.DataFrame, fig, ax, title: str | None) -> None:
    x = np.arange(len(data))
    width = 0.28
    offset = 0.22
    exit_bars = ax.bar(
        x - offset,
        data["exit_share"],
        width,
        color=COLORS["exit"],
        label="Share of exit",
    )
    relabel_bars = ax.bar(
        x + offset,
        data["R_B_share"],
        width,
        color=COLORS["relabel"],
        label="Share of R_B",
    )

    for xpos, share in zip(x, data["total_pop_share"]):
        ax.hlines(
            share,
            xpos - 0.48,
            xpos + 0.48,
            colors=COLORS["reference"],
            linestyles=(0, (3, 2)),
            linewidth=1.0,
            zorder=0,
        )
    ax.plot([], [], color=COLORS["reference"], linestyle=(0, (3, 2)), label="2008 population share")

    for bar_group, extra_offset, small_ha, small_dx in [
        (exit_bars, 0.006, "right", -0.02),
        (relabel_bars, 0.012, "left", 0.02),
    ]:
        for bar in bar_group:
            height = bar.get_height()
            is_small = height < 0.08
            ax.text(
                bar.get_x() + bar.get_width() / 2 + (small_dx if is_small else 0),
                height + extra_offset,
                f"{100 * height:.1f}%",
                ha=small_ha if is_small else "center",
                va="bottom",
                fontsize=9,
                rotation=0,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(data["age_band"])
    ax.set_xlabel("Age band")
    ax.set_ylabel("Percent of total")
    ax.set_ylim(0, max(data[["exit_share", "R_B_share", "total_pop_share"]].max()) * 1.18)
    format_percent_axis(ax, "y")
    ax.legend(frameon=False, loc="upper right")
    if title:
        ax.set_title(title, loc="left", pad=8)


def main() -> None:
    ensure_dirs()
    data = build_figure_data()
    data.to_parquet(FIGURE_DATA_DIR / "figure_05_data.parquet", index=False)
    save_matplotlib_variants(
        lambda fig, ax, title: plot(data, fig, ax, title),
        FILENAME,
        TITLE,
    )
    print(f"Saved {FILENAME} and figure_05_data.parquet")


if __name__ == "__main__":
    main()
