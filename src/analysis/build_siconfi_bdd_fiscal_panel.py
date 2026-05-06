from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from google.cloud import bigquery
from google.oauth2 import service_account

import build_downstream_outcomes_panel as downstream


ROOT = Path(__file__).resolve().parents[2]
INTERIM_DIR = ROOT / "data" / "interim" / "siconfi_bdd"
CLEAN_DIR = ROOT / "data" / "clean" / "downstream"
DOCS_DIR = ROOT / "docs"

CREDENTIALS_PATH = ROOT / "credentials" / "gcp-key.json"
CROSSWALK_PATH = ROOT / "data" / "raw" / "ibge" / "bd-tse_mun_ids.csv"
CURRENT_PANEL_PATH = CLEAN_DIR / "downstream_outcomes_panel.parquet"
BACKUP_PANEL_PATH = CLEAN_DIR / "downstream_outcomes_panel_pre_bdd.parquet"
FISCAL_PANEL_PATH = CLEAN_DIR / "siconfi_bdd_fiscal_panel_2000_2022.parquet"
PANEL_V2_PATH = CLEAN_DIR / "downstream_outcomes_panel_v2.parquet"
NOTES_PATH = DOCS_DIR / "DOWNSTREAM_OUTCOMES_NOTES.md"

DATASET = "basedosdados.br_me_siconfi"
RESULT_YEARS = downstream.RESULT_YEARS
MIN_YEAR = min(RESULT_YEARS)
MAX_YEAR = max(RESULT_YEARS)
FUNCTION_STAGE = "Despesas Empenhadas"
REVENUE_STAGE = "Receitas Brutas Realizadas"
SIDRA_IPCA_URL = f"https://apisidra.ibge.gov.br/values/t/1737/v/2266/n1/1/p/{MIN_YEAR}01-{MAX_YEAR}12?formato=json"

FUNCTION_CODE_MAP = {
    "3.01.000": "legislative_pc",
    "3.02.000": "judiciary_pc",
    "3.03.000": "essential_justice_pc",
    "3.04.000": "administration_pc",
    "3.05.000": "national_defense_pc",
    "3.06.000": "public_security_pc",
    "3.07.000": "foreign_relations_pc",
    "3.08.000": "social_assistance_pc",
    "3.09.000": "social_security_pc",
    "3.10.000": "health_spending_pc",
    "3.11.000": "labor_pc",
    "3.12.000": "education_spending_pc",
    "3.13.000": "culture_pc",
    "3.14.000": "citizenship_rights_pc",
    "3.15.000": "urbanism_pc",
    "3.16.000": "housing_pc",
    "3.17.000": "sanitation_pc",
    "3.18.000": "environmental_management_pc",
    "3.19.000": "science_technology_pc",
    "3.20.000": "agriculture_pc",
    "3.21.000": "agrarian_organization_pc",
    "3.22.000": "industry_pc",
    "3.23.000": "commerce_services_pc",
    "3.24.000": "communications_pc",
    "3.25.000": "energy_pc",
    "3.26.000": "transport_pc",
    "3.27.000": "sport_leisure_pc",
    "3.28.000": "special_charges_pc",
}

ECONOMIC_CODE_MAP = {
    "2.0.0.00.00.00": "total_spending_pc",
    "2.3.1.00.00.00": "personnel_spending_pc",
    "2.3.2.00.00.00": "interest_charges_pc",
    "2.3.3.00.00.00": "other_current_spending_pc",
    "2.4.4.00.00.00": "investment_spending_pc",
    "2.4.5.00.00.00": "financial_inversions_pc",
    "2.4.6.00.00.00": "amortization_pc",
}

REVENUE_CASES = {
    "1.0.0.0.0.00.00.00": "total_revenue_pc",
    "1.1.1.0.0.00.00.00": "total_tax_revenue_pc",
    "1.1.1.1.8.01.01.00": "IPTU_pc",
    "1.1.1.1.8.02.03.00": "ISS_pc",
    "1.1.7.1.1.51.00.00": "FPM_transfers_pc",
}

ALL_FISCAL_RAW_COLUMNS = [
    *FUNCTION_CODE_MAP.values(),
    "total_spending_pc",
    "personnel_spending_pc",
    "investment_spending_pc",
    "other_current_spending_pc",
    "financial_inversions_pc",
    "debt_service_pc",
    "total_discretionary_spending_pc",
    "total_revenue_pc",
    "total_tax_revenue_pc",
    "IPTU_pc",
    "ISS_pc",
    "FPM_transfers_pc",
    "SUS_transfers_pc",
]

ALIAS_MAP = {
    "health_spending_per_capita": "health_spending_pc",
    "education_spending_per_capita": "education_spending_pc",
    "social_assistance_spending_per_capita": "social_assistance_pc",
    "total_discretionary_spending_per_capita": "total_discretionary_spending_pc",
    "IPTU_collection_per_capita": "IPTU_pc",
    "FPM_transfers_per_capita": "FPM_transfers_pc",
}

FUNCTION_LABEL_MAP = {
    "Legislativa": "legislative_pc",
    "Judiciária": "judiciary_pc",
    "Essencial à Justiça": "essential_justice_pc",
    "Administração": "administration_pc",
    "Defesa Nacional": "national_defense_pc",
    "Segurança Pública": "public_security_pc",
    "Relações Exteriores": "foreign_relations_pc",
    "Assistência Social": "social_assistance_pc",
    "Assistência e Previdência": "social_assistance_pc",
    "Previdência Social": "social_security_pc",
    "Saúde": "health_spending_pc",
    "Saúde e Saneamento": "health_spending_pc",
    "Trabalho": "labor_pc",
    "Educação": "education_spending_pc",
    "Educação e Cultura": "education_spending_pc",
    "Cultura": "culture_pc",
    "Direitos da Cidadania": "citizenship_rights_pc",
    "Urbanismo": "urbanism_pc",
    "Habitação": "housing_pc",
    "Saneamento": "sanitation_pc",
    "Gestão Ambiental": "environmental_management_pc",
    "Ciência e Tecnologia": "science_technology_pc",
    "Agricultura": "agriculture_pc",
    "Organização Agrária": "agrarian_organization_pc",
    "Indústria": "industry_pc",
    "Comércio E Serviços": "commerce_services_pc",
    "Comércio e Serviços": "commerce_services_pc",
    "Comunicações": "communications_pc",
    "Energia": "energy_pc",
    "Transporte": "transport_pc",
    "Desporto e Lazer": "sport_leisure_pc",
    "Encargos Especiais": "special_charges_pc",
}


def get_client() -> bigquery.Client:
    with CREDENTIALS_PATH.open("r", encoding="utf-8") as handle:
        creds_info = json.load(handle)
    credentials = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(credentials=credentials, project=credentials.project_id)


def normalize_municipality_id(series: pd.Series) -> pd.Series:
    out = series.astype("string")
    out = out.str.replace(".0", "", regex=False).str.strip()
    out = out.mask(out.isin(["<NA>", "nan", "None", ""]))
    out = out.where(out.isna(), out.str.zfill(7))
    return out


def run_cached_query(client: bigquery.Client, name: str, query: str, *, dry_run_limit_gb: float = 10.0) -> pd.DataFrame:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = INTERIM_DIR / f"{name}.parquet"
    sql_path = INTERIM_DIR / f"{name}.sql"
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    dry_run_job = client.query(query, job_config=job_config)
    total_gb = dry_run_job.total_bytes_processed / 1e9
    if total_gb > dry_run_limit_gb:
        raise RuntimeError(f"Query `{name}` would process {total_gb:.2f} GB, above the {dry_run_limit_gb:.2f} GB limit.")

    df = client.query(query).result().to_dataframe()
    df.to_parquet(cache_path, index=False)
    sql_path.write_text(query, encoding="utf-8")
    return df


def get_ipca_annual_deflator() -> pd.DataFrame:
    cache_path = INTERIM_DIR / "ipca_annual_deflator_2018_base.parquet"
    if cache_path.exists():
        return pd.read_parquet(cache_path)

    response = requests.get(SIDRA_IPCA_URL, timeout=120)
    response.raise_for_status()
    payload = response.json()
    frame = pd.DataFrame(payload[1:])
    frame["month_code"] = pd.to_numeric(frame["D3C"], errors="coerce").astype("Int64")
    frame["year"] = (frame["month_code"] // 100).astype("Int64")
    frame["ipca_index"] = pd.to_numeric(frame["V"], errors="coerce")
    annual = frame.groupby("year", as_index=False)["ipca_index"].mean()
    base_2018 = annual.loc[annual["year"] == 2018, "ipca_index"]
    if base_2018.empty:
        raise ValueError("Could not locate annual IPCA value for 2018.")
    annual["ipca_2018_base_deflator"] = float(base_2018.iloc[0]) / annual["ipca_index"]
    annual.to_parquet(cache_path, index=False)
    return annual


def latest_crosswalk_ids() -> set[str]:
    crosswalk = pd.read_csv(CROSSWALK_PATH, usecols=["year", "municipality_id"])
    latest_year = int(pd.to_numeric(crosswalk["year"], errors="coerce").max())
    latest = crosswalk.loc[crosswalk["year"] == latest_year, "municipality_id"]
    return set(normalize_municipality_id(latest.dropna()).tolist())


def get_panel_skeleton() -> pd.DataFrame:
    panel = pd.read_parquet(CURRENT_PANEL_PATH)
    keep = ["municipality_id", "state", "municipality_name", "year_treated", "year_election", "dist_treatment"]
    out = panel[keep].copy()
    out["municipality_id"] = normalize_municipality_id(out["municipality_id"])
    out = out[out["municipality_id"].notna()].copy()
    return out.drop_duplicates(["municipality_id", "year_election"]).sort_values(["municipality_id", "year_election"])


def with_zero_fill_within_coverage(
    values: pd.DataFrame,
    stage_coverage: pd.DataFrame,
    value_columns: list[str],
    coverage_flag: str,
) -> pd.DataFrame:
    out = stage_coverage.merge(values, on=["year_election", "municipality_id"], how="left")
    out[coverage_flag] = out[coverage_flag].fillna(False)
    for col in value_columns:
        if col in out.columns:
            out.loc[out[coverage_flag] & out[col].isna(), col] = 0.0
    return out


def fetch_function_data(client: bigquery.Client) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    label_list = "', '".join(FUNCTION_LABEL_MAP.keys())
    coverage = run_cached_query(
        client,
        "function_stage_coverage_empenhadas_2000_2022",
        f"""
        SELECT
            ano AS year_election,
            id_municipio AS municipality_id,
            TRUE AS has_function_stage_data
        FROM `{DATASET}.municipio_despesas_funcao`
        WHERE ano BETWEEN {MIN_YEAR} AND {MAX_YEAR}
          AND estagio_bd = '{FUNCTION_STAGE}'
        GROUP BY year_election, municipality_id
        """,
    )
    values = run_cached_query(
        client,
        "function_harmonized_outcomes_empenhadas_2000_2022",
        f"""
        SELECT
            ano AS year_election,
            id_municipio AS municipality_id,
            CASE
                WHEN id_conta_bd = '3.01.000' THEN 'legislative_pc'
                WHEN id_conta_bd = '3.02.000' THEN 'judiciary_pc'
                WHEN id_conta_bd = '3.03.000' THEN 'essential_justice_pc'
                WHEN id_conta_bd = '3.04.000' THEN 'administration_pc'
                WHEN id_conta_bd = '3.05.000' THEN 'national_defense_pc'
                WHEN id_conta_bd = '3.06.000' THEN 'public_security_pc'
                WHEN id_conta_bd = '3.07.000' THEN 'foreign_relations_pc'
                WHEN id_conta_bd = '3.08.000' THEN 'social_assistance_pc'
                WHEN id_conta_bd = '3.09.000' THEN 'social_security_pc'
                WHEN id_conta_bd = '3.10.000' THEN 'health_spending_pc'
                WHEN id_conta_bd = '3.11.000' THEN 'labor_pc'
                WHEN id_conta_bd = '3.12.000' THEN 'education_spending_pc'
                WHEN id_conta_bd = '3.13.000' THEN 'culture_pc'
                WHEN id_conta_bd = '3.14.000' THEN 'citizenship_rights_pc'
                WHEN id_conta_bd = '3.15.000' THEN 'urbanism_pc'
                WHEN id_conta_bd = '3.16.000' THEN 'housing_pc'
                WHEN id_conta_bd = '3.17.000' THEN 'sanitation_pc'
                WHEN id_conta_bd = '3.18.000' THEN 'environmental_management_pc'
                WHEN id_conta_bd = '3.19.000' THEN 'science_technology_pc'
                WHEN id_conta_bd = '3.20.000' THEN 'agriculture_pc'
                WHEN id_conta_bd = '3.21.000' THEN 'agrarian_organization_pc'
                WHEN id_conta_bd = '3.22.000' THEN 'industry_pc'
                WHEN id_conta_bd = '3.23.000' THEN 'commerce_services_pc'
                WHEN id_conta_bd = '3.24.000' THEN 'communications_pc'
                WHEN id_conta_bd = '3.25.000' THEN 'energy_pc'
                WHEN id_conta_bd = '3.26.000' THEN 'transport_pc'
                WHEN id_conta_bd = '3.27.000' THEN 'sport_leisure_pc'
                WHEN id_conta_bd = '3.28.000' THEN 'special_charges_pc'
                WHEN conta_bd = 'Legislativa' THEN 'legislative_pc'
                WHEN conta_bd = 'Judiciária' THEN 'judiciary_pc'
                WHEN conta_bd = 'Essencial à Justiça' THEN 'essential_justice_pc'
                WHEN conta_bd = 'Administração' THEN 'administration_pc'
                WHEN conta_bd = 'Defesa Nacional' THEN 'national_defense_pc'
                WHEN conta_bd = 'Segurança Pública' THEN 'public_security_pc'
                WHEN conta_bd = 'Relações Exteriores' THEN 'foreign_relations_pc'
                WHEN conta_bd = 'Assistência Social' THEN 'social_assistance_pc'
                WHEN conta_bd = 'Assistência e Previdência' THEN 'social_assistance_pc'
                WHEN conta_bd = 'Previdência Social' THEN 'social_security_pc'
                WHEN conta_bd = 'Saúde' THEN 'health_spending_pc'
                WHEN conta_bd = 'Saúde e Saneamento' THEN 'health_spending_pc'
                WHEN conta_bd = 'Trabalho' THEN 'labor_pc'
                WHEN conta_bd = 'Educação' THEN 'education_spending_pc'
                WHEN conta_bd = 'Educação e Cultura' THEN 'education_spending_pc'
                WHEN conta_bd = 'Cultura' THEN 'culture_pc'
                WHEN conta_bd = 'Direitos da Cidadania' THEN 'citizenship_rights_pc'
                WHEN conta_bd = 'Urbanismo' THEN 'urbanism_pc'
                WHEN conta_bd = 'Habitação' THEN 'housing_pc'
                WHEN conta_bd = 'Saneamento' THEN 'sanitation_pc'
                WHEN conta_bd = 'Gestão Ambiental' THEN 'environmental_management_pc'
                WHEN conta_bd = 'Ciência e Tecnologia' THEN 'science_technology_pc'
                WHEN conta_bd = 'Agricultura' THEN 'agriculture_pc'
                WHEN conta_bd = 'Organização Agrária' THEN 'agrarian_organization_pc'
                WHEN conta_bd = 'Indústria' THEN 'industry_pc'
                WHEN conta_bd = 'Comércio E Serviços' THEN 'commerce_services_pc'
                WHEN conta_bd = 'Comércio e Serviços' THEN 'commerce_services_pc'
                WHEN conta_bd = 'Comunicações' THEN 'communications_pc'
                WHEN conta_bd = 'Energia' THEN 'energy_pc'
                WHEN conta_bd = 'Transporte' THEN 'transport_pc'
                WHEN conta_bd = 'Desporto e Lazer' THEN 'sport_leisure_pc'
                WHEN conta_bd = 'Encargos Especiais' THEN 'special_charges_pc'
            END AS outcome_key,
            SUM(valor) AS nominal_value
        FROM `{DATASET}.municipio_despesas_funcao`
        WHERE ano BETWEEN {MIN_YEAR} AND {MAX_YEAR}
          AND estagio_bd = '{FUNCTION_STAGE}'
          AND (
              REGEXP_CONTAINS(id_conta_bd, r'^3\\.[0-9]{{2}}\\.000$')
              OR conta_bd IN ('{label_list}')
          )
        GROUP BY year_election, municipality_id, outcome_key
        """,
    )
    values["municipality_id"] = normalize_municipality_id(values["municipality_id"])
    coverage["municipality_id"] = normalize_municipality_id(coverage["municipality_id"])

    values = values[values["outcome_key"].notna()].copy()
    wide = values.pivot_table(index=["year_election", "municipality_id"], columns="outcome_key", values="nominal_value", aggfunc="sum")
    wide = wide.rename(columns={col: f"{col}_nominal" for col in wide.columns}).reset_index()
    target_cols = [f"{col}_nominal" for col in FUNCTION_CODE_MAP.values()]
    wide = with_zero_fill_within_coverage(wide, coverage, target_cols, "has_function_stage_data")
    support = (
        values.groupby(["outcome_key", "year_election"])["municipality_id"]
        .nunique()
        .reset_index(name="n_muni_supported")
    )
    return wide, coverage, support


def fetch_economic_data(client: bigquery.Client) -> tuple[pd.DataFrame, pd.DataFrame]:
    code_list = "', '".join(ECONOMIC_CODE_MAP.keys())
    coverage = run_cached_query(
        client,
        "economic_stage_coverage_empenhadas_2000_2022",
        f"""
        SELECT
            ano AS year_election,
            id_municipio AS municipality_id,
            TRUE AS has_economic_stage_data
        FROM `{DATASET}.municipio_despesas_orcamentarias`
        WHERE ano BETWEEN {MIN_YEAR} AND {MAX_YEAR}
          AND estagio_bd = '{FUNCTION_STAGE}'
        GROUP BY year_election, municipality_id
        """,
    )
    values = run_cached_query(
        client,
        "economic_categories_empenhadas_full_2000_2022",
        f"""
        SELECT
            ano AS year_election,
            id_municipio AS municipality_id,
            id_conta_bd,
            SUM(valor) AS nominal_value
        FROM `{DATASET}.municipio_despesas_orcamentarias`
        WHERE ano BETWEEN {MIN_YEAR} AND {MAX_YEAR}
          AND estagio_bd = '{FUNCTION_STAGE}'
          AND id_conta_bd IN ('{code_list}')
        GROUP BY year_election, municipality_id, id_conta_bd
        """,
    )
    values["municipality_id"] = normalize_municipality_id(values["municipality_id"])
    coverage["municipality_id"] = normalize_municipality_id(coverage["municipality_id"])

    wide = values.pivot_table(index=["year_election", "municipality_id"], columns="id_conta_bd", values="nominal_value", aggfunc="sum")
    nominal_map = {code: f"{name}_nominal" for code, name in ECONOMIC_CODE_MAP.items()}
    wide = wide.rename(columns=nominal_map).reset_index()
    wide = with_zero_fill_within_coverage(wide, coverage, list(nominal_map.values()), "has_economic_stage_data")
    wide["debt_service_pc_nominal"] = wide[["interest_charges_pc_nominal", "amortization_pc_nominal"]].sum(axis=1, min_count=1)
    wide["total_discretionary_spending_pc_nominal"] = wide[
        ["other_current_spending_pc_nominal", "investment_spending_pc_nominal", "financial_inversions_pc_nominal"]
    ].sum(axis=1, min_count=1)
    return wide, coverage


def fetch_revenue_data(client: bigquery.Client) -> tuple[pd.DataFrame, pd.DataFrame]:
    coded = "', '".join(REVENUE_CASES.keys())
    coverage = run_cached_query(
        client,
        "revenue_stage_coverage_2000_2022",
        f"""
        SELECT
            ano AS year_election,
            id_municipio AS municipality_id,
            TRUE AS has_revenue_stage_data
        FROM `{DATASET}.municipio_receitas_orcamentarias`
        WHERE ano BETWEEN {MIN_YEAR} AND {MAX_YEAR}
          AND estagio_bd = '{REVENUE_STAGE}'
        GROUP BY year_election, municipality_id
        """,
    )
    values = run_cached_query(
        client,
        "revenue_categories_realizadas_2000_2022",
        f"""
        SELECT
            ano AS year_election,
            id_municipio AS municipality_id,
            CASE
                WHEN id_conta_bd = '1.0.0.0.0.00.00.00' THEN 'total_revenue_pc'
                WHEN id_conta_bd = '1.1.1.0.0.00.00.00' THEN 'total_tax_revenue_pc'
                WHEN id_conta_bd = '1.1.1.1.8.01.01.00' THEN 'IPTU_pc'
                WHEN id_conta_bd = '1.1.1.1.8.02.03.00' THEN 'ISS_pc'
                WHEN id_conta_bd = '1.1.7.1.1.51.00.00' THEN 'FPM_transfers_pc'
                WHEN conta_bd LIKE '%Sistema Único de Saúde - SUS%' THEN 'SUS_transfers_pc'
            END AS revenue_key,
            SUM(valor) AS nominal_value
        FROM `{DATASET}.municipio_receitas_orcamentarias`
        WHERE ano BETWEEN {MIN_YEAR} AND {MAX_YEAR}
          AND estagio_bd = '{REVENUE_STAGE}'
          AND (
                id_conta_bd IN ('{coded}')
                OR conta_bd LIKE '%Sistema Único de Saúde - SUS%'
          )
        GROUP BY year_election, municipality_id, revenue_key
        """,
    )
    values["municipality_id"] = normalize_municipality_id(values["municipality_id"])
    coverage["municipality_id"] = normalize_municipality_id(coverage["municipality_id"])

    wide = values.pivot_table(index=["year_election", "municipality_id"], columns="revenue_key", values="nominal_value", aggfunc="sum")
    wide = wide.rename(columns={col: f"{col}_nominal" for col in wide.columns}).reset_index()
    value_cols = [
        "total_revenue_pc_nominal",
        "total_tax_revenue_pc_nominal",
        "IPTU_pc_nominal",
        "ISS_pc_nominal",
        "FPM_transfers_pc_nominal",
        "SUS_transfers_pc_nominal",
    ]
    wide = with_zero_fill_within_coverage(wide, coverage, value_cols, "has_revenue_stage_data")
    return wide, coverage


def apply_deflator_and_population(panel: pd.DataFrame, value_columns: list[str]) -> pd.DataFrame:
    out = panel.copy()
    deflator = get_ipca_annual_deflator()[["year", "ipca_2018_base_deflator"]].rename(columns={"year": "year_election"})
    population = downstream.get_population_panel().rename(columns={"year": "year_election"})
    population["municipality_id"] = normalize_municipality_id(population["municipality_id"])

    out = out.merge(deflator, on="year_election", how="left")
    out = out.merge(population, on=["year_election", "municipality_id"], how="left")

    for col in value_columns:
        nominal_col = f"{col}_nominal"
        if nominal_col not in out.columns:
            continue
        out[col] = (pd.to_numeric(out[nominal_col], errors="coerce") * out["ipca_2018_base_deflator"]) / pd.to_numeric(
            out["population_estimate"], errors="coerce"
        )

    return out


def winsorize_series(series: pd.Series) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce")
    if series.dropna().empty:
        return series
    lower = series.quantile(0.01)
    upper = series.quantile(0.99)
    return series.clip(lower=lower, upper=upper)


def build_fiscal_panel() -> pd.DataFrame:
    skeleton = get_panel_skeleton()
    client = get_client()

    function_panel, function_coverage, function_support = fetch_function_data(client)
    economic_panel, economic_coverage = fetch_economic_data(client)
    revenue_panel, revenue_coverage = fetch_revenue_data(client)

    merged = skeleton.merge(function_panel, on=["year_election", "municipality_id"], how="left")
    merged = merged.merge(
        economic_panel.drop(columns=["has_economic_stage_data"], errors="ignore"),
        on=["year_election", "municipality_id"],
        how="left",
    )
    merged = merged.merge(
        revenue_panel.drop(columns=["has_revenue_stage_data"], errors="ignore"),
        on=["year_election", "municipality_id"],
        how="left",
    )

    # Bring coverage flags back in after the wide merges.
    for coverage, flag in [
        (function_coverage, "has_function_stage_data"),
        (economic_coverage, "has_economic_stage_data"),
        (revenue_coverage, "has_revenue_stage_data"),
    ]:
        if flag not in merged.columns:
            coverage = coverage.copy()
            coverage["municipality_id"] = normalize_municipality_id(coverage["municipality_id"])
            merged = merged.merge(coverage, on=["year_election", "municipality_id"], how="left")
        merged[flag] = merged[flag].fillna(False)

    merged = apply_deflator_and_population(
        merged,
        [
            *FUNCTION_CODE_MAP.values(),
            *ECONOMIC_CODE_MAP.values(),
            "debt_service_pc",
            "total_discretionary_spending_pc",
            "total_revenue_pc",
            "total_tax_revenue_pc",
            "IPTU_pc",
            "ISS_pc",
            "FPM_transfers_pc",
            "SUS_transfers_pc",
        ],
    )

    raw_cols = [col for col in ALL_FISCAL_RAW_COLUMNS if col in merged.columns]

    # Keep outcomes missing in years where the historical coding scheme did not identify the category at all.
    supported_by_year = {
        outcome: set(group["year_election"].tolist())
        for outcome, group in function_support.groupby("outcome_key")
    }
    for col in FUNCTION_CODE_MAP.values():
        supported_years = supported_by_year.get(col, set())
        if not supported_years:
            continue
        unsupported_mask = ~merged["year_election"].isin(sorted(supported_years))
        merged.loc[unsupported_mask, col] = np.nan

    for col in raw_cols:
        merged[col] = winsorize_series(merged[col])
        merged[f"log_{col}"] = np.log1p(merged[col])

    for alias, canonical in ALIAS_MAP.items():
        if canonical in merged.columns:
            merged[alias] = merged[canonical]
            merged[f"log_{alias}"] = merged[f"log_{canonical}"]

    expected_ids = latest_crosswalk_ids()
    observed_ids = set(normalize_municipality_id(pd.Series(merged["municipality_id"]).dropna()).unique().tolist())
    unmatched = sorted(observed_ids - expected_ids)
    unmatched_df = pd.DataFrame({"municipality_id": unmatched})
    unmatched_df.to_csv(INTERIM_DIR / "unmatched_municipality_ids.csv", index=False)

    coverage_summary = []
    for col in raw_cols:
        for year in RESULT_YEARS:
            subset = merged.loc[merged["year_election"] == year]
            coverage_summary.append(
                {
                    "outcome": col,
                    "year_election": year,
                    "n_muni_nonmissing": int(subset[col].notna().sum()),
                }
            )
    pd.DataFrame(coverage_summary).to_csv(INTERIM_DIR / "outcome_coverage_summary.csv", index=False)

    compare_to_finbra(merged)

    keep_cols = [
        "municipality_id",
        "state",
        "municipality_name",
        "year_election",
        "year_treated",
        "dist_treatment",
        "population_estimate",
        "ipca_2018_base_deflator",
        "has_function_stage_data",
        "has_economic_stage_data",
        "has_revenue_stage_data",
        *raw_cols,
        *[f"log_{col}" for col in raw_cols],
        *ALIAS_MAP.keys(),
        *[f"log_{alias}" for alias in ALIAS_MAP],
    ]
    keep_cols = [col for col in keep_cols if col in merged.columns]
    out = merged[keep_cols].sort_values(["municipality_id", "year_election"]).reset_index(drop=True)
    out.to_parquet(FISCAL_PANEL_PATH, index=False)
    return out


def compare_to_finbra(new_fiscal: pd.DataFrame) -> None:
    existing = pd.read_parquet(CURRENT_PANEL_PATH)
    existing["municipality_id"] = normalize_municipality_id(existing["municipality_id"])
    existing = existing[existing["municipality_id"].notna()].copy()
    compare_years = [2010, 2012]
    correlations: list[dict[str, object]] = []
    pairs = {
        "health_spending_per_capita": "health_spending_pc",
        "education_spending_per_capita": "education_spending_pc",
        "social_assistance_spending_per_capita": "social_assistance_pc",
        "IPTU_collection_per_capita": "IPTU_pc",
        "FPM_transfers_per_capita": "FPM_transfers_pc",
    }
    if "total_discretionary_spending_per_capita" in existing.columns and "total_discretionary_spending_pc" in new_fiscal.columns:
        pairs["total_discretionary_spending_per_capita"] = "total_discretionary_spending_pc"

    for year in compare_years:
        old_year = existing.loc[existing["year_election"] == year, ["municipality_id", *pairs.keys()]].copy()
        new_year = new_fiscal.loc[new_fiscal["year_election"] == year, ["municipality_id", *pairs.values()]].copy()
        merged = old_year.merge(new_year, on="municipality_id", how="inner")
        for old_col, new_col in pairs.items():
            subset = merged[[old_col, new_col]].dropna()
            corr = subset[old_col].corr(subset[new_col]) if len(subset) >= 2 else np.nan
            correlations.append(
                {
                    "year_election": year,
                    "old_column": old_col,
                    "new_column": new_col,
                    "n_overlap": int(len(subset)),
                    "correlation": corr,
                }
            )
    pd.DataFrame(correlations).to_csv(INTERIM_DIR / "finbra_bdd_overlap_correlations.csv", index=False)


def build_merged_panel(fiscal_panel: pd.DataFrame) -> pd.DataFrame:
    current = pd.read_parquet(CURRENT_PANEL_PATH)
    current["municipality_id"] = normalize_municipality_id(current["municipality_id"])
    current = current[current["municipality_id"].notna()].copy()

    if CURRENT_PANEL_PATH.exists():
        shutil.copy2(CURRENT_PANEL_PATH, BACKUP_PANEL_PATH)

    fiscal_cols_to_drop = [
        col
        for col in current.columns
        if col in ALIAS_MAP
        or col.startswith("log_")
        and col.replace("log_", "", 1) in ALIAS_MAP
    ]
    merged = current.drop(columns=fiscal_cols_to_drop, errors="ignore").merge(
        fiscal_panel.drop(
            columns=["state", "municipality_name", "year_treated", "dist_treatment", "population_estimate"],
            errors="ignore",
        ),
        on=["municipality_id", "year_election"],
        how="left",
    )
    merged.to_parquet(PANEL_V2_PATH, index=False)
    return merged


def update_notes(fiscal_panel: pd.DataFrame) -> None:
    overlap = pd.read_csv(INTERIM_DIR / "finbra_bdd_overlap_correlations.csv")
    coverage = pd.read_csv(INTERIM_DIR / "outcome_coverage_summary.csv")
    election_coverage = (
        coverage.groupby("outcome", as_index=False)["n_muni_nonmissing"]
        .min()
        .rename(columns={"n_muni_nonmissing": "min_n_muni_nonmissing"})
        .sort_values("outcome")
    )
    unmatched = pd.read_csv(INTERIM_DIR / "unmatched_municipality_ids.csv")

    note = f"""

## SICONFI Base dos Dados Fiscal Extension

- Built with `src/analysis/build_siconfi_bdd_fiscal_panel.py` using Base dos Dados BigQuery tables in `basedosdados.br_me_siconfi`.
- Clean fiscal output: `data/clean/downstream/siconfi_bdd_fiscal_panel_2000_2022.parquet`.
- Merged panel output: `data/clean/downstream/downstream_outcomes_panel_v2.parquet`.
- Backup of the pre-extension panel: `data/clean/downstream/downstream_outcomes_panel_pre_bdd.parquet`.
- Query caches live under `data/interim/siconfi_bdd/`.
- Spending tables use `{FUNCTION_STAGE}`; revenue tables use `Receitas Brutas Realizadas`.
- All monetary values are deflated to 2018 reais with annual-average national IPCA from IBGE SIDRA table 1737, then normalized by the project population panel from `build_downstream_outcomes_panel.py`.
- Within municipality-years that are present in the relevant SICONFI stage, missing category rows are treated as zeros; municipality-years absent from the stage remain missing and are flagged by `has_function_stage_data`, `has_economic_stage_data`, and `has_revenue_stage_data`.
- Unmatched municipality IDs relative to the IBGE-TSE crosswalk: `{len(unmatched)}`.
- The prompt preferred `Despesas Liquidadas`, but the Base dos Dados historical archive does not provide that stage consistently before 2009 in `municipio_despesas_orcamentarias` or before 2013 in `municipio_despesas_funcao`. The full-horizon panel therefore uses the only comparable spending stage available across 2000-2022: `Despesas Empenhadas`.

### Coverage summary

```text
{election_coverage.to_string(index=False)}
```

### FINBRA vs. Base dos Dados overlap check (2010 and 2012)

```text
{overlap.to_string(index=False)}
```
"""
    existing = NOTES_PATH.read_text(encoding="utf-8") if NOTES_PATH.exists() else "# Downstream Outcomes Notes\n"
    marker = "\n## SICONFI Base dos Dados Fiscal Extension\n"
    if marker in existing:
        existing = existing.split(marker)[0].rstrip() + "\n"
    NOTES_PATH.write_text(existing.rstrip() + note, encoding="utf-8")


def main() -> None:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    fiscal_panel = build_fiscal_panel()
    build_merged_panel(fiscal_panel)
    update_notes(fiscal_panel)
    print(f"Wrote {FISCAL_PANEL_PATH}")
    print(f"Wrote {PANEL_V2_PATH}")
    print(f"Updated {NOTES_PATH}")


if __name__ == "__main__":
    main()
