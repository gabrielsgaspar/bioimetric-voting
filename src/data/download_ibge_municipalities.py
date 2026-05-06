from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.tse_bvr_common import IBGE_MUNICIPALITIES_PATH, RAW_IBGE_DIR, ensure_directories, normalize_name


IBGE_API_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"


def download_ibge() -> tuple[pd.DataFrame, str]:
    ensure_directories()

    response = requests.get(IBGE_API_URL, timeout=120)
    response.raise_for_status()
    payload = response.json()

    raw_path = RAW_IBGE_DIR / "ibge_municipios_api_v1_localidades_municipios.json"
    with raw_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    rows = []
    for item in payload:
        state = None
        if item.get("microrregiao") and item["microrregiao"].get("mesorregiao"):
            state = item["microrregiao"]["mesorregiao"]["UF"]["sigla"]
        elif item.get("regiao-imediata") and item["regiao-imediata"].get("regiao-intermediaria"):
            state = item["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]
        elif item.get("UF"):
            state = item["UF"]["sigla"]
        if state is None:
            raise ValueError(f"Could not recover UF for IBGE municipality payload: {item}")

        rows.append(
            {
                "municipality_id": str(item["id"]).zfill(7),
                "municipality_name_raw": item["nome"],
                "state": state,
            }
        )

    df = pd.DataFrame(rows).sort_values(["state", "municipality_name_raw"]).reset_index(drop=True)
    df["municipality_name"] = df["municipality_name_raw"].map(normalize_name)
    cleaned = df[["municipality_id", "municipality_name", "state", "municipality_name_raw"]].copy()

    IBGE_MUNICIPALITIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(IBGE_MUNICIPALITIES_PATH, index=False)
    return cleaned, IBGE_API_URL


def main() -> None:
    download_ibge()


if __name__ == "__main__":
    main()
