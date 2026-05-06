from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.tse_bvr_common import INTERIM_DIR, RAW_TSE_DIR, VALID_UFS, ensure_directories, normalize_name, zone_to_int_or_none


SOURCE_2008 = "https://www.tse.jus.br/legislacao/compilada/res/2008/resolucao-no-22-713-de-28-de-fevereiro-de-2008"
SOURCE_2010_PROV_1 = "https://www.tse.jus.br/legislacao/compilada/prv-cge/2010/provimento-no-1-cge-de-2-de-fevereiro-de-2010"
SOURCE_2010_PROV_7 = "https://www.tse.jus.br/legislacao/compilada/prv-cge/2010/provimento-no-7-cge-de-70-de-outubro-de-2010"
SOURCE_2012_ATTACHMENT = "https://www.justicaeleitoral.jus.br/arquivos/tse-lista-de-localidades-onde-havera-recadastramento-biometrico-em-2012"
SOURCE_2014_ATTACHMENT = "https://www.justicaeleitoral.jus.br/arquivos/eleitores-de-todos-os-estados-serao-identificados-pela-biometria-nas-eleicoes-de-2014"
SOURCE_2014_ARTICLE = "https://www.tse.jus.br/comunicacao/noticias/2013/Marco/eleitores-de-todos-os-estados-serao-identificados-pela-biometria-nas-eleicoes-de-2014"
SOURCE_2014_OPEN_DATA = "https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2014.zip"
SOURCE_2016_ARTICLE = "https://www.tse.jus.br/comunicacao/noticias/2016/Agosto/27-dos-eleitores-estao-aptos-a-serem-identificados-biometricamente-nas-eleicoes-2016"
SOURCE_2016_OPEN_DATA = "https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2016.zip"
SOURCE_2018_ARTICLE = "https://www.tse.jus.br/comunicacao/noticias/2018/Setembro/faltam-21-dias-cadastramento-biometrico-completa-10-anos-e-alcanca-a-mais-de-87-milhoes-de-eleitores"
SOURCE_2018_OPEN_DATA = "https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2018.zip"


def _read_text(path: Path) -> str:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
    return "\n".join(lines)


def _path_for_url(url: str, suffix: str) -> Path:
    for path in RAW_TSE_DIR.iterdir():
        if path.name.startswith(url.replace("https://", "").replace("http://", "").replace("/", "__").replace("?", "__q__")):
            return path
    matches = [path for path in RAW_TSE_DIR.iterdir() if path.suffix == suffix and url.split("//", 1)[-1].split("/", 1)[0] in path.name]
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(url)


def _manual_2008_rows(text: str) -> list[dict]:
    article_match = re.search(
        r"Art\. 1º No dia das eleições, nas seções eleitorais dos municípios de (.+?), a identificação",
        text,
        flags=re.DOTALL,
    )
    if not article_match:
        raise ValueError("Could not locate Art. 1 in the 2008 resolution text.")

    pairs = re.findall(r"([A-Za-zÀ-ÿ' \-]+?)/([A-Z]{2})", article_match.group(1))
    rows = []
    for name, state in pairs:
        clean_name = re.sub(r"^\s*e\s+", "", name.strip(), flags=re.IGNORECASE)
        rows.append(
            {
                "raw_name_tse": clean_name,
                "normalized_name_tse": normalize_name(clean_name),
                "state": state,
                "zone": None,
                "url_tse": SOURCE_2008,
                "year_first_treat": 2008,
                "source_title": "Resolucao no 22.713, de 28 de fevereiro de 2008",
                "source_date": "2008-02-28",
                "treatment_scope": "municipality",
                "source_kind": "legal_act",
                "notes": "Pilot municipality explicitly named in Art. 1.",
            }
        )
    return rows


def _parse_2010_annex(text: str, source_url: str, source_title: str, issue_date: str) -> list[dict]:
    start = text.find("Anexo")
    end = text.find("Este texto não substitui")
    if start == -1 or end == -1:
        raise ValueError(f"Could not isolate annex text for {source_url}.")

    snippet = text[start:end]
    lines = [line.strip() for line in snippet.splitlines() if line.strip()]
    try:
        header_index = lines.index("ZONA ELEITORAL") + 1
    except ValueError as exc:
        raise ValueError(f"Could not find the annex header in {source_url}.") from exc

    data_lines = lines[header_index:]
    parsed_rows: list[tuple[str, str, int]] = []
    index = 0
    while index < len(data_lines):
        current = data_lines[index]
        if re.match(r"^\d+º$", current):
            if index + 3 >= len(data_lines):
                break
            state = data_lines[index + 1]
            name = data_lines[index + 2]
            zone = zone_to_int_or_none(data_lines[index + 3])
            index += 4
        elif re.match(r"^[A-Z]{2}$", current):
            if index + 2 >= len(data_lines):
                break
            state = current
            name = data_lines[index + 1]
            zone = zone_to_int_or_none(data_lines[index + 2])
            index += 3
        else:
            index += 1
            continue

        if state not in {"AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"}:
            continue
        if zone is None:
            continue
        parsed_rows.append((state, name, zone))

    rows = []
    for state, name, zone in parsed_rows:
        rows.append(
            {
                "raw_name_tse": name.strip(),
                "normalized_name_tse": normalize_name(name),
                "state": state,
                "zone": int(zone),
                "url_tse": source_url,
                "year_first_treat": 2010,
                "source_title": source_title,
                "source_date": issue_date,
                "treatment_scope": "municipality_zone",
                "source_kind": "legal_act",
                "notes": "Municipality-zone pair parsed from annex text exposed on the compiled TSE page.",
            }
        )
    return rows


def _parse_2010_attachment(path: Path) -> list[dict]:
    with zipfile.ZipFile(path, "r") as archive:
        excel_name = archive.namelist()[0]
        df = pd.read_excel(io.BytesIO(archive.read(excel_name)), header=1)

    df.columns = ["state", "raw_name_tse", "zone", "qt_eleitores"]
    df["state"] = df["state"].astype(str).str.strip()
    df = df[df["state"].isin(VALID_UFS)].copy()
    df["raw_name_tse"] = df["raw_name_tse"].astype(str).str.strip()
    df["normalized_name_tse"] = df["raw_name_tse"].map(normalize_name)
    df = df[df["normalized_name_tse"] != "municipio"].copy()
    df["zone"] = df["zone"].map(zone_to_int_or_none)
    df = df.drop_duplicates(subset=["state", "normalized_name_tse"], keep="first")

    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "raw_name_tse": row["raw_name_tse"],
                "normalized_name_tse": row["normalized_name_tse"],
                "state": row["state"],
                "zone": None,
                "url_tse": "https://www.justicaeleitoral.jus.br/arquivos/tse-lista-de-cidades-onde-houve-votacao-em-urnas-com-leitor-biometrico-nas-eleicoes-2010",
                "year_first_treat": 2010,
                "source_title": "Lista de cidades onde houve votacao em urnas com leitor biometrico nas eleicoes de 2010",
                "source_date": "",
                "treatment_scope": "municipality",
                "source_kind": "official_attachment",
                "notes": "Official TSE 2010 election-use attachment. First-treatment year is later collapsed against the 2008 pilot municipalities.",
            }
        )
    return rows


def _parse_2012_attachment(path: Path) -> list[dict]:
    with zipfile.ZipFile(path, "r") as archive:
        excel_name = archive.namelist()[0]
        df = pd.read_excel(io.BytesIO(archive.read(excel_name)))

    df.columns = ["col1", "col2", "col3", "col4", "col5"]
    body = df.iloc[2:].copy()
    body["state"] = body["col1"].ffill()
    body = body[~body["state"].astype(str).str.contains("Subtotal|TOTAL", na=False)]
    body = body[body["col2"].notna()].copy()
    body["raw_name_tse"] = body["col2"].astype(str)

    rows = []
    for _, row in body[["state", "raw_name_tse"]].drop_duplicates().iterrows():
        rows.append(
            {
                "raw_name_tse": row["raw_name_tse"].strip(),
                "normalized_name_tse": normalize_name(row["raw_name_tse"]),
                "state": row["state"],
                "zone": None,
                "url_tse": SOURCE_2012_ATTACHMENT,
                "year_first_treat": 2012,
                "source_title": "Lista de localidades onde havera recadastramento biometrico em 2012",
                "source_date": "",
                "treatment_scope": "municipality",
                "source_kind": "official_attachment",
                "notes": "Official TSE attachment listing municipalities apt for biometric identification in the 2012 election cycle.",
            }
        )
    return rows


def _parse_2014_attachment(path: Path) -> list[dict]:
    reader = PdfReader(str(path))
    rows: list[dict] = []
    current_state: str | None = None
    seen: set[tuple[str, str]] = set()

    for page in reader.pages:
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("PROGRAMA DE IDENTIFICACAO") or line.startswith("PROGRAMA DE IDENTIFICA") or line.startswith("UF MUNIC"):
                continue
            if line.startswith("Subtotal") or line.startswith("TOTAL"):
                continue

            full_match = re.match(r"^([A-Z]{2})\s+(.+?)\s+([\d\.]+)$", line)
            if full_match:
                current_state, name, _ = full_match.groups()
                key = (current_state, normalize_name(name))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "raw_name_tse": name.strip(),
                        "normalized_name_tse": normalize_name(name),
                        "state": current_state,
                        "zone": None,
                        "url_tse": SOURCE_2014_ATTACHMENT,
                        "year_first_treat": 2014,
                        "source_title": "Programa de Identificacao Biometrica 2013-2014",
                        "source_date": "2013-03-04",
                        "treatment_scope": "municipality",
                        "source_kind": "official_attachment",
                        "notes": "Official TSE attachment linked from an article explicitly describing recadastramento with focus on the 2014 elections.",
                    }
                )
                continue

            partial_match = re.match(r"^(.+?)\s+([\d\.]+)$", line)
            if partial_match and current_state:
                name, _ = partial_match.groups()
                key = (current_state, normalize_name(name))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "raw_name_tse": name.strip(),
                        "normalized_name_tse": normalize_name(name),
                        "state": current_state,
                        "zone": None,
                        "url_tse": SOURCE_2014_ATTACHMENT,
                        "year_first_treat": 2014,
                        "source_title": "Programa de Identificacao Biometrica 2013-2014",
                        "source_date": "2013-03-04",
                        "treatment_scope": "municipality",
                        "source_kind": "official_attachment",
                        "notes": "Official TSE attachment linked from an article explicitly describing recadastramento with focus on the 2014 elections.",
                    }
                )

    return rows


def _aggregate_2014_open_data(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path, "r") as archive:
        csv_name = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        with archive.open(csv_name) as handle:
            df = pd.read_csv(
                handle,
                sep=";",
                encoding="latin1",
                usecols=["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "QT_ELEITORES_PERFIL", "QT_ELEITORES_BIOMETRIA"],
                dtype=str,
            )

    for column in ["QT_ELEITORES_PERFIL", "QT_ELEITORES_BIOMETRIA"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    aggregated = (
        df.groupby(["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"], as_index=False)[["QT_ELEITORES_PERFIL", "QT_ELEITORES_BIOMETRIA"]]
        .sum()
        .rename(
            columns={
                "SG_UF": "state",
                "CD_MUNICIPIO": "tse_municipality_id",
                "NM_MUNICIPIO": "raw_name_tse",
            }
        )
    )
    aggregated = aggregated[aggregated["state"].isin(VALID_UFS)].copy()
    aggregated["tse_municipality_id"] = aggregated["tse_municipality_id"].astype(str).str.split(".").str[0].str.strip()
    aggregated["raw_name_tse"] = aggregated["raw_name_tse"].astype(str).str.strip()
    aggregated["normalized_name_tse"] = aggregated["raw_name_tse"].map(normalize_name)
    aggregated["biometric_share"] = aggregated["QT_ELEITORES_BIOMETRIA"] / aggregated["QT_ELEITORES_PERFIL"].replace({0: pd.NA})
    return aggregated


def _parse_2014_open_data(path: Path) -> list[dict]:
    aggregated = _aggregate_2014_open_data(path)
    # The official TSE benchmark implies 764 municipalities voting with biometrics in 2014 or earlier.
    # The PDF attachment extraction reliably yields 458 new municipalities for the 2013-2014 cycle, but
    # misses a small number of municipalities in the full 2014 election-use set. In the election-year
    # administrative file, a municipal biometric-share cutoff of 0.45 reproduces the official cumulative
    # benchmark of 764 municipalities and isolates a clear support gap below the cutoff.
    full_biometric = aggregated[aggregated["biometric_share"] >= 0.45].copy()

    rows = []
    for _, row in full_biometric.iterrows():
        rows.append(
            {
                "tse_municipality_id": row["tse_municipality_id"],
                "raw_name_tse": row["raw_name_tse"],
                "normalized_name_tse": row["normalized_name_tse"],
                "state": row["state"],
                "zone": None,
                "url_tse": SOURCE_2014_OPEN_DATA,
                "year_first_treat": 2014,
                "source_title": "Perfil do eleitorado 2014",
                "source_date": "",
                "treatment_scope": "municipality",
                "source_kind": "official_open_data_calibrated",
                "notes": (
                    "Official TSE 2014 electorate file. Municipality retained in the 2014 election-use set when municipal biometric-elector share >= 0.45; "
                    "this reproduces the official cumulative benchmark of 764 municipalities by 2014 after combining with the 2008, 2010, and 2012 verified sets."
                ),
            }
        )
    return rows


def _aggregate_eleitorado_open_data(path: Path, usecols: list[str]) -> pd.DataFrame:
    with zipfile.ZipFile(path, "r") as archive:
        csv_name = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        with archive.open(csv_name) as handle:
            df = pd.read_csv(handle, sep=";", encoding="latin1", usecols=usecols, dtype=str)

    for column in ["QT_ELEITORES_PERFIL", "QT_ELEITORES_BIOMETRIA"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    agg_dict: dict[str, object] = {
        "QT_ELEITORES_PERFIL": "sum",
        "QT_ELEITORES_BIOMETRIA": "sum",
    }
    if "DS_MUN_SIT_BIOMETRICA" in df.columns:
        agg_dict["DS_MUN_SIT_BIOMETRICA"] = lambda s: "|".join(sorted(set(s.dropna().astype(str))))

    aggregated = (
        df.groupby(["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"], as_index=False)
        .agg(agg_dict)
        .rename(
            columns={
                "SG_UF": "state",
                "CD_MUNICIPIO": "tse_municipality_id",
                "NM_MUNICIPIO": "raw_name_tse",
            }
        )
    )
    aggregated = aggregated[aggregated["state"].isin(VALID_UFS)].copy()
    aggregated["tse_municipality_id"] = aggregated["tse_municipality_id"].astype(str).str.split(".").str[0].str.strip()
    aggregated["raw_name_tse"] = aggregated["raw_name_tse"].astype(str).str.strip()
    aggregated["normalized_name_tse"] = aggregated["raw_name_tse"].map(normalize_name)
    aggregated["biometric_share"] = aggregated["QT_ELEITORES_BIOMETRIA"] / aggregated["QT_ELEITORES_PERFIL"].where(
        aggregated["QT_ELEITORES_PERFIL"] != 0
    )
    return aggregated


def _parse_2016_open_data(path: Path) -> list[dict]:
    aggregated = _aggregate_eleitorado_open_data(
        path,
        ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "QT_ELEITORES_PERFIL", "QT_ELEITORES_BIOMETRIA"],
    )
    # The 2016 TSE article reports 1,540 municipalities voting totalmente com biometria.
    full_biometric = aggregated[aggregated["biometric_share"] >= 0.95].copy()

    rows = []
    for _, row in full_biometric.iterrows():
        rows.append(
            {
                "tse_municipality_id": row["tse_municipality_id"],
                "raw_name_tse": row["raw_name_tse"],
                "normalized_name_tse": row["normalized_name_tse"],
                "state": row["state"],
                "zone": None,
                "url_tse": SOURCE_2016_OPEN_DATA,
                "year_first_treat": 2016,
                "source_title": "Perfil do eleitorado 2016",
                "source_date": "",
                "treatment_scope": "municipality",
                "source_kind": "official_open_data_calibrated",
                "notes": (
                    "Official TSE 2016 electorate file. Municipality retained as full biometric when municipal biometric-elector share >= 0.95; "
                    "this threshold reproduces the official TSE count of 1,540 municipalities voting totalmente com biometria in 2016."
                ),
            }
        )
    return rows


def _parse_2018_open_data(path: Path) -> tuple[list[dict], pd.DataFrame]:
    aggregated = _aggregate_eleitorado_open_data(
        path,
        [
            "SG_UF",
            "CD_MUNICIPIO",
            "NM_MUNICIPIO",
            "QT_ELEITORES_PERFIL",
            "QT_ELEITORES_BIOMETRIA",
            "DS_MUN_SIT_BIOMETRICA",
        ],
    )

    full_biometric = aggregated[aggregated["DS_MUN_SIT_BIOMETRICA"] == "Biométrico"].copy()
    hybrid = aggregated[aggregated["DS_MUN_SIT_BIOMETRICA"] == "Híbrido"].copy()

    rows = []
    for _, row in full_biometric.iterrows():
        rows.append(
            {
                "tse_municipality_id": row["tse_municipality_id"],
                "raw_name_tse": row["raw_name_tse"],
                "normalized_name_tse": row["normalized_name_tse"],
                "state": row["state"],
                "zone": None,
                "url_tse": SOURCE_2018_OPEN_DATA,
                "year_first_treat": 2018,
                "source_title": "Perfil do eleitorado 2018",
                "source_date": "",
                "treatment_scope": "municipality",
                "source_kind": "official_open_data_status",
                "notes": "Official TSE 2018 electorate file marks the municipality as Biométrico in the election-year snapshot.",
            }
        )

    hybrid = hybrid[
        [
            "state",
            "tse_municipality_id",
            "raw_name_tse",
            "normalized_name_tse",
            "QT_ELEITORES_PERFIL",
            "QT_ELEITORES_BIOMETRIA",
            "biometric_share",
            "DS_MUN_SIT_BIOMETRICA",
        ]
    ].rename(
        columns={
            "QT_ELEITORES_PERFIL": "qt_eleitores_perfil",
            "QT_ELEITORES_BIOMETRIA": "qt_eleitores_biometria",
            "DS_MUN_SIT_BIOMETRICA": "status_2018",
        }
    )
    hybrid["url_tse"] = SOURCE_2018_OPEN_DATA
    hybrid["notes"] = (
        "Official TSE 2018 electorate file marks the municipality as Híbrido. These rows are kept for review and are not promoted to the clean municipality-level first-treatment dataset because municipality-wide first use may predate 2018 and zone coverage is not explicit."
    )
    return rows, hybrid


def parse_tse_rows() -> pd.DataFrame:
    ensure_directories()

    path_2008 = next(path for path in RAW_TSE_DIR.iterdir() if "resolucao-no-22-713-de-28-de-fevereiro-de-2008" in path.name)
    path_prov1 = next(path for path in RAW_TSE_DIR.iterdir() if "provimento-no-1-cge-de-2-de-fevereiro-de-2010" in path.name)
    path_prov7 = next(path for path in RAW_TSE_DIR.iterdir() if "provimento-no-7-cge-de-70-de-outubro-de-2010" in path.name)
    path_2010_attachment = next(path for path in RAW_TSE_DIR.iterdir() if "tse-lista-de-cidades-onde-houve-votacao-em-urnas-com-leitor-biometrico-nas-eleicoes-2010" in path.name)
    path_2012 = next(path for path in RAW_TSE_DIR.iterdir() if "tse-lista-de-localidades-onde-havera-recadastramento-biometrico-em-2012" in path.name)
    path_2014 = next(path for path in RAW_TSE_DIR.iterdir() if "eleitores-de-todos-os-estados-serao-identificados-pela-biometria-nas-eleicoes-de-2014" in path.name and path.suffix == ".pdf")
    path_2014_open_data = next((Path(__file__).resolve().parents[2] / "data" / "raw" / "tse_eleitorado" / "2014").glob("*.zip"))
    path_2016_open_data = next(path for path in RAW_TSE_DIR.iterdir() if "perfil_eleitorado_2016" in path.name and path.suffix == ".zip")
    path_2018_open_data = next(path for path in RAW_TSE_DIR.iterdir() if "perfil_eleitorado_2018" in path.name and path.suffix == ".zip")

    rows = []
    rows.extend(_manual_2008_rows(_read_text(path_2008)))
    rows.extend(_parse_2010_attachment(path_2010_attachment))
    rows.extend(_parse_2012_attachment(path_2012))
    rows.extend(_parse_2014_open_data(path_2014_open_data))
    rows.extend(_parse_2016_open_data(path_2016_open_data))
    rows_2018, hybrid_2018 = _parse_2018_open_data(path_2018_open_data)
    rows.extend(rows_2018)

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("No TSE rows were parsed.")

    if "tse_municipality_id" not in df.columns:
        df["tse_municipality_id"] = None
    df["tse_municipality_id"] = df["tse_municipality_id"].fillna("").astype(str).str.strip()
    df["zone"] = df["zone"].map(zone_to_int_or_none)
    df["zone_key"] = df["zone"].map(lambda value: "" if value is None else str(value))
    df = (
        df.sort_values(["state", "normalized_name_tse", "zone_key", "year_first_treat", "url_tse", "tse_municipality_id"])
        .drop_duplicates(subset=["state", "normalized_name_tse", "zone_key", "year_first_treat", "url_tse", "tse_municipality_id"])
        .reset_index(drop=True)
    )
    df.to_csv(INTERIM_DIR / "tse_parsed_rows.csv", index=False)
    hybrid_2018.to_csv(INTERIM_DIR / "hybrid_2018_review.csv", index=False)
    return df


def main() -> None:
    parse_tse_rows()


if __name__ == "__main__":
    main()
