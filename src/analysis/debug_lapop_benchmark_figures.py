from __future__ import annotations

import csv
import json
import string
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from unidecode import unidecode


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "src" / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from run_lapop_trust_regressions import (  # noqa: E402
    IBGE_MUNICIPALITIES_PATH,
    REG_READY_PARQUET,
    STATE_NAME_TO_ABBREV,
    TREATMENT_PATH,
    build_municipal_covariates,
)


ZIP_PATH = ROOT / "Biometric-Voting.zip"
BENCHMARK_CACHE_DIR = ROOT / "data" / "interim" / "lapop" / "benchmark_zip_cache"
INTERIM_DIR = ROOT / "data" / "interim" / "lapop"
DOCS_DIR = ROOT / "docs"
LOG_DIR = ROOT / "resources" / "logs"

BENCHMARK_NOTEBOOK_PATH = BENCHMARK_CACHE_DIR / "regressions.ipynb"
CORRECTED_REG_READY_PARQUET = (
    ROOT / "data" / "clean" / "lapop" / "lapop_brazil_with_pca_indices_regression_ready_corrected.parquet"
)
CORRECTED_REG_READY_CSV = (
    ROOT / "data" / "clean" / "lapop" / "lapop_brazil_with_pca_indices_regression_ready_corrected.csv"
)

BENCHMARK_NOTEBOOK_AUDIT_PATH = INTERIM_DIR / "benchmark_notebook_lapop_audit.csv"
BENCHMARK_COMPARISON_PATH = INTERIM_DIR / "lapop_benchmark_vs_current_comparison.csv"
SAMPLE_COMPARISON_PATH = INTERIM_DIR / "lapop_regression_sample_comparison.csv"
MATCHING_AUDIT_PATH = INTERIM_DIR / "lapop_municipality_matching_audit.csv"

BENCHMARK_NOTES_PATH = DOCS_DIR / "LAPOP_BENCHMARK_NOTEBOOK_NOTES.md"
DEBUG_NOTES_PATH = DOCS_DIR / "LAPOP_TRUST_REPLICATION_DEBUG_NOTES.md"
DEBUG_LOG_PATH = LOG_DIR / "lapop_trust_replication_debug_log.md"

NOTEBOOK_SOURCE_YEARS = [2006, 2008, 2010, 2012, 2014, 2016, 2018, 2021, 2023]
NOTEBOOK_REGRESSION_YEARS = [2006, 2008, 2010, 2012, 2014, 2016, 2018]
NOTEBOOK_YEAR_MAP = {2006: 2006, 2008: 2008, 2010: 2010, 2012: 2012, 2014: 2014, 2016: 2016, 2018: 2018, 2021: 2020, 2023: 2022}

NOTEBOOK_TRUST_TARGETS = {
    "female": (0.085, 0.054),
    "white": (-0.042, 0.053),
    "married": (-0.049, 0.058),
    "low_ed": (0.124, 0.029),
}

DICT_LAPOP_COLS = {
    "Provincia": "state_name",
    "prov": "state_name",
    "prov1t": "state_name",
    "BRAMUNICIPIO": "municipality_name",
    "municipio": "municipality_name",
    "bramunicipio": "municipality_name",
    "municipio1t": "municipality_name",
    "bradistrito": "bairro",
    "fecha": "date",
    "data": "date",
    "q1": "gender",
    "q1tb": "gender",
    "q1tc_r": "gender",
    "q10": "income",
    "q10new": "income",
    "q11": "married",
    "q11n": "married",
    "vs8": "married",
    "q12c": "household_size",
    "q13bra": "household_size",
    "q2": "age",
    "q2y": "born",
    "etid": "white",
    "vs20": "white",
    "ur": "urban",
    "ur1new": "urban",
    "edr": "ed",
    "edre": "ed",
    "vs2": "ed",
    "ocup4a": "working",
    "vs3": "working",
    "vb1": "has_title",
    "gi0": "check_news",
    "gi0n": "check_news",
    "l1": "left_right",
    "l1n": "left_right",
    "pol1": "interest_politics",
    "a4": "policy_priority",
    "b2": "trust_inst",
    "b21": "trust_parties",
    "b21a": "trust_pres",
    "b3": "trust_rights_protected",
    "b47": "trust_elec",
    "b47a": "trust_elec",
    "b4": "trust_proud_elec_sys",
    "b6": "trust_support_elec_sys",
    "b32": "trust_mun",
    "ing4": "dem_best",
    "pn4": "dem_satisfied",
    "eff1": "dem_you_matter",
    "eff2": "dem_knows_pol",
    "countfair1": "count_votes_fair",
    "countfair3": "count_votes_find",
    "vb3n": "who_vote_last",
}

RAW_TO_FINAL = {key.lower(): value for key, value in DICT_LAPOP_COLS.items()}
NAMED_VARS = ["prov", "prov1t", "Provincia", "municipio", "BRAMUNICIPIO", "municipio1t", "q10", "q10new", "wt"]
INDIVIDUAL_VARS = ["data", "fecha", "q1", "q1tb", "q1tc_r", "q11", "q11n", "vs8", "ur", "ur1new", "q2", "q2y", "etid", "vs20", "ed", "edr", "vs2", "edre", "ocup4a", "vs3", "vb1", "pol1", "gi0", "gi0n", "l1", "l1n"]
OUTCOME_VARS = ["b2", "b21", "b21a", "b3", "b32", "b47", "b47a", "b4", "b6", "countfair1", "countfair3", "vb3n", "ing4", "pn4", "eff1", "eff2"]

TRUST_VARS = ["trust_inst", "trust_parties", "trust_pres", "trust_rights_protected", "trust_mun", "trust_elec", "trust_proud_elec_sys", "trust_support_elec_sys"]
DEM_VARS = ["dem_best", "dem_satisfied", "dem_you_matter"]

UNKN_KEYS = ["151500107", "151501303", "15355030", "151501501", "151502202", "355038"]

UF_MAP = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapa",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceara",
    "DF": "Distrito Federal",
    "ES": "Espirito Santo",
    "GO": "Goias",
    "MA": "Maranhao",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Para",
    "PB": "Paraiba",
    "PR": "Parana",
    "PE": "Pernambuco",
    "PI": "Piaui",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondonia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "Sao Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}

SURVEY_FIX_RULES = [
    ("fatima do sul", "mato grosso", "state_name", "mato grosso do sul"),
    ("3550308", "sao paulo", "municipality_name", "sao paulo"),
    ("3515004", "sao paulo", "municipality_name", "embu das artes"),
    ("151504208", "para", "municipality_name", "maraba"),
    ("rio preto eva", "amazonas", "municipality_name", "rio preto da eva"),
    ("senador la roque", "maranhao", "municipality_name", "senador la rocque"),
    ("iguaraci", "pernambuco", "municipality_name", "iguaracy"),
    ("embu", "sao paulo", "municipality_name", "embu das artes"),
    ("moji das cruzes", "sao paulo", "municipality_name", "mogi das cruzes"),
    ("biritibamirim", "sao paulo", "municipality_name", "biritiba mirim"),
    ("moji mirim", "sao paulo", "municipality_name", "mogi mirim"),
    ("ji parana", "rondonia", "municipality_name", "jiparana"),
]

YEAR_2006_NAME_FIXES = {
    "itapolis": "itapolis sp",
    "itaberaba": "itaberaba ba",
    "rio preto": "rio preto mg",
    "maraba": "maraba pa",
    "iguaraci": "iguaracy pe",
    "vigia": "vigia pa",
    "recife": "recife pe",
    "bayeux": "bayeux pb",
    "primavera": "primavera pa",
    "nova cruz": "nova cruz rn",
    "natal": "natal rn",
    "fortaleza": "fortaleza ce",
    "senador la roque ma": "senador la rocque ma",
    "satubinha": "satubinha ma",
}

IBGE_ALIAS_RULES = [
    ("PA", "eldorado dos carajas", "eldorado do carajas"),
    ("RN", "arez", "ares"),
    ("RN", "assu", "acu"),
    ("MG", "sao thome das letras", "sao tome das letras"),
    ("BA", "camaca", "camacan"),
    ("MG", "pingo dagua", "pingodagua"),
    ("MG", "olhos dagua", "olhosdagua"),
    ("PA", "santa isabel do para", "santa izabel do para"),
    ("RO", "alvorada do oeste", "alvorada doeste"),
    ("RN", "boa saude", "januario cicco"),
    ("RO", "espigao do oeste", "espigao doeste"),
    ("SP", "sao luis do paraitinga", "sao luiz do paraitinga"),
    ("MT", "santo antonio do leverger", "santo antonio de leverger"),
    ("SE", "amparo de sao francisco", "amparo do sao francisco"),
    ("RO", "ji parana", "jiparana"),
    ("PE", "iguaracy", "iguaraci"),
    ("RO", "machadinho do oeste", "machadinho doeste"),
    ("CE", "itapaje", "itapage"),
    ("PB", "sao domingos de pombal", "sao domingos"),
    ("RJ", "trajano de moraes", "trajano de morais"),
]


def _ensure_dirs() -> None:
    for path in [
        BENCHMARK_CACHE_DIR,
        INTERIM_DIR,
        CORRECTED_REG_READY_PARQUET.parent,
        DOCS_DIR,
        LOG_DIR,
        (ROOT / "resources" / "figures" / "regressions"),
        (ROOT / "resources" / "lapop" / "figures"),
        (ROOT / "resources" / "lapop" / "regressions" / "trust_interactions"),
        (ROOT / "resources" / "lapop" / "regressions" / "democracy_interactions"),
        (ROOT / "resources" / "tables"),
    ]:
        path.mkdir(parents=True, exist_ok=True)


def remove_punctuation(text: str) -> str:
    return text.translate(str.maketrans("", "", string.punctuation))


def _normalize_text(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return unidecode(remove_punctuation(str(value)).lower().strip())


def _zip_member_for_filename(filename: str) -> str:
    with zipfile.ZipFile(ZIP_PATH) as zf:
        matches = [name for name in zf.namelist() if name.endswith(filename)]
    if not matches:
        raise FileNotFoundError(f"Could not find `{filename}` inside {ZIP_PATH}")
    return sorted(matches, key=len)[0]


def _extract_zip_member(filename: str) -> Path:
    target = BENCHMARK_CACHE_DIR / filename
    if target.exists():
        return target
    member = _zip_member_for_filename(filename)
    with zipfile.ZipFile(ZIP_PATH) as zf:
        with zf.open(member) as src, target.open("wb") as dst:
            dst.write(src.read())
    return target


def _resolve_actual_columns(meta_columns: list[str], candidates: list[str]) -> list[str]:
    lookup = {column.lower(): column for column in meta_columns}
    resolved: list[str] = []
    for candidate in candidates:
        actual = lookup.get(candidate.lower())
        if actual is not None:
            resolved.append(actual)
    return list(dict.fromkeys(resolved))


def _rename_from_raw(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {column: RAW_TO_FINAL.get(column.lower(), column.lower()) for column in df.columns}
    return df.rename(columns=rename_map)


def _read_lapop_wave(year: int) -> pd.DataFrame:
    path = _extract_zip_member(f"brazil_lapop_{year}.dta")
    _, meta = pyreadstat.read_dta(path, metadataonly=True)
    meta_columns = meta.column_names

    named_columns = _resolve_actual_columns(meta_columns, NAMED_VARS)
    numeric_columns = _resolve_actual_columns(meta_columns, INDIVIDUAL_VARS + OUTCOME_VARS)

    named_df, _ = pyreadstat.read_dta(path, usecols=named_columns, apply_value_formats=True)
    numeric_df, _ = pyreadstat.read_dta(path, usecols=numeric_columns, apply_value_formats=False)
    numeric_df.columns = [column.lower() for column in numeric_df.columns]

    df = pd.concat([_rename_from_raw(named_df), _rename_from_raw(numeric_df)], axis=1)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    df = df.loc[df["municipality_name"].notna() & df["state_name"].notna()].copy()
    df["source_file"] = path.name
    df["source_year"] = year
    return df


def _recode_education(year: int, value: object) -> object:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan
    if year == 2021:
        if 0 <= number < 2:
            return "ES"
        if 2 <= number < 3:
            return "HS"
        if 3 <= number < 7:
            return "UNI"
        return np.nan
    if year == 2023:
        if 0 <= number < 3:
            return "ES"
        if 3 <= number < 5:
            return "HS"
        if 5 <= number < 7:
            return "UNI"
        return np.nan
    if 0 <= number < 9:
        return "ES"
    if 9 <= number < 12:
        return "HS"
    if 12 <= number < 18:
        return "UNI"
    return np.nan


def _apply_notebook_recodes(df: pd.DataFrame, year: int) -> pd.DataFrame:
    working = df.copy()
    for column in ["state_name", "municipality_name", "gender", "ed"]:
        if column in working.columns:
            working[column] = working[column].astype(object)
    working["year"] = year
    working["gender"] = working["gender"].map({1: "M", 2: "F", 3: "O"})
    working["female"] = working["gender"].map({"F": 1.0, "M": 0.0, "O": 0.0})
    working["state_name"] = working["state_name"].apply(
        lambda value: _normalize_text(UF_MAP[value]) if value in UF_MAP else _normalize_text(value)
    )
    working["municipality_name"] = (
        working["municipality_name"]
        .apply(_normalize_text)
        .str.replace("ce cap", "", regex=False)
        .str.replace("rn cap", "", regex=False)
        .str.replace("pe cap", "", regex=False)
        .str.replace("rn fx4", "", regex=False)
        .str.replace("pb fx5", "", regex=False)
        .str.replace("sp fx4", "", regex=False)
        .str.strip()
    )
    working["urban"] = np.where(working["urban"].eq(1), 1.0, np.where(working["urban"].notna(), 0.0, np.nan))
    working["white"] = np.where(working["white"].eq(1), 1.0, np.where(working["white"].notna(), 0.0, np.nan))
    working["married"] = np.where(working["married"].eq(2), 1.0, np.where(working["married"].notna(), 0.0, np.nan))
    working["working"] = np.where(working["working"].eq(2), 1.0, np.where(working["working"].notna(), 0.0, np.nan))
    if "dem_satisfied" in working.columns:
        working["dem_satisfied"] = np.where(working["dem_satisfied"].notna(), 5 - working["dem_satisfied"], np.nan)
    working["ed_years"] = pd.to_numeric(working["ed"], errors="coerce")
    working["ed"] = working["ed"].apply(lambda value: _recode_education(year, value))

    for municipality_name, state_name, target_column, replacement in SURVEY_FIX_RULES:
        mask = working["municipality_name"].eq(municipality_name) & working["state_name"].eq(state_name)
        working.loc[mask, target_column] = replacement

    if year == 2006:
        for original, replacement in YEAR_2006_NAME_FIXES.items():
            working.loc[working["municipality_name"].eq(original), "municipality_name"] = replacement

    if "born" in working.columns:
        born = pd.to_numeric(working["born"], errors="coerce")
        working["age"] = year - born

    working["age"] = pd.to_numeric(working["age"], errors="coerce")
    working = working.loc[~working["municipality_name"].isin(UNKN_KEYS)].copy()

    if year == 2008 and "wt" in working.columns:
        working["wt"] = 1

    if year == 2006:
        working["state"] = working["municipality_name"].apply(lambda value: value.split(" ")[-1].upper() if value else "")
        working["municipality_name"] = working["municipality_name"].apply(
            lambda value: " ".join(value.split(" ")[:-1]).strip() if value else value
        )
    else:
        working["state"] = working["state_name"].map(STATE_NAME_TO_ABBREV)

    return working


def _build_ibge_lookup() -> pd.DataFrame:
    ibge = pd.read_csv(IBGE_MUNICIPALITIES_PATH, dtype={"municipality_id": str}).copy()
    ibge["municipality_id"] = ibge["municipality_id"].astype(str).str.zfill(7)
    state_reverse = {abbrev: _normalize_text(name) for abbrev, name in UF_MAP.items()}
    ibge["state_name"] = ibge["state"].map(state_reverse)

    extra_rows: list[pd.Series] = []
    for state, canonical_name, alias_name in IBGE_ALIAS_RULES:
        match = (ibge["state"] == state) & (ibge["municipality_name"] == canonical_name)
        if match.any():
            alias_row = ibge.loc[match].iloc[0].copy()
            alias_row["municipality_name"] = alias_name
            extra_rows.append(alias_row)

    if extra_rows:
        ibge = pd.concat([ibge, pd.DataFrame(extra_rows)], ignore_index=True)
    ibge = ibge.drop_duplicates(subset=["state", "state_name", "municipality_name", "municipality_id"]).reset_index(drop=True)
    return ibge[["municipality_id", "municipality_name", "state", "state_name"]]


def _merge_wave_to_municipality_ids(df_wave: pd.DataFrame, ibge_lookup: pd.DataFrame) -> pd.DataFrame:
    if int(df_wave["year"].iloc[0]) == 2006:
        merged = df_wave.merge(
            ibge_lookup[["municipality_id", "municipality_name", "state"]],
            on=["state", "municipality_name"],
            how="left",
            validate="m:1",
        )
    else:
        merged = df_wave.merge(
            ibge_lookup[["municipality_id", "municipality_name", "state", "state_name"]],
            on=["state_name", "municipality_name"],
            how="left",
            validate="m:1",
            suffixes=("", "_ibge"),
        )
        if "state_ibge" in merged.columns:
            merged["state"] = merged["state_ibge"].combine_first(merged["state"])
            merged = merged.drop(columns=["state_ibge"])
    merged["matched_to_municipality"] = merged["municipality_id"].notna()
    return merged


def _build_lapop_notebook_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    ibge_lookup = _build_ibge_lookup()
    frames: list[pd.DataFrame] = []
    matching_rows: list[dict[str, object]] = []

    for year in NOTEBOOK_SOURCE_YEARS:
        wave = _apply_notebook_recodes(_read_lapop_wave(year), year)
        merged = _merge_wave_to_municipality_ids(wave, ibge_lookup)
        matched_n = int(merged["matched_to_municipality"].sum())
        unmatched_n = int((~merged["matched_to_municipality"]).sum())
        matching_rows.append(
            {
                "source_year": year,
                "benchmark_year": NOTEBOOK_YEAR_MAP[year],
                "rows_total": int(len(merged)),
                "rows_matched": matched_n,
                "rows_unmatched": unmatched_n,
                "match_rate": matched_n / len(merged) if len(merged) else np.nan,
            }
        )
        frames.append(merged)

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.loc[panel["municipality_id"].notna()].copy()
    panel["municipality_id"] = panel["municipality_id"].astype(float).astype(int).astype(str).str.zfill(7)
    panel["survey_year_source"] = panel["year"]
    panel["year"] = panel["year"].map(NOTEBOOK_YEAR_MAP).astype(int)
    panel["survey_year"] = panel["survey_year_source"]
    return panel.reset_index(drop=True), pd.DataFrame(matching_rows)


def _merge_treatment_and_covariates(panel: pd.DataFrame) -> pd.DataFrame:
    treatment = pd.read_parquet(TREATMENT_PATH)[["municipality_id", "year_first_treat"]].copy()
    treatment["municipality_id"] = treatment["municipality_id"].astype(str).str.zfill(7)
    covariates = build_municipal_covariates(sorted({2006, 2008, 2010, 2012, 2014, 2016, 2018})).copy()
    covariates["municipality_id"] = covariates["municipality_id"].astype(str).str.zfill(7)

    merged = panel.merge(treatment, on="municipality_id", how="left", validate="m:1")
    merged["year_first_treat"] = merged["year_first_treat"].fillna(9999).astype(int)
    merged["treatment_year"] = merged["year_first_treat"]
    merged["treatment_dist"] = np.where(
        merged["treatment_year"].ne(9999),
        merged["year"] - merged["treatment_year"],
        -9999,
    )
    merged["treatment_dummy"] = np.where(merged["treatment_dist"] >= 0, 1, 0).astype(int)
    merged["is_hybrid"] = 0

    merged = merged.merge(
        covariates[["municipality_id", "year", "gdp_pc", "total_pop"]],
        on=["municipality_id", "year"],
        how="left",
        validate="m:1",
    )
    merged["log_gdp_pc"] = np.log(merged["gdp_pc"] + 0.1)
    merged["log_total_pop"] = np.log(merged["total_pop"] + 0.1)
    merged["college"] = np.where(merged["ed"].eq("UNI"), 1.0, np.where(merged["ed"].notna(), 0.0, np.nan))
    merged["low_ed"] = np.where(merged["ed"].eq("ES"), 1.0, np.where(merged["ed"].notna(), 0.0, np.nan))
    merged["education_category"] = merged["ed"].map({"ES": "less_than_secondary", "HS": "secondary_or_more", "UNI": "tertiary"})
    return merged


def _pca_zscore(values: pd.Series) -> pd.Series:
    centered = values - float(values.mean())
    scale = float(values.std(ddof=0))
    if scale == 0 or not np.isfinite(scale):
        raise ValueError("Cannot z-score a constant or invalid series.")
    return centered / scale


def _build_notebook_indices(panel: pd.DataFrame) -> pd.DataFrame:
    output = panel.copy()

    trust_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("pca", PCA(n_components=2, random_state=0)),
        ]
    )
    trust_pcs = trust_pipe.fit_transform(output[TRUST_VARS])
    trust_pc1 = pd.Series(trust_pcs[:, 0], index=output.index, name="trust_pc1")
    output["z_score_pca1_trust"] = _pca_zscore(trust_pc1)
    output["trust_index_std"] = output["z_score_pca1_trust"]

    dem_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("pca", PCA(n_components=2, random_state=0)),
        ]
    )
    dem_pcs = dem_pipe.fit_transform(output[DEM_VARS])
    dem_df = pd.DataFrame(dem_pcs, index=output.index, columns=["PC1", "PC2"])
    dem_pc1 = pd.Series(dem_pcs[:, 0], index=output.index, name="democracy_pc1")
    dem_combo = (0.411 * dem_df["PC1"]) + (0.303 * dem_df["PC2"])
    output["z_score_pca1_dem"] = _pca_zscore(dem_pc1)
    output["democracy_index_std"] = output["z_score_pca1_dem"]
    output["democracy_index_legacy_combo_std"] = _pca_zscore(dem_combo)
    output["benchmark_democracy_combo_formula"] = "0.411 * PC1 + 0.303 * PC2"

    return output


def _load_current_reference() -> pd.DataFrame:
    if REG_READY_PARQUET.exists():
        return pd.read_parquet(REG_READY_PARQUET)
    return pd.DataFrame()


def _build_sample_comparison(current_df: pd.DataFrame, benchmark_df: pd.DataFrame, matching_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if not current_df.empty:
        current = current_df.copy()
        if "survey_year" in current.columns:
            for year, count in current.groupby("survey_year").size().sort_index().items():
                rows.append(
                    {
                        "dataset": "current_repo_regression_ready",
                        "sample_type": "all_rows",
                        "year": int(year),
                        "n_rows": int(count),
                    }
                )
    for year, count in benchmark_df.groupby("survey_year_source").size().sort_index().items():
        rows.append({"dataset": "benchmark_notebook_style", "sample_type": "all_rows", "year": int(year), "n_rows": int(count)})
    for year, count in benchmark_df.loc[benchmark_df["year"] <= 2018].groupby("year").size().sort_index().items():
        rows.append(
            {
                "dataset": "benchmark_notebook_style",
                "sample_type": "regression_sample_year<=2018",
                "year": int(year),
                "n_rows": int(count),
            }
        )
    for row in matching_summary.itertuples(index=False):
        rows.append(
            {
                "dataset": "benchmark_notebook_style",
                "sample_type": "raw_matching",
                "year": int(row.source_year),
                "n_rows": int(row.rows_total),
                "matched_rows": int(row.rows_matched),
                "unmatched_rows": int(row.rows_unmatched),
                "match_rate": float(row.match_rate),
            }
        )
    comparison = pd.DataFrame(rows)
    comparison.to_csv(SAMPLE_COMPARISON_PATH, index=False)
    return comparison


def _build_notebook_audit(current_df: pd.DataFrame, benchmark_df: pd.DataFrame, matching_summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    current_years = []
    if not current_df.empty and "survey_year" in current_df.columns:
        current_years = sorted(int(year) for year in pd.Series(current_df["survey_year"]).dropna().unique())
    benchmark_years = sorted(int(year) for year in benchmark_df["year"].dropna().unique())

    audit_rows = [
        {
            "component": "lapop_raw_source",
            "notebook_path": "regressions.ipynb cell 143",
            "notebook_logic": "Builds the LAPOP panel directly from raw Brazil DTA waves 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2021, 2023 stored in the older project.",
            "current_repo_logic": "Used the newer clean comparable LAPOP core as the starting point, which begins in 2008 and already bakes in later harmonization choices.",
            "same_or_different": "different",
            "likely_effect": "Changes the estimation sample and the PCA universe because the 2006 wave is absent from the newer clean core.",
            "fix_needed": True,
        },
        {
            "component": "sample_years",
            "notebook_path": "regressions.ipynb cells 143, 146, 147",
            "notebook_logic": f"Constructs a full panel with source years {NOTEBOOK_SOURCE_YEARS} and then runs the interactions on benchmark years {NOTEBOOK_REGRESSION_YEARS} via `year <= 2018`.",
            "current_repo_logic": f"Current regression-ready file used survey years {current_years}.",
            "same_or_different": "different",
            "likely_effect": "Missing 2006 in the current cleaned core was a first-order source of divergence.",
            "fix_needed": True,
        },
        {
            "component": "municipality_matching",
            "notebook_path": "regressions.ipynb cells 143, 160, 161",
            "notebook_logic": "Applies manual municipality-name and state corrections before merging to IBGE municipality IDs, including 2006 suffix disambiguations.",
            "current_repo_logic": "Current repo already had most of the active harmonizations, but it did not rebuild the matching from the older raw notebook source files.",
            "same_or_different": "mostly_different_upstream",
            "likely_effect": "Matching rules were not the dominant gap, but the benchmark path needs the raw-notebook merge to be faithful.",
            "fix_needed": True,
        },
        {
            "component": "trust_index",
            "notebook_path": "regressions.ipynb cell 144",
            "notebook_logic": "Builds `z_score_pca1_trust` from the first principal component of the eight trust items on the full matched LAPOP panel after median imputation and standardization.",
            "current_repo_logic": "Used `trust_index_std` from the newer clean core, which was constructed on a smaller comparable sample that excludes 2006 and later notebook-only waves.",
            "same_or_different": "different",
            "likely_effect": "Changes the trust outcome scaling and the coefficient magnitudes slightly.",
            "fix_needed": True,
        },
        {
            "component": "democracy_index",
            "notebook_path": "regressions.ipynb cell 145",
            "notebook_logic": "The notebook contains a legacy weighted PC1/PC2 democracy combo, but the paper-consistent democracy index is the standardized first principal component of the three-item block.",
            "current_repo_logic": "The benchmark-linked pipeline had been overwriting `z_score_pca1_dem` with that legacy combo instead of keeping PCA1 as the main democracy outcome.",
            "same_or_different": "different",
            "likely_effect": "This created an inconsistency between the paper text and the stored democracy regressions and figures.",
            "fix_needed": True,
        },
        {
            "component": "treatment_dummy",
            "notebook_path": "regressions.ipynb cells 143, 161",
            "notebook_logic": "Uses municipality treatment timing and sets treatment_dummy = 1 when benchmark year >= treatment_year.",
            "current_repo_logic": "Uses the cleaned municipality first-treatment file and the same basic treated-by-year rule.",
            "same_or_different": "mostly_same",
            "likely_effect": "Treatment timing itself does not appear to be the main source of the mismatch.",
            "fix_needed": False,
        },
        {
            "component": "controls",
            "notebook_path": "regressions.ipynb cells 146, 147",
            "notebook_logic": "Includes C(low_ed), C(female), C(white), C(married), C(working), age, log_gdp_pc, log_total_pop.",
            "current_repo_logic": "Current replicated script eventually aligned to the same set, but the upstream file did not reproduce the benchmark low_ed and democracy definitions exactly.",
            "same_or_different": "partly_different",
            "likely_effect": "Control definitions, especially low education, mattered once the benchmark raw panel was restored.",
            "fix_needed": True,
        },
        {
            "component": "fixed_effects_and_vcov",
            "notebook_path": "regressions.ipynb cells 146, 147",
            "notebook_logic": "Uses municipality and benchmark-year fixed effects with CRV1 clustering on municipality_id + year.",
            "current_repo_logic": "Current replicated path moved toward this, but earlier runs used the wrong year variable and a statsmodels fallback.",
            "same_or_different": "different",
            "likely_effect": "Changing FE and vcov mattered, but less than restoring the benchmark sample and outcomes.",
            "fix_needed": True,
        },
        {
            "component": "plotting_logic",
            "notebook_path": "regressions.ipynb cells 146, 147",
            "notebook_logic": "Plots the baseline treatment effect, the combined effect for the interacted group, black CI lines, hatched Yes bars, brackets, and the interaction difference above each pair.",
            "current_repo_logic": "Current repo used a cleaner but not benchmark-faithful plotting layout with different spacing, legend placement, and bar styling.",
            "same_or_different": "different",
            "likely_effect": "Visual mismatch was obvious even when coefficients were close.",
            "fix_needed": True,
        },
    ]
    audit_df = pd.DataFrame(audit_rows)
    audit_df.to_csv(BENCHMARK_NOTEBOOK_AUDIT_PATH, index=False)

    comparison_rows = [
        {
            "component": "current_vs_benchmark_years",
            "current_repo_logic": ", ".join(map(str, current_years)),
            "benchmark_logic": ", ".join(map(str, benchmark_years)),
            "same_or_different": "different",
            "likely_effect": "Current repo dropped the 2006 benchmark wave and used different field-year conventions before correction.",
        },
        {
            "component": "benchmark_matched_rows_total",
            "current_repo_logic": f"{int(len(current_df)) if not current_df.empty else 0}",
            "benchmark_logic": f"{int(len(benchmark_df))}",
            "same_or_different": "different",
            "likely_effect": "The benchmark panel is larger because it rebuilds from the raw notebook waves and keeps the 2006 matched respondents.",
        },
        {
            "component": "benchmark_match_rate_by_source_year",
            "current_repo_logic": "Current repo matching was performed on the newer clean core rather than the notebook raw waves.",
            "benchmark_logic": "; ".join(
                f"{int(row.source_year)}: {row.rows_matched}/{row.rows_total} ({row.match_rate:.3f})"
                for row in matching_summary.itertuples(index=False)
            ),
            "same_or_different": "different",
            "likely_effect": "Confirms that the benchmark data build is a distinct upstream object from the current clean comparable core.",
        },
        {
            "component": "trust_standardization_universe",
            "current_repo_logic": "2008-2019 clean comparable core only.",
            "benchmark_logic": "Full matched notebook panel after source-year mapping, including 2006 and the later 2020/2022 waves.",
            "same_or_different": "different",
            "likely_effect": "Changes trust score scaling and the downstream interaction coefficients.",
        },
        {
            "component": "democracy_standardization_universe",
            "current_repo_logic": "PCA1 in the paper-consistent pipeline, with a separate legacy comparison column.",
            "benchmark_logic": "Corrected benchmark build now stores `z_score_pca1_dem` as the standardized first democracy principal component and retains the legacy weighted combo separately.",
            "same_or_different": "different",
            "likely_effect": "Clarifies that the main democracy results use the same PCA1 z-score logic as the institutional-trust outcome.",
        },
    ]
    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df.to_csv(BENCHMARK_COMPARISON_PATH, index=False)
    return audit_df, comparison_df


def _plain_table(df: pd.DataFrame) -> str:
    columns = [str(column) for column in df.columns]
    header = " | ".join(columns)
    divider = " | ".join(["---"] * len(columns))
    safe_df = df.astype(object).where(pd.notna(df), "")
    rows = [" | ".join(str(value) for value in row) for row in safe_df.values.tolist()]
    return "\n".join([header, divider, *rows])


def _write_notes_and_log(benchmark_df: pd.DataFrame, matching_summary: pd.DataFrame) -> None:
    benchmark_years = sorted(int(year) for year in benchmark_df["year"].dropna().unique())
    source_years = sorted(int(year) for year in benchmark_df["survey_year_source"].dropna().unique())
    matched_total = int(len(benchmark_df))
    notebook_text = f"""# LAPOP Benchmark Notebook Notes

## Benchmark Notebook Source

- Zip file inspected: `{ZIP_PATH.name}`
- Notebook inspected: `Biometric-Voting/regressions.ipynb`
- Benchmark figure cells: 146 (`lapop_trust_by_cat.pgf`) and 147 (`lapop_dem_by_cat.pgf`)
- PCA cells: 144 (trust) and 145 (democracy)
- Raw LAPOP build cell: 143
- Municipality and treatment setup cells: 160 and 161

## What The Benchmark Notebook Does

- Reads the raw Brazil LAPOP DTA files for 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2021, and 2023.
- Harmonizes municipality and state strings inside the notebook rather than starting from the newer clean comparable core.
- Remaps source years to benchmark years `{NOTEBOOK_YEAR_MAP}` so that 2021 becomes 2020 and 2023 becomes 2022.
- Builds `z_score_pca1_trust` from the first principal component of the eight trust variables.
- Builds `z_score_pca1_dem` from the first principal component of the three democracy variables in the corrected benchmark build, while retaining the legacy weighted combination `0.411 * PC1 + 0.303 * PC2` only as a comparison variable.
- Runs the interaction regressions on the sample `year <= 2018`.
- Uses municipality and year fixed effects plus CRV1 clustering on `municipality_id + year`.
- Plots the base treatment effect, the combined treatment effect, and the interaction difference using hatched Yes bars, black CIs, black outlines, and brackets.

## Main Upstream Differences Relative To The Current Repo

- The benchmark notebook includes the 2006 wave, while the newer clean comparable core begins in 2008.
- The trust and democracy indices are standardized on the full matched benchmark panel, not only on the later clean comparable core.
- The archived notebook contains a legacy weighted democracy combo, but the corrected repository pipeline uses the standardized first democracy component as the main outcome and keeps the legacy combo only for comparison.
- The benchmark plot styling is more specific than the current repo's generic interaction plotter.

## Benchmark Panel Summary

- Source years present: {source_years}
- Benchmark years present after remapping: {benchmark_years}
- Matched respondents retained after municipality merge: {matched_total:,}
- Regression sample years: {NOTEBOOK_REGRESSION_YEARS}

## Municipality Matching Summary

{_plain_table(matching_summary)}

## Outputs Updated

- `{CORRECTED_REG_READY_PARQUET.relative_to(ROOT)}`
- `{CORRECTED_REG_READY_CSV.relative_to(ROOT)}`
- `{BENCHMARK_NOTEBOOK_AUDIT_PATH.relative_to(ROOT)}`
- `{BENCHMARK_COMPARISON_PATH.relative_to(ROOT)}`
- `{SAMPLE_COMPARISON_PATH.relative_to(ROOT)}`
"""
    BENCHMARK_NOTES_PATH.write_text(notebook_text + "\n", encoding="utf-8")

    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    log_text = "\n".join(
        [
            "# LAPOP Trust Replication Debug Log",
            "",
            f"- Timestamp: `{timestamp}`",
            f"- Zip source: `{ZIP_PATH.relative_to(ROOT)}`",
            f"- Benchmark notebook: `{BENCHMARK_NOTEBOOK_PATH.relative_to(ROOT)}`",
            f"- Corrected regression-ready file: `{CORRECTED_REG_READY_PARQUET.relative_to(ROOT)}`",
            f"- Source years in benchmark build: `{source_years}`",
            f"- Benchmark years in benchmark build: `{benchmark_years}`",
            f"- Matched respondents retained: `{matched_total}`",
            f"- Matching audit: `{MATCHING_AUDIT_PATH.relative_to(ROOT)}`",
            f"- Notebook audit: `{BENCHMARK_NOTEBOOK_AUDIT_PATH.relative_to(ROOT)}`",
            f"- Comparison audit: `{BENCHMARK_COMPARISON_PATH.relative_to(ROOT)}`",
            "",
            "This log is updated by the benchmark notebook rebuild and then extended by the replicated regression runner.",
        ]
    )
    DEBUG_LOG_PATH.write_text(log_text + "\n", encoding="utf-8")


def build_benchmark_dataset(save_outputs: bool = True) -> pd.DataFrame:
    _ensure_dirs()
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"Missing benchmark zip file at {ZIP_PATH}")

    _extract_zip_member("regressions.ipynb")
    benchmark_panel, matching_summary = _build_lapop_notebook_panel()
    benchmark_panel = _merge_treatment_and_covariates(benchmark_panel)
    benchmark_panel = _build_notebook_indices(benchmark_panel)

    benchmark_panel["used_in_notebook_replication_sample"] = benchmark_panel["year"].le(2018)
    benchmark_panel["benchmark_source"] = "Biometric-Voting/regressions.ipynb"
    benchmark_panel["benchmark_notebook_logic"] = True

    current_reference = _load_current_reference()
    _build_sample_comparison(current_reference, benchmark_panel, matching_summary)
    _build_notebook_audit(current_reference, benchmark_panel, matching_summary)
    matching_summary.to_csv(MATCHING_AUDIT_PATH, index=False)

    if save_outputs:
        object_columns = benchmark_panel.select_dtypes(include=["object"]).columns
        for column in object_columns:
            benchmark_panel[column] = benchmark_panel[column].astype("string")
        benchmark_panel.to_parquet(CORRECTED_REG_READY_PARQUET, index=False)
        benchmark_panel.to_csv(CORRECTED_REG_READY_CSV, index=False, quoting=csv.QUOTE_MINIMAL)

    _write_notes_and_log(benchmark_panel, matching_summary)

    return benchmark_panel


def main() -> None:
    build_benchmark_dataset(save_outputs=True)
    df = pd.read_parquet(CORRECTED_REG_READY_PARQUET)
    print(f"Saved benchmark-corrected LAPOP regression-ready file to {CORRECTED_REG_READY_PARQUET.relative_to(ROOT)}")
    print(f"Rows: {len(df):,}")
    print(f"Benchmark years: {sorted(df['year'].dropna().unique().tolist())}")


if __name__ == "__main__":
    main()
