from __future__ import annotations

import argparse
import hashlib
import re
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_URL = "https://dadosabertos.tse.jus.br/dataset/rae-requerimento-de-alistamento-eleitoral"
TSE_IBGE_CODES_DATASET_URL = (
    "https://dadosabertos.tse.jus.br/dataset/codigos-oficiais-de-uf-e-municipios-segundo-o-tse-e-o-ibge"
)
TSE_IBGE_CODES_API_URL = (
    "https://dadosabertos.tse.jus.br/api/3/action/package_show?"
    "id=codigos-oficiais-de-uf-e-municipios-segundo-o-tse-e-o-ibge"
)
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "tse" / "rae"
RAW_TSE_IBGE_CODES_DIR = PROJECT_ROOT / "data" / "raw" / "tse" / "municipio_tse_ibge"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "tse" / "rae"
CLEAN_DIR = PROJECT_ROOT / "data" / "clean" / "tse"
DEFAULT_OUTPUT_PATH = CLEAN_DIR / "rae.parquet"

DOCUMENTED_ENCODING = "latin1"
TARGET_START_YEAR = 2009
TARGET_END_YEAR = 2020
CHUNKSIZE = 500_000

RAW_REQUIRED_COLUMNS = [
    "NR_ANO_REGISTRO",
    "NR_MES_REGISTRO",
    "SG_UF",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "DS_TIPO_OPERACAO",
    "DS_GENERO",
    "DS_FAIXA_ETARIA",
    "DS_GRAU_ESCOLARIDADE",
    "QT_RAE",
]
OUTPUT_COLUMNS = [
    "year",
    "month",
    "state",
    "tse_municipality_id",
    "municipality_id",
    "municipality_name",
    "rae_operation",
    "gender",
    "age_group",
    "education",
    "num_rae",
]
GROUP_COLUMNS = [column for column in OUTPUT_COLUMNS if column != "num_rae"]
RAW_GROUP_COLUMNS = [column for column in GROUP_COLUMNS if column != "municipality_id"]
RAW_NUMERIC_COLUMNS = ["NR_ANO_REGISTRO", "NR_MES_REGISTRO", "QT_RAE"]
NUMERIC_COLUMNS = ["year", "month", "num_rae"]
TEXT_COLUMNS = [
    "state",
    "tse_municipality_id",
    "municipality_name",
    "rae_operation",
    "gender",
    "age_group",
    "education",
]
CATEGORICAL_COLUMNS = TEXT_COLUMNS
STRING_COLUMNS = ["municipality_id"]
BRAZILIAN_UFS = {
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
EXCLUDED_UFS = {"ZZ"}
NUMERIC_DTYPE = {
    "year": "Int16",
    "month": "Int8",
    "num_rae": "Int64",
}
RAW_TO_OUTPUT_RENAME = {
    "NR_ANO_REGISTRO": "year",
    "NR_MES_REGISTRO": "month",
    "SG_UF": "state",
    "CD_MUNICIPIO": "tse_municipality_id",
    "NM_MUNICIPIO": "municipality_name",
    "DS_TIPO_OPERACAO": "rae_operation",
    "DS_GENERO": "gender",
    "DS_FAIXA_ETARIA": "age_group",
    "DS_GRAU_ESCOLARIDADE": "education",
    "QT_RAE": "num_rae",
}
NUMERIC_NULL_SENTINELS = {"#NULO": "-1", "#NE": "-3"}
TEXT_NULL_MARKERS = {"#NULO", "#NE", ""}
MOJIBAKE_MARKERS = ("Ã", "Â", "\x81")
RESOURCE_YEAR_RE = re.compile(r"perfil_rae_(\d{4})\.(?:zip|csv)$", re.IGNORECASE)
RESOURCE_TITLE_RE = re.compile(r"Perfil\s+RAE\s*-\s*(\d{4})", re.IGNORECASE)


@dataclass(frozen=True)
class Resource:
    year: int
    url: str
    source_page: str
    format: str


def ensure_directories() -> None:
    for path in [RAW_DIR, RAW_TSE_IBGE_CODES_DIR, INTERIM_DIR, CLEAN_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def request_with_retries(
    session: requests.Session,
    method: str,
    url: str,
    *,
    timeout: int,
    retries: int,
    backoff: float,
    stream: bool = False,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.request(
                method,
                url,
                allow_redirects=True,
                stream=stream,
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(backoff * attempt)
    raise RuntimeError(f"{method} request failed after {retries} attempts for {url}: {last_error}") from last_error


def file_name_from_url(url: str, year: int) -> str:
    name = Path(urlparse(url).path).name
    return name or f"perfil_rae_{year}.zip"


def resource_format_from_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower().lstrip(".")
    return suffix.upper() if suffix else ""


def normalize_code(value: object, width: int | None = None) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(character for character in text if character.isdigit())
    if not digits:
        return ""
    if width is None:
        return digits.lstrip("0") or "0"
    return digits.zfill(width)


def discover_resources(
    *,
    start_year: int,
    end_year: int,
    session: requests.Session,
    retries: int,
    backoff: float,
) -> list[Resource]:
    response = request_with_retries(
        session,
        "GET",
        DATASET_URL,
        timeout=60,
        retries=retries,
        backoff=backoff,
    )
    soup = BeautifulSoup(response.text, "html.parser")

    direct_links: dict[int, str] = {}
    resource_pages: dict[int, str] = {}
    for anchor in soup.find_all("a", href=True):
        text = " ".join(anchor.get_text(" ", strip=True).split())
        href = urljoin(DATASET_URL, anchor["href"])

        direct_match = RESOURCE_YEAR_RE.search(Path(urlparse(href).path).name)
        if direct_match:
            direct_links[int(direct_match.group(1))] = href
            continue

        title_match = RESOURCE_TITLE_RE.search(text)
        if title_match:
            resource_pages[int(title_match.group(1))] = href

    missing_direct = [year for year in range(start_year, end_year + 1) if year not in direct_links]
    for year in missing_direct:
        page = resource_pages.get(year)
        if not page:
            continue
        resource_response = request_with_retries(
            session,
            "GET",
            page,
            timeout=60,
            retries=retries,
            backoff=backoff,
        )
        resource_soup = BeautifulSoup(resource_response.text, "html.parser")
        for anchor in resource_soup.find_all("a", href=True):
            href = urljoin(page, anchor["href"])
            direct_match = RESOURCE_YEAR_RE.search(Path(urlparse(href).path).name)
            if direct_match and int(direct_match.group(1)) == year:
                direct_links[year] = href
                break

    missing = [year for year in range(start_year, end_year + 1) if year not in direct_links]
    if missing:
        raise RuntimeError(f"Could not discover RAE download links for years: {missing}")

    resources = []
    for year in range(start_year, end_year + 1):
        url = direct_links[year]
        resources.append(
            Resource(
                year=year,
                url=url,
                source_page=resource_pages.get(year, DATASET_URL),
                format=resource_format_from_url(url),
            )
        )
    return resources


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_resource(
    resource: Resource,
    *,
    session: requests.Session,
    retries: int,
    backoff: float,
) -> dict:
    raw_year_dir = RAW_DIR / str(resource.year)
    raw_year_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_year_dir / file_name_from_url(resource.url, resource.year)

    expected_size: int | None = None
    head_note = ""
    try:
        head = request_with_retries(
            session,
            "HEAD",
            resource.url,
            timeout=60,
            retries=retries,
            backoff=backoff,
        )
        content_length = head.headers.get("content-length")
        expected_size = int(content_length) if content_length else None
        head.close()
    except RuntimeError as exc:
        head_note = f"HEAD unavailable; validated by GET only. {exc}"

    if destination.exists():
        if expected_size is not None and destination.stat().st_size != expected_size:
            raise RuntimeError(
                f"Existing raw file {destination} has size {destination.stat().st_size}, "
                f"but TSE reports {expected_size}. Remove or quarantine the raw file before rebuilding."
            )
        status = "cached"
    else:
        tmp_destination = destination.with_suffix(destination.suffix + ".part")
        last_download_error: Exception | None = None
        for attempt in range(1, retries + 1):
            if tmp_destination.exists():
                tmp_destination.unlink()
            try:
                response = request_with_retries(
                    session,
                    "GET",
                    resource.url,
                    timeout=300,
                    retries=1,
                    backoff=backoff,
                    stream=True,
                )
            except RuntimeError as exc:
                last_download_error = exc
                if attempt < retries:
                    time.sleep(backoff * attempt)
                    continue
                break
            if expected_size is None:
                content_length = response.headers.get("content-length")
                expected_size = int(content_length) if content_length else None
            try:
                with tmp_destination.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            except (requests.ConnectionError, requests.Timeout, requests.ChunkedEncodingError) as exc:
                last_download_error = exc
            finally:
                response.close()

            tmp_size = tmp_destination.stat().st_size if tmp_destination.exists() else 0
            if expected_size is None or tmp_size == expected_size:
                tmp_destination.replace(destination)
                status = "downloaded"
                break

            last_download_error = RuntimeError(
                f"Incomplete download for {destination.name}: expected {expected_size} bytes, got {tmp_size}."
            )
            tmp_destination.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(backoff * attempt)
        else:
            raise RuntimeError(
                f"Download failed after {retries} attempts for {destination.name}: {last_download_error}"
            ) from last_download_error

    return {
        "year": resource.year,
        "source_url": resource.url,
        "source_page": resource.source_page,
        "file_name": destination.name,
        "file_format": resource.format,
        "status": status,
        "download_path": relative_path(destination),
        "content_length": expected_size if expected_size is not None else "",
        "sha256": sha256sum(destination),
        "notes": head_note or "Official TSE Open Data Portal RAE package.",
    }


def discover_tse_ibge_codes_resource(
    *,
    session: requests.Session,
    retries: int,
    backoff: float,
) -> dict:
    response = request_with_retries(
        session,
        "GET",
        TSE_IBGE_CODES_API_URL,
        timeout=60,
        retries=retries,
        backoff=backoff,
    )
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"TSE-IBGE code lookup package lookup failed: {payload}")
    resources = payload["result"].get("resources", [])
    candidates = [resource for resource in resources if resource.get("url")]
    if not candidates:
        raise RuntimeError("No downloadable resource found for TSE-IBGE municipality code lookup.")
    return candidates[0]


def download_tse_ibge_codes(
    *,
    session: requests.Session,
    retries: int,
    backoff: float,
    skip_download: bool,
) -> tuple[Path, dict]:
    resource = discover_tse_ibge_codes_resource(session=session, retries=retries, backoff=backoff)
    url = resource["url"]
    destination = RAW_TSE_IBGE_CODES_DIR / (Path(urlparse(url).path).name or "municipio_tse_ibge.zip")

    expected_size: int | None = None
    if not skip_download:
        try:
            head = request_with_retries(
                session,
                "HEAD",
                url,
                timeout=60,
                retries=retries,
                backoff=backoff,
            )
            content_length = head.headers.get("content-length")
            expected_size = int(content_length) if content_length else None
            head.close()
        except RuntimeError:
            expected_size = None

    if destination.exists():
        if expected_size is not None and destination.stat().st_size != expected_size:
            raise RuntimeError(
                f"Existing TSE-IBGE lookup {destination} has size {destination.stat().st_size}, "
                f"but TSE reports {expected_size}."
            )
        status = "cached_skip_download" if skip_download else "cached"
    elif skip_download:
        raise FileNotFoundError(f"Missing cached TSE-IBGE municipality lookup: {destination}")
    else:
        tmp_destination = destination.with_suffix(destination.suffix + ".part")
        if tmp_destination.exists():
            tmp_destination.unlink()
        response = request_with_retries(
            session,
            "GET",
            url,
            timeout=120,
            retries=retries,
            backoff=backoff,
            stream=True,
        )
        if expected_size is None:
            content_length = response.headers.get("content-length")
            expected_size = int(content_length) if content_length else None
        try:
            with tmp_destination.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        finally:
            response.close()
        if expected_size is not None and tmp_destination.stat().st_size != expected_size:
            tmp_size = tmp_destination.stat().st_size
            tmp_destination.unlink(missing_ok=True)
            raise RuntimeError(
                f"Incomplete TSE-IBGE lookup download: expected {expected_size} bytes, got {tmp_size}."
            )
        tmp_destination.replace(destination)
        status = "downloaded"

    row = {
        "source_url": url,
        "source_page": TSE_IBGE_CODES_DATASET_URL,
        "file_name": destination.name,
        "file_format": resource_format_from_url(url),
        "status": status,
        "download_path": relative_path(destination),
        "content_length": expected_size if expected_size is not None else destination.stat().st_size,
        "sha256": sha256sum(destination),
        "notes": "Official TSE lookup linking TSE municipality codes to IBGE municipality codes.",
    }
    return destination, row


def write_municipality_lookup_source(row: dict) -> Path:
    output_path = INTERIM_DIR / "municipality_id_lookup_source.csv"
    pd.DataFrame([row]).to_csv(output_path, index=False)
    return output_path


def write_source_index(rows: list[dict]) -> Path:
    source_index = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    output_path = INTERIM_DIR / "source_index.csv"
    source_index.to_csv(output_path, index=False)
    return output_path


def find_csv_member(archive: zipfile.ZipFile, zip_path: Path) -> str:
    csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if not csv_members:
        raise RuntimeError(f"No CSV file found inside {zip_path}")
    preferred = [name for name in csv_members if "perfil_rae" in Path(name).name.lower()]
    return preferred[0] if preferred else csv_members[0]


@contextmanager
def open_csv_handle(path: Path, member: str | None = None) -> Iterator[tuple[BinaryIO, zipfile.ZipFile | None]]:
    if path.suffix.lower() == ".zip":
        archive = zipfile.ZipFile(path)
        selected_member = member or find_csv_member(archive, path)
        try:
            with archive.open(selected_member) as handle:
                yield handle, archive
        finally:
            archive.close()
    else:
        with path.open("rb") as handle:
            yield handle, None


def read_columns(path: Path, *, encoding: str) -> tuple[str, list[str]]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            member = find_csv_member(archive, path)
            with archive.open(member) as handle:
                columns = list(pd.read_csv(handle, sep=";", encoding=encoding, nrows=0).columns)
        return member, columns
    with path.open("rb") as handle:
        columns = list(pd.read_csv(handle, sep=";", encoding=encoding, nrows=0).columns)
    return "", columns


def load_municipality_lookup(path: Path, *, encoding: str) -> pd.DataFrame:
    required = ["SG_UF", "CD_MUNICIPIO_TSE", "CD_MUNICIPIO_IBGE", "NM_MUNICIPIO_IBGE"]
    member, columns = read_columns(path, encoding=encoding)
    missing = [column for column in required if column not in columns]
    if missing:
        raise RuntimeError(f"{path.name} is missing required TSE-IBGE lookup columns: {missing}")

    with open_csv_handle(path, member) as (handle, _archive):
        lookup = pd.read_csv(
            handle,
            sep=";",
            quotechar='"',
            encoding=encoding,
            usecols=required,
            dtype=str,
            keep_default_na=False,
        )
    lookup["state"] = lookup["SG_UF"].astype(str).str.upper().str.strip()
    lookup["_tse_municipality_key"] = lookup["CD_MUNICIPIO_TSE"].map(normalize_code)
    lookup["municipality_id"] = lookup["CD_MUNICIPIO_IBGE"].map(lambda value: normalize_code(value, width=7))
    lookup["NM_MUNICIPIO_IBGE"] = lookup["NM_MUNICIPIO_IBGE"].map(
        lambda value: clean_text_value(value, repair_mojibake=False)
    )
    lookup = lookup[["state", "_tse_municipality_key", "municipality_id", "NM_MUNICIPIO_IBGE"]].drop_duplicates()
    duplicates = int(lookup.duplicated(["state", "_tse_municipality_key"]).sum())
    if duplicates:
        raise RuntimeError(f"TSE-IBGE municipality lookup has {duplicates} duplicate SG_UF/CD_MUNICIPIO_TSE keys.")
    missing_ids = int(lookup["municipality_id"].eq("").sum())
    if missing_ids:
        raise RuntimeError(f"TSE-IBGE municipality lookup has {missing_ids} blank IBGE municipality IDs.")
    return lookup


def has_utf8_mojibake_markers(value: str) -> bool:
    return any(marker in value for marker in MOJIBAKE_MARKERS) or any(0x80 <= ord(character) <= 0x9F for character in value)


def repair_utf8_mojibake(value: str) -> str:
    if not has_utf8_mojibake_markers(value):
        return value
    try:
        repaired = value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired else value


def clean_text_value(value: object, *, repair_mojibake: bool) -> object:
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    if text in TEXT_NULL_MARKERS:
        return pd.NA
    if repair_mojibake:
        text = repair_utf8_mojibake(text)
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text


def clean_text_series(series: pd.Series, *, repair_mojibake: bool) -> pd.Series:
    return series.map(lambda value: clean_text_value(value, repair_mojibake=repair_mojibake)).astype("string")


def clean_numeric_series(series: pd.Series, column: str) -> pd.Series:
    text = series.astype("string").str.strip()
    text = text.replace(NUMERIC_NULL_SENTINELS)
    text = text.mask(text.eq(""), pd.NA)
    numeric = pd.to_numeric(text, errors="coerce")
    invalid = numeric.isna() & text.notna()
    if invalid.any():
        examples = sorted(text[invalid].dropna().astype(str).unique().tolist())[:5]
        raise ValueError(f"Column {column} contains nonnumeric values after null handling: {examples}")
    dtype = NUMERIC_DTYPE[RAW_TO_OUTPUT_RENAME.get(column, column)]
    return numeric.astype(dtype)


def clean_chunk(chunk: pd.DataFrame, *, repair_mojibake: bool) -> pd.DataFrame:
    cleaned = chunk.copy()
    for column in RAW_NUMERIC_COLUMNS:
        cleaned[column] = clean_numeric_series(cleaned[column], column)
    for column in ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "DS_TIPO_OPERACAO", "DS_GENERO", "DS_FAIXA_ETARIA", "DS_GRAU_ESCOLARIDADE"]:
        cleaned[column] = clean_text_series(cleaned[column], repair_mojibake=repair_mojibake)
    cleaned["SG_UF"] = cleaned["SG_UF"].str.upper()
    cleaned = cleaned.rename(columns=RAW_TO_OUTPUT_RENAME)
    return cleaned


def attach_municipality_ids(chunk: pd.DataFrame, municipality_lookup: pd.DataFrame) -> pd.DataFrame:
    keyed = chunk.copy()
    keyed["_tse_municipality_key"] = keyed["tse_municipality_id"].map(normalize_code)
    merged = keyed.merge(
        municipality_lookup,
        how="left",
        on=["state", "_tse_municipality_key"],
        validate="many_to_one",
    )
    merged["municipality_id"] = merged["municipality_id"].astype("string")
    merged.loc[merged["municipality_id"].eq(""), "municipality_id"] = pd.NA
    return merged[OUTPUT_COLUMNS]


def collapse_groups(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    collapsed = (
        combined.groupby(GROUP_COLUMNS, as_index=False, dropna=False, sort=False, observed=True)["num_rae"]
        .sum()
        .reset_index(drop=True)
    )
    for column in NUMERIC_COLUMNS:
        collapsed[column] = collapsed[column].astype(NUMERIC_DTYPE[column])
    for column in STRING_COLUMNS:
        collapsed[column] = collapsed[column].astype("string")
    return collapsed


def process_year(
    year: int,
    raw_path: Path,
    *,
    chunksize: int,
    encoding: str,
    repair_mojibake: bool,
    municipality_lookup: pd.DataFrame,
) -> dict:
    member, columns = read_columns(raw_path, encoding=encoding)
    missing = [column for column in RAW_REQUIRED_COLUMNS if column not in columns]
    if missing:
        raise RuntimeError(f"{raw_path.name} is missing required columns: {missing}")

    raw_rows = 0
    included_rows = 0
    raw_total = 0
    included_total = 0
    excluded_zz_rows = 0
    excluded_zz_total = 0
    negative_num_rae_rows = 0
    missing_group_key_rows = 0
    missing_municipality_id_rows = 0
    missing_brazilian_municipality_id_rows = 0
    grouped_chunks: list[pd.DataFrame] = []

    with open_csv_handle(raw_path, member) as (handle, _archive):
        reader = pd.read_csv(
            handle,
            sep=";",
            quotechar='"',
            encoding=encoding,
            usecols=RAW_REQUIRED_COLUMNS,
            dtype=str,
            keep_default_na=False,
            chunksize=chunksize,
            low_memory=False,
        )
        for chunk in reader:
            cleaned = clean_chunk(chunk, repair_mojibake=repair_mojibake)
            cleaned = attach_municipality_ids(cleaned, municipality_lookup)
            raw_rows += len(cleaned)
            raw_total += int(cleaned["num_rae"].sum())
            negative_num_rae_rows += int(cleaned["num_rae"].lt(0).sum())

            excluded = cleaned["state"].isin(EXCLUDED_UFS)
            excluded_zz_rows += int(excluded.sum())
            excluded_zz_total += int(cleaned.loc[excluded, "num_rae"].sum())
            cleaned = cleaned.loc[~excluded].copy()
            included_rows += len(cleaned)
            included_total += int(cleaned["num_rae"].sum())
            missing_group_key_rows += int(cleaned[RAW_GROUP_COLUMNS].isna().any(axis=1).sum())
            missing_municipality_id_rows += int(cleaned["municipality_id"].isna().sum())
            missing_brazilian_municipality_id_rows += int(
                (cleaned["municipality_id"].isna() & cleaned["state"].isin(BRAZILIAN_UFS)).sum()
            )

            if not cleaned.empty:
                grouped_chunks.append(
                    cleaned.groupby(GROUP_COLUMNS, as_index=False, dropna=False, sort=False, observed=True)["num_rae"]
                    .sum()
                    .reset_index(drop=True)
                )
            if len(grouped_chunks) >= 8:
                grouped_chunks = [collapse_groups(grouped_chunks)]

    year_df = collapse_groups(grouped_chunks).sort_values(GROUP_COLUMNS).reset_index(drop=True)
    year_output = INTERIM_DIR / f"rae_{year}_municipality_month_profile.parquet"
    year_df.to_parquet(year_output, index=False, engine="pyarrow", compression="zstd")
    output_total = int(year_df["num_rae"].sum()) if not year_df.empty else 0
    if included_total != output_total:
        raise RuntimeError(
            f"Aggregation changed included num_rae total for {year}: included={included_total}, output={output_total}"
        )

    return {
        "year": year,
        "raw_path": relative_path(raw_path),
        "csv_member": member,
        "raw_rows": raw_rows,
        "included_rows": included_rows,
        "excluded_zz_rows": excluded_zz_rows,
        "aggregated_rows": len(year_df),
        "raw_num_rae_total": raw_total,
        "included_num_rae_total": included_total,
        "excluded_zz_num_rae_total": excluded_zz_total,
        "aggregated_num_rae_total": output_total,
        "negative_num_rae_rows": negative_num_rae_rows,
        "rows_with_missing_group_key": missing_group_key_rows,
        "rows_with_missing_municipality_id": missing_municipality_id_rows,
        "brazilian_uf_rows_with_missing_municipality_id": missing_brazilian_municipality_id_rows,
        "interim_path": relative_path(year_output),
        "schema_columns": "|".join(columns),
    }


def finalize_dataset(years: list[int], *, output_path: Path) -> pd.DataFrame:
    frames = []
    for year in years:
        year_path = INTERIM_DIR / f"rae_{year}_municipality_month_profile.parquet"
        if not year_path.exists():
            raise FileNotFoundError(f"Missing processed year file: {year_path}")
        frames.append(pd.read_parquet(year_path))
    master = collapse_groups(frames).sort_values(GROUP_COLUMNS).reset_index(drop=True)

    duplicates = int(master.duplicated(GROUP_COLUMNS).sum())
    if duplicates:
        raise RuntimeError(f"Final RAE dataset has {duplicates} duplicate municipality-month-profile keys.")

    for column in CATEGORICAL_COLUMNS:
        master[column] = master[column].astype("string").astype("category")
    for column in STRING_COLUMNS:
        master[column] = master[column].astype("string")
    for column in NUMERIC_COLUMNS:
        master[column] = master[column].astype(NUMERIC_DTYPE[column])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    master.to_parquet(output_path, index=False, engine="pyarrow", compression="zstd")
    return master


def build_rae(
    *,
    start_year: int,
    end_year: int,
    chunksize: int,
    encoding: str,
    repair_mojibake: bool,
    output_path: Path,
    skip_download: bool,
    download_only: bool,
    keep_going: bool,
    retries: int,
    backoff: float,
) -> None:
    ensure_directories()
    years = list(range(start_year, end_year + 1))
    session = requests.Session()
    session.headers.update({"User-Agent": "bioimetric-voting-tse-rae-pipeline/1.0"})

    resources = discover_resources(
        start_year=start_year,
        end_year=end_year,
        session=session,
        retries=retries,
        backoff=backoff,
    )

    source_rows: list[dict] = []
    if skip_download:
        for resource in resources:
            raw_path = RAW_DIR / str(resource.year) / file_name_from_url(resource.url, resource.year)
            if not raw_path.exists():
                raise FileNotFoundError(f"Missing cached raw file for {resource.year}: {raw_path}")
            source_rows.append(
                {
                    "year": resource.year,
                    "source_url": resource.url,
                    "source_page": resource.source_page,
                    "file_name": raw_path.name,
                    "file_format": resource.format,
                    "status": "cached_skip_download",
                    "download_path": relative_path(raw_path),
                    "content_length": raw_path.stat().st_size,
                    "sha256": sha256sum(raw_path),
                    "notes": "Raw file already present; download skipped by user option.",
                }
            )
    else:
        for resource in resources:
            try:
                source_rows.append(
                    download_resource(resource, session=session, retries=retries, backoff=backoff)
                )
            except Exception as exc:
                if not keep_going:
                    raise
                source_rows.append(
                    {
                        "year": resource.year,
                        "source_url": resource.url,
                        "source_page": resource.source_page,
                        "file_name": file_name_from_url(resource.url, resource.year),
                        "file_format": resource.format,
                        "status": "download_failed",
                        "download_path": "",
                        "content_length": "",
                        "sha256": "",
                        "notes": str(exc),
                    }
                )

    source_index_path = write_source_index(source_rows)
    print(f"Wrote {relative_path(source_index_path)} with {len(source_rows)} rows.")
    municipality_lookup_path, municipality_lookup_row = download_tse_ibge_codes(
        session=session,
        retries=retries,
        backoff=backoff,
        skip_download=skip_download,
    )
    municipality_lookup_source_path = write_municipality_lookup_source(municipality_lookup_row)
    print(f"Wrote {relative_path(municipality_lookup_source_path)}.")
    if download_only:
        return

    failed_years = [row["year"] for row in source_rows if row["status"] == "download_failed"]
    if failed_years:
        raise RuntimeError(f"Cannot process RAE because downloads failed for years: {failed_years}")

    diagnostics = []
    municipality_lookup = load_municipality_lookup(municipality_lookup_path, encoding=encoding)
    download_path_by_year = {
        int(row["year"]): PROJECT_ROOT / row["download_path"] for row in source_rows if row["download_path"]
    }
    for year in years:
        diagnostics.append(
            process_year(
                year,
                download_path_by_year[year],
                chunksize=chunksize,
                encoding=encoding,
                repair_mojibake=repair_mojibake,
                municipality_lookup=municipality_lookup,
            )
        )
        print(f"Processed RAE {year}.")

    diagnostics_df = pd.DataFrame(diagnostics).sort_values("year").reset_index(drop=True)
    diagnostics_path = INTERIM_DIR / "build_diagnostics.csv"
    diagnostics_df.to_csv(diagnostics_path, index=False)
    print(f"Wrote {relative_path(diagnostics_path)}.")

    master = finalize_dataset(years, output_path=output_path)
    print(f"Wrote {relative_path(output_path)} with {len(master)} rows and num_rae total {int(master['num_rae'].sum())}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and aggregate TSE RAE profile data to municipality-month profile level."
    )
    parser.add_argument("--start-year", type=int, default=TARGET_START_YEAR)
    parser.add_argument("--end-year", type=int, default=TARGET_END_YEAR)
    parser.add_argument("--chunksize", type=int, default=CHUNKSIZE)
    parser.add_argument("--encoding", default=DOCUMENTED_ENCODING)
    parser.add_argument("--no-repair-mojibake", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--backoff", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.start_year > args.end_year:
        raise ValueError("--start-year must be less than or equal to --end-year")
    build_rae(
        start_year=args.start_year,
        end_year=args.end_year,
        chunksize=args.chunksize,
        encoding=args.encoding,
        repair_mojibake=not args.no_repair_mojibake,
        output_path=args.output,
        skip_download=args.skip_download,
        download_only=args.download_only,
        keep_going=args.keep_going,
        retries=args.retries,
        backoff=args.backoff,
    )


if __name__ == "__main__":
    main()
