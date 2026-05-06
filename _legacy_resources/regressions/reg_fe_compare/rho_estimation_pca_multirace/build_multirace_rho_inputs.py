#!/usr/bin/env python3
"""Build multi-race PCA inputs for rho estimation."""

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

OUT_DIR = ROOT / "resources" / "regressions" / "reg_fe_compare" / "rho_estimation_pca_multirace"
CONFIG_DIR = OUT_DIR / "configs"
REG_DIR = OUT_DIR / "regressions"
INTERIM_DIR = ROOT / "data" / "interim" / "rho_estimation_pca_multirace"
RAW_DEP_FED_DIR = ROOT / "data" / "raw" / "tse_dep_fed"
RAW_DEP_EST_DIR = ROOT / "data" / "raw" / "tse_dep_est"
CLEAN_TSE_DIR = ROOT / "data" / "clean" / "tse"

SOURCE_TABLE = "basedosdados.br_tse_eleicoes.resultados_candidato_municipio"
MAX_QUERY_BYTES = 2 * 1_000_000_000
YEARS = [2006, 2010, 2014]
LEFT_COALITION_PARTIES = {"PT", "PSB", "PCDOB", "PC DO B", "PDT", "PSOL", "PV", "REDE"}

PRESIDENT_PATHS = {
    2006: CLEAN_TSE_DIR / "president_2006_municipality.csv",
    2010: CLEAN_TSE_DIR / "president_2010_municipality.csv",
    2014: CLEAN_TSE_DIR / "president_2014_municipality.csv",
}
DEP_FED_CLEAN = CLEAN_TSE_DIR / "dep_fed_left_coalition_municipality.csv"
DEP_EST_CLEAN = CLEAN_TSE_DIR / "dep_est_left_coalition_municipality.csv"
PREFERENCE_PANEL = CLEAN_TSE_DIR / "preference_panel_3races_2006_2014.csv"
ORIGINAL_RHO_EVENT0 = (
    ROOT
    / "resources"
    / "regressions"
    / "reg_fe_compare"
    / "rho_estimation"
    / "rho_dataset_event0.parquet"
)


@dataclass
class QueryRecord:
    label: str
    bytes_processed: int
    destination: str
    cached: bool


def ensure_dirs() -> None:
    for path in [OUT_DIR, CONFIG_DIR, REG_DIR, INTERIM_DIR, RAW_DEP_FED_DIR, RAW_DEP_EST_DIR, CLEAN_TSE_DIR]:
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
    if cache_path.exists() and csv_path.exists():
        print(f"{label}: using cached {cache_path.relative_to(ROOT)}")
        records.append(QueryRecord(label, processed, str(cache_path.relative_to(ROOT)), True))
        return pd.read_parquet(cache_path)
    if csv_path.exists():
        print(f"{label}: using existing raw CSV {csv_path.relative_to(ROOT)}")
        df = pd.read_csv(csv_path, dtype={"id_municipio": str})
        df.to_parquet(cache_path, index=False)
        records.append(QueryRecord(label, processed, str(csv_path.relative_to(ROOT)), True))
        return df

    df = client.query(query).result().to_dataframe()
    df.to_parquet(cache_path, index=False)
    df.to_csv(csv_path, index=False)
    records.append(QueryRecord(label, processed, str(csv_path.relative_to(ROOT)), False))
    return df


def deputy_query(year: int, cargo: str) -> str:
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
  AND LOWER(TRIM(cargo)) = '{cargo}'
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


def aggregate_deputy(raw: pd.DataFrame, year: int, prefix: str) -> pd.DataFrame:
    df = clean_vote_file(raw)
    left_keys = {normalize_party(p) for p in LEFT_COALITION_PARTIES}
    grouped = (
        df.groupby(["id_municipio", "sigla_uf", "party_key"], as_index=False)["votos"]
        .sum()
    )
    totals = (
        grouped.groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": f"total_valid_votes_{prefix}_{year}"})
    )
    left = (
        grouped[grouped["party_key"].isin(left_keys)]
        .groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": f"left_votes_{prefix}_{year}"})
    )
    out = totals.merge(left, on=["id_municipio", "sigla_uf"], how="left")
    out[f"left_votes_{prefix}_{year}"] = out[f"left_votes_{prefix}_{year}"].fillna(0)
    out[f"left_share_{prefix}_{year}"] = (
        out[f"left_votes_{prefix}_{year}"] / out[f"total_valid_votes_{prefix}_{year}"]
    )
    return out[
        [
            "id_municipio",
            "sigla_uf",
            f"left_share_{prefix}_{year}",
            f"total_valid_votes_{prefix}_{year}",
            f"left_votes_{prefix}_{year}",
        ]
    ].sort_values("id_municipio")


def pull_deputies() -> tuple[pd.DataFrame, pd.DataFrame, list[QueryRecord]]:
    client = make_client()
    records: list[QueryRecord] = []
    office_specs = [
        ("dep_fed", "deputado federal", RAW_DEP_FED_DIR),
        ("dep_est", "deputado estadual", RAW_DEP_EST_DIR),
    ]
    outputs: dict[str, pd.DataFrame] = {}
    for prefix, cargo, raw_dir in office_specs:
        year_frames = []
        for year in YEARS:
            label = f"{prefix}_{year}"
            raw = query_to_frame(
                client,
                label,
                deputy_query(year, cargo),
                INTERIM_DIR / f"resultados_candidato_{prefix}_{year}.parquet",
                raw_dir / f"resultados_candidato_{prefix}_{year}.csv",
                records,
            )
            year_frames.append(aggregate_deputy(raw, year, prefix))
        wide = year_frames[0]
        for frame in year_frames[1:]:
            wide = wide.merge(frame.drop(columns=["sigla_uf"]), on="id_municipio", how="outer")
        wide = wide.sort_values("id_municipio").reset_index(drop=True)
        if prefix == "dep_fed":
            wide.to_csv(DEP_FED_CLEAN, index=False)
        else:
            wide.to_csv(DEP_EST_CLEAN, index=False)
        outputs[prefix] = wide
    return outputs["dep_fed"], outputs["dep_est"], records


def read_president(year: int) -> pd.DataFrame:
    df = pd.read_csv(PRESIDENT_PATHS[year], dtype={"id_municipio": str})
    df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(7)
    return df


def build_preference_panel(dep_fed: pd.DataFrame, dep_est: pd.DataFrame) -> pd.DataFrame:
    p2006 = read_president(2006)[
        ["id_municipio", "sigla_uf", "lula_share_2006_runoff", "total_valid_votes_2006_runoff"]
    ].rename(
        columns={
            "sigla_uf": "sigla_uf_2006",
            "lula_share_2006_runoff": "pt_share_2006_runoff",
            "total_valid_votes_2006_runoff": "total_valid_votes_pres_2006_runoff",
        }
    )
    p2010 = read_president(2010)[
        ["id_municipio", "sigla_uf", "dilma_share_2010_runoff", "total_valid_votes_2010_runoff"]
    ].rename(
        columns={
            "sigla_uf": "sigla_uf_2010",
            "dilma_share_2010_runoff": "pt_share_2010_runoff",
            "total_valid_votes_2010_runoff": "total_valid_votes_pres_2010_runoff",
        }
    )
    p2014 = read_president(2014)[
        ["id_municipio", "sigla_uf", "dilma_share_2014_runoff", "total_valid_votes_2014_runoff"]
    ].rename(
        columns={
            "sigla_uf": "sigla_uf_2014",
            "dilma_share_2014_runoff": "pt_share_2014_runoff",
            "total_valid_votes_2014_runoff": "total_valid_votes_pres_2014_runoff",
        }
    )

    panel = p2006.merge(p2010, on="id_municipio", how="outer")
    panel = panel.merge(p2014, on="id_municipio", how="outer")
    panel = panel.merge(dep_fed.drop(columns=["sigla_uf"], errors="ignore"), on="id_municipio", how="outer")
    panel = panel.merge(dep_est.drop(columns=["sigla_uf"], errors="ignore"), on="id_municipio", how="outer")
    panel["id_municipio"] = panel["id_municipio"].astype(str).str.zfill(7)
    panel = panel.sort_values("id_municipio").reset_index(drop=True)
    panel.to_csv(PREFERENCE_PANEL, index=False)
    return panel


PCA_VARS = [
    "pt_share_2006_runoff",
    "pt_share_2010_runoff",
    "pt_share_2014_runoff",
    "left_share_dep_fed_2006",
    "left_share_dep_fed_2010",
    "left_share_dep_fed_2014",
    "left_share_dep_est_2006",
    "left_share_dep_est_2010",
    "left_share_dep_est_2014",
]


def run_pca(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    complete = panel.dropna(subset=PCA_VARS).copy()
    x = complete[PCA_VARS].astype(float)
    means = x.mean()
    stds = x.std(ddof=0)
    z = (x - means) / stds

    _, s, vt = np.linalg.svd(z.to_numpy(), full_matrices=False)
    loadings = vt[0, :]
    raw_score = z.to_numpy() @ loadings
    simple_mean_z = z.mean(axis=1)
    sign_correction = 1
    if np.corrcoef(raw_score, simple_mean_z)[0, 1] < 0:
        sign_correction = -1
        loadings = -loadings
        raw_score = -raw_score

    eigenvalues = (s**2) / (len(z) - 1)
    variance_share = eigenvalues / eigenvalues.sum()
    pc1_z = (raw_score - raw_score.mean()) / raw_score.std(ddof=0)
    # Rescale to the mean/sd of the standardized 9-variable simple mean,
    # matching the prompt's robustness measure scale.
    pc1_simple_mean_scale = pc1_z * simple_mean_z.std(ddof=0) + simple_mean_z.mean()

    scores = complete[["id_municipio"]].copy()
    scores["pc1_score"] = pc1_simple_mean_scale
    scores["pc1_score_z"] = pc1_z
    scores["pc1_score_raw"] = raw_score
    scores["preference_simple_mean"] = simple_mean_z
    scores["pt_share_mean_runoff"] = complete[
        ["pt_share_2006_runoff", "pt_share_2010_runoff", "pt_share_2014_runoff"]
    ].mean(axis=1)
    scores["left_share_dep_fed_mean"] = complete[
        ["left_share_dep_fed_2006", "left_share_dep_fed_2010", "left_share_dep_fed_2014"]
    ].mean(axis=1)
    scores["left_share_dep_est_mean"] = complete[
        ["left_share_dep_est_2006", "left_share_dep_est_2010", "left_share_dep_est_2014"]
    ].mean(axis=1)

    loadings_df = pd.DataFrame(
        {
            "variable": PCA_VARS,
            "race": ["president"] * 3 + ["dep_fed"] * 3 + ["dep_est"] * 3,
            "year": [2006, 2010, 2014] * 3,
            "pc1_loading": loadings,
            "standardized_mean": [means[col] for col in PCA_VARS],
            "standardized_sd": [stds[col] for col in PCA_VARS],
        }
    )
    variance_df = pd.DataFrame(
        {
            "component": [f"PC{i}" for i in range(1, 10)],
            "eigenvalue": eigenvalues,
            "variance_explained": variance_share,
            "cumulative_variance_explained": np.cumsum(variance_share),
        }
    )
    diagnostics = {
        "n_total_municipalities": int(len(panel)),
        "n_full_coverage": int(len(complete)),
        "n_missing_any_pca_var": int(len(panel) - len(complete)),
        "pc1_variance_explained": float(variance_share[0]),
        "pc1_loadings_same_sign": bool((loadings > 0).all() or (loadings < 0).all()),
        "sign_correction": int(sign_correction),
        "corr_pc1_simple_mean": float(np.corrcoef(pc1_simple_mean_scale, simple_mean_z)[0, 1]),
        "mean_abs_loading_president": float(loadings_df.loc[loadings_df["race"] == "president", "pc1_loading"].abs().mean()),
        "mean_abs_loading_dep_fed": float(loadings_df.loc[loadings_df["race"] == "dep_fed", "pc1_loading"].abs().mean()),
        "mean_abs_loading_dep_est": float(loadings_df.loc[loadings_df["race"] == "dep_est", "pc1_loading"].abs().mean()),
    }
    return scores, loadings_df, variance_df, diagnostics


def write_pca_outputs(
    scores: pd.DataFrame,
    loadings: pd.DataFrame,
    variance: pd.DataFrame,
    diagnostics: dict[str, object],
) -> None:
    loadings.to_csv(OUT_DIR / "pca_loadings.csv", index=False)
    variance.to_csv(OUT_DIR / "pca_variance_explained.csv", index=False)
    scores.to_csv(OUT_DIR / "municipality_pc1_scores.csv", index=False)
    scores[
        [
            "id_municipio",
            "pc1_score",
            "pc1_score_z",
            "preference_simple_mean",
            "pt_share_mean_runoff",
            "left_share_dep_fed_mean",
            "left_share_dep_est_mean",
        ]
    ].to_csv(OUT_DIR / "aggregate_measures.csv", index=False)

    race_loadings = (
        loadings.groupby("race")["pc1_loading"]
        .agg(["mean", "min", "max", lambda s: s.abs().mean()])
        .rename(columns={"<lambda_0>": "mean_abs"})
        .reset_index()
    )
    lines = [
        "# Multi-Race PCA Diagnostics",
        "",
        "The PCA uses standardized 2006, 2010, and 2014 values for PT presidential runoff share, federal deputy left-coalition candidate share, and state deputy left-coalition candidate share. The sign is oriented so that higher PC1 means greater left support.",
        "",
        "## Coverage",
        "",
        f"- Municipalities in the integrated panel: {diagnostics['n_total_municipalities']:,}.",
        f"- Municipalities with complete 9-variable coverage: {diagnostics['n_full_coverage']:,}.",
        f"- Municipalities missing at least one PCA variable: {diagnostics['n_missing_any_pca_var']:,}.",
        "",
        "## Loadings",
        "",
        loadings.to_markdown(index=False),
        "",
        "## Loadings By Race",
        "",
        race_loadings.to_markdown(index=False),
        "",
        "## Variance Explained",
        "",
        variance.to_markdown(index=False),
        "",
        "## Interpretation Checks",
        "",
        f"All PC1 loadings have the same sign: {diagnostics['pc1_loadings_same_sign']}.",
        f"Sign correction applied: {diagnostics['sign_correction']} (`-1` means the raw SVD score was flipped).",
        f"PC1 variance explained: {diagnostics['pc1_variance_explained']:.4f}.",
        f"Correlation between simple-mean-scaled PC1 and standardized simple mean: {diagnostics['corr_pc1_simple_mean']:.4f}.",
        f"Mean absolute loading by race: president = {diagnostics['mean_abs_loading_president']:.4f}, federal deputy = {diagnostics['mean_abs_loading_dep_fed']:.4f}, state deputy = {diagnostics['mean_abs_loading_dep_est']:.4f}.",
        "",
        "The deputy shares are candidate-vote shares from `resultados_candidato_municipio`; party-list votes are not included because the prompt requested this candidate-result table.",
        "",
    ]
    (OUT_DIR / "pca_diagnostics.md").write_text("\n".join(lines))


def build_rho_dataset(scores: pd.DataFrame) -> dict[str, object]:
    rho = pd.read_parquet(ORIGINAL_RHO_EVENT0)
    rho["municipality_id"] = rho["municipality_id"].astype(str).str.zfill(7)
    agg = scores[
        [
            "id_municipio",
            "pc1_score",
            "pc1_score_z",
            "preference_simple_mean",
            "pt_share_mean_runoff",
            "left_share_dep_fed_mean",
            "left_share_dep_est_mean",
        ]
    ].copy()
    agg["municipality_id"] = agg["id_municipio"].astype(str).str.zfill(7)
    merged = rho.merge(agg.drop(columns=["id_municipio"]), on="municipality_id", how="left", indicator="pca_merge")
    required = [
        "pc1_score",
        "pc1_score_z",
        "preference_simple_mean",
        "pt_share_mean_runoff",
        "left_share_dep_fed_mean",
        "left_share_dep_est_mean",
    ]
    complete = merged.dropna(subset=required).copy()
    complete.to_parquet(OUT_DIR / "rho_dataset_event0.parquet", index=False)
    complete.to_csv(OUT_DIR / "rho_dataset_event0.csv", index=False)
    return {
        "original_event0_rows": int(len(rho)),
        "original_event0_municipalities": int(rho["municipality_id"].nunique()),
        "matched_pca_rows": int((merged["pca_merge"] == "both").sum()),
        "unmatched_pca_rows": int((merged["pca_merge"] != "both").sum()),
        "complete_rows": int(len(complete)),
        "complete_municipalities": int(complete["municipality_id"].nunique()),
        "unmatched_by_state": merged.loc[merged["pca_merge"] != "both", "state"].value_counts().to_dict(),
    }


def write_config(name: str, outcome: str, regressor: str) -> None:
    config = {
        "data": {"path": str((OUT_DIR / "rho_dataset_event0.parquet").relative_to(ROOT))},
        "regression": {
            "outcome": outcome,
            "regressors": [regressor],
            "controls": ["log_population_2010", "log_gdp_per_capita_2010"],
            "fixed_effects": ["state"],
            "cluster": ["state"],
        },
        "output": {"dir": str((REG_DIR / name).relative_to(ROOT))},
    }
    with (CONFIG_DIR / f"{name}.yml").open("w") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)


def write_configs() -> None:
    specs = [
        ("rho_L", "cost_proxy_low_ed"),
        ("rho_H", "cost_proxy_high_ed"),
        ("rho_gap", "compliance_gap"),
    ]
    for outcome_suffix, outcome in [
        ("pca", "pc1_score"),
        ("mean", "preference_simple_mean"),
    ]:
        for label, cost in specs:
            write_config(f"{label}_event0_{outcome_suffix}", outcome, cost)


def summarize_election_data(
    dep_fed: pd.DataFrame,
    dep_est: pd.DataFrame,
    panel: pd.DataFrame,
    pca_diag: dict[str, object],
    rho_diag: dict[str, object],
    query_records: list[QueryRecord],
) -> None:
    pd.DataFrame([r.__dict__ for r in query_records]).to_csv(OUT_DIR / "bdd_query_log.csv", index=False)

    rows = []
    for prefix, office, df in [
        ("dep_fed", "deputado federal", dep_fed),
        ("dep_est", "deputado estadual", dep_est),
    ]:
        for year in YEARS:
            share = f"left_share_{prefix}_{year}"
            total = f"total_valid_votes_{prefix}_{year}"
            rows.append(
                {
                    "office": office,
                    "year": year,
                    "municipality_rows": int(df[share].notna().sum()),
                    "unweighted_mean_left_share": df[share].mean(),
                    "weighted_left_share": float((df[share] * df[total]).sum() / df[total].sum()),
                    "min_left_share": df[share].min(),
                    "max_left_share": df[share].max(),
                }
            )
    sanity = pd.DataFrame(rows)
    anomalies = sanity[(sanity["min_left_share"] < -1e-12) | (sanity["max_left_share"] > 1 + 1e-12)]

    missing = {var: int(panel[var].isna().sum()) for var in PCA_VARS}
    lines = [
        "# Multi-Race Election Data Summary",
        "",
        f"Source table: `{SOURCE_TABLE}`. The left coalition is coded as PT, PSB, PCdoB, PDT, PSOL, PV, and REDE. Deputy elections use candidate-result rows from the Base dos Dados candidate-municipality table.",
        "",
        "## Files",
        "",
        "- Federal deputy raw files: `data/raw/tse_dep_fed/resultados_candidato_dep_fed_2006.csv`, `..._2010.csv`, `..._2014.csv`.",
        "- State deputy raw files: `data/raw/tse_dep_est/resultados_candidato_dep_est_2006.csv`, `..._2010.csv`, `..._2014.csv`.",
        "- Federal deputy clean file: `data/clean/tse/dep_fed_left_coalition_municipality.csv`.",
        "- State deputy clean file: `data/clean/tse/dep_est_left_coalition_municipality.csv`.",
        "- Integrated preference panel: `data/clean/tse/preference_panel_3races_2006_2014.csv`.",
        "",
        "## Deputy Vote-Share Sanity Checks",
        "",
        sanity.to_markdown(index=False),
        "",
        f"Share anomalies outside [0, 1]: {len(anomalies)}.",
        "",
        "## Coverage",
        "",
        f"- Integrated panel rows: {len(panel):,}.",
        f"- Missing values by PCA variable: `{missing}`.",
        f"- Municipalities with complete 9-variable coverage: {pca_diag['n_full_coverage']:,}.",
        f"- Event-time-0 rho rows before multirace merge: {rho_diag['original_event0_rows']:,}.",
        f"- Event-time-0 rho rows matched to multirace PC1: {rho_diag['matched_pca_rows']:,}.",
        f"- Event-time-0 rho rows unmatched to multirace PC1: {rho_diag['unmatched_pca_rows']:,}.",
        f"- Unmatched event-time-0 rows by state: `{rho_diag['unmatched_by_state']}`.",
        "",
        "The Federal District lacks `deputado estadual` rows in this office definition; this is expected because it elects district deputies rather than state deputies.",
        "",
    ]
    (OUT_DIR / "election_data_summary.md").write_text("\n".join(lines))


def main() -> None:
    ensure_dirs()
    dep_fed, dep_est, records = pull_deputies()
    panel = build_preference_panel(dep_fed, dep_est)
    scores, loadings, variance, pca_diag = run_pca(panel)
    write_pca_outputs(scores, loadings, variance, pca_diag)
    rho_diag = build_rho_dataset(scores)
    write_configs()
    summarize_election_data(dep_fed, dep_est, panel, pca_diag, rho_diag, records)
    print(f"Wrote multirace rho inputs to {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
