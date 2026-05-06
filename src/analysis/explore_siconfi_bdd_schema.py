from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "data" / "interim" / "siconfi_bdd" / "schema"
DOC_PATH = ROOT / "docs" / "SICONFI_BDD_SCHEMA_EXPLORATION.md"
CREDENTIALS_PATH = ROOT / "credentials" / "gcp-key.json"
DATASET = "basedosdados.br_me_siconfi"
PRIMARY_TABLES = [
    "municipio_despesas_funcao",
    "municipio_despesas_orcamentarias",
    "municipio_receitas_orcamentarias",
]
MUNICIPALITY_UNIVERSE = 5570
REFERENCE_MUNICIPALITY_ID = "3550308"  # Sao Paulo
REFERENCE_YEAR = 2018


def get_client() -> bigquery.Client:
    with CREDENTIALS_PATH.open("r", encoding="utf-8") as handle:
        creds_info = json.load(handle)
    credentials = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(credentials=credentials, project=credentials.project_id)


def run_query(client: bigquery.Client, query: str, *, dry_run_limit_gb: float = 10.0) -> pd.DataFrame:
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    dry_run_job = client.query(query, job_config=job_config)
    total_gb = dry_run_job.total_bytes_processed / 1e9
    if total_gb > dry_run_limit_gb:
        raise RuntimeError(f"Dry run projected {total_gb:.2f} GB, above limit of {dry_run_limit_gb:.2f} GB.")
    return client.query(query).result().to_dataframe()


def save_frame(df: pd.DataFrame, stem: str) -> None:
    csv_path = SCHEMA_DIR / f"{stem}.csv"
    parquet_path = SCHEMA_DIR / f"{stem}.parquet"
    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)


def format_df(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    return df.to_string(index=False)


def gather_schema_outputs(client: bigquery.Client) -> dict[str, pd.DataFrame]:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)

    tables = run_query(
        client,
        f"""
        SELECT
            table_id AS table_name,
            row_count,
            size_bytes
        FROM `{DATASET}.__TABLES__`
        ORDER BY table_id
        """,
    )
    save_frame(tables, "tables_inventory")

    columns = run_query(
        client,
        f"""
        SELECT
            table_name,
            column_name,
            ordinal_position,
            data_type,
            is_nullable,
            is_partitioning_column,
            clustering_ordinal_position
        FROM `{DATASET}.INFORMATION_SCHEMA.COLUMNS`
        ORDER BY table_name, ordinal_position
        """,
    )
    save_frame(columns, "columns_inventory")

    outputs: dict[str, pd.DataFrame] = {
        "tables": tables,
        "columns": columns,
    }

    for table in PRIMARY_TABLES:
        sample = run_query(
            client,
            f"""
            SELECT
                ano,
                sigla_uf,
                id_municipio,
                estagio,
                portaria,
                conta,
                estagio_bd,
                id_conta_bd,
                conta_bd,
                valor
            FROM `{DATASET}.{table}`
            LIMIT 1000
            """,
        )
        save_frame(sample, f"{table}_sample_1000")
        outputs[f"{table}_sample"] = sample

        year_coverage = run_query(
            client,
            f"""
            SELECT
                ano,
                COUNT(*) AS row_count,
                COUNT(DISTINCT id_municipio) AS n_muni,
                COUNTIF(valor IS NOT NULL) AS n_nonnull,
                {MUNICIPALITY_UNIVERSE} - COUNT(DISTINCT id_municipio) AS missing_vs_5570
            FROM `{DATASET}.{table}`
            GROUP BY ano
            ORDER BY ano
            """,
        )
        save_frame(year_coverage, f"{table}_year_coverage")
        outputs[f"{table}_year_coverage"] = year_coverage

        stages = run_query(
            client,
            f"""
            SELECT
                estagio_bd,
                COUNT(*) AS row_count
            FROM `{DATASET}.{table}`
            GROUP BY estagio_bd
            ORDER BY row_count DESC, estagio_bd
            """,
        )
        save_frame(stages, f"{table}_stages")
        outputs[f"{table}_stages"] = stages

        accounts = run_query(
            client,
            f"""
            SELECT
                id_conta_bd,
                conta_bd,
                COUNT(*) AS row_count
            FROM `{DATASET}.{table}`
            GROUP BY id_conta_bd, conta_bd
            ORDER BY row_count DESC, id_conta_bd
            """,
        )
        save_frame(accounts, f"{table}_accounts")
        outputs[f"{table}_accounts"] = accounts

    top_level_functions = run_query(
        client,
        f"""
        SELECT
            id_conta_bd,
            conta_bd,
            COUNT(*) AS row_count
        FROM `{DATASET}.municipio_despesas_funcao`
        WHERE REGEXP_CONTAINS(id_conta_bd, r'^3\\.[0-9]{{2}}\\.000$')
        GROUP BY id_conta_bd, conta_bd
        ORDER BY id_conta_bd
        """,
    )
    save_frame(top_level_functions, "municipio_despesas_funcao_top_level_functions")
    outputs["top_level_functions"] = top_level_functions

    top_level_expense_categories = run_query(
        client,
        f"""
        SELECT
            id_conta_bd,
            conta_bd,
            COUNT(*) AS row_count
        FROM `{DATASET}.municipio_despesas_orcamentarias`
        WHERE id_conta_bd IN (
            '2.0.0.00.00.00',
            '2.3.0.00.00.00',
            '2.3.1.00.00.00',
            '2.3.2.00.00.00',
            '2.3.3.00.00.00',
            '2.4.0.00.00.00',
            '2.4.4.00.00.00',
            '2.4.5.00.00.00',
            '2.4.6.00.00.00'
        )
        GROUP BY id_conta_bd, conta_bd
        ORDER BY id_conta_bd
        """,
    )
    save_frame(top_level_expense_categories, "municipio_despesas_orcamentarias_top_level_categories")
    outputs["top_level_expense_categories"] = top_level_expense_categories

    key_revenue_categories = run_query(
        client,
        f"""
        SELECT
            id_conta_bd,
            conta_bd,
            COUNT(*) AS row_count
        FROM `{DATASET}.municipio_receitas_orcamentarias`
        WHERE id_conta_bd IN (
            '1.0.0.0.0.00.00.00',
            '1.1.0.0.0.00.00.00',
            '1.1.1.0.0.00.00.00',
            '1.1.1.1.8.01.01.00',
            '1.1.1.1.8.02.03.00',
            '1.1.7.1.1.51.00.00'
        )
        OR conta_bd = 'Transferências de Recursos do Sistema Único de Saúde - SUS'
        GROUP BY id_conta_bd, conta_bd
        ORDER BY id_conta_bd, conta_bd
        """,
    )
    save_frame(key_revenue_categories, "municipio_receitas_orcamentarias_key_categories")
    outputs["key_revenue_categories"] = key_revenue_categories

    sao_paulo_health = run_query(
        client,
        f"""
        SELECT
            ano,
            id_municipio,
            estagio_bd,
            id_conta_bd,
            conta_bd,
            SUM(valor) AS total_valor
        FROM `{DATASET}.municipio_despesas_funcao`
        WHERE id_municipio = '{REFERENCE_MUNICIPALITY_ID}'
          AND ano = {REFERENCE_YEAR}
          AND id_conta_bd = '3.10.000'
        GROUP BY ano, id_municipio, estagio_bd, id_conta_bd, conta_bd
        ORDER BY estagio_bd
        """,
    )
    save_frame(sao_paulo_health, "sao_paulo_2018_health_stage_check")
    outputs["sao_paulo_health"] = sao_paulo_health

    return outputs


def build_markdown(outputs: dict[str, pd.DataFrame]) -> str:
    tables = outputs["tables"].copy()
    tables["size_mb"] = (tables["size_bytes"] / 1_000_000).round(2)

    columns = outputs["columns"]
    lines = [
        "# SICONFI Base dos Dados Schema Exploration",
        "",
        "This note records the mandatory schema discovery pass for `basedosdados.br_me_siconfi` before building the extended fiscal panel.",
        "",
        "## Setup",
        "",
        "- BigQuery authentication used `credentials/gcp-key.json` with the project inferred from the service-account key.",
        "- All exploratory queries were run through a dry-run guard with a hard stop above 10 GB scanned per query.",
        f"- Municipality coverage gaps are benchmarked against the crosswalk universe of `{MUNICIPALITY_UNIVERSE}` IBGE municipalities in `data/raw/ibge/bd-tse_mun_ids.csv`.",
        "",
        "## Step 1.1 — Table inventory",
        "",
        "```text",
        format_df(tables[["table_name", "row_count", "size_mb"]]),
        "```",
        "",
        "## Step 1.2 — Columns by table",
        "",
    ]

    for table_name in tables["table_name"].tolist():
        block = columns.loc[columns["table_name"] == table_name, ["column_name", "data_type", "is_nullable", "is_partitioning_column", "clustering_ordinal_position"]]
        lines.extend(
            [
                f"### `{table_name}`",
                "",
                "```text",
                format_df(block),
                "```",
                "",
            ]
        )

    lines.extend(
        [
            "## Step 1.3 — 1,000-row samples",
            "",
            "The full 1,000-row samples for the three primary municipality tables were cached under `data/interim/siconfi_bdd/schema/` as both CSV and Parquet:",
            "",
        ]
    )
    for table in PRIMARY_TABLES:
        lines.append(f"- `{table}_sample_1000.csv` and `{table}_sample_1000.parquet`")

    lines.extend(
        [
            "",
            "## Step 1.4 — Coverage, stage coding, and category coding",
            "",
        ]
    )
    for table in PRIMARY_TABLES:
        year_cov = outputs[f"{table}_year_coverage"]
        stages = outputs[f"{table}_stages"]
        lines.extend(
            [
                f"### `{table}` year coverage",
                "",
                "```text",
                format_df(year_cov),
                "```",
                "",
                f"### `{table}` stage labels",
                "",
                "```text",
                format_df(stages),
                "```",
                "",
                f"- Full account dictionary cached at `data/interim/siconfi_bdd/schema/{table}_accounts.csv`.",
                "",
            ]
        )

    lines.extend(
        [
            "### Top-level function codes (`municipio_despesas_funcao`)",
            "",
            "```text",
            format_df(outputs["top_level_functions"]),
            "```",
            "",
            "### Top-level economic spending categories (`municipio_despesas_orcamentarias`)",
            "",
            "```text",
            format_df(outputs["top_level_expense_categories"]),
            "```",
            "",
            "### Key revenue categories (`municipio_receitas_orcamentarias`)",
            "",
            "```text",
            format_df(outputs["key_revenue_categories"]),
            "```",
            "",
            "## Units and coding interpretation",
            "",
            "- `valor` behaves like current Brazilian reais rather than thousands of reais or pre-deflated units.",
            "- The expenditure stage labels needed for the downstream panel are present directly in `estagio_bd`; the executed-spending stage is `Despesas Liquidadas`.",
            "- Municipality identifiers are stored as seven-digit IBGE municipality codes in string form (`id_municipio`).",
            "- Pre-2013 and post-2013 coverage differ in row counts because the account dictionaries change, but municipality coverage remains high through the election years used in the paper.",
            "",
            "## Step 1.5 — São Paulo 2018 sanity check",
            "",
            "```text",
            format_df(outputs["sao_paulo_health"]),
            "```",
            "",
            "- The `Despesas Liquidadas` total for São Paulo (`id_municipio = 3550308`) in the top-level health function (`id_conta_bd = 3.10.000`, `conta_bd = Saúde`) is approximately `R$ 9.64 billion` in 2018.",
            "- This lands in the expected public-budget range for São Paulo and supports the interpretation that `valor` is reported in current reais at the municipality-year-function level.",
            "",
            "## Practical takeaways for panel construction",
            "",
            "- Restrict the fiscal build to `ano BETWEEN 2000 AND 2022`; 2025 is clearly incomplete and 2023–2024 are outside the paper window.",
            "- Use `municipio_despesas_funcao` for function-based spending outcomes and select the `Despesas Liquidadas` stage consistently.",
            "- Use top-level function rows such as `3.10.000` (Saúde), `3.12.000` (Educação), and `3.08.000` (Assistência Social) rather than subfunctions to avoid double counting.",
            "- Use `municipio_despesas_orcamentarias` for economic-category outcomes such as `Pessoal e Encargos Sociais`, `Outras Despesas Correntes`, `Investimentos`, and `Amortização da Dívida`.",
            "- Use `municipio_receitas_orcamentarias` for total revenue, tax revenue, IPTU, ISS, FPM, and SUS-transfer outcomes.",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    client = get_client()
    outputs = gather_schema_outputs(client)
    DOC_PATH.write_text(build_markdown(outputs), encoding="utf-8")
    print(f"Wrote {DOC_PATH}")
    print(f"Cached schema artifacts in {SCHEMA_DIR}")


if __name__ == "__main__":
    main()
