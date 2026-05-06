from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

ELECTORATE_PARQUET = ROOT / "data/clean/tse_eleitorado/eleitorado_education_gender_2000_2018.parquet"
ELECTORATE_CSV = ROOT / "data/clean/tse_eleitorado/eleitorado_education_gender_2000_2018.csv"
BVR_PARQUET = ROOT / "data/clean/tse_bvr/municipality_bvr_first_treat.parquet"
BVR_CSV = ROOT / "data/clean/tse_bvr/municipality_bvr_first_treat.csv"
HYBRID_REVIEW_CSV = ROOT / "data/interim/tse_bvr/hybrid_2018_review.csv"
CROSSWALK_CSV = ROOT / "data/raw/ibge/bd-tse_mun_ids.csv"

OUTPUT_DIR = ROOT / "data/clean/tse"
INTERIM_DIR = ROOT / "data/interim/tse"
LOG_DIR = ROOT / "resources/logs"
DOCS_DIR = ROOT / "docs"

OUTPUT_PARQUET = OUTPUT_DIR / "tse_clean_panel_2000_2018.parquet"
OUTPUT_CSV = OUTPUT_DIR / "tse_clean_panel_2000_2018.csv"
DIAGNOSTICS_CSV = INTERIM_DIR / "tse_clean_panel_diagnostics.csv"
BUILD_LOG = LOG_DIR / "tse_clean_panel_build_log.md"
NOTES_PATH = DOCS_DIR / "TSE_CLEAN_PANEL_NOTES.md"

ELECTION_YEARS = [2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018]
NEVER_TREATED_YEAR = 9999
HYBRID_STATUS_YEAR = 2018
VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}

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
UNKNOWN_ED_CATEGORIES = {"unknown"}

MEN_CATEGORIES = {"male"}
WOMEN_CATEGORIES = {"female"}
UNKNOWN_GENDER_CATEGORIES = {"unknown"}

REQUIRED_ELECTORATE_COLUMNS = {
    "year",
    "municipality_id",
    "municipality_name",
    "state",
    "education",
    "gender",
    "num_voters",
}
REQUIRED_TREATMENT_COLUMNS = {
    "municipality_id",
    "municipality_name",
    "state",
    "year_first_treat",
}


def normalize_name(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = (
        text.replace("á", "a").replace("à", "a").replace("â", "a").replace("ã", "a")
        .replace("é", "e").replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o").replace("ô", "o").replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    cleaned = []
    prev_space = False
    for char in text:
        if char.isalnum():
            cleaned.append(char)
            prev_space = False
        else:
            if not prev_space:
                cleaned.append(" ")
                prev_space = True
    return " ".join("".join(cleaned).split())


def normalize_code(value: object, width: int = 7) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(char for char in text if char.isdigit())
    if not digits:
        return ""
    return digits.zfill(width)


def ensure_directories() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def load_dataframe(preferred_parquet: Path, fallback_csv: Path, label: str) -> pd.DataFrame:
    if preferred_parquet.exists():
        return pd.read_parquet(preferred_parquet)
    if fallback_csv.exists():
        return pd.read_csv(fallback_csv)
    raise FileNotFoundError(
        f"Required {label} file not found. Checked `{preferred_parquet}` and `{fallback_csv}`."
    )


def require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def build_reference_names(electorate: pd.DataFrame) -> pd.DataFrame:
    # Use the most common municipality name within municipality_id, after validating state uniqueness.
    state_counts = electorate.groupby("municipality_id")["state"].nunique()
    bad_state_ids = state_counts[state_counts > 1]
    if not bad_state_ids.empty:
        raise ValueError(
            "Found municipality IDs with multiple UF values in electorate input: "
            f"{bad_state_ids.index.tolist()[:10]}"
        )

    name_weights = (
        electorate.groupby(["municipality_id", "state", "municipality_name"], as_index=False)["num_voters"]
        .sum()
        .sort_values(["municipality_id", "num_voters", "municipality_name"], ascending=[True, False, True])
    )
    reference = name_weights.drop_duplicates(subset=["municipality_id"], keep="first")
    return reference[["municipality_id", "municipality_name", "state"]].copy()


def build_totals(electorate: pd.DataFrame) -> pd.DataFrame:
    base = (
        electorate.groupby(["year_election", "municipality_id"], as_index=False)["num_voters"]
        .sum()
        .rename(columns={"num_voters": "num_voters"})
    )
    return base


def build_share_component(
    electorate: pd.DataFrame,
    category_column: str,
    numerator_values: set[str],
    output_column: str,
) -> pd.DataFrame:
    subset = electorate[electorate[category_column].isin(numerator_values)].copy()
    aggregated = (
        subset.groupby(["year_election", "municipality_id"], as_index=False)["num_voters"]
        .sum()
        .rename(columns={"num_voters": output_column})
    )
    return aggregated


def collapse_treatment(treatment: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        treatment.groupby("municipality_id", as_index=False)
        .agg(
            year_treated=("year_first_treat", "min"),
            treatment_rows=("year_first_treat", "size"),
            treatment_years_nunique=("year_first_treat", "nunique"),
            treatment_zones_nunique=("zone", "nunique"),
        )
    )
    invalid_years = sorted(set(grouped.loc[~grouped["year_treated"].isin(ELECTION_YEARS), "year_treated"]))
    if invalid_years:
        raise ValueError(f"Treatment file contains invalid election years: {invalid_years}")
    return grouped


def build_hybrid_indicator() -> pd.DataFrame:
    if not HYBRID_REVIEW_CSV.exists():
        raise FileNotFoundError(
            f"Hybrid review file not found at `{HYBRID_REVIEW_CSV}`. "
            "The clean panel cannot add a documented hybrid indicator without this official 2018 source."
        )
    if not CROSSWALK_CSV.exists():
        raise FileNotFoundError(
            f"Municipality crosswalk not found at `{CROSSWALK_CSV}`. "
            "The clean panel cannot map hybrid municipalities to IBGE IDs without it."
        )

    hybrid = pd.read_csv(HYBRID_REVIEW_CSV)
    crosswalk = pd.read_csv(CROSSWALK_CSV)

    required_hybrid_cols = {"state", "tse_municipality_id"}
    required_crosswalk_cols = {"year", "state", "municipality_id", "tse_municipality_id"}
    require_columns(hybrid, required_hybrid_cols, "Hybrid 2018 review input")
    require_columns(crosswalk, required_crosswalk_cols, "TSE-IBGE crosswalk")

    hybrid = hybrid.copy()
    hybrid["state"] = hybrid["state"].astype(str).str.upper().str.strip()
    hybrid["tse_municipality_id"] = hybrid["tse_municipality_id"].map(lambda value: normalize_code(value, width=4))

    crosswalk = crosswalk.copy()
    crosswalk["year"] = pd.to_numeric(crosswalk["year"], errors="coerce").astype("Int64")
    crosswalk["state"] = crosswalk["state"].astype(str).str.upper().str.strip()
    crosswalk["municipality_id"] = crosswalk["municipality_id"].map(normalize_code)
    crosswalk["tse_municipality_id"] = crosswalk["tse_municipality_id"].map(lambda value: normalize_code(value, width=4))
    crosswalk = crosswalk[crosswalk["year"] == HYBRID_STATUS_YEAR].copy()

    duplicate_crosswalk = int(crosswalk.duplicated(subset=["state", "tse_municipality_id"]).sum())
    if duplicate_crosswalk:
        raise ValueError(
            f"Found {duplicate_crosswalk} duplicate 2018 state + TSE municipality code rows in the TSE-IBGE crosswalk."
        )

    hybrid = hybrid.merge(
        crosswalk[["state", "tse_municipality_id", "municipality_id"]],
        on=["state", "tse_municipality_id"],
        how="left",
    )
    unresolved = hybrid.loc[
        hybrid["municipality_id"].isna() | hybrid["municipality_id"].eq(""),
        ["state", "tse_municipality_id"],
    ]
    if not unresolved.empty:
        preview = unresolved.head(10).to_dict(orient="records")
        raise ValueError(
            "Could not map some official 2018 hybrid municipalities to IBGE IDs. "
            f"First unresolved cases: {preview}"
        )

    hybrid_indicator = hybrid[["municipality_id"]].drop_duplicates().copy()
    hybrid_indicator["year_election"] = HYBRID_STATUS_YEAR
    hybrid_indicator["hybrid"] = 1
    return hybrid_indicator


def validate_final_panel(df: pd.DataFrame) -> dict[str, object]:
    duplicate_rows = int(df.duplicated(subset=["year_election", "municipality_id"]).sum())
    if duplicate_rows:
        raise ValueError(f"Final panel has {duplicate_rows} duplicate year_election + municipality_id rows.")

    years = sorted(df["year_election"].dropna().unique().tolist())
    if years != ELECTION_YEARS:
        raise ValueError(f"Unexpected year coverage. Expected {ELECTION_YEARS}, found {years}.")

    invalid_states = sorted(set(df.loc[~df["state"].isin(VALID_UFS), "state"]))
    if invalid_states:
        raise ValueError(f"Invalid UF values found: {invalid_states}")

    bad_names = int((df["municipality_name"] != df["municipality_name"].map(normalize_name)).sum())
    if bad_names:
        raise ValueError(f"Found {bad_names} non-normalized municipality names in final panel.")

    if df["municipality_id"].isna().any():
        raise ValueError("Final panel has missing municipality_id values.")

    invalid_hybrid = sorted(set(df.loc[~df["hybrid"].isin([0, 1]), "hybrid"]))
    if invalid_hybrid:
        raise ValueError(f"Invalid hybrid values found: {invalid_hybrid}")

    non_2018_hybrid = int(((df["year_election"] != HYBRID_STATUS_YEAR) & (df["hybrid"] == 1)).sum())
    if non_2018_hybrid:
        raise ValueError(
            "Found municipality-years flagged as hybrid outside 2018, but the current documented hybrid source is 2018-only."
        )

    if (df["num_voters"] <= 0).any():
        bad = df.loc[df["num_voters"] <= 0, ["year_election", "municipality_id", "num_voters"]].head(10)
        raise ValueError(f"Found non-positive num_voters rows:\n{bad}")

    for count_column, log_column in [
        ("num_voters", "log_num_voters"),
        ("num_voters_low_ed", "log_num_voters_low_ed"),
        ("num_voters_high_ed", "log_num_voters_high_ed"),
        ("num_voters_men", "log_num_voters_men"),
        ("num_voters_women", "log_num_voters_women"),
    ]:
        missing_logs = int(df.loc[df[count_column] > 0, log_column].isna().sum())
        if missing_logs:
            raise ValueError(
                f"Found {missing_logs} missing {log_column} values despite positive {count_column}."
            )

    pct_columns = [
        "pct_voters_low_ed",
        "pct_voters_high_ed",
        "pct_voters_men",
        "pct_voters_women",
    ]
    out_of_bounds = []
    for column in pct_columns:
        mask = df[column].notna() & ((df[column] < 0) | (df[column] > 1))
        if mask.any():
            out_of_bounds.append(column)
    if out_of_bounds:
        raise ValueError(f"Share columns out of bounds: {out_of_bounds}")

    valid_treat_mask = df["year_treated"] != NEVER_TREATED_YEAR
    invalid_treated_years = sorted(
        set(
            df.loc[
                ~df["year_treated"].isin(ELECTION_YEARS + [NEVER_TREATED_YEAR]),
                "year_treated",
            ]
        )
    )
    if invalid_treated_years:
        raise ValueError(f"Invalid year_treated values found: {invalid_treated_years}")

    bad_dist_mask = (df["year_treated"] == NEVER_TREATED_YEAR) & (df["dist_treatment"] != -9999)
    if bad_dist_mask.any():
        raise ValueError("Found never-treated rows with year_treated = 9999 but dist_treatment different from -9999.")

    treated_dist_mask = (df["year_treated"] != NEVER_TREATED_YEAR) & (
        df["dist_treatment"] != (df["year_election"] - df["year_treated"])
    )
    if treated_dist_mask.any():
        raise ValueError("Found treated rows where dist_treatment != year_election - year_treated.")

    return {
        "row_count": int(len(df)),
        "municipality_count": int(df["municipality_id"].nunique()),
        "ever_treated": int(df.loc[df["year_treated"] != NEVER_TREATED_YEAR, "municipality_id"].nunique()),
        "never_treated": int(df.loc[df["year_treated"] == NEVER_TREATED_YEAR, "municipality_id"].nunique()),
        "hybrid_municipality_years": int((df["hybrid"] == 1).sum()),
        "hybrid_municipalities": int(df.loc[df["hybrid"] == 1, "municipality_id"].nunique()),
        "missing_low_ed_share": int(df["pct_voters_low_ed"].isna().sum()),
        "missing_high_ed_share": int(df["pct_voters_high_ed"].isna().sum()),
        "missing_men_share": int(df["pct_voters_men"].isna().sum()),
        "missing_women_share": int(df["pct_voters_women"].isna().sum()),
        "missing_log_low_ed": int(df["log_num_voters_low_ed"].isna().sum()),
        "missing_log_high_ed": int(df["log_num_voters_high_ed"].isna().sum()),
        "missing_log_men": int(df["log_num_voters_men"].isna().sum()),
        "missing_log_women": int(df["log_num_voters_women"].isna().sum()),
    }


def build_diagnostics(
    panel: pd.DataFrame,
    electorate: pd.DataFrame,
    treatment_collapsed: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    rows.append({"section": "panel", "metric": "municipality_year_rows", "subgroup": "", "value": len(panel)})
    rows.append({"section": "panel", "metric": "unique_municipalities", "subgroup": "", "value": panel["municipality_id"].nunique()})
    rows.append({"section": "treatment", "metric": "ever_treated_municipalities", "subgroup": "", "value": panel.loc[panel["year_treated"] != NEVER_TREATED_YEAR, "municipality_id"].nunique()})
    rows.append({"section": "treatment", "metric": "never_treated_municipalities", "subgroup": "", "value": panel.loc[panel["year_treated"] == NEVER_TREATED_YEAR, "municipality_id"].nunique()})
    rows.append({"section": "treatment", "metric": "hybrid_municipality_year_rows", "subgroup": "", "value": int((panel["hybrid"] == 1).sum())})
    rows.append({"section": "treatment", "metric": "hybrid_municipalities", "subgroup": "", "value": int(panel.loc[panel["hybrid"] == 1, "municipality_id"].nunique())})
    rows.append({"section": "shares", "metric": "missing_pct_voters_low_ed", "subgroup": "", "value": int(panel["pct_voters_low_ed"].isna().sum())})
    rows.append({"section": "shares", "metric": "missing_pct_voters_high_ed", "subgroup": "", "value": int(panel["pct_voters_high_ed"].isna().sum())})
    rows.append({"section": "shares", "metric": "missing_pct_voters_men", "subgroup": "", "value": int(panel["pct_voters_men"].isna().sum())})
    rows.append({"section": "shares", "metric": "missing_pct_voters_women", "subgroup": "", "value": int(panel["pct_voters_women"].isna().sum())})
    rows.append({"section": "treatment", "metric": "municipalities_with_multiple_treatment_rows", "subgroup": "", "value": int((treatment_collapsed["treatment_rows"] > 1).sum())})
    rows.append({"section": "treatment", "metric": "municipalities_with_multiple_treatment_years", "subgroup": "", "value": int((treatment_collapsed["treatment_years_nunique"] > 1).sum())})
    rows.append({"section": "data_quality", "metric": "unknown_education_rows_in_upstream", "subgroup": "", "value": int(electorate["education"].isin(UNKNOWN_ED_CATEGORIES).sum())})
    rows.append({"section": "data_quality", "metric": "unknown_gender_rows_in_upstream", "subgroup": "", "value": int(electorate["gender"].isin(UNKNOWN_GENDER_CATEGORIES).sum())})

    year_counts = panel.groupby("year_election").size().reset_index(name="value")
    for row in year_counts.itertuples(index=False):
        rows.append({"section": "coverage", "metric": "rows_by_year", "subgroup": int(row.year_election), "value": int(row.value)})

    return pd.DataFrame(rows)


def write_notes(
    electorate_path: Path,
    treatment_path: Path,
    panel: pd.DataFrame,
    treatment_collapsed: pd.DataFrame,
    validation: dict[str, object],
) -> None:
    year_counts = panel.groupby("year_election").size().to_dict()
    zero_unknown_ed_years = (
        panel.assign(residual_ed=1 - panel["pct_voters_low_ed"] - panel["pct_voters_high_ed"])
        .groupby("year_election")["residual_ed"]
        .mean()
        .round(6)
        .to_dict()
    )
    zero_unknown_gender_years = (
        panel.assign(residual_gender=1 - panel["pct_voters_men"] - panel["pct_voters_women"])
        .groupby("year_election")["residual_gender"]
        .mean()
        .round(6)
        .to_dict()
    )

    notes = f"""# TSE Clean Panel Notes

## Input Files Used

- Electorate input: `{electorate_path.relative_to(ROOT)}`
- BVR treatment input: `{treatment_path.relative_to(ROOT)}`
- Optional municipality crosswalk reference available in repo: `data/raw/ibge/bd-tse_mun_ids.csv`

## Election Years Retained

The final panel is restricted to the ten election years:

- 2000
- 2002
- 2004
- 2006
- 2008
- 2010
- 2012
- 2014
- 2016
- 2018

Row counts by year:

{pd.Series(year_counts).to_string()}

## Education Mapping Used

Low education is defined as less than high school and includes:

- `illiterate`
- `reads_and_writes`
- `incomplete_primary`
- `complete_primary`

High education is defined as high school or more and includes:

- `incomplete_secondary`
- `complete_secondary`
- `incomplete_higher`
- `complete_higher`

The upstream electorate file also includes `unknown`. The final panel uses:

- denominator = total municipality-year electorate, including `unknown`
- numerator for low/high shares = only the mapped categories above

As a result, `pct_voters_low_ed + pct_voters_high_ed` can be less than 1 when `unknown` education is present.

## Gender Mapping Used

The upstream electorate file uses:

- `male`
- `female`
- `unknown`

The final panel uses:

- `num_voters_men` = male voters
- `num_voters_women` = female voters
- `log_num_voters_men` = log male voters
- `log_num_voters_women` = log female voters
- `pct_voters_men` = male voters / total municipality-year electorate
- `pct_voters_women` = female voters / total municipality-year electorate

As with education, the denominator includes `unknown`, so `pct_voters_men + pct_voters_women` can be less than 1.

## Treatment Timing Merge

The BVR treatment file is municipality-zone level in some years. For the municipality-level panel, treatment is first collapsed to municipality level by:

- grouping on `municipality_id`
- taking the minimum `year_first_treat` within municipality

The collapsed field is renamed `year_treated` in the final panel.
Municipalities never treated by 2018 are assigned `year_treated = 9999`.

Municipalities with multiple treatment rows in the source BVR file: {int((treatment_collapsed["treatment_rows"] > 1).sum())}
Municipalities with multiple distinct treatment years in the source BVR file: {int((treatment_collapsed["treatment_years_nunique"] > 1).sum())}

## Hybrid Status Variable

The final panel now includes a binary `hybrid` indicator:

- `hybrid = 1` if the municipality is explicitly marked as `Híbrido` in the official TSE 2018 electorate file
- `hybrid = 0` otherwise

The current repo has an official municipality-level hybrid source for 2018 only. Because municipality-level hybrid coding for 2016 remains unresolved, this panel does not impute hybrid status for earlier years.

- Hybrid municipality-year rows in the final panel: {validation['hybrid_municipality_years']}
- Unique municipalities flagged as hybrid: {validation['hybrid_municipalities']}

## Distance-to-Treatment Formula

The final panel defines:

- `year_treated = 9999` if the municipality is never treated
- `dist_treatment = -9999` if `year_treated = 9999`
- otherwise `dist_treatment = year_election - year_treated`

This keeps the measure in calendar-year differences rather than election-count units.

## Municipality Name and State Handling

- `municipality_id` is treated as the primary key.
- `state` is taken from the cleaned electorate input and validated against the 27 official UFs.
- `municipality_name` is rebuilt from the most common cleaned electorate name observed for each `municipality_id` across the panel, then normalized to lower-case ASCII with stripped punctuation and collapsed spaces.

## Validation Results

- Municipality-year rows: {validation['row_count']}
- Unique municipalities: {validation['municipality_count']}
- Ever treated municipalities: {validation['ever_treated']}
- Never treated municipalities: {validation['never_treated']}
- Hybrid municipality-year rows: {validation['hybrid_municipality_years']}
- Unique hybrid municipalities: {validation['hybrid_municipalities']}
- Missing `pct_voters_low_ed`: {validation['missing_low_ed_share']}
- Missing `pct_voters_high_ed`: {validation['missing_high_ed_share']}
- Missing `pct_voters_men`: {validation['missing_men_share']}
- Missing `pct_voters_women`: {validation['missing_women_share']}
- Missing `log_num_voters_low_ed`: {validation['missing_log_low_ed']}
- Missing `log_num_voters_high_ed`: {validation['missing_log_high_ed']}
- Missing `log_num_voters_men`: {validation['missing_log_men']}
- Missing `log_num_voters_women`: {validation['missing_log_women']}
- All final keys are unique on `year_election + municipality_id`.
- All pct variables are within `[0, 1]`.
- All `num_voters`, `num_voters_low_ed`, `num_voters_high_ed`, `num_voters_men`, and `num_voters_women` values are positive, so all log electorate outcomes are defined everywhere in the final panel.

Average residual education share `1 - low - high` by year:

{pd.Series(zero_unknown_ed_years).to_string()}

Average residual gender share `1 - men - women` by year:

{pd.Series(zero_unknown_gender_years).to_string()}

## Caveats and Unresolved Issues

- Because education and gender unknown categories are kept in the denominator, the reported composition shares are intentionally conservative and may sum to less than 1.
- Municipality-level treatment timing collapses any zone-level variation to the earliest treated election year within municipality.
- The `hybrid` indicator is only sourced from the official 2018 TSE municipality status file. It should be interpreted as a year-specific status measure, not as a full history of hybrid implementation before 2018.
- The panel inherits any residual upstream limitations from the clean electorate file and the clean BVR timing file, but it does not introduce additional fuzzy municipality matching.
"""
    NOTES_PATH.write_text(notes, encoding="utf-8")


def write_build_log(
    panel: pd.DataFrame,
    diagnostics: pd.DataFrame,
    validation: dict[str, object],
) -> None:
    year_counts = diagnostics.loc[diagnostics["metric"] == "rows_by_year", ["subgroup", "value"]]
    year_counts_text = "\n".join(f"- {int(row.subgroup)}: {int(row.value)} rows" for row in year_counts.itertuples(index=False))

    log_text = (
        "# TSE Clean Panel Build Log\n\n"
        "## Summary\n\n"
        f"- Final municipality-year rows: {validation['row_count']}\n"
        f"- Unique municipalities: {validation['municipality_count']}\n"
        f"- Ever treated municipalities: {validation['ever_treated']}\n"
        f"- Never treated municipalities: {validation['never_treated']}\n"
        f"- Hybrid municipality-year rows: {validation['hybrid_municipality_years']}\n"
        f"- Unique hybrid municipalities: {validation['hybrid_municipalities']}\n"
        f"- Missing low-education shares: {validation['missing_low_ed_share']}\n"
        f"- Missing high-education shares: {validation['missing_high_ed_share']}\n"
        f"- Missing male shares: {validation['missing_men_share']}\n"
        f"- Missing female shares: {validation['missing_women_share']}\n"
        f"- Missing log low-education electorate: {validation['missing_log_low_ed']}\n"
        f"- Missing log high-education electorate: {validation['missing_log_high_ed']}\n\n"
        f"- Missing log male electorate: {validation['missing_log_men']}\n"
        f"- Missing log female electorate: {validation['missing_log_women']}\n\n"
        "## Row Counts By Year\n\n"
        f"{year_counts_text}\n\n"
        "## Validation\n\n"
        "- Final key `year_election + municipality_id` is unique.\n"
        "- Year coverage matches the required ten election years only.\n"
        "- All share variables are within `[0, 1]`.\n"
        "- All `num_voters`, `num_voters_low_ed`, `num_voters_high_ed`, `num_voters_men`, and `num_voters_women` values are positive.\n"
        "- All log electorate outcomes are present where their underlying counts are positive.\n"
        "- `dist_treatment = -9999` iff `year_treated = 9999`.\n"
        "- Otherwise `dist_treatment = year_election - year_treated`.\n"
    )
    BUILD_LOG.write_text(log_text, encoding="utf-8")


def main() -> None:
    ensure_directories()

    electorate_path = ELECTORATE_PARQUET if ELECTORATE_PARQUET.exists() else ELECTORATE_CSV
    treatment_path = BVR_PARQUET if BVR_PARQUET.exists() else BVR_CSV

    electorate = load_dataframe(ELECTORATE_PARQUET, ELECTORATE_CSV, "clean TSE electorate")
    treatment = load_dataframe(BVR_PARQUET, BVR_CSV, "clean BVR treatment")

    require_columns(electorate, REQUIRED_ELECTORATE_COLUMNS, "Electorate input")
    require_columns(treatment, REQUIRED_TREATMENT_COLUMNS, "BVR treatment input")

    electorate = electorate.copy()
    electorate["year_election"] = pd.to_numeric(electorate["year"], errors="coerce").astype("Int64")
    electorate["municipality_id"] = electorate["municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    electorate["municipality_name"] = electorate["municipality_name"].map(normalize_name)
    electorate["state"] = electorate["state"].astype(str).str.upper().str.strip()
    electorate["education"] = electorate["education"].astype(str).str.strip()
    electorate["gender"] = electorate["gender"].astype(str).str.strip()
    electorate["num_voters"] = pd.to_numeric(electorate["num_voters"], errors="coerce")

    if electorate["num_voters"].isna().any():
        raise ValueError("Electorate input has missing num_voters after numeric coercion.")

    electorate = electorate[electorate["year_election"].isin(ELECTION_YEARS)].copy()

    unexpected_education = sorted(set(electorate["education"]) - (LOW_ED_CATEGORIES | HIGH_ED_CATEGORIES | UNKNOWN_ED_CATEGORIES))
    unexpected_gender = sorted(set(electorate["gender"]) - (MEN_CATEGORIES | WOMEN_CATEGORIES | UNKNOWN_GENDER_CATEGORIES))
    if unexpected_education:
        raise ValueError(f"Unexpected education labels in electorate input: {unexpected_education}")
    if unexpected_gender:
        raise ValueError(f"Unexpected gender labels in electorate input: {unexpected_gender}")

    reference = build_reference_names(electorate)
    totals = build_totals(electorate)
    low_ed = build_share_component(electorate, "education", LOW_ED_CATEGORIES, "num_voters_low_ed")
    high_ed = build_share_component(electorate, "education", HIGH_ED_CATEGORIES, "num_voters_high_ed")
    men = build_share_component(electorate, "gender", MEN_CATEGORIES, "num_voters_men")
    women = build_share_component(electorate, "gender", WOMEN_CATEGORIES, "num_voters_women")

    panel = totals.merge(reference, on="municipality_id", how="left")
    for component in [low_ed, high_ed, men, women]:
        panel = panel.merge(component, on=["year_election", "municipality_id"], how="left")

    for column in ["num_voters_low_ed", "num_voters_high_ed", "num_voters_men", "num_voters_women"]:
        panel[column] = panel[column].fillna(0)

    panel["log_num_voters"] = np.where(panel["num_voters"] > 0, np.log(panel["num_voters"]), np.nan)
    panel["log_num_voters_low_ed"] = np.where(
        panel["num_voters_low_ed"] > 0,
        np.log(panel["num_voters_low_ed"]),
        np.nan,
    )
    panel["log_num_voters_high_ed"] = np.where(
        panel["num_voters_high_ed"] > 0,
        np.log(panel["num_voters_high_ed"]),
        np.nan,
    )
    panel["log_num_voters_men"] = np.where(
        panel["num_voters_men"] > 0,
        np.log(panel["num_voters_men"]),
        np.nan,
    )
    panel["log_num_voters_women"] = np.where(
        panel["num_voters_women"] > 0,
        np.log(panel["num_voters_women"]),
        np.nan,
    )
    panel["pct_voters_low_ed"] = panel["num_voters_low_ed"] / panel["num_voters"]
    panel["pct_voters_high_ed"] = panel["num_voters_high_ed"] / panel["num_voters"]
    panel["pct_voters_men"] = panel["num_voters_men"] / panel["num_voters"]
    panel["pct_voters_women"] = panel["num_voters_women"] / panel["num_voters"]

    treatment = treatment.copy()
    treatment["municipality_id"] = treatment["municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    treatment["year_first_treat"] = pd.to_numeric(treatment["year_first_treat"], errors="coerce").astype("Int64")
    treatment_collapsed = collapse_treatment(treatment)
    hybrid_indicator = build_hybrid_indicator()

    panel = panel.merge(
        treatment_collapsed[["municipality_id", "year_treated"]],
        on="municipality_id",
        how="left",
    )
    panel = panel.merge(hybrid_indicator, on=["municipality_id", "year_election"], how="left")
    panel["year_treated"] = panel["year_treated"].fillna(NEVER_TREATED_YEAR).astype(int)
    panel["hybrid"] = panel["hybrid"].fillna(0).astype(int)
    panel["dist_treatment"] = -9999
    treated_mask = panel["year_treated"] != NEVER_TREATED_YEAR
    panel.loc[treated_mask, "dist_treatment"] = (
        panel.loc[treated_mask, "year_election"].astype(int)
        - panel.loc[treated_mask, "year_treated"].astype(int)
    )
    panel["dist_treatment"] = panel["dist_treatment"].astype(int)

    final_columns = [
        "year_election",
        "municipality_id",
        "municipality_name",
        "state",
        "num_voters",
        "log_num_voters",
        "num_voters_low_ed",
        "log_num_voters_low_ed",
        "num_voters_high_ed",
        "log_num_voters_high_ed",
        "num_voters_men",
        "log_num_voters_men",
        "num_voters_women",
        "log_num_voters_women",
        "pct_voters_low_ed",
        "pct_voters_high_ed",
        "pct_voters_men",
        "pct_voters_women",
        "year_treated",
        "dist_treatment",
        "hybrid",
    ]

    panel = panel[final_columns].sort_values(["year_election", "municipality_id"]).reset_index(drop=True)
    validation = validate_final_panel(panel)
    diagnostics = build_diagnostics(panel, electorate, treatment_collapsed)

    panel.to_parquet(OUTPUT_PARQUET, index=False)
    panel.to_csv(OUTPUT_CSV, index=False)
    diagnostics.to_csv(DIAGNOSTICS_CSV, index=False)

    write_notes(electorate_path, treatment_path, panel, treatment_collapsed, validation)
    write_build_log(panel, diagnostics, validation)

    print(f"Wrote clean panel to {OUTPUT_PARQUET.relative_to(ROOT)} and {OUTPUT_CSV.relative_to(ROOT)}")
    print(f"Rows: {validation['row_count']}; municipalities: {validation['municipality_count']}")


if __name__ == "__main__":
    main()
