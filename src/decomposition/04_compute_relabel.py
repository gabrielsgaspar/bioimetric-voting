from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from src.decomposition.aging_operator import AGE_COHORTS


PANEL_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_panel_main.parquet"
EXIT_COHORT_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_exit_cohort.parquet"
OUTPUT_DIR = ROOT / "data" / "clean" / "decomposition"

PROGRESSION_PATH = OUTPUT_DIR / "decomposition_progression_rates.parquet"
PREDICTION_EDU_PATH = OUTPUT_DIR / "decomposition_prediction_education.parquet"
RELABEL_COHORT_PATH = OUTPUT_DIR / "decomposition_relabel_cohort.parquet"
RELABEL_MUNICIPALITY_PATH = OUTPUT_DIR / "decomposition_relabel_municipality.parquet"

ELECTION_YEARS = [2008, 2010, 2012, 2014, 2016, 2018]
STATE_MIN_CYCLES = 100
MUNICIPALITY_MIN_CYCLES = 2
MIN_COHORT_POPULATION = 100

YOUNGER_COHORTS = {
    "16 anos",
    "17 anos",
    "18 anos",
    "19 anos",
    "20 anos",
    "21 a 24 anos",
    "25 a 29 anos",
    "30 a 34 anos",
}

CROSS_SECTION_R_B = 0.0522
CROSS_SECTION_R_C = 0.1040


def percent(value: float) -> str:
    return "NA" if pd.isna(value) else f"{100 * float(value):.2f}%"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    for path in [PANEL_PATH, EXIT_COHORT_PATH]:
        if not path.exists():
            raise FileNotFoundError(path)

    panel = pd.read_parquet(PANEL_PATH)
    exit_cohort = pd.read_parquet(EXIT_COHORT_PATH)

    required_panel = {
        "ibge_municipality_id",
        "state",
        "year",
        "age_cohort",
        "low_ed",
        "high_ed",
        "num_voters",
        "num_voters_bvr",
        "year_first_any_bvr",
        "first_regime",
    }
    required_exit = {
        "ibge_municipality_id",
        "state",
        "t",
        "t_post",
        "age_cohort",
        "N_observed_t",
        "N_predicted_no_bvr",
        "N_observed_t_post",
        "exit_count",
        "year_first_any_bvr",
        "first_regime",
    }
    missing_panel = sorted(required_panel - set(panel.columns))
    missing_exit = sorted(required_exit - set(exit_cohort.columns))
    if missing_panel:
        raise RuntimeError(f"{PANEL_PATH} missing required columns: {missing_panel}")
    if missing_exit:
        raise RuntimeError(f"{EXIT_COHORT_PATH} missing required columns: {missing_exit}")

    panel = panel.copy()
    panel["ibge_municipality_id"] = panel["ibge_municipality_id"].astype(str).str.zfill(7)
    panel["state"] = panel["state"].astype(str).str.upper().str.strip()
    panel["year"] = pd.to_numeric(panel["year"], errors="raise").astype(int)
    panel["year_first_any_bvr"] = pd.to_numeric(panel["year_first_any_bvr"], errors="raise").astype(int)
    panel["low_ed"] = pd.to_numeric(panel["low_ed"], errors="raise").astype(int)
    panel["high_ed"] = pd.to_numeric(panel["high_ed"], errors="raise").astype(int)
    panel["num_voters"] = pd.to_numeric(panel["num_voters"], errors="raise").astype("int64")
    panel["num_voters_bvr"] = pd.to_numeric(panel["num_voters_bvr"], errors="coerce").fillna(0).astype("int64")

    bad_education_flags = ~(
        ((panel["low_ed"] == 1) & (panel["high_ed"] == 0))
        | ((panel["low_ed"] == 0) & (panel["high_ed"] == 1))
    )
    if bad_education_flags.any():
        raise RuntimeError(
            f"Main panel has {int(bad_education_flags.sum()):,} rows that are not exactly one of low_ed/high_ed"
        )

    exit_cohort = exit_cohort.copy()
    exit_cohort["ibge_municipality_id"] = exit_cohort["ibge_municipality_id"].astype(str).str.zfill(7)
    exit_cohort["state"] = exit_cohort["state"].astype(str).str.upper().str.strip()
    for column in ["t", "t_post", "year_first_any_bvr"]:
        exit_cohort[column] = pd.to_numeric(exit_cohort[column], errors="raise").astype(int)
    numeric_exit = ["N_observed_t", "N_predicted_no_bvr", "N_observed_t_post", "exit_count"]
    for column in numeric_exit:
        exit_cohort[column] = pd.to_numeric(exit_cohort[column], errors="coerce")

    unexpected_age = sorted(set(panel["age_cohort"].unique()) - set(AGE_COHORTS))
    if unexpected_age:
        raise ValueError(f"Unexpected age cohorts in main panel: {unexpected_age}")
    return panel, exit_cohort


def build_education_counts(panel: pd.DataFrame) -> pd.DataFrame:
    working = panel.copy()
    working["N_low"] = working["num_voters"] * working["low_ed"]
    working["N_high"] = working["num_voters"] * working["high_ed"]
    counts = (
        working.groupby(
            ["ibge_municipality_id", "state", "year", "year_first_any_bvr", "first_regime", "age_cohort"],
            as_index=False,
        )
        .agg(
            N_low=("N_low", "sum"),
            N_high=("N_high", "sum"),
            N_total=("num_voters", "sum"),
            N_bvr=("num_voters_bvr", "sum"),
        )
        .sort_values(["ibge_municipality_id", "year", "age_cohort"])
        .reset_index(drop=True)
    )
    counts["N_low_plus_high"] = counts["N_low"] + counts["N_high"]
    inconsistent = counts["N_total"].ne(counts["N_low_plus_high"])
    if inconsistent.any():
        raise RuntimeError(
            f"Education-count aggregation has {int(inconsistent.sum()):,} cohort cells where low+high != total"
        )
    counts = counts.drop(columns="N_low_plus_high")
    counts["pi_low"] = counts["N_low"] / counts["N_total"]
    counts["b_uptake"] = counts["N_bvr"] / counts["N_total"]
    return counts


def build_progression_cycles(edu_counts: pd.DataFrame) -> pd.DataFrame:
    left = edu_counts[
        [
            "ibge_municipality_id",
            "state",
            "year",
            "year_first_any_bvr",
            "first_regime",
            "age_cohort",
            "N_low",
            "N_high",
            "N_total",
            "pi_low",
        ]
    ].copy()
    left = left.rename(
        columns={
            "year": "t",
            "N_low": "N_low_t",
            "N_high": "N_high_t",
            "N_total": "N_total_t",
            "pi_low": "pi_low_t",
        }
    )
    left["t_post"] = left["t"] + 2

    right = edu_counts[["ibge_municipality_id", "year", "age_cohort", "N_low", "N_high", "N_total", "pi_low"]].copy()
    right = right.rename(
        columns={
            "year": "t_post",
            "N_low": "N_low_t_post",
            "N_high": "N_high_t_post",
            "N_total": "N_total_t_post",
            "pi_low": "pi_low_t_post",
        }
    )

    cycles = left.merge(
        right,
        how="inner",
        on=["ibge_municipality_id", "t_post", "age_cohort"],
        validate="one_to_one",
    )
    cycles = cycles[cycles["t_post"].lt(cycles["year_first_any_bvr"])].copy()
    cycles["delta_cycle"] = cycles["pi_low_t"] - cycles["pi_low_t_post"]
    cycles["usable_for_delta"] = (
        cycles["N_total_t"].ge(MIN_COHORT_POPULATION)
        & cycles["N_total_t_post"].ge(MIN_COHORT_POPULATION)
        & cycles["pi_low_t"].notna()
        & cycles["pi_low_t_post"].notna()
    )
    cycles["delta_weight"] = cycles["N_total_t"].where(cycles["usable_for_delta"], 0.0)
    cycles["weighted_delta"] = cycles["delta_cycle"].where(cycles["usable_for_delta"], 0.0) * cycles["delta_weight"]
    return cycles


def weighted_average_from_cycles(
    frame: pd.DataFrame,
    group_cols: list[str],
    value_name: str,
    min_cycles: int | None = None,
) -> pd.DataFrame:
    usable = frame[frame["usable_for_delta"]].copy()
    grouped = (
        usable.groupby(group_cols, as_index=False)
        .agg(
            n_cycles=("delta_cycle", "size"),
            total_weight=("delta_weight", "sum"),
            weighted_delta=("weighted_delta", "sum"),
        )
    )
    grouped[value_name] = grouped["weighted_delta"] / grouped["total_weight"].replace(0, np.nan)
    if min_cycles is not None:
        grouped[f"{value_name}_threshold_met"] = grouped["n_cycles"].ge(min_cycles)
    return grouped


def estimate_progression_rates(edu_counts: pd.DataFrame, cycles: pd.DataFrame) -> pd.DataFrame:
    municipalities = (
        edu_counts[["ibge_municipality_id", "state"]]
        .drop_duplicates()
        .sort_values(["state", "ibge_municipality_id"])
        .reset_index(drop=True)
    )
    all_municipality_age = municipalities.merge(pd.DataFrame({"age_cohort": AGE_COHORTS}), how="cross")

    national = weighted_average_from_cycles(cycles, ["age_cohort"], "delta_national")
    all_age = pd.DataFrame({"age_cohort": AGE_COHORTS})
    national = all_age.merge(national[["age_cohort", "n_cycles", "total_weight", "delta_national"]], how="left", on="age_cohort")
    national = national.rename(columns={"n_cycles": "n_cycles_national", "total_weight": "total_weight_national"})
    national["n_cycles_national"] = national["n_cycles_national"].fillna(0).astype(int)
    national["total_weight_national"] = national["total_weight_national"].fillna(0.0)
    national["delta_national"] = national["delta_national"].fillna(0.0)

    state = weighted_average_from_cycles(cycles, ["state", "age_cohort"], "delta_state")
    states = pd.DataFrame({"state": sorted(edu_counts["state"].unique())})
    state = states.merge(all_age, how="cross").merge(
        state[["state", "age_cohort", "n_cycles", "total_weight", "delta_state"]],
        how="left",
        on=["state", "age_cohort"],
    )
    state = state.merge(national[["age_cohort", "delta_national"]], how="left", on="age_cohort")
    state = state.rename(columns={"n_cycles": "n_cycles_state", "total_weight": "total_weight_state"})
    state["n_cycles_state"] = state["n_cycles_state"].fillna(0).astype(int)
    state["total_weight_state"] = state["total_weight_state"].fillna(0.0)
    state["state_threshold_met"] = state["n_cycles_state"].ge(STATE_MIN_CYCLES) & state["delta_state"].notna()
    state["delta_state_used"] = np.where(state["state_threshold_met"], state["delta_state"], state["delta_national"])
    state["state_fallback_source"] = np.where(state["state_threshold_met"], "state", "national")

    municipality = weighted_average_from_cycles(
        cycles,
        ["ibge_municipality_id", "state", "age_cohort"],
        "delta_municipality",
        min_cycles=MUNICIPALITY_MIN_CYCLES,
    )
    municipality = all_municipality_age.merge(
        municipality[
            [
                "ibge_municipality_id",
                "state",
                "age_cohort",
                "n_cycles",
                "total_weight",
                "delta_municipality",
                "delta_municipality_threshold_met",
            ]
        ],
        how="left",
        on=["ibge_municipality_id", "state", "age_cohort"],
    )
    municipality = municipality.rename(columns={"n_cycles": "n_cycles_used", "total_weight": "total_weight_used"})
    municipality["n_cycles_used"] = municipality["n_cycles_used"].fillna(0).astype(int)
    municipality["total_weight_used"] = municipality["total_weight_used"].fillna(0.0)
    municipality["municipality_threshold_met"] = (
        municipality["delta_municipality_threshold_met"].eq(True) & municipality["delta_municipality"].notna()
    )
    municipality = municipality.drop(columns="delta_municipality_threshold_met")

    output = municipality.merge(
        state[
            [
                "state",
                "age_cohort",
                "delta_state",
                "delta_state_used",
                "n_cycles_state",
                "state_threshold_met",
                "state_fallback_source",
            ]
        ],
        how="left",
        on=["state", "age_cohort"],
        validate="many_to_one",
    )
    output = output.merge(national[["age_cohort", "delta_national", "n_cycles_national"]], how="left", on="age_cohort")
    output["delta_used"] = np.where(
        output["municipality_threshold_met"],
        output["delta_municipality"],
        output["delta_state_used"],
    )
    output["rate_source"] = np.select(
        [output["municipality_threshold_met"], output["state_fallback_source"].eq("state")],
        ["municipality", "state"],
        default="national",
    )
    output["delta_used"] = output["delta_used"].fillna(output["delta_national"]).fillna(0.0)
    return output[
        [
            "ibge_municipality_id",
            "state",
            "age_cohort",
            "delta_municipality",
            "delta_state",
            "delta_national",
            "delta_used",
            "n_cycles_used",
            "n_cycles_state",
            "n_cycles_national",
            "municipality_threshold_met",
            "state_threshold_met",
            "rate_source",
        ]
    ].sort_values(["ibge_municipality_id", "age_cohort"]).reset_index(drop=True)


def year_age_shares(edu_counts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    state = (
        edu_counts.groupby(["state", "year", "age_cohort"], as_index=False)
        .agg(N_low=("N_low", "sum"), N_total=("N_total", "sum"))
    )
    state["pi_low_state_year"] = state["N_low"] / state["N_total"].replace(0, np.nan)
    state = state[["state", "year", "age_cohort", "pi_low_state_year"]]

    national = (
        edu_counts.groupby(["year", "age_cohort"], as_index=False)
        .agg(N_low=("N_low", "sum"), N_total=("N_total", "sum"))
    )
    national["pi_low_national_year"] = national["N_low"] / national["N_total"].replace(0, np.nan)
    national = national[["year", "age_cohort", "pi_low_national_year"]]
    return state, national


def build_prediction_education(
    edu_counts: pd.DataFrame,
    exit_cohort: pd.DataFrame,
    progression: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    counts_t = edu_counts[
        ["ibge_municipality_id", "year", "age_cohort", "N_low", "N_high", "N_total", "pi_low"]
    ].rename(
        columns={
            "year": "t",
            "N_low": "N_low_observed_t",
            "N_high": "N_high_observed_t",
            "N_total": "N_total_observed_t",
            "pi_low": "pi_low_observed_t",
        }
    )
    counts_post = edu_counts[
        ["ibge_municipality_id", "year", "age_cohort", "N_low", "N_high", "N_total", "N_bvr", "b_uptake", "pi_low"]
    ].rename(
        columns={
            "year": "t_post",
            "N_low": "N_low_observed_t_post",
            "N_high": "N_high_observed_t_post",
            "N_total": "N_observed_total",
            "N_bvr": "N_bvr_t_post",
            "pi_low": "pi_low_observed_t_post",
        }
    )

    prediction = exit_cohort.merge(
        counts_t,
        how="left",
        on=["ibge_municipality_id", "t", "age_cohort"],
        validate="one_to_one",
    )
    prediction = prediction.merge(
        counts_post,
        how="left",
        on=["ibge_municipality_id", "t_post", "age_cohort"],
        validate="one_to_one",
    )

    count_columns = [
        "N_low_observed_t",
        "N_high_observed_t",
        "N_total_observed_t",
        "N_low_observed_t_post",
        "N_high_observed_t_post",
        "N_observed_total",
        "N_bvr_t_post",
    ]
    prediction[count_columns] = prediction[count_columns].fillna(0.0)

    state_shares, national_shares = year_age_shares(edu_counts)
    prediction = prediction.merge(
        state_shares.rename(columns={"year": "t"}),
        how="left",
        on=["state", "t", "age_cohort"],
        validate="many_to_one",
    )
    prediction = prediction.merge(
        national_shares.rename(columns={"year": "t"}),
        how="left",
        on=["t", "age_cohort"],
        validate="many_to_one",
    )
    prediction["pi_low_t_source"] = np.select(
        [
            prediction["N_total_observed_t"].gt(0),
            prediction["pi_low_state_year"].notna(),
        ],
        ["municipality", "state_year"],
        default="national_year",
    )
    prediction["pi_low_t"] = np.select(
        [
            prediction["N_total_observed_t"].gt(0),
            prediction["pi_low_state_year"].notna(),
        ],
        [prediction["pi_low_observed_t"], prediction["pi_low_state_year"]],
        default=prediction["pi_low_national_year"],
    )
    missing_pi = prediction["pi_low_t"].isna().sum()
    if missing_pi:
        raise RuntimeError(f"Missing pi_low_t for {int(missing_pi):,} prediction rows")

    prediction = prediction.merge(
        progression[["ibge_municipality_id", "state", "age_cohort", "delta_used", "rate_source"]],
        how="left",
        on=["ibge_municipality_id", "state", "age_cohort"],
        validate="many_to_one",
    )
    if prediction["delta_used"].isna().any():
        raise RuntimeError(f"Missing progression delta for {int(prediction['delta_used'].isna().sum()):,} rows")

    prediction["pi_low_predicted_raw"] = prediction["pi_low_t"] - prediction["delta_used"]
    prediction["pi_low_predicted_t_post"] = prediction["pi_low_predicted_raw"].clip(lower=0.0, upper=1.0)
    prediction["N_predicted_total"] = prediction["N_predicted_no_bvr"]
    prediction["N_low_predicted_t_post"] = prediction["N_predicted_total"] * prediction["pi_low_predicted_t_post"]
    prediction["N_high_predicted_t_post"] = prediction["N_predicted_total"] - prediction["N_low_predicted_t_post"]
    prediction["pi_low_observed_t_post"] = np.where(
        prediction["N_observed_total"].gt(0),
        prediction["N_low_observed_t_post"] / prediction["N_observed_total"],
        np.nan,
    )
    prediction["b_uptake"] = np.where(
        prediction["N_observed_total"].gt(0),
        prediction["N_bvr_t_post"] / prediction["N_observed_total"],
        0.0,
    )

    diagnostics = {
        "pi_low_clipped_low": int(prediction["pi_low_predicted_raw"].lt(0).sum()),
        "pi_low_clipped_high": int(prediction["pi_low_predicted_raw"].gt(1).sum()),
        "pi_low_t_from_fallback": int((~prediction["pi_low_t_source"].eq("municipality")).sum()),
    }
    output = prediction[
        [
            "ibge_municipality_id",
            "state",
            "t",
            "t_post",
            "age_cohort",
            "N_low_observed_t",
            "N_high_observed_t",
            "N_low_predicted_t_post",
            "N_high_predicted_t_post",
            "N_low_observed_t_post",
            "N_high_observed_t_post",
            "N_predicted_total",
            "exit_count",
            "pi_low_t",
            "pi_low_predicted_t_post",
            "pi_low_observed_t_post",
            "delta_used",
            "N_observed_total",
            "b_uptake",
            "pi_low_t_source",
            "rate_source",
        ]
    ].copy()
    return output, diagnostics


def compute_relabel_cohort(prediction: pd.DataFrame, exit_cohort: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    relabel = prediction.merge(
        exit_cohort[
            [
                "ibge_municipality_id",
                "state",
                "t",
                "t_post",
                "age_cohort",
                "year_first_any_bvr",
                "first_regime",
            ]
        ],
        how="left",
        on=["ibge_municipality_id", "state", "t", "t_post", "age_cohort"],
        validate="one_to_one",
    )

    relabel["E_low_B"] = relabel["exit_count"]
    relabel["E_low_C"] = relabel["exit_count"] * relabel["pi_low_t"]
    relabel["R_B_unfloored"] = relabel["N_low_predicted_t_post"] - relabel["N_low_observed_t_post"] - relabel["E_low_B"]
    relabel["R_C_unfloored"] = relabel["N_low_predicted_t_post"] - relabel["N_low_observed_t_post"] - relabel["E_low_C"]
    relabel["R_B_raw"] = relabel["R_B_unfloored"].clip(lower=0.0)
    relabel["R_C_raw"] = relabel["R_C_unfloored"].clip(lower=0.0)

    relabel["R_max_b"] = relabel["b_uptake"].clip(lower=0.0, upper=1.0) * relabel["N_observed_total"]
    relabel["R_B_bounded"] = np.minimum(relabel["R_B_raw"], relabel["R_max_b"])
    relabel["R_C_bounded"] = np.minimum(relabel["R_C_raw"], relabel["R_max_b"])
    relabel["bound_binds_B"] = relabel["R_B_raw"].gt(relabel["R_max_b"] + 1e-9)
    relabel["bound_binds_C"] = relabel["R_C_raw"].gt(relabel["R_max_b"] + 1e-9)

    diagnostics = {
        "negative_raw_B": int(relabel["R_B_unfloored"].lt(0).sum()),
        "negative_raw_C": int(relabel["R_C_unfloored"].lt(0).sum()),
        "R_B_raw_exceeds_observed": int(relabel["R_B_raw"].gt(relabel["N_observed_total"] + 1e-9).sum()),
        "R_C_raw_exceeds_observed": int(relabel["R_C_raw"].gt(relabel["N_observed_total"] + 1e-9).sum()),
        "R_C_less_than_R_B": int(relabel["R_C_raw"].lt(relabel["R_B_raw"] - 1e-9).sum()),
    }
    bad_bounded = (
        relabel["R_B_bounded"].gt(relabel["N_observed_total"] + 1e-9)
        | relabel["R_C_bounded"].gt(relabel["N_observed_total"] + 1e-9)
    ).sum()
    if bad_bounded:
        raise RuntimeError(f"Bounded re-labeling exceeds observed cohort total for {int(bad_bounded):,} rows")

    return relabel[
        [
            "ibge_municipality_id",
            "state",
            "t",
            "t_post",
            "age_cohort",
            "year_first_any_bvr",
            "first_regime",
            "R_B_raw",
            "R_B_bounded",
            "R_C_raw",
            "R_C_bounded",
            "R_max_b",
            "b_uptake",
            "bound_binds_B",
            "bound_binds_C",
            "exit_count",
            "N_predicted_total",
            "N_observed_total",
            "R_B_unfloored",
            "R_C_unfloored",
        ]
    ].sort_values(["t_post", "state", "ibge_municipality_id", "age_cohort"]).reset_index(drop=True), diagnostics


def aggregate_relabel_municipality(relabel: pd.DataFrame) -> pd.DataFrame:
    working = relabel.copy()
    working["is_younger"] = working["age_cohort"].isin(YOUNGER_COHORTS)
    working["R_B_younger_component"] = np.where(working["is_younger"], working["R_B_bounded"], 0.0)
    working["R_B_older_component"] = np.where(~working["is_younger"], working["R_B_bounded"], 0.0)
    working["R_C_younger_component"] = np.where(working["is_younger"], working["R_C_bounded"], 0.0)
    working["R_C_older_component"] = np.where(~working["is_younger"], working["R_C_bounded"], 0.0)
    working["cohort_has_relabel"] = working["R_B_bounded"].gt(0) | working["R_C_bounded"].gt(0)

    grouped = (
        working.groupby(["ibge_municipality_id", "state", "t_post", "year_first_any_bvr", "first_regime"], as_index=False)
        .agg(
            R_B_total=("R_B_bounded", "sum"),
            R_C_total=("R_C_bounded", "sum"),
            R_B_younger=("R_B_younger_component", "sum"),
            R_B_older=("R_B_older_component", "sum"),
            R_C_younger=("R_C_younger_component", "sum"),
            R_C_older=("R_C_older_component", "sum"),
            N_observed_total=("N_observed_total", "sum"),
            n_cohorts_with_relabel=("cohort_has_relabel", "sum"),
            n_cohorts_bound_binds_B=("bound_binds_B", "sum"),
            n_cohorts_bound_binds_C=("bound_binds_C", "sum"),
        )
    )
    grouped["R_rate_B_total"] = grouped["R_B_total"] / grouped["N_observed_total"].replace(0, np.nan)
    grouped["R_rate_C_total"] = grouped["R_C_total"] / grouped["N_observed_total"].replace(0, np.nan)
    return grouped[
        [
            "ibge_municipality_id",
            "state",
            "t_post",
            "year_first_any_bvr",
            "first_regime",
            "R_B_total",
            "R_C_total",
            "R_rate_B_total",
            "R_rate_C_total",
            "R_B_younger",
            "R_B_older",
            "R_C_younger",
            "R_C_older",
            "N_observed_total",
            "n_cohorts_with_relabel",
            "n_cohorts_bound_binds_B",
            "n_cohorts_bound_binds_C",
        ]
    ].sort_values(["t_post", "state", "ibge_municipality_id"]).reset_index(drop=True)


def format_rate_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    output = frame.copy()
    for column in columns:
        if column in output.columns:
            output[column] = output[column].map(percent)
    return output


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


def relabel_summary(municipality: pd.DataFrame) -> pd.DataFrame:
    return (
        municipality.groupby("first_regime", as_index=False)
        .agg(
            municipalities=("ibge_municipality_id", "nunique"),
            mean_R_rate_B=("R_rate_B_total", "mean"),
            mean_R_rate_C=("R_rate_C_total", "mean"),
            total_R_B=("R_B_total", "sum"),
            total_R_C=("R_C_total", "sum"),
            total_observed=("N_observed_total", "sum"),
        )
        .sort_values("first_regime")
    )


def cohort_distribution(relabel: pd.DataFrame) -> pd.DataFrame:
    return (
        relabel.groupby(["first_regime", "age_cohort"], as_index=False)
        .agg(
            mean_R_B=("R_B_bounded", "mean"),
            mean_R_C=("R_C_bounded", "mean"),
            mean_b_uptake=("b_uptake", "mean"),
            rows=("age_cohort", "size"),
            bound_binds_B=("bound_binds_B", "sum"),
            bound_binds_C=("bound_binds_C", "sum"),
        )
        .sort_values(["first_regime", "age_cohort"])
    )


def comparison_to_cross_section(municipality: pd.DataFrame) -> pd.DataFrame:
    by_year = (
        municipality.groupby("year_first_any_bvr", as_index=False)
        .agg(
            municipalities=("ibge_municipality_id", "nunique"),
            mean_R_rate_B=("R_rate_B_total", "mean"),
            mean_R_rate_C=("R_rate_C_total", "mean"),
        )
        .sort_values("year_first_any_bvr")
    )
    by_year["R_B_vs_cross_section"] = by_year["mean_R_rate_B"] - CROSS_SECTION_R_B
    by_year["R_C_vs_cross_section"] = by_year["mean_R_rate_C"] - CROSS_SECTION_R_C
    return by_year


def main() -> None:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)

    panel, exit_cohort = load_inputs()
    edu_counts = build_education_counts(panel)
    progression_cycles = build_progression_cycles(edu_counts)
    progression = estimate_progression_rates(edu_counts, progression_cycles)
    prediction_education, prediction_diagnostics = build_prediction_education(edu_counts, exit_cohort, progression)
    relabel_cohort, relabel_diagnostics = compute_relabel_cohort(prediction_education, exit_cohort)
    relabel_municipality = aggregate_relabel_municipality(relabel_cohort)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    progression.to_parquet(PROGRESSION_PATH, index=False)
    prediction_education.to_parquet(PREDICTION_EDU_PATH, index=False)
    relabel_cohort.to_parquet(RELABEL_COHORT_PATH, index=False)
    relabel_municipality.to_parquet(RELABEL_MUNICIPALITY_PATH, index=False)

    summary = relabel_summary(relabel_municipality)
    summary_rates = format_rate_columns(summary, ["mean_R_rate_B", "mean_R_rate_C"])

    strict = relabel_municipality[relabel_municipality["first_regime"].eq("strict")].copy()
    strict_younger_B = strict["R_B_younger"].sum() / strict["N_observed_total"].sum()
    strict_older_B = strict["R_B_older"].sum() / strict["N_observed_total"].sum()

    cohort_dist = cohort_distribution(relabel_cohort)
    strict_cohort = cohort_dist[cohort_dist["first_regime"].eq("strict")][
        ["age_cohort", "mean_R_B", "mean_R_C", "mean_b_uptake", "rows", "bound_binds_B", "bound_binds_C"]
    ].copy()

    total_cells = len(relabel_cohort)
    bound_B_share = relabel_cohort["bound_binds_B"].mean()
    bound_C_share = relabel_cohort["bound_binds_C"].mean()
    bound_by_regime = (
        relabel_cohort.groupby("first_regime", as_index=False)
        .agg(
            cells=("age_cohort", "size"),
            B_bind_share=("bound_binds_B", "mean"),
            C_bind_share=("bound_binds_C", "mean"),
        )
        .sort_values("first_regime")
    )
    high_bind_munis = relabel_municipality[
        (relabel_municipality["n_cohorts_bound_binds_B"] > len(AGE_COHORTS) / 2)
        | (relabel_municipality["n_cohorts_bound_binds_C"] > len(AGE_COHORTS) / 2)
    ]

    comparison = comparison_to_cross_section(relabel_municipality)
    overall_B = relabel_municipality["R_rate_B_total"].mean()
    direction = "same sign" if overall_B >= 0 and CROSS_SECTION_R_B >= 0 else "different sign"
    factor = max(overall_B, CROSS_SECTION_R_B) / max(min(overall_B, CROSS_SECTION_R_B), 1e-12)
    order = "within factor of 2" if factor <= 2 else "within factor of 3" if factor <= 3 else "different order of magnitude"

    anomalies: list[str] = []
    if relabel_diagnostics["R_B_raw_exceeds_observed"] or relabel_diagnostics["R_C_raw_exceeds_observed"]:
        anomalies.append(
            "unbounded re-labeling exceeds observed cohort total in "
            f"{relabel_diagnostics['R_B_raw_exceeds_observed']:,} Scenario B cells and "
            f"{relabel_diagnostics['R_C_raw_exceeds_observed']:,} Scenario C cells; bounded estimates are capped by pct_bvr"
        )
    if relabel_diagnostics["R_C_less_than_R_B"]:
        anomalies.append(f"Scenario C is below Scenario B in {relabel_diagnostics['R_C_less_than_R_B']:,} cells")
    strict_bind_B = bound_by_regime.loc[bound_by_regime["first_regime"].eq("strict"), "B_bind_share"]
    if not strict_bind_B.empty and strict_bind_B.iloc[0] > 0.30:
        anomalies.append("strict-first bound-binding rate under Scenario B exceeds 30%")

    print("=" * 64)
    print("RE-LABELING IDENTIFICATION SUMMARY")
    print("=" * 64)
    print(f"Treated municipalities processed: {relabel_municipality['ibge_municipality_id'].nunique():,}")

    print_table("Average re-labeling rate at adoption by first_regime", summary_rates)
    print("\nAverage re-labeling by age range (strict-first, Scenario B):")
    print(f"  Younger cohorts (16-34): {percent(strict_younger_B)} of strict t-period electorate")
    print(f"  Older cohorts (35+): {percent(strict_older_B)} of strict t-period electorate")

    strict_cohort_display = strict_cohort.copy()
    strict_cohort_display = format_rate_columns(strict_cohort_display, ["mean_b_uptake"])
    print_table("Average bounded re-labeling by age cohort, strict-first municipalities", strict_cohort_display)

    bound_display = format_rate_columns(bound_by_regime, ["B_bind_share", "C_bind_share"])
    print("\nBound-binding cells:")
    print(f"  Scenario B: {percent(bound_B_share)} of cohort cells ({int(relabel_cohort['bound_binds_B'].sum()):,}/{total_cells:,})")
    print(f"  Scenario C: {percent(bound_C_share)} of cohort cells ({int(relabel_cohort['bound_binds_C'].sum()):,}/{total_cells:,})")
    print_table("Bound-binding by first_regime", bound_display)
    print(f"  Municipalities where either bound binds in more than half the cohorts: {len(high_bind_munis):,}")

    comparison_display = format_rate_columns(
        comparison,
        ["mean_R_rate_B", "mean_R_rate_C", "R_B_vs_cross_section", "R_C_vs_cross_section"],
    )
    print_table("Comparison to cross-section re-labeling benchmarks by adoption year", comparison_display)

    print("\nComparison to cross-section national bounds:")
    print("  Scenario B (cross-section): 5.22% of 2006 baseline")
    print(f"  Scenario B (municipality-level, this analysis): {percent(overall_B)} of t-period electorate")
    print(f"  Direction agreement: {direction}")
    print(f"  Order of magnitude: {order}")

    print("\nDiagnostics:")
    print(f"  Pre-treatment progression cycles available: {len(progression_cycles):,}")
    print(f"  Progression cycles meeting population threshold: {int(progression_cycles['usable_for_delta'].sum()):,}")
    print(f"  pi_low predictions clipped below 0: {prediction_diagnostics['pi_low_clipped_low']:,}")
    print(f"  pi_low predictions clipped above 1: {prediction_diagnostics['pi_low_clipped_high']:,}")
    print(f"  Negative Scenario B raw values floored to zero: {relabel_diagnostics['negative_raw_B']:,}")
    print(f"  Negative Scenario C raw values floored to zero: {relabel_diagnostics['negative_raw_C']:,}")
    print(f"  Anomalies flagged: {len(anomalies)}")
    for anomaly in anomalies:
        print(f"    - {anomaly}")

    print("\nFiles saved:")
    print(f"  {PROGRESSION_PATH.relative_to(ROOT)}")
    print(f"  {PREDICTION_EDU_PATH.relative_to(ROOT)}")
    print(f"  {RELABEL_COHORT_PATH.relative_to(ROOT)}")
    print(f"  {RELABEL_MUNICIPALITY_PATH.relative_to(ROOT)}")
    print("\nReady for aggregation and final consistency check in Prompt 5.")


if __name__ == "__main__":
    main()
