from __future__ import annotations

from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf


ROOT = Path(__file__).resolve().parents[2]
BVR_PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"
MAYOR_IDEOLOGY_PATH = ROOT / "data" / "clean" / "tse" / "tse_mayor_ideology_votes.parquet"
VEREADOR_IDEOLOGY_PATH = ROOT / "data" / "clean" / "tse" / "tse_vereador_ideology_votes.parquet"
OUTPUT_DIR = ROOT / "resources" / "regressions" / "tse_ideology_hybrid2016"
RESULTS_PATH = OUTPUT_DIR / "hybrid2016_ideology_regressions.csv"
SAMPLE_PATH = OUTPUT_DIR / "hybrid2016_ideology_sample.csv"
DIAGNOSTICS_PATH = OUTPUT_DIR / "hybrid2016_ideology_diagnostics.csv"

ELECTIONS = {
    "mayor": {
        "path": MAYOR_IDEOLOGY_PATH,
        "outcomes": ["pct_mayor_R", "pct_mayor_L", "pct_mayor_C"],
    },
    "vereador": {
        "path": VEREADOR_IDEOLOGY_PATH,
        "outcomes": ["pct_vereador_R", "pct_vereador_L", "pct_vereador_C"],
    },
}

CONTROL_SPECS = {
    "hybrid_vs_no_bvr_2016": "no_bvr_2016",
    "hybrid_vs_never_bvr": "never_bvr",
}


def treatment_status(control_type: str) -> pd.DataFrame:
    bvr = pd.read_parquet(BVR_PANEL_PATH)
    bvr_2016 = bvr.loc[bvr["year_election"] == 2016].copy()
    bvr_2016["municipality_id"] = bvr_2016["municipality_id"].astype(str).str.zfill(7)

    treated_ids = set(bvr_2016.loc[bvr_2016["hybrid"].eq(1), "municipality_id"])
    if control_type == "no_bvr_2016":
        control_ids = set(bvr_2016.loc[bvr_2016["no_bvr"].eq(1), "municipality_id"])
    elif control_type == "never_bvr":
        control_ids = set(bvr_2016.loc[bvr_2016["year_first_any_bvr"].eq(9999), "municipality_id"])
    else:
        raise ValueError(f"Unknown control type: {control_type}")

    status = pd.DataFrame({"municipality_id": sorted(treated_ids | control_ids)})
    status["treated_hybrid_2016"] = status["municipality_id"].isin(treated_ids).astype(int)
    return status


def build_sample(election: str, spec_name: str, control_type: str) -> pd.DataFrame:
    vote_path = ELECTIONS[election]["path"]
    votes = pd.read_parquet(vote_path)
    votes = votes.loc[votes["year"].isin([2012, 2016])].copy()
    votes["municipality_id"] = votes["municipality_id"].astype(str).str.zfill(7)

    sample = votes.merge(treatment_status(control_type), on="municipality_id", how="inner")
    balanced_ids = sample.groupby("municipality_id")["year"].nunique()
    balanced_ids = set(balanced_ids.loc[balanced_ids.eq(2)].index)
    sample = sample.loc[sample["municipality_id"].isin(balanced_ids)].copy()
    sample["year"] = sample["year"].astype(int)
    sample["municipality_id"] = sample["municipality_id"].astype(str)
    sample["state"] = sample["state"].astype(str)
    sample["treated_hybrid_2016"] = sample["treated_hybrid_2016"].astype(int)
    sample["treat_hybrid2016_x_2016"] = (
        sample["treated_hybrid_2016"].eq(1) & sample["year"].eq(2016)
    ).astype(int)
    sample["election"] = election
    sample["spec"] = spec_name
    return sample.sort_values(["spec", "election", "municipality_id", "year"]).reset_index(drop=True)


def run_regression(sample: pd.DataFrame, outcome: str) -> dict[str, float | int | str]:
    model_df = sample.dropna(subset=[outcome, "treated_hybrid_2016", "municipality_id", "year"]).copy()
    wide = model_df.pivot(index="municipality_id", columns="year", values=outcome)
    wide = wide.dropna(subset=[2012, 2016]).copy()
    treated = model_df[["municipality_id", "treated_hybrid_2016"]].drop_duplicates("municipality_id")
    diff_df = (
        wide.assign(delta_outcome=wide[2016] - wide[2012])
        .reset_index()[["municipality_id", "delta_outcome"]]
        .merge(treated, on="municipality_id", how="left")
    )
    model = smf.ols("delta_outcome ~ treated_hybrid_2016", data=diff_df).fit(
        cov_type="cluster",
        cov_kwds={"groups": diff_df["municipality_id"]},
        use_t=True,
    )
    term = "treated_hybrid_2016"
    return {
        "spec": sample["spec"].iloc[0],
        "election": sample["election"].iloc[0],
        "outcome": outcome,
        "coefficient": model.params[term],
        "std_error_cluster_municipality": model.bse[term],
        "p_value": model.pvalues[term],
        "n_observations": int(model_df.loc[model_df["municipality_id"].isin(diff_df["municipality_id"])].shape[0]),
        "n_municipalities": int(diff_df["municipality_id"].nunique()),
        "n_treated_municipalities": int(diff_df.loc[diff_df["treated_hybrid_2016"].eq(1), "municipality_id"].nunique()),
        "n_control_municipalities": int(diff_df.loc[diff_df["treated_hybrid_2016"].eq(0), "municipality_id"].nunique()),
        "years": ", ".join(str(year) for year in sorted(model_df["year"].unique())),
        "estimation_note": "First-difference equivalent of municipality and year fixed effects for the balanced 2012/2016 panel.",
    }


def build_diagnostics(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (spec, election, year), group in sample.groupby(["spec", "election", "year"]):
        rows.append(
            {
                "spec": spec,
                "election": election,
                "year": int(year),
                "rows": len(group),
                "municipalities": group["municipality_id"].nunique(),
                "treated_municipalities": group.loc[group["treated_hybrid_2016"].eq(1), "municipality_id"].nunique(),
                "control_municipalities": group.loc[group["treated_hybrid_2016"].eq(0), "municipality_id"].nunique(),
            }
        )
    return pd.DataFrame(rows).sort_values(["spec", "election", "year"])


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    samples = []
    results = []
    for spec_name, control_type in CONTROL_SPECS.items():
        for election, config in ELECTIONS.items():
            sample = build_sample(election, spec_name, control_type)
            samples.append(sample)
            for outcome in config["outcomes"]:
                results.append(run_regression(sample, outcome))

    sample_df = pd.concat(samples, ignore_index=True)
    results_df = pd.DataFrame(results)
    diagnostics_df = build_diagnostics(sample_df)

    sample_df.to_csv(SAMPLE_PATH, index=False)
    results_df.to_csv(RESULTS_PATH, index=False)
    diagnostics_df.to_csv(DIAGNOSTICS_PATH, index=False)

    print(f"Wrote {RESULTS_PATH.relative_to(ROOT)}")
    print(f"Wrote {DIAGNOSTICS_PATH.relative_to(ROOT)}")
    print(f"Wrote {SAMPLE_PATH.relative_to(ROOT)}")
    print("\nResults:")
    print(results_df.to_string(index=False))
    print("\nDiagnostics:")
    print(diagnostics_df.to_string(index=False))


if __name__ == "__main__":
    main()
