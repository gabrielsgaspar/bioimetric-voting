from __future__ import annotations

import pandas as pd


REQUIRED_BY_RUN_TYPE = {
    "single_model": ["data_path", "outcome", "main_var", "output_dir"],
    "interaction_series": ["data_path", "outcome", "main_var", "interaction_vars", "output_dir"],
}


def validate_config(config: dict) -> None:
    run_type = config.get("run_type")
    if run_type not in REQUIRED_BY_RUN_TYPE:
        raise ValueError(
            f"Unsupported run_type `{run_type}`. Expected one of {sorted(REQUIRED_BY_RUN_TYPE)}."
        )
    missing = [field for field in REQUIRED_BY_RUN_TYPE[run_type] if not config.get(field)]
    if missing:
        raise ValueError(f"Missing required config fields for `{run_type}`: {missing}")


def validate_columns(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = sorted({column for column in columns if column and column not in df.columns})
    if missing:
        raise ValueError(f"Missing required columns for {label}: {missing}")


def apply_sample_filter(df: pd.DataFrame, filter_expr: str | None) -> pd.DataFrame:
    if not filter_expr:
        return df.copy()
    filtered = df.query(filter_expr, engine="python").copy()
    if filtered.empty:
        raise ValueError(f"Sample filter `{filter_expr}` removed all rows.")
    return filtered
