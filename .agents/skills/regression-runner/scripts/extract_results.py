from __future__ import annotations

import pandas as pd

from compute_linear_combinations import linear_combination
from fit_model_pyfixest import FittedModel
from utils import stars_from_pvalue


def interaction_term_name(main_var: str, interaction_var: str, index: pd.Index) -> str:
    direct = f"{main_var}:{interaction_var}"
    reverse = f"{interaction_var}:{main_var}"
    if direct in index:
        return direct
    if reverse in index:
        return reverse
    raise KeyError(
        f"Could not find the interaction coefficient for `{main_var}` and `{interaction_var}` in {list(index)}"
    )


def extract_tidy_results(model: FittedModel, *, category: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "category": category,
            "outcome": model.outcome,
            "term": model.params.index,
            "estimate": model.params.values,
            "std_error": model.std_errors.reindex(model.params.index).values,
            "p_value": model.p_values.reindex(model.params.index).values,
            "ci95_low": model.ci_low.reindex(model.params.index).values,
            "ci95_high": model.ci_high.reindex(model.params.index).values,
            "n_obs": model.sample_n,
            "backend": model.backend,
            "formula": model.formula,
        }
    )


def extract_interaction_effects(
    *,
    model: FittedModel,
    interaction_var: str,
    category_label: str,
    outcome_label: str,
) -> pd.DataFrame:
    interaction_name = interaction_term_name(model.main_var, interaction_var, model.params.index)
    base = linear_combination(params=model.params, vcov=model.vcov, weights={model.main_var: 1.0})
    interacted = linear_combination(
        params=model.params,
        vcov=model.vcov,
        weights={model.main_var: 1.0, interaction_name: 1.0},
    )
    difference = linear_combination(params=model.params, vcov=model.vcov, weights={interaction_name: 1.0})
    stars = stars_from_pvalue(difference["p_value"])

    rows = []
    for group_label, effect in [("No", base), ("Yes", interacted)]:
        rows.append(
            {
                "outcome": model.outcome,
                "outcome_label": outcome_label,
                "category": category_label,
                "interaction_var": interaction_var,
                "group_label": group_label,
                "estimate": effect["estimate"],
                "std_error": effect["std_error"],
                "ci95_low": effect["ci95_low"],
                "ci95_high": effect["ci95_high"],
                "interaction_difference": difference["estimate"],
                "interaction_difference_std_err": difference["std_error"],
                "interaction_difference_ci95_low": difference["ci95_low"],
                "interaction_difference_ci95_high": difference["ci95_high"],
                "interaction_p_value": difference["p_value"],
                "stars": stars,
                "n_obs": model.sample_n,
                "formula": model.formula,
                "backend": model.backend,
                "cluster_vars": " + ".join(model.cluster_vars),
            }
        )
    return pd.DataFrame(rows)
