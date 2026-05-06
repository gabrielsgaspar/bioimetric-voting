from __future__ import annotations

import importlib.util
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_data_v2.parquet"
OUTPUT_DIR = ROOT / "data" / "clean" / "decomposition"

PANEL_MAIN_V2_PATH = OUTPUT_DIR / "decomposition_panel_main_v2.parquet"
PANEL_FULL_V2_PATH = OUTPUT_DIR / "decomposition_panel_full_v2.parquet"
RESIDUAL_REPORT_V2_PATH = OUTPUT_DIR / "decomposition_residual_report_v2.parquet"
PROGRESSION_V2_PATH = OUTPUT_DIR / "decomposition_progression_rates_v2.parquet"
PREDICTION_EDU_V2_PATH = OUTPUT_DIR / "decomposition_prediction_education_v2.parquet"
RELABEL_COHORT_V2_PATH = OUTPUT_DIR / "decomposition_relabel_cohort_v2.parquet"
RELABEL_MUNICIPALITY_V2_PATH = OUTPUT_DIR / "decomposition_relabel_municipality_v2.parquet"
FINAL_MUNICIPALITY_V2_PATH = OUTPUT_DIR / "decomposition_final_municipality_v2.parquet"
FINAL_AGGREGATE_V2_PATH = OUTPUT_DIR / "decomposition_final_aggregate_v2.parquet"
FINAL_BY_COHORT_V2_PATH = OUTPUT_DIR / "decomposition_final_by_cohort_v2.parquet"
CONSISTENCY_V2_PATH = OUTPUT_DIR / "decomposition_consistency_check_v2.parquet"
MAP_COUNTS_V2_PATH = OUTPUT_DIR / "decomposition_map_counts_v2.parquet"
MAP_RATES_V2_PATH = OUTPUT_DIR / "decomposition_map_rates_v2.parquet"
COMPARISON_PATH = OUTPUT_DIR / "decomposition_v1_vs_v2_comparison.parquet"

EXIT_COHORT_PATH = OUTPUT_DIR / "decomposition_exit_cohort.parquet"
EXIT_MUNICIPALITY_PATH = OUTPUT_DIR / "decomposition_exit_municipality.parquet"
FINAL_AGGREGATE_V1_PATH = OUTPUT_DIR / "decomposition_final_aggregate.parquet"
FINAL_MUNICIPALITY_V1_PATH = OUTPUT_DIR / "decomposition_final_municipality.parquet"
FINAL_BY_COHORT_V1_PATH = OUTPUT_DIR / "decomposition_final_by_cohort.parquet"
CONSISTENCY_V1_PATH = OUTPUT_DIR / "decomposition_consistency_check.parquet"

EXPECTED_YEARS = [2008, 2010, 2012, 2014, 2016, 2018]
TREATED_YEARS = {2010, 2012, 2014, 2016, 2018}
REQUIRED_COLUMNS = [
    "year",
    "ibge_municipality_id",
    "state",
    "bvr_status",
    "year_first_any_bvr",
    "year_first_strict_bvr",
    "year_first_hybrid_bvr",
    "age_cohort",
    "education",
    "low_ed",
    "high_ed",
    "num_voters",
    "num_voters_bvr",
    "pct_bvr",
    "pct_bvr_imputed",
    "pct_bvr_source",
]
PANEL_COLUMNS = [
    "ibge_municipality_id",
    "state",
    "year",
    "age_cohort",
    "education",
    "low_ed",
    "high_ed",
    "num_voters",
    "num_voters_bvr",
    "pct_bvr",
    "pct_bvr_imputed",
    "pct_bvr_source",
    "bvr_status",
    "year_first_any_bvr",
    "year_first_strict_bvr",
    "year_first_hybrid_bvr",
    "first_regime",
    "event_time",
]


def load_module(module_name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not import {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


decomp04 = load_module("decomp04", "src/decomposition/04_compute_relabel.py")
decomp05 = load_module("decomp05", "src/decomposition/05_aggregate_and_check.py")


def percent(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{100 * float(value):.2f}%"


def pp(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{100 * float(value):+.2f}pp"


def count(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{float(value):,.0f}"


def normalize_label(value: object) -> str:
    text = "" if value is None else str(value).strip().lower()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def load_v2_source() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(INPUT_PATH)
    df = pd.read_parquet(INPUT_PATH)
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise RuntimeError(f"{INPUT_PATH} is missing required columns: {missing}")
    df = df.copy()
    df["ibge_municipality_id"] = df["ibge_municipality_id"].astype(str).str.zfill(7)
    df["state"] = df["state"].astype(str).str.upper().str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    for column in ["year_first_any_bvr", "year_first_strict_bvr", "year_first_hybrid_bvr"]:
        df[column] = pd.to_numeric(df[column], errors="raise").astype(int)
    for column in ["low_ed", "high_ed", "num_voters", "num_voters_bvr"]:
        df[column] = pd.to_numeric(df[column], errors="raise").astype("int64")
    df["pct_bvr"] = pd.to_numeric(df["pct_bvr"], errors="coerce").fillna(0.0)
    df["pct_bvr_imputed"] = df["pct_bvr_imputed"].astype(bool)
    df["pct_bvr_source"] = df["pct_bvr_source"].astype(str)
    return df


def attach_first_regime(df: pd.DataFrame) -> pd.DataFrame:
    muni_year_status = df[["ibge_municipality_id", "year", "bvr_status"]].drop_duplicates()
    timing = df[["ibge_municipality_id", "year_first_any_bvr"]].drop_duplicates("ibge_municipality_id")
    treated = timing[timing["year_first_any_bvr"].ne(9999)].rename(columns={"year_first_any_bvr": "year"})
    first_status = treated.merge(muni_year_status, how="left", on=["ibge_municipality_id", "year"])
    first_status["first_regime"] = first_status["bvr_status"].map({"strict_bvr": "strict", "hybrid_bvr": "hybrid"})
    regime = first_status[["ibge_municipality_id", "first_regime"]]
    output = df.merge(regime, how="left", on="ibge_municipality_id", validate="many_to_one")
    output["first_regime"] = output["first_regime"].fillna("never_treated")
    output["event_time"] = pd.Series(pd.NA, index=output.index, dtype="Int64")
    treated_rows = output["year_first_any_bvr"].ne(9999)
    output.loc[treated_rows, "event_time"] = (
        output.loc[treated_rows, "year"] - output.loc[treated_rows, "year_first_any_bvr"]
    ).astype("int64")
    return output


def residual_masks(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    invalid_age = df["age_cohort"].map(normalize_label).eq("invalido")
    unknown_education = df["education"].map(normalize_label).isin({"nao informado", "#ne", "ne", ""})
    return invalid_age, unknown_education


def rebuild_panels(source: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prepared = attach_first_regime(source)
    positive = prepared[prepared["num_voters"].gt(0)].copy()
    invalid_age, unknown_education = residual_masks(positive)
    full = positive[PANEL_COLUMNS].copy().sort_values(["ibge_municipality_id", "year", "age_cohort", "education"])
    main = positive.loc[~invalid_age & ~unknown_education, PANEL_COLUMNS].copy()
    main = main.sort_values(["ibge_municipality_id", "year", "age_cohort", "education"]).reset_index(drop=True)
    full = full.reset_index(drop=True)

    excluded = invalid_age | unknown_education
    residual = (
        positive.assign(excluded=excluded, excluded_voters=np.where(excluded, positive["num_voters"], 0))
        .groupby(["year", "state", "first_regime"], as_index=False)
        .agg(total_voters_full=("num_voters", "sum"), total_voters_excluded=("excluded_voters", "sum"))
    )
    residual["excluded_share"] = residual["total_voters_excluded"] / residual["total_voters_full"].replace(0, np.nan)
    return main, full, residual


def build_cohort_bvr_flags(panel_main: pd.DataFrame) -> pd.DataFrame:
    working = panel_main.copy()
    working["imputed_voters"] = np.where(working["pct_bvr_imputed"], working["num_voters"], 0)
    source_summary = (
        working.groupby(["ibge_municipality_id", "year", "age_cohort"])["pct_bvr_source"]
        .agg(lambda s: "|".join(sorted(set(map(str, s)))))
        .reset_index(name="pct_bvr_source")
    )
    flags = (
        working.groupby(["ibge_municipality_id", "year", "age_cohort"], as_index=False)
        .agg(
            pct_bvr_imputed_any=("pct_bvr_imputed", "any"),
            pct_bvr_imputed_voter_share=("imputed_voters", "sum"),
            N_total_for_impute_share=("num_voters", "sum"),
        )
        .merge(source_summary, how="left", on=["ibge_municipality_id", "year", "age_cohort"])
    )
    flags["pct_bvr_imputed_voter_share"] = (
        flags["pct_bvr_imputed_voter_share"] / flags["N_total_for_impute_share"].replace(0, np.nan)
    )
    return flags.drop(columns="N_total_for_impute_share").rename(columns={"year": "t_post"})


def rerun_relabel(panel_main: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    exit_cohort = pd.read_parquet(EXIT_COHORT_PATH)
    exit_cohort["ibge_municipality_id"] = exit_cohort["ibge_municipality_id"].astype(str).str.zfill(7)
    exit_cohort["state"] = exit_cohort["state"].astype(str).str.upper().str.strip()

    edu_counts = decomp04.build_education_counts(panel_main)
    progression_cycles = decomp04.build_progression_cycles(edu_counts)
    progression = decomp04.estimate_progression_rates(edu_counts, progression_cycles)
    prediction_education, _ = decomp04.build_prediction_education(edu_counts, exit_cohort, progression)
    relabel_cohort, _ = decomp04.compute_relabel_cohort(prediction_education, exit_cohort)

    flags = build_cohort_bvr_flags(panel_main)
    relabel_cohort = relabel_cohort.merge(
        flags,
        how="left",
        on=["ibge_municipality_id", "t_post", "age_cohort"],
        validate="one_to_one",
    )
    prediction_education = prediction_education.merge(
        flags,
        how="left",
        on=["ibge_municipality_id", "t_post", "age_cohort"],
        validate="one_to_one",
    )
    for frame in [relabel_cohort, prediction_education]:
        frame["pct_bvr_imputed_any"] = frame["pct_bvr_imputed_any"].fillna(False).astype(bool)
        frame["pct_bvr_imputed_voter_share"] = frame["pct_bvr_imputed_voter_share"].fillna(0.0)
        frame["pct_bvr_source"] = frame["pct_bvr_source"].fillna("missing")

    relabel_municipality = decomp04.aggregate_relabel_municipality(relabel_cohort)
    impute_summary = (
        relabel_cohort.assign(
            imputed_cohort=relabel_cohort["pct_bvr_imputed_any"],
            imputed_voters=relabel_cohort["pct_bvr_imputed_voter_share"] * relabel_cohort["N_observed_total"],
        )
        .groupby(["ibge_municipality_id", "t_post"], as_index=False)
        .agg(
            n_cohorts_pct_bvr_imputed=("imputed_cohort", "sum"),
            pct_bvr_imputed_voters=("imputed_voters", "sum"),
            N_observed_total_for_impute=("N_observed_total", "sum"),
        )
    )
    impute_summary["pct_bvr_imputed_voter_share"] = (
        impute_summary["pct_bvr_imputed_voters"] / impute_summary["N_observed_total_for_impute"].replace(0, np.nan)
    )
    relabel_municipality = relabel_municipality.merge(
        impute_summary[
            [
                "ibge_municipality_id",
                "t_post",
                "n_cohorts_pct_bvr_imputed",
                "pct_bvr_imputed_voter_share",
            ]
        ],
        how="left",
        on=["ibge_municipality_id", "t_post"],
        validate="one_to_one",
    )
    return progression, prediction_education, relabel_cohort, relabel_municipality


def rerun_aggregate(panel_main: pd.DataFrame, relabel_municipality: pd.DataFrame, relabel_cohort: pd.DataFrame):
    exit_muni = pd.read_parquet(EXIT_MUNICIPALITY_PATH)
    for frame in [exit_muni, relabel_municipality, relabel_cohort]:
        frame["ibge_municipality_id"] = frame["ibge_municipality_id"].astype(str).str.zfill(7)
        if "state" in frame.columns:
            frame["state"] = frame["state"].astype(str).str.upper().str.strip()
    baseline = decomp05.build_2008_baseline(panel_main)
    final = decomp05.build_final_municipality(exit_muni, relabel_municipality, baseline)
    aggregate = decomp05.build_aggregate(final)
    by_cohort = decomp05.build_by_cohort(final, relabel_cohort)
    ratio, _ = decomp05.estimate_2008_to_2006_ratio(final)
    consistency = decomp05.build_consistency(aggregate, ratio)
    map_rates, map_counts = decomp05.build_map_files(final)
    return final, aggregate, by_cohort, consistency, map_rates, map_counts


def aggregate_by_year(final: pd.DataFrame) -> pd.DataFrame:
    out = (
        final.groupby("year_first_any_bvr", as_index=False)
        .agg(
            municipalities=("ibge_municipality_id", "nunique"),
            N_2008_total=("N_2008_total", "sum"),
            exit_count=("exit_count", "sum"),
            R_B_count=("R_B_count", "sum"),
            R_C_count=("R_C_count", "sum"),
        )
        .sort_values("year_first_any_bvr")
    )
    out["exit_rate_2008"] = out["exit_count"] / out["N_2008_total"].replace(0, np.nan)
    out["R_B_rate_2008"] = out["R_B_count"] / out["N_2008_total"].replace(0, np.nan)
    out["R_C_rate_2008"] = out["R_C_count"] / out["N_2008_total"].replace(0, np.nan)
    return out


def aggregate_by_state(final: pd.DataFrame) -> pd.DataFrame:
    out = (
        final.groupby("state", as_index=False)
        .agg(
            municipalities=("ibge_municipality_id", "nunique"),
            N_2008_total=("N_2008_total", "sum"),
            exit_count=("exit_count", "sum"),
            R_B_count=("R_B_count", "sum"),
            R_C_count=("R_C_count", "sum"),
        )
        .sort_values("state")
    )
    out["exit_rate_2008"] = out["exit_count"] / out["N_2008_total"].replace(0, np.nan)
    out["R_B_rate_2008"] = out["R_B_count"] / out["N_2008_total"].replace(0, np.nan)
    out["R_C_rate_2008"] = out["R_C_count"] / out["N_2008_total"].replace(0, np.nan)
    return out


def build_comparison(
    final_v2: pd.DataFrame,
    aggregate_v2: pd.DataFrame,
    consistency_v2: pd.DataFrame,
) -> pd.DataFrame:
    aggregate_v1 = pd.read_parquet(FINAL_AGGREGATE_V1_PATH)
    final_v1 = pd.read_parquet(FINAL_MUNICIPALITY_V1_PATH)
    consistency_v1 = pd.read_parquet(CONSISTENCY_V1_PATH)
    for frame in [final_v1, final_v2]:
        frame["ibge_municipality_id"] = frame["ibge_municipality_id"].astype(str).str.zfill(7)

    v1 = aggregate_v1[aggregate_v1["aggregation_level"].eq("all_treated")].iloc[0]
    v2 = aggregate_v2[aggregate_v2["aggregation_level"].eq("all_treated")].iloc[0]
    rows: list[dict[str, object]] = []
    for metric, label in [
        ("national_exit_count", "National exit count"),
        ("national_exit_rate_2008", "National exit rate (2008 baseline)"),
        ("national_R_B_count", "National R_B count"),
        ("national_R_B_rate_2008", "National R_B rate (2008 baseline)"),
        ("national_R_C_count", "National R_C count"),
        ("national_R_C_rate_2008", "National R_C rate (2008 baseline)"),
    ]:
        rows.append(
            {
                "section": "aggregate_headline",
                "group": "all_treated",
                "metric": label,
                "v1": float(v1[metric]),
                "v2": float(v2[metric]),
                "delta": float(v2[metric] - v1[metric]),
                "cross_section": np.nan,
            }
        )

    by_year_v1 = aggregate_by_year(final_v1)
    by_year_v2 = aggregate_by_year(final_v2)
    by_year = by_year_v1[["year_first_any_bvr", "R_B_count", "R_B_rate_2008"]].merge(
        by_year_v2[["year_first_any_bvr", "R_B_count", "R_B_rate_2008"]],
        how="outer",
        on="year_first_any_bvr",
        suffixes=("_v1", "_v2"),
    )
    for _, row in by_year.iterrows():
        rows.append(
            {
                "section": "relabel_by_treatment_cohort_year",
                "group": str(int(row["year_first_any_bvr"])),
                "metric": "R_B_count",
                "v1": float(row["R_B_count_v1"]),
                "v2": float(row["R_B_count_v2"]),
                "delta": float(row["R_B_count_v2"] - row["R_B_count_v1"]),
                "cross_section": np.nan,
            }
        )
        rows.append(
            {
                "section": "relabel_by_treatment_cohort_year",
                "group": str(int(row["year_first_any_bvr"])),
                "metric": "R_B_rate_2008",
                "v1": float(row["R_B_rate_2008_v1"]),
                "v2": float(row["R_B_rate_2008_v2"]),
                "delta": float(row["R_B_rate_2008_v2"] - row["R_B_rate_2008_v1"]),
                "cross_section": np.nan,
            }
        )

    state_v1 = aggregate_by_state(final_v1)
    state_v2 = aggregate_by_state(final_v2)
    states = state_v1[["state", "R_B_rate_2008"]].merge(
        state_v2[["state", "R_B_rate_2008"]],
        how="outer",
        on="state",
        suffixes=("_v1", "_v2"),
    )
    for state in ["AL", "SE"]:
        row = states[states["state"].eq(state)].iloc[0]
        rows.append(
            {
                "section": "state_level_changes",
                "group": state,
                "metric": "R_B_rate_2008",
                "v1": float(row["R_B_rate_2008_v1"]),
                "v2": float(row["R_B_rate_2008_v2"]),
                "delta": float(row["R_B_rate_2008_v2"] - row["R_B_rate_2008_v1"]),
                "cross_section": np.nan,
            }
        )

    cross = {"exit_scenario_B": 0.1260, "R_B_lower_bound": 0.0522, "R_C_scenario_C": 0.1040}
    merged_consistency = consistency_v1.merge(consistency_v2, how="outer", on="metric", suffixes=("_v1", "_v2"))
    for _, row in merged_consistency.iterrows():
        metric = str(row["metric"])
        rows.append(
            {
                "section": "cross_section_consistency",
                "group": metric,
                "metric": "muni_level_value_2008_baseline",
                "v1": float(row["muni_level_value_2008_baseline_v1"]),
                "v2": float(row["muni_level_value_2008_baseline_v2"]),
                "delta": float(row["muni_level_value_2008_baseline_v2"] - row["muni_level_value_2008_baseline_v1"]),
                "cross_section": cross.get(metric, np.nan),
            }
        )
        rows.append(
            {
                "section": "cross_section_consistency",
                "group": metric,
                "metric": "muni_level_value_rescaled_to_2006",
                "v1": float(row["muni_level_value_rescaled_to_2006_v1"]),
                "v2": float(row["muni_level_value_rescaled_to_2006_v2"]),
                "delta": float(row["muni_level_value_rescaled_to_2006_v2"] - row["muni_level_value_rescaled_to_2006_v1"]),
                "cross_section": cross.get(metric, np.nan),
            }
        )
    return pd.DataFrame(rows)


def print_comparison_tables(comparison: pd.DataFrame, final_v2: pd.DataFrame, aggregate_v2: pd.DataFrame, consistency_v2: pd.DataFrame) -> None:
    aggregate_rows = comparison[comparison["section"].eq("aggregate_headline")].copy()
    aggregate_rows["v1_display"] = aggregate_rows.apply(
        lambda r: percent(r["v1"]) if "rate" in r["metric"] else count(r["v1"]), axis=1
    )
    aggregate_rows["v2_display"] = aggregate_rows.apply(
        lambda r: percent(r["v2"]) if "rate" in r["metric"] else count(r["v2"]), axis=1
    )
    aggregate_rows["delta_display"] = aggregate_rows.apply(
        lambda r: pp(r["delta"]) if "rate" in r["metric"] else count(r["delta"]), axis=1
    )
    print("\nAggregate headline comparison")
    print("-----------------------------")
    print(aggregate_rows[["metric", "v1_display", "v2_display", "delta_display"]].to_string(index=False))

    by_year = comparison[
        comparison["section"].eq("relabel_by_treatment_cohort_year") & comparison["metric"].eq("R_B_count")
    ].copy()
    by_year["v1_R_B_count"] = by_year["v1"].map(count)
    by_year["v2_R_B_count"] = by_year["v2"].map(count)
    by_year["delta"] = by_year["delta"].map(count)
    print("\nR_B count by treatment cohort year")
    print("----------------------------------")
    print(by_year[["group", "v1_R_B_count", "v2_R_B_count", "delta"]].to_string(index=False))

    state = comparison[comparison["section"].eq("state_level_changes")].copy()
    state["v1_R_B_rate"] = state["v1"].map(percent)
    state["v2_R_B_rate"] = state["v2"].map(percent)
    state["delta"] = state["delta"].map(pp)
    print("\nState-level R_B rate changes")
    print("----------------------------")
    print(state[["group", "v1_R_B_rate", "v2_R_B_rate", "delta"]].to_string(index=False))

    cons = consistency_v2.copy()
    print("\nV2 consistency check")
    print("--------------------")
    display = cons[[
        "metric",
        "cross_section_value",
        "muni_level_value_2008_baseline",
        "muni_level_value_rescaled_to_2006",
        "agreement_qualitative",
        "agreement_directional",
    ]].copy()
    for column in ["cross_section_value", "muni_level_value_2008_baseline", "muni_level_value_rescaled_to_2006"]:
        display[column] = display[column].map(percent)
    print(display.to_string(index=False))

    v1 = pd.read_parquet(FINAL_AGGREGATE_V1_PATH)
    v1_all = v1[v1["aggregation_level"].eq("all_treated")].iloc[0]
    v2_all = aggregate_v2[aggregate_v2["aggregation_level"].eq("all_treated")].iloc[0]
    print("\n" + "=" * 64)
    print("Decomposition Re-run with Corrected pct_bvr — Summary")
    print("=" * 64)
    print(f"Source: {INPUT_PATH.relative_to(ROOT)}")
    print("  pct_bvr backfilled for 2008, 2010, 2012 from 2014 values")
    print("\nRe-run components: Prompts 1, 4, 5 (Prompts 2, 3 unchanged)")
    print("\nHeadline changes:")
    print(
        f"  National exit:        {percent(v1_all['national_exit_rate_2008'])} → "
        f"{percent(v2_all['national_exit_rate_2008'])} (change: {pp(v2_all['national_exit_rate_2008'] - v1_all['national_exit_rate_2008'])})"
    )
    print(
        f"  National R_B:         {percent(v1_all['national_R_B_rate_2008'])} → "
        f"{percent(v2_all['national_R_B_rate_2008'])} (change: {pp(v2_all['national_R_B_rate_2008'] - v1_all['national_R_B_rate_2008'])})"
    )
    print(
        f"  National R_C:         {percent(v1_all['national_R_C_rate_2008'])} → "
        f"{percent(v2_all['national_R_C_rate_2008'])} (change: {pp(v2_all['national_R_C_rate_2008'] - v1_all['national_R_C_rate_2008'])})"
    )

    nonzero_early = aggregate_by_year(final_v2)
    early = nonzero_early[nonzero_early["year_first_any_bvr"].isin([2010, 2012])]
    print("\nEarly treatment cohorts after backfill:")
    for _, row in early.iterrows():
        print(f"  {int(row['year_first_any_bvr'])}: R_B_count={count(row['R_B_count'])}, R_B_rate={percent(row['R_B_rate_2008'])}")

    v2_good = (
        consistency_v2["agreement_qualitative"].eq("within_factor_2").all()
        and consistency_v2["agreement_directional"].eq("same_sign").all()
    )
    print("\nConsistency check status:")
    print("  V1: All three metrics within_factor_2, same_sign")
    print(f"  V2: {'All three metrics within_factor_2, same_sign' if v2_good else 'Check warnings in consistency output'}")
    print("\nFiles produced: 13 v2 parquet files under data/clean/decomposition/ plus 1 comparison file.")


def main() -> None:
    pd.set_option("display.width", 240)
    pd.set_option("display.max_columns", None)

    source = load_v2_source()
    panel_main, panel_full, residual = rebuild_panels(source)
    panel_main.to_parquet(PANEL_MAIN_V2_PATH, index=False)
    panel_full.to_parquet(PANEL_FULL_V2_PATH, index=False)
    residual.to_parquet(RESIDUAL_REPORT_V2_PATH, index=False)

    spot = panel_main[
        panel_main["year"].isin([2010, 2012])
        & panel_main["year_first_any_bvr"].eq(panel_main["year"])
    ].groupby("year", as_index=False).agg(
        municipalities=("ibge_municipality_id", "nunique"),
        mean_pct_bvr=("pct_bvr", "mean"),
        share_positive=("pct_bvr", lambda s: s.gt(0).mean()),
        imputed_share=("pct_bvr_imputed", "mean"),
    )

    progression, prediction_education, relabel_cohort, relabel_municipality = rerun_relabel(panel_main)
    progression.to_parquet(PROGRESSION_V2_PATH, index=False)
    prediction_education.to_parquet(PREDICTION_EDU_V2_PATH, index=False)
    relabel_cohort.to_parquet(RELABEL_COHORT_V2_PATH, index=False)
    relabel_municipality.to_parquet(RELABEL_MUNICIPALITY_V2_PATH, index=False)

    final, aggregate, by_cohort, consistency, map_rates, map_counts = rerun_aggregate(
        panel_main, relabel_municipality, relabel_cohort
    )
    final.to_parquet(FINAL_MUNICIPALITY_V2_PATH, index=False)
    aggregate.to_parquet(FINAL_AGGREGATE_V2_PATH, index=False)
    by_cohort.to_parquet(FINAL_BY_COHORT_V2_PATH, index=False)
    consistency.to_parquet(CONSISTENCY_V2_PATH, index=False)
    map_counts.to_parquet(MAP_COUNTS_V2_PATH, index=False)
    map_rates.to_parquet(MAP_RATES_V2_PATH, index=False)

    comparison = build_comparison(final, aggregate, consistency)
    comparison.to_parquet(COMPARISON_PATH, index=False)

    rb_by_year = aggregate_by_year(final)[["year_first_any_bvr", "municipalities", "R_B_count", "R_B_rate_2008"]]
    print("=" * 64)
    print("V2 panel spot checks")
    print("=" * 64)
    display_spot = spot.copy()
    for column in ["mean_pct_bvr", "share_positive", "imputed_share"]:
        display_spot[column] = display_spot[column].map(percent)
    print(display_spot.to_string(index=False))
    print("\nV2 R_B_count by year_first_any_bvr")
    print("----------------------------------")
    display_year = rb_by_year.copy()
    display_year["R_B_count"] = display_year["R_B_count"].map(count)
    display_year["R_B_rate_2008"] = display_year["R_B_rate_2008"].map(percent)
    print(display_year.to_string(index=False))

    print_comparison_tables(comparison, final, aggregate, consistency)

    print("\nFiles saved:")
    for path in [
        PANEL_MAIN_V2_PATH,
        PANEL_FULL_V2_PATH,
        RESIDUAL_REPORT_V2_PATH,
        PROGRESSION_V2_PATH,
        PREDICTION_EDU_V2_PATH,
        RELABEL_COHORT_V2_PATH,
        RELABEL_MUNICIPALITY_V2_PATH,
        FINAL_MUNICIPALITY_V2_PATH,
        FINAL_AGGREGATE_V2_PATH,
        FINAL_BY_COHORT_V2_PATH,
        CONSISTENCY_V2_PATH,
        MAP_COUNTS_V2_PATH,
        MAP_RATES_V2_PATH,
        COMPARISON_PATH,
    ]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
