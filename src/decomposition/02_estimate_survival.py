from __future__ import annotations

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
    per_cycle_threshold,
    validate_aging_matrix,
)


PANEL_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_panel_main.parquet"
OUTPUT_DIR = ROOT / "data" / "clean" / "decomposition"
PRETREATMENT_CYCLES_PATH = OUTPUT_DIR / "decomposition_pretreatment_cycles.parquet"
SURVIVAL_NATIONAL_PATH = OUTPUT_DIR / "decomposition_survival_national.parquet"
SURVIVAL_STATE_PATH = OUTPUT_DIR / "decomposition_survival_state.parquet"
SURVIVAL_MUNICIPALITY_PATH = OUTPUT_DIR / "decomposition_survival_municipality.parquet"
INFLOWS_PATH = OUTPUT_DIR / "decomposition_inflows.parquet"

ELECTION_YEARS = [2008, 2010, 2012, 2014, 2016, 2018]
STATE_MIN_CYCLES = 100
MUNICIPALITY_MIN_CYCLES = 2


def percent(value: float) -> str:
    return "NA" if pd.isna(value) else f"{100 * float(value):.2f}%"


def sigma_text(value: float) -> str:
    return "NA" if pd.isna(value) else f"{float(value):.3f}"


def load_panel() -> pd.DataFrame:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"Missing Prompt 1 main panel: {PANEL_PATH}")
    panel = pd.read_parquet(PANEL_PATH)
    required = {
        "ibge_municipality_id",
        "state",
        "year",
        "age_cohort",
        "education",
        "num_voters",
        "year_first_any_bvr",
        "first_regime",
    }
    missing = sorted(required - set(panel.columns))
    if missing:
        raise RuntimeError(f"{PANEL_PATH} is missing required columns: {missing}")

    panel = panel.copy()
    panel["ibge_municipality_id"] = panel["ibge_municipality_id"].astype(str).str.zfill(7)
    panel["state"] = panel["state"].astype(str).str.upper().str.strip()
    panel["year"] = pd.to_numeric(panel["year"], errors="raise").astype(int)
    panel["year_first_any_bvr"] = pd.to_numeric(panel["year_first_any_bvr"], errors="raise").astype(int)
    panel["num_voters"] = pd.to_numeric(panel["num_voters"], errors="raise").astype("int64")
    unexpected_age = sorted(set(panel["age_cohort"].unique()) - set(AGE_COHORTS))
    if unexpected_age:
        raise ValueError(f"Unexpected age cohorts in main panel: {unexpected_age}")
    return panel


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
    return wide[["ibge_municipality_id", "state", "year", "year_first_any_bvr", "first_regime", "total_voters"] + AGE_COHORTS]


def build_transition_data(age_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    left = age_panel.copy()
    left["t"] = left["year"]
    left["t_plus_2"] = left["year"] + 2

    right = age_panel[["ibge_municipality_id", "year"] + AGE_COHORTS].copy()
    right = right.rename(columns={"year": "t_plus_2", **{cohort: f"{cohort}__tp2" for cohort in AGE_COHORTS}})

    cycles_wide = left.merge(
        right,
        how="inner",
        on=["ibge_municipality_id", "t_plus_2"],
        validate="one_to_one",
    )
    cycles_wide = cycles_wide[cycles_wide["t_plus_2"].lt(cycles_wide["year_first_any_bvr"])].copy()
    cycles_wide = cycles_wide.sort_values(["ibge_municipality_id", "t"]).reset_index(drop=True)

    aged_forward = apply_aging_operator(cycles_wide[AGE_COHORTS])
    aged_forward = aged_forward.rename(columns={cohort: f"{cohort}__aged" for cohort in AGE_COHORTS})
    cycles_wide = pd.concat([cycles_wide, aged_forward], axis=1)

    id_columns = [
        "ibge_municipality_id",
        "state",
        "t",
        "t_plus_2",
        "total_voters",
        "year_first_any_bvr",
        "first_regime",
    ]
    pieces: list[pd.DataFrame] = []
    for cohort in AGE_COHORTS:
        piece = cycles_wide[id_columns].copy()
        piece["age_cohort"] = cohort
        piece["N_t"] = cycles_wide[cohort].to_numpy()
        piece["N_t_plus_2"] = cycles_wide[f"{cohort}__tp2"].to_numpy()
        piece["aged_forward_count"] = cycles_wide[f"{cohort}__aged"].to_numpy()
        piece["is_survival_cohort"] = cohort in SURVIVAL_COHORTS
        piece["is_inflow_cohort"] = cohort in INFLOW_COHORTS
        pieces.append(piece)
    transition_long = pd.concat(pieces, ignore_index=True)
    transition_long = transition_long.rename(columns={"total_voters": "total_voters_t"})
    transition_long = transition_long.sort_values(
        ["ibge_municipality_id", "t", "age_cohort"]
    ).reset_index(drop=True)
    return transition_long, cycles_wide


def cycle_availability(cycles_wide: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    cohort_municipalities = (
        panel[["ibge_municipality_id", "year_first_any_bvr"]]
        .drop_duplicates()
        .groupby("year_first_any_bvr", as_index=False)
        .agg(total_municipalities=("ibge_municipality_id", "nunique"))
    )
    usable = (
        cycles_wide.groupby("year_first_any_bvr", as_index=False)
        .agg(
            municipalities_with_cycles=("ibge_municipality_id", "nunique"),
            municipality_cycles=("ibge_municipality_id", "size"),
        )
    )
    availability = cohort_municipalities.merge(usable, how="left", on="year_first_any_bvr")
    availability[["municipalities_with_cycles", "municipality_cycles"]] = availability[
        ["municipalities_with_cycles", "municipality_cycles"]
    ].fillna(0).astype(int)
    availability["max_possible_cycles_per_municipality"] = availability["year_first_any_bvr"].map(
        lambda first_year: sum((year + 2) < first_year for year in ELECTION_YEARS[:-1])
    )
    availability["expected_municipality_cycles_if_all_years_present"] = (
        availability["total_municipalities"] * availability["max_possible_cycles_per_municipality"]
    )
    availability["age_cohort_cycle_rows"] = availability["municipality_cycles"] * len(AGE_COHORTS)
    return availability.sort_values("year_first_any_bvr")


def estimate_national_survival(transition_long: pd.DataFrame) -> pd.DataFrame:
    survival = transition_long[
        transition_long["age_cohort"].isin(SURVIVAL_COHORTS)
        & transition_long["aged_forward_count"].gt(0)
    ].copy()
    raw = (
        survival.groupby("age_cohort", as_index=False)
        .agg(
            n_cycles=("aged_forward_count", "size"),
            total_predicted=("aged_forward_count", "sum"),
            total_observed=("N_t_plus_2", "sum"),
        )
    )
    raw["sigma_national"] = raw["total_observed"] / raw["total_predicted"]

    all_ages = pd.DataFrame({"age_cohort": AGE_COHORTS})
    national = all_ages.merge(raw, how="left", on="age_cohort")
    national["n_cycles"] = national["n_cycles"].fillna(0).astype(int)
    national[["total_predicted", "total_observed"]] = national[["total_predicted", "total_observed"]].fillna(0.0)
    national["rate_type"] = np.where(national["age_cohort"].isin(INFLOW_COHORTS), "inflow_only", "survival")
    return national


def estimate_state_survival(transition_long: pd.DataFrame, national: pd.DataFrame) -> pd.DataFrame:
    survival = transition_long[
        transition_long["age_cohort"].isin(SURVIVAL_COHORTS)
        & transition_long["aged_forward_count"].gt(0)
    ].copy()
    raw = (
        survival.groupby(["state", "age_cohort"], as_index=False)
        .agg(
            n_cycles=("aged_forward_count", "size"),
            total_predicted=("aged_forward_count", "sum"),
            total_observed=("N_t_plus_2", "sum"),
        )
    )
    raw["sigma_state"] = raw["total_observed"] / raw["total_predicted"]

    states = pd.DataFrame({"state": sorted(transition_long["state"].unique())})
    all_state_age = states.merge(pd.DataFrame({"age_cohort": AGE_COHORTS}), how="cross")
    state = all_state_age.merge(raw, how="left", on=["state", "age_cohort"])
    state = state.merge(national[["age_cohort", "sigma_national"]], how="left", on="age_cohort")
    state["n_cycles"] = state["n_cycles"].fillna(0).astype(int)
    state[["total_predicted", "total_observed"]] = state[["total_predicted", "total_observed"]].fillna(0.0)
    state["state_threshold_met"] = (
        state["age_cohort"].isin(SURVIVAL_COHORTS)
        & state["n_cycles"].ge(STATE_MIN_CYCLES)
        & state["sigma_state"].notna()
    )
    state["sigma_used"] = np.where(state["state_threshold_met"], state["sigma_state"], state["sigma_national"])
    state.loc[state["age_cohort"].isin(INFLOW_COHORTS), "sigma_used"] = np.nan
    state["fallback_source"] = np.select(
        [
            state["age_cohort"].isin(INFLOW_COHORTS),
            state["state_threshold_met"],
            state["age_cohort"].isin(SURVIVAL_COHORTS),
        ],
        ["inflow_only", "state", "national"],
        default="unknown",
    )
    return state


def estimate_municipality_survival(
    transition_long: pd.DataFrame,
    state_survival: pd.DataFrame,
    national: pd.DataFrame,
    panel: pd.DataFrame,
) -> pd.DataFrame:
    survival = transition_long[
        transition_long["age_cohort"].isin(SURVIVAL_COHORTS)
        & transition_long["aged_forward_count"].gt(0)
    ].copy()
    survival["cycle_threshold"] = survival["age_cohort"].map(per_cycle_threshold)
    usable = survival[survival["aged_forward_count"].ge(survival["cycle_threshold"])].copy()

    raw = (
        usable.groupby(["ibge_municipality_id", "state", "age_cohort"], as_index=False)
        .agg(
            n_cycles_used=("aged_forward_count", "size"),
            total_predicted_used=("aged_forward_count", "sum"),
            total_observed_used=("N_t_plus_2", "sum"),
        )
    )
    raw["sigma_municipality"] = raw["total_observed_used"] / raw["total_predicted_used"]

    municipalities = panel[["ibge_municipality_id", "state"]].drop_duplicates()
    all_muni_age = municipalities.merge(pd.DataFrame({"age_cohort": AGE_COHORTS}), how="cross")
    muni = all_muni_age.merge(raw, how="left", on=["ibge_municipality_id", "state", "age_cohort"])
    muni = muni.merge(
        state_survival[
            [
                "state",
                "age_cohort",
                "sigma_state",
                "sigma_used",
                "fallback_source",
                "state_threshold_met",
            ]
        ].rename(
            columns={
                "sigma_used": "sigma_state_fallback",
                "fallback_source": "state_fallback_source",
            }
        ),
        how="left",
        on=["state", "age_cohort"],
    )
    muni = muni.merge(national[["age_cohort", "sigma_national"]], how="left", on="age_cohort")
    muni["n_cycles_used"] = muni["n_cycles_used"].fillna(0).astype(int)
    muni[["total_predicted_used", "total_observed_used"]] = muni[
        ["total_predicted_used", "total_observed_used"]
    ].fillna(0.0)
    muni["municipality_threshold_met"] = (
        muni["age_cohort"].isin(SURVIVAL_COHORTS)
        & muni["n_cycles_used"].ge(MUNICIPALITY_MIN_CYCLES)
        & muni["sigma_municipality"].notna()
    )
    muni["state_threshold_met"] = muni["state_threshold_met"].map(lambda value: bool(value) if pd.notna(value) else False)

    muni["sigma_used"] = np.nan
    muni["rate_source"] = "inflow_only"
    municipality_rows = muni["municipality_threshold_met"]
    state_rows = (
        muni["age_cohort"].isin(SURVIVAL_COHORTS)
        & ~municipality_rows
        & muni["state_threshold_met"]
    )
    national_rows = (
        muni["age_cohort"].isin(SURVIVAL_COHORTS)
        & ~municipality_rows
        & ~muni["state_threshold_met"]
    )
    muni.loc[municipality_rows, "sigma_used"] = muni.loc[municipality_rows, "sigma_municipality"]
    muni.loc[state_rows, "sigma_used"] = muni.loc[state_rows, "sigma_state_fallback"]
    muni.loc[national_rows, "sigma_used"] = muni.loc[national_rows, "sigma_national"]
    muni.loc[municipality_rows, "rate_source"] = "municipality"
    muni.loc[state_rows, "rate_source"] = "state"
    muni.loc[national_rows, "rate_source"] = "national"

    return muni.sort_values(["ibge_municipality_id", "age_cohort"]).reset_index(drop=True)


def estimate_inflows(transition_long: pd.DataFrame, panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    inflow_cycles = transition_long[transition_long["age_cohort"].isin(INFLOW_COHORTS)].copy()
    inflow_cycles = inflow_cycles[inflow_cycles["total_voters_t"].gt(0)].copy()

    national = (
        inflow_cycles.groupby("age_cohort", as_index=False)
        .agg(
            n_cycles=("total_voters_t", "size"),
            total_inflow=("N_t_plus_2", "sum"),
            total_denominator=("total_voters_t", "sum"),
        )
    )
    national["inflow_rate_national"] = national["total_inflow"] / national["total_denominator"]

    state_raw = (
        inflow_cycles.groupby(["state", "age_cohort"], as_index=False)
        .agg(
            n_cycles_state=("total_voters_t", "size"),
            total_inflow_state=("N_t_plus_2", "sum"),
            total_denominator_state=("total_voters_t", "sum"),
        )
    )
    state_raw["inflow_rate_state"] = state_raw["total_inflow_state"] / state_raw["total_denominator_state"]
    states = pd.DataFrame({"state": sorted(panel["state"].unique())})
    state = states.merge(pd.DataFrame({"age_cohort": INFLOW_COHORTS}), how="cross")
    state = state.merge(state_raw, how="left", on=["state", "age_cohort"])
    state = state.merge(national[["age_cohort", "inflow_rate_national"]], how="left", on="age_cohort")
    state["n_cycles_state"] = state["n_cycles_state"].fillna(0).astype(int)
    state["state_threshold_met"] = state["n_cycles_state"].ge(STATE_MIN_CYCLES) & state["inflow_rate_state"].notna()
    state["inflow_rate_state_used"] = np.where(
        state["state_threshold_met"],
        state["inflow_rate_state"],
        state["inflow_rate_national"],
    )

    inflow_cycles["cycle_threshold"] = 100
    usable = inflow_cycles[inflow_cycles["total_voters_t"].ge(inflow_cycles["cycle_threshold"])].copy()
    muni_raw = (
        usable.groupby(["ibge_municipality_id", "state", "age_cohort"], as_index=False)
        .agg(
            n_cycles_used=("total_voters_t", "size"),
            total_inflow=("N_t_plus_2", "sum"),
            total_denominator=("total_voters_t", "sum"),
        )
    )
    muni_raw["inflow_rate"] = muni_raw["total_inflow"] / muni_raw["total_denominator"]

    municipalities = panel[["ibge_municipality_id", "state"]].drop_duplicates()
    inflows = municipalities.merge(pd.DataFrame({"age_cohort": INFLOW_COHORTS}), how="cross")
    inflows = inflows.merge(muni_raw, how="left", on=["ibge_municipality_id", "state", "age_cohort"])
    inflows = inflows.merge(
        state[
            [
                "state",
                "age_cohort",
                "inflow_rate_state",
                "inflow_rate_state_used",
                "state_threshold_met",
            ]
        ],
        how="left",
        on=["state", "age_cohort"],
    )
    inflows = inflows.merge(national[["age_cohort", "inflow_rate_national"]], how="left", on="age_cohort")
    inflows["n_cycles_used"] = inflows["n_cycles_used"].fillna(0).astype(int)
    inflows[["total_inflow", "total_denominator"]] = inflows[["total_inflow", "total_denominator"]].fillna(0.0)
    inflows["municipality_threshold_met"] = (
        inflows["n_cycles_used"].ge(MUNICIPALITY_MIN_CYCLES) & inflows["inflow_rate"].notna()
    )
    municipality_rows = inflows["municipality_threshold_met"]
    state_rows = ~municipality_rows & inflows["state_threshold_met"].fillna(False)
    national_rows = ~municipality_rows & ~inflows["state_threshold_met"].fillna(False)
    inflows["inflow_rate_used"] = np.nan
    inflows["rate_source"] = "national"
    inflows.loc[municipality_rows, "inflow_rate_used"] = inflows.loc[municipality_rows, "inflow_rate"]
    inflows.loc[state_rows, "inflow_rate_used"] = inflows.loc[state_rows, "inflow_rate_state_used"]
    inflows.loc[national_rows, "inflow_rate_used"] = inflows.loc[national_rows, "inflow_rate_national"]
    inflows.loc[municipality_rows, "rate_source"] = "municipality"
    inflows.loc[state_rows, "rate_source"] = "state"
    return inflows.sort_values(["ibge_municipality_id", "age_cohort"]).reset_index(drop=True), national


def national_survival_anomalies(national: pd.DataFrame) -> pd.DataFrame:
    check = national[
        national["age_cohort"].isin(SURVIVAL_COHORTS)
        & national["age_cohort"].ne("100 anos ou mais")
        & national["sigma_national"].notna()
    ].copy()
    return check[check["sigma_national"].gt(1.05) | check["sigma_national"].lt(0.50)].copy()


def municipality_consistency_diagnostics(
    panel: pd.DataFrame,
    municipality_survival: pd.DataFrame,
) -> pd.DataFrame:
    latest_year = int(panel["year"].max())
    large_munis = (
        panel[panel["year"].eq(latest_year)]
        .groupby("ibge_municipality_id", as_index=False)
        .agg(total_voters=("num_voters", "sum"))
        .sort_values("total_voters", ascending=False)
        .head(50)
    )
    comparison = municipality_survival[
        municipality_survival["ibge_municipality_id"].isin(large_munis["ibge_municipality_id"])
        & municipality_survival["rate_source"].eq("municipality")
        & municipality_survival["sigma_state_fallback"].notna()
    ].copy()
    comparison["abs_diff_state"] = (comparison["sigma_municipality"] - comparison["sigma_state_fallback"]).abs()
    flags = (
        comparison.groupby(["ibge_municipality_id", "state"], as_index=False)
        .agg(
            cohorts_compared=("age_cohort", "size"),
            cohorts_diff_gt_0_10=("abs_diff_state", lambda s: int(s.gt(0.10).sum())),
            max_abs_diff=("abs_diff_state", "max"),
        )
    )
    flags = flags[flags["cohorts_diff_gt_0_10"].ge(5)].sort_values(
        ["cohorts_diff_gt_0_10", "max_abs_diff"], ascending=False
    )
    return flags


def inflow_pattern_anomalies(inflow_national: pd.DataFrame) -> list[str]:
    rates = inflow_national.set_index("age_cohort")["inflow_rate_national"].to_dict()
    anomalies: list[str] = []
    if rates.get("18 anos", -np.inf) < max(rates.values()):
        anomalies.append("18-year inflow rate is not the largest of the 16-19 cohorts")
    if rates.get("16 anos", 0) > rates.get("18 anos", np.inf):
        anomalies.append("16-year inflow rate exceeds the 18-year inflow rate")
    if rates.get("17 anos", 0) > rates.get("18 anos", np.inf):
        anomalies.append("17-year inflow rate exceeds the 18-year inflow rate")
    if rates.get("19 anos", 0) > rates.get("18 anos", np.inf):
        anomalies.append("19-year inflow rate exceeds the 18-year inflow rate")
    return anomalies


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


def main() -> None:
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)

    validate_aging_matrix()
    panel = load_panel()
    age_panel = build_age_count_panel(panel)
    transition_long, cycles_wide = build_transition_data(age_panel)

    cycle_output = transition_long[
        [
            "ibge_municipality_id",
            "state",
            "t",
            "t_plus_2",
            "age_cohort",
            "N_t",
            "N_t_plus_2",
            "aged_forward_count",
            "total_voters_t",
            "year_first_any_bvr",
            "first_regime",
        ]
    ].copy()

    national = estimate_national_survival(transition_long)
    state = estimate_state_survival(transition_long, national)
    municipality = estimate_municipality_survival(transition_long, state, national, panel)
    inflows, inflow_national = estimate_inflows(transition_long, panel)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cycle_output.to_parquet(PRETREATMENT_CYCLES_PATH, index=False)
    national.to_parquet(SURVIVAL_NATIONAL_PATH, index=False)
    state.to_parquet(SURVIVAL_STATE_PATH, index=False)
    municipality.to_parquet(SURVIVAL_MUNICIPALITY_PATH, index=False)
    inflows.to_parquet(INFLOWS_PATH, index=False)

    availability = cycle_availability(cycles_wide, panel)

    national_anomalies = national_survival_anomalies(national)
    municipality_flags = municipality_consistency_diagnostics(panel, municipality)
    inflow_anomalies = inflow_pattern_anomalies(inflow_national)

    survival_cells = municipality[municipality["age_cohort"].isin(SURVIVAL_COHORTS)].copy()
    source_counts = survival_cells["rate_source"].value_counts(normalize=True).mul(100)
    source_counts_abs = survival_cells["rate_source"].value_counts()
    muni_specific_pct = source_counts.get("municipality", 0.0)
    state_fallback_pct = source_counts.get("state", 0.0)
    national_fallback_pct = source_counts.get("national", 0.0)

    state_below_threshold = state[
        state["age_cohort"].isin(SURVIVAL_COHORTS) & ~state["state_threshold_met"]
    ]
    state_below_50 = state[state["age_cohort"].isin(SURVIVAL_COHORTS) & state["n_cycles"].lt(50)]

    national_display = national.copy()
    national_display["sigma_national"] = national_display["sigma_national"].map(sigma_text)
    national_display = national_display[["age_cohort", "sigma_national", "n_cycles", "total_predicted", "total_observed", "rate_type"]]

    inflow_display = inflow_national[["age_cohort", "inflow_rate_national", "n_cycles"]].copy()
    inflow_display["inflow_rate_national"] = inflow_display["inflow_rate_national"].map(percent)

    print("=" * 64)
    print("PRE-TREATMENT CYCLE AVAILABILITY")
    print("=" * 64)
    print_table("Municipality-cycle availability by first-treatment cohort", availability)
    print(f"\nPre-treatment municipality-cycle pairs: {len(cycles_wide):,}")
    print(f"Pre-treatment age-cohort rows: {len(transition_long):,}")

    print("\n" + "=" * 64)
    print("SURVIVAL AND INFLOW RATE ESTIMATION SUMMARY")
    print("=" * 64)
    print("\nNational survival rates by age cohort:")
    for _, row in national.iterrows():
        label = row["age_cohort"]
        if label in INFLOW_COHORTS:
            print(f"  {label}: inflow-only (n=0)")
        else:
            print(f"  {label}: {sigma_text(row['sigma_national'])} (n={int(row['n_cycles']):,})")

    print("\nNational inflow rates (share of total t-period electorate):")
    for _, row in inflow_national.iterrows():
        print(f"  {row['age_cohort']}: {percent(row['inflow_rate_national'])} (n={int(row['n_cycles']):,})")

    print(
        "\nMunicipality-specific estimates: "
        f"{muni_specific_pct:.1f}% of municipality-cohort cells met the threshold for muni-specific rates; "
        f"{state_fallback_pct:.1f}% used state fallback; "
        f"{national_fallback_pct:.1f}% used national fallback."
    )
    print(f"  Absolute cells by source: {source_counts_abs.to_dict()}")
    print(f"\nState-cohort survival cells below {STATE_MIN_CYCLES} cycles: {len(state_below_threshold):,}")
    print(f"State-cohort survival cells below 50 cycles: {len(state_below_50):,}")

    print_table("National survival-rate anomalies", national_anomalies[["age_cohort", "sigma_national", "n_cycles"]])
    print_table("Large-municipality consistency flags", municipality_flags, max_rows=15)
    if inflow_anomalies:
        print("\nInflow pattern anomalies:")
        for anomaly in inflow_anomalies:
            print(f"  - {anomaly}")
    else:
        print("\nInflow pattern anomalies: none")

    anomaly_count = len(national_anomalies) + len(municipality_flags) + len(inflow_anomalies)
    print(f"\nAnomalies flagged: {anomaly_count}")

    print("\nFiles saved:")
    for path in [
        PRETREATMENT_CYCLES_PATH,
        SURVIVAL_NATIONAL_PATH,
        SURVIVAL_STATE_PATH,
        SURVIVAL_MUNICIPALITY_PATH,
        INFLOWS_PATH,
    ]:
        print(f"  {path.relative_to(ROOT)}")

    print("\nReady for counterfactual prediction in Prompt 3.")


if __name__ == "__main__":
    main()
