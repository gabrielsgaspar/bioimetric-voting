from __future__ import annotations

from pathlib import Path

import requests

from discover_lapop_sources import discover_sources
from utils import OFFICIAL_WAVES, RAW_DIR


def download_wave(year: int, force: bool = False) -> Path:
    if year not in OFFICIAL_WAVES:
        raise ValueError(f"Brazil wave {year} is not in the official public LAPOP wave list.")

    inventory = discover_sources()
    row = inventory[(inventory["survey_year"] == year) & (inventory["source_type"] == "dataset_file")].iloc[0]
    url = row["source_url"]
    filename = row["title"]

    outdir = RAW_DIR / str(year)
    outdir.mkdir(parents=True, exist_ok=True)
    outpath = outdir / filename

    if outpath.exists() and not force:
        return outpath

    with requests.get(url, timeout=180) as resp:
        resp.raise_for_status()
        outpath.write_bytes(resp.content)

    return outpath


def download_waves(years: list[int], force: bool = False) -> list[Path]:
    return [download_wave(year, force=force) for year in years]


if __name__ == "__main__":
    download_waves([2008, 2010, 2012, 2014, 2017, 2019, 2021])
