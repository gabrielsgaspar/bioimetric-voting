from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

try:
    from plot_style import apply_matplotlib_paper_style, save_pdf_png
except ImportError:  # pragma: no cover
    from src.analysis.plot_style import apply_matplotlib_paper_style, save_pdf_png


ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = ROOT / "resources" / "did" / "siconfi_bdd" / "baseline"
PLOT_DIR = ROOT / "resources" / "images" / "regressions" / "estimator_comparison" / "siconfi_bdd"
TARGET_OUTCOMES = [
    "health_spending_pc",
    "education_spending_pc",
    "social_assistance_pc",
    "total_spending_pc",
    "agriculture_pc",
    "investment_spending_pc",
]
ESTIMATORS = [
    ("twfe_dynamic", "Dynamic TWFE", "#2C5A8A"),
    ("callaway_santanna", "Callaway-Sant'Anna", "#2F7D32"),
    ("bjs", "BJS", "#B23A48"),
]
X_TICKS = list(range(-8, 9, 2))
OUTCOME_TITLES = {
    "health_spending_pc": "Health",
    "education_spending_pc": "Education",
    "social_assistance_pc": "Social assistance",
    "total_spending_pc": "Total spending",
    "agriculture_pc": "Agriculture",
    "investment_spending_pc": "Investment",
}


def load_event_study(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if "event_time" not in df.columns:
        return None
    df["event_time"] = pd.to_numeric(df["event_time"], errors="coerce")
    df = df[df["event_time"].isin(X_TICKS)].copy()
    if df.empty:
        return None
    return df


def build_plot() -> None:
    apply_matplotlib_paper_style()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(15, 8.4), sharex=True)
    axes = axes.flatten()

    plotted_any = False
    for ax, outcome in zip(axes, TARGET_OUTCOMES):
        outcome_found = False
        for idx, (estimator, label, color) in enumerate(ESTIMATORS):
            path = BASE_DIR / outcome / estimator / "event_study_estimates.csv"
            df = load_event_study(path)
            if df is None:
                continue
            outcome_found = True
            plotted_any = True
            x = df["event_time"] + (idx - 1) * 0.16
            ax.errorbar(
                x,
                df["estimate"],
                yerr=[df["estimate"] - df["conf.low"], df["conf.high"] - df["estimate"]],
                fmt="o",
                linestyle="none",
                color=color,
                ecolor=color,
                markersize=4.8,
                elinewidth=1.0,
                label=label,
            )
        ax.axhline(0, color="0.35", linewidth=0.9)
        ax.set_xticks(X_TICKS)
        ax.set_title(OUTCOME_TITLES.get(outcome, outcome))
        ax.grid(True, which="major", axis="both", color="#D9D9D9", linewidth=0.8)
        if outcome_found:
            all_bounds = []
            for estimator, _, _ in ESTIMATORS:
                path = BASE_DIR / outcome / estimator / "event_study_estimates.csv"
                df = load_event_study(path)
                if df is not None:
                    all_bounds.extend(df["conf.low"].tolist())
                    all_bounds.extend(df["conf.high"].tolist())
            if all_bounds:
                max_abs = max(0.10, max(abs(v) for v in all_bounds))
                max_abs = math.ceil(max_abs / 0.05) * 0.05
                ax.set_ylim(-max_abs, max_abs)
        else:
            ax.text(0.5, 0.5, "Not available", ha="center", va="center", transform=ax.transAxes)

    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    if plotted_any:
        save_pdf_png(fig, PLOT_DIR / "fiscal_grid")
    plt.close(fig)


if __name__ == "__main__":
    build_plot()
