from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.sandwich_covariance import cov_cluster, cov_cluster_2groups

from build_formula import build_formula
from utils import safe_float, two_sided_p_from_z


@dataclass
class FittedModel:
    backend: str
    formula: str
    outcome: str
    main_var: str
    interaction_var: str | None
    sample_n: int
    r_squared: float | None
    params: pd.Series
    std_errors: pd.Series
    p_values: pd.Series
    ci_low: pd.Series
    ci_high: pd.Series
    vcov: pd.DataFrame
    cluster_vars: list[str]
    cluster_counts: dict[str, int]
    fixed_effects: list[str]
    controls: list[str]
    sample_filter: str | None
    notes: list[str]


def _build_cluster_covariance(result, data: pd.DataFrame, cluster_vars: list[str]) -> tuple[np.ndarray, list[str]]:
    notes: list[str] = []
    if not cluster_vars:
        return np.asarray(result.cov_params()), notes

    cluster_arrays = {
        cluster: pd.Series(data[cluster]).astype("category").cat.codes.to_numpy()
        for cluster in cluster_vars
    }

    if len(cluster_vars) == 1:
        covariance = cov_cluster(result, cluster_arrays[cluster_vars[0]])
        return np.asarray(covariance), notes

    if len(cluster_vars) == 2:
        covariance = cov_cluster_2groups(
            result,
            cluster_arrays[cluster_vars[0]],
            cluster_arrays[cluster_vars[1]],
        )[0]
        covariance = np.asarray(covariance)
        diagonal = np.diag(covariance)
        if not np.all(np.isfinite(diagonal)) or np.any(diagonal < -1e-12):
            fallback = cov_cluster(result, cluster_arrays[cluster_vars[0]])
            notes.append(
                "Two-way clustered covariance produced non-finite or negative variances; "
                f"fell back to one-way clustering on `{cluster_vars[0]}`."
            )
            return np.asarray(fallback), notes
        return covariance, notes

    raise ValueError(
        f"Only zero, one, or two clustering dimensions are supported. Received: {cluster_vars}"
    )


def fit_model(
    *,
    data: pd.DataFrame,
    outcome: str,
    main_var: str,
    interaction_var: str | None,
    controls: list[str] | None,
    fixed_effects: list[str] | None,
    cluster_vars: list[str] | None,
    weight_var: str | None,
    sample_filter: str | None,
) -> FittedModel:
    formula = build_formula(
        outcome=outcome,
        main_var=main_var,
        interaction_var=interaction_var,
        controls=controls,
        fixed_effects=fixed_effects,
    )

    if weight_var:
        result = smf.wls(formula=formula, data=data, weights=data[weight_var]).fit()
        backend = "statsmodels_wls_fe"
    else:
        result = smf.ols(formula=formula, data=data).fit()
        backend = "statsmodels_ols_fe"

    cluster_vars = cluster_vars or []
    covariance, notes = _build_cluster_covariance(result, data, cluster_vars)

    params = result.params.copy()
    vcov = pd.DataFrame(covariance, index=params.index, columns=params.index)
    std_errors = pd.Series(np.sqrt(np.clip(np.diag(vcov), 0.0, None)), index=params.index, name="std_error")
    z_values = params / std_errors.replace(0.0, np.nan)
    p_values = z_values.map(lambda value: np.nan if pd.isna(value) else two_sided_p_from_z(float(value)))
    ci_low = params - 1.96 * std_errors
    ci_high = params + 1.96 * std_errors
    cluster_counts = {cluster: int(data[cluster].nunique()) for cluster in cluster_vars}

    return FittedModel(
        backend=backend,
        formula=formula,
        outcome=outcome,
        main_var=main_var,
        interaction_var=interaction_var,
        sample_n=int(len(data)),
        r_squared=safe_float(result.rsquared),
        params=params,
        std_errors=std_errors,
        p_values=p_values,
        ci_low=ci_low,
        ci_high=ci_high,
        vcov=vcov,
        cluster_vars=cluster_vars,
        cluster_counts=cluster_counts,
        fixed_effects=fixed_effects or [],
        controls=controls or [],
        sample_filter=sample_filter,
        notes=notes,
    )
