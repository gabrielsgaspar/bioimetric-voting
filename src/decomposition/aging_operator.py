from __future__ import annotations

import numpy as np
import pandas as pd


AGE_COHORTS = [
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

INFLOW_COHORTS = AGE_COHORTS[:4]
SURVIVAL_COHORTS = AGE_COHORTS[4:]
SINGLE_YEAR_SURVIVAL_COHORTS = {"20 anos"}


def build_aging_matrix() -> pd.DataFrame:
    """Return the two-year mechanical aging operator.

    Rows are target cohorts at t+2, columns are source cohorts at t.
    Multiplying a source row vector by matrix.T yields the aged-forward
    target vector T(N_{m,t,.}).
    """
    matrix = pd.DataFrame(0.0, index=AGE_COHORTS, columns=AGE_COHORTS)

    matrix.loc["18 anos", "16 anos"] = 1.0
    matrix.loc["19 anos", "17 anos"] = 1.0
    matrix.loc["20 anos", "18 anos"] = 1.0
    matrix.loc["21 a 24 anos", "19 anos"] = 1.0
    matrix.loc["21 a 24 anos", "20 anos"] = 1.0

    matrix.loc["21 a 24 anos", "21 a 24 anos"] = 2.0 / 4.0
    matrix.loc["25 a 29 anos", "21 a 24 anos"] = 2.0 / 4.0

    five_year_bins = AGE_COHORTS[6:-1]
    for source, target in zip(five_year_bins, AGE_COHORTS[7:]):
        matrix.loc[source, source] = 3.0 / 5.0
        matrix.loc[target, source] = 2.0 / 5.0

    matrix.loc["100 anos ou mais", "100 anos ou mais"] = 1.0
    return matrix


AGING_MATRIX = build_aging_matrix()


def apply_aging_operator(wide_counts: pd.DataFrame) -> pd.DataFrame:
    """Apply T to a DataFrame with one column per age cohort."""
    missing = [cohort for cohort in AGE_COHORTS if cohort not in wide_counts.columns]
    if missing:
        raise ValueError(f"Missing age-cohort columns: {missing}")
    aged = wide_counts[AGE_COHORTS].to_numpy(dtype=float) @ AGING_MATRIX.to_numpy(dtype=float).T
    return pd.DataFrame(aged, index=wide_counts.index, columns=AGE_COHORTS)


def per_cycle_threshold(age_cohort: str) -> int:
    if age_cohort in SINGLE_YEAR_SURVIVAL_COHORTS:
        return 100
    if age_cohort in SURVIVAL_COHORTS:
        return 200
    return 100


def validate_aging_matrix() -> None:
    expected_shape = (len(AGE_COHORTS), len(AGE_COHORTS))
    if AGING_MATRIX.shape != expected_shape:
        raise ValueError(f"Aging matrix has shape {AGING_MATRIX.shape}, expected {expected_shape}")
    column_sums = AGING_MATRIX.sum(axis=0).to_numpy()
    if not np.allclose(column_sums, np.ones(len(AGE_COHORTS))):
        raise ValueError(f"Aging matrix columns do not sum to one: {column_sums}")
