from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.tse_bvr_common import CLEAN_DIR, INTERIM_DIR, RAW_TSE_DIR, ensure_directories, normalize_name


YEARS = [2012, 2014, 2016, 2018]
RAW_TEMPLATE = "quantitativo_municipios-municipio_{year}.csv"
OUT_BASE = "quantitativo_municipios_municipio_2012_2018"
COUNT_COLUMNS = [
    "qt_municipio",
    "qt_municipio_brasil",
    "qt_municipio_exterior",
    "qt_municipio_sem_biometria",
    "qt_municipio_biometria",
    "qt_municipio_hibrido",
]


def _read_quantitativo(path: Path, year: int) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="latin1", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df["year"] = year
    for col in COUNT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="raise").astype(int)
    df["state"] = df["sg_uf"].str.strip()
    df["municipality_name_tse_raw"] = df["nm_municipio"].str.strip()
    df["municipality_name_tse"] = df["municipality_name_tse_raw"].map(normalize_name)
    return df


def _status(row: pd.Series) -> str:
    if row["qt_municipio_biometria"] == 1:
        return "strict_bvr"
    if row["qt_municipio_hibrido"] == 1:
        return "hybrid_bvr"
    if row["qt_municipio_sem_biometria"] == 1:
        return "no_bvr"
    return "invalid_status"


def _load_year_match_map(year: int) -> pd.DataFrame:
    path = Path("data/interim/tse_eleitorado") / f"harmonized_{year}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing harmonized TSE eleitorado file: {path}")
    cols = [
        "state",
        "municipality_name",
        "municipality_name_raw",
        "municipality_id",
        "matched_name_crosswalk",
        "match_method",
        "confidence",
        "notes",
    ]
    df = pd.read_parquet(path, columns=cols).drop_duplicates()
    df = df.rename(
        columns={
            "municipality_name": "municipality_name_tse",
            "municipality_name_raw": "municipality_name_tse_eleitorado_raw",
            "matched_name_crosswalk": "municipality_name_ibge_from_crosswalk",
            "match_method": "eleitorado_match_method",
            "confidence": "eleitorado_match_confidence",
            "notes": "eleitorado_match_notes",
        }
    )
    df["year"] = year
    duplicate_keys = df.duplicated(["year", "state", "municipality_name_tse"], keep=False)
    if duplicate_keys.any():
        dupes = df.loc[duplicate_keys, ["year", "state", "municipality_name_tse", "municipality_id"]]
        raise ValueError(f"Ambiguous year/state/name keys in {path}:\n{dupes.to_string(index=False)}")
    return df


def build_matched_quantitativo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ensure_directories()
    ibge = pd.read_csv(CLEAN_DIR / "ibge_municipalities.csv", dtype={"municipality_id": str})
    ibge = ibge.rename(
        columns={
            "municipality_name": "municipality_name_ibge_current",
            "municipality_name_raw": "municipality_name_ibge_raw",
        }
    )

    raw_frames = []
    match_frames = []
    for year in YEARS:
        raw_path = RAW_TSE_DIR / RAW_TEMPLATE.format(year=year)
        if not raw_path.exists():
            raise FileNotFoundError(f"Missing raw quantitativo file: {raw_path}")
        raw_frames.append(_read_quantitativo(raw_path, year))
        match_frames.append(_load_year_match_map(year))

    raw = pd.concat(raw_frames, ignore_index=True)
    match_map = pd.concat(match_frames, ignore_index=True)
    matched = raw.merge(
        match_map,
        on=["year", "state", "municipality_name_tse"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    matched = matched.merge(ibge, on=["municipality_id", "state"], how="left", validate="many_to_one")

    matched["bvr_status"] = matched.apply(_status, axis=1)
    matched["has_bvr"] = matched["bvr_status"].isin(["strict_bvr", "hybrid_bvr"])
    matched["is_strict_bvr"] = matched["bvr_status"].eq("strict_bvr")
    matched["is_hybrid_bvr"] = matched["bvr_status"].eq("hybrid_bvr")
    matched["status_count_sum"] = (
        matched["qt_municipio_sem_biometria"]
        + matched["qt_municipio_biometria"]
        + matched["qt_municipio_hibrido"]
    )
    matched["name_matches_current_ibge"] = matched["municipality_name_tse"].eq(
        matched["municipality_name_ibge_current"]
    )
    matched["match_method"] = matched["name_matches_current_ibge"].map(
        {True: "exact_state_normalized_ibge_name", False: "state_name_via_harmonized_tse_eleitorado"}
    )
    matched.loc[matched["_merge"].ne("both"), "match_method"] = "unmatched"
    matched["needs_manual_review"] = (
        matched["_merge"].ne("both")
        | matched["municipality_id"].isna()
        | matched["municipality_name_ibge_current"].isna()
        | matched["bvr_status"].eq("invalid_status")
        | matched["status_count_sum"].ne(1)
    )
    matched["review_reason"] = ""
    matched.loc[matched["_merge"].ne("both"), "review_reason"] = "No year/state/name match in harmonized TSE eleitorado map."
    matched.loc[matched["municipality_id"].isna(), "review_reason"] = "Missing IBGE municipality ID after matching."
    matched.loc[matched["municipality_name_ibge_current"].isna(), "review_reason"] = "Matched ID is absent from current IBGE municipality table."
    matched.loc[matched["bvr_status"].eq("invalid_status"), "review_reason"] = "Could not classify BVR status."
    matched.loc[matched["status_count_sum"].ne(1), "review_reason"] = "Status columns do not sum to one."

    out_cols = [
        "year",
        "nm_pais",
        "nm_regiao",
        "state",
        "municipality_id",
        "municipality_name_ibge_current",
        "municipality_name_ibge_raw",
        "municipality_name_tse",
        "municipality_name_tse_raw",
        "municipality_name_tse_eleitorado_raw",
        "municipality_name_ibge_from_crosswalk",
        *COUNT_COLUMNS,
        "bvr_status",
        "has_bvr",
        "is_strict_bvr",
        "is_hybrid_bvr",
        "match_method",
        "eleitorado_match_method",
        "eleitorado_match_confidence",
        "name_matches_current_ibge",
        "needs_manual_review",
        "review_reason",
        "eleitorado_match_notes",
    ]
    matched = matched[out_cols].sort_values(["year", "state", "municipality_name_tse"]).reset_index(drop=True)

    review = matched.loc[
        matched["needs_manual_review"] | ~matched["name_matches_current_ibge"],
        [
            "year",
            "state",
            "municipality_id",
            "municipality_name_tse_raw",
            "municipality_name_tse",
            "municipality_name_ibge_current",
            "municipality_name_ibge_raw",
            "bvr_status",
            "match_method",
            "needs_manual_review",
            "review_reason",
        ],
    ].copy()

    summary = (
        matched.groupby(["year", "bvr_status"], dropna=False)
        .agg(municipalities=("municipality_id", "nunique"), rows=("municipality_id", "size"))
        .reset_index()
        .sort_values(["year", "bvr_status"])
    )
    return matched, review, summary


def main() -> None:
    matched, review, summary = build_matched_quantitativo()
    csv_path = INTERIM_DIR / f"{OUT_BASE}_matched.csv"
    parquet_path = INTERIM_DIR / f"{OUT_BASE}_matched.parquet"
    review_path = INTERIM_DIR / f"{OUT_BASE}_match_review.csv"
    summary_path = INTERIM_DIR / f"{OUT_BASE}_summary.csv"

    matched.to_csv(csv_path, index=False)
    matched.to_parquet(parquet_path, index=False)
    review.to_csv(review_path, index=False)
    summary.to_csv(summary_path, index=False)

    print(f"Wrote {len(matched)} matched rows to {csv_path}")
    print(f"Wrote {len(review)} audit/review rows to {review_path}")
    print(f"Rows requiring manual review: {int(matched['needs_manual_review'].sum())}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
