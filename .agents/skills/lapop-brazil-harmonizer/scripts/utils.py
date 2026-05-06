from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from unidecode import unidecode


ROOT = Path(__file__).resolve().parents[4]
RAW_DIR = ROOT / "data" / "raw" / "lapop"
INTERIM_DIR = ROOT / "data" / "interim" / "lapop"
CLEAN_DIR = ROOT / "data" / "clean" / "lapop"
LOG_DIR = ROOT / "resources" / "logs"
DOCS_DIR = ROOT / "docs"

OFFICIAL_WAVES = [2008, 2010, 2012, 2014, 2017, 2019, 2021]
CORE_WAVES = [2008, 2010, 2012, 2014, 2017, 2019]
KNOWN_CLOSEST_WAVES = [2019, 2021]
CATALOG_PAGE = "https://www.vanderbilt.edu/lapop/raw-data.php"
DATASET_BASE = "https://lapop.app.vanderbilt.edu"

UF_TO_STATE = {
    "ac": "acre",
    "al": "alagoas",
    "am": "amazonas",
    "ap": "amapa",
    "ba": "bahia",
    "ce": "ceara",
    "df": "distrito federal",
    "es": "espirito santo",
    "go": "goias",
    "ma": "maranhao",
    "mg": "minas gerais",
    "ms": "mato grosso do sul",
    "mt": "mato grosso",
    "pa": "para",
    "pb": "paraiba",
    "pe": "pernambuco",
    "pi": "piaui",
    "pr": "parana",
    "rj": "rio de janeiro",
    "rn": "rio grande do norte",
    "ro": "rondonia",
    "rr": "roraima",
    "rs": "rio grande do sul",
    "sc": "santa catarina",
    "se": "sergipe",
    "sp": "sao paulo",
    "to": "tocantins",
}


def ensure_dirs() -> None:
    for path in [RAW_DIR, INTERIM_DIR, CLEAN_DIR, LOG_DIR, DOCS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def write_yaml(data: dict[str, Any], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def normalize_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = unidecode(text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_state_name(value: Any) -> str | None:
    text = normalize_text(value)
    if text in UF_TO_STATE:
        return UF_TO_STATE[text]
    return text


def normalize_code_for_lookup(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def save_dataframe(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
    elif path.suffix.lower() == ".parquet":
        df.to_parquet(path, index=False)
    else:
        raise ValueError(f"Unsupported output format: {path}")


def year_slug(year: int) -> str:
    return f"bra_{year}"


def requested_year_error(year: int) -> dict[str, Any]:
    nearest = [wave for wave in OFFICIAL_WAVES if abs(wave - year) <= 5]
    if not nearest:
        nearest = KNOWN_CLOSEST_WAVES
    return {
        "requested_year": year,
        "available": False,
        "message": f"No official public LAPOP Brazil wave found for {year}.",
        "nearby_available_waves": nearest,
    }
