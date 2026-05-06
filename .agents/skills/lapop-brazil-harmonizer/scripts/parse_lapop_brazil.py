from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyreadstat

from utils import RAW_DIR


def raw_wave_path(year: int) -> Path:
    files = sorted((RAW_DIR / str(year)).glob("*.dta"))
    if not files:
        raise FileNotFoundError(f"No raw LAPOP Brazil .dta file found for {year}.")
    return files[0]


def read_wave(year: int, usecols: list[str] | None = None, apply_value_formats: bool = False) -> tuple[pd.DataFrame, object]:
    path = raw_wave_path(year)
    df, meta = pyreadstat.read_dta(
        path,
        usecols=usecols,
        apply_value_formats=apply_value_formats,
    )
    return df, meta


def read_wave_metadata(year: int):
    path = raw_wave_path(year)
    _, meta = pyreadstat.read_dta(path, metadataonly=True)
    return meta
