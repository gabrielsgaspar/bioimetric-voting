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

INTERIM_DIR = ROOT / "data" / "interim" / "tse"
CLEAN_DIR = ROOT / "data" / "clean" / "tse"
DOCS_DIR = ROOT / "docs"

PARTY_IDEOLOGY_PATH = ROOT / "data" / "clean" / "party_ideology" / "party_lcr_crosswalk_2000_2024.parquet"
PARTY_VOTES_PATH = INTERIM_DIR / "tse_vereador_party_votes_bdd_2000_2020.parquet"
PARTY_VOTES_CSV_PATH = INTERIM_DIR / "tse_vereador_party_votes_bdd_2000_2020.csv"
OUTPUT_PATH = CLEAN_DIR / "tse_vereador_ideology_votes.parquet"
OUTPUT_CSV_PATH = CLEAN_DIR / "tse_vereador_ideology_votes.csv"
DIAGNOSTICS_PATH = INTERIM_DIR / "tse_vereador_ideology_votes_diagnostics.csv"
QUERY_LOG_PATH = INTERIM_DIR / "tse_vereador_ideology_votes_bigquery_log.csv"
NOTES_PATH = DOCS_DIR / "TSE_VEREADOR_IDEOLOGY_VOTES_NOTES.md"
DATA_SOURCES_PATH = DOCS_DIR / "DATA_SOURCES.md"

MUNICIPAL_ELECTION_YEARS = [2000, 2004, 2008, 2012, 2016, 2020]
IDEOLOGIES = ["R", "C", "L", "IDK"]
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


def normalize_party_key(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"\s+", " ", text)
    return text


def vereador_party_votes_query() -> str:
    years = ", ".join(str(year) for year in MUNICIPAL_ELECTION_YEARS)
    return f"""
SELECT
  ano AS year,
  sigla_uf AS state,
  id_municipio AS municipality_id,
  COALESCE(NULLIF(UPPER(TRIM(sigla_partido)), ''), '__MISSING_PARTY__') AS party,
  SUM(COALESCE(votos, 0)) AS vereador_votes,
  COUNT(*) AS result_rows
FROM `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`
WHERE ano IN ({years})
  AND turno = 1
  AND LOWER(TRIM(cargo)) = 'vereador'
GROUP BY year, state, municipality_id, party
HAVING vereador_votes > 0
ORDER BY year, state, municipality_id, party
"""


def load_party_ideology() -> pd.DataFrame:
    ideology = pd.read_parquet(PARTY_IDEOLOGY_PATH)
    ideology = ideology[["party_key", "ideology_lcr"]].drop_duplicates()
    if ideology["party_key"].duplicated().any():
        duplicated = ideology.loc[ideology["party_key"].duplicated(), "party_key"].tolist()
        raise ValueError(f"Duplicated party ideology keys: {duplicated[:10]}")
    return ideology


def build_ideology_shares(party_votes: pd.DataFrame, ideology: pd.DataFrame) -> pd.DataFrame:
    votes = party_votes.copy()
    votes["party_key"] = votes["party"].map(normalize_party_key)
    votes["vereador_votes"] = pd.to_numeric(votes["vereador_votes"], errors="coerce").fillna(0)
    votes = votes.merge(ideology, on="party_key", how="left")
    votes["ideology_lcr"] = votes["ideology_lcr"].fillna("IDK")

    grouped = (
        votes.groupby(["year", "state", "municipality_id", "ideology_lcr"], as_index=False)["vereador_votes"]
        .sum()
    )
    totals = (
        grouped.groupby(["year", "state", "municipality_id"], as_index=False)["vereador_votes"]
        .sum()
        .rename(columns={"vereador_votes": "total_vereador_votes"})
    )
    grouped = grouped.merge(totals, on=["year", "state", "municipality_id"], how="left")
    grouped["vote_share"] = grouped["vereador_votes"] / grouped["total_vereador_votes"]

    wide = (
        grouped.pivot_table(
            index=["year", "state", "municipality_id"],
            columns="ideology_lcr",
            values="vote_share",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(columns=None)
    )
    for ideology_code in IDEOLOGIES:
        if ideology_code not in wide.columns:
            wide[ideology_code] = 0.0
    wide = wide.rename(
        columns={
            "R": "pct_vereador_R",
            "C": "pct_vereador_C",
            "L": "pct_vereador_L",
            "IDK": "pct_vereador_IDK",
        }
    )
    out_cols = [
        "year",
        "state",
        "municipality_id",
        "pct_vereador_R",
        "pct_vereador_C",
        "pct_vereador_L",
        "pct_vereador_IDK",
    ]
    out = wide[out_cols].sort_values(["year", "state", "municipality_id"]).reset_index(drop=True)
    for col in ["pct_vereador_R", "pct_vereador_C", "pct_vereador_L", "pct_vereador_IDK"]:
        out[col] = out[col].astype(float)
    return out


def build_diagnostics(out: pd.DataFrame, party_votes: pd.DataFrame) -> pd.DataFrame:
    share_cols = ["pct_vereador_R", "pct_vereador_C", "pct_vereador_L", "pct_vereador_IDK"]
    diagnostics = out.copy()
    diagnostics["share_sum"] = diagnostics[share_cols].sum(axis=1)
    yearly = diagnostics.groupby("year").agg(
        rows=("municipality_id", "size"),
        states=("state", "nunique"),
        municipalities=("municipality_id", "nunique"),
        min_share_sum=("share_sum", "min"),
        max_share_sum=("share_sum", "max"),
    )
    idk_parties = party_votes.copy()
    ideology = load_party_ideology()
    idk_parties["party_key"] = idk_parties["party"].map(normalize_party_key)
    idk_parties = idk_parties.merge(ideology, on="party_key", how="left")
    idk_parties["ideology_lcr"] = idk_parties["ideology_lcr"].fillna("IDK")
    idk_counts = (
        idk_parties.loc[idk_parties["ideology_lcr"] == "IDK"]
        .groupby("year")["party"]
        .nunique()
        .rename("idk_parties")
    )
    result = yearly.join(idk_counts, how="left").fillna({"idk_parties": 0}).reset_index()
    result["idk_parties"] = result["idk_parties"].astype(int)
    return result


def write_notes(out: pd.DataFrame, diagnostics: pd.DataFrame) -> None:
    share_cols = ["pct_vereador_R", "pct_vereador_C", "pct_vereador_L", "pct_vereador_IDK"]
    lines = [
        "# TSE Vereador Ideology Vote Shares",
        "",
        "- Source: Base dos Dados BigQuery table `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`.",
        f"- Years: {', '.join(map(str, MUNICIPAL_ELECTION_YEARS))}.",
        "- Filters: first round only (`turno = 1`) and city-council race only (`cargo = 'Vereador'`).",
        "- Ideology source: `data/clean/party_ideology/party_lcr_crosswalk_2000_2024.parquet`.",
        "- Unit: municipality-election year.",
        "- Denominator: total positive candidate vereador votes in the municipality-year, excluding blank/null and party-list votes.",
        f"- Output: `{OUTPUT_PATH.relative_to(ROOT)}` and `.csv`.",
        f"- Interim party-vote cache: `{PARTY_VOTES_PATH.relative_to(ROOT)}` and `.csv`.",
        "",
        "## Output Columns",
        "",
        ", ".join(["year", "state", "municipality_id", *share_cols]),
        "",
        "## Diagnostics",
        "",
        "```text",
        diagnostics.to_string(index=False),
        "```",
        "",
    ]
    NOTES_PATH.write_text("\n".join(lines), encoding="utf-8")


def update_data_sources() -> None:
    marker = "\n## TSE vereador ideology vote shares\n"
    entry = f"""{marker}
- Source: Base dos Dados BigQuery table `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`.
- Scope: first-round (`turno = 1`) vereador (`cargo = 'Vereador'`) candidate votes in municipal election years 2000, 2004, 2008, 2012, 2016, and 2020.
- Party ideology merge: `data/clean/party_ideology/party_lcr_crosswalk_2000_2024.csv`, using normalized party sigla and assigning unmatched parties to `IDK`.
- Interim output: `data/interim/tse/tse_vereador_party_votes_bdd_2000_2020.csv` and `.parquet`.
- Clean output: `data/clean/tse/tse_vereador_ideology_votes.csv` and `.parquet`.
- Columns: `year`, `state`, `municipality_id`, `pct_vereador_R`, `pct_vereador_C`, `pct_vereador_L`, and `pct_vereador_IDK`.
"""
    current = DATA_SOURCES_PATH.read_text(encoding="utf-8") if DATA_SOURCES_PATH.exists() else "# Data Sources\n"
    if marker in current:
        current = current.split(marker)[0].rstrip() + "\n" + entry
    else:
        current = current.rstrip() + "\n" + entry
    DATA_SOURCES_PATH.write_text(current, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-run the BigQuery query instead of using cached party votes.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()
    query_log: list[QueryRecord] = []
    client = make_client()

    party_votes = query_to_frame(
        client,
        "bdd_tse_vereador_party_votes_2000_2020",
        vereador_party_votes_query(),
        PARTY_VOTES_PATH,
        force=args.force,
        query_log=query_log,
    )
    party_votes.to_csv(PARTY_VOTES_CSV_PATH, index=False)

    ideology = load_party_ideology()
    out = build_ideology_shares(party_votes, ideology)
    diagnostics = build_diagnostics(out, party_votes)

    out.to_parquet(OUTPUT_PATH, index=False)
    out.to_csv(OUTPUT_CSV_PATH, index=False)
    diagnostics.to_csv(DIAGNOSTICS_PATH, index=False)
    pd.DataFrame([record.__dict__ for record in query_log]).to_csv(QUERY_LOG_PATH, index=False)
    write_notes(out, diagnostics)
    update_data_sources()

    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {OUTPUT_CSV_PATH.relative_to(ROOT)}")
    print(f"Wrote {DIAGNOSTICS_PATH.relative_to(ROOT)}")
    print("\nDiagnostics:")
    print(diagnostics.to_string(index=False))


if __name__ == "__main__":
    main()
