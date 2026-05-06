#!/usr/bin/env python3
"""Build vote-share shift analysis inputs for BVR policy-shift tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from google.cloud import bigquery
from google.oauth2 import service_account


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "data").exists() and (parent / "resources").exists():
            return parent
    raise RuntimeError("Could not find repository root.")


ROOT = find_repo_root()
CREDENTIALS_PATH = ROOT / "credentials" / "gcp-key.json"

OUT_DIR = ROOT / "resources" / "regressions" / "reg_fe_left"
CONFIG_DIR = OUT_DIR / "configs"
REG_DIR = OUT_DIR / "regressions"
REG_DATA_DIR = OUT_DIR / "regression_data"
INTERIM_DIR = ROOT / "data" / "interim" / "reg_fe_left"
RAW_2018_DIR = ROOT / "data" / "raw" / "tse_2018_president"
CLEAN_TSE_DIR = ROOT / "data" / "clean" / "tse"

SOURCE_TABLE = "basedosdados.br_tse_eleicoes.resultados_candidato_municipio"
MAX_QUERY_BYTES = 2 * 1_000_000_000
LEFT_COALITION_PARTIES = {"PT", "PSB", "PCDOB", "PC DO B", "PDT", "PSOL", "PV"}

PRESIDENT_2006 = CLEAN_TSE_DIR / "president_2006_municipality.csv"
PRESIDENT_2010 = CLEAN_TSE_DIR / "president_2010_municipality.csv"
PRESIDENT_2014 = CLEAN_TSE_DIR / "president_2014_municipality.csv"
PRESIDENT_2018 = CLEAN_TSE_DIR / "president_2018_municipality.csv"
PRESIDENT_PANEL_2006_2018 = CLEAN_TSE_DIR / "president_pt_runoff_panel_2006_2018.csv"
TSE_PANEL = CLEAN_TSE_DIR / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"
GDP_PATH = ROOT / "data" / "clean" / "ibge" / "municipality_gdp_population_survey_years.parquet"
REGION_PATH = ROOT / "data" / "clean" / "region_mapping" / "state_to_region.csv"


@dataclass
class QueryRecord:
    label: str
    bytes_processed: int
    destination: str
    cached: bool


def ensure_dirs() -> None:
    for path in [OUT_DIR, CONFIG_DIR, REG_DIR, REG_DATA_DIR, INTERIM_DIR, RAW_2018_DIR, CLEAN_TSE_DIR]:
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
            f"Query `{label}` would process {processed / 1e9:.2f} GB, above guardrail."
        )
    return processed


def query_to_frame(
    client: bigquery.Client,
    label: str,
    query: str,
    cache_path: Path,
    csv_path: Path,
    records: list[QueryRecord],
) -> pd.DataFrame:
    processed = dry_run(client, query, label)
    if csv_path.exists():
        print(f"{label}: using existing raw CSV {csv_path.relative_to(ROOT)}")
        df = pd.read_csv(csv_path, dtype={"id_municipio": str})
        if not cache_path.exists():
            df.to_parquet(cache_path, index=False)
        records.append(QueryRecord(label, processed, str(csv_path.relative_to(ROOT)), True))
        return df
    if cache_path.exists():
        print(f"{label}: using cached {cache_path.relative_to(ROOT)}")
        df = pd.read_parquet(cache_path)
        df.to_csv(csv_path, index=False)
        records.append(QueryRecord(label, processed, str(cache_path.relative_to(ROOT)), True))
        return df

    df = client.query(query).result().to_dataframe()
    df.to_parquet(cache_path, index=False)
    df.to_csv(csv_path, index=False)
    records.append(QueryRecord(label, processed, str(csv_path.relative_to(ROOT)), False))
    return df


def election_query(year: int, turn: int) -> str:
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
FROM `{SOURCE_TABLE}`
WHERE ano = {year}
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


def build_2018_output(runoff_raw: pd.DataFrame, first_raw: pd.DataFrame) -> pd.DataFrame:
    runoff = clean_vote_file(runoff_raw)
    first = clean_vote_file(first_raw)

    runoff_group = (
        runoff.groupby(["id_municipio", "sigla_uf", "party_key"], as_index=False)["votos"]
        .sum()
    )
    runoff_totals = (
        runoff_group.groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "total_valid_votes_2018_runoff"})
    )
    haddad_runoff = (
        runoff_group[runoff_group["party_key"] == "PT"]
        .groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "haddad_votes_2018_runoff"})
    )
    runoff_clean = runoff_totals.merge(haddad_runoff, on=["id_municipio", "sigla_uf"], how="left")
    runoff_clean["haddad_votes_2018_runoff"] = runoff_clean["haddad_votes_2018_runoff"].fillna(0)
    runoff_clean["haddad_share_2018_runoff"] = (
        runoff_clean["haddad_votes_2018_runoff"] / runoff_clean["total_valid_votes_2018_runoff"]
    )

    first_group = (
        first.groupby(["id_municipio", "sigla_uf", "party_key"], as_index=False)["votos"]
        .sum()
    )
    first_totals = (
        first_group.groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "total_valid_votes_2018_first_round"})
    )
    haddad_first = (
        first_group[first_group["party_key"] == "PT"]
        .groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "haddad_votes_2018_first_round"})
    )
    left_keys = {normalize_party(p) for p in LEFT_COALITION_PARTIES}
    left_first = (
        first_group[first_group["party_key"].isin(left_keys)]
        .groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": "left_coalition_votes_2018_first_round"})
    )
    first_clean = first_totals.merge(haddad_first, on=["id_municipio", "sigla_uf"], how="left")
    first_clean = first_clean.merge(left_first, on=["id_municipio", "sigla_uf"], how="left")
    first_clean[["haddad_votes_2018_first_round", "left_coalition_votes_2018_first_round"]] = (
        first_clean[["haddad_votes_2018_first_round", "left_coalition_votes_2018_first_round"]].fillna(0)
    )
    first_clean["haddad_share_2018_first_round"] = (
        first_clean["haddad_votes_2018_first_round"] / first_clean["total_valid_votes_2018_first_round"]
    )
    first_clean["left_coalition_share_2018_first_round"] = (
        first_clean["left_coalition_votes_2018_first_round"]
        / first_clean["total_valid_votes_2018_first_round"]
    )

    combined = runoff_clean.merge(first_clean, on=["id_municipio", "sigla_uf"], how="outer", validate="one_to_one")
    combined = combined[
        [
            "id_municipio",
            "sigla_uf",
            "haddad_share_2018_runoff",
            "haddad_share_2018_first_round",
            "left_coalition_share_2018_first_round",
            "total_valid_votes_2018_runoff",
            "total_valid_votes_2018_first_round",
            "haddad_votes_2018_runoff",
            "haddad_votes_2018_first_round",
            "left_coalition_votes_2018_first_round",
        ]
    ].sort_values("id_municipio")
    combined.to_csv(PRESIDENT_2018, index=False)
    return combined.reset_index(drop=True)


def pull_2018() -> tuple[pd.DataFrame, list[QueryRecord]]:
    records: list[QueryRecord] = []
    if PRESIDENT_2018.exists():
        df = pd.read_csv(PRESIDENT_2018, dtype={"id_municipio": str})
        df["id_municipio"] = df["id_municipio"].str.zfill(7)
        return df, records

    client = make_client()
    runoff_raw = query_to_frame(
        client,
        "president_2018_runoff",
        election_query(2018, 2),
        INTERIM_DIR / "resultados_candidato_2018_segundo_turno.parquet",
        RAW_2018_DIR / "resultados_candidato_2018_segundo_turno.csv",
        records,
    )
    first_raw = query_to_frame(
        client,
        "president_2018_first_round",
        election_query(2018, 1),
        INTERIM_DIR / "resultados_candidato_2018_primeiro_turno.parquet",
        RAW_2018_DIR / "resultados_candidato_2018_primeiro_turno.csv",
        records,
    )
    return build_2018_output(runoff_raw, first_raw), records


def read_president(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"id_municipio": str})
    df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(7)
    return df


def build_vote_panel(p2018: pd.DataFrame) -> pd.DataFrame:
    p2006 = read_president(PRESIDENT_2006)
    p2010 = read_president(PRESIDENT_2010)
    p2014 = read_president(PRESIDENT_2014)

    keep_2006 = p2006[
        [
            "id_municipio",
            "sigla_uf",
            "lula_share_2006_runoff",
            "lula_share_2006_first_round",
            "left_coalition_share_2006_first_round",
            "total_valid_votes_2006_runoff",
            "total_valid_votes_2006_first_round",
        ]
    ].rename(
        columns={
            "sigla_uf": "sigla_uf_2006",
            "lula_share_2006_runoff": "pt_share_2006_runoff",
            "lula_share_2006_first_round": "pt_share_2006_first_round",
        }
    )
    keep_2010 = p2010[
        [
            "id_municipio",
            "sigla_uf",
            "dilma_share_2010_runoff",
            "dilma_share_2010_first_round",
            "left_coalition_share_2010_first_round",
            "total_valid_votes_2010_runoff",
            "total_valid_votes_2010_first_round",
        ]
    ].rename(
        columns={
            "sigla_uf": "sigla_uf_2010",
            "dilma_share_2010_runoff": "pt_share_2010_runoff",
            "dilma_share_2010_first_round": "pt_share_2010_first_round",
        }
    )
    keep_2014 = p2014[
        [
            "id_municipio",
            "sigla_uf",
            "dilma_share_2014_runoff",
            "dilma_share_2014_first_round",
            "left_coalition_share_2014_first_round",
            "total_valid_votes_2014_runoff",
            "total_valid_votes_2014_first_round",
        ]
    ].rename(
        columns={
            "sigla_uf": "sigla_uf_2014",
            "dilma_share_2014_runoff": "pt_share_2014_runoff",
            "dilma_share_2014_first_round": "pt_share_2014_first_round",
        }
    )
    keep_2018 = p2018[
        [
            "id_municipio",
            "sigla_uf",
            "haddad_share_2018_runoff",
            "haddad_share_2018_first_round",
            "left_coalition_share_2018_first_round",
            "total_valid_votes_2018_runoff",
            "total_valid_votes_2018_first_round",
        ]
    ].rename(
        columns={
            "sigla_uf": "sigla_uf_2018",
            "haddad_share_2018_runoff": "pt_share_2018_runoff",
            "haddad_share_2018_first_round": "pt_share_2018_first_round",
        }
    )

    panel = keep_2006.merge(keep_2010, on="id_municipio", how="outer")
    panel = panel.merge(keep_2014, on="id_municipio", how="outer")
    panel = panel.merge(keep_2018, on="id_municipio", how="outer")
    panel["id_municipio"] = panel["id_municipio"].astype(str).str.zfill(7)
    panel.to_csv(PRESIDENT_PANEL_2006_2018, index=False)
    return panel.sort_values("id_municipio").reset_index(drop=True)


def build_pc1_2006_2010(vote_panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    cols = ["pt_share_2006_runoff", "pt_share_2010_runoff"]
    complete = vote_panel.dropna(subset=cols).copy()
    x = complete[cols].astype(float)
    means = x.mean()
    stds = x.std(ddof=0)
    z = (x - means) / stds
    _, s, vt = np.linalg.svd(z.to_numpy(), full_matrices=False)
    loadings = vt[0, :]
    raw_score = z.to_numpy() @ loadings
    sign_correction = 1
    if np.corrcoef(raw_score, x.mean(axis=1))[0, 1] < 0:
        sign_correction = -1
        loadings = -loadings
        raw_score = -raw_score

    eigenvalues = (s**2) / (len(z) - 1)
    variance_share = eigenvalues / eigenvalues.sum()
    score_z = (raw_score - raw_score.mean()) / raw_score.std(ddof=0)
    mean_share = x.mean(axis=1)
    # Vote-share scaled score is included for interpretation; the z-score is
    # used in heterogeneity regressions.
    score_vote_scale = score_z * mean_share.std(ddof=0) + mean_share.mean()

    scores = complete[["id_municipio"]].copy()
    scores["pc1_2006_2010_score"] = score_vote_scale
    scores["pc1_2006_2010_score_z"] = score_z
    scores["pt_share_mean_2006_2010"] = mean_share
    scores.to_csv(OUT_DIR / "pc1_2006_2010.csv", index=False)

    diagnostics = {
        "n_total_municipalities": int(len(vote_panel)),
        "n_complete_2006_2010": int(len(complete)),
        "n_missing_any_2006_2010": int(len(vote_panel) - len(complete)),
        "pc1_variance_explained": float(variance_share[0]),
        "pc1_loading_2006": float(loadings[0]),
        "pc1_loading_2010": float(loadings[1]),
        "pc1_loadings_same_sign": bool((loadings > 0).all() or (loadings < 0).all()),
        "sign_correction": int(sign_correction),
        "corr_pc1_mean": float(np.corrcoef(score_vote_scale, mean_share)[0, 1]),
    }
    return scores, diagnostics


def classify_first_regime(row: pd.Series) -> str:
    strict = row["year_first_strict_bvr"]
    hybrid = row["year_first_hybrid_bvr"]
    strict_finite = pd.notna(strict) and strict != 9999
    hybrid_finite = pd.notna(hybrid) and hybrid != 9999
    if not strict_finite and not hybrid_finite:
        return "never_treated"
    if hybrid_finite and (not strict_finite or hybrid < strict):
        return "hybrid"
    return "strict"


def treatment_cross_section() -> pd.DataFrame:
    panel = pd.read_parquet(TSE_PANEL)
    cols = [
        "municipality_id",
        "state",
        "year_first_any_bvr",
        "year_first_strict_bvr",
        "year_first_hybrid_bvr",
    ]
    cross = (
        panel[cols]
        .drop_duplicates("municipality_id")
        .copy()
    )
    cross["municipality_id"] = cross["municipality_id"].astype(str).str.zfill(7)
    cross["id_municipio"] = cross["municipality_id"]
    cross["first_regime"] = cross.apply(classify_first_regime, axis=1)
    return cross


def controls_cross_section() -> pd.DataFrame:
    controls = pd.read_parquet(GDP_PATH)
    controls = controls[controls["year"] == 2010].copy()
    controls["municipality_id"] = controls["municipality_id"].astype(str).str.zfill(7)
    controls = controls[
        ["municipality_id", "log_total_pop", "log_gdp_pc"]
    ].rename(
        columns={
            "log_total_pop": "log_population_2010",
            "log_gdp_pc": "log_gdp_per_capita_2010",
        }
    )
    regions = pd.read_csv(REGION_PATH)
    return controls, regions


def add_deltas_and_treatment(vote_panel: pd.DataFrame, pc1: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    panel = vote_panel.copy()
    panel["id_municipio"] = panel["id_municipio"].astype(str).str.zfill(7)
    panel["delta_pt_2006_2010"] = panel["pt_share_2010_runoff"] - panel["pt_share_2006_runoff"]
    panel["delta_pt_2010_2014"] = panel["pt_share_2014_runoff"] - panel["pt_share_2010_runoff"]
    panel["delta_pt_2014_2018"] = panel["pt_share_2018_runoff"] - panel["pt_share_2014_runoff"]
    panel["delta_left_2014_2018"] = (
        panel["left_coalition_share_2018_first_round"]
        - panel["left_coalition_share_2014_first_round"]
    )

    treatment = treatment_cross_section()
    controls, regions = controls_cross_section()
    pc1 = pc1.copy()
    pc1["id_municipio"] = pc1["id_municipio"].astype(str).str.zfill(7)

    merged = panel.merge(treatment, on="id_municipio", how="left", indicator="treatment_merge")
    merged = merged.merge(controls, on="municipality_id", how="left", indicator="controls_merge")
    merged = merged.merge(regions, on="state", how="left")
    merged = merged.merge(pc1, on="id_municipio", how="left", indicator="pc1_merge")

    merged["bvr_by_2014"] = (merged["year_first_any_bvr"] <= 2014).astype(int)
    merged["bvr_by_2018"] = (merged["year_first_any_bvr"] <= 2018).astype(int)
    merged["bvr_by_2014_strict"] = (
        (merged["bvr_by_2014"] == 1) & (merged["first_regime"] == "strict")
    ).astype(int)
    merged["bvr_by_2014_hybrid"] = (
        (merged["bvr_by_2014"] == 1) & (merged["first_regime"] == "hybrid")
    ).astype(int)
    merged["bvr_by_2018_strict"] = (
        (merged["bvr_by_2018"] == 1) & (merged["first_regime"] == "strict")
    ).astype(int)
    merged["bvr_by_2018_hybrid"] = (
        (merged["bvr_by_2018"] == 1) & (merged["first_regime"] == "hybrid")
    ).astype(int)
    merged["bvr_by_2018_minus_2014_only"] = (
        (merged["year_first_any_bvr"] > 2014) & (merged["year_first_any_bvr"] <= 2018)
    ).astype(int)
    merged["bvr_by_2014_x_pc1"] = merged["bvr_by_2014"] * merged["pc1_2006_2010_score_z"]
    merged["bvr_by_2018_x_pc1"] = merged["bvr_by_2018"] * merged["pc1_2006_2010_score_z"]

    required = [
        "id_municipio",
        "delta_pt_2006_2010",
        "delta_pt_2010_2014",
        "delta_pt_2014_2018",
        "delta_left_2014_2018",
        "pt_share_2006_runoff",
        "pt_share_2010_runoff",
        "pt_share_2014_runoff",
        "pt_share_2018_runoff",
        "pc1_2006_2010_score",
        "pc1_2006_2010_score_z",
        "pt_share_mean_2006_2010",
        "year_first_any_bvr",
        "first_regime",
        "bvr_by_2014",
        "bvr_by_2018",
        "bvr_by_2014_strict",
        "bvr_by_2014_hybrid",
        "bvr_by_2018_strict",
        "bvr_by_2018_hybrid",
        "bvr_by_2018_minus_2014_only",
        "bvr_by_2014_x_pc1",
        "bvr_by_2018_x_pc1",
        "log_population_2010",
        "log_gdp_per_capita_2010",
        "state",
        "region",
    ]
    complete = merged.dropna(subset=required).copy()
    complete = complete[required].sort_values("id_municipio").reset_index(drop=True)
    complete.to_parquet(OUT_DIR / "analysis_panel.parquet", index=False)
    complete.to_csv(OUT_DIR / "analysis_panel.csv", index=False)

    diagnostics = {
        "vote_panel_rows": int(len(panel)),
        "analysis_panel_rows": int(len(complete)),
        "analysis_panel_municipalities": int(complete["id_municipio"].nunique()),
        "treatment_nonmatches": int((merged["treatment_merge"] != "both").sum()),
        "control_nonmatches": int((merged["controls_merge"] != "both").sum()),
        "pc1_nonmatches": int((merged["pc1_merge"] != "both").sum()),
        "first_regime_counts": complete["first_regime"].value_counts().to_dict(),
        "year_first_any_bvr_counts": complete["year_first_any_bvr"].value_counts().sort_index().to_dict(),
    }
    return complete, diagnostics


def sample_panels(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    test1 = panel[(panel["year_first_any_bvr"] <= 2014) | (panel["first_regime"] == "never_treated")].copy()
    test2 = panel[(panel["year_first_any_bvr"] <= 2018) | (panel["first_regime"] == "never_treated")].copy()
    placebo2 = panel[
        ((panel["year_first_any_bvr"] > 2014) & (panel["year_first_any_bvr"] <= 2018))
        | (panel["first_regime"] == "never_treated")
    ].copy()
    out = {"test1": test1, "test2": test2, "placebo2": placebo2}
    for name, df in out.items():
        df.to_parquet(REG_DATA_DIR / f"{name}.parquet", index=False)
        df.to_csv(REG_DATA_DIR / f"{name}.csv", index=False)
    return out


def write_config(name: str, data_name: str, outcome: str, regressors: list[str]) -> None:
    config = {
        "data": {"path": str((REG_DATA_DIR / f"{data_name}.parquet").relative_to(ROOT))},
        "regression": {
            "outcome": outcome,
            "regressors": regressors,
            "controls": ["log_population_2010", "log_gdp_per_capita_2010"],
            "fixed_effects": ["state"],
            "cluster": ["state"],
        },
        "output": {"dir": str((REG_DIR / name).relative_to(ROOT))},
    }
    with (CONFIG_DIR / f"{name}.yml").open("w") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)


def write_configs() -> None:
    write_config("test1_pooled", "test1", "delta_pt_2010_2014", ["bvr_by_2014"])
    write_config(
        "test1_breakdown",
        "test1",
        "delta_pt_2010_2014",
        ["bvr_by_2014_strict", "bvr_by_2014_hybrid"],
    )
    write_config(
        "test1_heterogeneity",
        "test1",
        "delta_pt_2010_2014",
        ["bvr_by_2014", "bvr_by_2014_x_pc1", "pc1_2006_2010_score_z"],
    )
    write_config("test2_pooled", "test2", "delta_pt_2014_2018", ["bvr_by_2018"])
    write_config(
        "test2_breakdown",
        "test2",
        "delta_pt_2014_2018",
        ["bvr_by_2018_strict", "bvr_by_2018_hybrid"],
    )
    write_config(
        "test2_heterogeneity",
        "test2",
        "delta_pt_2014_2018",
        ["bvr_by_2018", "bvr_by_2018_x_pc1", "pc1_2006_2010_score_z"],
    )
    write_config(
        "test2_pooled_left_coalition",
        "test2",
        "delta_left_2014_2018",
        ["bvr_by_2018"],
    )
    write_config(
        "test2_breakdown_left_coalition",
        "test2",
        "delta_left_2014_2018",
        ["bvr_by_2018_strict", "bvr_by_2018_hybrid"],
    )
    write_config("placebo_2006_2010_test1", "test1", "delta_pt_2006_2010", ["bvr_by_2014"])
    write_config(
        "placebo_2010_2014_test2",
        "placebo2",
        "delta_pt_2010_2014",
        ["bvr_by_2018_minus_2014_only"],
    )


def weighted_share(df: pd.DataFrame, share: str, total: str) -> float:
    return float((df[share] * df[total]).sum() / df[total].sum())


def write_summaries(
    p2018: pd.DataFrame,
    vote_panel: pd.DataFrame,
    pc1_diag: dict[str, object],
    analysis_diag: dict[str, object],
    sample_dfs: dict[str, pd.DataFrame],
    query_records: list[QueryRecord],
) -> None:
    pd.DataFrame([record.__dict__ for record in query_records]).to_csv(
        OUT_DIR / "bdd_query_log.csv", index=False
    )

    election_rows = []
    for year, path, candidate, expected in [
        (2006, PRESIDENT_2006, "lula", 0.6083),
        (2010, PRESIDENT_2010, "dilma", 0.5605),
        (2014, PRESIDENT_2014, "dilma", 0.5164),
        (2018, PRESIDENT_2018, "haddad", 0.4487),
    ]:
        df = read_president(path)
        election_rows.append(
            {
                "year": year,
                "clean_rows": len(df),
                "weighted_runoff_share": weighted_share(
                    df,
                    f"{candidate}_share_{year}_runoff",
                    f"total_valid_votes_{year}_runoff",
                ),
                "unweighted_runoff_mean": df[f"{candidate}_share_{year}_runoff"].mean(),
                "expected_national_runoff_share": expected,
            }
        )
    election_table = pd.DataFrame(election_rows)
    missing = {
        "missing_2006_runoff": int(vote_panel["pt_share_2006_runoff"].isna().sum()),
        "missing_2010_runoff": int(vote_panel["pt_share_2010_runoff"].isna().sum()),
        "missing_2014_runoff": int(vote_panel["pt_share_2014_runoff"].isna().sum()),
        "missing_2018_runoff": int(vote_panel["pt_share_2018_runoff"].isna().sum()),
    }
    lines = [
        "# Election Data Summary",
        "",
        f"Source table: `{SOURCE_TABLE}`. The 2018 file was pulled with the same municipality-candidate query used in the earlier rho-estimation presidential pulls.",
        "",
        "## Files",
        "",
        "- 2018 raw runoff: `data/raw/tse_2018_president/resultados_candidato_2018_segundo_turno.csv`.",
        "- 2018 raw first round: `data/raw/tse_2018_president/resultados_candidato_2018_primeiro_turno.csv`.",
        "- 2018 clean: `data/clean/tse/president_2018_municipality.csv`.",
        "- Integrated wide panel: `data/clean/tse/president_pt_runoff_panel_2006_2018.csv`.",
        "",
        "## Sanity Checks",
        "",
        election_table.to_markdown(index=False),
        "",
        "## Coverage",
        "",
        f"- Wide panel rows: {len(vote_panel):,}.",
        f"- Missing runoff shares by year: `{missing}`.",
        "",
    ]
    (OUT_DIR / "election_data_summary.md").write_text("\n".join(lines))

    pc1_lines = [
        "# PC1 2006-2010 Diagnostics",
        "",
        "This PC1 uses only standardized PT second-round runoff shares from 2006 and 2010 so that the baseline preference measure predates 2014 hybrid exposure.",
        "",
        f"Municipalities with complete 2006 and 2010 coverage: {pc1_diag['n_complete_2006_2010']:,} of {pc1_diag['n_total_municipalities']:,}.",
        f"PC1 variance explained: {pc1_diag['pc1_variance_explained']:.4f}.",
        f"PC1 loadings: 2006 = {pc1_diag['pc1_loading_2006']:.4f}, 2010 = {pc1_diag['pc1_loading_2010']:.4f}.",
        f"All loadings same sign: {pc1_diag['pc1_loadings_same_sign']}.",
        f"Sign correction applied: {pc1_diag['sign_correction']}.",
        f"Correlation with simple 2006-2010 mean: {pc1_diag['corr_pc1_mean']:.4f}.",
        "",
    ]
    (OUT_DIR / "pc1_2006_2010_diagnostics.md").write_text("\n".join(pc1_lines))

    sample_rows = []
    for name, df in sample_dfs.items():
        sample_rows.append(
            {
                "sample": name,
                "rows": len(df),
                "states": df["state"].nunique(),
                "never_treated": int((df["first_regime"] == "never_treated").sum()),
                "strict_first": int((df["first_regime"] == "strict").sum()),
                "hybrid_first": int((df["first_regime"] == "hybrid").sum()),
                "bvr_by_2014": int(df["bvr_by_2014"].sum()),
                "bvr_by_2018": int(df["bvr_by_2018"].sum()),
            }
        )
    sample_table = pd.DataFrame(sample_rows)
    cohort = (
        sample_dfs["test2"]
        .groupby(["year_first_any_bvr", "first_regime"], observed=False)
        .size()
        .reset_index(name="n_municipalities")
        .sort_values(["year_first_any_bvr", "first_regime"])
    )
    panel_lines = [
        "# Analysis Panel Summary",
        "",
        f"The analysis panel has {analysis_diag['analysis_panel_rows']:,} complete municipalities after merging the presidential vote panel, treatment timing, 2010 controls, region, and the 2006-2010 PC1.",
        "",
        "## Merge Diagnostics",
        "",
        f"- Treatment nonmatches: {analysis_diag['treatment_nonmatches']:,}.",
        f"- Control nonmatches: {analysis_diag['control_nonmatches']:,}.",
        f"- PC1 nonmatches: {analysis_diag['pc1_nonmatches']:,}.",
        f"- First-regime counts: `{analysis_diag['first_regime_counts']}`.",
        f"- First-treatment-year counts: `{analysis_diag['year_first_any_bvr_counts']}`.",
        "",
        "## Regression Samples",
        "",
        sample_table.to_markdown(index=False),
        "",
        "## Cohorts In Full Test Sample",
        "",
        cohort.to_markdown(index=False),
        "",
        "The Test 1 sample keeps never-treated municipalities and municipalities first treated by 2014, excluding municipalities first treated in 2016 or 2018. The Test 2 sample includes all complete municipalities because every treated municipality in this panel is treated by 2018 or never treated. The placebo-2 sample keeps never-treated municipalities and municipalities first treated in 2016 or 2018.",
        "",
    ]
    (OUT_DIR / "analysis_panel_summary.md").write_text("\n".join(panel_lines))


def main() -> None:
    ensure_dirs()
    p2018, records = pull_2018()
    vote_panel = build_vote_panel(p2018)
    pc1, pc1_diag = build_pc1_2006_2010(vote_panel)
    analysis_panel, analysis_diag = add_deltas_and_treatment(vote_panel, pc1)
    samples = sample_panels(analysis_panel)
    write_configs()
    write_summaries(p2018, vote_panel, pc1_diag, analysis_diag, samples, records)
    print(f"Wrote vote-shift inputs to {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
