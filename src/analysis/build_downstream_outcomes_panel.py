from __future__ import annotations

import argparse
import hashlib
import io
import math
import re
import subprocess
import unicodedata
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[2]
RAW_TSE_DIR = ROOT / "data" / "raw" / "tse_resultados"
RAW_FINBRA_DIR = ROOT / "data" / "raw" / "finbra"
INTERIM_DIR = ROOT / "data" / "interim" / "downstream"
CLEAN_DIR = ROOT / "data" / "clean" / "downstream"
DOCS_DIR = ROOT / "docs"
OUTPUT_PATH = CLEAN_DIR / "downstream_outcomes_panel.parquet"
NOTES_PATH = DOCS_DIR / "DOWNSTREAM_OUTCOMES_NOTES.md"

TREATMENT_PATH = ROOT / "data" / "clean" / "tse_bvr" / "municipality_bvr_first_treat.parquet"
TSE_PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018.parquet"
CROSSWALK_PATH = ROOT / "data" / "raw" / "ibge" / "bd-tse_mun_ids.csv"
DATASUS_EXPORT_SCRIPT = ROOT / "src" / "analysis" / "export_datasus_downstream_outcomes.R"
DATASUS_EXPORT_PATH = INTERIM_DIR / "datasus_outcomes.csv"
SICONFI_ENTES_PATH = INTERIM_DIR / "siconfi_entes.parquet"
TSE_SOURCE_INDEX_PATH = INTERIM_DIR / "tse_results_source_index.csv"
IBGE_POP_PANEL_PATH = INTERIM_DIR / "ibge_population_panel.parquet"

RESULT_YEARS = [2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022]
MUNICIPAL_YEARS = {2000, 2004, 2008, 2012, 2016, 2020}
NATIONAL_YEARS = {2002, 2006, 2010, 2014, 2018, 2022}
PRESIDENTIAL_SHARE_YEARS = {2002, 2006, 2010, 2014, 2018}
MAYORAL_OUTCOMES = [
    "effective_number_of_candidates_mayor",
    "margin_of_victory_mayor",
    "incumbent_mayor_reelection",
]
ALL_OUTCOME_COLUMNS = [
    "turnout",
    "blank_null_rate",
    "effective_number_of_candidates_mayor",
    "PT_vote_share_president",
    "PSDB_vote_share_president",
    "incumbent_mayor_reelection",
    "margin_of_victory_mayor",
    "health_spending_per_capita",
    "education_spending_per_capita",
    "social_assistance_spending_per_capita",
    "total_discretionary_spending_per_capita",
    "IPTU_collection_per_capita",
    "FPM_transfers_per_capita",
    "infant_mortality_rate",
    "neonatal_mortality_rate",
    "pre_natal_7plus_visits_share",
    "bolsa_familia_coverage",
]
FINBRA_PUBLICATION_YEARS = list(range(2000, 2013))

TSE_PACKAGE_API = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-{year}"
TSE_DATASET_PAGE = "https://dadosabertos.tse.jus.br/dataset/resultados-{year}"
SICONFI_ENTES_API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/entes"
SIDRA_POP_TABLE = "6579"
SIDRA_POP_VARIABLE = "9324"
SIDRA_POP_2010_CENSUS_TABLE = "202"

STATE_CODE_TO_UF = {
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


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def safe_sidra_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce")


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_directories() -> None:
    for path in [RAW_TSE_DIR, RAW_FINBRA_DIR, INTERIM_DIR, CLEAN_DIR, DOCS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected_size = 0
    try:
        head = requests.head(url, allow_redirects=True, timeout=60)
        if head.ok:
            expected_size = int(head.headers.get("content-length", "0") or 0)
    except requests.RequestException:
        expected_size = 0
    if destination.exists() and (expected_size == 0 or destination.stat().st_size == expected_size):
        return
    tmp_path = destination.with_suffix(destination.suffix + ".part")
    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with tmp_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    tmp_path.replace(destination)


def fetch_tse_results_resource_index() -> pd.DataFrame:
    rows: list[dict] = []
    for year in RESULT_YEARS:
        response = requests.get(TSE_PACKAGE_API.format(year=year), timeout=60)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError(f"TSE package lookup failed for {year}: {payload}")
        result = payload["result"]
        resources = result.get("resources", [])
        detail = next(
            resource
            for resource in resources
            if resource["name"].strip().startswith("Detalhe da apuração por município e zona")
        )
        party = next(
            resource
            for resource in resources
            if resource["name"].strip().startswith("Votação em partido por município e zona")
        )
        candidate = next(
            resource
            for resource in resources
            if resource["name"].strip().startswith("Votação nominal por município e zona")
        )

        rows.append(
            {
                "year": year,
                "dataset_page": TSE_DATASET_PAGE.format(year=year),
                "detail_url": detail["url"],
                "party_url": party["url"],
                "candidate_url": candidate["url"],
                "detail_file": Path(urlparse(detail["url"]).path).name,
                "party_file": Path(urlparse(party["url"]).path).name,
                "candidate_file": Path(urlparse(candidate["url"]).path).name,
            }
        )
    out = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    out.to_csv(TSE_SOURCE_INDEX_PATH, index=False)
    return out


def get_crosswalk() -> tuple[pd.DataFrame, pd.DataFrame]:
    crosswalk = pd.read_csv(CROSSWALK_PATH)
    crosswalk["municipality_id"] = crosswalk["municipality_id"].astype("Int64").astype(str)
    crosswalk["tse_municipality_id"] = pd.to_numeric(crosswalk["tse_municipality_id"], errors="coerce").astype("Int64")
    crosswalk["municipality_id6"] = crosswalk["municipality_id"].str[:6]

    latest = crosswalk.sort_values(["municipality_id", "year"]).drop_duplicates("municipality_id", keep="last")
    latest["state"] = latest["state"].str.upper()
    return crosswalk, latest


def get_treatment_panel() -> pd.DataFrame:
    treatment = pd.read_parquet(TREATMENT_PATH).rename(columns={"year_first_treat": "year_treated"})
    treatment["municipality_id"] = treatment["municipality_id"].astype(str)
    treatment["state"] = treatment["state"].str.upper()
    treatment["municipality_name_norm"] = treatment["municipality_name"].map(normalize_text)
    return treatment


def get_municipality_name_lookup(treatment: pd.DataFrame) -> pd.DataFrame:
    lookup_frames = [
        treatment[["municipality_id", "state", "municipality_name", "municipality_name_norm"]].drop_duplicates()
    ]
    if TSE_PANEL_PATH.exists():
        tse_panel = pd.read_parquet(TSE_PANEL_PATH, columns=["municipality_id", "state", "municipality_name"])
        tse_panel["municipality_id"] = tse_panel["municipality_id"].astype(str)
        tse_panel["state"] = tse_panel["state"].str.upper()
        tse_panel["municipality_name_norm"] = tse_panel["municipality_name"].map(normalize_text)
        lookup_frames.append(tse_panel.drop_duplicates())

    lookup = pd.concat(lookup_frames, ignore_index=True)
    lookup = lookup.sort_values(["municipality_id", "state", "municipality_name"]).drop_duplicates(
        ["municipality_id", "state"], keep="first"
    )
    return lookup


def build_skeleton(crosswalk_latest: pd.DataFrame, treatment: pd.DataFrame, municipality_lookup: pd.DataFrame) -> pd.DataFrame:
    base = (
        crosswalk_latest[["municipality_id", "state"]]
        .drop_duplicates()
        .merge(
            municipality_lookup[["municipality_id", "municipality_name", "state"]],
            on=["municipality_id", "state"],
            how="left",
        )
        .merge(
            treatment[["municipality_id", "state", "year_treated"]],
            on=["municipality_id", "state"],
            how="left",
        )
    )
    base["year_treated"] = base["year_treated"].fillna(9999).astype(int)
    if "municipality_name" not in base:
        base["municipality_name"] = base["municipality_id"]
    years = pd.DataFrame({"year_election": RESULT_YEARS})
    skeleton = base.assign(_key=1).merge(years.assign(_key=1), on="_key").drop(columns="_key")
    skeleton["dist_treatment"] = skeleton["year_election"] - skeleton["year_treated"]
    skeleton.loc[skeleton["year_treated"] == 9999, "dist_treatment"] = -9999
    return skeleton


def get_population_panel() -> pd.DataFrame:
    if IBGE_POP_PANEL_PATH.exists():
        cached = pd.read_parquet(IBGE_POP_PANEL_PATH)
        cached_years = sorted(pd.to_numeric(cached["year"], errors="coerce").dropna().astype(int).unique().tolist())
        if cached_years == RESULT_YEARS:
            return cached

    frames: list[pd.DataFrame] = []
    for year in RESULT_YEARS:
        if year in {2000, 2010}:
            sidra_year = year
            url = f"https://apisidra.ibge.gov.br/values/t/{SIDRA_POP_2010_CENSUS_TABLE}/n6/all/p/{sidra_year}?formato=json"
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or len(payload) < 2 or "D1C" not in payload[0]:
                raise ValueError(f"Unexpected SIDRA census population response for {year}: {response.text[:500]}")
            frame = pd.DataFrame(payload[1:]).rename(columns={"D1C": "municipality_id", "D2C": "year", "V": "population_estimate"})
        else:
            sidra_year = 2021 if year == 2022 else year
            url = f"https://apisidra.ibge.gov.br/values/t/{SIDRA_POP_TABLE}/n6/all/v/{SIDRA_POP_VARIABLE}/p/{sidra_year}?formato=json"
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or len(payload) < 2 or "D1C" not in payload[0]:
                raise ValueError(f"Unexpected SIDRA population response for {year}: {response.text[:500]}")
            frame = pd.DataFrame(payload[1:]).rename(columns={"D1C": "municipality_id", "D3C": "year", "V": "population_estimate"})
            frame["year"] = year

        frame["municipality_id"] = frame["municipality_id"].astype(str).str.zfill(7)
        frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
        frame["population_estimate"] = safe_sidra_numeric(frame["population_estimate"])
        frames.append(frame[["municipality_id", "year", "population_estimate"]])

    population = pd.concat(frames, ignore_index=True).drop_duplicates(["municipality_id", "year"])
    population.to_parquet(IBGE_POP_PANEL_PATH, index=False)
    return population


def read_zip_csv(zip_path: Path, suffix: str = "_BRASIL.csv", usecols: list[str] | None = None) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        names = [name for name in zf.namelist() if name.endswith(suffix)]
        if not names:
            raise FileNotFoundError(f"No archive member ending with {suffix} found in {zip_path}")
        with zf.open(names[0]) as handle:
            return pd.read_csv(handle, sep=";", encoding="latin-1", usecols=usecols, low_memory=False)


def iter_zip_csv_chunks(
    zip_path: Path,
    suffix: str = "_BRASIL.csv",
    usecols: list[str] | None = None,
    chunksize: int = 250_000,
):
    with zipfile.ZipFile(zip_path) as zf:
        names = [name for name in zf.namelist() if name.endswith(suffix)]
        if not names:
            raise FileNotFoundError(f"No archive member ending with {suffix} found in {zip_path}")
        with zf.open(names[0]) as handle:
            yield from pd.read_csv(
                handle,
                sep=";",
                encoding="latin-1",
                usecols=usecols,
                low_memory=False,
                chunksize=chunksize,
            )


def _merge_tse_crosswalk(df: pd.DataFrame, crosswalk: pd.DataFrame, year: int) -> pd.DataFrame:
    year_crosswalk = crosswalk.loc[crosswalk["year"] == year, ["municipality_id", "tse_municipality_id"]].drop_duplicates()
    out = df.copy()
    out["tse_municipality_id"] = pd.to_numeric(out["tse_municipality_id"], errors="coerce").astype("Int64")
    out = out.merge(year_crosswalk, on="tse_municipality_id", how="left")
    return out


def build_tse_turnout_blanknull(detail_index: pd.DataFrame, crosswalk: pd.DataFrame, download_missing: bool) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    usecols = [
        "ANO_ELEICAO",
        "NR_TURNO",
        "CD_MUNICIPIO",
        "DS_CARGO",
        "QT_APTOS",
        "QT_TOTAL_VOTOS_VALIDOS",
        "QT_VOTOS_BRANCOS",
        "QT_TOTAL_VOTOS_NULOS",
        "QT_COMPARECIMENTO",
    ]
    for row in detail_index.itertuples(index=False):
        zip_path = RAW_TSE_DIR / str(row.year) / row.detail_file
        if download_missing:
            download_file(row.detail_url, zip_path)
        if not zip_path.exists():
            continue

        detail = read_zip_csv(zip_path, usecols=usecols)
        detail = detail.loc[pd.to_numeric(detail["NR_TURNO"], errors="coerce") == 1].copy()
        detail["cargo_norm"] = detail["DS_CARGO"].map(normalize_text)
        target = "prefeito" if row.year in MUNICIPAL_YEARS else "presidente"
        detail = detail.loc[detail["cargo_norm"] == target].copy()
        if detail.empty:
            continue

        for col in ["QT_APTOS", "QT_TOTAL_VOTOS_VALIDOS", "QT_VOTOS_BRANCOS", "QT_TOTAL_VOTOS_NULOS", "QT_COMPARECIMENTO"]:
            detail[col] = pd.to_numeric(detail[col], errors="coerce")
        detail = (
            detail.rename(columns={"CD_MUNICIPIO": "tse_municipality_id"})
            .groupby("tse_municipality_id", as_index=False)[
                ["QT_APTOS", "QT_TOTAL_VOTOS_VALIDOS", "QT_VOTOS_BRANCOS", "QT_TOTAL_VOTOS_NULOS", "QT_COMPARECIMENTO"]
            ]
            .sum()
        )
        detail = _merge_tse_crosswalk(detail, crosswalk, row.year)
        detail["year_election"] = row.year
        detail["turnout"] = detail["QT_TOTAL_VOTOS_VALIDOS"] / detail["QT_APTOS"]
        detail["blank_null_rate"] = (
            detail["QT_VOTOS_BRANCOS"] + detail["QT_TOTAL_VOTOS_NULOS"]
        ) / detail["QT_COMPARECIMENTO"].replace({0: pd.NA})
        rows.append(detail[["year_election", "municipality_id", "turnout", "blank_null_rate"]])

    if not rows:
        return pd.DataFrame(columns=["year_election", "municipality_id", "turnout", "blank_null_rate"])
    return pd.concat(rows, ignore_index=True)


def build_tse_candidate_outcomes(source_index: pd.DataFrame, crosswalk: pd.DataFrame, download_missing: bool) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    mayor_winners: list[pd.DataFrame] = []
    usecols = [
        "ANO_ELEICAO",
        "NR_TURNO",
        "CD_MUNICIPIO",
        "DS_CARGO",
        "NM_CANDIDATO",
        "NM_URNA_CANDIDATO",
        "SG_PARTIDO",
        "NR_CANDIDATO",
        "QT_VOTOS_NOMINAIS_VALIDOS",
    ]

    for row in source_index.itertuples(index=False):
        if row.year not in MUNICIPAL_YEARS:
            continue
        zip_path = RAW_TSE_DIR / str(row.year) / row.candidate_file
        if download_missing:
            download_file(row.candidate_url, zip_path)
        if not zip_path.exists():
            continue

        year_crosswalk = crosswalk.loc[crosswalk["year"] == row.year, ["municipality_id", "tse_municipality_id"]].drop_duplicates()
        tse_to_muni = {
            int(tse_id): municipality_id
            for municipality_id, tse_id in year_crosswalk.itertuples(index=False)
            if pd.notna(tse_id)
        }
        mayor_chunks: list[pd.DataFrame] = []

        for chunk in iter_zip_csv_chunks(zip_path, usecols=usecols):
            chunk = chunk.loc[pd.to_numeric(chunk["NR_TURNO"], errors="coerce") == 1].copy()
            if chunk.empty:
                continue
            chunk["cargo_norm"] = chunk["DS_CARGO"].map(normalize_text)
            chunk["QT_VOTOS_NOMINAIS_VALIDOS"] = pd.to_numeric(chunk["QT_VOTOS_NOMINAIS_VALIDOS"], errors="coerce").fillna(0)
            chunk["tse_municipality_id"] = pd.to_numeric(chunk["CD_MUNICIPIO"], errors="coerce")
            chunk["municipality_id"] = chunk["tse_municipality_id"].map(tse_to_muni)
            chunk = chunk.dropna(subset=["municipality_id"])
            if chunk.empty:
                continue

            mayor = chunk.loc[
                chunk["cargo_norm"] == "prefeito",
                ["municipality_id", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "NR_CANDIDATO", "QT_VOTOS_NOMINAIS_VALIDOS"],
            ].copy()
            if not mayor.empty:
                mayor_chunks.append(
                    mayor.groupby(
                        ["municipality_id", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "NR_CANDIDATO"],
                        as_index=False,
                    )["QT_VOTOS_NOMINAIS_VALIDOS"].sum()
                )

        if mayor_chunks:
            mayor = pd.concat(mayor_chunks, ignore_index=True)
            grp = mayor.groupby(["municipality_id", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "NR_CANDIDATO"], as_index=False)[
                "QT_VOTOS_NOMINAIS_VALIDOS"
            ].sum()
            totals = grp.groupby("municipality_id", as_index=False)["QT_VOTOS_NOMINAIS_VALIDOS"].sum().rename(
                columns={"QT_VOTOS_NOMINAIS_VALIDOS": "total_valid_mayor"}
            )
            merged = grp.merge(totals, on="municipality_id", how="left")
            merged["vote_share"] = merged["QT_VOTOS_NOMINAIS_VALIDOS"] / merged["total_valid_mayor"].replace({0: pd.NA})
            eff = (
                merged.groupby("municipality_id")["vote_share"]
                .apply(lambda s: 1 / (s.fillna(0).pow(2).sum()) if s.notna().any() else math.nan)
                .reset_index(name="effective_number_of_candidates_mayor")
            )
            top2 = (
                merged.sort_values(["municipality_id", "vote_share"], ascending=[True, False])
                .groupby("municipality_id")
                .head(2)
                .copy()
            )
            top2["rank"] = top2.groupby("municipality_id").cumcount() + 1
            pivot = top2.pivot(index="municipality_id", columns="rank", values="vote_share").reset_index().rename(
                columns={1: "top_share", 2: "runner_up_share"}
            )
            pivot["margin_of_victory_mayor"] = pivot["top_share"] - pivot["runner_up_share"]
            yearly = eff.merge(pivot[["municipality_id", "margin_of_victory_mayor"]], on="municipality_id", how="left")
            yearly["year_election"] = row.year
            rows.append(yearly[["year_election", "municipality_id", "effective_number_of_candidates_mayor", "margin_of_victory_mayor"]])

            winners = (
                merged.sort_values(["municipality_id", "vote_share", "QT_VOTOS_NOMINAIS_VALIDOS"], ascending=[True, False, False])
                .groupby("municipality_id")
                .head(1)
                .copy()
            )
            winners["year_election"] = row.year
            winners["winner_name_norm"] = winners["NM_CANDIDATO"].map(normalize_text)
            mayor_winners.append(winners[["year_election", "municipality_id", "winner_name_norm"]])

    if mayor_winners:
        winners_df = pd.concat(mayor_winners, ignore_index=True).sort_values(["municipality_id", "year_election"])
        winners_df["previous_winner"] = winners_df.groupby("municipality_id")["winner_name_norm"].shift(1)
        winners_df["incumbent_mayor_reelection"] = (
            winners_df["winner_name_norm"].notna() & winners_df["winner_name_norm"].eq(winners_df["previous_winner"])
        ).astype(float)
        rows.append(winners_df[["year_election", "municipality_id", "incumbent_mayor_reelection"]])

    if not rows:
        return pd.DataFrame(columns=["year_election", "municipality_id"] + MAYORAL_OUTCOMES)
    combined = pd.concat(rows, ignore_index=True)
    outcome_cols = [col for col in combined.columns if col not in {"year_election", "municipality_id"}]
    return combined.groupby(["year_election", "municipality_id"], as_index=False)[outcome_cols].first()


def build_tse_party_presidential_outcomes(source_index: pd.DataFrame, crosswalk: pd.DataFrame, download_missing: bool) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []

    for row in source_index.itertuples(index=False):
        if row.year not in PRESIDENTIAL_SHARE_YEARS:
            continue
        zip_path = RAW_TSE_DIR / str(row.year) / row.party_file
        if download_missing:
            download_file(row.party_url, zip_path)
        if not zip_path.exists():
            continue

        party = read_zip_csv(zip_path)
        party = party.loc[pd.to_numeric(party["NR_TURNO"], errors="coerce") == 1].copy()
        party["cargo_norm"] = party["DS_CARGO"].map(normalize_text)
        party = party.loc[party["cargo_norm"] == "presidente"].copy()
        if party.empty:
            continue

        vote_col = "QT_VOTOS_NOMINAIS_VALIDOS" if "QT_VOTOS_NOMINAIS_VALIDOS" in party.columns else "QT_VOTOS_NOMINAIS"
        party[vote_col] = pd.to_numeric(party[vote_col], errors="coerce").fillna(0)
        party = party.rename(columns={"CD_MUNICIPIO": "tse_municipality_id"})
        party = _merge_tse_crosswalk(party, crosswalk, row.year)
        party = party.dropna(subset=["municipality_id"])
        if party.empty:
            continue

        grouped = party.groupby(["municipality_id", "SG_PARTIDO"], as_index=False)[vote_col].sum()
        totals = grouped.groupby("municipality_id", as_index=False)[vote_col].sum().rename(
            columns={vote_col: "total_valid_president"}
        )
        focal = grouped.loc[grouped["SG_PARTIDO"].isin(["PT", "PSDB"])].copy()
        pivot = focal.pivot(index="municipality_id", columns="SG_PARTIDO", values=vote_col).reset_index()
        if "PT" not in pivot.columns:
            pivot["PT"] = 0
        if "PSDB" not in pivot.columns:
            pivot["PSDB"] = 0
        pivot = pivot.rename(columns={"PT": "pt_votes", "PSDB": "psdb_votes"})
        merged = totals.merge(pivot, on="municipality_id", how="left").fillna({"pt_votes": 0, "psdb_votes": 0})
        merged["PT_vote_share_president"] = merged["pt_votes"] / merged["total_valid_president"].replace({0: pd.NA})
        merged["PSDB_vote_share_president"] = merged["psdb_votes"] / merged["total_valid_president"].replace({0: pd.NA})
        merged["year_election"] = row.year
        rows.append(merged[["year_election", "municipality_id", "PT_vote_share_president", "PSDB_vote_share_president"]])

    if not rows:
        return pd.DataFrame(columns=["year_election", "municipality_id", "PT_vote_share_president", "PSDB_vote_share_president"])
    return pd.concat(rows, ignore_index=True).groupby(["year_election", "municipality_id"], as_index=False).first()


def ensure_datasus_export(run_export: bool) -> pd.DataFrame:
    if run_export or not DATASUS_EXPORT_PATH.exists():
        subprocess.run(
            ["Rscript", str(DATASUS_EXPORT_SCRIPT), str(DATASUS_EXPORT_PATH)],
            cwd=ROOT,
            check=True,
        )
    df = pd.read_csv(DATASUS_EXPORT_PATH)
    df["code6"] = df["code6"].astype(str).str.zfill(6)
    return df


def build_datasus_outcomes(datasus_raw: pd.DataFrame, population_panel: pd.DataFrame, crosswalk: pd.DataFrame) -> pd.DataFrame:
    code_lookup = crosswalk[["municipality_id", "municipality_id6"]].drop_duplicates()
    df = datasus_raw.merge(code_lookup, left_on="code6", right_on="municipality_id6", how="left")
    df = df.rename(columns={"year": "year_election"})
    df = df.merge(
        population_panel.rename(columns={"year": "year_election"}),
        on=["municipality_id", "year_election"],
        how="left",
    )
    df["infant_mortality_rate"] = df["deaths_under_1"] / df["live_births"].replace({0: pd.NA}) * 1000
    df["neonatal_mortality_rate"] = df["deaths_neonatal_0_27d"] / df["live_births"].replace({0: pd.NA}) * 1000
    df["pre_natal_7plus_visits_share"] = df["births_prenatal_7plus"] / df["live_births"].replace({0: pd.NA})
    df.loc[df["population_estimate"] <= 1000, ["infant_mortality_rate", "neonatal_mortality_rate"]] = pd.NA
    return df[
        [
            "year_election",
            "municipality_id",
            "infant_mortality_rate",
            "neonatal_mortality_rate",
            "pre_natal_7plus_visits_share",
        ]
    ]


def _state_name_lookup() -> pd.DataFrame:
    return pd.DataFrame({"state_code": list(STATE_CODE_TO_UF.keys()), "state": list(STATE_CODE_TO_UF.values())})


def safe_numeric_col(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(float("nan"), index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def load_mdb_csv(mdb_path: Path, table: str) -> pd.DataFrame:
    result = subprocess.run(
        ["mdb-export", str(mdb_path), table],
        check=True,
        capture_output=True,
        text=True,
    )
    return pd.read_csv(io.StringIO(result.stdout))


def download_finbra_historical_zip(year: int) -> Path | None:
    page = f"https://www.tesourotransparente.gov.br/publicacoes/finbra-dados-contabeis-dos-municipios-1989-a-2012/{year}/26"
    html = requests.get(page, timeout=120).text
    match = re.search(r"thot-arquivos\.tesouro\.gov\.br/publicacao/(\d+)", html)
    if not match:
        return None
    publication_id = match.group(1)
    raw_dir = RAW_FINBRA_DIR / str(year)
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / f"finbra_{year}.zip"
    if not destination.exists():
        download_file(f"https://thot-arquivos.tesouro.gov.br/publicacao/{publication_id}", destination)
    return destination


def _extract_mdb(zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path) as zf:
        names = [name for name in zf.namelist() if name.lower().endswith(".mdb")]
        if not names:
            raise FileNotFoundError(f"No MDB found inside {zip_path}")
        target = INTERIM_DIR / f"{zip_path.stem}.mdb"
        if not target.exists():
            with zf.open(names[0]) as src, target.open("wb") as dst:
                dst.write(src.read())
        return target


def build_finbra_historical(municipality_lookup: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    name_lookup = municipality_lookup[["municipality_id", "state", "municipality_name_norm"]].drop_duplicates()

    for year in FINBRA_PUBLICATION_YEARS:
        zip_path = download_finbra_historical_zip(year)
        if zip_path is None or not zip_path.exists():
            continue
        mdb_path = _extract_mdb(zip_path)
        tables = subprocess.run(["mdb-tables", "-1", str(mdb_path)], check=True, capture_output=True, text=True).stdout.splitlines()
        table_set = set(tables)
        has_func = "DSubFuncao" in tables
        if has_func:
            receita = load_mdb_csv(mdb_path, "Receita")
            func = load_mdb_csv(mdb_path, "DSubFuncao")
            desp = load_mdb_csv(mdb_path, "Despesa")
            out = func.rename(columns={"UF": "state_code", "Cod Mun": "mun_code"})
            out["health_spending_per_capita_raw"] = safe_numeric_col(out, "Saúde")
            out["education_spending_per_capita_raw"] = safe_numeric_col(out, "Educação")
            out["social_assistance_spending_per_capita_raw"] = safe_numeric_col(out, "Assistência Social")
            discretionary_raw = (
                safe_numeric_col(desp, "Despesas Orçamentárias")
                - safe_numeric_col(desp, "Pessoal e Encarg Soc_PES").fillna(0)
                - safe_numeric_col(desp, "Juros e Encargos Dívida_JED").fillna(0)
                - safe_numeric_col(desp, "Amortização da Dívida").fillna(0)
            )
            out["total_discretionary_spending_per_capita_raw"] = discretionary_raw
            receita = receita.rename(columns={receita.columns[0]: "state_code", receita.columns[1]: "mun_code"})
            receita_cols = [col for col in ["state_code", "mun_code", "IPTU", "Cota FPM"] if col in receita.columns]
            receita = receita[receita_cols]
        elif "RecDesp" in table_set:
            out = load_mdb_csv(mdb_path, "RecDesp").rename(columns={"CD_UF": "state_code", "CD_MUN": "mun_code"})
            out["health_spending_per_capita_raw"] = safe_numeric_col(out, "Saúde")
            out["education_spending_per_capita_raw"] = safe_numeric_col(out, "Educação")
            out["social_assistance_spending_per_capita_raw"] = safe_numeric_col(out, "Assistência Social")
            out["total_discretionary_spending_per_capita_raw"] = (
                safe_numeric_col(out, "Despesas Orçamentárias")
                - safe_numeric_col(out, "Pessoal e Encarg Soc_PES").fillna(0)
                - safe_numeric_col(out, "Juros e Encargos Dívida").fillna(0)
                - safe_numeric_col(out, "Amortização da Dívida").fillna(0)
            )
            receita = out[[col for col in ["state_code", "mun_code", "IPTU", "Cota FPM"] if col in out.columns]].copy()
        else:
            receita = load_mdb_csv(mdb_path, "Receita")
            desp = load_mdb_csv(mdb_path, "Despesa")
            out = desp.rename(columns={"CD_UF": "state_code", "CD_MUN": "mun_code"})
            out["health_spending_per_capita_raw"] = safe_numeric_col(out, "Saúde e Saneamento")
            out["education_spending_per_capita_raw"] = safe_numeric_col(out, "Educação e Cultura")
            out["social_assistance_spending_per_capita_raw"] = safe_numeric_col(out, "Assistência e Previdência")
            out["total_discretionary_spending_per_capita_raw"] = (
                safe_numeric_col(out, "Despesas Orçamentárias")
                - safe_numeric_col(out, "Desp de Pessoal").fillna(0)
                - safe_numeric_col(out, "Juros e Encargos da Dívida").fillna(0)
                - safe_numeric_col(out, "Amortizações").fillna(0)
            )
            receita = receita.rename(columns={receita.columns[0]: "state_code", receita.columns[1]: "mun_code"})
            receita_cols = [col for col in ["state_code", "mun_code", "IPTU", "Cota FPM"] if col in receita.columns]
            receita = receita[receita_cols]

        pop = load_mdb_csv(mdb_path, "Pop Ibge")
        pop_col = str(year) if str(year) in pop.columns else next((col for col in reversed(pop.columns) if re.fullmatch(r"\d{4}", str(col))), None)
        if pop_col is None:
            continue
        pop = pop.rename(columns={pop.columns[0]: "state_code", pop.columns[1]: "mun_code", pop_col: "population"})
        merged = out.merge(receita, on=["state_code", "mun_code"], how="left")
        merged = merged.merge(pop[["state_code", "mun_code", "population"]], on=["state_code", "mun_code"], how="left")
        merged["state_code"] = merged["state_code"].astype(str).str.zfill(2)
        merged["state"] = merged["state_code"].map(STATE_CODE_TO_UF)
        name_table = load_mdb_csv(mdb_path, "Cod IBGE Mun")
        name_table = name_table.rename(columns={name_table.columns[0]: "state_code", name_table.columns[1]: "mun_code", name_table.columns[2]: "municipality_name_finbra"})
        name_table["state_code"] = name_table["state_code"].astype(str).str.zfill(2)
        name_table["state"] = name_table["state_code"].map(STATE_CODE_TO_UF)
        name_table["municipality_name_norm"] = name_table["municipality_name_finbra"].map(normalize_text)
        merged = merged.merge(name_table[["state_code", "mun_code", "state", "municipality_name_norm"]], on=["state_code", "mun_code", "state"], how="left")
        merged = merged.merge(
            name_lookup,
            on=["state", "municipality_name_norm"],
            how="left",
        )
        merged["year_fiscal"] = year
        merged["health_spending_per_capita"] = pd.to_numeric(merged["health_spending_per_capita_raw"], errors="coerce") / pd.to_numeric(
            merged["population"], errors="coerce"
        )
        merged["education_spending_per_capita"] = pd.to_numeric(merged["education_spending_per_capita_raw"], errors="coerce") / pd.to_numeric(
            merged["population"], errors="coerce"
        )
        merged["social_assistance_spending_per_capita"] = pd.to_numeric(
            merged["social_assistance_spending_per_capita_raw"], errors="coerce"
        ) / pd.to_numeric(merged["population"], errors="coerce")
        merged["total_discretionary_spending_per_capita"] = pd.to_numeric(
            merged["total_discretionary_spending_per_capita_raw"], errors="coerce"
        ) / pd.to_numeric(merged["population"], errors="coerce")
        merged["IPTU_collection_per_capita"] = safe_numeric_col(merged, "IPTU") / pd.to_numeric(
            merged["population"], errors="coerce"
        )
        merged["FPM_transfers_per_capita"] = safe_numeric_col(merged, "Cota FPM") / pd.to_numeric(
            merged["population"], errors="coerce"
        )
        frames.append(
            merged[
                [
                    "year_fiscal",
                    "municipality_id",
                    "health_spending_per_capita",
                    "education_spending_per_capita",
                    "social_assistance_spending_per_capita",
                    "total_discretionary_spending_per_capita",
                    "IPTU_collection_per_capita",
                    "FPM_transfers_per_capita",
                ]
            ]
        )

    if not frames:
        return pd.DataFrame(columns=["year_election", "municipality_id"])
    fiscal = pd.concat(frames, ignore_index=True)
    fiscal["year_election"] = fiscal["year_fiscal"].where(fiscal["year_fiscal"].isin(RESULT_YEARS), fiscal["year_fiscal"] + 1)
    fiscal = fiscal.drop(columns="year_fiscal")
    return fiscal.groupby(["year_election", "municipality_id"], as_index=False).first()


def winsorize_series(series: pd.Series) -> pd.Series:
    if series.dropna().empty:
        return series
    lower = series.quantile(0.01)
    upper = series.quantile(0.99)
    return series.clip(lower=lower, upper=upper)


def finalize_panel(panel: pd.DataFrame, population_panel: pd.DataFrame, fiscal_df: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    out = out.merge(
        population_panel.rename(columns={"year": "year_election"}),
        on=["municipality_id", "year_election"],
        how="left",
    )
    out = out.merge(fiscal_df, on=["municipality_id", "year_election"], how="left")

    for col in [
        "health_spending_per_capita",
        "education_spending_per_capita",
        "social_assistance_spending_per_capita",
        "total_discretionary_spending_per_capita",
        "IPTU_collection_per_capita",
        "FPM_transfers_per_capita",
    ]:
        if col in out.columns:
            out[col] = winsorize_series(pd.to_numeric(out[col], errors="coerce"))
            out[f"log_{col}"] = winsorize_series((pd.to_numeric(out[col], errors="coerce").fillna(0) + 1).map(math.log))

    for col in ALL_OUTCOME_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    return out.sort_values(["municipality_id", "year_election"]).reset_index(drop=True)


def build_notes(panel: pd.DataFrame) -> str:
    available = [col for col in ALL_OUTCOME_COLUMNS if col in panel.columns and panel[col].notna().any()]
    unavailable = [col for col in ALL_OUTCOME_COLUMNS if col not in available]
    text = f"""# Downstream Outcomes Notes

- Panel key: `(year_election, municipality_id)`.
- Treatment timing source: `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`.
- Election years covered in the skeleton: `{", ".join(map(str, RESULT_YEARS))}`.
- Fiscal-year alignment rule: prior odd fiscal year is carried to the following election year, so FY2001 maps to election year 2002.
- DATASUS mortality rates are blanked out when `population_estimate <= 1000`.
- Spending variables are prepared as per-capita levels and, when available, logged as `log_<variable>` after adding one.

## Available Outcomes

{chr(10).join(f"- `{col}`" for col in available) if available else "- None in this environment."}

## Currently Missing or Partial

{chr(10).join(f"- `{col}`" for col in unavailable) if unavailable else "- None."}

## Source-Specific Caveats

- TSE turnout and blank/null rates come from `detalhe_votacao_munzona`, aggregated to the executive race in each election year (`Prefeito` in municipal years, `Presidente` in national years).
- Mayoral and presidential vote-share outcomes require the much larger TSE candidate archives. The builder fills them when those raw files are present, but it does not silently backfill them from non-official mirrors.
- Historical FINBRA 2000-2012 files are downloaded from the Tesouro publication archive. The post-2012 Siconfi bulk path is more brittle in this environment, so fiscal coverage may be concentrated in the historical span unless the public Siconfi extraction is completed later.
- DATASUS outcomes are pulled through the open-source `datasus` R wrapper, which submits the official TabNet forms and writes municipality-year aggregates to `data/interim/downstream/datasus_outcomes.csv`.
- Bolsa Família coverage is intentionally left blank until the municipal bulk extract from the Cidadania explorer is stabilized and documented.
"""
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-tse-detail", action="store_true")
    parser.add_argument("--download-tse-candidate", action="store_true")
    parser.add_argument("--run-datasus-export", action="store_true")
    parser.add_argument("--skip-datasus", action="store_true")
    parser.add_argument("--skip-finbra", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_directories()

    crosswalk, crosswalk_latest = get_crosswalk()
    treatment = get_treatment_panel()
    municipality_lookup = get_municipality_name_lookup(treatment)
    source_index = fetch_tse_results_resource_index()
    skeleton = build_skeleton(crosswalk_latest, treatment, municipality_lookup)
    population_panel = get_population_panel()

    turnout_blank = build_tse_turnout_blanknull(source_index, crosswalk, download_missing=args.download_tse_detail)
    candidate_outcomes = build_tse_candidate_outcomes(source_index, crosswalk, download_missing=args.download_tse_candidate)

    if args.skip_datasus:
        datasus_outcomes = pd.DataFrame(columns=["year_election", "municipality_id"])
    else:
        datasus_raw = ensure_datasus_export(run_export=args.run_datasus_export)
        datasus_outcomes = build_datasus_outcomes(datasus_raw, population_panel, crosswalk)

    fiscal_outcomes = (
        pd.DataFrame(columns=["year_election", "municipality_id"])
        if args.skip_finbra
        else build_finbra_historical(municipality_lookup)
    )

    panel = skeleton.merge(turnout_blank, on=["municipality_id", "year_election"], how="left")
    panel = panel.merge(candidate_outcomes, on=["municipality_id", "year_election"], how="left")
    panel = panel.merge(datasus_outcomes, on=["municipality_id", "year_election"], how="left")
    panel = finalize_panel(panel, population_panel, fiscal_outcomes)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(OUTPUT_PATH, index=False)
    NOTES_PATH.write_text(build_notes(panel), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Wrote {NOTES_PATH}")


if __name__ == "__main__":
    main()
