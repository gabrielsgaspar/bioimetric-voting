from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.cleaning.parse_tse_eleitorado import canonicalize_text, map_education
from src.tse_eleitorado_common import (
    IBGE_CROSSWALK_PATH,
    INTERIM_DIR,
    OFFICIAL_PACKAGE_YEARS,
    RAW_DIR,
    VALID_UFS,
    ensure_directories,
    normalize_name,
    normalize_state,
)


ROOT = Path(__file__).resolve().parents[2]
CLEAN_DIR = ROOT / "data" / "clean" / "tse_eleitorado"
INTERIM_OUTPUT = INTERIM_DIR / "biometric_education_shares_2000_2018_diagnostics.csv"
OUTPUT_CSV = CLEAN_DIR / "eleitorado_biometric_shares_2000_2018.csv"
OUTPUT_PARQUET = CLEAN_DIR / "eleitorado_biometric_shares_2000_2018.parquet"

IBGE_NAME_PATH = ROOT / "data" / "clean" / "tse_bvr" / "ibge_municipalities.csv"

CHUNKSIZE = 500_000
REQUIRED_COLUMNS = [
    "ANO_ELEICAO",
    "SG_UF",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "DS_GRAU_ESCOLARIDADE",
    "QT_ELEITORES_PERFIL",
    "QT_ELEITORES_BIOMETRIA",
]

LOW_ED_CATEGORIES = {
    "illiterate",
    "reads_and_writes",
    "incomplete_primary",
    "complete_primary",
}
HIGH_ED_CATEGORIES = {
    "incomplete_secondary",
    "complete_secondary",
    "incomplete_higher",
    "complete_higher",
}


def open_zip_csv(zip_path: Path) -> tuple[zipfile.ZipFile, str]:
    archive = zipfile.ZipFile(zip_path)
    csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if not csv_names:
        archive.close()
        raise RuntimeError(f"No CSV file found inside {zip_path}")
    preferred = next((name for name in csv_names if "perfil_eleitorado" in Path(name).name.lower()), csv_names[0])
    return archive, preferred


def load_crosswalk() -> pd.DataFrame:
    crosswalk = pd.read_csv(IBGE_CROSSWALK_PATH, dtype=str)
    crosswalk["year"] = pd.to_numeric(crosswalk["year"], errors="coerce").astype("Int64")
    crosswalk["state"] = crosswalk["state"].astype(str).str.upper().str.strip()
    crosswalk["municipality_id"] = (
        crosswalk["municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    )
    crosswalk["tse_municipality_id"] = (
        crosswalk["tse_municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    )
    return crosswalk


def load_ibge_names() -> pd.DataFrame:
    if not IBGE_NAME_PATH.exists():
        return pd.DataFrame(columns=["municipality_id", "matched_name_crosswalk", "state", "_norm_name"])
    ibge = pd.read_csv(IBGE_NAME_PATH, dtype=str)
    ibge = ibge.rename(columns={"municipality_name": "matched_name_crosswalk"})[
        ["municipality_id", "matched_name_crosswalk", "state"]
    ].copy()
    ibge["municipality_id"] = ibge["municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    ibge["state"] = ibge["state"].astype(str).str.upper().str.strip()
    ibge["_norm_name"] = ibge["matched_name_crosswalk"].map(normalize_name)
    return ibge


def parse_year(year: int) -> pd.DataFrame:
    zip_path = RAW_DIR / str(year) / f"perfil_eleitorado_{year}.zip"
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    archive, member = open_zip_csv(zip_path)
    try:
        with archive.open(member) as handle:
            columns = list(pd.read_csv(handle, sep=";", encoding="latin1", nrows=0).columns)
        missing = [column for column in REQUIRED_COLUMNS if column not in columns]
        if missing:
            raise RuntimeError(f"{zip_path.name} is missing required columns: {missing}")

        chunks: list[pd.DataFrame] = []
        with archive.open(member) as handle:
            reader = pd.read_csv(
                handle,
                sep=";",
                encoding="latin1",
                usecols=REQUIRED_COLUMNS,
                chunksize=CHUNKSIZE,
            )
            for chunk in reader:
                chunk = chunk.rename(
                    columns={
                        "ANO_ELEICAO": "year",
                        "SG_UF": "state",
                        "CD_MUNICIPIO": "tse_municipality_id",
                        "NM_MUNICIPIO": "municipality_name_raw",
                        "DS_GRAU_ESCOLARIDADE": "education_raw",
                        "QT_ELEITORES_PERFIL": "num_voters",
                        "QT_ELEITORES_BIOMETRIA": "num_voters_biometric",
                    }
                )
                chunk["year"] = pd.to_numeric(chunk["year"], errors="coerce").astype("Int64")
                chunk["state"] = chunk["state"].map(normalize_state)
                chunk["tse_municipality_id"] = (
                    chunk["tse_municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
                )
                chunk["municipality_name_raw"] = chunk["municipality_name_raw"].map(canonicalize_text)
                chunk["municipality_name"] = chunk["municipality_name_raw"].map(normalize_name)
                chunk["education_raw"] = chunk["education_raw"].map(canonicalize_text)
                chunk["education"] = chunk["education_raw"].map(map_education)
                chunk["num_voters"] = pd.to_numeric(chunk["num_voters"], errors="coerce").fillna(0).astype("int64")
                chunk["num_voters_biometric"] = (
                    pd.to_numeric(chunk["num_voters_biometric"], errors="coerce").fillna(0).astype("int64")
                )

                grouped = (
                    chunk.groupby(
                        [
                            "year",
                            "state",
                            "tse_municipality_id",
                            "municipality_name_raw",
                            "municipality_name",
                            "education",
                        ],
                        as_index=False,
                        dropna=False,
                    )[["num_voters", "num_voters_biometric"]]
                    .sum()
                )
                chunks.append(grouped)
    finally:
        archive.close()

    if not chunks:
        return pd.DataFrame()

    parsed = (
        pd.concat(chunks, ignore_index=True)
        .groupby(
            ["year", "state", "tse_municipality_id", "municipality_name_raw", "municipality_name", "education"],
            as_index=False,
            dropna=False,
        )[["num_voters", "num_voters_biometric"]]
        .sum()
    )
    parsed["year"] = parsed["year"].astype(int)
    return parsed


def attach_ids(df: pd.DataFrame, crosswalk: pd.DataFrame, ibge_names: pd.DataFrame) -> pd.DataFrame:
    merged = df.merge(
        crosswalk,
        how="left",
        on=["year", "state", "tse_municipality_id"],
        validate="many_to_one",
    )
    merged["matched_via_direct_code"] = merged["municipality_id"].notna()

    unmatched_mask = merged["municipality_id"].isna()
    if unmatched_mask.any() and not ibge_names.empty:
        fallback = (
            merged.loc[
                unmatched_mask,
                ["year", "state", "tse_municipality_id", "municipality_name_raw", "municipality_name"],
            ]
            .drop_duplicates()
            .merge(
                ibge_names,
                how="left",
                left_on=["state", "municipality_name"],
                right_on=["state", "_norm_name"],
            )
        )
        fallback = fallback[["year", "state", "tse_municipality_id", "municipality_id", "matched_name_crosswalk"]]
        merged = merged.merge(
            fallback,
            how="left",
            on=["year", "state", "tse_municipality_id"],
            suffixes=("", "_fallback"),
        )
        merged["municipality_id"] = merged["municipality_id"].fillna(merged["municipality_id_fallback"])
        merged = merged.drop(columns=[col for col in merged.columns if col.endswith("_fallback")], errors="ignore")

    merged = merged.merge(
        ibge_names[["municipality_id", "state", "matched_name_crosswalk"]],
        how="left",
        on=["municipality_id", "state"],
    )
    if "matched_name_crosswalk_x" in merged.columns or "matched_name_crosswalk_y" in merged.columns:
        left = merged.get("matched_name_crosswalk_x", pd.Series(index=merged.index, dtype="object"))
        right = merged.get("matched_name_crosswalk_y", pd.Series(index=merged.index, dtype="object"))
        merged["matched_name_crosswalk"] = left.fillna(right)
        merged = merged.drop(columns=["matched_name_crosswalk_x", "matched_name_crosswalk_y"], errors="ignore")
    return merged


def _safe_share(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.where(denominator > 0) / denominator.where(denominator > 0)


def build_shares() -> tuple[pd.DataFrame, pd.DataFrame]:
    ensure_directories()
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    crosswalk = load_crosswalk()
    ibge_names = load_ibge_names()
    frames = [parse_year(year) for year in OFFICIAL_PACKAGE_YEARS]
    parsed = pd.concat(frames, ignore_index=True)
    parsed = parsed[parsed["state"].isin(VALID_UFS)].copy()

    harmonized = attach_ids(parsed, crosswalk, ibge_names)
    unmatched = harmonized[harmonized["municipality_id"].isna()].copy()
    municipality_rows = harmonized[harmonized["municipality_id"].notna()].copy()
    municipality_rows["municipality_id"] = (
        municipality_rows["municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    )

    municipality_rows["is_low_ed"] = municipality_rows["education"].isin(LOW_ED_CATEGORIES)
    municipality_rows["is_high_ed"] = municipality_rows["education"].isin(HIGH_ED_CATEGORIES)

    municipality_rows["num_voters_low_ed"] = np.where(municipality_rows["is_low_ed"], municipality_rows["num_voters"], 0)
    municipality_rows["num_voters_high_ed"] = np.where(
        municipality_rows["is_high_ed"], municipality_rows["num_voters"], 0
    )
    municipality_rows["num_voters_biometric_low_ed"] = np.where(
        municipality_rows["is_low_ed"], municipality_rows["num_voters_biometric"], 0
    )
    municipality_rows["num_voters_biometric_high_ed"] = np.where(
        municipality_rows["is_high_ed"], municipality_rows["num_voters_biometric"], 0
    )

    grouped = (
        municipality_rows.groupby(["year", "municipality_id", "state"], as_index=False)
        .agg(
            municipality_name=("matched_name_crosswalk", "first"),
            num_voters=("num_voters", "sum"),
            num_voters_biometric=("num_voters_biometric", "sum"),
            num_voters_low_ed=("num_voters_low_ed", "sum"),
            num_voters_high_ed=("num_voters_high_ed", "sum"),
            num_voters_biometric_low_ed=("num_voters_biometric_low_ed", "sum"),
            num_voters_biometric_high_ed=("num_voters_biometric_high_ed", "sum"),
        )
        .sort_values(["year", "state", "municipality_id"])
        .reset_index(drop=True)
    )

    year_totals = grouped.groupby("year")["num_voters_biometric"].sum()
    available_years = sorted(year_totals[year_totals > 0].index.astype(int).tolist())
    grouped["biometric_share_data_available"] = grouped["year"].isin(available_years)

    grouped["pct_with_bvr"] = _safe_share(grouped["num_voters_biometric"], grouped["num_voters"])
    grouped["pct_low_ed_with_bvr"] = _safe_share(
        grouped["num_voters_biometric_low_ed"], grouped["num_voters_low_ed"]
    )
    grouped["pct_high_ed_with_bvr"] = _safe_share(
        grouped["num_voters_biometric_high_ed"], grouped["num_voters_high_ed"]
    )
    share_cols = ["pct_with_bvr", "pct_low_ed_with_bvr", "pct_high_ed_with_bvr"]
    grouped.loc[~grouped["biometric_share_data_available"], share_cols] = np.nan

    for column in share_cols:
        bad = grouped[column].dropna()
        if ((bad < -1e-12) | (bad > 1 + 1e-12)).any():
            raise ValueError(f"{column} has values outside [0, 1].")

    output = grouped[
        [
            "year",
            "municipality_id",
            "municipality_name",
            "state",
            "pct_with_bvr",
            "pct_low_ed_with_bvr",
            "pct_high_ed_with_bvr",
            "biometric_share_data_available",
        ]
    ].copy()

    duplicate = int(output.duplicated(["year", "municipality_id"]).sum())
    if duplicate:
        raise ValueError(f"Biometric share output has {duplicate} duplicate year x municipality_id rows.")

    diagnostics = (
        grouped.groupby("year", as_index=False)
        .agg(
            rows=("municipality_id", "size"),
            municipalities=("municipality_id", "nunique"),
            biometric_share_data_available=("biometric_share_data_available", "max"),
            national_num_voters=("num_voters", "sum"),
            national_num_voters_biometric=("num_voters_biometric", "sum"),
            nonmissing_pct_with_bvr=("pct_with_bvr", lambda s: int(s.notna().sum())),
            nonmissing_pct_low_ed_with_bvr=("pct_low_ed_with_bvr", lambda s: int(s.notna().sum())),
            nonmissing_pct_high_ed_with_bvr=("pct_high_ed_with_bvr", lambda s: int(s.notna().sum())),
            mean_pct_with_bvr=("pct_with_bvr", "mean"),
            mean_pct_low_ed_with_bvr=("pct_low_ed_with_bvr", "mean"),
            mean_pct_high_ed_with_bvr=("pct_high_ed_with_bvr", "mean"),
        )
        .sort_values("year")
    )
    diagnostics["unmatched_valid_uf_rows"] = int(len(unmatched))
    diagnostics["shares_set_missing_rule"] = np.where(
        diagnostics["biometric_share_data_available"],
        "raw biometric counts positive nationally",
        "raw biometric counts zero nationally; set shares missing",
    )
    return output, diagnostics


def main() -> None:
    shares, diagnostics = build_shares()
    shares.to_csv(OUTPUT_CSV, index=False)
    shares.to_parquet(OUTPUT_PARQUET, index=False)
    diagnostics.to_csv(INTERIM_OUTPUT, index=False)
    print(f"Wrote {len(shares)} rows to {OUTPUT_CSV}")
    print(f"Wrote diagnostics to {INTERIM_OUTPUT}")
    print(diagnostics.to_string(index=False))


if __name__ == "__main__":
    main()
