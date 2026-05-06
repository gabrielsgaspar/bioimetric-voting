from __future__ import annotations

from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf


ROOT = Path(__file__).resolve().parents[2]
BVR_PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"
MAYOR_IDEOLOGY_PATH = ROOT / "data" / "clean" / "tse" / "tse_mayor_ideology_votes.parquet"
GDP_PATH = ROOT / "data" / "clean" / "ibge" / "municipality_gdp_population_survey_years.parquet"
OUTPUT_DIR = ROOT / "resources" / "regressions" / "tse_mayor_ideology_bvr2016_gdp_split"
RESULTS_PATH = OUTPUT_DIR / "bvr2016_never_mayor_ideology_gdp_split_regressions.csv"
STANDARDIZED_RESULTS_PATH = OUTPUT_DIR / "bvr2016_never_mayor_ideology_gdp_split_regressions_zscore.csv"
SAMPLE_PATH = OUTPUT_DIR / "bvr2016_never_mayor_ideology_gdp_split_sample.csv"
DIAGNOSTICS_PATH = OUTPUT_DIR / "bvr2016_never_mayor_ideology_gdp_split_diagnostics.csv"

OUTCOMES = ["pct_mayor_R", "pct_mayor_L", "pct_mayor_C"]
BASELINE_GDP_YEAR = 2012


def build_status() -> pd.DataFrame:
    bvr = pd.read_parquet(BVR_PANEL_PATH)
    bvr_2016 = bvr.loc[bvr["year_election"] == 2016].copy()
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
    return status


def build_sample() -> tuple[pd.DataFrame, float]:
    mayor = pd.read_parquet(MAYOR_IDEOLOGY_PATH)
    mayor = mayor.loc[mayor["year"].isin([2012, 2016])].copy()
    mayor["municipality_id"] = mayor["municipality_id"].astype(str).str.zfill(7)

    gdp = pd.read_parquet(GDP_PATH)
    gdp = gdp.loc[gdp["year"].eq(BASELINE_GDP_YEAR), ["municipality_id", "gdp_pc", "log_gdp_pc"]].copy()
    gdp["municipality_id"] = gdp["municipality_id"].astype(str).str.zfill(7)
    gdp = gdp.dropna(subset=["gdp_pc"]).drop_duplicates("municipality_id")

    sample = mayor.merge(build_status(), on="municipality_id", how="inner")
    balanced_ids = sample.groupby("municipality_id")["year"].nunique()
    balanced_ids = set(balanced_ids.loc[balanced_ids.eq(2)].index)
    sample = sample.loc[sample["municipality_id"].isin(balanced_ids)].copy()
    sample = sample.merge(gdp, on="municipality_id", how="inner")

    gdp_by_muni = sample[["municipality_id", "gdp_pc"]].drop_duplicates("municipality_id")
    median_gdp_pc = float(gdp_by_muni["gdp_pc"].median())

    sample["gdp_split"] = "above_or_equal_median"
    sample.loc[sample["gdp_pc"] < median_gdp_pc, "gdp_split"] = "below_median"
    sample["gdp_median_cutoff"] = median_gdp_pc
    sample["baseline_gdp_year"] = BASELINE_GDP_YEAR
    sample["year"] = sample["year"].astype(int)
    sample["municipality_id"] = sample["municipality_id"].astype(str)
    sample["state"] = sample["state"].astype(str)
    sample["treated_bvr_2016"] = sample["treated_bvr_2016"].astype(int)
    sample["treat_bvr2016_x_2016"] = (sample["treated_bvr_2016"].eq(1) & sample["year"].eq(2016)).astype(int)
    return sample.sort_values(["municipality_id", "year"]).reset_index(drop=True), median_gdp_pc


def run_regression(
    sample: pd.DataFrame,
    outcome: str,
    subgroup: str,
    *,
    standardize_outcome: bool = False,
) -> dict[str, float | int | str]:
    if subgroup == "full_sample":
        model_df = sample.copy()
    else:
        model_df = sample.loc[sample["gdp_split"].eq(subgroup)].copy()

    model_df = model_df.dropna(subset=[outcome, "treated_bvr_2016", "municipality_id", "year"])
    outcome_sd = float(model_df[outcome].std(ddof=1))
    if standardize_outcome:
        if outcome_sd <= 0:
            raise ValueError(f"Cannot z-score {outcome} in {subgroup}; sample standard deviation is {outcome_sd}.")
        model_df = model_df.copy()
        model_df[outcome] = (model_df[outcome] - model_df[outcome].mean()) / outcome_sd

    wide = model_df.pivot(index="municipality_id", columns="year", values=outcome)
    wide = wide.dropna(subset=[2012, 2016]).copy()
    treated = model_df[["municipality_id", "treated_bvr_2016"]].drop_duplicates("municipality_id")
    diff_df = (
        wide.assign(delta_outcome=wide[2016] - wide[2012])
        .reset_index()[["municipality_id", "delta_outcome"]]
        .merge(treated, on="municipality_id", how="left")
    )
    model = smf.ols("delta_outcome ~ treated_bvr_2016", data=diff_df).fit(
        cov_type="cluster",
        cov_kwds={"groups": diff_df["municipality_id"]},
        use_t=True,
    )
    term = "treated_bvr_2016"
    return {
        "subgroup": subgroup,
        "outcome": outcome,
        "outcome_scale": "z_score" if standardize_outcome else "raw_share",
        "outcome_sd_used_for_zscore": outcome_sd if standardize_outcome else pd.NA,
        "coefficient": model.params[term],
        "std_error_cluster_municipality": model.bse[term],
        "p_value": model.pvalues[term],
        "n_observations": int(model_df.loc[model_df["municipality_id"].isin(diff_df["municipality_id"])].shape[0]),
        "n_municipalities": int(diff_df["municipality_id"].nunique()),
        "n_treated_municipalities": int(diff_df.loc[diff_df["treated_bvr_2016"].eq(1), "municipality_id"].nunique()),
        "n_control_municipalities": int(diff_df.loc[diff_df["treated_bvr_2016"].eq(0), "municipality_id"].nunique()),
        "years": ", ".join(str(year) for year in sorted(model_df["year"].unique())),
        "estimation_note": "First-difference equivalent of municipality and year fixed effects for the balanced 2012/2016 panel.",
    }


def build_diagnostics(sample: pd.DataFrame, median_gdp_pc: float) -> pd.DataFrame:
    rows = []
    for subgroup in ["full_sample", "below_median", "above_or_equal_median"]:
        group = sample if subgroup == "full_sample" else sample.loc[sample["gdp_split"].eq(subgroup)]
        muni = group[["municipality_id", "treated_bvr_2016", "gdp_pc"]].drop_duplicates("municipality_id")
        rows.append(
            {
                "subgroup": subgroup,
                "baseline_gdp_year": BASELINE_GDP_YEAR,
                "median_gdp_pc_cutoff": median_gdp_pc,
                "rows": len(group),
                "municipalities": muni["municipality_id"].nunique(),
                "treated_municipalities": int(muni["treated_bvr_2016"].sum()),
                "control_municipalities": int(muni["treated_bvr_2016"].eq(0).sum()),
                "min_gdp_pc": muni["gdp_pc"].min(),
                "max_gdp_pc": muni["gdp_pc"].max(),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sample, median_gdp_pc = build_sample()
    subgroups = ["full_sample", "below_median", "above_or_equal_median"]
    results = pd.DataFrame(
        [run_regression(sample, outcome, subgroup) for subgroup in subgroups for outcome in OUTCOMES]
    )
    standardized_results = pd.DataFrame(
        [
            run_regression(sample, outcome, subgroup, standardize_outcome=True)
            for subgroup in subgroups
            for outcome in OUTCOMES
        ]
    )
    diagnostics = build_diagnostics(sample, median_gdp_pc)

    sample.to_csv(SAMPLE_PATH, index=False)
    results.to_csv(RESULTS_PATH, index=False)
    standardized_results.to_csv(STANDARDIZED_RESULTS_PATH, index=False)
    diagnostics.to_csv(DIAGNOSTICS_PATH, index=False)

    print(f"Wrote {RESULTS_PATH.relative_to(ROOT)}")
    print(f"Wrote {STANDARDIZED_RESULTS_PATH.relative_to(ROOT)}")
    print(f"Wrote {DIAGNOSTICS_PATH.relative_to(ROOT)}")
    print(f"Wrote {SAMPLE_PATH.relative_to(ROOT)}")
    print(f"\nBaseline GDP year: {BASELINE_GDP_YEAR}")
    print(f"Median GDP per capita cutoff: {median_gdp_pc:.6f}")
    print("\nResults:")
    print(results.to_string(index=False))
    print("\nZ-score standardized results:")
    print(standardized_results.to_string(index=False))
    print("\nDiagnostics:")
    print(diagnostics.to_string(index=False))


if __name__ == "__main__":
    main()
