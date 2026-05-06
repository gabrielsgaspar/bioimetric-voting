from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.cleaning.parse_tse_eleitorado import canonicalize_text, map_education, open_zip_csv
from src.tse_eleitorado_common import (
    IBGE_CROSSWALK_PATH,
    RAW_DIR,
    normalize_name,
    normalize_state,
)


ROOT = Path(__file__).resolve().parents[2]

BVR_PANEL_PARQUET = ROOT / "data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.parquet"
BVR_PANEL_CSV = ROOT / "data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.csv"
IBGE_NAME_PATH = ROOT / "data" / "clean" / "ibge" / "ibge_municipalities.csv"

CLEAN_DIR = ROOT / "data/clean/tse_eleitorado"
INTERIM_DIR = ROOT / "data/interim/tse"
REGRESSION_DIR = ROOT / "resources/regressions"
RESOURCE_DIR = REGRESSION_DIR / "did_cs_age_education"
CONFIG_DIR = RESOURCE_DIR / "configs"
LOG_DIR = ROOT / "resources/logs"
DOCS_DIR = ROOT / "docs"

LONG_CSV = CLEAN_DIR / "eleitorado_age_education_bands_2008_2018.csv"
LONG_PARQUET = CLEAN_DIR / "eleitorado_age_education_bands_2008_2018.parquet"
SAMPLE_CSV = INTERIM_DIR / "tse_age_education_bands_did_cs_sample.csv"
SAMPLE_PARQUET = INTERIM_DIR / "tse_age_education_bands_did_cs_sample.parquet"
RUNNER = ROOT / "scripts/run_did_estimator.sh"
NOTES_PATH = DOCS_DIR / "TSE_ELEITORADO_AGE_EDUCATION_DID_NOTES.md"
LOG_PATH = LOG_DIR / "tse_age_education_did_cs_log.md"

SOURCE_YEARS = [2008, 2010, 2012, 2014, 2016, 2018]
NEVER_TREATED_VALUE = 9999
SEED = 20260427

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

# The raw TSE files expose five-year age bins, not exact ages. Whole bins are
# assigned by midpoint to approximate the requested bands without splitting cells.
AGE_CODE_TO_BAND = {
    "1600": "age_16_30",
    "1700": "age_16_30",
    "1800": "age_16_30",
    "1900": "age_16_30",
    "2000": "age_16_30",
    "2124": "age_16_30",
    "2529": "age_16_30",
    "3034": "age_31_45",
    "3539": "age_31_45",
    "4044": "age_31_45",
    "4549": "age_46_60",
    "5054": "age_46_60",
    "5559": "age_46_60",
    "6064": "age_60_plus",
    "6569": "age_60_plus",
    "7074": "age_60_plus",
    "7579": "age_60_plus",
    "8084": "age_60_plus",
    "8589": "age_60_plus",
    "9094": "age_60_plus",
    "9599": "age_60_plus",
    "9999": "age_60_plus",
}
AGE_BANDS = ["age_16_30", "age_31_45", "age_46_60", "age_60_plus"]
RAW_AGE_LABELS = {
    "1600": "16 anos",
    "1700": "17 anos",
    "1800": "18 anos",
    "1900": "19 anos",
    "2000": "20 anos",
    "2124": "21 a 24 anos",
    "2529": "25 a 29 anos",
    "3034": "30 a 34 anos",
    "3539": "35 a 39 anos",
    "4044": "40 a 44 anos",
    "4549": "45 a 49 anos",
    "5054": "50 a 54 anos",
    "5559": "55 a 59 anos",
    "6064": "60 a 64 anos",
    "6569": "65 a 69 anos",
    "7074": "70 a 74 anos",
    "7579": "75 a 79 anos",
    "8084": "80 a 84 anos",
    "8589": "85 a 89 anos",
    "9094": "90 a 94 anos",
    "9599": "95 a 99 anos",
    "9999": "100 anos ou mais",
}

OUTCOMES = (
    [f"log_num_voters_{band}" for band in AGE_BANDS]
    + [f"log_num_voters_high_ed_{band}" for band in AGE_BANDS]
    + [f"log_num_voters_low_ed_{band}" for band in AGE_BANDS]
)


def ensure_directories() -> None:
    for path in [CLEAN_DIR, INTERIM_DIR, RESOURCE_DIR, CONFIG_DIR, LOG_DIR, DOCS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def outcome_output_dir(outcome: str) -> Path:
    return REGRESSION_DIR / f"did_cs_{outcome}"


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
    return digits.zfill(width) if width else digits


def education_group(education: str) -> str:
    if education in LOW_ED_CATEGORIES:
        return "low_ed"
    if education in HIGH_ED_CATEGORIES:
        return "high_ed"
    return "unknown_ed"


def load_crosswalk() -> pd.DataFrame:
    crosswalk = pd.read_csv(ROOT / IBGE_CROSSWALK_PATH, dtype=str)
    crosswalk["year"] = pd.to_numeric(crosswalk["year"], errors="coerce").astype("Int64")
    crosswalk["state"] = crosswalk["state"].astype(str).str.upper().str.strip()
    crosswalk["municipality_id"] = crosswalk["municipality_id"].map(lambda x: normalize_code(x, width=7))
    crosswalk["tse_municipality_id"] = crosswalk["tse_municipality_id"].map(normalize_code)
    return crosswalk[["year", "state", "tse_municipality_id", "municipality_id"]].drop_duplicates()


def load_ibge_names() -> pd.DataFrame:
    if not IBGE_NAME_PATH.exists():
        return pd.DataFrame(columns=["municipality_id", "matched_name_crosswalk", "state", "_norm_name"])
    ibge = pd.read_csv(IBGE_NAME_PATH, dtype=str)
    ibge["municipality_id"] = ibge["municipality_id"].map(lambda x: normalize_code(x, width=7))
    ibge["state"] = ibge["state"].astype(str).str.upper().str.strip()
    ibge = ibge.rename(columns={"municipality_name": "matched_name_crosswalk"})
    ibge["_norm_name"] = ibge["matched_name_crosswalk"].map(normalize_name)
    return ibge[["municipality_id", "matched_name_crosswalk", "state", "_norm_name"]]


def parse_year(year: int) -> pd.DataFrame:
    zip_path = RAW_DIR / str(year) / f"perfil_eleitorado_{year}.zip"
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    usecols = [
        "ANO_ELEICAO",
        "SG_UF",
        "CD_MUNICIPIO",
        "NM_MUNICIPIO",
        "DS_GRAU_ESCOLARIDADE",
        "CD_FAIXA_ETARIA",
        "DS_FAIXA_ETARIA",
        "QT_ELEITORES_PERFIL",
    ]
    chunks: list[pd.DataFrame] = []
    archive: zipfile.ZipFile | None = None
    try:
        archive, member = open_zip_csv(zip_path)
        with archive.open(member) as handle:
            reader = pd.read_csv(
                handle,
                sep=";",
                encoding="latin1",
                usecols=usecols,
                dtype=str,
                chunksize=300_000,
            )
            for chunk in reader:
                chunk = chunk.rename(
                    columns={
                        "ANO_ELEICAO": "year",
                        "SG_UF": "state",
                        "CD_MUNICIPIO": "tse_municipality_id",
                        "NM_MUNICIPIO": "municipality_name_raw",
                        "DS_GRAU_ESCOLARIDADE": "education_raw",
                        "CD_FAIXA_ETARIA": "age_code",
                        "DS_FAIXA_ETARIA": "age_raw",
                        "QT_ELEITORES_PERFIL": "num_voters",
                    }
                )
                chunk["year"] = pd.to_numeric(chunk["year"], errors="coerce").astype("Int64")
                chunk["state"] = chunk["state"].map(normalize_state)
                chunk["tse_municipality_id"] = chunk["tse_municipality_id"].map(normalize_code)
                chunk["municipality_name_raw"] = chunk["municipality_name_raw"].map(canonicalize_text)
                chunk["municipality_name"] = chunk["municipality_name_raw"].map(normalize_name)
                chunk["education_raw"] = chunk["education_raw"].map(canonicalize_text)
                chunk["education"] = chunk["education_raw"].map(map_education)
                chunk["education_group"] = chunk["education"].map(education_group)
                chunk["age_code"] = chunk["age_code"].map(normalize_code)
                chunk["age_raw"] = chunk["age_raw"].map(canonicalize_text)
                chunk["age_band"] = chunk["age_code"].map(AGE_CODE_TO_BAND)
                chunk["num_voters"] = pd.to_numeric(chunk["num_voters"], errors="coerce").fillna(0).astype("int64")
                chunk = chunk[chunk["age_band"].notna()].copy()

                grouped = (
                    chunk.groupby(
                        [
                            "year",
                            "state",
                            "tse_municipality_id",
                            "municipality_name_raw",
                            "municipality_name",
                            "education_group",
                            "age_band",
                        ],
                        as_index=False,
                        dropna=False,
                    )["num_voters"]
                    .sum()
                )
                chunks.append(grouped)
    finally:
        if archive is not None:
            archive.close()

    if not chunks:
        return pd.DataFrame()

    return (
        pd.concat(chunks, ignore_index=True)
        .groupby(
            [
                "year",
                "state",
                "tse_municipality_id",
                "municipality_name_raw",
                "municipality_name",
                "education_group",
                "age_band",
            ],
            as_index=False,
            dropna=False,
        )["num_voters"]
        .sum()
    )


def attach_municipality_ids(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    crosswalk = load_crosswalk()
    ibge_names = load_ibge_names()

    merged = df.merge(
        crosswalk,
        how="left",
        on=["year", "state", "tse_municipality_id"],
        validate="many_to_one",
    )
    merged["matched_via_direct_code"] = merged["municipality_id"].notna() & merged["municipality_id"].ne("")

    unmatched_mask = merged["municipality_id"].isna() | merged["municipality_id"].eq("")
    if unmatched_mask.any() and not ibge_names.empty:
        fallback_keys = (
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
        fallback = fallback_keys[
            ["year", "state", "tse_municipality_id", "municipality_id", "matched_name_crosswalk"]
        ]
        merged = merged.merge(
            fallback,
            how="left",
            on=["year", "state", "tse_municipality_id"],
            suffixes=("", "_fallback"),
        )
        merged["municipality_id"] = merged["municipality_id"].fillna(merged["municipality_id_fallback"])
        merged = merged.drop(columns=[c for c in merged.columns if c.endswith("_fallback")], errors="ignore")

    merged = merged.merge(ibge_names.drop(columns=["_norm_name"], errors="ignore"), how="left", on=["municipality_id", "state"])
    if "matched_name_crosswalk_x" in merged.columns or "matched_name_crosswalk_y" in merged.columns:
        left = merged.get("matched_name_crosswalk_x", pd.Series(index=merged.index, dtype="object"))
        right = merged.get("matched_name_crosswalk_y", pd.Series(index=merged.index, dtype="object"))
        merged["matched_name_crosswalk"] = left.fillna(right)
        merged = merged.drop(columns=["matched_name_crosswalk_x", "matched_name_crosswalk_y"], errors="ignore")

    merged["match_method"] = "unmatched"
    merged.loc[merged["matched_via_direct_code"], "match_method"] = "direct_code_year_state"
    merged.loc[
        merged["municipality_id"].notna() & merged["municipality_id"].ne("") & ~merged["matched_via_direct_code"],
        "match_method",
    ] = "exact_state_name_fallback"

    review = (
        merged[
            [
                "year",
                "state",
                "tse_municipality_id",
                "municipality_name_raw",
                "municipality_name",
                "municipality_id",
                "matched_name_crosswalk",
                "match_method",
            ]
        ]
        .drop_duplicates()
        .rename(columns={"municipality_id": "matched_municipality_id"})
        .sort_values(["year", "state", "municipality_name", "tse_municipality_id"])
        .reset_index(drop=True)
    )

    merged = merged[merged["municipality_id"].notna() & merged["municipality_id"].ne("")].copy()
    merged["municipality_id"] = merged["municipality_id"].map(lambda x: normalize_code(x, width=7))
    merged["municipality_name"] = merged["matched_name_crosswalk"].fillna(merged["municipality_name"]).map(normalize_name)
    return merged, review


def build_long_panel() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parsed = pd.concat([parse_year(year) for year in SOURCE_YEARS], ignore_index=True)
    harmonized, review = attach_municipality_ids(parsed)

    long_panel = (
        harmonized.groupby(
            ["year", "municipality_id", "municipality_name", "state", "age_band", "education_group"],
            as_index=False,
            dropna=False,
        )["num_voters"]
        .sum()
        .sort_values(["year", "state", "municipality_name", "age_band", "education_group"])
        .reset_index(drop=True)
    )

    raw_age_mapping = pd.DataFrame(
        [
            {
                "raw_age_code": code,
                "raw_age_label": RAW_AGE_LABELS[code],
                "assigned_age_band": band,
                "assignment_rule": "whole raw TSE age bin assigned by midpoint",
            }
            for code, band in AGE_CODE_TO_BAND.items()
        ]
    )

    return long_panel, review, raw_age_mapping


def load_bvr_panel() -> pd.DataFrame:
    if BVR_PANEL_PARQUET.exists():
        panel = pd.read_parquet(BVR_PANEL_PARQUET)
    elif BVR_PANEL_CSV.exists():
        panel = pd.read_csv(BVR_PANEL_CSV)
    else:
        raise FileNotFoundError(f"Missing BVR panel at {BVR_PANEL_PARQUET} or {BVR_PANEL_CSV}")
    panel["municipality_id"] = panel["municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    return panel


def pivot_counts(long_panel: pd.DataFrame) -> pd.DataFrame:
    key = ["year_election", "municipality_id"]
    long_panel = long_panel.rename(columns={"year": "year_election"}).copy()

    total = (
        long_panel.groupby(key + ["age_band"], as_index=False)["num_voters"]
        .sum()
        .pivot(index=key, columns="age_band", values="num_voters")
        .reset_index()
    )
    total = total.rename(columns={band: f"num_voters_{band}" for band in AGE_BANDS})

    pieces = [total]
    for group in ["high_ed", "low_ed"]:
        part = (
            long_panel[long_panel["education_group"].eq(group)]
            .groupby(key + ["age_band"], as_index=False)["num_voters"]
            .sum()
            .pivot(index=key, columns="age_band", values="num_voters")
            .reset_index()
        )
        part = part.rename(columns={band: f"num_voters_{group}_{band}" for band in AGE_BANDS})
        pieces.append(part)

    out = pieces[0]
    for part in pieces[1:]:
        out = out.merge(part, on=key, how="outer")
    return out


def build_estimation_sample(long_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    bvr = load_bvr_panel()
    bvr = bvr[bvr["year_election"].isin(SOURCE_YEARS)].copy()
    base_columns = [
        "year_election",
        "municipality_id",
        "municipality_name",
        "state",
        "num_voters",
        "log_num_voters",
        "year_treated",
        "dist_treatment",
        "year_first_strict_bvr",
        "dist_strict_bvr",
        "strict_bvr",
        "hybrid",
        "any_bvr",
        "no_bvr",
    ]
    base = bvr[base_columns].copy()

    counts = pivot_counts(long_panel)
    count_columns = [c for c in counts.columns if c.startswith("num_voters_")]
    counts["has_age_data"] = counts[count_columns].notna().any(axis=1)
    sample = base.merge(counts, on=["year_election", "municipality_id"], how="left")
    sample["has_age_data"] = sample["has_age_data"].where(sample["has_age_data"].notna(), False).astype(bool)

    for column in count_columns:
        sample.loc[sample["has_age_data"], column] = sample.loc[sample["has_age_data"], column].fillna(0)
        log_column = "log_" + column
        sample[log_column] = np.nan
        positive_mask = sample[column].gt(0)
        sample.loc[positive_mask, log_column] = np.log(sample.loc[positive_mask, column])

    expected_log_columns = OUTCOMES
    missing = sorted(set(expected_log_columns) - set(sample.columns))
    if missing:
        raise ValueError(f"Missing expected log outcome columns: {missing}")

    diagnostics = build_sample_diagnostics(sample, count_columns)
    return sample.sort_values(["municipality_id", "year_election"]).reset_index(drop=True), diagnostics


def build_sample_diagnostics(sample: pd.DataFrame, count_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = [
        {"metric": "rows", "outcome": "", "value": int(len(sample))},
        {"metric": "municipalities", "outcome": "", "value": int(sample["municipality_id"].nunique())},
        {"metric": "years", "outcome": "", "value": ",".join(map(str, sorted(sample["year_election"].unique())))},
        {"metric": "rows_with_any_age_data", "outcome": "", "value": int(sample["has_age_data"].sum())},
        {
            "metric": "treated_municipalities_strict_bvr",
            "outcome": "",
            "value": int(sample.loc[sample["year_first_strict_bvr"].ne(NEVER_TREATED_VALUE), "municipality_id"].nunique()),
        },
        {
            "metric": "never_treated_municipalities_strict_bvr",
            "outcome": "",
            "value": int(sample.loc[sample["year_first_strict_bvr"].eq(NEVER_TREATED_VALUE), "municipality_id"].nunique()),
        },
    ]

    for outcome in OUTCOMES:
        count_column = outcome.removeprefix("log_")
        rows.extend(
            [
                {"metric": "nonmissing_log_rows", "outcome": outcome, "value": int(sample[outcome].notna().sum())},
                {"metric": "zero_count_rows", "outcome": outcome, "value": int(sample[count_column].eq(0).sum())},
                {"metric": "positive_count_rows", "outcome": outcome, "value": int(sample[count_column].gt(0).sum())},
            ]
        )

    total_age_columns = [f"num_voters_{band}" for band in AGE_BANDS]
    sample["age_band_total"] = sample[total_age_columns].sum(axis=1)
    sample["age_total_minus_panel_total"] = sample["age_band_total"] - sample["num_voters"]
    rows.append(
        {
            "metric": "max_abs_age_total_minus_panel_total",
            "outcome": "",
            "value": float(sample.loc[sample["has_age_data"], "age_total_minus_panel_total"].abs().max()),
        }
    )
    rows.append(
        {
            "metric": "rows_where_age_total_differs_from_panel_total",
            "outcome": "",
            "value": int(
                sample.loc[sample["has_age_data"], "age_total_minus_panel_total"]
                .fillna(0)
                .ne(0)
                .sum()
            ),
        }
    )

    sample.drop(columns=["age_band_total", "age_total_minus_panel_total"], inplace=True)
    return pd.DataFrame(rows)


def write_estimator_config(outcome: str) -> Path:
    output_dir = outcome_output_dir(outcome)
    config = {
        "estimator": "callaway_santanna",
        "data_path": str(SAMPLE_PARQUET.relative_to(ROOT)),
        "file_format": "parquet",
        "outcome": outcome,
        "unit_id": "municipality_id",
        "time_id": "year_election",
        "group_id": "year_first_strict_bvr",
        "treatment_var": None,
        "event_time_var": "dist_strict_bvr",
        "controls": [],
        "cluster_var": "municipality_id",
        "weights_var": None,
        "lead": 8,
        "lag": 8,
        "anticipation": 0,
        "control_group": "nevertreated",
        "balanced_panel_required": False,
        "never_treated_value": NEVER_TREATED_VALUE,
        "reference_event_time": -2,
        "plot_reference_event_time": -2,
        "seed": SEED,
        "output_dir": str(output_dir.relative_to(ROOT)),
        "notes": (
            "Callaway-Sant'Anna DID for a log age-by-education electorate-count outcome. "
            "The specification matches resources/regressions/did_cs_log_num_voters: strict-BVR cohort timing "
            "via year_first_strict_bvr, never-treated controls, no controls, and municipality-clustered standard errors. "
            "Age groups are built from raw TSE age bins assigned by midpoint; exact ages are not observed."
        ),
        "output": {
            "save_csv": True,
            "save_parquet": False,
            "save_json": True,
            "save_yaml_metadata": True,
            "save_model_summary": True,
        },
        "plot": {
            "latex_figure_format": "pdf",
            "save_tight_png": True,
            "save_png": False,
            "width": 8,
            "height": 5,
            "dpi": 320,
            "omit_title": True,
            "x_label": "Distance to treatment",
            "y_label": None,
            "reference_line": True,
            "reference_line_type": "dashed",
            "zero_line": True,
            "zero_line_width": 1.1,
            "show_ci": True,
            "ci_geom": "linerange",
            "show_border": True,
            "show_grid": True,
            "x_breaks": [-8, -6, -4, -2, 0, 2, 4, 6, 8],
        },
    }
    config_path = CONFIG_DIR / f"{outcome}.yml"
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
    return config_path


def run_estimator(config_path: Path) -> dict[str, object]:
    proc = subprocess.run(
        ["bash", str(RUNNER.relative_to(ROOT)), str(config_path.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    outcome = config_path.stem
    return {
        "outcome": outcome,
        "success": proc.returncode == 0,
        "config": str(config_path.relative_to(ROOT)),
        "output_dir": str(outcome_output_dir(outcome).relative_to(ROOT)),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def collect_outputs(run_status: pd.DataFrame) -> None:
    event_frames: list[pd.DataFrame] = []
    simple_frames: list[pd.DataFrame] = []
    for row in run_status.itertuples(index=False):
        if not row.success:
            continue
        outcome_dir = outcome_output_dir(row.outcome)
        event_path = outcome_dir / "event_study_estimates.csv"
        simple_path = outcome_dir / "aggregate_simple.csv"
        if event_path.exists():
            event = pd.read_csv(event_path)
            event.insert(0, "outcome", row.outcome)
            event_frames.append(event)
        if simple_path.exists():
            simple = pd.read_csv(simple_path)
            simple.insert(0, "outcome", row.outcome)
            simple_frames.append(simple)

    if event_frames:
        pd.concat(event_frames, ignore_index=True).to_csv(RESOURCE_DIR / "event_study_estimates_all.csv", index=False)
    if simple_frames:
        pd.concat(simple_frames, ignore_index=True).to_csv(RESOURCE_DIR / "aggregate_simple_all.csv", index=False)


def write_notes(
    sample: pd.DataFrame,
    diagnostics: pd.DataFrame,
    review: pd.DataFrame,
    age_mapping: pd.DataFrame,
    run_status: pd.DataFrame,
) -> None:
    direct = int(review["match_method"].eq("direct_code_year_state").sum())
    fallback = int(review["match_method"].eq("exact_state_name_fallback").sum())
    unmatched = int(review["match_method"].eq("unmatched").sum())
    successful_runs = int(run_status["success"].sum())
    failed_runs = int((~run_status["success"]).sum())

    mapping_table = age_mapping.to_markdown(index=False)
    diag_table = diagnostics.to_markdown(index=False)
    status_table = run_status[["outcome", "success", "output_dir"]].to_markdown(index=False)

    text = f"""# TSE Age-Education DID Notes

## Scope

This note documents the construction of age-band electorate-count outcomes and Callaway-Sant'Anna DID runs for those outcomes.

## Inputs

- Raw official TSE `perfil_eleitorado` zip files under `data/raw/tse_eleitorado/`.
- TSE-to-IBGE municipality crosswalk: `data/raw/ibge/bd-tse_mun_ids.csv`.
- Treatment and status panel: `data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.parquet`.

## Age Data Coverage

The raw TSE age field is usable for 2008, 2010, 2012, 2014, 2016, and 2018. In the 2000-2006 files, the age field is only `#NE`, so those years are not used for the age-band outcomes.

The TSE files report pre-binned age ranges, not exact ages. The requested bands overlap at their boundaries and cannot be recovered exactly from the source bins. This build assigns each whole raw age bin by midpoint, producing non-overlapping analysis bands.

## Age-Bin Mapping

{mapping_table}

## Education Groups

- `low_ed`: illiterate, reads and writes, incomplete primary, complete primary.
- `high_ed`: incomplete secondary, complete secondary, incomplete higher, complete higher.
- Unknown education is included in total age-band counts but excluded from the low- and high-education subgroup counts.

## Outputs

- Long age-by-education panel: `{LONG_CSV.relative_to(ROOT)}` and `{LONG_PARQUET.relative_to(ROOT)}`.
- Wide DID sample: `{SAMPLE_CSV.relative_to(ROOT)}` and `{SAMPLE_PARQUET.relative_to(ROOT)}`.
- Estimator configs: `{CONFIG_DIR.relative_to(ROOT)}/`.
- Estimator outputs: `resources/regressions/did_cs_log_num_voters_<category>/`.
- Combined event-study output: `{(RESOURCE_DIR / 'event_study_estimates_all.csv').relative_to(ROOT)}`.
- Combined simple ATT output: `{(RESOURCE_DIR / 'aggregate_simple_all.csv').relative_to(ROOT)}`.

## Municipality Matching

- Direct code-year-state matches: {direct}.
- Exact state-name fallback matches: {fallback}.
- Unmatched raw municipality rows: {unmatched}. Unmatched rows are overseas `ZZ` units or otherwise outside the Brazilian municipality panel and are excluded.

## Sample Diagnostics

{diag_table}

## DID Specification

Each outcome uses the same Callaway-Sant'Anna specification as `resources/regressions/did_cs_log_num_voters`: strict-BVR first-treatment year (`year_first_strict_bvr`) as the cohort variable, never-treated controls, no covariates, municipality-clustered standard errors, event window from -8 to +8, and reference event time -2 in plots.

## Run Status

Successful estimator runs: {successful_runs}. Failed estimator runs: {failed_runs}.

{status_table}
"""
    NOTES_PATH.write_text(text + "\n", encoding="utf-8")
    LOG_PATH.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    ensure_directories()

    long_panel, review, age_mapping = build_long_panel()
    sample, diagnostics = build_estimation_sample(long_panel)

    long_panel.to_csv(LONG_CSV, index=False)
    long_panel.to_parquet(LONG_PARQUET, index=False)
    review.to_csv(RESOURCE_DIR / "municipality_crosswalk_review_age_education.csv", index=False)
    age_mapping.to_csv(RESOURCE_DIR / "age_band_mapping.csv", index=False)
    sample.to_csv(SAMPLE_CSV, index=False)
    sample.to_parquet(SAMPLE_PARQUET, index=False)
    diagnostics.to_csv(RESOURCE_DIR / "sample_diagnostics_age_education.csv", index=False)

    config_paths = [write_estimator_config(outcome) for outcome in OUTCOMES]
    run_status = pd.DataFrame([run_estimator(path) for path in config_paths])
    run_status.to_csv(RESOURCE_DIR / "run_status.csv", index=False)

    collect_outputs(run_status)
    write_notes(sample, diagnostics, review, age_mapping, run_status)

    failed = run_status.loc[~run_status["success"]]
    print(f"Wrote {LONG_CSV.relative_to(ROOT)}")
    print(f"Wrote {SAMPLE_PARQUET.relative_to(ROOT)}")
    print("Wrote estimator outputs under resources/regressions/did_cs_log_num_voters_<category>")
    print(f"Successful estimator runs: {int(run_status['success'].sum())}/{len(run_status)}")
    if not failed.empty:
        print("Failed runs:")
        print(failed[["outcome", "returncode", "stderr"]].to_string(index=False))
        raise RuntimeError("One or more DID estimator runs failed.")


if __name__ == "__main__":
    main()
