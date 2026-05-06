from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from src.decomposition.aging_operator import (
    AGE_COHORTS,
    INFLOW_COHORTS,
    SURVIVAL_COHORTS,
    apply_aging_operator,
    validate_aging_matrix,
)


PANEL_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_panel_main.parquet"
SURVIVAL_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_survival_municipality.parquet"
INFLOW_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_inflows.parquet"
OUTPUT_DIR = ROOT / "data" / "clean" / "decomposition"
EXIT_COHORT_PATH = OUTPUT_DIR / "decomposition_exit_cohort.parquet"
EXIT_MUNICIPALITY_PATH = OUTPUT_DIR / "decomposition_exit_municipality.parquet"

ADOPTION_YEARS = {2010, 2012, 2014, 2016, 2018}
CROSS_SECTION_SCENARIO_B_EXIT = 0.1260


def percent(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{100 * float(value):.2f}%"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    for path in [PANEL_PATH, SURVIVAL_PATH, INFLOW_PATH]:
        if not path.exists():
            raise FileNotFoundError(path)

    panel = pd.read_parquet(PANEL_PATH)
    survival = pd.read_parquet(SURVIVAL_PATH)
    inflows = pd.read_parquet(INFLOW_PATH)

    panel = panel.copy()
    panel["ibge_municipality_id"] = panel["ibge_municipality_id"].astype(str).str.zfill(7)
    panel["state"] = panel["state"].astype(str).str.upper().str.strip()
    panel["year"] = pd.to_numeric(panel["year"], errors="raise").astype(int)
    panel["year_first_any_bvr"] = pd.to_numeric(panel["year_first_any_bvr"], errors="raise").astype(int)
    panel["num_voters"] = pd.to_numeric(panel["num_voters"], errors="raise").astype("int64")

    survival = survival.copy()
    survival["ibge_municipality_id"] = survival["ibge_municipality_id"].astype(str).str.zfill(7)
    survival["state"] = survival["state"].astype(str).str.upper().str.strip()
    survival["sigma_used"] = pd.to_numeric(survival["sigma_used"], errors="coerce")

    inflows = inflows.copy()
    inflows["ibge_municipality_id"] = inflows["ibge_municipality_id"].astype(str).str.zfill(7)
    inflows["state"] = inflows["state"].astype(str).str.upper().str.strip()
    inflows["inflow_rate_used"] = pd.to_numeric(inflows["inflow_rate_used"], errors="coerce")
    return panel, survival, inflows


def build_age_count_panel(panel: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        panel.groupby(
            ["ibge_municipality_id", "state", "year", "year_first_any_bvr", "first_regime", "age_cohort"],
            as_index=False,
        )
        .agg(num_voters=("num_voters", "sum"))
    )
    wide = (
        grouped.pivot_table(
            index=["ibge_municipality_id", "state", "year", "year_first_any_bvr", "first_regime"],
            columns="age_cohort",
            values="num_voters",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )
    for cohort in AGE_COHORTS:
        if cohort not in wide.columns:
            wide[cohort] = 0
    wide[AGE_COHORTS] = wide[AGE_COHORTS].astype("float64")
    wide["total_voters"] = wide[AGE_COHORTS].sum(axis=1)
    return wide[
        ["ibge_municipality_id", "state", "year", "year_first_any_bvr", "first_regime", "total_voters"]
        + AGE_COHORTS
    ].copy()


def build_adoption_cycles(age_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    municipality_timing = (
        age_panel[["ibge_municipality_id", "state", "year_first_any_bvr", "first_regime"]]
        .drop_duplicates()
        .copy()
    )
    treated = municipality_timing[municipality_timing["year_first_any_bvr"].isin(ADOPTION_YEARS)].copy()
    treated["t"] = treated["year_first_any_bvr"] - 2
    treated["t_post"] = treated["year_first_any_bvr"]

    t_counts = age_panel.rename(columns={"year": "t", "total_voters": "total_voters_t"}).copy()
    t_counts = t_counts[
        ["ibge_municipality_id", "t", "total_voters_t"] + AGE_COHORTS
    ].rename(columns={cohort: f"{cohort}__t" for cohort in AGE_COHORTS})

    post_counts = age_panel.rename(columns={"year": "t_post", "total_voters": "total_voters_post"}).copy()
    post_counts = post_counts[
        ["ibge_municipality_id", "t_post", "total_voters_post"] + AGE_COHORTS
    ].rename(columns={cohort: f"{cohort}__post" for cohort in AGE_COHORTS})

    cycles = treated.merge(t_counts, how="left", on=["ibge_municipality_id", "t"], validate="one_to_one")
    cycles = cycles.merge(post_counts, how="left", on=["ibge_municipality_id", "t_post"], validate="one_to_one")
    cycles["has_t"] = cycles["total_voters_t"].notna()
    cycles["has_t_post"] = cycles["total_voters_post"].notna()

    missing = cycles[~cycles["has_t"] | ~cycles["has_t_post"]][
        ["ibge_municipality_id", "state", "year_first_any_bvr", "t", "t_post", "has_t", "has_t_post"]
    ].copy()
    cycles = cycles[cycles["has_t"] & cycles["has_t_post"]].copy()
    cycles[["total_voters_t", "total_voters_post"]] = cycles[["total_voters_t", "total_voters_post"]].astype(float)

    source_counts = cycles[[f"{cohort}__t" for cohort in AGE_COHORTS]].copy()
    source_counts.columns = AGE_COHORTS
    aged_forward = apply_aging_operator(source_counts)
    aged_forward = aged_forward.rename(columns={cohort: f"{cohort}__aged" for cohort in AGE_COHORTS})
    cycles = pd.concat([cycles.reset_index(drop=True), aged_forward.reset_index(drop=True)], axis=1)
    return cycles, missing


def make_cohort_predictions(
    cycles: pd.DataFrame,
    survival: pd.DataFrame,
    inflows: pd.DataFrame,
) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    id_columns = [
        "ibge_municipality_id",
        "state",
        "t",
        "t_post",
        "total_voters_t",
        "year_first_any_bvr",
        "first_regime",
    ]
    for cohort in AGE_COHORTS:
        piece = cycles[id_columns].copy()
        piece["age_cohort"] = cohort
        piece["N_observed_t"] = cycles[f"{cohort}__t"].to_numpy(dtype=float)
        piece["N_aged_forward"] = cycles[f"{cohort}__aged"].to_numpy(dtype=float)
        piece["N_observed_t_post"] = cycles[f"{cohort}__post"].to_numpy(dtype=float)
        pieces.append(piece)
    cohort = pd.concat(pieces, ignore_index=True)

    cohort = cohort.merge(
        survival[["ibge_municipality_id", "state", "age_cohort", "sigma_used"]],
        how="left",
        on=["ibge_municipality_id", "state", "age_cohort"],
        validate="many_to_one",
    )
    cohort = cohort.merge(
        inflows[["ibge_municipality_id", "state", "age_cohort", "inflow_rate_used"]],
        how="left",
        on=["ibge_municipality_id", "state", "age_cohort"],
        validate="many_to_one",
    )

    survival_rows = cohort["age_cohort"].isin(SURVIVAL_COHORTS)
    inflow_rows = cohort["age_cohort"].isin(INFLOW_COHORTS)
    missing_sigma = cohort.loc[survival_rows, "sigma_used"].isna().sum()
    missing_inflow = cohort.loc[inflow_rows, "inflow_rate_used"].isna().sum()
    if missing_sigma:
        raise RuntimeError(f"Missing sigma_used for {missing_sigma:,} survival-cohort prediction rows")
    if missing_inflow:
        raise RuntimeError(f"Missing inflow_rate_used for {missing_inflow:,} youngest-cohort prediction rows")

    cohort["inflow_used"] = 0.0
    cohort.loc[inflow_rows, "inflow_used"] = (
        cohort.loc[inflow_rows, "inflow_rate_used"] * cohort.loc[inflow_rows, "total_voters_t"]
    )
    cohort["survived_count"] = 0.0
    cohort.loc[survival_rows, "survived_count"] = (
        cohort.loc[survival_rows, "sigma_used"] * cohort.loc[survival_rows, "N_aged_forward"]
    )
    cohort["N_predicted_no_bvr"] = cohort["survived_count"] + cohort["inflow_used"]
    cohort["raw_gap"] = cohort["N_predicted_no_bvr"] - cohort["N_observed_t_post"]
    cohort["exit_count"] = cohort["raw_gap"].clip(lower=0)
    cohort["exit_rate"] = 0.0
    positive_prediction = cohort["N_predicted_no_bvr"].gt(0)
    cohort.loc[positive_prediction, "exit_rate"] = (
        cohort.loc[positive_prediction, "exit_count"] / cohort.loc[positive_prediction, "N_predicted_no_bvr"]
    )

    bad_prediction = cohort["N_predicted_no_bvr"].lt(-1e-9).sum()
    bad_exit_rate = (cohort["exit_rate"].lt(-1e-9) | cohort["exit_rate"].gt(1 + 1e-9)).sum()
    if bad_prediction or bad_exit_rate:
        raise RuntimeError(
            f"Invalid prediction output: negative predictions={bad_prediction:,}, invalid exit rates={bad_exit_rate:,}"
        )

    output = cohort[
        [
            "ibge_municipality_id",
            "state",
            "t",
            "t_post",
            "age_cohort",
            "N_observed_t",
            "N_aged_forward",
            "N_predicted_no_bvr",
            "N_observed_t_post",
            "exit_count",
            "exit_rate",
            "year_first_any_bvr",
            "first_regime",
            "sigma_used",
            "inflow_used",
        ]
    ].copy()
    return output.sort_values(["ibge_municipality_id", "t_post", "age_cohort"]).reset_index(drop=True)


def json_cohort_breakdown(frame: pd.DataFrame) -> str:
    values = frame.set_index("age_cohort")["exit_count"].reindex(AGE_COHORTS).fillna(0.0)
    return json.dumps({cohort: float(values.loc[cohort]) for cohort in AGE_COHORTS}, ensure_ascii=False)


def aggregate_municipality_exit(cohort_exit: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        cohort_exit.groupby(
            ["ibge_municipality_id", "state", "t", "t_post", "year_first_any_bvr", "first_regime"],
            as_index=False,
        )
        .agg(
            total_predicted=("N_predicted_no_bvr", "sum"),
            total_observed=("N_observed_t_post", "sum"),
            exit_count_total=("exit_count", "sum"),
            n_cohorts_with_exit=("exit_count", lambda s: int(s.gt(0).sum())),
        )
    )
    grouped["exit_rate_total"] = 0.0
    positive_prediction = grouped["total_predicted"].gt(0)
    grouped.loc[positive_prediction, "exit_rate_total"] = (
        grouped.loc[positive_prediction, "exit_count_total"] / grouped.loc[positive_prediction, "total_predicted"]
    )
    breakdown = (
        cohort_exit.groupby(["ibge_municipality_id", "t_post"], as_index=False)
        .apply(json_cohort_breakdown, include_groups=False)
        .rename(columns={None: "exit_count_by_cohort"})
    )
    output = grouped.merge(breakdown, how="left", on=["ibge_municipality_id", "t_post"], validate="one_to_one")
    return output[
        [
            "ibge_municipality_id",
            "state",
            "t",
            "t_post",
            "year_first_any_bvr",
            "first_regime",
            "total_predicted",
            "total_observed",
            "exit_count_total",
            "exit_rate_total",
            "exit_count_by_cohort",
            "n_cohorts_with_exit",
        ]
    ].sort_values(["t_post", "state", "ibge_municipality_id"]).reset_index(drop=True)


def cohort_year_counts(municipality_exit: pd.DataFrame) -> pd.DataFrame:
    return (
        municipality_exit.groupby("t_post", as_index=False)
        .agg(municipalities=("ibge_municipality_id", "nunique"))
        .sort_values("t_post")
    )


def sampled_municipality_diagnostics(
    cohort_exit: pd.DataFrame,
    municipality_exit: pd.DataFrame,
    n: int = 50,
) -> pd.DataFrame:
    total_t = (
        cohort_exit.groupby(["ibge_municipality_id", "t_post"], as_index=False)
        .agg(total_t=("N_observed_t", "sum"))
    )
    diag = municipality_exit.merge(total_t, how="left", on=["ibge_municipality_id", "t_post"])
    diag["raw_predicted_minus_observed"] = diag["total_predicted"] - diag["total_observed"]
    diag["predicted_vs_t_pct"] = diag["total_predicted"] / diag["total_t"] - 1
    sample_n = min(n, len(diag))
    return diag.sample(n=sample_n, random_state=20260430).sort_values(
        ["t_post", "state", "ibge_municipality_id"]
    )


def regime_summary(municipality_exit: pd.DataFrame) -> pd.DataFrame:
    return (
        municipality_exit.groupby("first_regime", as_index=False)
        .agg(
            municipalities=("ibge_municipality_id", "nunique"),
            mean_exit_rate=("exit_rate_total", "mean"),
            median_exit_rate=("exit_rate_total", "median"),
            total_exit=("exit_count_total", "sum"),
            total_predicted=("total_predicted", "sum"),
        )
        .assign(weighted_exit_rate=lambda x: x["total_exit"] / x["total_predicted"])
        .sort_values("first_regime")
    )


def cohort_regime_summary(cohort_exit: pd.DataFrame) -> pd.DataFrame:
    working = cohort_exit.assign(
        observed_exceeds_predicted=cohort_exit["N_observed_t_post"].gt(cohort_exit["N_predicted_no_bvr"])
    )
    return (
        working.groupby(["first_regime", "age_cohort"], as_index=False)
        .agg(
            mean_exit_rate=("exit_rate", "mean"),
            median_exit_rate=("exit_rate", "median"),
            total_exit=("exit_count", "sum"),
            total_predicted=("N_predicted_no_bvr", "sum"),
            rows=("exit_rate", "size"),
            max_operator_zeroed=("observed_exceeds_predicted", "sum"),
        )
        .assign(weighted_exit_rate=lambda x: x["total_exit"] / x["total_predicted"].replace(0, np.nan))
    )


def cohort_year_comparison(municipality_exit: pd.DataFrame) -> pd.DataFrame:
    comparison = (
        municipality_exit.groupby("year_first_any_bvr", as_index=False)
        .agg(
            municipalities=("ibge_municipality_id", "nunique"),
            mean_exit_rate=("exit_rate_total", "mean"),
            median_exit_rate=("exit_rate_total", "median"),
            weighted_exit_rate=("exit_count_total", "sum"),
            total_predicted=("total_predicted", "sum"),
        )
        .sort_values("year_first_any_bvr")
    )
    comparison["weighted_exit_rate"] = comparison["weighted_exit_rate"] / comparison["total_predicted"]
    comparison["relative_to_cross_section"] = comparison["mean_exit_rate"] - CROSS_SECTION_SCENARIO_B_EXIT
    comparison["magnitude_flag"] = np.select(
        [
            comparison["mean_exit_rate"].lt(0.02),
            comparison["mean_exit_rate"].gt(0.20),
        ],
        ["below few-percent range", "above roughly-20-percent range"],
        default="same broad order",
    )
    return comparison


def print_table(title: str, frame: pd.DataFrame, max_rows: int | None = None) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if frame.empty:
        print("(none)")
        return
    if max_rows is not None and len(frame) > max_rows:
        print(frame.head(max_rows).to_string(index=False))
        print(f"... ({len(frame) - max_rows:,} additional rows)")
    else:
        print(frame.to_string(index=False))


def format_rate_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    output = frame.copy()
    for column in columns:
        if column in output.columns:
            output[column] = output[column].map(percent)
    return output


def main() -> None:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)
    validate_aging_matrix()

    panel, survival, inflows = load_inputs()
    age_panel = build_age_count_panel(panel)
    adoption_cycles, missing_cycles = build_adoption_cycles(age_panel)
    cohort_exit = make_cohort_predictions(adoption_cycles, survival, inflows)
    municipality_exit = aggregate_municipality_exit(cohort_exit)

    bad_exit_rates = (municipality_exit["exit_rate_total"].lt(-1e-9) | municipality_exit["exit_rate_total"].gt(1 + 1e-9)).sum()
    if bad_exit_rates:
        raise RuntimeError(f"Invalid municipality exit rates: {bad_exit_rates:,}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cohort_exit.to_parquet(EXIT_COHORT_PATH, index=False)
    municipality_exit.to_parquet(EXIT_MUNICIPALITY_PATH, index=False)

    cycle_counts = cohort_year_counts(municipality_exit)
    regime = regime_summary(municipality_exit)
    by_cohort = cohort_regime_summary(cohort_exit)
    strict_by_cohort = by_cohort[by_cohort["first_regime"].eq("strict")].copy()
    comparison = cohort_year_comparison(municipality_exit)
    sample = sampled_municipality_diagnostics(cohort_exit, municipality_exit)

    observed_exceeds_predicted = cohort_exit["N_predicted_no_bvr"].lt(cohort_exit["N_observed_t_post"])
    raw_negative = observed_exceeds_predicted.sum()
    raw_negative_by_cohort = (
        cohort_exit.assign(max_operator_zeroed=observed_exceeds_predicted)
        .groupby("age_cohort", as_index=False)
        .agg(rows=("age_cohort", "size"), max_operator_zeroed=("max_operator_zeroed", "sum"))
    )
    raw_negative_by_cohort["share_zeroed"] = raw_negative_by_cohort["max_operator_zeroed"] / raw_negative_by_cohort["rows"]

    total_t = (
        cohort_exit.groupby(["ibge_municipality_id", "t_post"], as_index=False)
        .agg(total_t=("N_observed_t", "sum"))
    )
    pred_vs_t = municipality_exit.merge(total_t, how="left", on=["ibge_municipality_id", "t_post"])
    pred_vs_t["abs_predicted_vs_t_pct"] = (pred_vs_t["total_predicted"] / pred_vs_t["total_t"] - 1).abs()
    predicted_far_from_t = pred_vs_t[pred_vs_t["abs_predicted_vs_t_pct"].gt(0.20)]

    anomalies: list[str] = []
    if len(missing_cycles):
        anomalies.append(f"{len(missing_cycles):,} treated municipalities missing the adoption-cycle t or t_post row")
    if len(predicted_far_from_t):
        anomalies.append(f"{len(predicted_far_from_t):,} municipality predictions differ from t total by more than 20%")
    strict_mean = regime.loc[regime["first_regime"].eq("strict"), "mean_exit_rate"]
    hybrid_mean = regime.loc[regime["first_regime"].eq("hybrid"), "mean_exit_rate"]
    if not strict_mean.empty and not hybrid_mean.empty and strict_mean.iloc[0] <= hybrid_mean.iloc[0]:
        anomalies.append("strict-first mean exit rate is not larger than hybrid-first mean exit rate")
    outside_order = comparison[~comparison["magnitude_flag"].eq("same broad order")]
    if len(outside_order):
        anomalies.append(f"{len(outside_order):,} treatment cohorts outside the qualitative 2%-20% range")

    print("=" * 64)
    print("COHORT-LEVEL EXIT ESTIMATION SUMMARY")
    print("=" * 64)
    print(f"Treated municipalities processed: {municipality_exit['ibge_municipality_id'].nunique():,}")
    if len(missing_cycles):
        print(f"Treated municipalities skipped for missing adoption-cycle data: {len(missing_cycles):,}")

    print("\nAdoption-cycle predictions by cohort year:")
    for _, row in cycle_counts.iterrows():
        print(f"  {int(row['t_post'])}: {int(row['municipalities']):,} municipalities")

    regime_display = format_rate_columns(regime, ["mean_exit_rate", "median_exit_rate", "weighted_exit_rate"])
    print_table("Average exit rate at adoption by first_regime", regime_display)

    strict_display = strict_by_cohort[["age_cohort", "mean_exit_rate", "weighted_exit_rate", "rows", "max_operator_zeroed"]].copy()
    strict_display = format_rate_columns(strict_display, ["mean_exit_rate", "weighted_exit_rate"])
    print_table("Average exit rate by age cohort, strict-first municipalities", strict_display)

    comparison_display = comparison.copy()
    comparison_display = format_rate_columns(
        comparison_display,
        ["mean_exit_rate", "median_exit_rate", "weighted_exit_rate", "relative_to_cross_section"],
    )
    print_table("Comparison to cross-section Scenario B exit estimate (12.60%)", comparison_display)

    sample_display = sample[
        [
            "ibge_municipality_id",
            "state",
            "t",
            "t_post",
            "first_regime",
            "total_t",
            "total_predicted",
            "total_observed",
            "raw_predicted_minus_observed",
            "exit_count_total",
            "exit_rate_total",
            "predicted_vs_t_pct",
        ]
    ].copy()
    sample_display = format_rate_columns(sample_display, ["exit_rate_total", "predicted_vs_t_pct"])
    print_table("Sample of 50 treated municipalities", sample_display)

    zeroed_display = raw_negative_by_cohort.copy()
    zeroed_display["share_zeroed"] = zeroed_display["share_zeroed"].map(percent)
    print_table("Max-operator zeroing by cohort (observed > predicted)", zeroed_display)
    print(f"\nCohort rows where observed exceeded predicted and exit was set to zero: {raw_negative:,}")

    overall_average = municipality_exit["exit_rate_total"].mean()
    direction = "below" if overall_average < CROSS_SECTION_SCENARIO_B_EXIT else "above"
    magnitude = "same broad order" if 0.02 <= overall_average <= 0.20 else "outside broad order"
    print(
        "\nComparison to cross-section national bound (Scenario B exit estimate of 12.60% of 2006 baseline):"
    )
    print(f"  Municipality-level average: {percent(overall_average)} of t-period predicted electorate")
    print(f"  Direction: {direction} the cross-section Scenario B estimate")
    print(f"  Magnitude: {magnitude}")

    print(f"\nAnomalies flagged: {len(anomalies)}")
    for anomaly in anomalies:
        print(f"  - {anomaly}")

    print("\nFiles saved:")
    print(f"  {EXIT_COHORT_PATH.relative_to(ROOT)}")
    print(f"  {EXIT_MUNICIPALITY_PATH.relative_to(ROOT)}")
    print("\nReady for re-labeling identification in Prompt 4.")


if __name__ == "__main__":
    main()
