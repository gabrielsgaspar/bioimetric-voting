from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import subprocess
import textwrap
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile, is_zipfile

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import urllib3


ROOT = Path(__file__).resolve().parents[2]

RAW_IBGE_DIR = ROOT / "data" / "raw" / "ibge" / "censo_2010_microdados"
INTERIM_IBGE_DIR = ROOT / "data" / "interim" / "ibge" / "censo_2010_docs_extracted"
AGENT_SIM_DIR = ROOT / "data" / "clean" / "agent_sim"
AGENT_SIM_FIGURES_DIR = ROOT / "resources" / "agent_sim" / "figures"
AGENT_SIM_TABLES_DIR = ROOT / "resources" / "tables"
AGENT_SIM_LOG_DIR = ROOT / "resources" / "agent_sim" / "logs"
DOCS_PATH = ROOT / "docs" / "AGENT_SIMULATION_NOTES.md"

PERSONAS_PATH = AGENT_SIM_DIR / "personas.parquet"
RESPONSES_PATH = AGENT_SIM_DIR / "persona_responses.parquet"
MUNICIPALITY_PRED_PATH = AGENT_SIM_DIR / "municipality_predicted_dropout.parquet"

SCATTER_FIGURE_PATH = AGENT_SIM_FIGURES_DIR / "predicted_vs_observed_scatter.pdf"
EDUCATION_FIGURE_PATH = AGENT_SIM_FIGURES_DIR / "education_gradient_comparison.pdf"
REGIONAL_FIGURE_PATH = AGENT_SIM_FIGURES_DIR / "regional_heterogeneity.pdf"

VALIDATION_TABLE_PATH = AGENT_SIM_TABLES_DIR / "agent_sim_validation_table.tex"
PROMPT_SENS_TABLE_PATH = AGENT_SIM_TABLES_DIR / "agent_sim_prompt_sensitivity.tex"

RUN_LOG_PATH = AGENT_SIM_LOG_DIR / "agent_simulation_summary.json"

TSE_PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018.parquet"
TREATMENT_PATH = ROOT / "data" / "clean" / "tse_bvr" / "municipality_bvr_first_treat.parquet"
POPULATION_PATH = ROOT / "data" / "clean" / "ibge" / "municipality_gdp_population_survey_years.parquet"

CODex_WORKDIR = Path("/tmp/codex_agent_sim")

DOCUMENTATION_URL = (
    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2010/Resultados_Gerais_da_Amostra/Microdados/Documentacao.zip"
)

STATE_ARCHIVES = [
    "AC.zip",
    "AL.zip",
    "AM.zip",
    "AP.zip",
    "BA.zip",
    "CE.zip",
    "DF.zip",
    "ES.zip",
    "GO.zip",
    "MA.zip",
    "MG.zip",
    "MS.zip",
    "MT.zip",
    "PA.zip",
    "PB.zip",
    "PE.zip",
    "PI.zip",
    "PR.zip",
    "RJ.zip",
    "RN.zip",
    "RO.zip",
    "RR.zip",
    "RS.zip",
    "SC.zip",
    "SE.zip",
    "SP1.zip",
    "SP2_RM.zip",
    "TO.zip",
]

STATE_NAME_MAP = {
    "11": "Rondonia",
    "12": "Acre",
    "13": "Amazonas",
    "14": "Roraima",
    "15": "Para",
    "16": "Amapa",
    "17": "Tocantins",
    "21": "Maranhao",
    "22": "Piaui",
    "23": "Ceara",
    "24": "Rio Grande do Norte",
    "25": "Paraiba",
    "26": "Pernambuco",
    "27": "Alagoas",
    "28": "Sergipe",
    "29": "Bahia",
    "31": "Minas Gerais",
    "32": "Espirito Santo",
    "33": "Rio de Janeiro",
    "35": "Sao Paulo",
    "41": "Parana",
    "42": "Santa Catarina",
    "43": "Rio Grande do Sul",
    "50": "Mato Grosso do Sul",
    "51": "Mato Grosso",
    "52": "Goias",
    "53": "Distrito Federal",
}

STATE_ABBR_MAP = {
    "11": "RO",
    "12": "AC",
    "13": "AM",
    "14": "RR",
    "15": "PA",
    "16": "AP",
    "17": "TO",
    "21": "MA",
    "22": "PI",
    "23": "CE",
    "24": "RN",
    "25": "PB",
    "26": "PE",
    "27": "AL",
    "28": "SE",
    "29": "BA",
    "31": "MG",
    "32": "ES",
    "33": "RJ",
    "35": "SP",
    "41": "PR",
    "42": "SC",
    "43": "RS",
    "50": "MS",
    "51": "MT",
    "52": "GO",
    "53": "DF",
}

REGION_MAP = {
    "1": "North",
    "2": "Northeast",
    "3": "Southeast",
    "4": "South",
    "5": "Center-West",
}

EDUCATION_LEVELS = ["illiterate", "primary", "secondary", "higher"]
AGE_GROUPS = ["18-29", "30-44", "45-64", "65+"]
SEX_GROUPS = ["male", "female"]
REGION_GROUPS = ["North", "Northeast", "Southeast", "South", "Center-West"]
SIZE_TIERS = ["<10k", "10k-50k", "50k-200k", "200k+"]

PRIMARY_CELL_COLS = ["education_group", "age_group", "sex", "region", "municipality_size_tier"]
MUNICIPALITY_CELL_COLS = ["municipality_id", "education_group", "age_group", "sex"]
ARCHIVE_CANDIDATE_SAMPLE_COLS = [
    "municipality_id",
    "state_name",
    "region",
    "municipality_size_tier",
    "urban_rural",
    "age",
    "age_group",
    "sex",
    "education_group",
    "occupation_category",
    "income_tier",
    "household_income",
    "personal_income",
    "weight",
    "sector_status_num",
]

MAIN_MODEL = "gpt-5.4-mini"
VALIDATION_MODEL = "gpt-5.4"
BASELINE_PROMPT_STYLE = "detailed"
PROMPT_STYLES = ["minimal", "detailed", "persona_driven"]
MAIN_BATCH_SIZE = 20
MAIN_MAX_WORKERS = 4
RANDOM_SEED = 20260423
ARCHIVE_MAX_WORKERS = 8

FIXED_WIDTH_COLUMNS = {
    "uf": (0, 2),
    "municipality_code5": (2, 7),
    "sample_weight_raw": (28, 44),
    "region_code": (44, 45),
    "urban_rural_code": (52, 53),
    "sex_code": (57, 58),
    "age_raw": (61, 64),
    "race_code": (67, 68),
    "birth_registration": (68, 69),
    "literate_code": (145, 146),
    "school_attendance": (146, 147),
    "course_highest": (153, 155),
    "instruction_level": (157, 158),
    "marital_status": (193, 194),
    "occupation_code": (199, 203),
    "activity_code": (203, 208),
    "personal_income_raw": (262, 269),
    "household_income_raw": (278, 285),
    "retired_pension": (317, 318),
    "bolsa_familia": (318, 319),
    "econ_active": (390, 391),
    "occupied_status": (391, 392),
    "employment_position": (393, 394),
    "employment_subgroup": (394, 395),
    "hh_pc_income_raw": (405, 413),
    "sector_status": (539, 540),
}

FIXED_WIDTH_COLSPECS = list(FIXED_WIDTH_COLUMNS.values())
FIXED_WIDTH_NAMES = list(FIXED_WIDTH_COLUMNS.keys())


@dataclass(frozen=True)
class PromptRun:
    scenario: str
    prompt_style: str
    language: str
    model: str
    personas: list[dict]


def _ensure_dirs() -> None:
    for path in [
        RAW_IBGE_DIR,
        INTERIM_IBGE_DIR,
        AGENT_SIM_DIR,
        AGENT_SIM_FIGURES_DIR,
        AGENT_SIM_LOG_DIR,
        CODex_WORKDIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def _disable_insecure_request_warnings() -> None:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _download_file(url: str, dest: Path, timeout: int = 600) -> None:
    if dest.exists():
        if dest.suffix.lower() != ".zip" or (dest.stat().st_size > 0 and is_zipfile(dest)):
            return
        dest.unlink()

    tmp_dest = dest.with_suffix(dest.suffix + ".partial")
    if tmp_dest.exists():
        tmp_dest.unlink()
    session = requests.Session()
    with session.get(url, stream=True, timeout=timeout, verify=False) as response:
        response.raise_for_status()
        with tmp_dest.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                if chunk:
                    handle.write(chunk)
    if dest.suffix.lower() == ".zip" and not is_zipfile(tmp_dest):
        tmp_dest.unlink(missing_ok=True)
        raise ValueError(f"Downloaded file is not a valid zip archive: {dest.name}")
    tmp_dest.replace(dest)


def download_ibge_census_microdata(state_archives: list[str]) -> None:
    _disable_insecure_request_warnings()
    _download_file(DOCUMENTATION_URL, RAW_IBGE_DIR / "Documentacao.zip")

    def _download_state(state_archive: str) -> str:
        url = (
            "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2010/Resultados_Gerais_da_Amostra/Microdados/"
            + state_archive
        )
        _download_file(url, RAW_IBGE_DIR / state_archive)
        return state_archive

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_download_state, archive) for archive in state_archives]
        for future in as_completed(futures):
            future.result()


def extract_documentation_files() -> None:
    zip_path = RAW_IBGE_DIR / "Documentacao.zip"
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    wanted = [
        "Layout_microdados_Amostra.xls",
        "Descri",
        "Notas Metodol",
        "Unidades da Federa",
    ]

    with ZipFile(zip_path) as zf:
        for name in zf.namelist():
            lowered = name.lower()
            if not any(token.lower() in lowered for token in wanted):
                continue
            payload = zf.read(name)
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
            (INTERIM_IBGE_DIR / safe_name).write_bytes(payload)


def _parse_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.strip(), errors="coerce")


def _parse_decimal(series: pd.Series, decimals: int) -> pd.Series:
    numeric = pd.to_numeric(series.astype(str).str.strip(), errors="coerce")
    return numeric / (10**decimals)


def _size_tier(population: float | int | None) -> str | None:
    if population is None or pd.isna(population):
        return None
    value = float(population)
    if value < 10_000:
        return "<10k"
    if value < 50_000:
        return "10k-50k"
    if value < 200_000:
        return "50k-200k"
    return "200k+"


def _age_group(age: float | int | None) -> str | None:
    if age is None or pd.isna(age):
        return None
    value = int(age)
    if value < 18:
        return None
    if value <= 29:
        return "18-29"
    if value <= 44:
        return "30-44"
    if value <= 64:
        return "45-64"
    return "65+"


def _education_group(instruction_level: float | int | None, literate_code: float | int | None) -> str | None:
    if pd.isna(instruction_level) and pd.isna(literate_code):
        return None
    if literate_code == 2:
        return "illiterate"
    if instruction_level == 1:
        return "primary"
    if instruction_level in {2, 3}:
        return "secondary"
    if instruction_level == 4:
        return "higher"
    return None


def _occupation_category(row: pd.Series) -> str:
    if row.get("school_attendance") in {1, 2} and row.get("age", 0) <= 29:
        return "student"
    if row.get("retired_pension") == 1 and row.get("econ_active") == 2:
        return "retired"
    if row.get("occupied_status") == 2 and row.get("econ_active") == 1:
        return "unemployed"
    if row.get("econ_active") == 2:
        return "inactive_adult"

    position = row.get("employment_position")
    subgroup = row.get("employment_subgroup")
    activity_code = str(row.get("activity_code", "")).strip()

    sector = "services"
    if activity_code:
        prefix = int(activity_code[:2]) if activity_code[:2].isdigit() else None
        if prefix is not None:
            if 1 <= prefix <= 3:
                sector = "agriculture"
            elif 5 <= prefix <= 9:
                sector = "extractive_industry"
            elif 10 <= prefix <= 33:
                sector = "manufacturing"
            elif 35 <= prefix <= 39:
                sector = "utilities"
            elif 41 <= prefix <= 43:
                sector = "construction"
            elif 45 <= prefix <= 47:
                sector = "commerce"
            elif 49 <= prefix <= 53:
                sector = "transport"
            elif 55 <= prefix <= 56:
                sector = "hospitality"
            elif 58 <= prefix <= 63:
                sector = "information"
            elif 64 <= prefix <= 66:
                sector = "finance"
            elif 69 <= prefix <= 82:
                sector = "business_services"
            elif 84 <= prefix <= 84:
                sector = "public_admin"
            elif 85 <= prefix <= 88:
                sector = "education_health"
            elif 90 <= prefix <= 99:
                sector = "other_services"

    if subgroup in {1, 2}:
        return "domestic_worker"
    if position == 1:
        return f"formal_{sector}_worker"
    if position == 2:
        return "uniformed_or_public_worker"
    if position == 3:
        return f"informal_{sector}_worker"
    if position == 4:
        return f"self_employed_{sector}"
    if position == 5:
        return f"employer_{sector}"
    if position in {6, 7}:
        return "unpaid_or_self_consumption_worker"
    return "other_worker"


def _income_tier(household_income: float | None) -> str:
    if household_income is None or pd.isna(household_income):
        return "unknown"
    value = float(household_income)
    if value < 1_000:
        return "very_low"
    if value < 2_000:
        return "low"
    if value < 5_000:
        return "lower_middle"
    if value < 10_000:
        return "middle"
    return "upper_middle_plus"


def _distance_km(row: pd.Series, rng: np.random.Generator) -> int:
    urban_rural = row.get("urban_rural")
    region = row.get("region")
    size_tier = row.get("municipality_size_tier")
    sector_status = row.get("sector_status")

    if urban_rural == "urban":
        return int(rng.integers(2, 6))
    remote = (
        urban_rural == "rural"
        and (
            sector_status in {5, 6, 7, 8}
            or region in {"North", "Center-West"}
            or size_tier == "<10k"
        )
    )
    if remote:
        return int(rng.integers(32, 61))
    return int(rng.integers(10, 31))


def _distance_band(distance_km: int) -> str:
    if distance_km < 5:
        return "<5km"
    if distance_km <= 30:
        return "10-30km"
    return ">30km"


def _has_id_document(row: pd.Series) -> str:
    score = 0.90
    if row.get("education_group") == "illiterate":
        score -= 0.30
    elif row.get("education_group") == "primary":
        score -= 0.10
    if row.get("urban_rural") == "rural":
        score -= 0.15
    if row.get("income_tier") in {"very_low", "low"}:
        score -= 0.15
    if row.get("region") == "North":
        score -= 0.05
    if row.get("municipality_size_tier") == "<10k":
        score -= 0.05
    if "public" in row.get("occupation_category", "") or row.get("education_group") == "higher":
        score += 0.10
    if row.get("age_group") == "65+":
        score -= 0.05
    return "yes" if score >= 0.55 else "no"


def _format_income(value: float | int | None) -> int:
    if value is None or pd.isna(value):
        return 0
    return int(round(float(value) / 50.0) * 50)


def _prepare_chunk(chunk: pd.DataFrame, population_lookup: dict[str, float]) -> pd.DataFrame:
    frame = chunk.copy()
    frame["uf"] = frame["uf"].astype(str).str.zfill(2)
    frame["municipality_code5"] = frame["municipality_code5"].astype(str).str.zfill(5)
    frame["municipality_id"] = frame["uf"] + frame["municipality_code5"]

    frame["weight"] = _parse_decimal(frame["sample_weight_raw"], 13)
    frame["age"] = _parse_int(frame["age_raw"])
    frame["instruction_level_num"] = _parse_int(frame["instruction_level"])
    frame["literate_num"] = _parse_int(frame["literate_code"])
    frame["sex_num"] = _parse_int(frame["sex_code"])
    frame["region_num"] = _parse_int(frame["region_code"])
    frame["urban_rural_num"] = _parse_int(frame["urban_rural_code"])
    frame["occupied_status_num"] = _parse_int(frame["occupied_status"])
    frame["econ_active_num"] = _parse_int(frame["econ_active"])
    frame["employment_position_num"] = _parse_int(frame["employment_position"])
    frame["employment_subgroup_num"] = _parse_int(frame["employment_subgroup"])
    frame["school_attendance_num"] = _parse_int(frame["school_attendance"])
    frame["retired_pension_num"] = _parse_int(frame["retired_pension"])
    frame["sector_status_num"] = _parse_int(frame["sector_status"])

    frame["personal_income"] = _parse_int(frame["personal_income_raw"])
    frame["household_income"] = _parse_int(frame["household_income_raw"])
    frame["household_pc_income"] = _parse_decimal(frame["hh_pc_income_raw"], 2)

    frame["region"] = frame["region_num"].astype("Int64").astype(str).map(REGION_MAP)
    frame["sex"] = frame["sex_num"].map({1: "male", 2: "female"})
    frame["urban_rural"] = frame["urban_rural_num"].map({1: "urban", 2: "rural"})
    frame["age_group"] = frame["age"].map(_age_group)
    frame["education_group"] = [
        _education_group(inst, lit)
        for inst, lit in zip(frame["instruction_level_num"], frame["literate_num"], strict=False)
    ]
    frame["total_pop_2010"] = frame["municipality_id"].map(population_lookup)
    frame["municipality_size_tier"] = frame["total_pop_2010"].map(_size_tier)
    frame["state_name"] = frame["uf"].map(STATE_NAME_MAP)

    adult = frame[
        (frame["age_group"].notna())
        & (frame["education_group"].notna())
        & (frame["sex"].notna())
        & (frame["region"].notna())
        & (frame["municipality_size_tier"].notna())
        & frame["weight"].notna()
    ].copy()

    adult["occupation_category"] = adult.apply(
        lambda row: _occupation_category(
            pd.Series(
                {
                    "school_attendance": row["school_attendance_num"],
                    "age": row["age"],
                    "retired_pension": row["retired_pension_num"],
                    "econ_active": row["econ_active_num"],
                    "occupied_status": row["occupied_status_num"],
                    "employment_position": row["employment_position_num"],
                    "employment_subgroup": row["employment_subgroup_num"],
                    "activity_code": row["activity_code"],
                }
            )
        ),
        axis=1,
    )
    adult["income_tier"] = adult["household_income"].map(_income_tier)
    return adult


def _iter_person_chunks(zip_path: Path, chunk_size: int = 100_000) -> Iterable[pd.DataFrame]:
    with ZipFile(zip_path) as zf:
        person_file = next(name for name in zf.namelist() if "Amostra_Pessoas" in name)
        with zf.open(person_file) as handle:
            reader = pd.read_fwf(
                handle,
                colspecs=FIXED_WIDTH_COLSPECS,
                names=FIXED_WIDTH_NAMES,
                dtype=str,
                chunksize=chunk_size,
            )
            for chunk in reader:
                yield chunk


def _process_archive_person_data(
    archive: str,
    population_lookup: dict[str, float],
    archive_seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[tuple[str, ...], list[dict]]]:
    zip_path = RAW_IBGE_DIR / archive
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    rng = np.random.default_rng(archive_seed)
    candidate_store: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    municipal_counts: list[pd.DataFrame] = []
    urban_counts: list[pd.DataFrame] = []
    national_counts: list[pd.DataFrame] = []

    for chunk in _iter_person_chunks(zip_path):
        adult = _prepare_chunk(chunk, population_lookup)
        if adult.empty:
            continue

        municipal_counts.append(
            adult.groupby(MUNICIPALITY_CELL_COLS, as_index=False)["weight"].sum().rename(columns={"weight": "weighted_count"})
        )
        urban_counts.append(
            adult.groupby(["municipality_id", "urban_rural"], as_index=False)["weight"].sum().rename(columns={"weight": "weighted_count"})
        )
        national_counts.append(
            adult.groupby(PRIMARY_CELL_COLS, as_index=False)["weight"].sum().rename(columns={"weight": "weighted_count"})
        )

        for cell_key, group in adult.groupby(PRIMARY_CELL_COLS, sort=False):
            sample_n = min(2, len(group))
            sampled = group.sample(
                n=sample_n,
                replace=False,
                weights="weight",
                random_state=int(rng.integers(0, 1_000_000_000)),
            )
            candidate_store[cell_key].extend(sampled[ARCHIVE_CANDIDATE_SAMPLE_COLS].to_dict("records"))
            if len(candidate_store[cell_key]) > 40:
                combined = pd.DataFrame(candidate_store[cell_key])
                combined = combined.sample(
                    n=25,
                    replace=False,
                    weights="weight",
                    random_state=int(rng.integers(0, 1_000_000_000)),
                )
                candidate_store[cell_key] = combined.to_dict("records")

    def _combine_or_empty(parts: list[pd.DataFrame], group_cols: list[str]) -> pd.DataFrame:
        if not parts:
            return pd.DataFrame(columns=group_cols + ["weighted_count"])
        combined = pd.concat(parts, ignore_index=True)
        return combined.groupby(group_cols, as_index=False)["weighted_count"].sum()

    return (
        _combine_or_empty(municipal_counts, MUNICIPALITY_CELL_COLS),
        _combine_or_empty(urban_counts, ["municipality_id", "urban_rural"]),
        _combine_or_empty(national_counts, PRIMARY_CELL_COLS),
        dict(candidate_store),
    )


def build_personas_from_census(state_archives: list[str], persona_count: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    population = pd.read_parquet(POPULATION_PATH)
    population_2010 = (
        population.loc[population["year"] == 2010, ["municipality_id", "total_pop"]]
        .drop_duplicates("municipality_id")
        .assign(municipality_id=lambda d: d["municipality_id"].astype(str).str.zfill(7))
    )
    population_lookup = dict(zip(population_2010["municipality_id"], population_2010["total_pop"], strict=False))

    rng = np.random.default_rng(RANDOM_SEED)
    candidate_store: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    municipal_counts: list[pd.DataFrame] = []
    urban_counts: list[pd.DataFrame] = []
    national_counts: list[pd.DataFrame] = []
    archive_seeds = {
        archive: RANDOM_SEED + idx * 10_007
        for idx, archive in enumerate(state_archives, start=1)
    }
    with ThreadPoolExecutor(max_workers=min(ARCHIVE_MAX_WORKERS, len(state_archives))) as executor:
        futures = {
            executor.submit(
                _process_archive_person_data,
                archive,
                population_lookup,
                archive_seeds[archive],
            ): archive
            for archive in state_archives
        }
        for future in as_completed(futures):
            municipal_part, urban_part, national_part, candidate_part = future.result()
            if not municipal_part.empty:
                municipal_counts.append(municipal_part)
            if not urban_part.empty:
                urban_counts.append(urban_part)
            if not national_part.empty:
                national_counts.append(national_part)
            for cell_key, records in candidate_part.items():
                candidate_store[cell_key].extend(records)
                if len(candidate_store[cell_key]) > 40:
                    combined = pd.DataFrame(candidate_store[cell_key])
                    combined = combined.sample(
                        n=25,
                        replace=False,
                        weights="weight",
                        random_state=int(rng.integers(0, 1_000_000_000)),
                    )
                    candidate_store[cell_key] = combined.to_dict("records")

    municipal_comp = pd.concat(municipal_counts, ignore_index=True)
    municipal_comp = municipal_comp.groupby(MUNICIPALITY_CELL_COLS, as_index=False)["weighted_count"].sum()

    urban_comp = pd.concat(urban_counts, ignore_index=True)
    urban_comp = urban_comp.groupby(["municipality_id", "urban_rural"], as_index=False)["weighted_count"].sum()

    national_comp = pd.concat(national_counts, ignore_index=True)
    national_comp = national_comp.groupby(PRIMARY_CELL_COLS, as_index=False)["weighted_count"].sum()

    municipal_meta = (
        municipal_comp[["municipality_id"]]
        .drop_duplicates()
        .merge(population_2010, on="municipality_id", how="left")
    )
    municipality_size_lookup = {
        row["municipality_id"]: _size_tier(row["total_pop"])
        for _, row in municipal_meta.iterrows()
    }

    municipality_region_lookup = {}
    for cell in candidate_store:
        region = cell[3]
        size_tier = cell[4]
        # region and size are cell specific; municipality region will be assigned later by TSE panel merge.
        if size_tier is None or region is None:
            continue

    totals = municipal_comp.groupby("municipality_id", as_index=False)["weighted_count"].sum().rename(columns={"weighted_count": "municipality_adult_total"})
    municipal_comp = municipal_comp.merge(totals, on="municipality_id", how="left")
    municipal_comp["share"] = municipal_comp["weighted_count"] / municipal_comp["municipality_adult_total"]

    urban_totals = urban_comp.groupby("municipality_id", as_index=False)["weighted_count"].sum().rename(columns={"weighted_count": "urban_total"})
    urban_comp = urban_comp.merge(urban_totals, on="municipality_id", how="left")
    urban_comp["share"] = urban_comp["weighted_count"] / urban_comp["urban_total"]

    all_cells = [(e, a, s, r, m) for e in EDUCATION_LEVELS for a in AGE_GROUPS for s in SEX_GROUPS for r in REGION_GROUPS for m in SIZE_TIERS]
    base_per_cell = persona_count // len(all_cells)
    extra = persona_count - base_per_cell * len(all_cells)
    extra_cells = set(rng.choice(len(all_cells), size=extra, replace=False).tolist())

    all_candidates = []
    for cell_records in candidate_store.values():
        all_candidates.extend(cell_records)
    all_candidates_df = pd.DataFrame(all_candidates)

    personas: list[dict] = []
    persona_counter = 1
    for idx, cell in enumerate(all_cells):
        target_n = base_per_cell + (1 if idx in extra_cells else 0)
        records = candidate_store.get(cell, [])
        pool = pd.DataFrame(records)
        if pool.empty:
            broader = all_candidates_df.copy()
            for col_name, col_value in zip(PRIMARY_CELL_COLS[:-1], cell[:-1], strict=False):
                broader = broader.loc[broader[col_name] == col_value]
            if broader.empty:
                broader = all_candidates_df.copy()
            pool = broader

        replace = len(pool) < target_n
        sampled = pool.sample(
            n=target_n,
            replace=replace,
            weights="weight" if "weight" in pool.columns else None,
            random_state=int(rng.integers(0, 1_000_000_000)),
        ).copy()

        for _, row in sampled.iterrows():
            persona = row.to_dict()
            persona["persona_id"] = f"p{persona_counter:04d}"
            persona_counter += 1
            persona["distance_to_cartorio_km"] = _distance_km(
                pd.Series(
                    {
                        "urban_rural": persona["urban_rural"],
                        "region": persona["region"],
                        "municipality_size_tier": persona["municipality_size_tier"],
                        "sector_status": persona.get("sector_status_num"),
                    }
                ),
                rng,
            )
            persona["distance_to_cartorio_band"] = _distance_band(persona["distance_to_cartorio_km"])
            persona["has_id_document"] = _has_id_document(pd.Series(persona))
            persona["household_income_reais"] = _format_income(persona.get("household_income"))
            persona["personal_income_reais"] = _format_income(persona.get("personal_income"))
            personas.append(persona)

    personas_df = pd.DataFrame(personas)
    personas_df = personas_df[
        [
            "persona_id",
            "municipality_id",
            "state_name",
            "region",
            "municipality_size_tier",
            "urban_rural",
            "age",
            "age_group",
            "sex",
            "education_group",
            "occupation_category",
            "income_tier",
            "household_income_reais",
            "personal_income_reais",
            "has_id_document",
            "distance_to_cartorio_km",
            "distance_to_cartorio_band",
            "weight",
        ]
    ].copy()
    personas_df.to_parquet(PERSONAS_PATH, index=False)
    return personas_df, municipal_comp, urban_comp


def _persona_text(persona: dict, style: str, language: str, scenario: str) -> str:
    age = int(persona["age"])
    sex = persona["sex"]
    area = persona["urban_rural"]
    state = persona["state_name"]
    education = persona["education_group"]
    occupation = persona["occupation_category"].replace("_", " ")
    income = int(persona["household_income_reais"])
    distance = int(persona["distance_to_cartorio_km"])
    id_doc = persona["has_id_document"]

    baseline_scenario = (
        "The government has announced that every voter in your municipality must visit the cartorio eleitoral "
        "in person within the next 12 months to register fingerprints, take a new photo, and update the voter ID. "
        "If you do not comply, your voter registration will be cancelled and you will be unable to vote in the next election. "
        "Voting is legally compulsory in Brazil and failure to vote without justification can trigger a fine and restrictions on issuing passports or taking public-sector jobs."
    )
    counterfactual_scenario = (
        "The government has announced a voluntary biometric update. Voters can visit the cartorio eleitoral "
        "to register fingerprints, take a new photo, and update the voter ID, but they are not forced to do so. "
        "Anyone who completes the update receives a small tax credit. People who do not comply keep their voter registration and can still vote."
    )
    scenario_text = baseline_scenario if scenario == "baseline" else counterfactual_scenario

    if language == "pt":
        intro = (
            f"Voce e uma pessoa de {age} anos, {sex}, morando em area {area} de {state}, Brasil. "
            f"Tem escolaridade {education}, trabalha como {occupation}, a renda familiar mensal aproximada e R$ {income}, "
            f"possui documento de identidade: {id_doc}, e o cartorio eleitoral mais proximo fica a cerca de {distance} km."
        )
    else:
        intro = (
            f"You are a {age}-year-old {sex} living in a {area} area of {state}, Brazil. "
            f"You have {education} education, work as a {occupation}, your household income is approximately R$ {income} per month, "
            f"you currently {'do' if id_doc == 'yes' else 'do not'} have an identity document, and the nearest electoral office is about {distance} km away."
        )

    task_line = (
        "Decide whether this voter will comply. Think about transportation cost, time away from work, childcare or household duties, "
        "bureaucratic difficulty, the cost of losing the right to vote, and trust in the electoral system."
    )
    if scenario != "baseline":
        task_line += " Compare the lower compliance burden to the incentive created by the small tax credit."

    if style == "minimal":
        return textwrap.dedent(
            f"""
            Persona {persona['persona_id']}:
            {intro}
            {scenario_text}
            {task_line}
            Return a JSON object with persona_id, decision, main_barriers, reasoning, confidence.
            Use exactly one decision label: will_register_immediately, will_register_eventually, probably_wont_register.
            """
        ).strip()

    if style == "persona_driven":
        return textwrap.dedent(
            f"""
            Persona {persona['persona_id']}:
            {intro}
            {scenario_text}
            Imagine the practical details of this person's week before you answer. Do not assume perfect information, abundant cash, or frictionless transport.
            Think through:
            1. transport and travel time
            2. ability to miss work or other obligations
            3. whether the legal penalty feels serious enough to motivate action
            4. whether this person procrastinates, eventually complies, or never gets there
            Return a JSON object with persona_id, decision, main_barriers, reasoning, confidence.
            Use exactly one decision label: will_register_immediately, will_register_eventually, probably_wont_register.
            """
        ).strip()

    return textwrap.dedent(
        f"""
        Persona {persona['persona_id']}:
        {intro}
        {scenario_text}
        Will this person make the trip to re-register?
        Think step by step about:
        1. practical barriers such as transportation, time off work, childcare, and bureaucratic literacy
        2. the cost of non-compliance such as fines and document restrictions
        3. trust in the electoral system
        4. whether the person goes immediately, delays, or probably never goes
        Return a JSON object with persona_id, decision, main_barriers, reasoning, confidence.
        Use exactly one decision label: will_register_immediately, will_register_eventually, probably_wont_register.
        """
    ).strip()


def _batch_prompt(personas: list[dict], style: str, language: str, scenario: str) -> str:
    system = (
        "SYSTEM:\n"
        "You are simulating the decision-making of specific Brazilian voters. Think carefully about what someone with each profile "
        "would actually do, given real-world barriers like transportation cost, time off work, information access, and bureaucratic literacy. "
        "Do not impose idealized rational-choice reasoning. Evaluate each persona independently and return only valid JSON.\n"
    )
    user_header = (
        "USER:\n"
        "Return a JSON array. Each array item must contain exactly these fields: persona_id, decision, main_barriers, reasoning, confidence.\n"
        "Use exactly one of these decision labels for every persona: will_register_immediately, will_register_eventually, probably_wont_register.\n"
    )
    body = "\n\n".join(_persona_text(persona, style=style, language=language, scenario=scenario) for persona in personas)
    return system + "\n" + user_header + "\n" + body


def _normalize_decision(decision: str) -> str:
    raw = (decision or "").strip().lower()
    raw = raw.replace("-", "_").replace(" ", "_")
    if raw in {"will_register_immediately", "register_immediately", "comply_immediately"}:
        return "will_register_immediately"
    if raw in {
        "will_register_eventually",
        "register_eventually",
        "eventually_register",
        "delay_then_register",
        "delayed_compliance",
    }:
        return "will_register_eventually"
    if raw in {
        "probably_wont_register",
        "probably_won_t_register",
        "will_not_register",
        "not_comply",
        "won_t_comply",
        "won_t_register",
        "probably_not_register",
    }:
        return "probably_wont_register"

    if "immediate" in raw or "right_away" in raw:
        return "will_register_immediately"
    if "eventual" in raw or "delay" in raw or "later" in raw:
        return "will_register_eventually"
    if "not" in raw or "won" in raw or "unlikely" in raw:
        return "probably_wont_register"
    return "will_register_eventually"


def _decision_to_dropout(decision: str) -> float:
    normalized = _normalize_decision(decision)
    if normalized == "will_register_immediately":
        return 0.0
    if normalized == "will_register_eventually":
        return 0.3
    return 1.0


def _extract_json_array(text: str) -> list[dict]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\[\s*\{.*\}\s*\])", cleaned, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(1))
    if not isinstance(payload, list):
        raise ValueError("Expected a JSON array from Codex batch response.")
    return payload


def _batch_cache_key(run: PromptRun, batch_index: int) -> str:
    payload = {
        "scenario": run.scenario,
        "prompt_style": run.prompt_style,
        "language": run.language,
        "model": run.model,
        "batch_index": batch_index,
        "persona_ids": [persona["persona_id"] for persona in run.personas],
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.md5(serialized.encode("utf-8")).hexdigest()[:12]


def _parse_batch_payload(
    payload: list[dict],
    run: PromptRun,
    batch_index: int,
    runtime: float,
) -> list[dict]:
    expected_ids = {persona["persona_id"] for persona in run.personas}
    rows = []
    seen_ids = set()
    for item in payload:
        persona_id = item.get("persona_id")
        if persona_id not in expected_ids:
            continue
        seen_ids.add(persona_id)
        rows.append(
            {
                "persona_id": persona_id,
                "scenario": run.scenario,
                "prompt_style": run.prompt_style,
                "language": run.language,
                "model": run.model,
                "decision_raw": item.get("decision", ""),
                "decision": _normalize_decision(item.get("decision", "")),
                "main_barriers": json.dumps(item.get("main_barriers", []), ensure_ascii=False),
                "reasoning": item.get("reasoning", ""),
                "confidence": float(item.get("confidence", np.nan)),
                "predicted_dropout": _decision_to_dropout(item.get("decision", "")),
                "batch_index": batch_index,
                "batch_runtime_seconds": runtime,
            }
        )
    missing_ids = expected_ids - seen_ids
    if missing_ids:
        raise ValueError(
            f"Missing personas in batch response: expected {len(expected_ids)}, got {len(seen_ids)}. "
            f"Missing IDs include {sorted(missing_ids)[:5]}"
        )
    return rows


def _run_codex_batch(run: PromptRun, batch_index: int) -> list[dict]:
    prompt = _batch_prompt(run.personas, style=run.prompt_style, language=run.language, scenario=run.scenario)
    cache_key = _batch_cache_key(run, batch_index)
    output_path = AGENT_SIM_LOG_DIR / (
        f"codex_output_{run.scenario}_{run.prompt_style}_{run.language}_{run.model}_{batch_index:04d}_{cache_key}.json"
    )
    stderr_path = output_path.with_suffix(".stderr.txt")

    if output_path.exists():
        payload = _extract_json_array(output_path.read_text(encoding="utf-8"))
        return _parse_batch_payload(payload, run, batch_index=batch_index, runtime=np.nan)

    cmd = [
        "codex",
        "exec",
        "-C",
        str(CODex_WORKDIR),
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--model",
        run.model,
        "-o",
        str(output_path),
        prompt,
    ]
    last_error = None
    for attempt in range(1, 4):
        started = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        runtime = time.time() - started
        stderr_path.write_text(result.stderr or "", encoding="utf-8")
        if result.returncode != 0:
            last_error = RuntimeError(
                f"Codex batch failed for scenario={run.scenario}, style={run.prompt_style}, language={run.language}, "
                f"model={run.model}, batch={batch_index}, attempt={attempt}: {result.stderr[-2000:]}"
            )
            time.sleep(1.0 * attempt)
            continue
        try:
            payload = _extract_json_array(output_path.read_text(encoding="utf-8"))
            return _parse_batch_payload(payload, run, batch_index=batch_index, runtime=runtime)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if output_path.exists():
                output_path.unlink()
            time.sleep(1.0 * attempt)
    raise RuntimeError(
        f"Unable to recover valid batch output after retries for scenario={run.scenario}, "
        f"style={run.prompt_style}, language={run.language}, model={run.model}, batch={batch_index}. "
        f"Last error: {last_error}"
    )


def run_agent_batches(
    personas_df: pd.DataFrame,
    batch_size: int,
    validation_count: int,
    max_workers: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    persona_records = personas_df.to_dict("records")
    main_batches = [
        PromptRun(
            scenario="baseline",
            prompt_style=BASELINE_PROMPT_STYLE,
            language="en",
            model=MAIN_MODEL,
            personas=persona_records[i : i + batch_size],
        )
        for i in range(0, len(persona_records), batch_size)
    ]

    validation_count = min(validation_count, len(personas_df))
    validation_ids = set(rng.choice(personas_df["persona_id"].to_numpy(), size=validation_count, replace=False).tolist())
    validation_personas = [record for record in persona_records if record["persona_id"] in validation_ids]
    validation_batches = [
        PromptRun(
            scenario="baseline",
            prompt_style=BASELINE_PROMPT_STYLE,
            language="en",
            model=VALIDATION_MODEL,
            personas=validation_personas[i : i + batch_size],
        )
        for i in range(0, len(validation_personas), batch_size)
    ]

    sensitivity_runs: list[PromptRun] = []
    for style in ["minimal", "persona_driven"]:
        sensitivity_runs.extend(
            [
                PromptRun(
                    scenario="baseline",
                    prompt_style=style,
                    language="en",
                    model=MAIN_MODEL,
                    personas=validation_personas[i : i + batch_size],
                )
                for i in range(0, len(validation_personas), batch_size)
            ]
        )

    portuguese_runs = [
        PromptRun(
            scenario="baseline",
            prompt_style=BASELINE_PROMPT_STYLE,
            language="pt",
            model=MAIN_MODEL,
            personas=validation_personas[i : i + batch_size],
        )
        for i in range(0, len(validation_personas), batch_size)
    ]

    counterfactual_runs = [
        PromptRun(
            scenario="voluntary_tax_credit",
            prompt_style=BASELINE_PROMPT_STYLE,
            language="en",
            model=MAIN_MODEL,
            personas=validation_personas[i : i + batch_size],
        )
        for i in range(0, len(validation_personas), batch_size)
    ]

    all_runs = main_batches + validation_batches + sensitivity_runs + portuguese_runs + counterfactual_runs

    responses: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_codex_batch, run, idx): (run, idx)
            for idx, run in enumerate(all_runs, start=1)
        }
        for future in as_completed(futures):
            responses.extend(future.result())

    responses_df = pd.DataFrame(responses)
    responses_df = responses_df.merge(
        personas_df,
        on="persona_id",
        how="left",
        validate="m:1",
    )
    responses_df.to_parquet(RESPONSES_PATH, index=False)
    return responses_df


def build_municipality_predictions(
    personas_df: pd.DataFrame,
    responses_df: pd.DataFrame,
    municipal_comp: pd.DataFrame,
    urban_comp: pd.DataFrame,
) -> pd.DataFrame:
    main_responses = responses_df[
        (responses_df["scenario"] == "baseline")
        & (responses_df["prompt_style"] == BASELINE_PROMPT_STYLE)
        & (responses_df["language"] == "en")
        & (responses_df["model"] == MAIN_MODEL)
    ].copy()

    cell_predictions = (
        main_responses.groupby(PRIMARY_CELL_COLS, as_index=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "cell_predicted_dropout": np.average(frame["predicted_dropout"], weights=frame["weight"]),
                    "cell_mean_confidence": np.average(frame["confidence"].fillna(0.5), weights=frame["weight"]),
                }
            )
        )
        .reset_index(drop=True)
    )

    population = pd.read_parquet(POPULATION_PATH)
    population_2010 = (
        population.loc[population["year"] == 2010, ["municipality_id", "total_pop"]]
        .drop_duplicates("municipality_id")
        .assign(municipality_id=lambda d: d["municipality_id"].astype(str).str.zfill(7))
    )

    municipal_meta = (
        population_2010.assign(
            municipality_size_tier=lambda d: d["total_pop"].map(_size_tier),
            state=lambda d: d["municipality_id"].str[:2].map(STATE_ABBR_MAP),
        )
    )

    state_region_lookup = {
        "RO": "North",
        "AC": "North",
        "AM": "North",
        "RR": "North",
        "PA": "North",
        "AP": "North",
        "TO": "North",
        "MA": "Northeast",
        "PI": "Northeast",
        "CE": "Northeast",
        "RN": "Northeast",
        "PB": "Northeast",
        "PE": "Northeast",
        "AL": "Northeast",
        "SE": "Northeast",
        "BA": "Northeast",
        "MG": "Southeast",
        "ES": "Southeast",
        "RJ": "Southeast",
        "SP": "Southeast",
        "PR": "South",
        "SC": "South",
        "RS": "South",
        "MS": "Center-West",
        "MT": "Center-West",
        "GO": "Center-West",
        "DF": "Center-West",
    }
    municipal_meta["region"] = municipal_meta["state"].map(state_region_lookup)

    municipal_comp = municipal_comp.merge(municipal_meta[["municipality_id", "region", "municipality_size_tier"]], on="municipality_id", how="left")
    municipal_comp = municipal_comp.merge(cell_predictions, on=PRIMARY_CELL_COLS, how="left")

    municipality_pred = (
        municipal_comp.groupby("municipality_id", as_index=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "predicted_dropout_rate": np.sum(frame["share"] * frame["cell_predicted_dropout"]),
                }
            )
        )
        .reset_index(drop=True)
    )

    low_pred = (
        municipal_comp.loc[municipal_comp["education_group"].isin(["illiterate", "primary"])]
        .groupby("municipality_id", as_index=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "predicted_dropout_low_ed": np.average(
                        frame["cell_predicted_dropout"],
                        weights=frame["weighted_count"],
                    ),
                }
            )
        )
        .reset_index(drop=True)
    )
    high_pred = (
        municipal_comp.loc[municipal_comp["education_group"].isin(["secondary", "higher"])]
        .groupby("municipality_id", as_index=False)
        .apply(
            lambda frame: pd.Series(
                {
                    "predicted_dropout_high_ed": np.average(
                        frame["cell_predicted_dropout"],
                        weights=frame["weighted_count"],
                    ),
                }
            )
        )
        .reset_index(drop=True)
    )

    urban_summary = (
        urban_comp.pivot_table(index="municipality_id", columns="urban_rural", values="weighted_count", fill_value=0.0)
        .reset_index()
        .rename_axis(columns=None)
    )
    for col in ["urban", "rural"]:
        if col not in urban_summary.columns:
            urban_summary[col] = 0.0
    urban_summary["rural_share_adult"] = urban_summary["rural"] / (urban_summary["urban"] + urban_summary["rural"])
    urban_summary["urban_rural_type"] = np.where(urban_summary["rural_share_adult"] >= 0.5, "Rural-majority", "Urban-majority")

    municipality_pred = (
        municipal_meta.merge(municipality_pred, on="municipality_id", how="left")
        .merge(low_pred, on="municipality_id", how="left")
        .merge(high_pred, on="municipality_id", how="left")
        .merge(urban_summary[["municipality_id", "rural_share_adult", "urban_rural_type"]], on="municipality_id", how="left")
    )
    municipality_pred.to_parquet(MUNICIPALITY_PRED_PATH, index=False)
    return municipality_pred


def _weighted_corr(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    mx = np.average(x, weights=w)
    my = np.average(y, weights=w)
    cov = np.average((x - mx) * (y - my), weights=w)
    vx = np.average((x - mx) ** 2, weights=w)
    vy = np.average((y - my) ** 2, weights=w)
    if vx <= 0 or vy <= 0:
        return np.nan
    return cov / math.sqrt(vx * vy)


def build_validation_dataset(municipality_pred: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    panel = pd.read_parquet(TSE_PANEL_PATH).copy()
    panel["municipality_id"] = panel["municipality_id"].astype(str).str.zfill(7)

    treated = panel.loc[panel["year_treated"] < 9999].copy()
    baseline = treated.loc[treated["dist_treatment"] == -2].copy()
    impact = treated.loc[treated["dist_treatment"] == 0].copy()
    observed = impact.merge(
        baseline[
            [
                "municipality_id",
                "log_num_voters",
                "pct_voters_low_ed",
                "pct_voters_high_ed",
                "num_voters",
                "state",
            ]
        ].rename(
            columns={
                "log_num_voters": "log_num_voters_pre",
                "pct_voters_low_ed": "pct_voters_low_ed_pre",
                "pct_voters_high_ed": "pct_voters_high_ed_pre",
                "num_voters": "num_voters_pre",
                "state": "state_pre",
            }
        ),
        on="municipality_id",
        how="inner",
        validate="1:1",
    )
    observed["observed_dropout_rate"] = 1.0 - np.exp(observed["log_num_voters"] - observed["log_num_voters_pre"])
    observed["observed_low_ed_share_change"] = observed["pct_voters_low_ed"] - observed["pct_voters_low_ed_pre"]
    observed["observed_high_ed_share_change"] = observed["pct_voters_high_ed"] - observed["pct_voters_high_ed_pre"]
    observed["pre_voters_weight"] = observed["num_voters_pre"]

    merged = municipality_pred.rename(columns={"state": "state_municipality", "region": "region_municipality"}).merge(
        observed,
        on="municipality_id",
        how="inner",
    )
    merged = merged.dropna(subset=["predicted_dropout_rate", "observed_dropout_rate"]).copy()
    if merged.empty:
        raise ValueError("No municipality observations with both predicted and observed dropout are available.")
    state_source = merged["state"] if "state" in merged.columns else merged["state_municipality"]
    merged["region"] = state_source.map(
        {
            "RO": "North",
            "AC": "North",
            "AM": "North",
            "RR": "North",
            "PA": "North",
            "AP": "North",
            "TO": "North",
            "MA": "Northeast",
            "PI": "Northeast",
            "CE": "Northeast",
            "RN": "Northeast",
            "PB": "Northeast",
            "PE": "Northeast",
            "AL": "Northeast",
            "SE": "Northeast",
            "BA": "Northeast",
            "MG": "Southeast",
            "ES": "Southeast",
            "RJ": "Southeast",
            "SP": "Southeast",
            "PR": "South",
            "SC": "South",
            "RS": "South",
            "MS": "Center-West",
            "MT": "Center-West",
            "GO": "Center-West",
            "DF": "Center-West",
        }
    )

    corr = merged["predicted_dropout_rate"].corr(merged["observed_dropout_rate"])
    weighted_corr = _weighted_corr(
        merged["predicted_dropout_rate"].to_numpy(),
        merged["observed_dropout_rate"].to_numpy(),
        merged["pre_voters_weight"].to_numpy(),
    )

    if merged["predicted_dropout_rate"].nunique() >= 2:
        fit = np.polyfit(merged["predicted_dropout_rate"], merged["observed_dropout_rate"], deg=1)
        fitted = np.polyval(fit, merged["predicted_dropout_rate"])
        total_ss = np.sum((merged["observed_dropout_rate"] - merged["observed_dropout_rate"].mean()) ** 2)
        r2 = 1.0 - np.sum((merged["observed_dropout_rate"] - fitted) ** 2) / total_ss if total_ss > 0 else np.nan
        scatter_slope = float(fit[0])
        scatter_intercept = float(fit[1])
    else:
        scatter_slope = np.nan
        scatter_intercept = np.nan
        r2 = np.nan

    validation_metrics = {
        "n_municipalities": int(len(merged)),
        "corr_unweighted": float(corr),
        "corr_weighted": float(weighted_corr),
        "scatter_slope": scatter_slope,
        "scatter_intercept": scatter_intercept,
        "scatter_r2": float(r2),
        "mean_predicted_dropout": float(merged["predicted_dropout_rate"].mean()),
        "mean_observed_dropout": float(merged["observed_dropout_rate"].mean()),
        "mean_predicted_dropout_low_ed": float(merged["predicted_dropout_low_ed"].mean()),
        "mean_predicted_dropout_high_ed": float(merged["predicted_dropout_high_ed"].mean()),
    }
    return merged, validation_metrics


def build_education_gradient_metrics(validation_df: pd.DataFrame) -> dict:
    merged = validation_df.copy()
    merged = merged.dropna(
        subset=[
            "predicted_dropout_low_ed",
            "predicted_dropout_high_ed",
            "pct_voters_low_ed_pre",
            "pct_voters_high_ed_pre",
            "pre_voters_weight",
        ]
    ).copy()
    if merged.empty:
        return {
            "pred_low_share_change_mean": np.nan,
            "observed_low_share_change_mean": np.nan,
            "paper_event_study_benchmark": -0.089,
        }
    merged["pred_low_post_share"] = (
        merged["pct_voters_low_ed_pre"] * (1.0 - merged["predicted_dropout_low_ed"])
    ) / (
        merged["pct_voters_low_ed_pre"] * (1.0 - merged["predicted_dropout_low_ed"])
        + merged["pct_voters_high_ed_pre"] * (1.0 - merged["predicted_dropout_high_ed"])
    )
    merged["pred_low_share_change"] = merged["pred_low_post_share"] - merged["pct_voters_low_ed_pre"]

    return {
        "pred_low_share_change_mean": float(np.average(merged["pred_low_share_change"], weights=merged["pre_voters_weight"])),
        "observed_low_share_change_mean": float(np.average(merged["observed_low_ed_share_change"], weights=merged["pre_voters_weight"])),
        "paper_event_study_benchmark": -0.089,
    }


def build_prompt_sensitivity_metrics(responses_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    validation_subset = responses_df[
        (responses_df["scenario"] == "baseline")
        & (responses_df["language"] == "en")
        & (responses_df["model"] == MAIN_MODEL)
        & (responses_df["prompt_style"].isin(PROMPT_STYLES))
    ].copy()

    baseline = validation_subset.loc[validation_subset["prompt_style"] == BASELINE_PROMPT_STYLE, ["persona_id", "decision", "predicted_dropout"]]
    baseline = baseline.rename(columns={"decision": "baseline_decision", "predicted_dropout": "baseline_dropout"})
    sensitivity = validation_subset.merge(baseline, on="persona_id", how="left")
    sensitivity["same_as_baseline"] = (sensitivity["decision"] == sensitivity["baseline_decision"]).astype(int)

    summary = (
        sensitivity.groupby("prompt_style", as_index=False)
        .agg(
            mean_dropout=("predicted_dropout", "mean"),
            mean_confidence=("confidence", "mean"),
            decision_agreement_with_baseline=("same_as_baseline", "mean"),
            n=("persona_id", "nunique"),
        )
        .sort_values("prompt_style")
        .reset_index(drop=True)
    )

    counterfactual = responses_df[
        (responses_df["scenario"] == "voluntary_tax_credit")
        & (responses_df["language"] == "en")
        & (responses_df["model"] == MAIN_MODEL)
        & (responses_df["prompt_style"] == BASELINE_PROMPT_STYLE)
    ]
    portuguese = responses_df[
        (responses_df["scenario"] == "baseline")
        & (responses_df["language"] == "pt")
        & (responses_df["model"] == MAIN_MODEL)
        & (responses_df["prompt_style"] == BASELINE_PROMPT_STYLE)
    ]
    high_quality = responses_df[
        (responses_df["scenario"] == "baseline")
        & (responses_df["language"] == "en")
        & (responses_df["model"] == VALIDATION_MODEL)
        & (responses_df["prompt_style"] == BASELINE_PROMPT_STYLE)
    ]
    main_validation = responses_df[
        (responses_df["scenario"] == "baseline")
        & (responses_df["language"] == "en")
        & (responses_df["model"] == MAIN_MODEL)
        & (responses_df["prompt_style"] == BASELINE_PROMPT_STYLE)
        & (responses_df["persona_id"].isin(high_quality["persona_id"]))
    ]

    comparison = main_validation.merge(
        high_quality[["persona_id", "decision", "predicted_dropout"]].rename(
            columns={"decision": "hq_decision", "predicted_dropout": "hq_dropout"}
        ),
        on="persona_id",
        how="inner",
    )
    comparison["hq_agreement"] = (comparison["decision"] == comparison["hq_decision"]).astype(int)

    pt_compare = main_validation.merge(
        portuguese[["persona_id", "decision", "predicted_dropout"]].rename(
            columns={"decision": "pt_decision", "predicted_dropout": "pt_dropout"}
        ),
        on="persona_id",
        how="inner",
    )
    pt_compare["pt_agreement"] = (pt_compare["decision"] == pt_compare["pt_decision"]).astype(int)

    metrics = {
        "counterfactual_mean_dropout": float(counterfactual["predicted_dropout"].mean()),
        "baseline_validation_mean_dropout": float(main_validation["predicted_dropout"].mean()),
        "portuguese_mean_dropout": float(portuguese["predicted_dropout"].mean()),
        "portuguese_agreement": float(pt_compare["pt_agreement"].mean()),
        "high_quality_mean_dropout": float(high_quality["predicted_dropout"].mean()),
        "high_quality_agreement": float(comparison["hq_agreement"].mean()),
    }
    return summary, metrics


def plot_predicted_vs_observed(validation_df: pd.DataFrame, metrics: dict) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 4.75))
    x = validation_df["predicted_dropout_rate"].to_numpy()
    y = validation_df["observed_dropout_rate"].to_numpy()
    ax.scatter(x, y, s=16, alpha=0.45, color="#335C67")
    slope = metrics["scatter_slope"]
    intercept = metrics["scatter_intercept"]
    xs = np.linspace(float(np.nanmin(x)), float(np.nanmax(x)), 100)
    ax.plot(xs, slope * xs + intercept, color="#9E2A2B", linewidth=2)
    ax.set_xlabel("Predicted dropout rate (LLM personas)")
    ax.set_ylabel("Observed dropout rate at first BVR election")
    ax.set_title("Predicted vs observed BVR dropout")
    ax.text(
        0.04,
        0.96,
        f"r = {metrics['corr_unweighted']:.3f}\nR^2 = {metrics['scatter_r2']:.3f}",
        transform=ax.transAxes,
        va="top",
        ha="left",
        bbox={"facecolor": "white", "edgecolor": "0.85"},
    )
    ax.grid(alpha=0.2, linestyle=":")
    fig.tight_layout()
    fig.savefig(SCATTER_FIGURE_PATH, bbox_inches="tight")
    plt.close(fig)


def plot_education_gradient(validation_df: pd.DataFrame, edu_metrics: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.5))
    axes[0].bar(
        ["Low education", "High education"],
        [
            validation_df["predicted_dropout_low_ed"].mean(),
            validation_df["predicted_dropout_high_ed"].mean(),
        ],
        color=["#8D6A9F", "#2A9D8F"],
    )
    axes[0].set_ylabel("Predicted dropout rate")
    axes[0].set_title("LLM-predicted dropout by education")

    axes[1].bar(
        ["Predicted", "Observed", "Paper benchmark"],
        [
            edu_metrics["pred_low_share_change_mean"],
            edu_metrics["observed_low_share_change_mean"],
            edu_metrics["paper_event_study_benchmark"],
        ],
        color=["#335C67", "#9E2A2B", "#6C757D"],
    )
    axes[1].axhline(0, color="black", linewidth=1, linestyle="--", alpha=0.7)
    axes[1].set_ylabel("Change in low-education share")
    axes[1].set_title("Low-education share change")
    fig.tight_layout()
    fig.savefig(EDUCATION_FIGURE_PATH, bbox_inches="tight")
    plt.close(fig)


def plot_regional_heterogeneity(validation_df: pd.DataFrame) -> None:
    region_df = (
        validation_df.groupby("region", as_index=False)
        .agg(
            predicted=("predicted_dropout_rate", "mean"),
            observed=("observed_dropout_rate", "mean"),
        )
        .sort_values("region")
    )
    urban_df = (
        validation_df.groupby("urban_rural_type", as_index=False)
        .agg(
            predicted=("predicted_dropout_rate", "mean"),
            observed=("observed_dropout_rate", "mean"),
        )
        .sort_values("urban_rural_type")
    )

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.75))
    x = np.arange(len(region_df))
    width = 0.38
    axes[0].bar(x - width / 2, region_df["predicted"], width=width, label="Predicted", color="#335C67")
    axes[0].bar(x + width / 2, region_df["observed"], width=width, label="Observed", color="#9E2A2B")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(region_df["region"], rotation=30, ha="right")
    axes[0].set_ylabel("Dropout rate")
    axes[0].set_title("Regional heterogeneity")
    axes[0].legend(frameon=False)

    x2 = np.arange(len(urban_df))
    axes[1].bar(x2 - width / 2, urban_df["predicted"], width=width, label="Predicted", color="#335C67")
    axes[1].bar(x2 + width / 2, urban_df["observed"], width=width, label="Observed", color="#9E2A2B")
    axes[1].set_xticks(x2)
    axes[1].set_xticklabels(urban_df["urban_rural_type"])
    axes[1].set_ylabel("Dropout rate")
    axes[1].set_title("Urban-rural heterogeneity")
    axes[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(REGIONAL_FIGURE_PATH, bbox_inches="tight")
    plt.close(fig)


def write_validation_table(metrics: dict, edu_metrics: dict, validation_df: pd.DataFrame, sensitivity_metrics: dict) -> None:
    region_bias = (
        validation_df.assign(residual=lambda d: d["predicted_dropout_rate"] - d["observed_dropout_rate"])
        .groupby("region", as_index=False)["residual"]
        .mean()
        .sort_values("region")
    )
    north_bias = float(region_bias.loc[region_bias["region"] == "North", "residual"].iloc[0]) if "North" in region_bias["region"].tolist() else np.nan

    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lc}",
        r"\doubletoprule",
        r"Statistic & Value \\",
        r"\midrule",
        rf"Municipalities in validation sample & {metrics['n_municipalities']:,} \\",
        rf"Predicted-observed correlation & {metrics['corr_unweighted']:.3f} \\",
        rf"Population-weighted correlation & {metrics['corr_weighted']:.3f} \\",
        rf"Scatter-plot $R^2$ & {metrics['scatter_r2']:.3f} \\",
        rf"Mean predicted dropout rate & {metrics['mean_predicted_dropout']:.3f} \\",
        rf"Mean observed dropout rate & {metrics['mean_observed_dropout']:.3f} \\",
        rf"Mean predicted dropout, low education & {metrics['mean_predicted_dropout_low_ed']:.3f} \\",
        rf"Mean predicted dropout, high education & {metrics['mean_predicted_dropout_high_ed']:.3f} \\",
        rf"Implied low-education share change & {edu_metrics['pred_low_share_change_mean']:.3f} \\",
        rf"Observed low-education share change & {edu_metrics['observed_low_share_change_mean']:.3f} \\",
        rf"Paper benchmark low-education share change & {edu_metrics['paper_event_study_benchmark']:.3f} \\",
        rf"North-region prediction residual & {north_bias:.3f} \\",
        rf"High-quality-model agreement (200-persona subsample) & {sensitivity_metrics['high_quality_agreement']:.3f} \\",
        r"\doublebottomrule",
        r"\end{tabular*}",
        "",
        r"\begin{minipage}{\textwidth}",
        r"\footnotesize",
        r"\textbf{Note:} Observed dropout is the municipality-specific change in the log number of registered voters between event time $-2$ and event time $0$, converted to a proportional drop as $1 - \exp(\Delta \log V)$. The implied low-education share change uses LLM-predicted low- and high-education dropout rates together with pre-treatment TSE education shares. The high-quality-model agreement compares the main `gpt-5.4-mini` batch to a 200-persona `gpt-5.4` validation subsample.",
        r"\end{minipage}",
    ]
    VALIDATION_TABLE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_prompt_sensitivity_table(summary: pd.DataFrame, metrics: dict) -> None:
    style_order = {"minimal": "Minimal", "detailed": "Detailed", "persona_driven": "Persona-driven"}
    summary = summary.copy()
    summary["label"] = summary["prompt_style"].map(style_order)
    summary = summary.sort_values("prompt_style")

    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lccc}",
        r"\doubletoprule",
        r"Prompt style & Mean predicted dropout & Mean confidence & Agreement with detailed baseline \\",
        r"\midrule",
    ]
    for _, row in summary.iterrows():
        lines.append(
            rf"{row['label']} & {row['mean_dropout']:.3f} & {row['mean_confidence']:.3f} & {row['decision_agreement_with_baseline']:.3f} \\"
        )
    lines.extend(
        [
            r"\midrule",
            rf"Portuguese mean predicted dropout & {metrics['portuguese_mean_dropout']:.3f} &  & {metrics['portuguese_agreement']:.3f} \\",
            rf"Voluntary-plus-tax-credit mean predicted dropout & {metrics['counterfactual_mean_dropout']:.3f} &  &  \\",
            r"\doublebottomrule",
            r"\end{tabular*}",
            "",
            r"\begin{minipage}{\textwidth}",
            r"\footnotesize",
            r"\textbf{Note:} Prompt sensitivity is evaluated on the same 200-persona subsample used for the higher-quality-model validation. The detailed baseline is the main prompt used in the full 2,000-persona run. The Portuguese line translates that baseline prompt for the same subsample. The counterfactual line replaces mandatory recadastramento with a voluntary update plus a small tax credit.",
            r"\end{minipage}",
        ]
    )
    PROMPT_SENS_TABLE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_notes(
    validation_metrics: dict,
    education_metrics: dict,
    sensitivity_metrics: dict,
    municipality_pred: pd.DataFrame,
    responses_df: pd.DataFrame,
) -> None:
    lines = [
        "# Agent Simulation Notes",
        "",
        "## Data construction",
        "",
        "- Persona source: official IBGE 2010 Census sample microdata from the public FTP directory under `Resultados_Gerais_da_Amostra/Microdados`.",
        "- Person records are read from the fixed-width `Amostra_Pessoas` files using the official layout workbook bundled in `Documentacao.zip`.",
        "- The balanced persona design uses 2,000 sampled adults across the requested education, age, sex, region, and municipality-size cells.",
        "- The census microdata do not include a clean direct field for whether an adult currently holds an identity document, so `has_id_document` is imputed from education, urban/rural status, income tier, region, and municipality size. This is the weakest measured persona attribute and should be treated as a modeling assumption.",
        "",
        "## LLM design",
        "",
        f"- Main model: `{MAIN_MODEL}`",
        f"- Higher-quality validation model on 200 personas: `{VALIDATION_MODEL}`",
        "- Main batch prompt style: detailed baseline modeled directly on the requested prompt.",
        "- Prompt-sensitivity variants: minimal and persona-driven.",
        "- Language check: Portuguese translation of the baseline prompt on the 200-persona validation subsample.",
        "- Counterfactual check: voluntary biometric update plus a small tax credit.",
        "",
        "## Main validation numbers",
        "",
        f"- Municipalities in merged validation sample: {validation_metrics['n_municipalities']:,}",
        f"- Predicted-observed correlation: {validation_metrics['corr_unweighted']:.3f}",
        f"- Weighted correlation: {validation_metrics['corr_weighted']:.3f}",
        f"- Scatter R^2: {validation_metrics['scatter_r2']:.3f}",
        f"- Mean predicted dropout: {validation_metrics['mean_predicted_dropout']:.3f}",
        f"- Mean observed dropout: {validation_metrics['mean_observed_dropout']:.3f}",
        f"- Mean predicted dropout low education: {validation_metrics['mean_predicted_dropout_low_ed']:.3f}",
        f"- Mean predicted dropout high education: {validation_metrics['mean_predicted_dropout_high_ed']:.3f}",
        f"- Implied low-education share change: {education_metrics['pred_low_share_change_mean']:.3f}",
        f"- Observed low-education share change: {education_metrics['observed_low_share_change_mean']:.3f}",
        f"- Paper benchmark low-education share change: {education_metrics['paper_event_study_benchmark']:.3f}",
        "",
        "## Stress tests",
        "",
        f"- Higher-quality-model agreement: {sensitivity_metrics['high_quality_agreement']:.3f}",
        f"- Portuguese agreement with English baseline: {sensitivity_metrics['portuguese_agreement']:.3f}",
        f"- Baseline mean dropout on validation subsample: {sensitivity_metrics['baseline_validation_mean_dropout']:.3f}",
        f"- Counterfactual mean dropout with tax credit: {sensitivity_metrics['counterfactual_mean_dropout']:.3f}",
        "",
        "## Coverage",
        "",
        f"- Stored persona rows: {len(pd.read_parquet(PERSONAS_PATH)):,}",
        f"- Stored response rows: {len(responses_df):,}",
        f"- Stored municipality prediction rows: {len(municipality_pred):,}",
    ]
    DOCS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BVR LLM agent simulation pipeline.")
    parser.add_argument(
        "--archives",
        type=str,
        default=",".join(STATE_ARCHIVES),
        help="Comma-separated list of IBGE census state archives to use.",
    )
    parser.add_argument(
        "--persona-count",
        type=int,
        default=2000,
        help="Number of personas to construct in the balanced sample.",
    )
    parser.add_argument(
        "--validation-count",
        type=int,
        default=200,
        help="Number of personas to rerun with the higher-quality model and prompt variations.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=MAIN_BATCH_SIZE,
        help="Number of personas per LLM batch call.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=MAIN_MAX_WORKERS,
        help="Maximum parallel Codex workers for the LLM batches.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading census archives and assume the requested files already exist locally.",
    )
    args = parser.parse_args()
    state_archives = [archive.strip() for archive in args.archives.split(",") if archive.strip()]
    if not state_archives:
        raise ValueError("At least one IBGE census archive must be provided.")
    if args.persona_count <= 0:
        raise ValueError("--persona-count must be positive.")
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be positive.")
    if args.max_workers <= 0:
        raise ValueError("--max-workers must be positive.")

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    _ensure_dirs()
    if not args.skip_download:
        download_ibge_census_microdata(state_archives=state_archives)
    extract_documentation_files()
    personas_df, municipal_comp, urban_comp = build_personas_from_census(
        state_archives=state_archives,
        persona_count=args.persona_count,
    )
    responses_df = run_agent_batches(
        personas_df,
        batch_size=args.batch_size,
        validation_count=args.validation_count,
        max_workers=args.max_workers,
    )
    municipality_pred = build_municipality_predictions(personas_df, responses_df, municipal_comp, urban_comp)
    validation_df, validation_metrics = build_validation_dataset(municipality_pred)
    education_metrics = build_education_gradient_metrics(validation_df)
    prompt_sensitivity_summary, sensitivity_metrics = build_prompt_sensitivity_metrics(responses_df)
    plot_predicted_vs_observed(validation_df, validation_metrics)
    plot_education_gradient(validation_df, education_metrics)
    plot_regional_heterogeneity(validation_df)
    write_validation_table(validation_metrics, education_metrics, validation_df, sensitivity_metrics)
    write_prompt_sensitivity_table(prompt_sensitivity_summary, sensitivity_metrics)
    write_notes(validation_metrics, education_metrics, sensitivity_metrics, municipality_pred, responses_df)

    RUN_LOG_PATH.write_text(
        json.dumps(
            {
                "validation_metrics": validation_metrics,
                "education_metrics": education_metrics,
                "sensitivity_metrics": sensitivity_metrics,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
