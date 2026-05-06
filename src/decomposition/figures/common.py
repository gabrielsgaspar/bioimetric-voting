from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[3]
DECOMP_DIR = ROOT / "data" / "clean" / "decomposition"
FIGURE_DATA_DIR = DECOMP_DIR / "figure_data"
FIGURE_DIR = ROOT / "resources" / "decomposition" / "figures"
TABLE_DIR = ROOT / "paper" / "tables" / "decomposition"

PAPER_FIGURE_WIDTH = 8.0
PAPER_FIGURE_HEIGHT = 5.0
PAPER_GRID_COLOR = "#D9D9D9"
PAPER_BORDER_COLOR = "black"
PAPER_SERIF_FONTS = ["Latin Modern Roman", "LM Roman 10", "Computer Modern Roman", "DejaVu Serif"]
PAPER_FONT_SIZE = 11

FINAL_AGG_PATH = DECOMP_DIR / "decomposition_final_aggregate_v2.parquet"
FINAL_MUNI_PATH = DECOMP_DIR / "decomposition_final_municipality_v2.parquet"
PANEL_PATH = DECOMP_DIR / "decomposition_panel_main_v2.parquet"
RELABEL_COHORT_PATH = DECOMP_DIR / "decomposition_relabel_cohort_v2.parquet"

COLORS = {
    "strict": "#006D77",
    "hybrid": "#E9A56A",
    "exit": "#2F5D7C",
    "relabel": "#F4A261",
    "zero": "#6B7280",
    "reference": "#9CA3AF",
}

REGION_COLORS = {
    "North": "#0072B2",
    "Northeast": "#E69F00",
    "Southeast": "#56B4E9",
    "South": "#CC79A7",
    "Center-West": "#6B7280",
}

STATE_REGIONS = {
    "AC": "North",
    "AM": "North",
    "AP": "North",
    "PA": "North",
    "RO": "North",
    "RR": "North",
    "TO": "North",
    "AL": "Northeast",
    "BA": "Northeast",
    "CE": "Northeast",
    "MA": "Northeast",
    "PB": "Northeast",
    "PE": "Northeast",
    "PI": "Northeast",
    "RN": "Northeast",
    "SE": "Northeast",
    "ES": "Southeast",
    "MG": "Southeast",
    "RJ": "Southeast",
    "SP": "Southeast",
    "PR": "South",
    "RS": "South",
    "SC": "South",
    "DF": "Center-West",
    "GO": "Center-West",
    "MS": "Center-West",
    "MT": "Center-West",
}

AGE_COHORT_ORDER = [
    "16 anos",
    "17 anos",
    "18 anos",
    "19 anos",
    "20 anos",
    "21 a 24 anos",
    "25 a 29 anos",
    "30 a 34 anos",
    "35 a 39 anos",
    "40 a 44 anos",
    "45 a 49 anos",
    "50 a 54 anos",
    "55 a 59 anos",
    "60 a 64 anos",
    "65 a 69 anos",
    "70 a 74 anos",
    "75 a 79 anos",
    "80 a 84 anos",
    "85 a 89 anos",
    "90 a 94 anos",
    "95 a 99 anos",
    "100 anos ou mais",
]

AGE_BANDS = ["16-24", "25-34", "35-44", "45-54", "55-64", "65+"]
AGE_BAND_MAP = {
    "16 anos": "16-24",
    "17 anos": "16-24",
    "18 anos": "16-24",
    "19 anos": "16-24",
    "20 anos": "16-24",
    "21 a 24 anos": "16-24",
    "25 a 29 anos": "25-34",
    "30 a 34 anos": "25-34",
    "35 a 39 anos": "35-44",
    "40 a 44 anos": "35-44",
    "45 a 49 anos": "45-54",
    "50 a 54 anos": "45-54",
    "55 a 59 anos": "55-64",
    "60 a 64 anos": "55-64",
    "65 a 69 anos": "65+",
    "70 a 74 anos": "65+",
    "75 a 79 anos": "65+",
    "80 a 84 anos": "65+",
    "85 a 89 anos": "65+",
    "90 a 94 anos": "65+",
    "95 a 99 anos": "65+",
    "100 anos ou mais": "65+",
}


def ensure_dirs() -> None:
    for path in [FIGURE_DIR, TABLE_DIR, FIGURE_DATA_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def set_plot_theme() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": PAPER_SERIF_FONTS,
            "font.size": PAPER_FONT_SIZE,
            "axes.titlesize": PAPER_FONT_SIZE,
            "axes.labelsize": PAPER_FONT_SIZE,
            "axes.edgecolor": PAPER_BORDER_COLOR,
            "axes.linewidth": 0.6,
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.spines.top": True,
            "axes.spines.right": True,
            "grid.color": PAPER_GRID_COLOR,
            "grid.linewidth": 0.8,
            "grid.linestyle": "-",
            "xtick.labelsize": PAPER_FONT_SIZE,
            "ytick.labelsize": PAPER_FONT_SIZE,
            "legend.fontsize": 10,
            "figure.dpi": 160,
            "savefig.dpi": 320,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def style_paper_axis(ax) -> None:
    ax.grid(True, which="major", axis="both", color=PAPER_GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ["top", "right", "bottom", "left"]:
        ax.spines[side].set_visible(True)
        ax.spines[side].set_linewidth(0.6)
        ax.spines[side].set_color(PAPER_BORDER_COLOR)


def percent_label(value: float) -> str:
    return f"{100 * float(value):.2f}%"


def normalize_muni_id(series: pd.Series) -> pd.Series:
    return series.astype(str).str.zfill(7)


def read_final_municipality() -> pd.DataFrame:
    final = pd.read_parquet(FINAL_MUNI_PATH)
    final = final.copy()
    final["ibge_municipality_id"] = normalize_muni_id(final["ibge_municipality_id"])
    final["state"] = final["state"].astype(str).str.upper().str.strip()
    return final[final["year_first_any_bvr"].lt(9999)].copy()


def read_panel(columns: list[str] | None = None) -> pd.DataFrame:
    panel = pd.read_parquet(PANEL_PATH, columns=columns)
    panel = panel.copy()
    panel["ibge_municipality_id"] = normalize_muni_id(panel["ibge_municipality_id"])
    if "state" in panel.columns:
        panel["state"] = panel["state"].astype(str).str.upper().str.strip()
    return panel


def build_baseline_low_ed_by_muni_year() -> pd.DataFrame:
    panel = read_panel(["ibge_municipality_id", "state", "year", "low_ed", "num_voters"])
    panel["low_ed_voters_2008"] = panel["num_voters"] * panel["low_ed"]
    baseline = (
        panel.groupby(["ibge_municipality_id", "state", "year"], as_index=False)
        .agg(
            baseline_low_ed_voters_2008=("low_ed_voters_2008", "sum"),
            baseline_total_2008_panel=("num_voters", "sum"),
        )
        .sort_values(["state", "ibge_municipality_id"])
    )
    baseline["baseline_low_ed_share_2008"] = (
        baseline["baseline_low_ed_voters_2008"] / baseline["baseline_total_2008_panel"].replace(0, np.nan)
    )
    return baseline


def load_muni_with_baseline_low_ed() -> pd.DataFrame:
    final = read_final_municipality()
    baseline_by_year = build_baseline_low_ed_by_muni_year()
    exact_2008 = baseline_by_year[baseline_by_year["year"].eq(2008)].drop(columns="year")
    out = final.merge(
        exact_2008,
        how="left",
        on=["ibge_municipality_id", "state"],
        validate="one_to_one",
    )
    out["baseline_low_ed_year_used"] = 2008
    out["baseline_low_ed_is_exact_2008"] = out["baseline_low_ed_share_2008"].notna()

    missing_mask = out["baseline_low_ed_share_2008"].isna()
    if missing_mask.any():
        fallback = baseline_by_year.rename(columns={"year": "baseline_year_used"})
        fallback = fallback.rename(
            columns={
                "baseline_low_ed_voters_2008": "fallback_low_ed_voters",
                "baseline_total_2008_panel": "fallback_total_panel",
                "baseline_low_ed_share_2008": "fallback_low_ed_share",
            }
        )
        out = out.merge(
            fallback,
            how="left",
            on=["ibge_municipality_id", "state", "baseline_year_used"],
            validate="one_to_one",
        )
        still_missing = out.loc[missing_mask, "fallback_low_ed_share"].isna().sum()
        if still_missing:
            raise RuntimeError(
                f"Missing baseline low-ed composition for {int(still_missing):,} treated municipalities"
            )
        for target, source in [
            ("baseline_low_ed_voters_2008", "fallback_low_ed_voters"),
            ("baseline_total_2008_panel", "fallback_total_panel"),
            ("baseline_low_ed_share_2008", "fallback_low_ed_share"),
        ]:
            out.loc[missing_mask, target] = out.loc[missing_mask, source]
        out.loc[missing_mask, "baseline_low_ed_year_used"] = out.loc[missing_mask, "baseline_year_used"]
        out = out.drop(columns=["fallback_low_ed_voters", "fallback_total_panel", "fallback_low_ed_share"])
    return out


def weighted_mean(values: pd.Series | np.ndarray, weights: pd.Series | np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    return float(np.average(values, weights=weights))


def weighted_se(values: pd.Series | np.ndarray, weights: pd.Series | np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if len(values) <= 1 or np.sum(weights) <= 0:
        return np.nan
    mean = np.average(values, weights=weights)
    variance = np.average((values - mean) ** 2, weights=weights)
    n_eff = (weights.sum() ** 2) / np.sum(weights**2)
    if n_eff <= 1:
        return np.nan
    return float(np.sqrt(variance / n_eff))


def assign_weighted_deciles(frame: pd.DataFrame, value_col: str, weight_col: str) -> pd.Series:
    ordered = frame.sort_values([value_col, weight_col], kind="mergesort").copy()
    weights = ordered[weight_col].astype(float)
    total = weights.sum()
    midpoint = (weights.cumsum() - 0.5 * weights) / total
    deciles = np.floor(midpoint * 10).astype(int) + 1
    deciles = np.clip(deciles, 1, 10)
    out = pd.Series(index=ordered.index, data=deciles, dtype="int64")
    return out.reindex(frame.index)


def fit_weighted_regression(
    formula: str,
    data: pd.DataFrame,
    weight_col: str,
    cluster_col: str | None = None,
):
    model = smf.wls(formula, data=data, weights=data[weight_col].astype(float))
    if cluster_col is None:
        return model.fit(cov_type="HC1")
    return model.fit(
        cov_type="cluster",
        cov_kwds={"groups": data[cluster_col], "use_correction": True},
    )


def save_matplotlib_variants(
    plotter,
    filename: str,
    title: str,
    width: float = PAPER_FIGURE_WIDTH,
    height: float = PAPER_FIGURE_HEIGHT,
) -> None:
    ensure_dirs()
    set_plot_theme()
    for with_title, suffix in [(True, ""), (False, "_notitle")]:
        fig, ax = plt.subplots(figsize=(width, height), constrained_layout=True)
        plotter(fig, ax, title if with_title else None)
        style_paper_axis(ax)
        fig.savefig(FIGURE_DIR / f"{filename}{suffix}.pdf", facecolor="white")
        fig.savefig(FIGURE_DIR / f"{filename}{suffix}.png", facecolor="white", dpi=320)
        plt.close(fig)


def format_percent_axis(ax, axis: str = "y") -> None:
    formatter = PercentFormatter(xmax=1.0, decimals=0)
    if axis == "x":
        ax.xaxis.set_major_formatter(formatter)
    else:
        ax.yaxis.set_major_formatter(formatter)
