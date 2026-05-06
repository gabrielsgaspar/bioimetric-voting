from __future__ import annotations

import numpy as np
import pandas as pd

from utils import two_sided_p_from_z


def linear_combination(
    *,
    params: pd.Series,
    vcov: pd.DataFrame,
    weights: dict[str, float],
) -> dict[str, float]:
    missing = [name for name in weights if name not in params.index]
    if missing:
        raise KeyError(f"Linear combination refers to missing coefficient(s): {missing}")

    vector = pd.Series(0.0, index=params.index)
    for name, weight in weights.items():
        vector.loc[name] = weight

    estimate = float(np.dot(vector, params))
    variance = float(np.dot(vector, np.dot(vcov.to_numpy(), vector)))
    variance = max(variance, 0.0)
    std_error = float(np.sqrt(variance))
    z_value = np.nan if std_error == 0 else estimate / std_error
    p_value = np.nan if std_error == 0 else two_sided_p_from_z(float(z_value))
    return {
        "estimate": estimate,
        "std_error": std_error,
        "ci95_low": estimate - 1.96 * std_error,
        "ci95_high": estimate + 1.96 * std_error,
        "z_value": z_value,
        "p_value": p_value,
    }
