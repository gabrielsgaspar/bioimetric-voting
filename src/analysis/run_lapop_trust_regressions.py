from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[2]

LAPOP_PCA_PATH = ROOT / "data" / "clean" / "lapop" / "lapop_brazil_with_pca_indices.parquet"
LAPOP_PCA_CSV_PATH = ROOT / "data" / "clean" / "lapop" / "lapop_brazil_with_pca_indices.csv"
REG_READY_PARQUET = ROOT / "data" / "clean" / "lapop" / "lapop_brazil_with_pca_indices_regression_ready.parquet"
REG_READY_CSV = ROOT / "data" / "clean" / "lapop" / "lapop_brazil_with_pca_indices_regression_ready.csv"

IBGE_MUNICIPALITIES_PATH = ROOT / "data" / "clean" / "tse_bvr" / "ibge_municipalities.csv"
TREATMENT_PATH = ROOT / "data" / "clean" / "tse_bvr" / "municipality_bvr_first_treat.parquet"
MUNICIPAL_COVARIATES_PARQUET = ROOT / "data" / "clean" / "ibge" / "municipality_gdp_population_survey_years.parquet"
MUNICIPAL_COVARIATES_CSV = ROOT / "data" / "clean" / "ibge" / "municipality_gdp_population_survey_years.csv"

TRUST_CONFIG = ROOT / ".agents" / "skills" / "regression-runner" / "examples" / "config_trust_interactions.yml"
DEMOCRACY_CONFIG = ROOT / ".agents" / "skills" / "regression-runner" / "examples" / "config_democracy_interactions.yml"
RUNNER_SCRIPT = ROOT / ".agents" / "skills" / "regression-runner" / "scripts" / "run_regression.py"
INTERACTION_PLOT_SCRIPT = ROOT / "src" / "analysis" / "build_lapop_interaction_barplots.py"

TRUST_SUMMARY_PATH = ROOT / "resources" / "lapop" / "regressions" / "trust_interactions" / "regression_table.csv"
DEMOCRACY_SUMMARY_PATH = ROOT / "resources" / "lapop" / "regressions" / "democracy_interactions" / "regression_table.csv"
TRUST_EFFECTS_PATH = ROOT / "resources" / "lapop" / "regressions" / "trust_interactions" / "interaction_effects.csv"
DEMOCRACY_EFFECTS_PATH = ROOT / "resources" / "lapop" / "regressions" / "democracy_interactions" / "interaction_effects.csv"

MAIN_TABLE_TEX_PATH = ROOT / "resources" / "tables" / "lapop_trust_interactions_main_table.tex"
MAIN_TABLE_CSV_PATH = ROOT / "resources" / "tables" / "lapop_trust_interactions_main_table.csv"
NOTES_PATH = ROOT / "docs" / "LAPOP_TRUST_REGRESSIONS_NOTES.md"
LOG_PATH = ROOT / "resources" / "logs" / "lapop_trust_regressions_log.md"

STATE_NAME_TO_ABBREV = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}

MUNICIPALITY_OVERRIDES = {
    ("fatima do sul", "mato grosso"): {
        "municipality_name_for_merge": "fatima do sul",
        "state": "MS",
        "reason": "Survey state label points to MT, but Fátima do Sul is an MS municipality.",
    },
    ("rio preto eva", "amazonas"): {
        "municipality_name_for_merge": "rio preto da eva",
        "state": "AM",
        "reason": "Survey municipality omits `da` relative to the IBGE municipality name.",
    },
    ("senador la roque", "maranhao"): {
        "municipality_name_for_merge": "senador la rocque",
        "state": "MA",
        "reason": "Survey spelling differs from the IBGE municipality spelling `rocque`.",
    },
    ("santana do livramento", "rio grande do sul"): {
        "municipality_name_for_merge": "sant ana do livramento",
        "state": "RS",
        "reason": "Survey name drops the apostrophe in Sant'Ana do Livramento.",
    },
    ("iguaraci", "pernambuco"): {
        "municipality_name_for_merge": "iguaracy",
        "state": "PE",
        "reason": "Survey spelling differs from the IBGE municipality spelling `iguaracy`.",
    },
    ("senador guiomnard", "acre"): {
        "municipality_name_for_merge": "senador guiomard",
        "state": "AC",
        "reason": "Survey spelling differs from the IBGE municipality spelling `guiomard`.",
    },
    ("porto espiridiao", "mato grosso"): {
        "municipality_name_for_merge": "porto esperidiao",
        "state": "MT",
        "reason": "Survey spelling differs from the IBGE municipality spelling `esperidiao`.",
    },
    ("embu", "sao paulo"): {
        "municipality_name_for_merge": "embu das artes",
        "state": "SP",
        "reason": "Survey uses the pre-2011 municipality name `Embu`; IBGE file uses `Embu das Artes`.",
    },
}

SIDRA_GDP_TABLE = "5938"
SIDRA_GDP_VARIABLE = "37"
SIDRA_POP_TABLE = "6579"
SIDRA_POP_VARIABLE = "9324"
SIDRA_POP_2010_CENSUS_TABLE = "202"


def _read_lapop_pca() -> pd.DataFrame:
    if LAPOP_PCA_PATH.exists():
        return pd.read_parquet(LAPOP_PCA_PATH)
    if LAPOP_PCA_CSV_PATH.exists():
        return pd.read_csv(LAPOP_PCA_CSV_PATH)
    raise FileNotFoundError("Could not locate the LAPOP PCA dataset in parquet or csv format.")


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce")


def fetch_sidra_series_by_year(*, table_id: str, variable_id: str, years: list[int], value_name: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in years:
        url = f"https://apisidra.ibge.gov.br/values/t/{table_id}/n6/all/v/{variable_id}/p/{year}?formato=json"
        payload = None
        for attempt in range(3):
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            candidate = response.json()
            if (
                isinstance(candidate, list)
                and len(candidate) >= 2
                and isinstance(candidate[0], dict)
                and "D1C" in candidate[0]
            ):
                payload = candidate
                break
        if payload is None:
            snippet = response.text[:500] if "response" in locals() else ""
            raise ValueError(
                f"Unexpected SIDRA response for table {table_id}, variable {variable_id}, year {year}: {snippet}"
            )
        frame = pd.DataFrame(payload[1:])
        frame = frame.rename(columns={"D1C": "municipality_id", "D3C": "year", "V": value_name})
        frame["municipality_id"] = frame["municipality_id"].astype(str).str.zfill(7)
        frame["year"] = frame["year"].astype(int)
        frame[value_name] = _safe_numeric(frame[value_name])
        frames.append(frame[["municipality_id", "year", value_name]])
    output = pd.concat(frames, ignore_index=True).drop_duplicates(["municipality_id", "year"])
    return output


def fetch_population_2010_census() -> pd.DataFrame:
    url = f"https://apisidra.ibge.gov.br/values/t/{SIDRA_POP_2010_CENSUS_TABLE}/n6/all/p/2010?formato=json"
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or len(payload) < 2 or "D1C" not in payload[0]:
        raise ValueError(f"Unexpected 2010 census population response: {response.text[:500]}")
    frame = pd.DataFrame(payload[1:])
    frame = frame.rename(columns={"D1C": "municipality_id", "D2C": "year", "V": "total_pop"})
    frame["municipality_id"] = frame["municipality_id"].astype(str).str.zfill(7)
    frame["year"] = frame["year"].astype(int)
    frame["total_pop"] = _safe_numeric(frame["total_pop"])
    return frame[["municipality_id", "year", "total_pop"]].drop_duplicates(["municipality_id", "year"])


def build_municipal_covariates(years: list[int]) -> pd.DataFrame:
    MUNICIPAL_COVARIATES_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    if MUNICIPAL_COVARIATES_PARQUET.exists():
        cached = pd.read_parquet(MUNICIPAL_COVARIATES_PARQUET)
        if sorted(cached["year"].dropna().unique().tolist()) == sorted(years):
            return cached

    gdp = fetch_sidra_series_by_year(
        table_id=SIDRA_GDP_TABLE,
        variable_id=SIDRA_GDP_VARIABLE,
        years=years,
        value_name="gdp_current_mil_reais",
    )

    population_frames: list[pd.DataFrame] = []
    pop_estimate_years = [year for year in years if year != 2010]
    if pop_estimate_years:
        population_frames.append(
            fetch_sidra_series_by_year(
                table_id=SIDRA_POP_TABLE,
                variable_id=SIDRA_POP_VARIABLE,
                years=pop_estimate_years,
                value_name="total_pop",
            )
        )
    if 2010 in years:
        population_frames.append(fetch_population_2010_census())

    population = pd.concat(population_frames, ignore_index=True).drop_duplicates(["municipality_id", "year"])
    covariates = gdp.merge(population, on=["municipality_id", "year"], how="inner", validate="one_to_one")
    covariates["gdp_current_reais"] = covariates["gdp_current_mil_reais"] * 1000.0
    covariates["gdp_pc"] = covariates["gdp_current_reais"] / covariates["total_pop"]
    covariates.loc[covariates["gdp_pc"] <= 0, "gdp_pc"] = np.nan
    covariates["log_gdp_pc"] = np.log(covariates["gdp_pc"])
    covariates["log_total_pop"] = np.log(covariates["total_pop"])
    covariates = covariates.sort_values(["year", "municipality_id"]).reset_index(drop=True)
    covariates.to_parquet(MUNICIPAL_COVARIATES_PARQUET, index=False)
    covariates.to_csv(MUNICIPAL_COVARIATES_CSV, index=False)
    return covariates


def build_regression_ready_dataset() -> tuple[pd.DataFrame, dict]:
    lapop = _read_lapop_pca().copy()
    survey_years = sorted(int(year) for year in lapop["survey_year"].dropna().unique())
    ibge = pd.read_csv(IBGE_MUNICIPALITIES_PATH, dtype={"municipality_id": str})
    treatment = pd.read_parquet(TREATMENT_PATH)
    covariates = build_municipal_covariates(survey_years)

    lapop["state"] = lapop["state_name"].map(STATE_NAME_TO_ABBREV)
    lapop["municipality_name_for_merge"] = lapop["municipality_name"]
    lapop["manual_override_applied"] = False
    lapop["manual_override_note"] = ""

    for (municipality_name, state_name), override in MUNICIPALITY_OVERRIDES.items():
        mask = (lapop["municipality_name"] == municipality_name) & (lapop["state_name"] == state_name)
        lapop.loc[mask, "municipality_name_for_merge"] = override["municipality_name_for_merge"]
        lapop.loc[mask, "state"] = override["state"]
        lapop.loc[mask, "manual_override_applied"] = True
        lapop.loc[mask, "manual_override_note"] = override["reason"]

    merged = lapop.merge(
        ibge[["municipality_id", "municipality_name", "state"]],
        left_on=["municipality_name_for_merge", "state"],
        right_on=["municipality_name", "state"],
        how="left",
        suffixes=("", "_ibge"),
    )
    merged["matched_to_municipality"] = merged["municipality_id"].notna()
    merged["match_method"] = np.where(
        merged["matched_to_municipality"] & merged["manual_override_applied"],
        "manual_override",
        np.where(merged["matched_to_municipality"], "exact_state_name", "unmatched"),
    )

    treatment = treatment.rename(columns={"year_first_treat": "year_first_treat"})
    treatment["municipality_id"] = treatment["municipality_id"].astype(str).str.zfill(7)
    merged = merged.merge(
        treatment[["municipality_id", "year_first_treat"]],
        on="municipality_id",
        how="left",
        validate="m:1",
    )
    merged["year_first_treat"] = merged["year_first_treat"].fillna(9999).astype(int)
    merged["treatment_dummy"] = (
        merged["municipality_id"].notna() & (merged["year_first_treat"] <= merged["survey_year"])
    ).astype(int)

    covariates = covariates.rename(columns={"year": "survey_year"})
    merged = merged.merge(
        covariates[["municipality_id", "survey_year", "gdp_pc", "log_gdp_pc", "total_pop", "log_total_pop"]],
        on=["municipality_id", "survey_year"],
        how="left",
        validate="m:1",
    )

    merged["low_ed"] = np.where(merged["education_category"].fillna("").eq("less_than_secondary"), 1.0, 0.0)
    merged.loc[merged["education_category"].isna(), "low_ed"] = np.nan
    merged["low_education"] = merged["low_ed"]
    merged["used_in_main_trust_sample"] = merged["survey_year"] <= 2018

    merged.to_parquet(REG_READY_PARQUET, index=False)
    merged.to_csv(REG_READY_CSV, index=False)

    summary = {
        "survey_years_all": survey_years,
        "survey_years_main": sorted(int(year) for year in merged.loc[merged["survey_year"] <= 2018, "survey_year"].dropna().unique()),
        "respondents_total": int(len(merged)),
        "respondents_matched_to_municipality": int(merged["matched_to_municipality"].sum()),
        "respondents_unmatched_to_municipality": int((~merged["matched_to_municipality"]).sum()),
        "respondents_with_manual_override": int(merged["manual_override_applied"].sum()),
        "respondents_with_covariates": int(merged["log_gdp_pc"].notna().sum()),
        "respondents_main_sample": int((merged["survey_year"] <= 2018).sum()),
        "matched_main_sample": int(merged.loc[merged["survey_year"] <= 2018, "matched_to_municipality"].sum()),
        "treated_main_sample": int(merged.loc[merged["survey_year"] <= 2018, "treatment_dummy"].sum()),
    }
    unmatched_pairs = (
        merged.loc[~merged["matched_to_municipality"], ["municipality_name", "state_name"]]
        .value_counts(dropna=False)
        .rename("n_respondents")
        .reset_index()
    )
    summary["unmatched_pairs"] = unmatched_pairs
    return merged, summary


def _tex_escape(text: str) -> str:
    return (
        str(text)
        .replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
    )


def build_main_table() -> pd.DataFrame:
    trust = pd.read_csv(TRUST_SUMMARY_PATH)
    democracy = pd.read_csv(DEMOCRACY_SUMMARY_PATH)
    combined = pd.concat([trust, democracy], ignore_index=True)
    combined.to_csv(MAIN_TABLE_CSV_PATH, index=False)

    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}llcccc}",
        r"\doubletoprule",
        r"Outcome & Category & Base group & Interacted group & Difference & $p$-value \\",
        r"\midrule",
    ]
    last_outcome = None
    for row in combined.itertuples(index=False):
        if last_outcome is not None and row.outcome != last_outcome:
            lines.append(r"\midrule")
        stars = "" if pd.isna(row.stars) else str(row.stars)
        lines.append(
            f"{_tex_escape(row.outcome)} & {_tex_escape(row.category)} & "
            f"{row.base_group_treatment_effect:.3f} & {row.interacted_group_treatment_effect:.3f} & "
            f"{row.interaction_difference:.3f}{stars} & {row.interaction_p_value:.3f} \\\\"
        )
        lines.append(
            f" &  & ({row.base_group_std_error:.3f}) & ({row.interacted_group_std_error:.3f}) & "
            f"({row.interaction_difference_std_error:.3f}) & \\\\"
        )
        last_outcome = row.outcome
    lines.extend(
        [
            r"\doublebottomrule",
            r"\end{tabular*}",
            "",
            r"\begin{minipage}{\textwidth}",
            r"\footnotesize",
            r"\textbf{Note:} Each row summarizes one interaction regression. The base-group effect is the treatment coefficient for the reference category, the interacted-group effect adds the treatment-interaction coefficient using the fitted covariance matrix, and the difference column reports the interaction term. Municipality and survey-year fixed effects are included in every model. Standard errors are clustered by municipality and survey year where feasible.",
            r"\end{minipage}",
        ]
    )
    MAIN_TABLE_TEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return combined


def run_regressions() -> None:
    for config_path in [TRUST_CONFIG, DEMOCRACY_CONFIG]:
        subprocess.run([sys.executable, str(RUNNER_SCRIPT), str(config_path)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(INTERACTION_PLOT_SCRIPT)], cwd=ROOT, check=True)


def write_notes_and_log(summary: dict, combined_table: pd.DataFrame) -> None:
    trust_effects = pd.read_csv(TRUST_EFFECTS_PATH)
    democracy_effects = pd.read_csv(DEMOCRACY_EFFECTS_PATH)
    trust_ns = trust_effects.groupby("category")["n_obs"].first().to_dict()
    democracy_ns = democracy_effects.groupby("category")["n_obs"].first().to_dict()

    notes = f"""# LAPOP Trust Regressions Notes

## Input Dataset Used

- Base respondent-level file: `data/clean/lapop/lapop_brazil_with_pca_indices.parquet`
- Regression-ready file created in this step: `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready.parquet`

## Actual Sample Years Used

- Full regression-ready file years: {summary['survey_years_all']}
- Main regression sample years with `survey_year <= 2018`: {summary['survey_years_main']}

## Outcomes Used

- `trust_index_std`
- `democracy_index_std`

## Controls Used

- `low_ed`
- `female`
- `white`
- `married`
- `working`
- `age`
- `log_gdp_pc`
- `log_total_pop`

## Fixed Effects And Clustering

- Municipality fixed effects: `municipality_id`
- Survey-year fixed effects: `survey_year`
- Requested clustering: `municipality_id + survey_year`
- The regression runner uses a two-way clustered covariance matrix when it is numerically well behaved and falls back to one-way municipality clustering if the two-way covariance is not usable.

## Municipality And Covariate Linkage

- Respondents matched to municipalities: {summary['respondents_matched_to_municipality']:,} of {summary['respondents_total']:,}
- Respondents unmatched to municipalities: {summary['respondents_unmatched_to_municipality']:,}
- Respondents with manual municipality overrides: {summary['respondents_with_manual_override']:,}
- Respondents with municipal GDP and population covariates: {summary['respondents_with_covariates']:,}

The municipality linkage uses LAPOP normalized municipality names and normalized state names, then merges them to the repo's clean IBGE municipality file. A small manual override list handles spelling or historical-name differences such as `Embu` versus `Embu das Artes` and `Santana do Livramento` versus `Sant'Ana do Livramento`.

## Treatment Coding

- `treatment_dummy` equals one when a respondent lives in a municipality whose first biometric election year is less than or equal to the respondent's survey year.
- Municipal treatment timing comes from `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`.

## Municipal Covariates

- `log_total_pop` is based on official IBGE resident-population estimates from SIDRA table `6579`, variable `9324`.
- `log_gdp_pc` is constructed from official IBGE municipal GDP at current prices from SIDRA table `5938`, variable `37`, divided by resident population in the same survey year.
- These covariates were fetched because the repository did not already contain a clean municipality-year GDP/population file.

## How Interaction Effects Were Computed

Each interaction model fits:

`outcome ~ treatment_dummy * interaction_var + controls + municipality FE + survey-year FE`

The saved interaction outputs then compute:

1. the base-group treatment effect as the coefficient on `treatment_dummy`,
2. the interacted-group treatment effect as `treatment_dummy + treatment_dummy:interaction_var`,
3. the interaction difference as the interaction coefficient itself,
4. the interacted-group standard error from the full fitted covariance matrix.

## How The Plots Were Built

- Single-outcome figures use two bars per category, labeled `No` and `Yes`.
- Whiskers show 95% confidence intervals.
- The interaction difference is printed above each pair with stars based on the interaction p-value.
- Trust plots use a dark-slate palette and democracy plots use a brown palette, following the existing project conventions.

## Deviations From The Notebook Request

- No executable LAPOP notebook file was present in the repository during this build, so the regression specification was reconstructed from the manuscript scaffold, the harmonization notes, the PCA notes, and the requested design target.
- The clean LAPOP file uses actual years `2008, 2010, 2012, 2014, 2017, 2019`, so the main sample restriction `survey_year <= 2018` corresponds to `2008, 2010, 2012, 2014, 2017`.
- `pyfixest` could not be installed cleanly in this environment because `llvmlite` required a local LLVM configuration. The reusable regression skill therefore runs a documented `statsmodels` fixed-effects fallback.

## Main Outputs

- `resources/lapop/regressions/trust_interactions/`
- `resources/lapop/regressions/democracy_interactions/`
- `resources/lapop/figures/trust_interactions_barplot.pdf`
- `resources/lapop/figures/democracy_interactions_barplot.pdf`
- `resources/tables/lapop_trust_interactions_main_table.tex`
"""
    NOTES_PATH.write_text(notes + "\n", encoding="utf-8")

    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    unmatched_preview = summary["unmatched_pairs"].head(10).to_string(index=False)
    log_text = f"""# LAPOP Trust Regressions Log

- Timestamp: `{timestamp}`
- Regression-ready dataset: `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready.parquet`
- Trust config: `.agents/skills/regression-runner/examples/config_trust_interactions.yml`
- Democracy config: `.agents/skills/regression-runner/examples/config_democracy_interactions.yml`

## Sample Years

- Full years in regression-ready file: {summary['survey_years_all']}
- Main regression years used: {summary['survey_years_main']}

## Respondent Match Summary

- Total respondents: {summary['respondents_total']:,}
- Municipality matched: {summary['respondents_matched_to_municipality']:,}
- Municipality unmatched: {summary['respondents_unmatched_to_municipality']:,}
- Manual override matches: {summary['respondents_with_manual_override']:,}
- Respondents with municipal covariates: {summary['respondents_with_covariates']:,}

## Estimation Sample Sizes By Category

### Trust

{pd.Series(trust_ns).to_string()}

### Democracy

{pd.Series(democracy_ns).to_string()}

## Output Files

- `resources/lapop/regressions/trust_interactions/config_used.yml`
- `resources/lapop/regressions/trust_interactions/tidy_results.csv`
- `resources/lapop/regressions/trust_interactions/interaction_effects.csv`
- `resources/lapop/regressions/trust_interactions/model_summaries.txt`
- `resources/lapop/regressions/trust_interactions/regression_table.csv`
- `resources/lapop/regressions/trust_interactions/regression_table.tex`
- `resources/lapop/regressions/democracy_interactions/config_used.yml`
- `resources/lapop/regressions/democracy_interactions/tidy_results.csv`
- `resources/lapop/regressions/democracy_interactions/interaction_effects.csv`
- `resources/lapop/regressions/democracy_interactions/model_summaries.txt`
- `resources/lapop/regressions/democracy_interactions/regression_table.csv`
- `resources/lapop/regressions/democracy_interactions/regression_table.tex`
- `resources/lapop/figures/trust_interactions_barplot.pdf`
- `resources/lapop/figures/democracy_interactions_barplot.pdf`
- `resources/tables/lapop_trust_interactions_main_table.tex`

## Unmatched Municipality-State Pairs

```text
{unmatched_preview}
```

## Warnings And Deviations

- No executable LAPOP notebook file was available in the repo, so notebook logic was reconstructed from existing notes and the requested design target.
- `pyfixest` installation failed because `llvmlite` could not build without a local LLVM configuration; the regression skill used the documented `statsmodels` fixed-effects fallback.
- The second clustering dimension has only a handful of survey-year groups in the main sample, so inference should be interpreted with that limitation in mind.
"""
    LOG_PATH.write_text(log_text + "\n", encoding="utf-8")


def main() -> None:
    REG_READY_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    summary = build_regression_ready_dataset()[1]
    run_regressions()
    combined_table = build_main_table()
    write_notes_and_log(summary, combined_table)
    print("Regression-ready dataset:", REG_READY_PARQUET.relative_to(ROOT))
    print("Main sample years:", summary["survey_years_main"])
    print("Matched respondents:", summary["respondents_matched_to_municipality"])
    print("Main table:", MAIN_TABLE_TEX_PATH.relative_to(ROOT))


if __name__ == "__main__":
    main()
