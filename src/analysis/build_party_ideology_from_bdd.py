from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account


ROOT = Path(__file__).resolve().parents[2]
CREDENTIALS_PATH = ROOT / "credentials" / "gcp-key.json"

INTERIM_DIR = ROOT / "data" / "interim" / "party_ideology"
CLEAN_DIR = ROOT / "data" / "clean" / "party_ideology"
DOCS_DIR = ROOT / "docs"

PARTY_YEAR_PATH = INTERIM_DIR / "bdd_voted_party_years_2000_2024.parquet"
PARTY_YEAR_CSV_PATH = INTERIM_DIR / "bdd_voted_party_years_2000_2024.csv"
CROSSWALK_PATH = CLEAN_DIR / "party_lcr_crosswalk_2000_2024.parquet"
CROSSWALK_CSV_PATH = CLEAN_DIR / "party_lcr_crosswalk_2000_2024.csv"
QUERY_LOG_PATH = INTERIM_DIR / "bigquery_query_log.csv"
NOTES_PATH = DOCS_DIR / "PARTY_IDEOLOGY_LCR_NOTES.md"
DATA_SOURCES_PATH = DOCS_DIR / "DATA_SOURCES.md"

MIN_YEAR = 2000
MAX_YEAR = 2024
MAX_QUERY_BYTES = 2 * 1_000_000_000


@dataclass
class QueryRecord:
    label: str
    bytes_processed: int
    destination: str
    cached: bool


def ensure_dirs() -> None:
    for path in [INTERIM_DIR, CLEAN_DIR, DOCS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def make_client() -> bigquery.Client:
    with CREDENTIALS_PATH.open() as handle:
        creds_info = json.load(handle)
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
            f"Query `{label}` would process {processed / 1e9:.2f} GB, above the 2 GB guardrail."
        )
    return processed


def query_to_frame(
    client: bigquery.Client,
    label: str,
    query: str,
    cache_path: Path,
    *,
    force: bool,
    query_log: list[QueryRecord],
) -> pd.DataFrame:
    processed = dry_run(client, query, label)
    if cache_path.exists() and not force:
        print(f"{label}: using cached {cache_path.relative_to(ROOT)}")
        query_log.append(QueryRecord(label, processed, str(cache_path.relative_to(ROOT)), True))
        return pd.read_parquet(cache_path)

    df = client.query(query).result().to_dataframe()
    df.to_parquet(cache_path, index=False)
    df.to_csv(cache_path.with_suffix(".csv"), index=False)
    query_log.append(QueryRecord(label, processed, str(cache_path.relative_to(ROOT)), False))
    return df


def voted_party_years_query() -> str:
    return f"""
WITH candidate_votes AS (
  SELECT
    ano,
    UPPER(TRIM(sigla_partido)) AS party,
    NULLIF(TRIM(numero_partido), '') AS party_number,
    SUM(COALESCE(votos, 0)) AS candidate_votes,
    0 AS party_list_votes,
    COUNT(*) AS candidate_result_rows,
    0 AS party_result_rows
  FROM `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`
  WHERE ano BETWEEN {MIN_YEAR} AND {MAX_YEAR}
    AND sigla_partido IS NOT NULL
    AND TRIM(sigla_partido) != ''
  GROUP BY ano, party, party_number
),
party_votes AS (
  SELECT
    ano,
    UPPER(TRIM(sigla_partido)) AS party,
    NULLIF(TRIM(numero_partido), '') AS party_number,
    0 AS candidate_votes,
    SUM(COALESCE(votos_nominais, 0) + COALESCE(votos_legenda, 0)) AS party_list_votes,
    0 AS candidate_result_rows,
    COUNT(*) AS party_result_rows
  FROM `basedosdados.br_tse_eleicoes.resultados_partido_municipio`
  WHERE ano BETWEEN {MIN_YEAR} AND {MAX_YEAR}
    AND sigla_partido IS NOT NULL
    AND TRIM(sigla_partido) != ''
  GROUP BY ano, party, party_number
),
combined AS (
  SELECT * FROM candidate_votes
  UNION ALL
  SELECT * FROM party_votes
),
party_names AS (
  SELECT
    ano,
    UPPER(TRIM(sigla)) AS party,
    NULLIF(TRIM(numero), '') AS party_number,
    STRING_AGG(DISTINCT NULLIF(TRIM(nome), ''), ' | ' ORDER BY NULLIF(TRIM(nome), '')) AS party_names
  FROM `basedosdados.br_tse_eleicoes.partidos`
  WHERE ano BETWEEN {MIN_YEAR} AND {MAX_YEAR}
    AND sigla IS NOT NULL
    AND TRIM(sigla) != ''
  GROUP BY ano, party, party_number
),
party_year AS (
  SELECT
    ano AS year,
    party,
    party_number,
    SUM(candidate_votes) AS candidate_votes,
    SUM(party_list_votes) AS party_list_votes,
    SUM(candidate_result_rows) AS candidate_result_rows,
    SUM(party_result_rows) AS party_result_rows
  FROM combined
  GROUP BY year, party, party_number
)
SELECT
  party_year.year,
  party_year.party,
  party_year.party_number,
  COALESCE(party_names.party_names, '') AS party_names,
  party_year.candidate_votes,
  party_year.party_list_votes,
  GREATEST(party_year.candidate_votes, party_year.party_list_votes) AS max_votes_observed,
  party_year.candidate_result_rows,
  party_year.party_result_rows
FROM party_year
LEFT JOIN party_names
  ON party_year.year = party_names.ano
 AND party_year.party = party_names.party
 AND COALESCE(party_year.party_number, '') = COALESCE(party_names.party_number, '')
WHERE party_year.candidate_votes > 0 OR party_year.party_list_votes > 0
ORDER BY party_year.year, party_year.party, party_year.party_number
"""


def normalize_party_key(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"\s+", " ", text)
    return text


LEFT_PARTIES = {
    normalize_party_key(party)
    for party in ["PSTU", "PCO", "PSOL", "PCB", "UP", "PT", "PCdoB", "PC do B"]
}
CENTER_PARTIES = {
    normalize_party_key(party)
    for party in [
        "PDT",
        "PSB",
        "REDE",
        "CIDADANIA",
        "PPS",
        "PV",
        "PMDB",
        "MDB",
        "PSDB",
        "PTN",
        "PST",
        "PGT",
        "PAN",
        "PTB",
        "AVANTE",
        "PT do B",
        "SDD",
        "SOLIDARIEDADE",
    ]
}
RIGHT_PARTIES = {
    normalize_party_key(party)
    for party in [
        "PPR",
        "PFL",
        "PRONA",
        "DEM",
        "PRTB",
        "AGIR",
        "PRN",
        "PTC",
        "UNIÃO",
        "DC",
        "PODE",
        "PODEMOS",
        "NOVO",
        "PP",
        "PPB",
        "PSL",
        "PSD",
        "PSC",
        "PL",
        "PR",
        "REPUBLICANOS",
        "PRP",
        "PRB",
        "PSDC",
        "PATRIOTA",
        "PROS",
        "PPL",
        "PMN",
        "PMB",
        "PHS",
        "MOBILIZA",
    ]
}


def party_ideology(party: object) -> str:
    key = normalize_party_key(party)
    if key in LEFT_PARTIES:
        return "L"
    if key in CENTER_PARTIES:
        return "C"
    if key in RIGHT_PARTIES:
        return "R"
    return "IDK"


def collapse_party_crosswalk(party_years: pd.DataFrame) -> pd.DataFrame:
    df = party_years.copy()
    df["party_key"] = df["party"].map(normalize_party_key)
    df["ideology_lcr"] = df["party"].map(party_ideology)
    df["party_number"] = df["party_number"].fillna("").astype(str)
    df["party_names"] = df["party_names"].fillna("").astype(str)

    def join_unique(values: pd.Series) -> str:
        cleaned = sorted({str(value).strip() for value in values if str(value).strip()})
        return " | ".join(cleaned)

    out = (
        df.groupby(["party_key", "ideology_lcr"], as_index=False)
        .agg(
            party=("party", join_unique),
            party_numbers=("party_number", join_unique),
            party_names=("party_names", join_unique),
            first_year_voted=("year", "min"),
            last_year_voted=("year", "max"),
            years_voted=("year", lambda values: ", ".join(str(int(year)) for year in sorted(set(values)))),
            n_years_voted=("year", "nunique"),
            candidate_votes=("candidate_votes", "sum"),
            party_list_votes=("party_list_votes", "sum"),
            max_votes_observed=("max_votes_observed", "sum"),
            candidate_result_rows=("candidate_result_rows", "sum"),
            party_result_rows=("party_result_rows", "sum"),
        )
        .sort_values(["ideology_lcr", "party_key"])
    )
    return out[
        [
            "party",
            "party_key",
            "ideology_lcr",
            "party_numbers",
            "party_names",
            "first_year_voted",
            "last_year_voted",
            "years_voted",
            "n_years_voted",
            "candidate_votes",
            "party_list_votes",
            "max_votes_observed",
            "candidate_result_rows",
            "party_result_rows",
        ]
    ]


def write_notes(crosswalk: pd.DataFrame, party_years: pd.DataFrame) -> None:
    ideology_counts = crosswalk["ideology_lcr"].value_counts().sort_index()
    year_counts = party_years.groupby("year")["party"].nunique().reset_index(name="n_parties_voted")
    idk_parties = crosswalk.loc[crosswalk["ideology_lcr"] == "IDK", "party"].tolist()

    lines = [
        "# Party Ideology L/C/R Crosswalk",
        "",
        f"- Source: Base dos Dados BigQuery dataset `basedosdados.br_tse_eleicoes`, years {MIN_YEAR}-{MAX_YEAR}.",
        "- Tables used: `resultados_candidato_municipio`, `resultados_partido_municipio`, and `partidos` for names.",
        "- Inclusion rule: party-year rows with strictly positive observed candidate votes or party-list votes.",
        "- Vote columns are source-specific; `max_votes_observed` avoids double counting nominal votes that appear in both TSE result tables.",
        "- Ideology coding: direct application of the L/C/R/IDK party-sigla mapping supplied by Gabriel on 2026-04-27.",
        f"- Party-year output: `{PARTY_YEAR_PATH.relative_to(ROOT)}` and `.csv`.",
        f"- Clean crosswalk: `{CROSSWALK_PATH.relative_to(ROOT)}` and `.csv`.",
        f"- BigQuery dry-run log: `{QUERY_LOG_PATH.relative_to(ROOT)}`.",
        "",
        "## Ideology Counts",
        "",
        "```text",
        ideology_counts.to_string(),
        "```",
        "",
        "## Parties Per Year",
        "",
        "```text",
        year_counts.to_string(index=False),
        "```",
        "",
        "## IDK Parties",
        "",
        ", ".join(idk_parties) if idk_parties else "None.",
        "",
    ]
    NOTES_PATH.write_text("\n".join(lines), encoding="utf-8")


def update_data_sources() -> None:
    marker = "\n## Party ideology L/C/R crosswalk\n"
    entry = f"""{marker}
- Source: Base dos Dados BigQuery dataset `basedosdados.br_tse_eleicoes`, covering election-result tables from {MIN_YEAR} through {MAX_YEAR}.
- Tables used: `resultados_candidato_municipio` and `resultados_partido_municipio` to identify parties with positive observed votes; `partidos` to recover official party names where available.
- Access pattern: Google BigQuery through the local service-account credentials in `credentials/gcp-key.json`, with a dry run before execution and cached outputs under `data/interim/party_ideology/`.
- Interim output: `data/interim/party_ideology/bdd_voted_party_years_2000_2024.csv` and `.parquet`.
- Clean output: `data/clean/party_ideology/party_lcr_crosswalk_2000_2024.csv` and `.parquet`.
- Coding rule: each party sigla is assigned `L`, `C`, `R`, or `IDK` using the explicit mapping supplied by Gabriel on 2026-04-27; party keys are uppercased and accent-insensitive for matching.
"""
    DATA_SOURCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    current = DATA_SOURCES_PATH.read_text(encoding="utf-8") if DATA_SOURCES_PATH.exists() else "# Data Sources\n"
    if marker in current:
        current = current.split(marker)[0].rstrip() + "\n" + entry
    else:
        current = current.rstrip() + "\n" + entry
    DATA_SOURCES_PATH.write_text(current, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-run the BigQuery query instead of using the cached parquet.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()
    query_log: list[QueryRecord] = []
    client = make_client()

    party_years = query_to_frame(
        client,
        "bdd_voted_party_years_2000_2024",
        voted_party_years_query(),
        PARTY_YEAR_PATH,
        force=args.force,
        query_log=query_log,
    )
    party_years.to_csv(PARTY_YEAR_CSV_PATH, index=False)

    crosswalk = collapse_party_crosswalk(party_years)
    crosswalk.to_parquet(CROSSWALK_PATH, index=False)
    crosswalk.to_csv(CROSSWALK_CSV_PATH, index=False)

    pd.DataFrame([record.__dict__ for record in query_log]).to_csv(QUERY_LOG_PATH, index=False)
    write_notes(crosswalk, party_years)
    update_data_sources()

    print(f"Wrote {CROSSWALK_PATH.relative_to(ROOT)}")
    print(f"Wrote {CROSSWALK_CSV_PATH.relative_to(ROOT)}")
    print(f"Wrote {PARTY_YEAR_PATH.relative_to(ROOT)}")
    print("\nIdeology counts:")
    print(crosswalk["ideology_lcr"].value_counts().sort_index().to_string())
    print("\nIDK parties:")
    idk = crosswalk.loc[crosswalk["ideology_lcr"] == "IDK", "party"].tolist()
    print(", ".join(idk) if idk else "None")


if __name__ == "__main__":
    main()
