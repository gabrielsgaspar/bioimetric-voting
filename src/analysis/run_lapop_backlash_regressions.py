from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pyreadstat
import statsmodels.formula.api as smf


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "src" / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from debug_lapop_benchmark_figures import (  # noqa: E402
    INDIVIDUAL_VARS,
    NAMED_VARS,
    OUTCOME_VARS,
    _apply_notebook_recodes,
    _build_ibge_lookup,
    _merge_wave_to_municipality_ids,
    _rename_from_raw,
    _resolve_actual_columns,
)
from run_lapop_trust_regressions import (  # noqa: E402
    TREATMENT_PATH,
    fetch_sidra_series_by_year,
)


RAW_2021_PATH = ROOT / "data" / "raw" / "lapop" / "2021" / "bra_2021_cy_spa-eng_p_v1-2.dta"
REG_READY_PARQUET = ROOT / "data" / "clean" / "lapop" / "lapop_brazil_backlash_2021_regression_ready.parquet"
REG_READY_CSV = ROOT / "data" / "clean" / "lapop" / "lapop_brazil_backlash_2021_regression_ready.csv"
POP_2021_PARQUET = ROOT / "data" / "clean" / "ibge" / "municipality_population_2021.parquet"
POP_2021_CSV = ROOT / "data" / "clean" / "ibge" / "municipality_population_2021.csv"

OUTPUT_DIR = ROOT / "resources" / "lapop" / "regressions" / "backlash_2021"
TIDY_RESULTS_CSV = OUTPUT_DIR / "tidy_results.csv"
MODEL_SUMMARIES_TXT = OUTPUT_DIR / "model_summaries.txt"
MERGE_SUMMARY_CSV = OUTPUT_DIR / "merge_summary.csv"
CONFIG_PATH = OUTPUT_DIR / "config_used.yml"
TABLE_CSV = ROOT / "resources" / "tables" / "lapop_backlash_2021_main_table.csv"
TABLE_TEX = ROOT / "resources" / "tables" / "lapop_backlash_2021_main_table.tex"
NOTES_PATH = ROOT / "docs" / "LAPOP_BACKLASH_REGRESSIONS_NOTES.md"
LOG_PATH = ROOT / "resources" / "logs" / "lapop_backlash_regressions_log.md"

CONTROL_VARS = ["low_ed", "female", "white", "age", "urban", "log_total_pop"]
CONTROL_FORMULA = " + ".join(CONTROL_VARS)

OUTCOME_SPECS = [
    {
        "name": "count_fair_always",
        "label": "Count Fair",
        "source_var": "count_votes_fair",
        "success_values": [1],
        "failure_values": [2, 3],
    },
    {
        "name": "ballot_secret_never",
        "label": "Ballot Secret",
        "source_var": "count_votes_find",
        "success_values": [3],
        "failure_values": [1, 2],
    },
]

MODEL_SPECS = [
    {
        "name": "baseline",
        "label": "No",
        "formula": "outcome ~ treatment_dummy + bolsonaro_approve + " + CONTROL_FORMULA,
    },
    {
        "name": "interaction",
        "label": "Yes",
        "formula": "outcome ~ treatment_dummy * bolsonaro_approve + " + CONTROL_FORMULA,
    },
]

TABLE_ROWS = [
    ("treatment_dummy", "BVR"),
    ("bolsonaro_approve", "Bolsonaro approval"),
    ("treatment_dummy:bolsonaro_approve", "BVR x Bolsonaro approval"),
]


def _ensure_dirs() -> None:
    for path in [
        REG_READY_PARQUET.parent,
        POP_2021_PARQUET.parent,
        OUTPUT_DIR,
        TABLE_TEX.parent,
        NOTES_PATH.parent,
        LOG_PATH.parent,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def _stars(p_value: float) -> str:
    if pd.isna(p_value):
        return ""
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return ""


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


def _format_cell(estimate: float | None, std_error: float | None, p_value: float | None) -> str:
    if estimate is None or pd.isna(estimate):
        return ""
    return f"{estimate:.3f}{_stars(float(p_value))}\\\\ ({std_error:.3f})"


def _load_public_2021_wave() -> pd.DataFrame:
    if not RAW_2021_PATH.exists():
        raise FileNotFoundError(f"Could not locate the public Brazil 2021 LAPOP file at {RAW_2021_PATH}")

    _, meta = pyreadstat.read_dta(RAW_2021_PATH, metadataonly=True)
    meta_columns = meta.column_names
    named_columns = _resolve_actual_columns(meta_columns, NAMED_VARS)
    numeric_columns = _resolve_actual_columns(meta_columns, INDIVIDUAL_VARS + OUTCOME_VARS + ["m1"])

    named_df, _ = pyreadstat.read_dta(RAW_2021_PATH, usecols=named_columns, apply_value_formats=True)
    numeric_df, _ = pyreadstat.read_dta(RAW_2021_PATH, usecols=numeric_columns, apply_value_formats=False)
    numeric_df.columns = [column.lower() for column in numeric_df.columns]

    wave = pd.concat([_rename_from_raw(named_df), _rename_from_raw(numeric_df)], axis=1)
    wave = wave.loc[:, ~wave.columns.duplicated()].copy()
    wave = wave.loc[wave["municipality_name"].notna() & wave["state_name"].notna()].copy()
    wave = _apply_notebook_recodes(wave, 2021)
    wave["survey_year"] = 2021
    wave["lapop_source_file"] = RAW_2021_PATH.name
    return wave


def _build_population_2021() -> pd.DataFrame:
    population = fetch_sidra_series_by_year(
        table_id="6579",
        variable_id="9324",
        years=[2021],
        value_name="total_pop",
    ).rename(columns={"year": "survey_year"})
    population["municipality_id"] = population["municipality_id"].astype(str).str.zfill(7)
    population["log_total_pop"] = np.log(population["total_pop"])
    population = population[["municipality_id", "survey_year", "total_pop", "log_total_pop"]].copy()
    population.to_parquet(POP_2021_PARQUET, index=False)
    population.to_csv(POP_2021_CSV, index=False)
    return population


def _build_regression_ready_dataset() -> tuple[pd.DataFrame, dict[str, object]]:
    wave = _load_public_2021_wave()
    ibge_lookup = _build_ibge_lookup()
    merged = _merge_wave_to_municipality_ids(wave, ibge_lookup)
    merged["municipality_id"] = merged["municipality_id"].astype(str).str.zfill(7)
    merged["matched_to_municipality"] = merged["matched_to_municipality"].fillna(False)

    treatment = pd.read_parquet(TREATMENT_PATH)[["municipality_id", "year_first_treat"]].copy()
    treatment["municipality_id"] = treatment["municipality_id"].astype(str).str.zfill(7)
    merged = merged.merge(treatment, on="municipality_id", how="left", validate="m:1")
    merged["year_first_treat"] = merged["year_first_treat"].fillna(9999).astype(int)
    merged["treatment_dummy"] = (
        merged["matched_to_municipality"] & (merged["year_first_treat"] <= merged["survey_year"])
    ).astype(int)

    population = _build_population_2021()
    merged = merged.merge(
        population,
        on=["municipality_id", "survey_year"],
        how="left",
        validate="m:1",
    )

    merged["low_ed"] = np.where(merged["ed"].eq("ES"), 1.0, np.where(merged["ed"].notna(), 0.0, np.nan))
    merged["bolsonaro_approve"] = np.where(
        merged["m1"].isin([1, 2]),
        1.0,
        np.where(merged["m1"].isin([3, 4, 5]), 0.0, np.nan),
    )

    for spec in OUTCOME_SPECS:
        source = merged[spec["source_var"]]
        merged[spec["name"]] = np.where(
            source.isin(spec["success_values"]),
            1.0,
            np.where(source.isin(spec["failure_values"]), 0.0, np.nan),
        )

    merged.to_parquet(REG_READY_PARQUET, index=False)
    merged.to_csv(REG_READY_CSV, index=False)

    summary = {
        "rows_total": int(len(merged)),
        "rows_matched": int(merged["matched_to_municipality"].sum()),
        "rows_unmatched": int((~merged["matched_to_municipality"]).sum()),
        "unique_municipalities_matched": int(merged.loc[merged["matched_to_municipality"], "municipality_id"].nunique()),
        "treated_share_matched": float(merged.loc[merged["matched_to_municipality"], "treatment_dummy"].mean()),
        "approval_share_matched": float(merged.loc[merged["matched_to_municipality"], "bolsonaro_approve"].mean()),
    }
    return merged, summary


def _fit_models(reg_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    tidy_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for outcome_spec in OUTCOME_SPECS:
        outcome = outcome_spec["name"]
        required_columns = [outcome, "municipality_id", "wt", "treatment_dummy", "bolsonaro_approve"] + CONTROL_VARS
        for model_spec in MODEL_SPECS:
            model_df = reg_df.loc[reg_df["matched_to_municipality"], required_columns].dropna().copy()
            model_df = model_df.rename(columns={outcome: "outcome"})

            fitted = smf.wls(
                formula=model_spec["formula"],
                data=model_df,
                weights=model_df["wt"],
            ).fit(cov_type="cluster", cov_kwds={"groups": model_df["municipality_id"]})

            dep_mean_weighted = float(np.average(model_df["outcome"], weights=model_df["wt"]))
            dep_mean_unweighted = float(model_df["outcome"].mean())
            n_obs = int(len(model_df))
            n_clusters = int(model_df["municipality_id"].nunique())

            for term in fitted.params.index:
                tidy_rows.append(
                    {
                        "outcome": outcome,
                        "outcome_label": outcome_spec["label"],
                        "model": model_spec["name"],
                        "interaction": model_spec["label"],
                        "term": term,
                        "estimate": float(fitted.params[term]),
                        "std_error": float(fitted.bse[term]),
                        "p_value": float(fitted.pvalues[term]),
                        "n_obs": n_obs,
                        "n_clusters": n_clusters,
                        "r_squared": float(fitted.rsquared),
                        "dep_mean_weighted": dep_mean_weighted,
                        "dep_mean_unweighted": dep_mean_unweighted,
                    }
                )

            summary_rows.append(
                {
                    "outcome": outcome,
                    "outcome_label": outcome_spec["label"],
                    "model": model_spec["name"],
                    "interaction": model_spec["label"],
                    "n_obs": n_obs,
                    "n_clusters": n_clusters,
                    "r_squared": float(fitted.rsquared),
                    "dep_mean_weighted": dep_mean_weighted,
                    "dep_mean_unweighted": dep_mean_unweighted,
                    "treated_share": float(model_df["treatment_dummy"].mean()),
                    "approval_share": float(model_df["bolsonaro_approve"].mean()),
                }
            )

    tidy = pd.DataFrame(tidy_rows)
    summary = pd.DataFrame(summary_rows)
    return tidy, summary


def _build_table(tidy: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    column_map = {
        ("count_fair_always", "baseline"): "1",
        ("count_fair_always", "interaction"): "2",
        ("ballot_secret_never", "baseline"): "3",
        ("ballot_secret_never", "interaction"): "4",
    }

    table_rows: list[dict[str, object]] = []
    for term, label in TABLE_ROWS:
        row: dict[str, object] = {"term": label}
        for (outcome, model_name), column in column_map.items():
            subset = tidy.loc[(tidy["outcome"] == outcome) & (tidy["model"] == model_name) & (tidy["term"] == term)]
            if subset.empty:
                row[column] = ""
                continue
            result = subset.iloc[0]
            row[column] = _format_cell(result["estimate"], result["std_error"], result["p_value"])
        table_rows.append(row)

    interaction_row = {"term": "Interaction included"}
    n_row = {"term": "Observations"}
    clusters_row = {"term": "Municipalities"}
    mean_row = {"term": "Weighted mean of dependent variable"}
    r2_row = {"term": "$R^2$"}

    for (outcome, model_name), column in column_map.items():
        model_summary = summary.loc[(summary["outcome"] == outcome) & (summary["model"] == model_name)].iloc[0]
        interaction_row[column] = "Yes" if model_name == "interaction" else "No"
        n_row[column] = f"{int(model_summary['n_obs'])}"
        clusters_row[column] = f"{int(model_summary['n_clusters'])}"
        mean_row[column] = f"{float(model_summary['dep_mean_weighted']):.3f}"
        r2_row[column] = f"{float(model_summary['r_squared']):.3f}"

    table_rows.extend([interaction_row, n_row, clusters_row, mean_row, r2_row])
    table_df = pd.DataFrame(table_rows)
    table_df.to_csv(TABLE_CSV, index=False)
    return table_df


def _write_tex_table(table_df: pd.DataFrame) -> None:
    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcccc}",
        r"\doubletoprule",
        r" & \multicolumn{2}{c}{Count Fair} & \multicolumn{2}{c}{Ballot Secret} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
        r" & (1) & (2) & (3) & (4) \\",
        r"\midrule",
    ]

    body_terms = set(label for _, label in TABLE_ROWS)
    for row in table_df.to_dict(orient="records"):
        if row["term"] not in body_terms:
            continue
        lines.append(
            f"{_tex_escape(str(row['term']))} & {row['1']} & {row['2']} & {row['3']} & {row['4']} \\\\"
        )

    lines.extend(
        [
            r"\midrule",
            f"Interaction included & {table_df.loc[table_df['term'] == 'Interaction included', '1'].iloc[0]} & {table_df.loc[table_df['term'] == 'Interaction included', '2'].iloc[0]} & {table_df.loc[table_df['term'] == 'Interaction included', '3'].iloc[0]} & {table_df.loc[table_df['term'] == 'Interaction included', '4'].iloc[0]} \\\\",
            f"Observations & {table_df.loc[table_df['term'] == 'Observations', '1'].iloc[0]} & {table_df.loc[table_df['term'] == 'Observations', '2'].iloc[0]} & {table_df.loc[table_df['term'] == 'Observations', '3'].iloc[0]} & {table_df.loc[table_df['term'] == 'Observations', '4'].iloc[0]} \\\\",
            f"Municipalities & {table_df.loc[table_df['term'] == 'Municipalities', '1'].iloc[0]} & {table_df.loc[table_df['term'] == 'Municipalities', '2'].iloc[0]} & {table_df.loc[table_df['term'] == 'Municipalities', '3'].iloc[0]} & {table_df.loc[table_df['term'] == 'Municipalities', '4'].iloc[0]} \\\\",
            f"Weighted mean of dependent variable & {table_df.loc[table_df['term'] == 'Weighted mean of dependent variable', '1'].iloc[0]} & {table_df.loc[table_df['term'] == 'Weighted mean of dependent variable', '2'].iloc[0]} & {table_df.loc[table_df['term'] == 'Weighted mean of dependent variable', '3'].iloc[0]} & {table_df.loc[table_df['term'] == 'Weighted mean of dependent variable', '4'].iloc[0]} \\\\",
            f"$R^2$ & {table_df.loc[table_df['term'] == '$R^2$', '1'].iloc[0]} & {table_df.loc[table_df['term'] == '$R^2$', '2'].iloc[0]} & {table_df.loc[table_df['term'] == '$R^2$', '3'].iloc[0]} & {table_df.loc[table_df['term'] == '$R^2$', '4'].iloc[0]} \\\\",
            r"\doublebottomrule",
            r"\end{tabular*}",
        ]
    )

    TABLE_TEX.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_notes(summary: dict[str, object], tidy: pd.DataFrame, model_summary: pd.DataFrame) -> None:
    fair_interaction = tidy.loc[
        (tidy["outcome"] == "count_fair_always")
        & (tidy["model"] == "interaction")
        & (tidy["term"] == "treatment_dummy:bolsonaro_approve")
    ].iloc[0]
    secrecy_interaction = tidy.loc[
        (tidy["outcome"] == "ballot_secret_never")
        & (tidy["model"] == "interaction")
        & (tidy["term"] == "treatment_dummy:bolsonaro_approve")
    ].iloc[0]

    notes = f"""# LAPOP Backlash Regressions Notes

## Why This Uses The 2021 Public File

- The draft section in `backlash.tex` was written as a `2023` LAPOP exercise tied to the `2022` presidential election.
- On April 23, 2026, the official Vanderbilt Brazil country page listed a `2023` Brazil study and linked its technical report, but the public dataset app route `https://lapop.app.vanderbilt.edu/datasets/download/bra_2023` returned an HTTP 500 error in this environment.
- The official public microdata file available locally and reproducibly in the repository is therefore `data/raw/lapop/2021/bra_2021_cy_spa-eng_p_v1-2.dta`.
- The public `2021` file contains the electoral-integrity battery (`countfair1` and `countfair3`) but does not expose an individual presidential vote-choice variable.
- The public `2019` file contains presidential vote choice (`vb3n`) but does not contain the `countfair` battery.
- The implemented section therefore keeps the same interaction design as the draft but uses `m1` (approval of the executive) as a respondent-level proxy for Bolsonaro alignment in the `2021` public wave.

## Inputs

- LAPOP public wave: `{RAW_2021_PATH.relative_to(ROOT)}`
- Municipal BVR treatment timing: `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`
- Municipal population control fetched from official IBGE SIDRA table `6579`, variable `9324`, year `2021`

## Variable Construction

- `count_fair_always` = 1 when `countfair1 == 1` (`Siempre`), 0 when `countfair1` is `Algunas veces` or `Nunca`
- `ballot_secret_never` = 1 when `countfair3 == 3` (`Nunca`), 0 when `countfair3` is `Siempre` or `Algunas veces`
- `bolsonaro_approve` = 1 when `m1` is `Muy bueno` or `Bueno`, 0 when `m1` is `Ni bueno, ni malo`, `Malo`, or `Muy malo`
- `treatment_dummy` = 1 when the respondent lives in a municipality with `year_first_treat <= 2021`
- Controls retained in the integrity module sample: `low_ed`, `female`, `white`, `age`, `urban`, `log_total_pop`

## Matching Summary

- LAPOP rows with municipality/state labels: {summary['rows_total']}
- Rows matched to IBGE municipality IDs: {summary['rows_matched']}
- Rows unmatched to IBGE municipality IDs: {summary['rows_unmatched']}
- Unique matched municipalities: {summary['unique_municipalities_matched']}
- Treated share in the matched 2021 sample: {summary['treated_share_matched']:.3f}
- Bolsonaro-approval share in the matched 2021 sample: {summary['approval_share_matched']:.3f}

## Main Results

- Count-fair interaction estimate: {fair_interaction['estimate']:.3f} (s.e. {fair_interaction['std_error']:.3f}, p = {fair_interaction['p_value']:.3f})
- Ballot-secrecy interaction estimate: {secrecy_interaction['estimate']:.3f} (s.e. {secrecy_interaction['std_error']:.3f}, p = {secrecy_interaction['p_value']:.3f})

## Interpretation Boundary

- These are weighted cross-sectional linear-probability models with municipality-clustered standard errors.
- Because the public `2021` file does not include individual presidential vote recall, the section should refer to `Bolsonaro approval` or `Bolsonaro-aligned respondents`, not to `voting for Bolsonaro in 2022`.
- The estimates should be read as suggestive associations rather than causal effects.
"""
    NOTES_PATH.write_text(notes, encoding="utf-8")

    merge_summary = pd.DataFrame([summary])
    merge_summary.to_csv(MERGE_SUMMARY_CSV, index=False)

    summary_lines: list[str] = []
    for row in model_summary.itertuples(index=False):
        summary_lines.extend(
            [
                f"Outcome: {row.outcome_label}",
                f"Model: {row.model}",
                f"Interaction included: {row.interaction}",
                f"Observations: {row.n_obs}",
                f"Municipalities: {row.n_clusters}",
                f"Weighted mean of dependent variable: {row.dep_mean_weighted:.4f}",
                f"R-squared: {row.r_squared:.4f}",
                "",
            ]
        )
    MODEL_SUMMARIES_TXT.write_text("\n".join(summary_lines).strip() + "\n", encoding="utf-8")


def _write_config() -> None:
    config_text = "\n".join(
        [
            "run_type: lapop_backlash_public_wave_2021",
            f"lapop_data_path: {RAW_2021_PATH.relative_to(ROOT)}",
            f"regression_ready_path: {REG_READY_PARQUET.relative_to(ROOT)}",
            f"population_2021_path: {POP_2021_PARQUET.relative_to(ROOT)}",
            "survey_year: 2021",
            "support_proxy: m1 -> bolsonaro_approve",
            "outcomes:",
            "  - count_fair_always",
            "  - ballot_secret_never",
            "controls:",
            *[f"  - {column}" for column in CONTROL_VARS],
            "weights: wt",
            "cluster:",
            "  - municipality_id",
        ]
    )
    CONFIG_PATH.write_text(config_text + "\n", encoding="utf-8")


def _write_log(summary: dict[str, object], tidy: pd.DataFrame) -> None:
    fair_interaction = tidy.loc[
        (tidy["outcome"] == "count_fair_always")
        & (tidy["model"] == "interaction")
        & (tidy["term"] == "treatment_dummy:bolsonaro_approve")
    ].iloc[0]
    secrecy_interaction = tidy.loc[
        (tidy["outcome"] == "ballot_secret_never")
        & (tidy["model"] == "interaction")
        & (tidy["term"] == "treatment_dummy:bolsonaro_approve")
    ].iloc[0]

    log_text = f"""# LAPOP Backlash Regressions Log

- Timestamp (UTC): {datetime.now(timezone.utc).isoformat()}
- Public LAPOP file used: `{RAW_2021_PATH.relative_to(ROOT)}`
- Rows matched to municipalities: {summary['rows_matched']} of {summary['rows_total']}
- Treated share in matched sample: {summary['treated_share_matched']:.3f}
- Count-fair interaction estimate: {fair_interaction['estimate']:.3f} (p = {fair_interaction['p_value']:.3f})
- Ballot-secrecy interaction estimate: {secrecy_interaction['estimate']:.3f} (p = {secrecy_interaction['p_value']:.3f})
"""
    LOG_PATH.write_text(log_text, encoding="utf-8")


def main() -> None:
    _ensure_dirs()
    reg_df, summary = _build_regression_ready_dataset()
    tidy, model_summary = _fit_models(reg_df)
    tidy.to_csv(TIDY_RESULTS_CSV, index=False)
    table_df = _build_table(tidy, model_summary)
    _write_tex_table(table_df)
    _write_config()
    _write_notes(summary, tidy, model_summary)
    _write_log(summary, tidy)


if __name__ == "__main__":
    main()
