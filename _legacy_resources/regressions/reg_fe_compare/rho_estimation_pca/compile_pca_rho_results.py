#!/usr/bin/env python3
"""Compile PCA-based rho estimation results and comparison tables."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path("resources/regressions/reg_fe_compare")
OUT_DIR = ROOT / "rho_estimation_pca"
REG_DIR = OUT_DIR / "regressions"
ORIGINAL_SUMMARY = ROOT / "rho_estimation" / "rho_regression_summary.csv"

COST_VARIABLE = {
    "rho_L": "cost_proxy_low_ed",
    "rho_H": "cost_proxy_high_ed",
    "rho_gap": "compliance_gap",
}

COST_LABEL = {
    "cost_proxy_low_ed": "Low-ed revealed cost",
    "cost_proxy_high_ed": "High-ed revealed cost",
    "compliance_gap": "High-low compliance gap",
}

ORDER = ["cost_proxy_low_ed", "cost_proxy_high_ed", "compliance_gap"]


def parse_run_name(name: str) -> dict[str, str]:
    parts = name.split("_")
    measure = "_".join(parts[:2])
    outcome_type = parts[-1]
    return {
        "run_name": name,
        "rho_measure": measure,
        "outcome_type": "pc1" if outcome_type == "pca" else "mean",
        "cost_variable": COST_VARIABLE[measure],
    }


def read_result(path: Path) -> dict[str, object]:
    obj = json.loads(path.read_text())
    meta = parse_run_name(path.parent.name)
    term = meta["cost_variable"]
    coef = next(row for row in obj["coefficients"] if row["term"] == term)
    stats = obj["model_stats"]
    return {
        **meta,
        "outcome": obj["outcome"],
        "n_obs": stats.get("nobs"),
        "beta": coef.get("estimate"),
        "se": coef.get("std_error"),
        "t_stat": coef.get("statistic"),
        "p_value": coef.get("p_value"),
        "ci_lower": coef.get("conf_low"),
        "ci_upper": coef.get("conf_high"),
        "r_squared": stats.get("r2"),
        "within_r_squared": stats.get("within_r2"),
    }


def ci_string(row: pd.Series, prefix: str = "") -> str:
    lo = row[f"{prefix}ci_lower"] if prefix else row["ci_lower"]
    hi = row[f"{prefix}ci_upper"] if prefix else row["ci_upper"]
    return f"[{lo:.3f}, {hi:.3f}]"


def fmt_p(x: float) -> str:
    if pd.isna(x):
        return "NA"
    if x < 0.001:
        return "<0.001"
    return f"{x:.3f}"


def diagnostics_table() -> pd.DataFrame:
    df = pd.read_parquet(OUT_DIR / "rho_dataset_event0_pca.parquet")
    outcomes = ["dilma_share_2010_runoff", "pc1_score", "pt_share_mean_runoff"]
    rows = []
    for outcome in outcomes:
        rows.append(
            {
                "outcome": outcome,
                "mean": df[outcome].mean(),
                "sd": df[outcome].std(ddof=0),
                "within_state_sd": (df[outcome] - df.groupby("state")[outcome].transform("mean")).std(ddof=0),
                "corr_with_2010_runoff": df[outcome].corr(df["dilma_share_2010_runoff"]),
                "corr_with_compliance_gap": df[outcome].corr(df["compliance_gap"]),
            }
        )
    return pd.DataFrame(rows)


def make_summary(
    results: pd.DataFrame,
    comparison: pd.DataFrame,
    pca_loadings: pd.DataFrame,
    pca_variance: pd.DataFrame,
    proxy_diag: pd.DataFrame,
) -> str:
    pc1_var = pca_variance.loc[pca_variance["component"].eq("PC1"), "variance_explained"].iloc[0]
    load_text = ", ".join(
        f"{int(row.year)}={row.pc1_loading:.3f}" for row in pca_loadings.itertuples()
    )
    pc1 = results[results["outcome_type"].eq("pc1")].set_index("cost_variable")
    mean = results[results["outcome_type"].eq("mean")].set_index("cost_variable")
    comp = comparison.set_index("cost_variable")
    pc1_corr_2010 = proxy_diag.loc[
        proxy_diag["outcome"].eq("pc1_score"), "corr_with_2010_runoff"
    ].iloc[0]
    mean_corr_2010 = proxy_diag.loc[
        proxy_diag["outcome"].eq("pt_share_mean_runoff"), "corr_with_2010_runoff"
    ].iloc[0]

    def result_sentence(table: pd.DataFrame, cost: str) -> str:
        row = table.loc[cost]
        return (
            f"{COST_LABEL[cost]}: beta={row['beta']:.3f}, "
            f"SE={row['se']:.3f}, 95% CI [{row['ci_lower']:.3f}, {row['ci_upper']:.3f}], "
            f"p={fmt_p(row['p_value'])}"
        )

    def reduction_sentence(cost: str) -> str:
        row = comp.loc[cost]
        return (
            f"{COST_LABEL[cost]}: {row['se_reduction_pct']:.1f}% "
            f"(single-year SE {row['single_year_se']:.3f}, PC1 SE {row['pc1_se']:.3f})"
        )

    gap_comp = comp.loc["compliance_gap"]
    gap_pc1 = pc1.loc["compliance_gap"]
    gap_mean = mean.loc["compliance_gap"]

    lines = [
        "# PCA-Based Rho Estimation Summary",
        "",
        "This phase replaces the single 2010 presidential vote-share proxy with a multi-year left-preference measure built from PT second-round presidential vote shares in 2006, 2010, and 2014. The purpose is to smooth away year-specific noise while preserving the same hybrid event-time-0 sample and the same state-fixed-effect, state-clustered regression design used in the original rho estimation.",
        "",
        "The three years cover Lula's 2006 runoff victory and Dilma's 2010 and 2014 runoff victories, all against PSDB candidates. The 2002 and 2018 elections are excluded because they reflect different coalition and backlash environments. The 2014 vote is contemporaneous with first hybrid status for the 2014 hybrid cohort, so it should be read as a useful but not perfectly pre-treatment component of the preference proxy.",
        "",
        "The signed PC1 score used in the regressions is rescaled to the mean and standard deviation of the simple three-year PT runoff average. This keeps the coefficient and standard-error scale comparable to the original single-year vote-share outcome while preserving the PCA ranking; raw and z-scored PC1 scores are retained in `municipality_pc1_scores.csv`.",
        "",
        "## PCA Construct Validation",
        "",
        f"PC1 explains {pc1_var:.1%} of the standardized three-year runoff-share variance. The loadings are all positive and nearly equal ({load_text}), so the component is a coherent level-of-PT-support construct. The vote-share-scaled PC1 has correlation {pc1_corr_2010:.3f} with the 2010 runoff share and the simple three-year mean has correlation {mean_corr_2010:.3f} with the 2010 runoff share.",
        "",
        "This is stronger coherence than expected: PC1 captures well above 80 percent of the variance. That validates the multi-year preference construct, but it also means the simple mean and PC1 are almost identical empirically.",
        "",
        "## Updated Rho Estimates",
        "",
        "Using PC1 as the political-preference outcome, the event-time-0 regressions give: "
        + "; ".join(result_sentence(pc1, cost) for cost in ORDER)
        + ".",
        "",
        "The gap-based estimate remains positive, but it is smaller and less precise than the 2010-only estimate. The separate low- and high-ed revealed-cost proxies remain close to zero and imprecise, as in the original state-fixed-effect specification.",
        "",
        "## Comparison To Single-Year Baseline",
        "",
        "Relative to the single-year 2010 outcome, the PC1 standard-error changes are: "
        + "; ".join(reduction_sentence(cost) for cost in ORDER)
        + ".",
        "",
        f"For the headline compliance-gap proxy, the point estimate falls from {gap_comp['single_year_beta']:.3f} in the single-year model to {gap_comp['pc1_beta']:.3f} using PC1, and the SE changes from {gap_comp['single_year_se']:.3f} to {gap_comp['pc1_se']:.3f}. Thus the multi-year PCA measure does not tighten the headline gap estimate. The likely reason is not an incoherent preference construct, since PC1 is very stable, but that the 2010-specific relationship between the compliance gap and Dilma support is stronger than the averaged 2006-2014 relationship; after state fixed effects and state-clustered inference, the smoothed outcome does not reduce residual uncertainty for the gap coefficient.",
        "",
        "## Robustness Via Simple Mean",
        "",
        "The simple three-year runoff mean produces nearly the same results as PC1: "
        + "; ".join(result_sentence(mean, cost) for cost in ORDER)
        + ".",
        "",
        f"For the gap proxy, the simple mean gives beta={gap_mean['beta']:.3f} with SE={gap_mean['se']:.3f}, compared with PC1 beta={gap_pc1['beta']:.3f} and SE={gap_pc1['se']:.3f}. Because PC1 and the simple mean are nearly identical and the simple mean is easier to explain, the simple mean is the more interpretable headline multi-year measure.",
        "",
        "## Implications For The Welfare Framework",
        "",
        f"The preferred multi-year descriptive value for the gap-based rho analog is therefore about {gap_mean['beta']:.3f} on the vote-share scale, with a plausible interval spanning roughly {gap_mean['ci_lower']:.3f} to {gap_mean['ci_upper']:.3f}. This keeps the sign positive, consistent with the model-relevant concern that differential compliance costs are politically non-random, but it weakens the precision relative to the borderline 2010-only estimate.",
        "",
        "## Limitations",
        "",
        "The same caveats from the original rho analysis apply: this is a cross-municipality correlation, not the within-individual correlation between compliance cost and ideal policy in the model; hybrid assignment is not random; and voluntary compliance can reflect information, trust, civic engagement, and administrative outreach as well as cost. The inclusion of 2014 may also contaminate the preference proxy for municipalities first exposed to hybrid BVR in 2014, so a narrower 2006-2010 robustness check would be the next natural sensitivity analysis if this measure becomes central to the welfare calibration.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    rows = [read_result(path) for path in sorted(REG_DIR.glob("*/results.json"))]
    results = pd.DataFrame(rows)
    results["outcome_type"] = pd.Categorical(results["outcome_type"], ["pc1", "mean"], ordered=True)
    results["cost_variable"] = pd.Categorical(results["cost_variable"], ORDER, ordered=True)
    results = results.sort_values(["outcome_type", "cost_variable"])

    result_cols = [
        "outcome_type",
        "cost_variable",
        "n_obs",
        "beta",
        "se",
        "t_stat",
        "p_value",
        "ci_lower",
        "ci_upper",
        "r_squared",
        "within_r_squared",
    ]
    results[result_cols].to_csv(OUT_DIR / "regression_results.csv", index=False)

    original = pd.read_csv(ORIGINAL_SUMMARY)
    original = original[original["event_time"].eq(0)].copy()
    original["cost_variable"] = pd.Categorical(original["cost_variable"], ORDER, ordered=True)
    original = original.sort_values("cost_variable")

    pc1 = results[results["outcome_type"].eq("pc1")].set_index("cost_variable")
    mean = results[results["outcome_type"].eq("mean")].set_index("cost_variable")
    rows = []
    for row in original.itertuples():
        cost = str(row.cost_variable)
        pc1_row = pc1.loc[cost]
        mean_row = mean.loc[cost]
        rows.append(
            {
                "cost_variable": cost,
                "single_year_beta": row.beta,
                "single_year_se": row.se,
                "single_year_ci": f"[{row.ci_lower:.3f}, {row.ci_upper:.3f}]",
                "pc1_beta": pc1_row["beta"],
                "pc1_se": pc1_row["se"],
                "pc1_ci": ci_string(pc1_row),
                "mean_beta": mean_row["beta"],
                "mean_se": mean_row["se"],
                "mean_ci": ci_string(mean_row),
                "se_reduction_pct": 100 * (1 - pc1_row["se"] / row.se),
            }
        )
    comparison = pd.DataFrame(rows)
    comparison.to_csv(OUT_DIR / "comparison_to_single_year.csv", index=False)

    proxy_diag = diagnostics_table()
    proxy_diag.to_csv(OUT_DIR / "preference_proxy_diagnostics.csv", index=False)

    pca_loadings = pd.read_csv(OUT_DIR / "pca_loadings.csv")
    pca_variance = pd.read_csv(OUT_DIR / "pca_variance_explained.csv")
    (OUT_DIR / "SUMMARY.md").write_text(
        make_summary(results, comparison, pca_loadings, pca_variance, proxy_diag)
    )

    print(f"Wrote {OUT_DIR / 'regression_results.csv'}")
    print(f"Wrote {OUT_DIR / 'comparison_to_single_year.csv'}")
    print(f"Wrote {OUT_DIR / 'preference_proxy_diagnostics.csv'}")
    print(f"Wrote {OUT_DIR / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
