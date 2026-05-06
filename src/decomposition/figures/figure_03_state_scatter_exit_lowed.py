from __future__ import annotations

import numpy as np
import pandas as pd

from common import (
    COLORS,
    FIGURE_DATA_DIR,
    REGION_COLORS,
    STATE_REGIONS,
    ensure_dirs,
    fit_weighted_regression,
    format_percent_axis,
    load_muni_with_baseline_low_ed,
    save_matplotlib_variants,
)


FILENAME = "figure_03_state_scatter_exit_lowed"
TITLE = "State exit rates track baseline low-education shares"


def repel_label_positions(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy().sort_values("state").reset_index(drop=True)
    x = out["state_low_ed_share_2008"].to_numpy(dtype=float)
    y = out["state_exit_rate"].to_numpy(dtype=float)
    x_span = max(float(x.max() - x.min()), 1e-6)
    y_span = max(float(y.max() - y.min()), 1e-6)
    xn = (x - x.min()) / x_span
    yn = (y - y.min()) / y_span

    angles = np.linspace(0, 2 * np.pi, len(out), endpoint=False)
    lx = xn + 0.035 * np.cos(angles)
    ly = yn + 0.045 * np.sin(angles)
    min_dx = 0.055
    min_dy = 0.050
    for _ in range(250):
        moved = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                dx = lx[j] - lx[i]
                dy = ly[j] - ly[i]
                if abs(dx) < min_dx and abs(dy) < min_dy:
                    push_x = (min_dx - abs(dx)) * (1 if dx >= 0 else -1) / 2
                    push_y = (min_dy - abs(dy)) * (1 if dy >= 0 else -1) / 2
                    lx[j] += push_x
                    lx[i] -= push_x
                    ly[j] += push_y
                    ly[i] -= push_y
                    moved = True
        lx = np.clip(lx, -0.03, 1.03)
        ly = np.clip(ly, -0.05, 1.05)
        if not moved:
            break

    out["label_x"] = x.min() + lx * x_span
    out["label_y"] = y.min() + ly * y_span
    return out


def build_figure_data() -> tuple[pd.DataFrame, dict[str, float]]:
    muni = load_muni_with_baseline_low_ed()
    muni["baseline_low_ed_count"] = muni["baseline_low_ed_voters_2008"]
    muni["state_exit_count"] = muni["exit_count"]

    state = (
        muni.groupby("state", as_index=False)
        .agg(
            state_baseline=("N_2008_total", "sum"),
            state_exit_count=("state_exit_count", "sum"),
            state_low_ed_count=("baseline_low_ed_count", "sum"),
            state_baseline_panel=("baseline_total_2008_panel", "sum"),
        )
        .sort_values("state")
    )
    state["state_exit_rate"] = state["state_exit_count"] / state["state_baseline"].replace(0, np.nan)
    state["state_low_ed_share_2008"] = (
        state["state_low_ed_count"] / state["state_baseline_panel"].replace(0, np.nan)
    )
    state["region"] = state["state"].map(STATE_REGIONS)
    missing_region = state[state["region"].isna()]["state"].tolist()
    if missing_region:
        raise RuntimeError(f"Missing region mapping for states: {missing_region}")

    reg = fit_weighted_regression(
        "state_exit_rate ~ state_low_ed_share_2008",
        state,
        "state_baseline",
        cluster_col=None,
    )
    stats = {
        "slope": float(reg.params["state_low_ed_share_2008"]),
        "se": float(reg.bse["state_low_ed_share_2008"]),
        "intercept": float(reg.params["Intercept"]),
        "r2": float(reg.rsquared),
    }
    state = repel_label_positions(state)
    state["regression_slope"] = stats["slope"]
    state["regression_se"] = stats["se"]
    state["regression_r2"] = stats["r2"]
    keep = [
        "state",
        "region",
        "state_baseline",
        "state_exit_rate",
        "state_low_ed_share_2008",
        "label_x",
        "label_y",
        "regression_slope",
        "regression_se",
        "regression_r2",
    ]
    return state[keep].reset_index(drop=True), stats


def plot(data: pd.DataFrame, stats: dict[str, float], fig, ax, title: str | None) -> None:
    max_baseline = data["state_baseline"].max()
    for region, subset in data.groupby("region"):
        sizes = 30 + 180 * np.sqrt(subset["state_baseline"] / max_baseline)
        ax.scatter(
            subset["state_low_ed_share_2008"],
            subset["state_exit_rate"],
            s=sizes,
            color=REGION_COLORS[region],
            alpha=0.82,
            edgecolor="white",
            linewidth=0.6,
            label=region,
            zorder=3,
        )

    for _, row in data.iterrows():
        ax.plot(
            [row["state_low_ed_share_2008"], row["label_x"]],
            [row["state_exit_rate"], row["label_y"]],
            color="#D1D5DB",
            linewidth=0.4,
            zorder=1,
        )
        ax.text(
            row["label_x"],
            row["label_y"],
            row["state"],
            ha="center",
            va="center",
            fontsize=9,
            color="#111827",
            zorder=4,
        )

    x_line = np.linspace(data["state_low_ed_share_2008"].min(), data["state_low_ed_share_2008"].max(), 100)
    y_line = stats["intercept"] + stats["slope"] * x_line
    ax.plot(x_line, y_line, color=COLORS["zero"], linewidth=1.2, linestyle="--", zorder=2)

    ax.text(
        0.03,
        0.97,
        f"Weighted slope: {stats['slope']:.3f} ({stats['se']:.3f})\nR-squared: {stats['r2']:.2f}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#D1D5DB", "linewidth": 0.5, "pad": 3},
    )
    ax.set_xlabel("State low-education share, 2008")
    ax.set_ylabel("State exit rate, percent of 2008 baseline")
    ax.set_xlim(max(0, data["state_low_ed_share_2008"].min() - 0.03), min(1, data["state_low_ed_share_2008"].max() + 0.03))
    ax.set_ylim(max(0, data["state_exit_rate"].min() - 0.015), data["state_exit_rate"].max() + 0.035)
    format_percent_axis(ax, "x")
    format_percent_axis(ax, "y")
    ax.legend(frameon=False, loc="lower right", ncol=2)
    if title:
        ax.set_title(title, loc="left", pad=8)


def main() -> None:
    ensure_dirs()
    data, stats = build_figure_data()
    data.to_parquet(FIGURE_DATA_DIR / "figure_03_data.parquet", index=False)
    save_matplotlib_variants(
        lambda fig, ax, title: plot(data, stats, fig, ax, title),
        FILENAME,
        TITLE,
    )
    print(f"Saved {FILENAME} and figure_03_data.parquet")


if __name__ == "__main__":
    main()
