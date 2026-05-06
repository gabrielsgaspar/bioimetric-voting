#!/usr/bin/env python3
"""Compile rho-estimation outputs from reg-fe JSON files."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path("resources/regressions/reg_fe_compare/rho_estimation")
REG_DIR = ROOT / "regressions"

MEASURE_LABEL = {
    "rho_L": "rho_L",
    "rho_H": "rho_H",
    "rho_gap": "rho_gap",
}

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

OUTCOME_LABEL = {
    "dilma_share_2010_runoff": "Dilma runoff share",
    "dilma_share_2010_first_round": "Dilma first-round share",
    "left_coalition_share_2010_first_round": "Left-coalition first-round share",
}


def parse_run_name(name: str) -> dict[str, object]:
    parts = name.split("_")
    measure = "_".join(parts[:2])
    if measure == "rho_gap":
        event_part = parts[2]
        suffix_parts = parts[3:]
    else:
        event_part = parts[2]
        suffix_parts = parts[3:]

    event_time = int(event_part.replace("event", ""))
    suffix = "_".join(suffix_parts) if suffix_parts else "main"

    specification = "main"
    sample_restriction = "all hybrid-status observations"
    fe = "state"

    if suffix == "first_round":
        specification = "alternative outcome: first-round Dilma"
    elif suffix == "left_coalition":
        specification = "alternative outcome: first-round left coalition"
    elif suffix == "region_fe":
        specification = "region fixed effects"
        fe = "region"
    elif suffix == "active_only":
        specification = "active-only hybrid sample"
        sample_restriction = "pct_with_bvr >= 0.05"
    elif suffix != "main":
        specification = suffix

    return {
        "run_name": name,
        "rho_measure": MEASURE_LABEL[measure],
        "event_time": event_time,
        "cost_variable": COST_VARIABLE[measure],
        "specification": specification,
        "sample_restriction": sample_restriction,
        "fe": fe,
    }


def read_result(path: Path) -> dict[str, object]:
    obj = json.loads(path.read_text())
    meta = parse_run_name(path.parent.name)
    term = meta["cost_variable"]
    coef = next(row for row in obj["coefficients"] if row["term"] == term)
    stats = obj["model_stats"]
    return {
        **meta,
        "political_outcome": obj["outcome"],
        "n_obs": stats.get("nobs"),
        "beta": coef.get("estimate"),
        "se": coef.get("std_error"),
        "t_stat": coef.get("statistic"),
        "p_value": coef.get("p_value"),
        "ci_lower": coef.get("conf_low"),
        "ci_upper": coef.get("conf_high"),
        "r_squared": stats.get("r2"),
        "within_r_squared": stats.get("within_r2"),
        "formula": obj.get("formula"),
        "cluster": obj.get("cluster"),
    }


def fmt_num(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}"


def fmt_p(x: float) -> str:
    if pd.isna(x):
        return "NA"
    if x < 0.001:
        return "<0.001"
    return f"{x:.3f}"


def fmt_ci(row: pd.Series) -> str:
    return f"[{fmt_num(row['ci_lower'])}, {fmt_num(row['ci_upper'])}]"


def make_summary(raw: pd.DataFrame, main: pd.DataFrame, robust: pd.DataFrame) -> str:
    raw0 = raw[
        (raw["event_time"] == 0)
        & (raw["preference_variable"] == "dilma_share_2010_runoff")
    ].set_index("cost_variable")
    raw2 = raw[
        (raw["event_time"] == 2)
        & (raw["preference_variable"] == "dilma_share_2010_runoff")
    ].set_index("cost_variable")
    main0 = main[
        (main["event_time"] == 0)
        & (main["political_outcome"] == "dilma_share_2010_runoff")
    ].set_index("cost_variable")
    main2 = main[
        (main["event_time"] == 2)
        & (main["political_outcome"] == "dilma_share_2010_runoff")
    ].set_index("cost_variable")

    def raw_sentence(cost: str) -> str:
        row = raw0.loc[cost]
        return (
            f"{COST_LABEL[cost]}: r={fmt_num(row['correlation'])}, "
            f"n={int(row['n_obs'])}, p={fmt_p(row['p_value'])}"
        )

    def main_sentence(cost: str) -> str:
        row = main0.loc[cost]
        return (
            f"{COST_LABEL[cost]}: beta={fmt_num(row['beta'])}, "
            f"SE={fmt_num(row['se'])}, 95% CI {fmt_ci(row)}, "
            f"p={fmt_p(row['p_value'])}"
        )

    first_round = robust[robust["specification"].eq("alternative outcome: first-round Dilma")]
    left_coalition = robust[robust["specification"].eq("alternative outcome: first-round left coalition")]
    region_fe = robust[robust["specification"].eq("region fixed effects")]
    active = robust[robust["specification"].eq("active-only hybrid sample")]

    gap_main = main0.loc["compliance_gap"]
    gap_event2 = main2.loc["compliance_gap"]
    gap_first = first_round[first_round["cost_variable"].eq("compliance_gap")].iloc[0]
    gap_left = left_coalition[left_coalition["cost_variable"].eq("compliance_gap")].iloc[0]
    gap_region = region_fe[region_fe["cost_variable"].eq("compliance_gap")].iloc[0]
    gap_active = active[active["cost_variable"].eq("compliance_gap")].iloc[0]

    lines = [
        "# Rho Estimation Summary",
        "",
        "This phase estimates the cross-municipality empirical analog of the model's cost-preference correlation. The analytical sample is hybrid-status municipality-years, where voluntary biometric compliance can be interpreted as revealed compliance friction rather than mechanical saturation after cancellation. The main political-preference proxy is Dilma Rousseff's 2010 second-round presidential vote share, which predates hybrid BVR exposure.",
        "",
        "The maintained interpretation is that lower voluntary compliance within an education group reflects higher average compliance cost for that group, while pre-BVR presidential vote shares proxy for local political preferences. These estimates are descriptive correlations, not causal effects, and they are intended to calibrate the sign and approximate magnitude of the welfare-framework parameter rather than identify a treatment effect.",
        "",
        "The event-time-0 dataset has 1,845 matched hybrid municipalities. The event-time-2 dataset has 528 matched hybrid municipalities; the `reg-fe` event-time-2 models drop one singleton fixed-effect observation, leaving 527 observations in the regression outputs.",
        "",
        "## Raw Correlations",
        "",
        "At event time 0 using Dilma's runoff share, the raw correlations are: "
        + "; ".join(
            [
                raw_sentence("cost_proxy_low_ed"),
                raw_sentence("cost_proxy_high_ed"),
                raw_sentence("compliance_gap"),
            ]
        )
        + ".",
        "",
        "At event time 2, the same correlations are "
        + "; ".join(
            [
                (
                    f"{COST_LABEL[cost]}: r={fmt_num(raw2.loc[cost, 'correlation'])}, "
                    f"n={int(raw2.loc[cost, 'n_obs'])}, p={fmt_p(raw2.loc[cost, 'p_value'])}"
                )
                for cost in ["cost_proxy_low_ed", "cost_proxy_high_ed", "compliance_gap"]
            ]
        )
        + ". The gap measure is the most stable raw signal: municipalities where high-ed compliance exceeds low-ed compliance by more also lean more toward Dilma in the pre-BVR runoff.",
        "",
        "## Regression-Based Estimates",
        "",
        "The main regressions include state fixed effects, controls for log 2010 population and log 2010 GDP per capita, and state-clustered standard errors. At event time 0, the estimates are: "
        + "; ".join(
            [
                main_sentence("cost_proxy_low_ed"),
                main_sentence("cost_proxy_high_ed"),
                main_sentence("compliance_gap"),
            ]
        )
        + ".",
        "",
        "After adding state fixed effects and controls, the separate low- and high-ed revealed-cost proxies are close to zero, slightly negative, and imprecise. The compliance-gap coefficient remains positive and is near the conventional 5 percent threshold, which matches the raw-correlation evidence that differential compliance costs are larger in more left-leaning hybrid municipalities.",
        "",
        "## Robustness",
        "",
        f"The event-time-2 gap coefficient remains positive, beta={fmt_num(gap_event2['beta'])} with SE={fmt_num(gap_event2['se'])}, though the confidence interval is wide. For event-time-0 alternative political outcomes, the gap coefficient is beta={fmt_num(gap_first['beta'])} for Dilma first-round share and beta={fmt_num(gap_left['beta'])} for the broader left-coalition first-round share. With region rather than state fixed effects, the gap coefficient is beta={fmt_num(gap_region['beta'])}. In the active-only hybrid sample, the gap coefficient is beta={fmt_num(gap_active['beta'])}. These checks preserve the positive sign for the gap-based measure, although precision varies across specifications.",
        "",
        "## Implication For The Welfare Framework",
        "",
        f"The best single empirical analog for rho_bar is the event-time-0 compliance-gap result, because it uses the within-municipality high-low compliance differential in the voluntary hybrid regime. On the raw correlation scale, this value is {fmt_num(raw0.loc['compliance_gap', 'correlation'])}; on the regression slope scale with state fixed effects and controls, it is {fmt_num(gap_main['beta'])}, with 95% CI {fmt_ci(gap_main)}. The sign is positive: in Brazil, hybrid municipalities with larger revealed education-based compliance gaps are also more left-leaning before BVR. In Corollary 1's threshold inequality, this pushes the welfare assessment toward greater concern about BVR when excluded or high-cost citizens are politically non-random rather than ideologically neutral.",
        "",
        "## Limitations",
        "",
        "The cross-municipality correlation is not the within-individual correlation between compliance cost and ideal policy that the model defines. Hybrid assignment is not random, voluntary compliance can reflect information, trust, civic engagement, administrative capacity, and outreach rather than only cost, and the 2010 presidential vote share is an aggregate political-preference proxy. The state-fixed-effect specification is therefore best read as a disciplined descriptive calibration of the sign and scale of rho_bar, not as a causal estimate.",
        "",
        "## Output Files",
        "",
        "The raw presidential data are saved under `data/raw/tse_2010_president/`, and cleaned municipality-level presidential files are saved under `data/clean/tse/`. The rho datasets, configs, regression outputs, raw correlations, main regression summary, and robustness summary are all saved in `resources/regressions/reg_fe_compare/rho_estimation/`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    rows = [read_result(path) for path in sorted(REG_DIR.glob("*/results.json"))]
    df = pd.DataFrame(rows)

    main_mask = (
        df["specification"].eq("main")
        & df["political_outcome"].eq("dilma_share_2010_runoff")
        & df["fe"].eq("state")
    )
    main = df[main_mask].sort_values(["event_time", "rho_measure"]).copy()
    robust = df[~main_mask].sort_values(
        ["specification", "event_time", "rho_measure"]
    ).copy()

    main_cols = [
        "event_time",
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
    main[main_cols].to_csv(ROOT / "rho_regression_summary.csv", index=False)

    robust_cols = [
        "specification",
        "event_time",
        "cost_variable",
        "political_outcome",
        "sample_restriction",
        "fe",
        "n_obs",
        "beta",
        "se",
        "ci_lower",
        "ci_upper",
        "p_value",
        "r_squared",
        "within_r_squared",
    ]
    robust[robust_cols].to_csv(ROOT / "robustness_summary.csv", index=False)

    df.sort_values(["event_time", "specification", "rho_measure"]).to_csv(
        ROOT / "all_regression_results.csv", index=False
    )

    raw = pd.read_csv(ROOT / "raw_correlations.csv")
    (ROOT / "SUMMARY.md").write_text(make_summary(raw, main, robust))

    print(f"Wrote {ROOT / 'rho_regression_summary.csv'}")
    print(f"Wrote {ROOT / 'robustness_summary.csv'}")
    print(f"Wrote {ROOT / 'all_regression_results.csv'}")
    print(f"Wrote {ROOT / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
