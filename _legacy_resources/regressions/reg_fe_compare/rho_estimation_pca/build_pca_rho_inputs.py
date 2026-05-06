#!/usr/bin/env python3
"""Build multi-year PCA inputs for rho estimation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from google.cloud import bigquery
from google.oauth2 import service_account


ROOT = Path(__file__).resolve().parents[4]
CREDENTIALS_PATH = ROOT / "credentials" / "gcp-key.json"

OUT_DIR = ROOT / "resources" / "regressions" / "reg_fe_compare" / "rho_estimation_pca"
CONFIG_DIR = OUT_DIR / "configs"
REG_DIR = OUT_DIR / "regressions"
INTERIM_DIR = ROOT / "data" / "interim" / "rho_estimation_pca"
CLEAN_TSE_DIR = ROOT / "data" / "clean" / "tse"

SOURCE_TABLE = "basedosdados.br_tse_eleicoes.resultados_candidato_municipio"
MAX_QUERY_BYTES = 2 * 1_000_000_000
LEFT_COALITION_PARTIES = {"PT", "PSB", "PCDOB", "PC DO B", "PDT", "PSOL", "PV"}

YEAR_META = {
    2006: {
        "candidate": "lula",
        "expected_runoff_share": 0.6083,
        "raw_dir": ROOT / "data" / "raw" / "tse_2006_president",
        "clean_path": CLEAN_TSE_DIR / "president_2006_municipality.csv",
    },
    2014: {
        "candidate": "dilma",
        "expected_runoff_share": 0.5164,
        "raw_dir": ROOT / "data" / "raw" / "tse_2014_president",
        "clean_path": CLEAN_TSE_DIR / "president_2014_municipality.csv",
    },
}

PRESIDENT_2010_PATH = CLEAN_TSE_DIR / "president_2010_municipality.csv"
PANEL_PATH = CLEAN_TSE_DIR / "president_pt_runoff_panel_2006_2014.csv"
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
    dirs = [OUT_DIR, CONFIG_DIR, REG_DIR, INTERIM_DIR, CLEAN_TSE_DIR]
    dirs.extend(meta["raw_dir"] for meta in YEAR_META.values())
    for path in dirs:
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


def build_year_output(year: int, runoff_raw: pd.DataFrame, first_raw: pd.DataFrame) -> pd.DataFrame:
    candidate = YEAR_META[year]["candidate"]
    runoff = clean_vote_file(runoff_raw)
    first = clean_vote_file(first_raw)

    runoff_group = (
        runoff.groupby(["id_municipio", "sigla_uf", "party_key"], as_index=False)["votos"]
        .sum()
    )
    runoff_totals = (
        runoff_group.groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": f"total_valid_votes_{year}_runoff"})
    )
    pt_runoff = (
        runoff_group[runoff_group["party_key"] == "PT"]
        .groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": f"{candidate}_votes_{year}_runoff"})
    )
    runoff_clean = runoff_totals.merge(pt_runoff, on=["id_municipio", "sigla_uf"], how="left")
    runoff_clean[f"{candidate}_votes_{year}_runoff"] = (
        runoff_clean[f"{candidate}_votes_{year}_runoff"].fillna(0)
    )
    runoff_clean[f"{candidate}_share_{year}_runoff"] = (
        runoff_clean[f"{candidate}_votes_{year}_runoff"]
        / runoff_clean[f"total_valid_votes_{year}_runoff"]
    )

    first_group = (
        first.groupby(["id_municipio", "sigla_uf", "party_key"], as_index=False)["votos"]
        .sum()
    )
    first_totals = (
        first_group.groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": f"total_valid_votes_{year}_first_round"})
    )
    pt_first = (
        first_group[first_group["party_key"] == "PT"]
        .groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": f"{candidate}_votes_{year}_first_round"})
    )
    left_keys = {normalize_party(p) for p in LEFT_COALITION_PARTIES}
    left_first = (
        first_group[first_group["party_key"].isin(left_keys)]
        .groupby(["id_municipio", "sigla_uf"], as_index=False)["votos"]
        .sum()
        .rename(columns={"votos": f"left_coalition_votes_{year}_first_round"})
    )
    first_clean = first_totals.merge(pt_first, on=["id_municipio", "sigla_uf"], how="left")
    first_clean = first_clean.merge(left_first, on=["id_municipio", "sigla_uf"], how="left")
    first_clean[
        [
            f"{candidate}_votes_{year}_first_round",
            f"left_coalition_votes_{year}_first_round",
        ]
    ] = first_clean[
        [
            f"{candidate}_votes_{year}_first_round",
            f"left_coalition_votes_{year}_first_round",
        ]
    ].fillna(0)
    first_clean[f"{candidate}_share_{year}_first_round"] = (
        first_clean[f"{candidate}_votes_{year}_first_round"]
        / first_clean[f"total_valid_votes_{year}_first_round"]
    )
    first_clean[f"left_coalition_share_{year}_first_round"] = (
        first_clean[f"left_coalition_votes_{year}_first_round"]
        / first_clean[f"total_valid_votes_{year}_first_round"]
    )

    combined = runoff_clean.merge(
        first_clean,
        on=["id_municipio", "sigla_uf"],
        how="outer",
        validate="one_to_one",
    )
    cols = [
        "id_municipio",
        "sigla_uf",
        f"{candidate}_share_{year}_runoff",
        f"{candidate}_share_{year}_first_round",
        f"left_coalition_share_{year}_first_round",
        f"total_valid_votes_{year}_runoff",
        f"total_valid_votes_{year}_first_round",
        f"{candidate}_votes_{year}_runoff",
        f"{candidate}_votes_{year}_first_round",
        f"left_coalition_votes_{year}_first_round",
    ]
    return combined[cols].sort_values("id_municipio").reset_index(drop=True)


def pull_year(client: bigquery.Client, year: int, records: list[QueryRecord]) -> pd.DataFrame:
    raw_dir = YEAR_META[year]["raw_dir"]
    runoff_csv = raw_dir / f"resultados_candidato_{year}_segundo_turno.csv"
    first_csv = raw_dir / f"resultados_candidato_{year}_primeiro_turno.csv"
    runoff_cache = INTERIM_DIR / f"resultados_candidato_{year}_segundo_turno.parquet"
    first_cache = INTERIM_DIR / f"resultados_candidato_{year}_primeiro_turno.parquet"

    runoff_raw = query_to_frame(
        client,
        f"president_{year}_runoff",
        election_query(year, 2),
        runoff_cache,
        runoff_csv,
        records,
    )
    first_raw = query_to_frame(
        client,
        f"president_{year}_first_round",
        election_query(year, 1),
        first_cache,
        first_csv,
        records,
    )
    clean = build_year_output(year, runoff_raw, first_raw)
    clean.to_csv(YEAR_META[year]["clean_path"], index=False)
    return clean


def load_2010() -> pd.DataFrame:
    df = pd.read_csv(PRESIDENT_2010_PATH, dtype={"id_municipio": str})
    df["id_municipio"] = df["id_municipio"].astype(str).str.zfill(7)
    return df


def build_wide_panel(p2006: pd.DataFrame, p2010: pd.DataFrame, p2014: pd.DataFrame) -> pd.DataFrame:
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
    panel = keep_2006.merge(keep_2010, on="id_municipio", how="outer")
    panel = panel.merge(keep_2014, on="id_municipio", how="outer")
    panel["id_municipio"] = panel["id_municipio"].astype(str).str.zfill(7)
    return panel.sort_values("id_municipio").reset_index(drop=True)


def weighted_share(df: pd.DataFrame, share: str, total: str) -> float:
    return float((df[share] * df[total]).sum() / df[total].sum())


def run_pca(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    runoff_cols = ["pt_share_2006_runoff", "pt_share_2010_runoff", "pt_share_2014_runoff"]
    complete = panel.dropna(subset=runoff_cols).copy()
    x = complete[runoff_cols].astype(float)
    means = x.mean()
    stds = x.std(ddof=0)
    z = (x - means) / stds

    u, s, vt = np.linalg.svd(z.to_numpy(), full_matrices=False)
    loadings = vt[0, :]
    raw_score = z.to_numpy() @ loadings
    sign_correction = 1
    if np.corrcoef(raw_score, x.mean(axis=1))[0, 1] < 0:
        sign_correction = -1
        loadings = -loadings
        raw_score = -raw_score

    eigenvalues = (s**2) / (len(z) - 1)
    variance_share = eigenvalues / eigenvalues.sum()
    pc1_z = (raw_score - raw_score.mean()) / raw_score.std(ddof=0)
    mean_runoff = x.mean(axis=1)
    # Put the regression-facing PC1 on the same scale as vote shares so
    # coefficients and SEs are comparable to the single-year benchmark.
    pc1_vote_scale = pc1_z * mean_runoff.std(ddof=0) + mean_runoff.mean()

    scores = complete[["id_municipio"]].copy()
    scores["pc1_score_raw"] = raw_score
    scores["pc1_score_z"] = pc1_z
    scores["pc1_score"] = pc1_vote_scale
    scores["pt_share_mean_runoff"] = mean_runoff
    scores["pt_share_mean_first_round"] = complete[
        ["pt_share_2006_first_round", "pt_share_2010_first_round", "pt_share_2014_first_round"]
    ].mean(axis=1)
    scores["left_coalition_share_mean_first_round"] = complete[
        [
            "left_coalition_share_2006_first_round",
            "left_coalition_share_2010_first_round",
            "left_coalition_share_2014_first_round",
        ]
    ].mean(axis=1)

    loadings_df = pd.DataFrame(
        {
            "year": [2006, 2010, 2014],
            "variable": runoff_cols,
            "pc1_loading": loadings,
            "standardized_mean": [means[col] for col in runoff_cols],
            "standardized_sd": [stds[col] for col in runoff_cols],
        }
    )
    variance_df = pd.DataFrame(
        {
            "component": ["PC1", "PC2", "PC3"],
            "eigenvalue": eigenvalues,
            "variance_explained": variance_share,
        }
    )
    diagnostics = {
        "n_total_municipalities": int(len(panel)),
        "n_full_runoff_coverage": int(len(complete)),
        "n_missing_any_runoff": int(len(panel) - len(complete)),
        "pc1_variance_explained": float(variance_share[0]),
        "pc1_loadings_same_sign": bool((loadings > 0).all() or (loadings < 0).all()),
        "sign_correction": int(sign_correction),
        "corr_pc1_mean_runoff": float(np.corrcoef(scores["pc1_score"], scores["pt_share_mean_runoff"])[0, 1]),
        "corr_pc1_2006": float(np.corrcoef(scores["pc1_score"], complete["pt_share_2006_runoff"])[0, 1]),
        "corr_pc1_2010": float(np.corrcoef(scores["pc1_score"], complete["pt_share_2010_runoff"])[0, 1]),
        "corr_pc1_2014": float(np.corrcoef(scores["pc1_score"], complete["pt_share_2014_runoff"])[0, 1]),
    }
    return scores, loadings_df, variance_df, diagnostics


def write_pca_diagnostics(loadings: pd.DataFrame, variance: pd.DataFrame, diagnostics: dict[str, object]) -> None:
    lines = [
        "# PCA Diagnostics",
        "",
        "The PCA uses standardized PT second-round vote shares from 2006, 2010, and 2014. The sign of PC1 is oriented so that higher scores indicate higher PT support.",
        "",
        "## Coverage",
        "",
        f"- Municipalities in the wide 2006-2014 panel: {diagnostics['n_total_municipalities']:,}.",
        f"- Municipalities with complete runoff coverage: {diagnostics['n_full_runoff_coverage']:,}.",
        f"- Municipalities missing at least one runoff share: {diagnostics['n_missing_any_runoff']:,}.",
        "",
        "## Loadings",
        "",
        loadings.to_markdown(index=False),
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
        f"Correlation between vote-share-scaled PC1 and simple runoff mean: {diagnostics['corr_pc1_mean_runoff']:.4f}.",
        f"Correlations with yearly runoff shares: 2006 = {diagnostics['corr_pc1_2006']:.4f}, 2010 = {diagnostics['corr_pc1_2010']:.4f}, 2014 = {diagnostics['corr_pc1_2014']:.4f}.",
        "",
        "For regression comparability with the single-year benchmark, `pc1_score` is the signed PC1 score rescaled to the mean and standard deviation of the simple three-year PT runoff average. The files also retain `pc1_score_raw` and `pc1_score_z` for audit.",
        "",
    ]
    (OUT_DIR / "pca_diagnostics.md").write_text("\n".join(lines))


def build_rho_pca_dataset(scores: pd.DataFrame) -> dict[str, object]:
    rho = pd.read_parquet(ORIGINAL_RHO_EVENT0)
    rho["municipality_id"] = rho["municipality_id"].astype(str).str.zfill(7)
    agg = scores[
        [
            "id_municipio",
            "pc1_score",
            "pt_share_mean_runoff",
            "pt_share_mean_first_round",
            "left_coalition_share_mean_first_round",
        ]
    ].copy()
    agg["municipality_id"] = agg["id_municipio"].astype(str).str.zfill(7)
    merged = rho.merge(
        agg.drop(columns=["id_municipio"]),
        on="municipality_id",
        how="left",
        indicator="pca_merge",
    )
    required = [
        "pc1_score",
        "pt_share_mean_runoff",
        "pt_share_mean_first_round",
        "left_coalition_share_mean_first_round",
    ]
    complete = merged.dropna(subset=required).copy()
    complete.to_parquet(OUT_DIR / "rho_dataset_event0_pca.parquet", index=False)
    diagnostics = {
        "original_event0_rows": int(len(rho)),
        "original_event0_municipalities": int(rho["municipality_id"].nunique()),
        "matched_pca_rows": int((merged["pca_merge"] == "both").sum()),
        "unmatched_pca_rows": int((merged["pca_merge"] != "both").sum()),
        "complete_rows": int(len(complete)),
        "complete_municipalities": int(complete["municipality_id"].nunique()),
        "unmatched_by_state": merged.loc[
            merged["pca_merge"] != "both", "state"
        ].value_counts().to_dict(),
    }
    return diagnostics


def write_config(name: str, outcome: str, regressor: str) -> None:
    config = {
        "data": {
            "path": str((OUT_DIR / "rho_dataset_event0_pca.parquet").relative_to(ROOT))
        },
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
        ("mean", "pt_share_mean_runoff"),
    ]:
        for label, cost in specs:
            write_config(f"{label}_event0_{outcome_suffix}", outcome, cost)


def write_election_summary(
    p2006: pd.DataFrame,
    p2010: pd.DataFrame,
    p2014: pd.DataFrame,
    panel: pd.DataFrame,
    pca_diag: dict[str, object],
    rho_diag: dict[str, object],
) -> None:
    rows = []
    for year, df, candidate in [
        (2006, p2006, "lula"),
        (2010, p2010, "dilma"),
        (2014, p2014, "dilma"),
    ]:
        rows.append(
            {
                "year": year,
                "clean_rows": len(df),
                "weighted_runoff_share": weighted_share(
                    df,
                    f"{candidate}_share_{year}_runoff",
                    f"total_valid_votes_{year}_runoff",
                ),
                "unweighted_runoff_mean": df[f"{candidate}_share_{year}_runoff"].mean(),
                "expected_national_runoff_share": YEAR_META.get(year, {}).get(
                    "expected_runoff_share", 0.5605
                ),
            }
        )
    summary = pd.DataFrame(rows)

    missing = {
        "missing_2006_runoff": int(panel["pt_share_2006_runoff"].isna().sum()),
        "missing_2010_runoff": int(panel["pt_share_2010_runoff"].isna().sum()),
        "missing_2014_runoff": int(panel["pt_share_2014_runoff"].isna().sum()),
    }
    lines = [
        "# Election Data Summary",
        "",
        f"Source table: `{SOURCE_TABLE}`. The 2010 file comes from the previously cleaned `data/clean/tse/president_2010_municipality.csv`; 2006 and 2014 were pulled with the same query structure.",
        "",
        "## Raw And Clean Files",
        "",
        "- 2006 raw runoff: `data/raw/tse_2006_president/resultados_candidato_2006_segundo_turno.csv`.",
        "- 2006 raw first round: `data/raw/tse_2006_president/resultados_candidato_2006_primeiro_turno.csv`.",
        "- 2006 clean: `data/clean/tse/president_2006_municipality.csv`.",
        "- 2014 raw runoff: `data/raw/tse_2014_president/resultados_candidato_2014_segundo_turno.csv`.",
        "- 2014 raw first round: `data/raw/tse_2014_president/resultados_candidato_2014_primeiro_turno.csv`.",
        "- 2014 clean: `data/clean/tse/president_2014_municipality.csv`.",
        "- Combined panel: `data/clean/tse/president_pt_runoff_panel_2006_2014.csv`.",
        "",
        "## Sanity Checks",
        "",
        summary.to_markdown(index=False),
        "",
        "## Coverage",
        "",
        f"- Wide panel rows: {len(panel):,}.",
        f"- Municipalities with complete 2006, 2010, and 2014 runoff coverage: {pca_diag['n_full_runoff_coverage']:,}.",
        f"- Missing by year: `{missing}`.",
        f"- Event-time-0 rho rows before PCA merge: {rho_diag['original_event0_rows']:,}.",
        f"- Event-time-0 rho rows matched to full PCA coverage: {rho_diag['matched_pca_rows']:,}.",
        f"- Event-time-0 rho rows unmatched to full PCA coverage: {rho_diag['unmatched_pca_rows']:,}.",
        f"- Unmatched event-time-0 rows by state: `{rho_diag['unmatched_by_state']}`.",
        "",
        "The 2014 presidential vote is contemporaneous with the first hybrid year for municipalities treated in 2014; this is retained by design for the multi-year construct and flagged in the summary as a limitation.",
        "",
    ]
    (OUT_DIR / "election_data_summary.md").write_text("\n".join(lines))


def main() -> None:
    ensure_dirs()
    records: list[QueryRecord] = []
    client = make_client()

    p2006 = pull_year(client, 2006, records)
    p2014 = pull_year(client, 2014, records)
    pd.DataFrame([record.__dict__ for record in records]).to_csv(
        OUT_DIR / "bdd_query_log.csv", index=False
    )

    p2010 = load_2010()
    panel = build_wide_panel(p2006, p2010, p2014)
    panel.to_csv(PANEL_PATH, index=False)

    scores, loadings, variance, pca_diag = run_pca(panel)
    loadings.to_csv(OUT_DIR / "pca_loadings.csv", index=False)
    variance.to_csv(OUT_DIR / "pca_variance_explained.csv", index=False)
    scores.to_csv(OUT_DIR / "municipality_pc1_scores.csv", index=False)
    scores[
        [
            "id_municipio",
            "pc1_score",
            "pt_share_mean_runoff",
            "pt_share_mean_first_round",
            "left_coalition_share_mean_first_round",
        ]
    ].to_csv(OUT_DIR / "aggregate_measures.csv", index=False)
    write_pca_diagnostics(loadings, variance, pca_diag)

    rho_diag = build_rho_pca_dataset(scores)
    write_configs()
    write_election_summary(p2006, p2010, p2014, panel, pca_diag, rho_diag)
    print(f"Wrote PCA rho inputs to {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
