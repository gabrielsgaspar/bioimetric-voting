from __future__ import annotations

import math
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from src.cleaning.parse_tse_eleitorado import map_education


SOURCE_CANDIDATES = [
    ROOT / "data" / "clean" / "decomposition" / "decomposition_data.parquet",
    ROOT / "data" / "raw" / "decomposition_data.parquet",
    ROOT / "decomposition_data.parquet",
]
OUTPUT_DIR = ROOT / "data" / "clean" / "decomposition"
MAIN_PANEL_PATH = OUTPUT_DIR / "decomposition_panel_main.parquet"
FULL_PANEL_PATH = OUTPUT_DIR / "decomposition_panel_full.parquet"
RESIDUAL_REPORT_PATH = OUTPUT_DIR / "decomposition_residual_report.parquet"

EXPECTED_YEARS = {2008, 2010, 2012, 2014, 2016, 2018}
EXPECTED_FIRST_YEARS = EXPECTED_YEARS | {9999}
LOW_ED_MAIN_CATEGORIES = {"illiterate", "reads_and_writes", "incomplete_primary", "complete_primary"}
HIGH_ED_MAIN_CATEGORIES = {"incomplete_secondary", "complete_secondary", "incomplete_higher", "complete_higher"}

REQUIRED_COLUMNS = [
    "year",
    "ibge_municipality_id",
    "state",
    "age_cohort",
    "education",
    "low_ed",
    "high_ed",
    "num_voters",
    "num_voters_bvr",
    "pct_bvr",
    "bvr_status",
    "year_first_any_bvr",
    "year_first_strict_bvr",
    "year_first_hybrid_bvr",
]

OUTPUT_COLUMNS = [
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
    "bvr_status",
    "year_first_any_bvr",
    "year_first_strict_bvr",
    "year_first_hybrid_bvr",
    "first_regime",
    "event_time",
]

AGE_ORDER = [
    "16 anos",
    "17 anos",
    "18 anos",
    "19 anos",
    "20 anos",
    "21 a 24 anos",
    "25 a 29 anos",
    "30 a 34 anos",
    "35 a 39 anos",
    "40 a 44 anos",
    "45 a 49 anos",
    "50 a 54 anos",
    "55 a 59 anos",
    "60 a 64 anos",
    "65 a 69 anos",
    "70 a 74 anos",
    "75 a 79 anos",
    "80 a 84 anos",
    "85 a 89 anos",
    "90 a 94 anos",
    "95 a 99 anos",
    "100 anos ou mais",
]
OLDER_AGE_COHORTS = set(AGE_ORDER[8:])


def normalize_label(value: object) -> str:
    text = "" if value is None else str(value).strip().lower()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def find_source_path() -> Path:
    for path in SOURCE_CANDIDATES:
        if path.exists():
            return path
    searched = "\n".join(f"  - {path}" for path in SOURCE_CANDIDATES)
    raise FileNotFoundError(f"Could not find decomposition_data.parquet. Searched:\n{searched}")


def percent(value: float | int | pd.NA) -> str:
    if pd.isna(value):
        return "NA"
    return f"{100 * float(value):.3f}%"


def pct_change(current: pd.Series, previous: pd.Series) -> pd.Series:
    return (current - previous) / previous.replace(0, np.nan)


def load_data() -> tuple[pd.DataFrame, Path]:
    source_path = find_source_path()
    df = pd.read_parquet(source_path)
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise RuntimeError(f"{source_path} is missing required columns: {missing}")

    df = df.copy()
    df["ibge_municipality_id"] = df["ibge_municipality_id"].astype(str).str.zfill(7)
    df["state"] = df["state"].astype(str).str.upper().str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    for column in ["year_first_any_bvr", "year_first_strict_bvr", "year_first_hybrid_bvr"]:
        df[column] = pd.to_numeric(df[column], errors="raise").astype(int)
    for column in ["low_ed", "high_ed", "num_voters", "num_voters_bvr"]:
        df[column] = pd.to_numeric(df[column], errors="raise")
    df["low_ed"] = df["low_ed"].astype(int)
    df["high_ed"] = df["high_ed"].astype(int)
    df["num_voters"] = df["num_voters"].astype("int64")
    df["num_voters_bvr"] = df["num_voters_bvr"].astype("int64")
    df["pct_bvr"] = pd.to_numeric(df["pct_bvr"], errors="coerce")
    return df, source_path


def verify_low_high_interpretation(df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    mapped = df["education"].map(map_education)
    expected_low = mapped.isin(LOW_ED_MAIN_CATEGORIES)
    expected_high = mapped.isin(HIGH_ED_MAIN_CATEGORIES)

    low_sum = int(df["low_ed"].sum())
    high_sum = int(df["high_ed"].sum())
    low_row_count = int(expected_low.sum())
    high_row_count = int(expected_high.sum())
    low_voter_total = int(df.loc[expected_low, "num_voters"].sum())
    high_voter_total = int(df.loc[expected_high, "num_voters"].sum())
    equals_counts = bool((df["num_voters"] == df["low_ed"] + df["high_ed"]).all())
    binary_values = set(df["low_ed"].dropna().unique()) <= {0, 1} and set(df["high_ed"].dropna().unique()) <= {0, 1}
    matches_mapping = bool((df["low_ed"].eq(expected_low.astype(int))).all()) and bool(
        (df["high_ed"].eq(expected_high.astype(int))).all()
    )

    if binary_values and matches_mapping and low_sum == low_row_count and high_sum == high_row_count:
        interpretation = "indicator flags"
    elif equals_counts or low_sum == low_voter_total or high_sum == high_voter_total:
        interpretation = "separate counts"
    else:
        interpretation = "ambiguous"

    checks = pd.DataFrame(
        [
            {"check": "sum(low_ed)", "value": low_sum},
            {"check": "low-ed row count from main mapping", "value": low_row_count},
            {"check": "low-ed voter count from main mapping", "value": low_voter_total},
            {"check": "sum(high_ed)", "value": high_sum},
            {"check": "high-ed row count from main mapping", "value": high_row_count},
            {"check": "high-ed voter count from main mapping", "value": high_voter_total},
            {"check": "num_voters always equals low_ed + high_ed", "value": equals_counts},
            {"check": "flags are binary and match main mapping", "value": matches_mapping},
        ]
    )
    return interpretation, checks


def first_treatment_checks(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int], pd.DataFrame, list[str]]:
    severe_issues: list[str] = []
    first_columns = ["year_first_any_bvr", "year_first_strict_bvr", "year_first_hybrid_bvr"]
    first_values = {column: sorted(df[column].dropna().unique().tolist()) for column in first_columns}
    for column, values in first_values.items():
        unexpected = sorted(set(values) - EXPECTED_FIRST_YEARS)
        if unexpected:
            severe_issues.append(f"{column} has unexpected values: {unexpected}")

    strict = df["year_first_strict_bvr"].replace(9999, np.nan)
    hybrid = df["year_first_hybrid_bvr"].replace(9999, np.nan)
    computed_any = pd.concat([strict, hybrid], axis=1).min(axis=1).fillna(9999).astype(int)
    min_mismatches = int(df["year_first_any_bvr"].ne(computed_any).sum())
    if min_mismatches:
        severe_issues.append(
            f"year_first_any_bvr differs from min(strict, hybrid) in {min_mismatches:,} rows"
        )

    constant_counts = (
        df.groupby("ibge_municipality_id")[first_columns]
        .nunique(dropna=False)
        .gt(1)
        .sum()
        .astype(int)
        .to_dict()
    )
    for column, count in constant_counts.items():
        if count:
            severe_issues.append(f"{column} varies within {count:,} municipalities")

    muni_year_status = df[["ibge_municipality_id", "year", "bvr_status"]].drop_duplicates()
    status_duplicates = int(muni_year_status.duplicated(["ibge_municipality_id", "year"]).sum())
    if status_duplicates:
        severe_issues.append(f"bvr_status is not unique in {status_duplicates:,} municipality-years")

    muni_timing = (
        df.groupby("ibge_municipality_id", as_index=False)
        .agg(
            year_first_any_bvr=("year_first_any_bvr", "first"),
            year_first_strict_bvr=("year_first_strict_bvr", "first"),
            year_first_hybrid_bvr=("year_first_hybrid_bvr", "first"),
        )
    )
    treated = muni_timing[muni_timing["year_first_any_bvr"].ne(9999)][
        ["ibge_municipality_id", "year_first_any_bvr"]
    ].rename(columns={"year_first_any_bvr": "year"})
    first_status = treated.merge(muni_year_status, how="left", on=["ibge_municipality_id", "year"])
    missing_first_status = int(first_status["bvr_status"].isna().sum())
    if missing_first_status:
        severe_issues.append(f"Missing first-treatment-year bvr_status for {missing_first_status:,} municipalities")
    first_status_bad = first_status["bvr_status"].eq("no_bvr").sum()
    if first_status_bad:
        severe_issues.append(f"{first_status_bad:,} treated municipalities have no_bvr at first treatment year")

    first_status["first_regime"] = first_status["bvr_status"].map({"strict_bvr": "strict", "hybrid_bvr": "hybrid"})
    regime_map = first_status[["ibge_municipality_id", "first_regime"]]
    muni_timing = muni_timing.merge(regime_map, how="left", on="ibge_municipality_id")
    muni_timing["first_regime"] = muni_timing["first_regime"].fillna("never_treated")

    cohort_breakdown = (
        muni_timing.groupby(["year_first_any_bvr", "first_regime"], as_index=False)
        .agg(municipalities=("ibge_municipality_id", "nunique"))
        .sort_values(["year_first_any_bvr", "first_regime"])
    )
    return cohort_breakdown, constant_counts, pd.DataFrame({"column": first_values.keys(), "values": first_values.values()}), severe_issues


def attach_first_regime(df: pd.DataFrame) -> pd.DataFrame:
    muni_year_status = df[["ibge_municipality_id", "year", "bvr_status"]].drop_duplicates()
    muni_timing = (
        df.groupby("ibge_municipality_id", as_index=False)
        .agg(year_first_any_bvr=("year_first_any_bvr", "first"))
    )
    treated = muni_timing[muni_timing["year_first_any_bvr"].ne(9999)][
        ["ibge_municipality_id", "year_first_any_bvr"]
    ].rename(columns={"year_first_any_bvr": "year"})
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


def share_tables(df: pd.DataFrame, flag: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    totals = df.groupby(["year", "state"], as_index=False).agg(total_voters=("num_voters", "sum"))
    flagged = (
        df.loc[flag]
        .groupby(["year", "state"], as_index=False)
        .agg(flagged_voters=("num_voters", "sum"))
    )
    state = totals.merge(flagged, how="left", on=["year", "state"])
    state["flagged_voters"] = state["flagged_voters"].fillna(0).astype("int64")
    state["share"] = state["flagged_voters"] / state["total_voters"]

    national_totals = df.groupby("year", as_index=False).agg(total_voters=("num_voters", "sum"))
    national_flagged = df.loc[flag].groupby("year", as_index=False).agg(flagged_voters=("num_voters", "sum"))
    national = national_totals.merge(national_flagged, how="left", on="year")
    national["flagged_voters"] = national["flagged_voters"].fillna(0).astype("int64")
    national["share"] = national["flagged_voters"] / national["total_voters"]

    idx_max = state.groupby("year")["share"].idxmax()
    idx_min = state.groupby("year")["share"].idxmin()
    max_by_year = state.loc[idx_max, ["year", "state", "share"]].rename(
        columns={"state": "max_state", "share": "max_share"}
    )
    min_by_year = state.loc[idx_min, ["year", "state", "share"]].rename(
        columns={"state": "min_state", "share": "min_share"}
    )
    yearly = national.merge(max_by_year, on="year").merge(min_by_year, on="year")
    overall = pd.Series(
        {
            "national_share": df.loc[flag, "num_voters"].sum() / df["num_voters"].sum(),
            "max_state_year": state.loc[state["share"].idxmax(), "year"],
            "max_state": state.loc[state["share"].idxmax(), "state"],
            "max_state_share": state["share"].max(),
            "min_state_year": state.loc[state["share"].idxmin(), "year"],
            "min_state": state.loc[state["share"].idxmin(), "state"],
            "min_state_share": state["share"].min(),
            "state_years_over_1pct": int(state["share"].gt(0.01).sum()),
            "state_years_over_5pct": int(state["share"].ge(0.05).sum()),
        }
    )
    return yearly, state, overall


def zero_cell_diagnostics(df: pd.DataFrame, invalid_age: pd.Series) -> tuple[pd.DataFrame, dict[str, float]]:
    municipality_years = df[["ibge_municipality_id", "year"]].drop_duplicates()
    n_municipality_years = len(municipality_years)
    n_age_full = df["age_cohort"].nunique()
    n_education = df["education"].nunique()
    n_age_substantive = df.loc[~invalid_age, "age_cohort"].nunique()

    explicit_total = len(df)
    explicit_positive = int(df["num_voters"].gt(0).sum())
    explicit_zero = int(df["num_voters"].eq(0).sum())
    expected_full_grid = n_municipality_years * n_age_full * n_education
    expected_substantive_grid = n_municipality_years * n_age_substantive * n_education
    observed_substantive = int((~invalid_age).sum())

    cells_per_my_full = df.groupby(["ibge_municipality_id", "year"]).size()
    cells_per_my_substantive = df.loc[~invalid_age].groupby(["ibge_municipality_id", "year"]).size()
    distribution = pd.DataFrame(
        [
            {
                "panel": "full including residual age",
                "mean_populated_cells": cells_per_my_full.mean(),
                "sd": cells_per_my_full.std(),
                "min": cells_per_my_full.min(),
                "p25": cells_per_my_full.quantile(0.25),
                "median": cells_per_my_full.median(),
                "p75": cells_per_my_full.quantile(0.75),
                "max": cells_per_my_full.max(),
                "possible_cells": n_age_full * n_education,
            },
            {
                "panel": "substantive ages only",
                "mean_populated_cells": cells_per_my_substantive.mean(),
                "sd": cells_per_my_substantive.std(),
                "min": cells_per_my_substantive.min(),
                "p25": cells_per_my_substantive.quantile(0.25),
                "median": cells_per_my_substantive.median(),
                "p75": cells_per_my_substantive.quantile(0.75),
                "max": cells_per_my_substantive.max(),
                "possible_cells": n_age_substantive * n_education,
            },
        ]
    )
    summary = {
        "municipality_years": n_municipality_years,
        "explicit_total_cells": explicit_total,
        "explicit_positive_cells": explicit_positive,
        "explicit_zero_cells": explicit_zero,
        "expected_full_grid_cells": expected_full_grid,
        "implied_missing_zero_cells_full_grid": expected_full_grid - explicit_total,
        "expected_substantive_grid_cells": expected_substantive_grid,
        "implied_missing_zero_cells_substantive_grid": expected_substantive_grid - observed_substantive,
    }
    return distribution, summary


def sample_municipalities_for_diagnostics(full_panel: pd.DataFrame, n: int = 100) -> list[str]:
    latest_year = int(full_panel["year"].max())
    municipality = (
        full_panel[full_panel["year"].eq(latest_year)]
        .groupby("ibge_municipality_id", as_index=False)
        .agg(total_voters_latest=("num_voters", "sum"), first_regime=("first_regime", "first"))
    )
    municipality["size_bucket"] = pd.qcut(
        municipality["total_voters_latest"],
        q=3,
        labels=["small", "medium", "large"],
        duplicates="drop",
    )
    strata = list(municipality.groupby(["first_regime", "size_bucket"], observed=True))
    n_per_stratum = max(1, math.ceil(n / max(1, len(strata))))
    pieces = []
    for index, (_, group) in enumerate(strata):
        pieces.append(group.sample(n=min(n_per_stratum, len(group)), random_state=20260430 + index))
    sample = pd.concat(pieces, ignore_index=True).drop_duplicates("ibge_municipality_id")
    if len(sample) < n:
        remaining = municipality[~municipality["ibge_municipality_id"].isin(sample["ibge_municipality_id"])]
        top_up = remaining.sample(n=min(n - len(sample), len(remaining)), random_state=20260430)
        sample = pd.concat([sample, top_up], ignore_index=True)
    if len(sample) > n:
        sample = sample.sample(n=n, random_state=20260430)
    return sample["ibge_municipality_id"].tolist()


def within_municipality_diagnostics(full_panel: pd.DataFrame) -> dict[str, object]:
    sample_ids = sample_municipalities_for_diagnostics(full_panel, n=100)
    sample_panel = full_panel[full_panel["ibge_municipality_id"].isin(sample_ids)].copy()

    totals = (
        sample_panel.groupby(["ibge_municipality_id", "year"], as_index=False)
        .agg(
            total_voters=("num_voters", "sum"),
            total_voters_bvr=("num_voters_bvr", "sum"),
            year_first_any_bvr=("year_first_any_bvr", "first"),
            bvr_status=("bvr_status", "first"),
            first_regime=("first_regime", "first"),
        )
        .sort_values(["ibge_municipality_id", "year"])
    )
    totals["previous_total_voters"] = totals.groupby("ibge_municipality_id")["total_voters"].shift()
    totals["pct_change_total_voters"] = pct_change(totals["total_voters"], totals["previous_total_voters"])
    totals["adoption_transition"] = totals["year"].eq(totals["year_first_any_bvr"])
    total_drop_anomalies = totals[
        totals["pct_change_total_voters"].le(-0.30) & ~totals["adoption_transition"].fillna(False)
    ].copy()

    age_totals = (
        sample_panel.groupby(["ibge_municipality_id", "year", "age_cohort"], as_index=False)
        .agg(
            age_voters=("num_voters", "sum"),
            year_first_any_bvr=("year_first_any_bvr", "first"),
            first_regime=("first_regime", "first"),
        )
        .sort_values(["ibge_municipality_id", "age_cohort", "year"])
    )
    age_totals["previous_age_voters"] = age_totals.groupby(["ibge_municipality_id", "age_cohort"])[
        "age_voters"
    ].shift()
    age_totals["pct_change_age_voters"] = pct_change(age_totals["age_voters"], age_totals["previous_age_voters"])
    age_totals["older_cohort"] = age_totals["age_cohort"].isin(OLDER_AGE_COHORTS)
    age_totals["adoption_transition"] = age_totals["year"].eq(age_totals["year_first_any_bvr"])
    age_growth_anomalies = age_totals[
        age_totals["older_cohort"]
        & age_totals["previous_age_voters"].ge(100)
        & age_totals["pct_change_age_voters"].gt(1.00)
        & ~age_totals["adoption_transition"].fillna(False)
    ].copy()

    bvr_by_year = (
        full_panel.groupby("year", as_index=False)
        .agg(num_voters=("num_voters", "sum"), num_voters_bvr=("num_voters_bvr", "sum"))
        .sort_values("year")
    )
    bvr_by_year["pct_bvr"] = bvr_by_year["num_voters_bvr"] / bvr_by_year["num_voters"]

    latest_year = int(full_panel["year"].max())
    sample_regime_size = (
        full_panel[
            full_panel["ibge_municipality_id"].isin(sample_ids)
            & full_panel["year"].eq(latest_year)
        ]
        .groupby("first_regime", as_index=False)
        .agg(municipalities=("ibge_municipality_id", "nunique"))
    )
    return {
        "sample_ids": sample_ids,
        "sample_regime_size": sample_regime_size,
        "total_drop_anomalies": total_drop_anomalies.sort_values("pct_change_total_voters").head(10),
        "total_drop_anomaly_count": len(total_drop_anomalies),
        "age_growth_anomalies": age_growth_anomalies.sort_values("pct_change_age_voters", ascending=False).head(10),
        "age_growth_anomaly_count": len(age_growth_anomalies),
        "bvr_by_year": bvr_by_year,
    }


def build_panels(df: pd.DataFrame, invalid_age: pd.Series, unknown_education: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    working = attach_first_regime(df)
    working = working[working["num_voters"].gt(0)].copy()
    working = working[OUTPUT_COLUMNS].sort_values(
        ["ibge_municipality_id", "year", "age_cohort", "education"]
    )

    working_invalid_age, working_unknown_education = residual_masks(working)
    residual = working_invalid_age | working_unknown_education
    full_panel = working.copy()
    main_panel = working.loc[~residual].copy()

    full_with_residual = full_panel.assign(excluded_from_main=residual.to_numpy())
    keys = ["year", "state", "first_regime"]
    totals = full_with_residual.groupby(keys, as_index=False).agg(total_voters_full=("num_voters", "sum"))
    excluded = (
        full_with_residual[full_with_residual["excluded_from_main"]]
        .groupby(keys, as_index=False)
        .agg(total_voters_excluded=("num_voters", "sum"))
    )
    residual_report = totals.merge(excluded, how="left", on=keys)
    residual_report["total_voters_excluded"] = residual_report["total_voters_excluded"].fillna(0).astype("int64")
    residual_report["excluded_share"] = (
        residual_report["total_voters_excluded"] / residual_report["total_voters_full"]
    )
    return main_panel, full_panel, residual_report


def print_table(title: str, frame: pd.DataFrame, max_rows: int | None = None) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if max_rows is not None and len(frame) > max_rows:
        print(frame.head(max_rows).to_string(index=False))
        print(f"... ({len(frame) - max_rows:,} additional rows)")
    else:
        print(frame.to_string(index=False))


def main() -> None:
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 180)

    df, source_path = load_data()
    invalid_age, unknown_education = residual_masks(df)

    severe_issues: list[str] = []
    if set(df["year"].unique()) != EXPECTED_YEARS:
        severe_issues.append(f"Unexpected year coverage: {sorted(df['year'].unique())}")
    duplicate_keys = int(df.duplicated(["ibge_municipality_id", "year", "age_cohort", "education"]).sum())
    if duplicate_keys:
        severe_issues.append(f"Found {duplicate_keys:,} duplicate municipality-year-age-education rows")

    interpretation, low_high_checks = verify_low_high_interpretation(df)
    if interpretation == "ambiguous":
        severe_issues.append("low_ed/high_ed interpretation is ambiguous")

    cohort_breakdown, constant_counts, first_values, treatment_issues = first_treatment_checks(df)
    severe_issues.extend(treatment_issues)

    invalid_yearly, invalid_state, invalid_overall = share_tables(df, invalid_age)
    unknown_yearly, unknown_state, unknown_overall = share_tables(df, unknown_education)
    if invalid_overall["state_years_over_5pct"]:
        severe_issues.append("At least one state-year has 5% or more invalid-age voters")
    if unknown_overall["state_years_over_5pct"]:
        severe_issues.append("At least one state-year has 5% or more unknown-education voters")

    cell_distribution, zero_summary = zero_cell_diagnostics(df, invalid_age)
    row_status_crosstab = pd.crosstab(df["year"], df["bvr_status"])
    muni_status_crosstab = pd.crosstab(
        df[["year", "ibge_municipality_id", "bvr_status"]].drop_duplicates()["year"],
        df[["year", "ibge_municipality_id", "bvr_status"]].drop_duplicates()["bvr_status"],
    )

    print("=" * 64)
    print("DECOMPOSITION SOURCE SCHEMA AND CONTENT VERIFICATION")
    print("=" * 64)
    print(f"Source file: {source_path.relative_to(ROOT)}")
    print(f"Rows: {len(df):,}")
    print("\nColumn dtypes:")
    print(df.dtypes.to_string())
    print("\nFirst 10 rows:")
    print(df.head(10).to_string(index=False))
    print(f"\nYear coverage: {sorted(df['year'].unique().tolist())}")
    print(f"State coverage ({df['state'].nunique()}): {sorted(df['state'].unique().tolist())}")
    print(f"Unique municipalities: {df['ibge_municipality_id'].nunique():,}")
    print_table("BVR status by year (municipality counts)", muni_status_crosstab.reset_index())
    print_table("BVR status by year (row counts)", row_status_crosstab.reset_index())
    print(f"\nAge cohorts ({df['age_cohort'].nunique()}):")
    print("\n".join(f"  - {value}" for value in sorted(df["age_cohort"].unique().tolist())))
    print(f"\nEducation categories ({df['education'].nunique()}):")
    print("\n".join(f"  - {value}" for value in sorted(df["education"].unique().tolist())))

    print("\n" + "=" * 64)
    print("LOW/HIGH EDUCATION VERIFICATION")
    print("=" * 64)
    print(f"Interpretation: {interpretation}")
    print(low_high_checks.to_string(index=False))

    print("\n" + "=" * 64)
    print("FIRST-TREATMENT-YEAR VERIFICATION")
    print("=" * 64)
    print_table("Observed first-treatment-year values", first_values)
    print(f"\nTreatment-year columns varying within municipality: {constant_counts}")
    print_table("Cohort breakdown: first treatment year x first regime", cohort_breakdown)

    invalid_display = invalid_yearly.copy()
    for column in ["share", "max_share", "min_share"]:
        invalid_display[column] = invalid_display[column].map(percent)
    unknown_display = unknown_yearly.copy()
    for column in ["share", "max_share", "min_share"]:
        unknown_display[column] = unknown_display[column].map(percent)

    print("\n" + "=" * 64)
    print("RESIDUAL CATEGORY SHARES")
    print("=" * 64)
    print_table("Invalid age share by year", invalid_display)
    print_table("Unknown education share by year", unknown_display)

    print("\n" + "=" * 64)
    print("ZERO-CELL PATTERNS")
    print("=" * 64)
    for key, value in zero_summary.items():
        print(f"{key}: {value:,.0f}")
    print_table("Populated cells per municipality-year", cell_distribution.round(2))

    if severe_issues:
        print("\n" + "=" * 64)
        print("SEVERE DATA QUALITY ISSUE(S): STOPPING BEFORE WRITING PANELS")
        print("=" * 64)
        for issue in severe_issues:
            print(f"- {issue}")
        raise SystemExit(1)

    main_panel, full_panel, residual_report = build_panels(df, invalid_age, unknown_education)
    diagnostics = within_municipality_diagnostics(full_panel)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    main_panel.to_parquet(MAIN_PANEL_PATH, index=False)
    full_panel.to_parquet(FULL_PANEL_PATH, index=False)
    residual_report.to_parquet(RESIDUAL_REPORT_PATH, index=False)

    print("\n" + "=" * 64)
    print("WITHIN-MUNICIPALITY DIAGNOSTICS")
    print("=" * 64)
    print(f"Sample municipalities: {len(diagnostics['sample_ids']):,}")
    print_table("Sample first-regime mix", diagnostics["sample_regime_size"])
    print_table("National biometric voter share by year", diagnostics["bvr_by_year"].assign(pct_bvr=lambda x: x["pct_bvr"].map(percent)))
    print(f"\nSample non-adoption total-voter drops over 30%: {diagnostics['total_drop_anomaly_count']:,}")
    if diagnostics["total_drop_anomaly_count"]:
        print_table("Largest sample total-voter drop anomalies", diagnostics["total_drop_anomalies"], max_rows=10)
    print(f"\nSample older-cohort growth anomalies over 100%: {diagnostics['age_growth_anomaly_count']:,}")
    if diagnostics["age_growth_anomaly_count"]:
        print_table("Largest sample older-cohort growth anomalies", diagnostics["age_growth_anomalies"], max_rows=10)

    cohort_summary = (
        cohort_breakdown.pivot_table(
            index="year_first_any_bvr",
            columns="first_regime",
            values="municipalities",
            fill_value=0,
            aggfunc="sum",
        )
        .reset_index()
        .sort_values("year_first_any_bvr")
    )

    print("\n" + "=" * 64)
    print("DECOMPOSITION DATA SUMMARY")
    print("=" * 64)
    print(f"File: {MAIN_PANEL_PATH.relative_to(ROOT)}")
    print(f"Rows: {len(main_panel):,}")
    print(f"Years: {', '.join(map(str, sorted(main_panel['year'].unique().tolist())))}")
    print(f"Municipalities: {main_panel['ibge_municipality_id'].nunique():,}")
    print(f"States: {main_panel['state'].nunique():,}")
    print("\nCohort breakdown (first treatment year x first regime):")
    print(cohort_summary.to_string(index=False))
    print(
        "\nInvalid age share (national): "
        f"{percent(invalid_overall['national_share'])} "
        f"(max state-year: {invalid_overall['max_state']} {int(invalid_overall['max_state_year'])} "
        f"at {percent(invalid_overall['max_state_share'])})"
    )
    print(
        "Unknown education share (national): "
        f"{percent(unknown_overall['national_share'])} "
        f"(max state-year: {unknown_overall['max_state']} {int(unknown_overall['max_state_year'])} "
        f"at {percent(unknown_overall['max_state_share'])})"
    )
    print(f"\nlow_ed / high_ed interpretation: {interpretation}")
    print("\nWorking panel ready for survival rate estimation in Prompt 2.")
    print("\nSaved outputs:")
    print(f"  - {MAIN_PANEL_PATH.relative_to(ROOT)}")
    print(f"  - {FULL_PANEL_PATH.relative_to(ROOT)}")
    print(f"  - {RESIDUAL_REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
