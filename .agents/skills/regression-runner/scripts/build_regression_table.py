from __future__ import annotations

import pandas as pd

from utils import latex_escape


def build_regression_summary(interaction_effects: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for category, group in interaction_effects.groupby("category", sort=False):
        no_row = group.loc[group["group_label"] == "No"].iloc[0]
        yes_row = group.loc[group["group_label"] == "Yes"].iloc[0]
        rows.append(
            {
                "outcome": no_row["outcome_label"],
                "category": category,
                "base_group_treatment_effect": no_row["estimate"],
                "base_group_std_error": no_row["std_error"],
                "interacted_group_treatment_effect": yes_row["estimate"],
                "interacted_group_std_error": yes_row["std_error"],
                "interaction_difference": no_row["interaction_difference"],
                "interaction_difference_std_error": no_row["interaction_difference_std_err"],
                "interaction_p_value": no_row["interaction_p_value"],
                "stars": no_row["stars"],
                "n_obs": no_row["n_obs"],
            }
        )
    return pd.DataFrame(rows)


def build_tex_table(summary: pd.DataFrame, *, note: str) -> str:
    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcccc}",
        r"\doubletoprule",
        r"Category & Base group & Interacted group & Difference & $p$-value \\",
        r"\midrule",
    ]

    for row in summary.itertuples(index=False):
        stars = "" if pd.isna(row.stars) else str(row.stars)
        difference = f"{row.interaction_difference:.3f}{stars}"
        lines.append(
            f"{latex_escape(row.category)} & {row.base_group_treatment_effect:.3f} & "
            f"{row.interacted_group_treatment_effect:.3f} & {difference} & {row.interaction_p_value:.3f} \\\\"
        )
        lines.append(
            f" & ({row.base_group_std_error:.3f}) & ({row.interacted_group_std_error:.3f}) & "
            f"({row.interaction_difference_std_error:.3f}) & \\\\"
        )

    lines.extend(
        [
            r"\doublebottomrule",
            r"\end{tabular*}",
            "",
            r"\begin{minipage}{\textwidth}",
            r"\footnotesize",
            rf"\textbf{{Note:}} {note}",
            r"\end{minipage}",
        ]
    )
    return "\n".join(lines) + "\n"
