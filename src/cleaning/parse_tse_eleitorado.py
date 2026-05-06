from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.tse_eleitorado_common import INTERIM_DIR, OFFICIAL_PACKAGE_YEARS, RAW_DIR, ensure_directories, normalize_name, normalize_state


CHUNKSIZE = 300_000
REQUIRED_COLUMNS = [
    "ANO_ELEICAO",
    "SG_UF",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "DS_GRAU_ESCOLARIDADE",
    "DS_GENERO",
    "QT_ELEITORES_PERFIL",
]


def canonicalize_text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() == "nan" else text


def map_education(value: object) -> str:
    normalized = normalize_name(value)
    if normalized in {"", "nao informado", "nao se aplica", "ne"}:
        return "unknown"
    if "analfab" in normalized:
        return "illiterate"
    if "le e escreve" in normalized:
        return "reads_and_writes"
    if "fundamental incompleto" in normalized or "1 grau incompleto" in normalized or "primeiro grau incompleto" in normalized:
        return "incomplete_primary"
    if "fundamental completo" in normalized or "1 grau completo" in normalized or "primeiro grau completo" in normalized:
        return "complete_primary"
    if "medio incompleto" in normalized or "2 grau incompleto" in normalized or "segundo grau incompleto" in normalized:
        return "incomplete_secondary"
    if "medio completo" in normalized or "2 grau completo" in normalized or "segundo grau completo" in normalized:
        return "complete_secondary"
    if "superior incompleto" in normalized:
        return "incomplete_higher"
    if "superior completo" in normalized:
        return "complete_higher"
    return "unknown"


def map_gender(value: object) -> str:
    normalized = normalize_name(value)
    if normalized == "masculino":
        return "male"
    if normalized == "feminino":
        return "female"
    return "unknown"


def open_zip_csv(zip_path: Path) -> tuple[zipfile.ZipFile, str]:
    archive = zipfile.ZipFile(zip_path)
    csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if not csv_names:
        archive.close()
        raise RuntimeError(f"No CSV file found inside {zip_path}")
    preferred = next((name for name in csv_names if "perfil_eleitorado" in Path(name).name.lower()), csv_names[0])
    return archive, preferred


def build_schema_row(year: int, columns: list[str]) -> dict:
    extras = []
    if "CD_RACA_COR" in columns:
        extras.append("race/color")
    if "CD_IDENTIDADE_GENERO" in columns:
        extras.append("gender identity")
    if "TP_OBRIGATORIEDADE_VOTO" in columns:
        extras.append("voting-obligation type")
    if "CD_MUN_SIT_BIOMETRICA" in columns:
        extras.append("biometric-status")
    note = "Core municipality, gender, education, and electorate count fields are present."
    if extras:
        note += f" Additional fields include {', '.join(extras)}; parser aggregates over these extra dimensions."
    return {
        "year": year,
        "raw_column_municipality_code": "CD_MUNICIPIO" if "CD_MUNICIPIO" in columns else "",
        "raw_column_municipality_name": "NM_MUNICIPIO" if "NM_MUNICIPIO" in columns else "",
        "raw_column_state": "SG_UF" if "SG_UF" in columns else "",
        "raw_column_num_voters": "QT_ELEITORES_PERFIL" if "QT_ELEITORES_PERFIL" in columns else "",
        "raw_column_education": "DS_GRAU_ESCOLARIDADE" if "DS_GRAU_ESCOLARIDADE" in columns else "",
        "raw_column_gender": "DS_GENERO" if "DS_GENERO" in columns else "",
        "transformation_notes": note,
    }


def parse_year(year: int) -> dict:
    zip_path = RAW_DIR / str(year) / f"perfil_eleitorado_{year}.zip"
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    archive, member = open_zip_csv(zip_path)
    try:
        with archive.open(member) as handle:
            columns = list(pd.read_csv(handle, sep=";", encoding="latin1", nrows=0).columns)

        missing = [column for column in REQUIRED_COLUMNS if column not in columns]
        if missing:
            raise RuntimeError(f"{zip_path.name} is missing required columns: {missing}")

        aggregated_chunks: list[pd.DataFrame] = []
        with archive.open(member) as handle:
            reader = pd.read_csv(handle, sep=";", encoding="latin1", usecols=REQUIRED_COLUMNS, chunksize=CHUNKSIZE)
            for chunk in reader:
                chunk = chunk.rename(
                    columns={
                        "ANO_ELEICAO": "year",
                        "SG_UF": "state",
                        "CD_MUNICIPIO": "tse_municipality_id",
                        "NM_MUNICIPIO": "municipality_name_raw",
                        "DS_GRAU_ESCOLARIDADE": "education_raw",
                        "DS_GENERO": "gender_raw",
                        "QT_ELEITORES_PERFIL": "num_voters",
                    }
                )
                chunk["year"] = pd.to_numeric(chunk["year"], errors="coerce").astype("Int64")
                chunk["state"] = chunk["state"].map(normalize_state)
                chunk["tse_municipality_id"] = (
                    chunk["tse_municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
                )
                chunk["municipality_name_raw"] = chunk["municipality_name_raw"].map(canonicalize_text)
                chunk["municipality_name"] = chunk["municipality_name_raw"].map(normalize_name)
                chunk["education_raw"] = chunk["education_raw"].map(canonicalize_text)
                chunk["education"] = chunk["education_raw"].map(map_education)
                chunk["gender_raw"] = chunk["gender_raw"].map(canonicalize_text)
                chunk["gender"] = chunk["gender_raw"].map(map_gender)
                chunk["num_voters"] = pd.to_numeric(chunk["num_voters"], errors="coerce").fillna(0).astype("int64")

                grouped = (
                    chunk.groupby(
                        [
                            "year",
                            "state",
                            "tse_municipality_id",
                            "municipality_name_raw",
                            "municipality_name",
                            "education_raw",
                            "education",
                            "gender_raw",
                            "gender",
                        ],
                        as_index=False,
                        dropna=False,
                    )["num_voters"]
                    .sum()
                )
                aggregated_chunks.append(grouped)

        year_df = (
            pd.concat(aggregated_chunks, ignore_index=True)
            .groupby(
                [
                    "year",
                    "state",
                    "tse_municipality_id",
                    "municipality_name_raw",
                    "municipality_name",
                    "education_raw",
                    "education",
                    "gender_raw",
                    "gender",
                ],
                as_index=False,
                dropna=False,
            )["num_voters"]
            .sum()
            .sort_values(["year", "state", "municipality_name", "education", "gender"])
            .reset_index(drop=True)
        )
        year_df.to_parquet(INTERIM_DIR / f"parsed_{year}.parquet", index=False)
        return build_schema_row(year, columns)
    finally:
        archive.close()


def main() -> None:
    ensure_directories()
    schema_rows = [parse_year(year) for year in OFFICIAL_PACKAGE_YEARS]
    schema_df = pd.DataFrame(schema_rows).sort_values("year").reset_index(drop=True)
    schema_df.to_csv(INTERIM_DIR / "schema_by_year.csv", index=False)
    print(f"Wrote parsed parquet files and {INTERIM_DIR / 'schema_by_year.csv'}.")


if __name__ == "__main__":
    main()
