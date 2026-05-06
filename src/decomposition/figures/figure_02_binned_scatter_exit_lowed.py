from __future__ import annotations

import numpy as np
import pandas as pd

from common import (
    COLORS,
    FIGURE_DATA_DIR,
    assign_weighted_deciles,
    ensure_dirs,
    fit_weighted_regression,
    format_percent_axis,
    load_muni_with_baseline_low_ed,
    save_matplotlib_variants,
    weighted_mean,
    weighted_se,
)


FILENAME = "figure_02_binned_scatter_exit_lowed"
TITLE = "Municipal exit rises with baseline low-education share"


def build_regime_regressions(muni: pd.DataFrame) -> dict[str, dict[str, float]]:
    regressions: dict[str, dict[str, float]] = {}
    for regime, frame in muni.groupby("first_regime"):
        result = fit_weighted_regression(
            "exit_rate_2008 ~ baseline_low_ed_share_2008 + C(state)",
            frame,
            "N_2008_total",
            cluster_col="state",
        )
        slope = float(result.params["baseline_low_ed_share_2008"])
        se = float(result.bse["baseline_low_ed_share_2008"])
        regressions[str(regime)] = {
            "slope": slope,
            "se": se,
            "xbar": weighted_mean(frame["baseline_low_ed_share_2008"], frame["N_2008_total"]),
            "ybar": weighted_mean(frame["exit_rate_2008"], frame["N_2008_total"]),
            "x_min": float(frame["baseline_low_ed_share_2008"].min()),
            "x_max": float(frame["baseline_low_ed_share_2008"].max()),
        }
    return regressions


def build_figure_data() -> pd.DataFrame:
    muni = load_muni_with_baseline_low_ed()
    if len(muni) != 4321:
        raise RuntimeError(f"Expected 4,321 treated municipalities, found {len(muni):,}")
    regressions = build_regime_regressions(muni)

    rows = []
    for regime, frame in muni.groupby("first_regime"):
        frame = frame.copy()
        frame["decile"] = assign_weighted_deciles(
            frame,
            "baseline_low_ed_share_2008",
            "N_2008_total",
        )
        reg = regressions[str(regime)]
        for decile, bin_frame in frame.groupby("decile"):
            x_mean = weighted_mean(bin_frame["baseline_low_ed_share_2008"], bin_frame["N_2008_total"])
            y_mean = weighted_mean(bin_frame["exit_rate_2008"], bin_frame["N_2008_total"])
            se = weighted_se(bin_frame["exit_rate_2008"], bin_frame["N_2008_total"])
            ci_half = 1.96 * se if not np.isnan(se) else np.nan
            rows.append(
                {
                    "regime": str(regime),
                    "decile": int(decile),
                    "n_munis": int(bin_frame["ibge_municipality_id"].nunique()),
                    "weighted_low_ed_share": x_mean,
                    "weighted_exit_rate": y_mean,
                    "ci_lower": max(0.0, y_mean - ci_half) if not np.isnan(ci_half) else np.nan,
                    "ci_upper": y_mean + ci_half if not np.isnan(ci_half) else np.nan,
                    "regression_slope": reg["slope"],
                    "regression_se": reg["se"],
                    "regression_xbar": reg["xbar"],
                    "regression_ybar": reg["ybar"],
                }
            )
    data = pd.DataFrame(rows)
    data["regime"] = pd.Categorical(data["regime"], categories=["strict", "hybrid"], ordered=True)
    return data.sort_values(["regime", "decile"]).reset_index(drop=True)


def plot(data: pd.DataFrame, fig, ax, title: str | None) -> None:
    for regime, label in [("strict", "Strict"), ("hybrid", "Hybrid")]:
        subset = data[data["regime"].astype(str).eq(regime)].copy()
        color = COLORS[regime]
        ax.fill_between(
            subset["weighted_low_ed_share"].to_numpy(dtype=float),
            subset["ci_lower"].to_numpy(dtype=float),
            subset["ci_upper"].to_numpy(dtype=float),
            color=color,
            alpha=0.16,
            linewidth=0,
        )
        ax.plot(
            subset["weighted_low_ed_share"],
            subset["weighted_exit_rate"],
            marker="o",
            color=color,
            linewidth=1.6,
            markersize=4,
            label=f"{label} bins",
        )

        slope = float(subset["regression_slope"].iloc[0])
        xbar = float(subset["regression_xbar"].iloc[0])
        ybar = float(subset["regression_ybar"].iloc[0])
        x_line = np.linspace(subset["weighted_low_ed_share"].min(), subset["weighted_low_ed_share"].max(), 100)
        y_line = ybar + slope * (x_line - xbar)
        ax.plot(x_line, y_line, color=color, linestyle="--", linewidth=1.1, alpha=0.9)

    text_lines = []
    for regime, label in [("strict", "Strict"), ("hybrid", "Hybrid")]:
        subset = data[data["regime"].astype(str).eq(regime)]
        slope = float(subset["regression_slope"].iloc[0])
        se = float(subset["regression_se"].iloc[0])
        text_lines.append(f"{label} FE slope: {slope:.3f} ({se:.3f})")
    ax.text(
        0.03,
        0.97,
        "\n".join(text_lines),
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=10,
            bbox={"facecolor": "white", "edgecolor": "#D1D5DB", "linewidth": 0.5, "pad": 3},
        )

    ax.set_xlabel("Low-education share of 2008 electorate")
    ax.set_ylabel("Exit rate, percent of 2008 baseline")
    ax.set_xlim(0.40, 1)
    ax.set_ylim(0, max(0.01, data["ci_upper"].max() * 1.08))
    format_percent_axis(ax, "x")
    format_percent_axis(ax, "y")
    ax.legend(frameon=False, loc="lower right")
    if title:
        ax.set_title(title, loc="left", pad=8)


def main() -> None:
    ensure_dirs()
    data = build_figure_data()
    data.to_parquet(FIGURE_DATA_DIR / "figure_02_data.parquet", index=False)
    save_matplotlib_variants(
        lambda fig, ax, title: plot(data, fig, ax, title),
        FILENAME,
        TITLE,
    )
    print(f"Saved {FILENAME} and figure_02_data.parquet")


if __name__ == "__main__":
    main()
