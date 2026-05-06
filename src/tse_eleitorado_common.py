from __future__ import annotations

import re
import unicodedata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "tse_eleitorado"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "tse_eleitorado"
CLEAN_DIR = PROJECT_ROOT / "data" / "clean" / "tse_eleitorado"
LOG_DIR = PROJECT_ROOT / "outputs" / "logs"
DOCS_DIR = PROJECT_ROOT / "docs"
IBGE_CROSSWALK_PATH = PROJECT_ROOT / "data" / "raw" / "ibge" / "bd-tse_mun_ids.csv"

VALID_UFS = {
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
}

TARGET_YEARS = list(range(2000, 2019))
OFFICIAL_PACKAGE_YEARS = list(range(2000, 2019, 2))


def ensure_directories() -> None:
    for path in [RAW_DIR, INTERIM_DIR, CLEAN_DIR, LOG_DIR, DOCS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def normalize_name(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.replace("'", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_state(value: object) -> str:
    text = "" if value is None else str(value).strip().upper()
    return text
