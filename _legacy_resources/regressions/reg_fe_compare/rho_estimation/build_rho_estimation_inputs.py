from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from google.cloud import bigquery
from google.oauth2 import service_account
from scipy import stats


ROOT = Path(__file__).resolve().parents[4]
CREDENTIALS_PATH = ROOT / "credentials" / "gcp-key.json"

OUT_DIR = ROOT / "resources" / "regressions" / "reg_fe_compare" / "rho_estimation"
CONFIG_DIR = OUT_DIR / "configs"
REG_DIR = OUT_DIR / "regressions"
RAW_DIR = ROOT / "data" / "raw" / "tse_2010_president"
CLEAN_TSE_DIR = ROOT / "data" / "clean" / "tse"
INTERIM_DIR = ROOT / "data" / "interim" / "rho_estimation"

COMPLIANCE_PANEL = (
    ROOT
    / "resources"
    / "regressions"
    / "reg_fe_compare"
    / "compliance_descriptives"
    / "panel.parquet"
)
GDP_PATH = ROOT / "data" / "clean" / "ibge" / "municipality_gdp_population_survey_years.parquet"
REGION_PATH = ROOT / "data" / "clean" / "region_mapping" / "state_to_region.csv"

SCHEMA_PATH = OUT_DIR / "bdd_resultados_candidato_municipio_schema.csv"
QUERY_LOG_PATH = OUT_DIR / "bdd_query_log.csv"
RAW_RUNOFF_PATH = RAW_DIR / "resultados_candidato_2010_segundo_turno.csv"
RAW_FIRST_PATH = RAW_DIR / "resultados_candidato_2010_primeiro_turno.csv"
RAW_RUNOFF_CACHE = INTERIM_DIR / "resultados_candidato_2010_segundo_turno.parquet"
RAW_FIRST_CACHE = INTERIM_DIR / "resultados_candidato_2010_primeiro_turno.parquet"

CLEAN_RUNOFF_PATH = CLEAN_TSE_DIR / "president_2010_second_round_municipality.csv"
CLEAN_COMBINED_PATH = CLEAN_TSE_DIR / "president_2010_municipality.csv"

MAX_QUERY_BYTES = 2 * 1_000_000_000
LEFT_COALITION_PARTIES = {"PT", "PSB", "PCDOB", "PC DO B", "PDT", "PSOL", "PV"}


@dataclass
class QueryRecord:
    label: str
    bytes_processed: int
    destination: str
    cached: bool


def ensure_dirs() -> None:
    for path in [OUT_DIR, CONFIG_DIR, REG_DIR, RAW_DIR, CLEAN_TSE_DIR, INTERIM_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def make_client() -> bigquery.Client:
    with CREDENTIALS_PATH.open() as handle:
        info = json.load(handle)
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(credentials=credentials, project=credentials.project_id)


def dry_run(client: bigquery.Client, query: str, label: str) -> int:
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    dry = client.query(query, job_config=job_config)
    processed = int(dry.total_bytes_processed or 0)
    print(f"{label}: dry run would process {processed / 1e9:.3f} GB")
    if processed > MAX_QUERY_BYTES:
        raise RuntimeError(
            f"Query `{label}` would process {processed / 1e9:.2f} GB, above the guardrail."
        )
    return processed


def query_to_frame(
    client: bigquery.Client,
    label: str,
    query: str,
    cache_path: Path,
    csv_path: Path,
    records: list[QueryRecord],
    *,
    force: bool = False,
) -> pd.DataFrame:
    processed = dry_run(client, query, label)
    if cache_path.exists() and csv_path.exists() and not force:
        print(f"{label}: using cached {cache_path.relative_to(ROOT)}")
        records.append(QueryRecord(label, processed, str(cache_path.relative_to(ROOT)), True))
        return pd.read_parquet(cache_path)

    df = client.query(query).result().to_dataframe()
    df.to_parquet(cache_path, index=False)
    df.to_csv(csv_path, index=False)
    records.append(QueryRecord(label, processed, str(csv_path.relative_to(ROOT)), False))
    return df


def schema_query() -> str:
    return """
SELECT column_name, data_type
FROM `basedosdados.br_tse_eleicoes.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'resultados_candidato_municipio'
ORDER BY ordinal_position
"""


def election_query(turn: int) -> str:
    return f"""
SELECT
  ano,
  turno,
  sigla_uf,
  id_municipio,
  cargo,
  numero_partido,
  sigla_partido,
  numero_candidato,
  votos
FROM `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`
WHERE ano = 2010
  AND turno = {turn}
  AND LOWER(TRIM(cargo)) = 'presidente'
  AND id_municipio IS NOT NULL
ORDER BY sigla_uf, id_municipio, numero_candidato
"""


def normalize_party(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().upper().replace("PC DO B", "PCDOB")


def clean_vote_file(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(7)
    df["votos"] = pd.to_numeric(df["votos"], errors="coerce").fillna(0)
    df["party_key"] = df["sigla_partido"].map(normalize_party)
    return df


def build_president_outputs(runoff_raw: pd.DataFrame, first_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    runoff = clean_vote_file(runoff_raw)
    first = clean_vote_file(first_raw)

    runoff_group = (
        runoff.groupby(["id_municipio", "sigla_uf", "party_key"], as_index=False)["votos"]
        .sum()
    )
    runoff_totals = (
        runoff_group.groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "total_valid_votes_2010_runoff"})
    )
    dilma_runoff = (
        runoff_group[runoff_group["party_key"] == "PT"]
        .groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "dilma_votes_2010_runoff"})
    )
    runoff_clean = runoff_totals.merge(dilma_runoff, on=["id_municipio", "sigla_uf"], how="left")
    runoff_clean["dilma_votes_2010_runoff"] = runoff_clean["dilma_votes_2010_runoff"].fillna(0)
    runoff_clean["dilma_share_2010_runoff"] = (
        runoff_clean["dilma_votes_2010_runoff"] / runoff_clean["total_valid_votes_2010_runoff"]
    )

    first_group = (
        first.groupby(["id_municipio", "sigla_uf", "party_key"], as_index=False)["votos"]
        .sum()
    )
    first_totals = (
        first_group.groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "total_valid_votes_2010_first_round"})
    )
    dilma_first = (
        first_group[first_group["party_key"] == "PT"]
        .groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "dilma_votes_2010_first_round"})
    )
    left_first = (
        first_group[first_group["party_key"].isin({p.replace("PC DO B", "PCDOB") for p in LEFT_COALITION_PARTIES})]
        .groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "left_coalition_votes_2010_first_round"})
    )
    first_clean = first_totals.merge(dilma_first, on=["id_municipio", "sigla_uf"], how="left")
    first_clean = first_clean.merge(left_first, on=["id_municipio", "sigla_uf"], how="left")
    first_clean[["dilma_votes_2010_first_round", "left_coalition_votes_2010_first_round"]] = (
        first_clean[["dilma_votes_2010_first_round", "left_coalition_votes_2010_first_round"]].fillna(0)
    )
    first_clean["dilma_share_2010_first_round"] = (
        first_clean["dilma_votes_2010_first_round"] / first_clean["total_valid_votes_2010_first_round"]
    )
    first_clean["left_coalition_share_2010_first_round"] = (
        first_clean["left_coalition_votes_2010_first_round"]
        / first_clean["total_valid_votes_2010_first_round"]
    )

    runoff_out = runoff_clean[
        [
            "id_municipio",
            "dilma_share_2010_runoff",
            "total_valid_votes_2010_runoff",
            "dilma_votes_2010_runoff",
        ]
    ].sort_values("id_municipio")

    combined = runoff_clean.merge(
        first_clean,
        on=["id_municipio", "sigla_uf"],
        how="outer",
        validate="one_to_one",
    )
    combined = combined[
        [
            "id_municipio",
            "sigla_uf",
            "dilma_share_2010_runoff",
            "dilma_share_2010_first_round",
            "left_coalition_share_2010_first_round",
            "total_valid_votes_2010_runoff",
            "total_valid_votes_2010_first_round",
            "dilma_votes_2010_runoff",
            "dilma_votes_2010_first_round",
            "left_coalition_votes_2010_first_round",
        ]
    ].sort_values("id_municipio")
    return runoff_out, combined


def build_rho_dataset(panel: pd.DataFrame, event_time: int, president: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    base = panel[
        (panel["bvr_status"] == "hybrid_bvr")
        & (panel["event_time"] == event_time)
        & panel[["pct_with_bvr", "pct_low_ed_with_bvr", "pct_high_ed_with_bvr"]].notna().all(axis=1)
    ].copy()
    base["municipality_id"] = base["municipality_id"].astype(str).str.zfill(7)
    base["cost_proxy_low_ed"] = 1 - base["pct_low_ed_with_bvr"]
    base["cost_proxy_high_ed"] = 1 - base["pct_high_ed_with_bvr"]
    base["compliance_gap"] = base["pct_high_ed_with_bvr"] - base["pct_low_ed_with_bvr"]

    controls = pd.read_parquet(GDP_PATH)
    controls = controls[controls["year"] == 2010].copy()
    controls["municipality_id"] = controls["municipality_id"].astype(str).str.zfill(7)
    controls = controls[
        ["municipality_id", "total_pop", "gdp_pc", "log_total_pop", "log_gdp_pc"]
    ].rename(
        columns={
            "total_pop": "population_2010",
            "gdp_pc": "gdp_per_capita_2010",
            "log_total_pop": "log_population_2010",
            "log_gdp_pc": "log_gdp_per_capita_2010",
        }
    )
    regions = pd.read_csv(REGION_PATH)
    president = president.copy()
    president["municipality_id"] = president["id_municipio"].astype(str).str.zfill(7)

    merged = base.merge(
        president[
            [
                "municipality_id",
                "dilma_share_2010_runoff",
                "dilma_share_2010_first_round",
                "left_coalition_share_2010_first_round",
                "total_valid_votes_2010_runoff",
                "total_valid_votes_2010_first_round",
            ]
        ],
        on="municipality_id",
        how="left",
        indicator="president_merge",
    )
    merged = merged.merge(controls, on="municipality_id", how="left", indicator="controls_merge")
    merged = merged.merge(regions, on="state", how="left")

    diagnostics = {
        "event_time": event_time,
        "initial_rows": int(len(base)),
        "initial_municipalities": int(base["municipality_id"].nunique()),
        "matched_president_rows": int((merged["president_merge"] == "both").sum()),
        "unmatched_president_rows": int((merged["president_merge"] != "both").sum()),
        "matched_controls_rows": int((merged["controls_merge"] == "both").sum()),
        "unmatched_controls_rows": int((merged["controls_merge"] != "both").sum()),
        "unmatched_president_by_state": merged.loc[
            merged["president_merge"] != "both", "state"
        ].value_counts().to_dict(),
        "unmatched_controls_by_state": merged.loc[
            merged["controls_merge"] != "both", "state"
        ].value_counts().to_dict(),
    }

    required = [
        "municipality_id",
        "year_election",
        "first_regime",
        "bvr_status",
        "event_time",
        "pct_low_ed_with_bvr",
        "pct_high_ed_with_bvr",
        "pct_with_bvr",
        "cost_proxy_low_ed",
        "cost_proxy_high_ed",
        "compliance_gap",
        "dilma_share_2010_runoff",
        "dilma_share_2010_first_round",
        "left_coalition_share_2010_first_round",
        "log_population_2010",
        "log_gdp_per_capita_2010",
        "state",
        "region",
    ]
    complete = merged.dropna(subset=required).copy()
    diagnostics["complete_rows"] = int(len(complete))
    diagnostics["complete_municipalities"] = int(complete["municipality_id"].nunique())
    return complete[required].sort_values(["state", "municipality_id"]).reset_index(drop=True), diagnostics


def correlation_table(datasets: dict[int, pd.DataFrame]) -> pd.DataFrame:
    cost_vars = ["cost_proxy_low_ed", "cost_proxy_high_ed", "compliance_gap"]
    pref_vars = [
        "dilma_share_2010_runoff",
        "dilma_share_2010_first_round",
        "left_coalition_share_2010_first_round",
    ]
    rows = []
    for event_time, df in datasets.items():
        for cost in cost_vars:
            for pref in pref_vars:
                sub = df[[cost, pref]].dropna()
                if len(sub) < 3:
                    corr, pval = np.nan, np.nan
                else:
                    corr, pval = stats.pearsonr(sub[cost], sub[pref])
                rows.append(
                    {
                        "event_time": event_time,
                        "cost_variable": cost,
                        "preference_variable": pref,
                        "correlation": corr,
                        "n_obs": len(sub),
                        "p_value": pval,
                    }
                )
    return pd.DataFrame(rows)


def write_config(
    name: str,
    data_path: Path,
    outcome: str,
    regressor: str,
    fixed_effects: list[str],
    cluster: list[str],
    output_dir: Path,
) -> None:
    config = {
        "data": {"path": str(data_path.relative_to(ROOT))},
        "regression": {
            "outcome": outcome,
            "regressors": [regressor],
            "controls": ["log_population_2010", "log_gdp_per_capita_2010"],
            "fixed_effects": fixed_effects,
            "cluster": cluster,
        },
        "output": {"dir": str(output_dir.relative_to(ROOT))},
    }
    with (CONFIG_DIR / f"{name}.yml").open("w") as f:
        yaml.safe_dump(config, f, sort_keys=False)


def write_all_configs() -> None:
    event0 = OUT_DIR / "rho_dataset_event0.parquet"
    event2 = OUT_DIR / "rho_dataset_event2.parquet"
    active = OUT_DIR / "rho_dataset_event0_active_only.parquet"
    specs = [
        ("rho_L", "cost_proxy_low_ed"),
        ("rho_H", "cost_proxy_high_ed"),
        ("rho_gap", "compliance_gap"),
    ]

    for event, data_path in [(0, event0), (2, event2)]:
        for label, cost in specs:
            name = f"{label}_event{event}"
            write_config(
                name,
                data_path,
                "dilma_share_2010_runoff",
                cost,
                ["state"],
                ["state"],
                REG_DIR / name,
            )

    for outcome_suffix, outcome in [
        ("first_round", "dilma_share_2010_first_round"),
        ("left_coalition", "left_coalition_share_2010_first_round"),
    ]:
        for label, cost in specs:
            name = f"{label}_event0_{outcome_suffix}"
            write_config(name, event0, outcome, cost, ["state"], ["state"], REG_DIR / name)

    for label, cost in specs:
        name = f"{label}_event0_region_fe"
        write_config(name, event0, "dilma_share_2010_runoff", cost, ["region"], ["state"], REG_DIR / name)

    for label, cost in specs:
        name = f"{label}_event0_active_only"
        write_config(name, active, "dilma_share_2010_runoff", cost, ["state"], ["state"], REG_DIR / name)


def main() -> None:
    ensure_dirs()
    client = make_client()
    records: list[QueryRecord] = []

    schema_processed = dry_run(client, schema_query(), "schema_resultados_candidato_municipio")
    schema = client.query(schema_query()).result().to_dataframe()
    schema.to_csv(SCHEMA_PATH, index=False)
    records.append(
        QueryRecord(
            "schema_resultados_candidato_municipio",
            schema_processed,
            str(SCHEMA_PATH.relative_to(ROOT)),
            False,
        )
    )

    runoff_raw = query_to_frame(
        client,
        "president_2010_runoff",
        election_query(2),
        RAW_RUNOFF_CACHE,
        RAW_RUNOFF_PATH,
        records,
    )
    first_raw = query_to_frame(
        client,
        "president_2010_first_round",
        election_query(1),
        RAW_FIRST_CACHE,
        RAW_FIRST_PATH,
        records,
    )
    pd.DataFrame([record.__dict__ for record in records]).to_csv(QUERY_LOG_PATH, index=False)

    runoff_clean, president = build_president_outputs(runoff_raw, first_raw)
    runoff_clean.to_csv(CLEAN_RUNOFF_PATH, index=False)
    president.to_csv(CLEAN_COMBINED_PATH, index=False)

    panel = pd.read_parquet(COMPLIANCE_PANEL)
    event_datasets = {}
    diagnostics = []
    for event_time in [0, 2]:
        rho, diag = build_rho_dataset(panel, event_time, president)
        out_path = OUT_DIR / f"rho_dataset_event{event_time}.parquet"
        rho.to_parquet(out_path, index=False)
        rho.to_csv(out_path.with_suffix(".csv"), index=False)
        event_datasets[event_time] = rho
        diagnostics.append(diag)

    active = event_datasets[0][event_datasets[0]["pct_with_bvr"] >= 0.05].copy()
    active.to_parquet(OUT_DIR / "rho_dataset_event0_active_only.parquet", index=False)
    active.to_csv(OUT_DIR / "rho_dataset_event0_active_only.csv", index=False)

    corr = correlation_table(event_datasets)
    corr.to_csv(OUT_DIR / "raw_correlations.csv", index=False)

    write_all_configs()

    national_runoff_share = (
        president["dilma_share_2010_runoff"] * president["total_valid_votes_2010_runoff"]
    ).sum() / president["total_valid_votes_2010_runoff"].sum()
    unweighted_runoff_share = president["dilma_share_2010_runoff"].mean()
    first_share = president["dilma_share_2010_first_round"].mean()
    left_share = president["left_coalition_share_2010_first_round"].mean()

    summary_lines = [
        "# Rho Estimation Dataset Summary",
        "",
        "## Base dos Dados Pull",
        "",
        "Source table: `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`.",
        "",
        f"- Schema saved to `{SCHEMA_PATH.relative_to(ROOT)}`.",
        f"- Raw runoff rows saved to `{RAW_RUNOFF_PATH.relative_to(ROOT)}`.",
        f"- Raw first-round rows saved to `{RAW_FIRST_PATH.relative_to(ROOT)}`.",
        f"- Clean runoff municipality file saved to `{CLEAN_RUNOFF_PATH.relative_to(ROOT)}`.",
        f"- Clean combined municipality file saved to `{CLEAN_COMBINED_PATH.relative_to(ROOT)}`.",
        f"- BigQuery query log saved to `{QUERY_LOG_PATH.relative_to(ROOT)}`.",
        "",
        "## Presidential Vote Sanity Checks",
        "",
        f"- Clean municipality rows: {len(president):,}.",
        f"- National weighted Dilma runoff share: {national_runoff_share:.4f}.",
        f"- Unweighted municipality mean Dilma runoff share: {unweighted_runoff_share:.4f}.",
        f"- Unweighted municipality mean Dilma first-round share: {first_share:.4f}.",
        f"- Unweighted municipality mean left-coalition first-round share: {left_share:.4f}.",
        "",
        "The weighted runoff share should be close to the official national Dilma second-round share of 56.05%.",
        "",
        "## Hybrid Rho Datasets",
        "",
    ]
    for diag in diagnostics:
        summary_lines.extend(
            [
                f"Event time {diag['event_time']}:",
                "",
                f"- Initial hybrid-status observations: {diag['initial_rows']:,}.",
                f"- Initial hybrid-status municipalities: {diag['initial_municipalities']:,}.",
                f"- Presidential matches: {diag['matched_president_rows']:,}; nonmatches: {diag['unmatched_president_rows']:,}.",
                f"- 2010 control matches: {diag['matched_controls_rows']:,}; nonmatches: {diag['unmatched_controls_rows']:,}.",
                f"- Complete analysis rows: {diag['complete_rows']:,}.",
                f"- Complete analysis municipalities: {diag['complete_municipalities']:,}.",
                f"- Unmatched presidential rows by state: `{diag['unmatched_president_by_state']}`.",
                f"- Unmatched control rows by state: `{diag['unmatched_controls_by_state']}`.",
                "",
            ]
        )
    summary_lines.extend(
        [
            "## Controls",
            "",
            "Controls use 2010 IBGE GDP/population from `data/clean/ibge/municipality_gdp_population_survey_years.parquet`, so no nearest-year fallback was required. Region comes from `data/clean/region_mapping/state_to_region.csv`.",
            "",
            "## Notes",
            "",
            "The broader first-round left-coalition measure is computed from candidate-party rows in the Base dos Dados table. Because the table records the candidate party rather than all coalition parties, coalition parties without a presidential candidate do not contribute separate votes.",
        ]
    )
    (OUT_DIR / "dataset_summary.md").write_text("\n".join(summary_lines))

    print(f"Wrote rho inputs to {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
