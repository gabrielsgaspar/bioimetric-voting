from __future__ import annotations

import pandas as pd

from utils import CORE_WAVES, normalize_text


def validate_core_panel(core: pd.DataFrame, crosswalk: pd.DataFrame, availability: pd.DataFrame) -> dict:
    wave_coverage = sorted(core["survey_year"].dropna().unique().tolist())
    if wave_coverage != CORE_WAVES:
        raise ValueError(f"Core wave coverage mismatch. Expected {CORE_WAVES}, got {wave_coverage}.")

    if "trust_elections" not in core.columns:
        raise ValueError("`trust_elections` missing from core panel.")

    fully_comparable = []
    partially_comparable = []
    excluded = []
    for canonical, group in crosswalk.groupby("canonical_variable"):
        core_group = group[group["survey_year"].isin(CORE_WAVES)]
        present_count = core_group["raw_variable"].notna().sum()
        if canonical in core.columns and present_count == len(CORE_WAVES):
            fully_comparable.append(canonical)
        elif canonical in core.columns and present_count > 0:
            partially_comparable.append(canonical)
        elif canonical not in core.columns:
            excluded.append(canonical)

    missingness = core.groupby("survey_year").agg(lambda s: s.isna().mean())
    missingness = (
        missingness.reset_index()
        .melt(id_vars="survey_year", var_name="variable", value_name="missing_share")
    )

    bad_state = int(
        (
            core["state_name"].fillna("@@")
            != core["state_name"].map(normalize_text).fillna("@@")
        ).sum()
    )
    bad_muni = int(
        (
            core["municipality_name"].fillna("@@")
            != core["municipality_name"].map(normalize_text).fillna("@@")
        ).sum()
    )

    return {
        "wave_coverage": wave_coverage,
        "fully_comparable_variables": sorted(fully_comparable),
        "partially_comparable_variables": sorted(partially_comparable),
        "excluded_variables": sorted(set(excluded)),
        "missingness": missingness,
        "bad_state_name_rows": bad_state,
        "bad_municipality_name_rows": bad_muni,
    }
