from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from common import (
    COLORS,
    FIGURE_DATA_DIR,
    REGION_COLORS,
    STATE_REGIONS,
    ensure_dirs,
    format_percent_axis,
    load_muni_with_baseline_low_ed,
    save_matplotlib_variants,
)


FILENAME = "figure_06_municipality_scatter_exit_lowed"
TITLE = "Municipal exit rates track baseline low-education shares"


def build_figure_data() -> tuple[pd.DataFrame, dict[str, float]]:
    muni = load_muni_with_baseline_low_ed().copy()
    muni["region"] = muni["state"].map(STATE_REGIONS)
    missing_region = muni[muni["region"].isna()]["state"].drop_duplicates().sort_values().tolist()
    if missing_region:
        raise RuntimeError(f"Missing region mapping for states: {missing_region}")

    data = muni[
        [
            "ibge_municipality_id",
            "state",
            "region",
            "first_regime",
            "N_2008_total",
            "exit_rate_2008",
            "baseline_low_ed_share_2008",
        ]
    ].copy()
    data = data.dropna(subset=["N_2008_total", "exit_rate_2008", "baseline_low_ed_share_2008"])
    if len(data) != 4321:
        raise RuntimeError(f"Expected 4,321 treated municipalities, found {len(data):,}")

    reg = smf.ols(
        "exit_rate_2008 ~ baseline_low_ed_share_2008",
        data,
    ).fit(
        cov_type="cluster",
        cov_kwds={"groups": data["state"], "use_correction": True},
    )
    stats = {
        "slope": float(reg.params["baseline_low_ed_share_2008"]),
        "se": float(reg.bse["baseline_low_ed_share_2008"]),
        "intercept": float(reg.params["Intercept"]),
        "r2": float(reg.rsquared),
    }
    data["regression_slope"] = stats["slope"]
    data["regression_se"] = stats["se"]
    data["regression_r2"] = stats["r2"]
    data["regression_weighting"] = "unweighted"
    data = data.rename(
        columns={
            "N_2008_total": "municipality_baseline",
            "exit_rate_2008": "municipality_exit_rate",
            "baseline_low_ed_share_2008": "municipality_low_ed_share_2008",
        }
    )
    return data.reset_index(drop=True), stats


def plot(data: pd.DataFrame, stats: dict[str, float], fig, ax, title: str | None) -> None:
    for region, subset in data.groupby("region"):
        ax.scatter(
            subset["municipality_low_ed_share_2008"],
            subset["municipality_exit_rate"],
            s=16,
            color=REGION_COLORS[region],
            alpha=0.34,
            edgecolor="white",
            linewidth=0.15,
            label=region,
            zorder=3,
        )

    x_min = max(0.00, float(data["municipality_low_ed_share_2008"].min()) - 0.03)
    x_max = min(1.00, float(data["municipality_low_ed_share_2008"].max()) + 0.03)
    x_line = np.linspace(x_min, x_max, 100)
    y_line = stats["intercept"] + stats["slope"] * x_line
    ax.plot(x_line, y_line, color=COLORS["zero"], linewidth=1.2, linestyle="--", zorder=4)

    ax.text(
        0.03,
        0.97,
        f"Unweighted slope: {stats['slope']:.3f} ({stats['se']:.3f})\nR-squared: {stats['r2']:.2f}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#D1D5DB", "linewidth": 0.5, "pad": 3},
    )
    ax.set_xlabel("Municipality low-education share, 2008")
    ax.set_ylabel("Municipality exit rate, percent of 2008 baseline")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0, float(data["municipality_exit_rate"].max()) * 1.08)
    format_percent_axis(ax, "x")
    format_percent_axis(ax, "y")
    ax.legend(frameon=False, loc="upper right", ncol=1, markerscale=1.2)
    if title:
        ax.set_title(title, loc="left", pad=8)


def main() -> None:
    ensure_dirs()
    data, stats = build_figure_data()
    data.to_parquet(FIGURE_DATA_DIR / "figure_06_data.parquet", index=False)
    save_matplotlib_variants(
        lambda fig, ax, title: plot(data, stats, fig, ax, title),
        FILENAME,
        TITLE,
    )
    print(f"Saved {FILENAME} and figure_06_data.parquet")


if __name__ == "__main__":
    main()
