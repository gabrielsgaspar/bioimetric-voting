from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.cleaning.parse_tse_eleitorado import canonicalize_text, map_education
from src.tse_eleitorado_common import IBGE_CROSSWALK_PATH, RAW_DIR, VALID_UFS, normalize_name, normalize_state


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_data.parquet"
IBGE_NAME_PATH = ROOT / "data" / "clean" / "tse_bvr" / "ibge_municipalities.csv"
BVR_PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"
BVR_PANEL_CSV_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018_bvr_status_updated.csv"

SOURCE_YEARS = list(range(2008, 2019, 2))
CHUNKSIZE = 500_000
LOW_ED_CATEGORIES = {"illiterate", "reads_and_writes", "incomplete_primary", "complete_primary"}
HIGH_ED_CATEGORIES = {"incomplete_secondary", "complete_secondary", "incomplete_higher", "complete_higher"}

REQUIRED_COLUMNS = [
    "ANO_ELEICAO",
    "SG_UF",
    "CD_MUNICIPIO",
    "NM_MUNICIPIO",
    "DS_FAIXA_ETARIA",
    "DS_GRAU_ESCOLARIDADE",
    "QT_ELEITORES_PERFIL",
    "QT_ELEITORES_BIOMETRIA",
]

OUTPUT_COLUMNS = [
    "year",
    "ibge_municipality_id",
    "state",
    "bvr_status",
    "year_first_any_bvr",
    "year_first_strict_bvr",
    "year_first_hybrid_bvr",
    "age_cohort",
    "education",
    "low_ed",
    "high_ed",
    "num_voters",
    "num_voters_bvr",
    "pct_bvr",
]


def normalize_code(value: object, width: int | None = None) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(char for char in text if char.isdigit())
    if not digits:
        return ""
    if width is None:
        return digits.lstrip("0") or "0"
    return digits.zfill(width) if width else digits


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
    crosswalk["ibge_municipality_id"] = crosswalk["municipality_id"].map(lambda x: normalize_code(x, width=7))
    crosswalk["tse_municipality_id"] = crosswalk["tse_municipality_id"].map(normalize_code)
    crosswalk = crosswalk[["year", "state", "tse_municipality_id", "ibge_municipality_id"]].drop_duplicates()
    duplicates = crosswalk.duplicated(["year", "state", "tse_municipality_id"]).sum()
    if duplicates:
        raise ValueError(f"Crosswalk has {duplicates} duplicate year/state/TSE municipality keys.")
    return crosswalk


def load_ibge_names() -> pd.DataFrame:
    if not IBGE_NAME_PATH.exists():
        return pd.DataFrame(columns=["ibge_municipality_id", "state", "_norm_name"])
    ibge = pd.read_csv(IBGE_NAME_PATH, dtype=str)
    ibge["ibge_municipality_id"] = ibge["municipality_id"].map(lambda x: normalize_code(x, width=7))
    ibge["state"] = ibge["state"].astype(str).str.upper().str.strip()
    ibge["_norm_name"] = ibge["municipality_name"].map(normalize_name)
    ibge = ibge[["ibge_municipality_id", "state", "_norm_name"]].drop_duplicates()
    duplicates = ibge.duplicated(["state", "_norm_name"]).sum()
    if duplicates:
        duplicated_names = ibge.loc[ibge.duplicated(["state", "_norm_name"], keep=False), ["state", "_norm_name"]]
        raise ValueError(f"IBGE name fallback has duplicate state/name keys:\n{duplicated_names.head()}")
    return ibge


def load_bvr_treatment() -> pd.DataFrame:
    if BVR_PANEL_PATH.exists():
        bvr = pd.read_parquet(BVR_PANEL_PATH)
    elif BVR_PANEL_CSV_PATH.exists():
        bvr = pd.read_csv(BVR_PANEL_CSV_PATH, dtype=str)
    else:
        raise FileNotFoundError(f"Missing BVR panel at {BVR_PANEL_PATH} or {BVR_PANEL_CSV_PATH}")

    required = {
        "year_election",
        "municipality_id",
        "bvr_status",
        "year_first_any_bvr",
        "year_first_strict_bvr",
        "year_first_hybrid_bvr",
    }
    missing = sorted(required - set(bvr.columns))
    if missing:
        raise RuntimeError(f"BVR panel is missing required columns: {missing}")

    bvr = bvr[
        [
            "year_election",
            "municipality_id",
            "bvr_status",
            "year_first_any_bvr",
            "year_first_strict_bvr",
            "year_first_hybrid_bvr",
        ]
    ].copy()
    bvr = bvr.rename(columns={"year_election": "year", "municipality_id": "ibge_municipality_id"})
    bvr["year"] = pd.to_numeric(bvr["year"], errors="coerce").astype("Int64")
    bvr = bvr[bvr["year"].isin(SOURCE_YEARS)].copy()
    bvr["year"] = bvr["year"].astype(int)
    bvr["ibge_municipality_id"] = bvr["ibge_municipality_id"].map(lambda x: normalize_code(x, width=7))
    bvr["bvr_status"] = bvr["bvr_status"].astype(str).str.strip()
    for column in ["year_first_any_bvr", "year_first_strict_bvr", "year_first_hybrid_bvr"]:
        bvr[column] = pd.to_numeric(bvr[column], errors="raise").astype(int)

    expected_statuses = {"strict_bvr", "hybrid_bvr", "no_bvr"}
    unexpected = sorted(set(bvr["bvr_status"].dropna()) - expected_statuses)
    if unexpected:
        raise ValueError(f"Unexpected bvr_status values: {unexpected}")

    duplicate_count = int(bvr.duplicated(["year", "ibge_municipality_id"]).sum())
    if duplicate_count:
        raise ValueError(f"BVR panel has {duplicate_count} duplicate year/municipality status rows.")
    return bvr


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

        pieces: list[pd.DataFrame] = []
        with archive.open(member) as handle:
            reader = pd.read_csv(
                handle,
                sep=";",
                encoding="latin1",
                usecols=REQUIRED_COLUMNS,
                dtype=str,
                chunksize=CHUNKSIZE,
            )
            for chunk in reader:
                chunk = chunk.rename(
                    columns={
                        "ANO_ELEICAO": "year",
                        "SG_UF": "state",
                        "CD_MUNICIPIO": "tse_municipality_id",
                        "NM_MUNICIPIO": "municipality_name_raw",
                        "DS_FAIXA_ETARIA": "age_cohort",
                        "DS_GRAU_ESCOLARIDADE": "education",
                        "QT_ELEITORES_PERFIL": "num_voters",
                        "QT_ELEITORES_BIOMETRIA": "num_voters_bvr",
                    }
                )
                chunk["year"] = pd.to_numeric(chunk["year"], errors="coerce").astype("Int64")
                chunk["state"] = chunk["state"].map(normalize_state)
                chunk["tse_municipality_id"] = chunk["tse_municipality_id"].map(normalize_code)
                chunk["municipality_name_raw"] = chunk["municipality_name_raw"].map(canonicalize_text)
                chunk["municipality_name_norm"] = chunk["municipality_name_raw"].map(normalize_name)
                chunk["age_cohort"] = chunk["age_cohort"].map(canonicalize_text)
                chunk["education"] = chunk["education"].map(canonicalize_text)
                chunk["num_voters"] = pd.to_numeric(chunk["num_voters"], errors="coerce").fillna(0).astype("int64")
                chunk["num_voters_bvr"] = (
                    pd.to_numeric(chunk["num_voters_bvr"], errors="coerce").fillna(0).astype("int64")
                )

                grouped = (
                    chunk.groupby(
                        [
                            "year",
                            "state",
                            "tse_municipality_id",
                            "municipality_name_raw",
                            "municipality_name_norm",
                            "age_cohort",
                            "education",
                        ],
                        as_index=False,
                        dropna=False,
                    )[["num_voters", "num_voters_bvr"]]
                    .sum()
                )
                pieces.append(grouped)
    finally:
        archive.close()

    parsed = pd.concat(pieces, ignore_index=True)
    parsed = (
        parsed.groupby(
            [
                "year",
                "state",
                "tse_municipality_id",
                "municipality_name_raw",
                "municipality_name_norm",
                "age_cohort",
                "education",
            ],
            as_index=False,
            dropna=False,
        )[["num_voters", "num_voters_bvr"]]
        .sum()
        .reset_index(drop=True)
    )
    parsed["year"] = parsed["year"].astype(int)
    return parsed


def attach_ibge_ids(parsed: pd.DataFrame, crosswalk: pd.DataFrame, ibge_names: pd.DataFrame) -> pd.DataFrame:
    merged = parsed.merge(
        crosswalk,
        how="left",
        on=["year", "state", "tse_municipality_id"],
        validate="many_to_one",
    )
    merged["matched_direct"] = merged["ibge_municipality_id"].notna() & merged["ibge_municipality_id"].ne("")

    unmatched = merged["ibge_municipality_id"].isna() | merged["ibge_municipality_id"].eq("")
    if unmatched.any() and not ibge_names.empty:
        fallback_keys = (
            merged.loc[
                unmatched,
                ["year", "state", "tse_municipality_id", "municipality_name_norm"],
            ]
            .drop_duplicates()
            .merge(
                ibge_names,
                how="left",
                left_on=["state", "municipality_name_norm"],
                right_on=["state", "_norm_name"],
            )
        )
        fallback = fallback_keys[["year", "state", "tse_municipality_id", "ibge_municipality_id"]]
        merged = merged.merge(
            fallback,
            how="left",
            on=["year", "state", "tse_municipality_id"],
            suffixes=("", "_fallback"),
        )
        merged["ibge_municipality_id"] = merged["ibge_municipality_id"].fillna(
            merged["ibge_municipality_id_fallback"]
        )
        merged = merged.drop(columns=["ibge_municipality_id_fallback"], errors="ignore")

    merged["ibge_municipality_id"] = merged["ibge_municipality_id"].map(lambda x: normalize_code(x, width=7))
    return merged


def build_decomposition() -> tuple[pd.DataFrame, pd.DataFrame]:
    crosswalk = load_crosswalk()
    ibge_names = load_ibge_names()
    bvr_treatment = load_bvr_treatment()

    parsed = pd.concat([parse_year(year) for year in SOURCE_YEARS], ignore_index=True)
    parsed = parsed[parsed["state"].isin(VALID_UFS)].copy()
    harmonized = attach_ibge_ids(parsed, crosswalk, ibge_names)

    unmatched = harmonized[harmonized["ibge_municipality_id"].eq("")].copy()
    if not unmatched.empty:
        unmatched_summary = (
            unmatched.groupby(["year", "state"], as_index=False)
            .agg(raw_municipality_cells=("tse_municipality_id", "nunique"), rows=("tse_municipality_id", "size"))
            .sort_values(["year", "state"])
        )
        raise RuntimeError(f"Unmatched valid-UF municipality rows remain:\n{unmatched_summary.to_string(index=False)}")

    output = (
        harmonized.groupby(
            ["year", "ibge_municipality_id", "state", "age_cohort", "education"],
            as_index=False,
            dropna=False,
        )[["num_voters", "num_voters_bvr"]]
        .sum()
        .sort_values(["year", "state", "ibge_municipality_id", "age_cohort", "education"])
        .reset_index(drop=True)
    )
    output = output.merge(bvr_treatment, how="left", on=["year", "ibge_municipality_id"], validate="many_to_one")
    missing_status = output["bvr_status"].isna().sum()
    if missing_status:
        missing_summary = (
            output.loc[output["bvr_status"].isna()]
            .groupby(["year", "state"], as_index=False)
            .agg(rows=("ibge_municipality_id", "size"), municipalities=("ibge_municipality_id", "nunique"))
            .sort_values(["year", "state"])
        )
        raise RuntimeError(f"{missing_status} rows are missing BVR status:\n{missing_summary.to_string(index=False)}")

    output["pct_bvr"] = output["num_voters_bvr"].where(output["num_voters"] > 0) / output["num_voters"].where(
        output["num_voters"] > 0
    )
    education_mapped = output["education"].map(map_education)
    output["low_ed"] = education_mapped.isin(LOW_ED_CATEGORIES).astype("int64")
    output["high_ed"] = education_mapped.isin(HIGH_ED_CATEGORIES).astype("int64")
    output = output[OUTPUT_COLUMNS].copy()

    duplicate_count = int(output.duplicated(["year", "ibge_municipality_id", "age_cohort", "education"]).sum())
    if duplicate_count:
        raise ValueError(f"Output has {duplicate_count} duplicate year/municipality/age/education rows.")

    diagnostics = (
        output.groupby("year", as_index=False)
        .agg(
            rows=("ibge_municipality_id", "size"),
            municipalities=("ibge_municipality_id", "nunique"),
            num_voters=("num_voters", "sum"),
            num_voters_bvr=("num_voters_bvr", "sum"),
            missing_pct_bvr=("pct_bvr", lambda s: int(s.isna().sum())),
            strict_bvr_municipalities=("ibge_municipality_id", lambda s: output.loc[s.index, "bvr_status"].eq("strict_bvr").groupby(s).any().sum()),
            hybrid_bvr_municipalities=("ibge_municipality_id", lambda s: output.loc[s.index, "bvr_status"].eq("hybrid_bvr").groupby(s).any().sum()),
            no_bvr_municipalities=("ibge_municipality_id", lambda s: output.loc[s.index, "bvr_status"].eq("no_bvr").groupby(s).any().sum()),
        )
        .sort_values("year")
    )
    diagnostics["age_categories"] = output.groupby("year")["age_cohort"].nunique().reindex(diagnostics["year"]).to_numpy()
    diagnostics["education_categories"] = (
        output.groupby("year")["education"].nunique().reindex(diagnostics["year"]).to_numpy()
    )
    return output, diagnostics


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output, diagnostics = build_decomposition()
    output.to_parquet(OUTPUT_PATH, index=False)
    print(f"Wrote {len(output):,} rows to {OUTPUT_PATH}")
    print(diagnostics.to_string(index=False))


if __name__ == "__main__":
    main()
