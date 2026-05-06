from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils import repo_path


def save_dataframe(df: pd.DataFrame, output_path: str | Path) -> None:
    resolved = repo_path(output_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if resolved.suffix == ".csv":
        df.to_csv(resolved, index=False)
        return
    if resolved.suffix == ".parquet":
        df.to_parquet(resolved, index=False)
        return
    raise ValueError(f"Unsupported tabular output suffix for {resolved}")


def write_text(text: str, output_path: str | Path) -> None:
    resolved = repo_path(output_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(text, encoding="utf-8")
