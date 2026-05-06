from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils import repo_path


def load_data(data_path: str | Path, file_format: str | None = None) -> pd.DataFrame:
    resolved = repo_path(data_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Data file not found: {resolved}")

    inferred = file_format.lower() if file_format else resolved.suffix.lower().lstrip(".")
    if inferred == "parquet":
        return pd.read_parquet(resolved)
    if inferred == "csv":
        return pd.read_csv(resolved)
    raise ValueError(f"Unsupported file format `{inferred}` for {resolved}")
