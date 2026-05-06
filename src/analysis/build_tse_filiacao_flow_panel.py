from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests
from google.cloud import bigquery
from google.oauth2 import service_account


ROOT = Path(__file__).resolve().parents[2]
CREDENTIALS_PATH = ROOT / "credentials" / "gcp-key.json"

INTERIM_DIR = ROOT / "data" / "interim" / "tse_filiacao"
CLEAN_DIR = ROOT / "data" / "clean" / "tse_filiacao"
DOCS_DIR = ROOT / "docs"
LOG_DIR = ROOT / "resources" / "logs"

FLOW_COUNTS_PATH = INTERIM_DIR / "flow_counts_election_years.parquet"
FLOW_COUNTS_CSV_PATH = INTERIM_DIR / "flow_counts_election_years.csv"
FLOW_COUNTS_NO_DURATION_PATH = INTERIM_DIR / "flow_counts_no_duration_filter_election_years.parquet"
POPULATION_PATH = INTERIM_DIR / "ibge_population_2000_2018.parquet"
ADULT_CENSUS_PATH = INTERIM_DIR / "adult_population_census_points.parquet"
FINAL_PANEL_PATH = CLEAN_DIR / "new_affiliations_election_year_panel.parquet"
FINAL_PANEL_CSV_PATH = CLEAN_DIR / "new_affiliations_election_year_panel.csv"

SCHEMA_DOC_PATH = DOCS_DIR / "TSE_FILIACAO_BDD_SCHEMA_EXPLORATION.md"
CLEANUP_DOC_PATH = DOCS_DIR / "FILIACAO_ADMIN_CLEANUP_DIAGNOSTIC.md"
DATA_SOURCES_PATH = DOCS_DIR / "DATA_SOURCES.md"
BUILD_LOG_PATH = LOG_DIR / "tse_filiacao_flow_build_log.md"

TREATMENT_PATH = ROOT / "data" / "clean" / "tse_bvr" / "municipality_bvr_first_treat.parquet"
TSE_PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018.parquet"

ELECTION_YEARS = [2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018]
KNOWN_MUNICIPALITIES = {
    "3550308": "Sao Paulo capital",
    "3304557": "Rio de Janeiro capital",
    "5300108": "Brasilia",
    "2927408": "Salvador",
}

MAX_QUERY_BYTES = 15 * 1_000_000_000


@dataclass
class QueryRecord:
    label: str
    bytes_processed: int
    destination: str
    cached: bool


QUERY_LOG: list[QueryRecord] = []


def ensure_dirs() -> None:
    for path in [INTERIM_DIR, CLEAN_DIR, DOCS_DIR, LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def make_client() -> bigquery.Client:
    with CREDENTIALS_PATH.open() as fh:
        creds_info = json.load(fh)
    credentials = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(credentials=credentials, project=credentials.project_id)


def dry_run(client: bigquery.Client, query: str, label: str) -> int:
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    dry = client.query(query, job_config=job_config)
    processed = int(dry.total_bytes_processed or 0)
    print(f"{label}: will process {processed / 1e9:.2f} GB")
    if processed > MAX_QUERY_BYTES:
        raise RuntimeError(
            f"Query `{label}` would process {processed / 1e9:.2f} GB, above the 15 GB guardrail."
        )
    return processed


def query_to_frame(
    client: bigquery.Client,
    label: str,
    query: str,
    cache_path: Path,
    *,
    force: bool = False,
) -> pd.DataFrame:
    if cache_path.exists() and not force:
        processed = dry_run(client, query, label)
        print(f"{label}: using cached {cache_path.relative_to(ROOT)}")
        QUERY_LOG.append(QueryRecord(label, processed, str(cache_path.relative_to(ROOT)), True))
        return pd.read_parquet(cache_path)

    processed = dry_run(client, query, label)
    rows = list(client.query(query).result())
    df = pd.DataFrame([dict(row) for row in rows])
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path, index=False)
    df.to_csv(cache_path.with_suffix(".csv"), index=False)
    QUERY_LOG.append(QueryRecord(label, processed, str(cache_path.relative_to(ROOT)), False))
    return df


def normalize_sidra_value(value: object) -> float:
    if value is None:
        return math.nan
    text = str(value).strip().replace(",", ".")
    if text in {"", "...", "-", "X"}:
        return math.nan
    try:
        return float(text)
    except ValueError:
        return math.nan


def fetch_json(url: str) -> object:
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    return response.json()


def fetch_sidra_table(url: str) -> pd.DataFrame:
    payload = fetch_json(url)
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError(f"Unexpected SIDRA response for {url}: {str(payload)[:500]}")
    return pd.DataFrame(payload[1:])


def chunks(values: list[int], size: int) -> Iterable[list[int]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def metadata_categories(table_id: int, classification_id: int) -> list[dict]:
    url = f"https://servicodados.ibge.gov.br/api/v3/agregados/{table_id}/metadados"
    metadata = fetch_json(url)
    for classification in metadata["classificacoes"]:
        if classification["id"] == classification_id:
            return classification["categorias"]
    raise ValueError(f"Classification {classification_id} not found in SIDRA table {table_id}.")


def build_union_cte(where_clause: str = "") -> str:
    where_clause = f"\n  WHERE {where_clause}" if where_clause else ""
    return f"""
WITH raw AS (
  SELECT 'microdados' AS source_table,
         sigla_partido,
         sigla_uf,
         id_municipio,
         id_municipio_tse,
         titulo_eleitor AS titulo_eleitoral,
         cpf,
         nome,
         situacao_registro,
         motivo_desfiliacao,
         motivo_cancelamento,
         data_filiacao,
         data_desfiliacao,
         data_cancelamento,
         data_exclusao
  FROM `basedosdados.br_tse_filiacao_partidaria.microdados`{where_clause}
  UNION ALL
  SELECT 'microdados_antigos' AS source_table,
         sigla_partido,
         sigla_uf,
         id_municipio,
         id_municipio_tse,
         titulo_eleitoral,
         NULL AS cpf,
         nome,
         situacao_registro,
         NULL AS motivo_desfiliacao,
         motivo_cancelamento,
         data_filiacao,
         data_desfiliacao,
         data_cancelamento,
         NULL AS data_exclusao
  FROM `basedosdados.br_tse_filiacao_partidaria.microdados_antigos`{where_clause}
),
keyed AS (
  SELECT *,
         TO_HEX(SHA256(CONCAT(
           IFNULL(sigla_partido, ''), '|',
           IFNULL(sigla_uf, ''), '|',
           IFNULL(id_municipio, ''), '|',
           IFNULL(titulo_eleitoral, IFNULL(cpf, IFNULL(nome, ''))), '|',
           CAST(data_filiacao AS STRING)
         ))) AS record_key
  FROM raw
),
dedup AS (
  SELECT
    record_key,
    ANY_VALUE(sigla_partido) AS sigla_partido,
    ANY_VALUE(sigla_uf) AS sigla_uf,
    ANY_VALUE(id_municipio) AS id_municipio,
    ANY_VALUE(id_municipio_tse) AS id_municipio_tse,
    ANY_VALUE(data_filiacao) AS data_filiacao,
    MIN(data_desfiliacao) AS data_desfiliacao,
    MIN(data_cancelamento) AS data_cancelamento,
    MIN(data_exclusao) AS data_exclusao,
    STRING_AGG(DISTINCT source_table, ',' ORDER BY source_table) AS source_tables,
    COUNT(*) AS source_record_count
  FROM keyed
  GROUP BY record_key
)
"""


def run_schema_discovery(client: bigquery.Client) -> dict[str, pd.DataFrame]:
    tables = query_to_frame(
        client,
        "filiacao_tables",
        """
SELECT table_id AS table_name, row_count, size_bytes
FROM `basedosdados.br_tse_filiacao_partidaria.__TABLES__`
ORDER BY table_id
""",
        INTERIM_DIR / "schema_tables.parquet",
    )

    schema_frames: list[pd.DataFrame] = []
    for table in ["microdados", "microdados_antigos"]:
        schema = query_to_frame(
            client,
            f"{table}_columns",
            f"""
SELECT column_name, data_type, ordinal_position, is_nullable
FROM `basedosdados.br_tse_filiacao_partidaria.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = '{table}'
ORDER BY ordinal_position
""",
            INTERIM_DIR / f"schema_columns_{table}.parquet",
        )
        schema["table_name"] = table
        schema_frames.append(schema)

    samples: list[pd.DataFrame] = []
    for table in ["microdados", "microdados_antigos"]:
        sample = query_to_frame(
            client,
            f"{table}_sample_1000",
            f"""
SELECT *
FROM `basedosdados.br_tse_filiacao_partidaria.{table}`
LIMIT 1000
""",
            INTERIM_DIR / f"sample_{table}_1000.parquet",
        )
        sample["source_table"] = table
        samples.append(sample)

    totals = query_to_frame(
        client,
        "filiacao_union_dedup_totals",
        build_union_cte("data_filiacao IS NOT NULL")
        + """
SELECT COUNT(*) AS total_records,
       COUNT(DISTINCT id_municipio) AS n_muni,
       MIN(data_filiacao) AS min_date,
       MAX(data_filiacao) AS max_date,
       COUNTIF(data_filiacao BETWEEN '1998-12-01' AND '2018-11-30') AS n_in_flow_window,
       COUNTIF(source_record_count > 1) AS n_keys_with_duplicate_sources
FROM dedup
""",
        INTERIM_DIR / "union_dedup_totals.parquet",
    )

    yearly = query_to_frame(
        client,
        "filiacao_union_dedup_yearly_coverage",
        build_union_cte("data_filiacao IS NOT NULL")
        + """
SELECT EXTRACT(YEAR FROM data_filiacao) AS year_filiacao,
       COUNT(*) AS n_affiliations,
       COUNT(DISTINCT id_municipio) AS n_municipalities
FROM dedup
WHERE data_filiacao >= '1996-01-01'
  AND data_filiacao <= '2019-12-31'
GROUP BY year_filiacao
ORDER BY year_filiacao
""",
        INTERIM_DIR / "union_dedup_yearly_coverage.parquet",
    )

    id_lengths = query_to_frame(
        client,
        "filiacao_id_length_check",
        build_union_cte("data_filiacao BETWEEN '1998-12-01' AND '2018-11-30'")
        + """
SELECT LENGTH(CAST(id_municipio AS STRING)) AS id_length,
       COUNT(*) AS n
FROM dedup
GROUP BY id_length
ORDER BY id_length
""",
        INTERIM_DIR / "union_dedup_id_lengths.parquet",
    )

    known = query_to_frame(
        client,
        "filiacao_known_municipality_check",
        build_union_cte("data_filiacao BETWEEN '1998-12-01' AND '2018-11-30'")
        + """
SELECT id_municipio, COUNT(*) AS n
FROM dedup
WHERE id_municipio IN ('3550308', '3304557', '5300108', '2927408')
GROUP BY id_municipio
ORDER BY id_municipio
""",
        INTERIM_DIR / "known_municipality_counts.parquet",
    )

    status = query_to_frame(
        client,
        "filiacao_status_distribution",
        """
WITH status_rows AS (
  SELECT 'microdados' AS source_table, situacao_registro
  FROM `basedosdados.br_tse_filiacao_partidaria.microdados`
  UNION ALL
  SELECT 'microdados_antigos' AS source_table, situacao_registro
  FROM `basedosdados.br_tse_filiacao_partidaria.microdados_antigos`
)
SELECT source_table, situacao_registro, COUNT(*) AS n
FROM status_rows
GROUP BY source_table, situacao_registro
ORDER BY source_table, n DESC
""",
        INTERIM_DIR / "status_distribution.parquet",
    )

    return {
        "tables": tables,
        "columns": pd.concat(schema_frames, ignore_index=True),
        "samples": pd.concat(samples, ignore_index=True, sort=False),
        "totals": totals,
        "yearly": yearly,
        "id_lengths": id_lengths,
        "known": known,
        "status": status,
    }


def build_cleanup_diagnostic(client: bigquery.Client) -> pd.DataFrame:
    monthly = query_to_frame(
        client,
        "filiacao_monthly_disaffiliations",
        build_union_cte("data_filiacao IS NOT NULL")
        + """
SELECT DATE_TRUNC(data_desfiliacao, MONTH) AS month_end,
       COUNT(*) AS n_disaffiliations
FROM dedup
WHERE data_desfiliacao IS NOT NULL
  AND data_desfiliacao BETWEEN '1998-01-01' AND '2019-12-31'
GROUP BY month_end
ORDER BY month_end
""",
        INTERIM_DIR / "monthly_disaffiliations.parquet",
    )

    monthly["month_end"] = pd.to_datetime(monthly["month_end"])
    monthly["n_disaffiliations"] = pd.to_numeric(monthly["n_disaffiliations"])
    median = float(monthly["n_disaffiliations"].median())
    monthly["threshold_5x_median"] = 5 * median
    monthly["administrative_event_flag"] = monthly["n_disaffiliations"] > 5 * median
    monthly.to_parquet(INTERIM_DIR / "monthly_disaffiliations_flagged.parquet", index=False)
    monthly.to_csv(INTERIM_DIR / "monthly_disaffiliations_flagged.csv", index=False)
    return monthly


def build_flow_counts(client: bigquery.Client) -> tuple[pd.DataFrame, pd.DataFrame]:
    flow_query = build_union_cte("data_filiacao BETWEEN '1998-12-01' AND '2018-11-30'") + """
, election_windows AS (
  SELECT year AS election_year,
         DATE(year - 2, 12, 1) AS window_start,
         DATE(year, 11, 30) AS window_end
  FROM UNNEST([2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018]) AS year
),
flow_counts AS (
  SELECT
    ew.election_year,
    d.id_municipio,
    ANY_VALUE(d.sigla_uf) AS sigla_uf,
    COUNT(*) AS n_new_affiliations
  FROM election_windows ew
  JOIN dedup d
    ON d.data_filiacao >= ew.window_start
   AND d.data_filiacao <= ew.window_end
  WHERE d.id_municipio IS NOT NULL
    AND (
      COALESCE(d.data_desfiliacao, d.data_cancelamento, d.data_exclusao) IS NULL
      OR DATE_DIFF(COALESCE(d.data_desfiliacao, d.data_cancelamento, d.data_exclusao), d.data_filiacao, MONTH) >= 6
    )
  GROUP BY ew.election_year, d.id_municipio
)
SELECT *
FROM flow_counts
ORDER BY election_year, id_municipio
"""
    flow_counts = query_to_frame(
        client,
        "flow_counts_election_years_duration_filtered",
        flow_query,
        FLOW_COUNTS_PATH,
    )
    flow_counts.to_csv(FLOW_COUNTS_CSV_PATH, index=False)

    no_filter_query = build_union_cte("data_filiacao BETWEEN '1998-12-01' AND '2018-11-30'") + """
, election_windows AS (
  SELECT year AS election_year,
         DATE(year - 2, 12, 1) AS window_start,
         DATE(year, 11, 30) AS window_end
  FROM UNNEST([2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018]) AS year
)
SELECT
  ew.election_year,
  d.id_municipio,
  ANY_VALUE(d.sigla_uf) AS sigla_uf,
  COUNT(*) AS n_new_affiliations_no_duration_filter
FROM election_windows ew
JOIN dedup d
  ON d.data_filiacao >= ew.window_start
 AND d.data_filiacao <= ew.window_end
WHERE d.id_municipio IS NOT NULL
GROUP BY ew.election_year, d.id_municipio
ORDER BY election_year, id_municipio
"""
    no_filter = query_to_frame(
        client,
        "flow_counts_no_duration_filter",
        no_filter_query,
        FLOW_COUNTS_NO_DURATION_PATH,
    )
    return flow_counts, no_filter


def build_population(client: bigquery.Client) -> pd.DataFrame:
    return query_to_frame(
        client,
        "ibge_population_2000_2018",
        """
SELECT id_municipio, ano, populacao
FROM `basedosdados.br_ibge_populacao.municipio`
WHERE ano BETWEEN 2000 AND 2018
ORDER BY ano, id_municipio
""",
        POPULATION_PATH,
    )


def fetch_adult_census_points() -> pd.DataFrame:
    if ADULT_CENSUS_PATH.exists():
        print(f"adult_population_census_points: using cached {ADULT_CENSUS_PATH.relative_to(ROOT)}")
        return pd.read_parquet(ADULT_CENSUS_PATH)

    age_200_ids = [1143, 1144, 1145, 1146, 1147, 1148, 1149, 1150, 1151, 1152, 1153, 1154, 1155, 2503]
    age_9514_ids = [93086, 93087, 93088, 93089, 93090, 93091, 93092, 93093, 93094, 93095, 93096, 93097, 93098, 49108, 49109, 60040, 60041, 6653]

    frames: list[pd.DataFrame] = []
    for year in [2000, 2010]:
        for age_chunk in chunks(age_200_ids, 4):
            url = (
                "https://apisidra.ibge.gov.br/values/"
                f"t/200/n6/all/v/93/p/{year}/c2/0/c1/0/c58/{','.join(map(str, age_chunk))}?formato=json"
            )
            frame = fetch_sidra_table(url)
            frame["ano"] = year
            frame["id_municipio"] = frame["D1C"].astype(str)
            frame["adult_population_component"] = frame["V"].map(normalize_sidra_value)
            frames.append(frame[["id_municipio", "ano", "adult_population_component"]])

    for age_chunk in chunks(age_9514_ids, 4):
        url_2022 = (
            "https://apisidra.ibge.gov.br/values/"
            f"t/9514/n6/all/v/93/p/2022/c2/6794/c286/113635/c287/{','.join(map(str, age_chunk))}?formato=json"
        )
        frame_2022 = fetch_sidra_table(url_2022)
        frame_2022["ano"] = 2022
        frame_2022["id_municipio"] = frame_2022["D1C"].astype(str)
        frame_2022["adult_population_component"] = frame_2022["V"].map(normalize_sidra_value)
        frames.append(frame_2022[["id_municipio", "ano", "adult_population_component"]])

    adult = (
        pd.concat(frames, ignore_index=True)
        .groupby(["id_municipio", "ano"], as_index=False)["adult_population_component"]
        .sum(min_count=1)
        .rename(columns={"adult_population_component": "adult_population"})
    )
    adult["adult_population"] = adult["adult_population"].round().astype("Int64")
    adult.to_parquet(ADULT_CENSUS_PATH, index=False)
    adult.to_csv(ADULT_CENSUS_PATH.with_suffix(".csv"), index=False)
    return adult


def interpolate_adult_population(census: pd.DataFrame, panel_keys: pd.DataFrame) -> pd.DataFrame:
    wide = census.pivot(index="id_municipio", columns="ano", values="adult_population").reset_index()
    for year in [2000, 2010, 2022]:
        if year not in wide.columns:
            wide[year] = np.nan

    out = panel_keys[["id_municipio", "election_year"]].copy()
    out = out.merge(wide[["id_municipio", 2000, 2010, 2022]], on="id_municipio", how="left")

    def interp(row: pd.Series) -> float:
        year = int(row["election_year"])
        p2000, p2010, p2022 = row[2000], row[2010], row[2022]
        if year <= 2010 and pd.notna(p2000) and pd.notna(p2010):
            return float(p2000) + (float(p2010) - float(p2000)) * (year - 2000) / 10
        if year >= 2010 and pd.notna(p2010) and pd.notna(p2022):
            return float(p2010) + (float(p2022) - float(p2010)) * (year - 2010) / 12
        return math.nan

    out["adult_population"] = out.apply(interp, axis=1)
    return out[["id_municipio", "election_year", "adult_population"]]


def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> tuple[pd.Series, float, float]:
    non_missing = pd.to_numeric(series, errors="coerce").dropna()
    lo = float(non_missing.quantile(lower))
    hi = float(non_missing.quantile(upper))
    return series.clip(lo, hi), lo, hi


def build_panel(
    flow_counts: pd.DataFrame,
    no_filter: pd.DataFrame,
    population: pd.DataFrame,
    adult_census: pd.DataFrame,
    cleanup_monthly: pd.DataFrame,
) -> pd.DataFrame:
    tse_panel = pd.read_parquet(TSE_PANEL_PATH)
    treatment = pd.read_parquet(TREATMENT_PATH)

    municipalities = (
        tse_panel.sort_values(["municipality_id", "year_election"])
        .groupby("municipality_id", as_index=False)
        .agg(
            municipality_name=("municipality_name", "last"),
            sigla_uf=("state", "last"),
            hybrid_flag=("hybrid", "max"),
        )
    )
    municipalities["id_municipio"] = municipalities["municipality_id"].astype(str)

    grid = municipalities[["id_municipio", "municipality_name", "sigla_uf", "hybrid_flag"]].merge(
        pd.DataFrame({"election_year": ELECTION_YEARS}),
        how="cross",
    )

    flow = flow_counts.copy()
    flow["id_municipio"] = flow["id_municipio"].astype(str)
    flow["election_year"] = pd.to_numeric(flow["election_year"], downcast="integer")

    no_filter = no_filter.copy()
    no_filter["id_municipio"] = no_filter["id_municipio"].astype(str)
    no_filter["election_year"] = pd.to_numeric(no_filter["election_year"], downcast="integer")

    panel = grid.merge(
        flow[["id_municipio", "election_year", "n_new_affiliations"]],
        on=["id_municipio", "election_year"],
        how="left",
    )
    panel = panel.merge(
        no_filter[["id_municipio", "election_year", "n_new_affiliations_no_duration_filter"]],
        on=["id_municipio", "election_year"],
        how="left",
    )
    panel["n_new_affiliations"] = panel["n_new_affiliations"].fillna(0).astype(int)
    panel["n_new_affiliations_no_duration_filter"] = (
        panel["n_new_affiliations_no_duration_filter"].fillna(0).astype(int)
    )

    treatment = treatment.rename(
        columns={
            "municipality_id": "id_municipio",
            "year_first_treat": "first_treatment_year",
        }
    )
    treatment["id_municipio"] = treatment["id_municipio"].astype(str)
    panel = panel.merge(
        treatment[["id_municipio", "first_treatment_year"]],
        on="id_municipio",
        how="left",
    )
    panel["event_time"] = panel["election_year"] - panel["first_treatment_year"]
    panel.loc[panel["first_treatment_year"].isna(), "event_time"] = np.nan
    panel["year_treated"] = panel["first_treatment_year"].fillna(9999).astype(int)
    panel["dist_treatment"] = panel["event_time"].fillna(-9999).astype(int)

    pop = population.rename(columns={"ano": "election_year", "populacao": "population"}).copy()
    pop["id_municipio"] = pop["id_municipio"].astype(str)
    panel = panel.merge(pop, on=["id_municipio", "election_year"], how="left")
    adult = interpolate_adult_population(adult_census, panel[["id_municipio", "election_year"]])
    panel = panel.merge(adult, on=["id_municipio", "election_year"], how="left")

    panel["log_new_affiliations_raw"] = np.log1p(panel["n_new_affiliations"])
    panel["new_affiliations_per_1000_population_raw"] = (
        panel["n_new_affiliations"] / panel["population"] * 1000
    )
    panel["new_affiliations_per_1000_adult_population_raw"] = (
        panel["n_new_affiliations"] / panel["adult_population"] * 1000
    )

    outcome_map = {
        "log_new_affiliations": "log_new_affiliations_raw",
        "new_affiliations_per_pop": "new_affiliations_per_1000_population_raw",
        "new_affiliations_per_adult_pop": "new_affiliations_per_1000_adult_population_raw",
    }

    distribution_rows: list[dict[str, object]] = []
    for out_col, raw_col in outcome_map.items():
        raw = pd.to_numeric(panel[raw_col], errors="coerce")
        winsorized, lo, hi = winsorize(raw)
        panel[out_col] = winsorized
        for stage, values in [("pre_winsor", raw), ("post_winsor", winsorized)]:
            distribution_rows.append(
                {
                    "outcome": out_col,
                    "stage": stage,
                    "n": int(values.notna().sum()),
                    "mean": float(values.mean()),
                    "sd": float(values.std()),
                    "p01": float(values.quantile(0.01)),
                    "p50": float(values.quantile(0.50)),
                    "p99": float(values.quantile(0.99)),
                    "winsor_lower": lo,
                    "winsor_upper": hi,
                }
            )

    distribution = pd.DataFrame(distribution_rows)
    distribution.to_csv(INTERIM_DIR / "outcome_distribution_pre_post_winsor.csv", index=False)
    distribution.to_parquet(INTERIM_DIR / "outcome_distribution_pre_post_winsor.parquet", index=False)

    flagged_months = cleanup_monthly.loc[cleanup_monthly["administrative_event_flag"], "month_end"]
    flagged_months = pd.to_datetime(flagged_months)
    affected_years: set[int] = set()
    for election_year in ELECTION_YEARS:
        start = pd.Timestamp(year=election_year - 2, month=12, day=1)
        end = pd.Timestamp(year=election_year, month=11, day=30)
        if ((flagged_months >= start) & (flagged_months <= end)).any():
            affected_years.add(election_year)
    panel["cleanup_window_flag"] = panel["election_year"].isin(affected_years).astype(int)
    panel["post_2002_sample"] = (panel["election_year"] > 2002).astype(int)

    panel["state_year_fe"] = panel["sigla_uf"].astype(str) + "_" + panel["election_year"].astype(str)
    panel["municipality_id"] = panel["id_municipio"]

    ordered = [
        "id_municipio",
        "municipality_id",
        "municipality_name",
        "sigla_uf",
        "election_year",
        "n_new_affiliations",
        "n_new_affiliations_no_duration_filter",
        "population",
        "adult_population",
        "first_treatment_year",
        "event_time",
        "year_treated",
        "dist_treatment",
        "hybrid_flag",
        "cleanup_window_flag",
        "post_2002_sample",
        "state_year_fe",
        "log_new_affiliations_raw",
        "new_affiliations_per_1000_population_raw",
        "new_affiliations_per_1000_adult_population_raw",
        "log_new_affiliations",
        "new_affiliations_per_pop",
        "new_affiliations_per_adult_pop",
    ]
    panel = panel[ordered].sort_values(["id_municipio", "election_year"]).reset_index(drop=True)
    panel.to_parquet(FINAL_PANEL_PATH, index=False)
    panel.to_csv(FINAL_PANEL_CSV_PATH, index=False)

    return panel


def md_table(df: pd.DataFrame, columns: Iterable[str] | None = None, max_rows: int | None = None) -> str:
    out = df.copy()
    if columns is not None:
        out = out[list(columns)]
    if max_rows is not None:
        out = out.head(max_rows)
    if out.empty:
        return "_No rows._"
    return out.to_markdown(index=False)


def write_schema_doc(frames: dict[str, pd.DataFrame], panel: pd.DataFrame) -> None:
    totals = frames["totals"].iloc[0].to_dict()
    yearly = frames["yearly"].copy()
    thin = yearly[(yearly["year_filiacao"] >= 2000) & (yearly["year_filiacao"] <= 2018)]
    thin_years = thin.loc[thin["n_affiliations"] < 500_000, "year_filiacao"].astype(int).tolist()
    known = frames["known"].copy()
    known["municipality"] = known["id_municipio"].map(KNOWN_MUNICIPALITIES)

    columns = frames["columns"].sort_values(["table_name", "ordinal_position"])
    status = frames["status"].copy()

    lines = [
        "# TSE Filiacao Base dos Dados Schema Exploration",
        "",
        "Generated by `src/analysis/build_tse_filiacao_flow_panel.py`.",
        "",
        "## Tables discovered",
        "",
        md_table(frames["tables"]),
        "",
        "The metadata query requested in the prompt needed two adjustments in this BigQuery project: "
        "`__TABLES__` exposes `table_id` rather than `table_name`, and the local "
        "`INFORMATION_SCHEMA.COLUMNS` result does not expose a `description` field. "
        "The alternate project-level schema search against `basedosdados.INFORMATION_SCHEMA.SCHEMATA` "
        "was not permitted for these credentials, but the expected filiation dataset exists and was "
        "queried directly. The verified structural schema is below.",
        "",
        "## Column schema",
        "",
        md_table(columns, ["table_name", "ordinal_position", "column_name", "data_type", "is_nullable"]),
        "",
        "## Column decisions",
        "",
        "- Main source: deduplicated union of `microdados` and `microdados_antigos`.",
        "- Affiliation start date: `data_filiacao`.",
        "- Affiliation end date: `data_desfiliacao`, with `data_cancelamento` and `data_exclusao` used as fallback invalidation dates for the six-month duration filter.",
        "- Status column: `situacao_registro`.",
        "- Municipality identifier: `id_municipio`, verified as a 7-digit IBGE code when non-missing.",
        "- State: `sigla_uf`.",
        "- Party sigla: `sigla_partido`.",
        "- Party number: not present in either discovered table.",
        "",
        "## Deduplicated union totals",
        "",
        md_table(pd.DataFrame([totals])),
        "",
        "The deduplicated union is used because `microdados` alone undercounts historical flow and "
        "`microdados_antigos` overlaps substantially with current records. Deduplication keys use party, state, "
        "municipality, voter title when available, CPF or name as fallback, and `data_filiacao`.",
        "",
        "## Temporal and geographic coverage",
        "",
        md_table(yearly),
        "",
        f"Years from 2000 through 2018 below the prompt's 500,000-affiliation heuristic: `{thin_years}`.",
        "This means the 2000 and 2002 election windows should be treated cautiously and are included as a robustness exclusion.",
        "",
        "## Municipality code checks",
        "",
        md_table(frames["id_lengths"]),
        "",
        md_table(known, ["id_municipio", "municipality", "n"]),
        "",
        "## Status values",
        "",
        md_table(status),
        "",
        "## Final panel checks",
        "",
        f"- Final grid rows: `{len(panel):,}`.",
        f"- Municipalities: `{panel['id_municipio'].nunique():,}`.",
        f"- Election years: `{sorted(panel['election_year'].unique().tolist())}`.",
        f"- Rows with missing total population: `{int(panel['population'].isna().sum()):,}`.",
        f"- Rows with missing adult population: `{int(panel['adult_population'].isna().sum()):,}`.",
        "",
    ]
    SCHEMA_DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_cleanup_doc(monthly: pd.DataFrame) -> None:
    median = float(monthly["n_disaffiliations"].median())
    top = monthly.sort_values("n_disaffiliations", ascending=False).head(50).copy()
    flagged = monthly[monthly["administrative_event_flag"]].sort_values("month_end").copy()
    for frame in [top, flagged]:
        frame["month_end"] = pd.to_datetime(frame["month_end"]).dt.strftime("%Y-%m-%d")

    lines = [
        "# Filiacao Administrative Cleanup Diagnostic",
        "",
        "Generated by `src/analysis/build_tse_filiacao_flow_panel.py`.",
        "",
        "The diagnostic counts deduplicated affiliation records by `data_desfiliacao` month. "
        "A month is flagged as an administrative event when its disaffiliation count is more than five times "
        "the median monthly count among months with disaffiliations in 1998-2019.",
        "",
        f"- Median monthly disaffiliation count: `{median:,.0f}`.",
        f"- Five-times-median threshold: `{5 * median:,.0f}`.",
        f"- Flagged months: `{len(flagged):,}`.",
        "",
        "## Flagged administrative-event months",
        "",
        md_table(flagged, ["month_end", "n_disaffiliations", "threshold_5x_median", "administrative_event_flag"]),
        "",
        "## Top 50 disaffiliation months",
        "",
        md_table(top, ["month_end", "n_disaffiliations", "threshold_5x_median", "administrative_event_flag"]),
        "",
        "The main outcome in this module is inflow of new affiliations, so these cleanup events are not interpreted "
        "as political behavior. They are used to mark election windows for a primary-outcome robustness check.",
        "",
    ]
    CLEANUP_DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


def append_data_sources() -> None:
    block = """

## TSE party affiliation flow

- Source: Base dos Dados BigQuery dataset `basedosdados.br_tse_filiacao_partidaria`.
- Tables used: deduplicated union of `microdados` and `microdados_antigos`.
- Access pattern: Google BigQuery through the local service-account credentials in `credentials/gcp-key.json`, with dry runs before execution and cached parquet outputs under `data/interim/tse_filiacao/`.
- Key columns: `data_filiacao`, `data_desfiliacao`, `data_cancelamento`, `data_exclusao`, `situacao_registro`, `id_municipio`, `sigla_uf`, and `sigla_partido`.
- Clean output: `data/clean/tse_filiacao/new_affiliations_election_year_panel.parquet`.
- Notes: the analytical flow outcome counts new affiliation start events in non-overlapping two-year windows from December 1 of `t-2` through November 30 of election year `t`. The primary count excludes records invalidated within six months of `data_filiacao`.

## IBGE population denominators for affiliation flow

- Total municipal population: Base dos Dados BigQuery table `basedosdados.br_ibge_populacao.municipio`, years 2000-2018.
- Adult population robustness denominator: official IBGE SIDRA census tables. Table 200 supplies 2000 and 2010 age-group counts; table 9514 supplies 2022 age-by-sex counts. The script sums ages 15+ and linearly interpolates adult population to election years.
- Cached outputs: `data/interim/tse_filiacao/ibge_population_2000_2018.parquet` and `data/interim/tse_filiacao/adult_population_census_points.parquet`.
"""
    if DATA_SOURCES_PATH.exists():
        existing = DATA_SOURCES_PATH.read_text(encoding="utf-8")
        if "## TSE party affiliation flow" in existing:
            return
        DATA_SOURCES_PATH.write_text(existing.rstrip() + block + "\n", encoding="utf-8")
    else:
        DATA_SOURCES_PATH.write_text("# Data Sources\n" + block + "\n", encoding="utf-8")


def write_build_log(panel: pd.DataFrame) -> None:
    log = pd.DataFrame([record.__dict__ for record in QUERY_LOG])
    log.to_csv(INTERIM_DIR / "bigquery_query_log.csv", index=False)
    total_bytes = int(log.loc[~log["cached"], "bytes_processed"].sum()) if not log.empty else 0
    potential_bytes = int(log["bytes_processed"].sum()) if not log.empty else 0
    summary = panel.groupby("election_year", as_index=False).agg(
        total_new_affiliations=("n_new_affiliations", "sum"),
        total_new_affiliations_no_duration_filter=("n_new_affiliations_no_duration_filter", "sum"),
        municipalities_with_positive_flow=("n_new_affiliations", lambda s: int((s > 0).sum())),
        population_missing=("population", lambda s: int(s.isna().sum())),
        adult_population_missing=("adult_population", lambda s: int(s.isna().sum())),
    )
    summary.to_csv(INTERIM_DIR / "flow_panel_election_year_summary.csv", index=False)

    lines = [
        "# TSE Filiacao Flow Build Log",
        "",
        f"- Final panel: `{FINAL_PANEL_PATH.relative_to(ROOT)}`",
        f"- Rows: `{len(panel):,}`",
        f"- Municipalities: `{panel['id_municipio'].nunique():,}`",
        f"- BigQuery bytes processed in uncached queries during this run: `{total_bytes / 1e9:.2f} GB`",
        f"- Dry-run bytes represented by the cached/query outputs: `{potential_bytes / 1e9:.2f} GB`",
        "- Every analytical query was dry-run before execution or cache reuse, and every single dry run was below the 15 GB guardrail.",
        "",
        "## Query log",
        "",
        md_table(log),
        "",
        "## Election-year summary",
        "",
        md_table(summary),
        "",
    ]
    BUILD_LOG_PATH.write_text("\n".join(lines), encoding="utf-8")


def validate_panel(panel: pd.DataFrame) -> None:
    expected_rows = len(ELECTION_YEARS) * panel["id_municipio"].nunique()
    if len(panel) != expected_rows:
        raise ValueError(f"Panel has {len(panel):,} rows; expected full grid of {expected_rows:,}.")
    if panel.duplicated(["id_municipio", "election_year"]).any():
        raise ValueError("Panel has duplicate id_municipio x election_year rows.")

    id_lengths = panel["id_municipio"].str.len().value_counts(dropna=False).to_dict()
    bad_lengths = {length: count for length, count in id_lengths.items() if length != 7}
    if bad_lengths:
        raise ValueError(f"Unexpected municipality id lengths in final panel: {bad_lengths}")

    missing_known = set(KNOWN_MUNICIPALITIES) - set(panel["id_municipio"].unique())
    if missing_known:
        raise ValueError(f"Known municipality ids missing from final panel: {missing_known}")


def main() -> None:
    ensure_dirs()
    client = make_client()

    schema_frames = run_schema_discovery(client)
    cleanup_monthly = build_cleanup_diagnostic(client)
    flow_counts, no_filter = build_flow_counts(client)
    population = build_population(client)
    adult_census = fetch_adult_census_points()
    panel = build_panel(flow_counts, no_filter, population, adult_census, cleanup_monthly)
    validate_panel(panel)

    write_schema_doc(schema_frames, panel)
    write_cleanup_doc(cleanup_monthly)
    append_data_sources()
    write_build_log(panel)

    print(f"Wrote {FINAL_PANEL_PATH.relative_to(ROOT)} with {len(panel):,} rows.")


if __name__ == "__main__":
    main()
