from __future__ import annotations

from pathlib import Path

import pandas as pd

from download_lapop_brazil import download_wave
from parse_lapop_brazil import read_wave_metadata, read_wave
from utils import OFFICIAL_WAVES, requested_year_error, save_dataframe, write_yaml


def build_requested_extract(requested_year: int, requested_questions: list[str], output_path: str | Path) -> pd.DataFrame:
    if requested_year not in OFFICIAL_WAVES:
        error_payload = requested_year_error(requested_year)
        note_path = Path(output_path).with_suffix(".yml")
        note_path.parent.mkdir(parents=True, exist_ok=True)
        write_yaml(error_payload, note_path)
        raise ValueError(f"No official public LAPOP Brazil wave found for {requested_year}. Nearby official waves: {error_payload['nearby_available_waves']}")

    download_wave(requested_year)
    meta = read_wave_metadata(requested_year)
    missing = [var for var in requested_questions if var not in meta.column_names]
    if missing:
        raise ValueError(f"Requested variables not found in official Brazil {requested_year} file: {missing}")

    df, _ = read_wave(requested_year, usecols=requested_questions, apply_value_formats=False)
    df.insert(0, "survey_year", requested_year)
    df.insert(1, "wave_label", f"brazil_{requested_year}")

    save_dataframe(df, output_path)
    csv_path = Path(output_path).with_suffix(".csv")
    save_dataframe(df, csv_path)
    return df
