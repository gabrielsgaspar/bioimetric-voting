from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import statsmodels.formula.api as smf

try:
    from plot_style import apply_matplotlib_paper_style, save_pdf_png
except ImportError:  # pragma: no cover
    from src.analysis.plot_style import apply_matplotlib_paper_style, save_pdf_png


ROOT = Path(__file__).resolve().parents[2]
BVR_PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"
MAYOR_IDEOLOGY_PATH = ROOT / "data" / "clean" / "tse" / "tse_mayor_ideology_votes.parquet"

OUTPUT_DIR = ROOT / "resources" / "regressions" / "tse_mayor_ideology_bvr2016_never_did"
IMAGE_DIR = ROOT / "resources" / "images" / "regressions" / "tse_mayor_ideology_bvr2016_never_did"
SAMPLE_PATH = OUTPUT_DIR / "mayor_left_bvr2016_never_did_sample.csv"
REGRESSION_PATH = OUTPUT_DIR / "mayor_left_bvr2016_never_did_regression.csv"
PLOT_DATA_PATH = OUTPUT_DIR / "mayor_left_bvr2016_never_did_plot_data.csv"
FIGURE_BASE = IMAGE_DIR / "mayor_left_bvr2016_never_did"

OUTCOME = "pct_mayor_L"
YEARS = [2000, 2004, 2008, 2012, 2016, 2020]
BASELINE_YEAR = 2012


def build_status() -> pd.DataFrame:
    bvr = pd.read_parquet(BVR_PANEL_PATH)
    bvr_2016 = bvr.loc[bvr["year_election"].eq(2016)].copy()
    bvr_2016["municipality_id"] = bvr_2016["municipality_id"].astype(str).str.zfill(7)

    treated_ids = set(
        bvr_2016.loc[
            bvr_2016["year_first_any_bvr"].eq(2016)
            & bvr_2016["strict_bvr"].eq(1)
            & bvr_2016["hybrid"].eq(0),
            "municipality_id",
        ]
    )
    never_ids = set(bvr_2016.loc[bvr_2016["year_first_any_bvr"].eq(9999), "municipality_id"])

    status = pd.DataFrame({"municipality_id": sorted(treated_ids | never_ids)})
    status["treated_bvr_2016"] = status["municipality_id"].isin(treated_ids).astype(int)
    status["group"] = status["treated_bvr_2016"].map({1: "Strict BVR in 2016", 0: "Never BVR"})
    return status


def build_sample() -> pd.DataFrame:
    mayor = pd.read_parquet(MAYOR_IDEOLOGY_PATH)
    mayor = mayor.loc[mayor["year"].isin(YEARS)].copy()
    mayor["municipality_id"] = mayor["municipality_id"].astype(str).str.zfill(7)

    sample = mayor.merge(build_status(), on="municipality_id", how="inner")
    sample = sample.dropna(subset=[OUTCOME, "treated_bvr_2016", "year", "municipality_id"]).copy()

    balanced_ids = sample.groupby("municipality_id")["year"].nunique()
    balanced_ids = set(balanced_ids.loc[balanced_ids.eq(len(YEARS))].index)
    sample = sample.loc[sample["municipality_id"].isin(balanced_ids)].copy()

    sample["year"] = sample["year"].astype(int)
    sample["municipality_id"] = sample["municipality_id"].astype(str)
    sample["state"] = sample["state"].astype(str)
    sample["treated_bvr_2016"] = sample["treated_bvr_2016"].astype(int)
    sample["post_2016"] = sample["year"].ge(2016).astype(int)
    sample["treated_x_post"] = sample["treated_bvr_2016"] * sample["post_2016"]
    return sample.sort_values(["municipality_id", "year"]).reset_index(drop=True)


def run_did(sample: pd.DataFrame) -> pd.DataFrame:
    model = smf.ols(
        f"{OUTCOME} ~ treated_bvr_2016:post_2016 + C(municipality_id) + C(year)",
        data=sample,
    ).fit(cov_type="cluster", cov_kwds={"groups": sample["municipality_id"]}, use_t=True)
    term = "treated_bvr_2016:post_2016"
    return pd.DataFrame(
        [
            {
                "outcome": OUTCOME,
                "term": term,
                "coefficient": model.params[term],
                "std_error_cluster_municipality": model.bse[term],
                "p_value": model.pvalues[term],
                "conf_low": model.conf_int().loc[term, 0],
                "conf_high": model.conf_int().loc[term, 1],
                "n_observations": int(model.nobs),
                "n_municipalities": sample["municipality_id"].nunique(),
                "n_treated_municipalities": sample.loc[
                    sample["treated_bvr_2016"].eq(1), "municipality_id"
                ].nunique(),
                "n_control_municipalities": sample.loc[
                    sample["treated_bvr_2016"].eq(0), "municipality_id"
                ].nunique(),
                "years": ", ".join(str(year) for year in sorted(sample["year"].unique())),
                "estimation_note": (
                    "Municipality and election-year fixed effects, clustered by municipality. "
                    "Treated group is strict first-any BVR in 2016; controls are never observed with BVR "
                    "through the current 2018 panel. Hybrids are excluded."
                ),
            }
        ]
    )


def build_plot_data(sample: pd.DataFrame) -> pd.DataFrame:
    plot_data = (
        sample.groupby(["year", "group", "treated_bvr_2016"], as_index=False)
        .agg(
            mean_pct_mayor_L=(OUTCOME, "mean"),
            sd_pct_mayor_L=(OUTCOME, "std"),
            n_municipalities=("municipality_id", "nunique"),
        )
        .sort_values(["treated_bvr_2016", "year"])
    )
    plot_data["se_pct_mayor_L"] = plot_data["sd_pct_mayor_L"] / plot_data["n_municipalities"].pow(0.5)
    plot_data["ci_low"] = plot_data["mean_pct_mayor_L"] - 1.96 * plot_data["se_pct_mayor_L"]
    plot_data["ci_high"] = plot_data["mean_pct_mayor_L"] + 1.96 * plot_data["se_pct_mayor_L"]

    treated = plot_data.loc[plot_data["treated_bvr_2016"].eq(1)].set_index("year")
    control = plot_data.loc[plot_data["treated_bvr_2016"].eq(0)].set_index("year")
    baseline_treated_mean = treated.loc[BASELINE_YEAR, "mean_pct_mayor_L"]
    baseline_control_mean = control.loc[BASELINE_YEAR, "mean_pct_mayor_L"]
    counterfactual = control.reset_index()[["year", "mean_pct_mayor_L"]].copy()
    counterfactual["group"] = "Treated counterfactual"
    counterfactual["treated_bvr_2016"] = 2
    counterfactual["mean_pct_mayor_L"] = (
        baseline_treated_mean + counterfactual["mean_pct_mayor_L"] - baseline_control_mean
    )
    counterfactual["sd_pct_mayor_L"] = float("nan")
    counterfactual["n_municipalities"] = treated.loc[BASELINE_YEAR, "n_municipalities"]
    counterfactual["se_pct_mayor_L"] = float("nan")
    counterfactual["ci_low"] = float("nan")
    counterfactual["ci_high"] = float("nan")
    counterfactual = counterfactual.loc[counterfactual["year"].ge(BASELINE_YEAR)]

    return pd.concat([plot_data, counterfactual], ignore_index=True, sort=False)


def plot_did(plot_data: pd.DataFrame, regression: pd.DataFrame) -> None:
    apply_matplotlib_paper_style()
    fig, ax = plt.subplots(figsize=(7.2, 4.6))

    colors = {
        "Never BVR": "#4E79A7",
        "Strict BVR in 2016": "#D55E00",
        "Treated counterfactual": "#D55E00",
    }
    labels = {
        "Never BVR": "Never BVR",
        "Strict BVR in 2016": "BVR in 2016",
        "Treated counterfactual": "Counterfactual",
    }

    for group in ["Never BVR", "Strict BVR in 2016"]:
        group_data = plot_data.loc[plot_data["group"].eq(group)].sort_values("year")
        ax.plot(
            group_data["year"],
            group_data["mean_pct_mayor_L"],
            marker="o",
            linewidth=2,
            color=colors[group],
            label=labels[group],
        )
        ax.fill_between(
            group_data["year"].to_numpy(),
            group_data["ci_low"].astype(float).to_numpy(),
            group_data["ci_high"].astype(float).to_numpy(),
            color=colors[group],
            alpha=0.14,
            linewidth=0,
        )

    counterfactual = plot_data.loc[plot_data["group"].eq("Treated counterfactual")].sort_values("year")
    ax.plot(
        counterfactual["year"],
        counterfactual["mean_pct_mayor_L"],
        linestyle="--",
        linewidth=1.8,
        color=colors["Treated counterfactual"],
        label=labels["Treated counterfactual"],
    )

    estimate = regression.iloc[0]
    ax.axvline(2016, color="0.35", linewidth=1, linestyle=":")
    ax.axhline(0, color="0.75", linewidth=0.8)
    ax.text(
        0.02,
        0.98,
        (
            r"$\hat\beta_{\mathrm{DiD}} = "
            + f"{estimate['coefficient']:.3f}"
            + r"$"
            + "\n"
            + f"SE = {estimate['std_error_cluster_municipality']:.3f}, "
            + f"p = {estimate['p_value']:.3g}"
        ),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=10,
    )

    ax.set_xlabel("Election year")
    ax.set_ylabel("Share of mayoral votes for left parties")
    ax.set_xticks(YEARS)
    y_max = max(0.18, float(plot_data["ci_high"].max(skipna=True)) + 0.035)
    ax.set_ylim(0, min(1, y_max))
    ax.legend(frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save_pdf_png(fig, FIGURE_BASE, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    sample = build_sample()
    regression = run_did(sample)
    plot_data = build_plot_data(sample)
    plot_did(plot_data, regression)

    sample.to_csv(SAMPLE_PATH, index=False)
    regression.to_csv(REGRESSION_PATH, index=False)
    plot_data.to_csv(PLOT_DATA_PATH, index=False)

    print(f"Wrote {SAMPLE_PATH.relative_to(ROOT)}")
    print(f"Wrote {REGRESSION_PATH.relative_to(ROOT)}")
    print(f"Wrote {PLOT_DATA_PATH.relative_to(ROOT)}")
    print(f"Wrote {FIGURE_BASE.with_suffix('.pdf').relative_to(ROOT)}")
    print(f"Wrote {FIGURE_BASE.with_suffix('.png').relative_to(ROOT)}")
    print("\nRegression:")
    print(regression.to_string(index=False))
    print("\nPlot data:")
    print(plot_data.to_string(index=False))


if __name__ == "__main__":
    main()
