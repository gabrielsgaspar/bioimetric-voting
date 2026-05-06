#!/usr/bin/env python3
"""Compile multi-race PCA rho estimation outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path("resources/regressions/reg_fe_compare")
OUT_DIR = ROOT / "rho_estimation_pca_multirace"
REG_DIR = OUT_DIR / "regressions"
SINGLE_YEAR = ROOT / "rho_estimation" / "rho_regression_summary.csv"
PCA_3YEAR = ROOT / "rho_estimation_pca" / "comparison_to_single_year.csv"

COST_VARIABLE = {
    "rho_L": "cost_proxy_low_ed",
    "rho_H": "cost_proxy_high_ed",
    "rho_gap": "compliance_gap",
}
ORDER = ["cost_proxy_low_ed", "cost_proxy_high_ed", "compliance_gap"]
LABEL = {
    "cost_proxy_low_ed": "Low-ed revealed cost",
    "cost_proxy_high_ed": "High-ed revealed cost",
    "compliance_gap": "High-low compliance gap",
}


def parse_name(name: str) -> dict[str, str]:
    parts = name.split("_")
    measure = "_".join(parts[:2])
    outcome_type = "pc1" if parts[-1] == "pca" else "mean"
    return {
        "run_name": name,
        "rho_measure": measure,
        "outcome_type": outcome_type,
        "cost_variable": COST_VARIABLE[measure],
    }


def read_result(path: Path) -> dict[str, object]:
    obj = json.loads(path.read_text())
    meta = parse_name(path.parent.name)
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


def fmt(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}"


def fmt_p(x: float) -> str:
    if pd.isna(x):
        return "NA"
    if x < 0.001:
        return "<0.001"
    return f"{x:.3f}"


def ci(row: pd.Series, prefix: str = "") -> str:
    lo = row[f"{prefix}ci_lower"] if prefix else row["ci_lower"]
    hi = row[f"{prefix}ci_upper"] if prefix else row["ci_upper"]
    return f"[{fmt(lo)}, {fmt(hi)}]"


def compile_results() -> pd.DataFrame:
    rows = [read_result(path) for path in sorted(REG_DIR.glob("*/results.json"))]
    df = pd.DataFrame(rows)
    df["outcome_type"] = pd.Categorical(df["outcome_type"], ["pc1", "mean"], ordered=True)
    df["cost_variable"] = pd.Categorical(df["cost_variable"], ORDER, ordered=True)
    df = df.sort_values(["outcome_type", "cost_variable"])
    cols = [
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
    df[cols].to_csv(OUT_DIR / "regression_results.csv", index=False)
    return df


def compile_comparison(results: pd.DataFrame) -> pd.DataFrame:
    single = pd.read_csv(SINGLE_YEAR)
    single = single[single["event_time"].eq(0)].set_index("cost_variable")
    pca3 = pd.read_csv(PCA_3YEAR).set_index("cost_variable")
    multi_pc1 = results[results["outcome_type"].eq("pc1")].set_index("cost_variable")
    multi_mean = results[results["outcome_type"].eq("mean")].set_index("cost_variable")
    rows = []
    for cost in ORDER:
        rows.append(
            {
                "cost_variable": cost,
                "single_year_beta": single.loc[cost, "beta"],
                "single_year_se": single.loc[cost, "se"],
                "pca_3year_beta": pca3.loc[cost, "pc1_beta"],
                "pca_3year_se": pca3.loc[cost, "pc1_se"],
                "pca_multirace_beta": multi_pc1.loc[cost, "beta"],
                "pca_multirace_se": multi_pc1.loc[cost, "se"],
                "mean_multirace_beta": multi_mean.loc[cost, "beta"],
                "mean_multirace_se": multi_mean.loc[cost, "se"],
                "se_reduction_pca_3year_vs_single": 100
                * (1 - pca3.loc[cost, "pc1_se"] / single.loc[cost, "se"]),
                "se_reduction_multirace_vs_3year": 100
                * (1 - multi_pc1.loc[cost, "se"] / pca3.loc[cost, "pc1_se"]),
                "se_reduction_multirace_vs_single": 100
                * (1 - multi_pc1.loc[cost, "se"] / single.loc[cost, "se"]),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "comparison_to_baselines.csv", index=False)
    return out


def make_summary(results: pd.DataFrame, comparison: pd.DataFrame) -> str:
    loadings = pd.read_csv(OUT_DIR / "pca_loadings.csv")
    variance = pd.read_csv(OUT_DIR / "pca_variance_explained.csv")
    election_summary = (OUT_DIR / "election_data_summary.md").read_text()
    pc1 = results[results["outcome_type"].eq("pc1")].set_index("cost_variable")
    mean = results[results["outcome_type"].eq("mean")].set_index("cost_variable")
    comp = comparison.set_index("cost_variable")
    pc1_var = variance.loc[variance["component"].eq("PC1"), "variance_explained"].iloc[0]
    pc2_var = variance.loc[variance["component"].eq("PC2"), "variance_explained"].iloc[0]
    gap = pc1.loc["compliance_gap"]
    gap_mean = mean.loc["compliance_gap"]
    gap_comp = comp.loc["compliance_gap"]
    load_text = "; ".join(
        f"{row.variable}={row.pc1_loading:.3f}" for row in loadings.itertuples()
    )
    race_load = (
        loadings.assign(abs_loading=lambda d: d["pc1_loading"].abs())
        .groupby("race")["abs_loading"]
        .mean()
        .to_dict()
    )

    def result_sentence(table: pd.DataFrame, cost: str) -> str:
        row = table.loc[cost]
        return (
            f"{LABEL[cost]}: beta={fmt(row['beta'])}, SE={fmt(row['se'])}, "
            f"95% CI {ci(row)}, p={fmt_p(row['p_value'])}"
        )

    lines = [
        "# Multi-Race PCA Rho Estimation Summary",
        "",
        "This phase builds a broader left-preference proxy from three electoral races in 2006, 2010, and 2014: PT presidential runoff vote share, federal deputy left-coalition candidate vote share, and state deputy left-coalition candidate vote share. The left coalition is coded as PT, PSB, PCdoB, PDT, PSOL, PV, and REDE. The goal is to move from a PT-presidential construct toward a more general local-left-preference construct.",
        "",
        "The tradeoff is visible in the data. Presidential races are highly persistent across municipalities, but deputy races add local-candidate and party-list noise. Because the deputy variables are candidate-vote shares from `resultados_candidato_municipio`, the measure does not include separate party-list votes.",
        "",
        "The multirace PC1 and simple mean are in standardized-index units, not presidential vote-share units. The comparison to the 2010 and PT-only PCA baselines is therefore informative about sign and precision, but the coefficient levels are not perfectly scale-equivalent across preference proxies.",
        "",
        "## PCA Construct Validation",
        "",
        f"PC1 explains only {pc1_var:.1%} of the 9-variable standardized variance, while PC2 explains {pc2_var:.1%}. This is below the 50 percent warning threshold in the prompt, so the multirace PCA should not be treated as a clean one-dimensional replacement for the PT-only presidential PCA.",
        "",
        f"All nine PC1 loadings have the same positive sign, so the first component is at least directionally coherent. The loadings are reasonably balanced by race: president mean absolute loading {race_load.get('president', float('nan')):.3f}, federal deputy {race_load.get('dep_fed', float('nan')):.3f}, and state deputy {race_load.get('dep_est', float('nan')):.3f}. The individual loadings are {load_text}.",
        "",
        "Deputy vote-share sanity checks show no values outside [0,1]. Weighted left-coalition shares are roughly 29-36 percent across office-years, while unweighted municipality means are lower, around 25-31 percent. These are somewhat below the rough expectation in the prompt but not wildly implausible given the candidate-result table and the narrow party list.",
        "",
        "## Updated Rho Estimates",
        "",
        "Using the multirace PC1 as the outcome, the event-time-0 regressions give: "
        + "; ".join(result_sentence(pc1, cost) for cost in ORDER)
        + ".",
        "",
        "The headline gap estimate remains positive but becomes very imprecise. The separate low- and high-ed revealed-cost proxies are also positive, unlike the PT-only specifications, but neither is distinguishable from zero.",
        "",
        "## Comparison To Baselines",
        "",
        f"For the compliance-gap proxy, the 2010 single-year estimate was beta={gap_comp['single_year_beta']:.3f} with SE={gap_comp['single_year_se']:.3f}; the PT-only 3-year PCA estimate was beta={gap_comp['pca_3year_beta']:.3f} with SE={gap_comp['pca_3year_se']:.3f}; and the multirace PCA estimate is beta={gap_comp['pca_multirace_beta']:.3f} with SE={gap_comp['pca_multirace_se']:.3f}. The multirace SE is {abs(gap_comp['se_reduction_multirace_vs_3year']):.1f}% larger than the PT-only PCA SE, so the broader measure does not tighten inference.",
        "",
        "This result is consistent with the PCA diagnostics: deputy races broaden the construct but introduce enough independent local noise that the first component is a weak summary of the full matrix.",
        "",
        "## Robustness Via Simple Mean",
        "",
        "Using the unweighted standardized simple mean of all nine variables gives: "
        + "; ".join(result_sentence(mean, cost) for cost in ORDER)
        + ".",
        "",
        f"For the gap proxy, the simple mean gives beta={gap_mean['beta']:.3f} with SE={gap_mean['se']:.3f}, compared with PC1 beta={gap['beta']:.3f} and SE={gap['se']:.3f}. The simple mean and PC1 agree on the positive sign, but both are too imprecise to improve on the PT-only benchmarks.",
        "",
        "## Implications For The Welfare Framework",
        "",
        "The multirace exercise supports the qualitative sign of rho_gap but weakens the case for using it as the headline calibration. Across the main specifications, the gap estimate is positive: about 0.215 in the 2010 single-year model, 0.174 in the PT-only 3-year PCA, and 0.241 in the multirace PC1 index. The plausible range remains wide because the multirace confidence interval is large and includes zero by a wide margin.",
        "",
        "The most defensible calibration remains the PT-only set of estimates, with the multirace result as a robustness check showing that the positive sign is not unique to presidential PT support. It should not replace the PT-only measure because PC1 captures only 35.9 percent of the multirace variance.",
        "",
        "## Limitations",
        "",
        "Deputy elections add local-candidate effects, coalition heterogeneity, and candidate-entry noise. The party coding is consequential, especially for PV and REDE, and the candidate-result table omits separate party-list votes. The broader construct is conceptually closer to general left preference, but empirically less one-dimensional and less precise than the presidential PT measures.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    results = compile_results()
    comparison = compile_comparison(results)
    (OUT_DIR / "SUMMARY.md").write_text(make_summary(results, comparison))
    print(f"Wrote {OUT_DIR / 'regression_results.csv'}")
    print(f"Wrote {OUT_DIR / 'comparison_to_baselines.csv'}")
    print(f"Wrote {OUT_DIR / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
