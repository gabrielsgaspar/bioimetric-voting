from __future__ import annotations

import math
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

INPUT_PARQUET = ROOT / "data" / "clean" / "lapop" / "lapop_brazil_with_pca_indices_regression_ready_corrected.parquet"
TREATMENT_PARQUET = ROOT / "data" / "clean" / "tse_bvr" / "municipality_bvr_first_treat.parquet"
OUTPUT_PARQUET = ROOT / "data" / "clean" / "lapop" / "lapop_brazil_individual_event_time.parquet"
OUTPUT_CSV = ROOT / "data" / "clean" / "lapop" / "lapop_brazil_individual_event_time.csv"

REGRESSION_DIR = ROOT / "resources" / "lapop" / "regressions" / "individual_event_time"
FIGURE_DIR = ROOT / "resources" / "lapop" / "figures"
TABLES_DIR = ROOT / "resources" / "tables"

MAIN_RESULTS_CSV = REGRESSION_DIR / "main_results.csv"
EVENT_RESULTS_CSV = REGRESSION_DIR / "event_study_results.csv"
SAMPLE_SUMMARY_CSV = REGRESSION_DIR / "sample_summary.csv"
MODEL_NOTES_MD = REGRESSION_DIR / "model_notes.md"

MAIN_TABLE_TEX = TABLES_DIR / "lapop_individual_level_main_table.tex"

EVENT_FIGURES = {
    ("trust_index_std", "all"): FIGURE_DIR / "individual_event_study_trust_all.pdf",
    ("democracy_index_std", "all"): FIGURE_DIR / "individual_event_study_democracy_all.pdf",
    ("trust_index_std", "no_hybrid"): FIGURE_DIR / "individual_event_study_trust_no_hybrid.pdf",
    ("democracy_index_std", "no_hybrid"): FIGURE_DIR / "individual_event_study_democracy_no_hybrid.pdf",
}

LEGACY_EVENT_FIGURES = {
    "trust_index_std": FIGURE_DIR / "individual_event_study_trust.pdf",
    "democracy_index_std": FIGURE_DIR / "individual_event_study_democracy.pdf",
}

MIN_YEAR = 2005
MAX_YEAR = 2020
REFERENCE_EVENT_TIME = -2
EVENT_TIMES = [-8, -6, -4, -2, 0, 2, 4, 6, 8]
EVENT_DUMMIES = {k: f"event_{'m' + str(abs(k)) if k < 0 else 'p' + str(k)}" for k in EVENT_TIMES if k != REFERENCE_EVENT_TIME}

INDIVIDUAL_CONTROLS = ["low_ed", "female", "white", "married", "working", "age", "age_sq", "age_cu"]
OUTCOME_LABELS = {
    "trust_index_std": "Trust in institutions",
    "democracy_index_std": "Trust in democracy",
}
EVENT_COLOR = {
    "trust_index_std": "#294C60",
    "democracy_index_std": "#7A4E2D",
}


def _ensure_dirs() -> None:
    for path in [OUTPUT_PARQUET.parent, REGRESSION_DIR, FIGURE_DIR, TABLES_DIR]:
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


def _fmt(value: float, digits: int = 3) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.{digits}f}"


def _fmt_int(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{int(value):,}"


def _read_input() -> pd.DataFrame:
    if not INPUT_PARQUET.exists():
        raise FileNotFoundError(f"Could not find input file: {INPUT_PARQUET}")
    if not TREATMENT_PARQUET.exists():
        raise FileNotFoundError(f"Could not find treatment file: {TREATMENT_PARQUET}")

    df = pd.read_parquet(INPUT_PARQUET)
    treatment = pd.read_parquet(TREATMENT_PARQUET)[["municipality_id", "year_first_treat"]].copy()
    treatment["municipality_id"] = treatment["municipality_id"].astype("string")
    treatment = treatment.rename(columns={"year_first_treat": "year_first_treat_project"})

    df["municipality_id"] = df["municipality_id"].astype("string")
    df = df.merge(treatment, on="municipality_id", how="left", validate="many_to_one")
    df["year_first_treat"] = pd.to_numeric(df["year_first_treat_project"], errors="coerce").fillna(9999).astype(int)
    df = df.drop(columns=["year_first_treat_project"])
    return df


def _bin_event_time(value: float, treat_year: float) -> float:
    if pd.isna(treat_year) or int(treat_year) >= 9999 or pd.isna(value):
        return np.nan
    if value <= -8:
        return -8
    if value >= 8:
        return 8
    return int(2 * math.floor(value / 2))


def _balanced_municipalities(df: pd.DataFrame) -> tuple[list[str], list[int]]:
    year_window = df[(df["year"] >= MIN_YEAR) & (df["year"] <= MAX_YEAR) & df["municipality_id"].notna()].copy()
    wave_years = sorted(int(year) for year in year_window["year"].dropna().unique())
    counts = year_window.groupby("municipality_id")["year"].nunique()
    municipalities = sorted(str(muni) for muni in counts[counts == len(wave_years)].index)
    return municipalities, wave_years


def build_individual_event_time_dataset() -> pd.DataFrame:
    df = _read_input().copy()

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["survey_year"] = pd.to_numeric(df["survey_year"], errors="coerce")
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["year_first_treat"] = pd.to_numeric(df["year_first_treat"], errors="coerce").fillna(9999).astype(int)
    df["municipality_id"] = df["municipality_id"].astype("string")

    balanced_municipalities, wave_years = _balanced_municipalities(df)
    df["balanced_municipality_all_waves"] = df["municipality_id"].isin(balanced_municipalities).astype(int)
    df["analysis_wave_years"] = ",".join(str(year) for year in wave_years)

    df = df[
        (df["year"] >= MIN_YEAR)
        & (df["year"] <= MAX_YEAR)
        & df["municipality_id"].isin(balanced_municipalities)
        & df["age"].ge(18)
    ].copy()

    age_floor = np.floor(df["age"])
    df["interview_year_for_event_time"] = df["year"]
    df["first_eligible_year"] = df["interview_year_for_event_time"] - age_floor + 18

    treated_by_interview = df["year_first_treat"].lt(9999) & df["year_first_treat"].le(df["interview_year_for_event_time"])
    df["treatment_dummy"] = treated_by_interview.astype(int)
    first_entry_under_bvr = treated_by_interview & df["first_eligible_year"].ge(df["year_first_treat"])
    mixed = treated_by_interview & df["first_eligible_year"].lt(df["year_first_treat"])

    df["registered_under_bvr"] = first_entry_under_bvr.astype("Int64")
    df["mixed_cohort"] = mixed.astype("Int64")
    df["T_im"] = np.select([first_entry_under_bvr, mixed], [1, -1], default=0).astype(int)

    finite_treat = df["year_first_treat"].lt(9999)
    exposure_start = np.maximum(df["year_first_treat"], df["first_eligible_year"])
    df["event_time"] = df["interview_year_for_event_time"] - exposure_start
    df.loc[~finite_treat | df["event_time"].isna(), "event_time"] = np.nan
    df["event_time_bin"] = [
        _bin_event_time(event_value, treat_year)
        for event_value, treat_year in zip(df["event_time"], df["year_first_treat"], strict=False)
    ]

    for event_time, column in EVENT_DUMMIES.items():
        df[column] = (df["event_time_bin"] == event_time).astype(int)

    df["age_sq"] = df["age"] ** 2
    df["age_cu"] = df["age"] ** 3
    df["muni_year"] = (
        df["municipality_id"].astype("string").fillna("missing")
        + "_"
        + df["year"].astype("Int64").astype("string").fillna("missing")
    )
    df["no_hybrid_sample"] = (pd.to_numeric(df["is_hybrid"], errors="coerce").fillna(0).eq(0)).astype(int)

    df.to_parquet(OUTPUT_PARQUET, index=False)
    df.to_csv(OUTPUT_CSV, index=False)
    return df


def _r_script_contents() -> str:
    event_terms = " + ".join(EVENT_DUMMIES.values())
    event_names_r = "c(" + ",".join(f'"{name}"' for name in EVENT_DUMMIES.values()) + ")"
    event_times_r = "c(" + ",".join(str(k) for k in EVENT_DUMMIES) + ")"
    controls_r = " + ".join(INDIVIDUAL_CONTROLS)
    return rf'''
suppressPackageStartupMessages({{
  library(arrow)
  library(dplyr)
  library(fixest)
}})

args <- commandArgs(trailingOnly = TRUE)
data_path <- args[1]
main_results_path <- args[2]
event_results_path <- args[3]
sample_summary_path <- args[4]

df <- read_parquet(data_path)

numeric_cols <- c(
  "year", "survey_year", "year_first_treat", "age", "age_sq", "age_cu",
  "treatment_dummy", "registered_under_bvr", "mixed_cohort", "T_im",
  "low_ed", "female", "white", "married", "working", "trust_index_std",
  "democracy_index_std", "is_hybrid", "no_hybrid_sample", "event_time",
  "event_time_bin", {event_names_r}
)

for (column in numeric_cols) {{
  if (column %in% names(df)) {{
    df[[column]] <- suppressWarnings(as.numeric(df[[column]]))
  }}
}}

df <- df %>%
  mutate(
    municipality_id = as.character(municipality_id),
    year = as.integer(year),
    muni_year = as.character(muni_year)
  )

required <- c(
  "municipality_id", "year", "muni_year", "trust_index_std", "democracy_index_std",
  "treatment_dummy", "registered_under_bvr", "mixed_cohort", "low_ed",
  "female", "white", "married", "working", "age", "age_sq", "age_cu",
  {event_names_r}
)

main_df <- df %>%
  filter(if_all(all_of(required), ~ !is.na(.)))

no_hybrid_df <- main_df %>%
  filter(no_hybrid_sample == 1)

event_names <- {event_names_r}
event_times <- {event_times_r}

extract_row <- function(model, term, outcome, spec_name, sample_name) {{
  ct <- as.data.frame(coeftable(model))
  ct$term <- rownames(ct)
  row <- ct[ct$term == term, , drop = FALSE]
  if (nrow(row) != 1) {{
    stop(sprintf("Could not find term `%s` in `%s` for `%s`.", term, spec_name, outcome))
  }}
  data.frame(
    outcome = outcome,
    spec = spec_name,
    sample = sample_name,
    term = term,
    estimate = as.numeric(row$Estimate),
    std_error = as.numeric(row$`Std. Error`),
    p_value = as.numeric(row$`Pr(>|t|)`),
    n_obs = nobs(model),
    stringsAsFactors = FALSE
  )
}}

run_event_model <- function(data, outcome, sample_name) {{
  event_formula <- as.formula(
    sprintf(
      "%s ~ {event_terms} + {controls_r} | municipality_id + year",
      outcome
    )
  )
  model <- feols(event_formula, data = data, vcov = ~ muni_year)
  rows <- list()
  for (idx in seq_along(event_names)) {{
    term <- event_names[[idx]]
    ct <- as.data.frame(coeftable(model))
    ct$term <- rownames(ct)
    row <- ct[ct$term == term, , drop = FALSE]
    if (nrow(row) == 1) {{
      rows[[length(rows) + 1]] <- data.frame(
        outcome = outcome,
        sample = sample_name,
        event_time = event_times[[idx]],
        term = term,
        estimate = as.numeric(row$Estimate),
        std_error = as.numeric(row$`Std. Error`),
        p_value = as.numeric(row$`Pr(>|t|)`),
        n_obs = nobs(model),
        stringsAsFactors = FALSE
      )
    }}
  }}
  bind_rows(rows)
}}

main_results <- list()
event_results <- list()

for (outcome in c("trust_index_std", "democracy_index_std")) {{
  municipality_formula <- as.formula(
    sprintf(
      "%s ~ treatment_dummy * low_ed + female + white + married + working + age | municipality_id + year",
      outcome
    )
  )
  municipality_model <- feols(municipality_formula, data = main_df, vcov = ~ muni_year)

  itt_formula <- as.formula(
    sprintf(
      "%s ~ registered_under_bvr + mixed_cohort + {controls_r} | municipality_id + year",
      outcome
    )
  )
  itt_model <- feols(itt_formula, data = main_df, vcov = ~ muni_year)

  triple_formula <- as.formula(
    sprintf(
      "%s ~ registered_under_bvr * low_ed + mixed_cohort * low_ed + female + white + married + working + age + age_sq + age_cu | municipality_id + year",
      outcome
    )
  )
  triple_model <- feols(triple_formula, data = main_df, vcov = ~ muni_year)

  main_results[[length(main_results) + 1]] <- extract_row(municipality_model, "treatment_dummy", outcome, "municipality_level", "all")
  main_results[[length(main_results) + 1]] <- extract_row(municipality_model, "treatment_dummy:low_ed", outcome, "municipality_level", "all")
  main_results[[length(main_results) + 1]] <- extract_row(itt_model, "registered_under_bvr", outcome, "individual_itt", "all")
  main_results[[length(main_results) + 1]] <- extract_row(triple_model, "registered_under_bvr", outcome, "individual_triple_diff", "all")
  main_results[[length(main_results) + 1]] <- extract_row(triple_model, "registered_under_bvr:low_ed", outcome, "individual_triple_diff", "all")

  event_results[[length(event_results) + 1]] <- run_event_model(main_df, outcome, "all")
  event_results[[length(event_results) + 1]] <- run_event_model(no_hybrid_df, outcome, "no_hybrid")
}}

sample_summary <- bind_rows(
  data.frame(
    sample = "all",
    n_obs = nrow(main_df),
    n_municipalities = dplyr::n_distinct(main_df$municipality_id),
    n_muni_year = dplyr::n_distinct(main_df$muni_year),
    n_waves = dplyr::n_distinct(main_df$year),
    min_year = min(main_df$year),
    max_year = max(main_df$year),
    n_registered_under_bvr = sum(main_df$registered_under_bvr == 1, na.rm = TRUE),
    n_mixed_cohort = sum(main_df$mixed_cohort == 1, na.rm = TRUE),
    n_low_ed_registered_under_bvr = sum(main_df$registered_under_bvr == 1 & main_df$low_ed == 1, na.rm = TRUE),
    n_low_ed_mixed = sum(main_df$mixed_cohort == 1 & main_df$low_ed == 1, na.rm = TRUE),
    n_hybrid_rows = sum(main_df$no_hybrid_sample == 0, na.rm = TRUE),
    stringsAsFactors = FALSE
  ),
  data.frame(
    sample = "no_hybrid",
    n_obs = nrow(no_hybrid_df),
    n_municipalities = dplyr::n_distinct(no_hybrid_df$municipality_id),
    n_muni_year = dplyr::n_distinct(no_hybrid_df$muni_year),
    n_waves = dplyr::n_distinct(no_hybrid_df$year),
    min_year = min(no_hybrid_df$year),
    max_year = max(no_hybrid_df$year),
    n_registered_under_bvr = sum(no_hybrid_df$registered_under_bvr == 1, na.rm = TRUE),
    n_mixed_cohort = sum(no_hybrid_df$mixed_cohort == 1, na.rm = TRUE),
    n_low_ed_registered_under_bvr = sum(no_hybrid_df$registered_under_bvr == 1 & no_hybrid_df$low_ed == 1, na.rm = TRUE),
    n_low_ed_mixed = sum(no_hybrid_df$mixed_cohort == 1 & no_hybrid_df$low_ed == 1, na.rm = TRUE),
    n_hybrid_rows = sum(no_hybrid_df$no_hybrid_sample == 0, na.rm = TRUE),
    stringsAsFactors = FALSE
  )
)

write.csv(bind_rows(main_results), main_results_path, row.names = FALSE)
write.csv(bind_rows(event_results), event_results_path, row.names = FALSE)
write.csv(sample_summary, sample_summary_path, row.names = FALSE)
'''


def run_regressions() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as handle:
        handle.write(_r_script_contents())
        temp_script = Path(handle.name)

    try:
        subprocess.run(
            [
                "Rscript",
                str(temp_script),
                str(OUTPUT_PARQUET),
                str(MAIN_RESULTS_CSV),
                str(EVENT_RESULTS_CSV),
                str(SAMPLE_SUMMARY_CSV),
            ],
            check=True,
            cwd=ROOT,
        )
    finally:
        temp_script.unlink(missing_ok=True)


def _main_row(results: pd.DataFrame, outcome: str, spec: str, term: str) -> pd.Series:
    subset = results[(results["outcome"] == outcome) & (results["spec"] == spec) & (results["term"] == term)]
    if subset.empty:
        raise KeyError(f"Missing result for outcome={outcome}, spec={spec}, term={term}")
    return subset.iloc[0]


def build_main_table(main_results: pd.DataFrame, sample_summary: pd.DataFrame) -> None:
    benchmark = sample_summary.loc[sample_summary["sample"] == "all"].iloc[0]

    lines = [
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{lccc}",
        r"\doubletoprule",
        r" & (1) Municipality-level & (2) Individual ITT & (3) Individual triple-difference \\",
        r"\midrule",
    ]

    for panel_index, (outcome, label) in enumerate(OUTCOME_LABELS.items(), start=1):
        municipal_base = _main_row(main_results, outcome, "municipality_level", "treatment_dummy")
        municipal_interaction = _main_row(main_results, outcome, "municipality_level", "treatment_dummy:low_ed")
        itt_base = _main_row(main_results, outcome, "individual_itt", "registered_under_bvr")
        triple_base = _main_row(main_results, outcome, "individual_triple_diff", "registered_under_bvr")
        triple_interaction = _main_row(main_results, outcome, "individual_triple_diff", "registered_under_bvr:low_ed")

        lines.extend(
            [
                rf"\multicolumn{{4}}{{l}}{{\textit{{Panel {chr(64 + panel_index)}. {label}}}}} \\",
                rf"Baseline treatment effect & {_fmt(municipal_base['estimate'])}{_stars(municipal_base['p_value'])} & {_fmt(itt_base['estimate'])}{_stars(itt_base['p_value'])} & {_fmt(triple_base['estimate'])}{_stars(triple_base['p_value'])} \\",
                rf" & ({_fmt(municipal_base['std_error'])}) & ({_fmt(itt_base['std_error'])}) & ({_fmt(triple_base['std_error'])}) \\",
                rf"Treatment $\times$ low education & {_fmt(municipal_interaction['estimate'])}{_stars(municipal_interaction['p_value'])} &  & {_fmt(triple_interaction['estimate'])}{_stars(triple_interaction['p_value'])} \\",
                rf" & ({_fmt(municipal_interaction['std_error'])}) &  & ({_fmt(triple_interaction['std_error'])}) \\",
            ]
        )
        if panel_index < len(OUTCOME_LABELS):
            lines.append(r"\midrule")

    lines.extend(
        [
            r"\midrule",
            rf"Observations & {_fmt_int(benchmark['n_obs'])} & {_fmt_int(benchmark['n_obs'])} & {_fmt_int(benchmark['n_obs'])} \\",
            rf"Municipalities & {_fmt_int(benchmark['n_municipalities'])} & {_fmt_int(benchmark['n_municipalities'])} & {_fmt_int(benchmark['n_municipalities'])} \\",
            rf"Survey waves & {_fmt_int(benchmark['n_waves'])} & {_fmt_int(benchmark['n_waves'])} & {_fmt_int(benchmark['n_waves'])} \\",
            rf"Municipality-year cells & {_fmt_int(benchmark['n_muni_year'])} & {_fmt_int(benchmark['n_muni_year'])} & {_fmt_int(benchmark['n_muni_year'])} \\",
            rf"Always-BVR respondents &  & {_fmt_int(benchmark['n_registered_under_bvr'])} & {_fmt_int(benchmark['n_registered_under_bvr'])} \\",
            rf"Mixed-cohort respondents &  & {_fmt_int(benchmark['n_mixed_cohort'])} & {_fmt_int(benchmark['n_mixed_cohort'])} \\",
            r"\doublebottomrule",
            r"\end{tabular}",
            r"}",
            "",
            r"\begin{minipage}{\textwidth}",
            r"\footnotesize",
            rf"\textbf{{Note:}} Column~(1) keeps the current municipality-level BVR treatment assignment but re-estimates it on the balanced municipality sample used here. Columns~(2) and (3) use respondent-level exposure timing constructed from interview age and municipal rollout year. The sample is restricted to benchmark years {MIN_YEAR}--{MAX_YEAR}, respondents age 18 or older, and municipalities observed in every survey wave in that window. All columns include municipality and survey-year fixed effects and cluster standard errors by municipality-year cell. Individual controls are low education, female, white, married, working, and age; respondent-level columns add a cubic in age because exposure timing is age-imputed. The mixed cohort is retained as a separate control group in columns~(2) and (3), with coefficients omitted from the table.",
            r"\end{minipage}",
        ]
    )

    MAIN_TABLE_TEX.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _event_plot_frame(event_results: pd.DataFrame, outcome: str, sample: str) -> pd.DataFrame:
    df = event_results[(event_results["outcome"] == outcome) & (event_results["sample"] == sample)].copy()
    if df.empty:
        raise ValueError(f"No event-study rows found for outcome={outcome}, sample={sample}")
    reference = pd.DataFrame(
        {
            "outcome": [outcome],
            "sample": [sample],
            "event_time": [REFERENCE_EVENT_TIME],
            "term": ["reference"],
            "estimate": [0.0],
            "std_error": [np.nan],
            "p_value": [np.nan],
            "n_obs": [df["n_obs"].max()],
        }
    )
    df = pd.concat([df, reference], ignore_index=True)
    df = df.sort_values("event_time")
    df["ci_low"] = df["estimate"] - 1.96 * df["std_error"]
    df["ci_high"] = df["estimate"] + 1.96 * df["std_error"]
    return df


def build_event_study_plot(event_results: pd.DataFrame, outcome: str, sample: str, output_path: Path) -> None:
    df = _event_plot_frame(event_results, outcome, sample)

    fig, ax = plt.subplots(figsize=(6.75, 4.25))
    color = EVENT_COLOR[outcome]
    ci_df = df.dropna(subset=["std_error"]).copy()
    ax.axhline(0, color="black", linewidth=1.0, linestyle="--", alpha=0.75)
    ax.axvline(0, color="0.55", linewidth=1.0, linestyle=":")
    ax.errorbar(
        ci_df["event_time"],
        ci_df["estimate"],
        yerr=1.96 * ci_df["std_error"],
        fmt="o-",
        color=color,
        ecolor=color,
        elinewidth=1.4,
        capsize=3,
        markersize=5,
        linewidth=1.8,
    )
    ref = df[df["event_time"] == REFERENCE_EVENT_TIME]
    if not ref.empty:
        ax.scatter(ref["event_time"], ref["estimate"], color="black", s=28, zorder=4)
    ax.set_xticks(EVENT_TIMES)
    ax.set_xlim(min(EVENT_TIMES) - 0.5, max(EVENT_TIMES) + 0.5)
    ax.set_xlabel("Individual event time (reference = -2)")
    ax.set_ylabel("Coefficient")
    title_suffix = "excluding hybrid municipalities" if sample == "no_hybrid" else "all balanced municipalities"
    ax.set_title(f"{OUTCOME_LABELS[outcome]}: {title_suffix}")
    ax.grid(axis="y", linestyle=":", alpha=0.35)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)

    legacy_path = LEGACY_EVENT_FIGURES.get(outcome)
    if sample == "all" and legacy_path is not None:
        # Keep the old figure names alive for the manuscript until the section is
        # edited to point at the all/no-hybrid split.
        legacy_path.write_bytes(output_path.read_bytes())


def write_model_notes(sample_summary: pd.DataFrame, main_results: pd.DataFrame, event_results: pd.DataFrame) -> None:
    benchmark = sample_summary.loc[sample_summary["sample"] == "all"].iloc[0]
    no_hybrid = sample_summary.loc[sample_summary["sample"] == "no_hybrid"].iloc[0]
    trust_itt = _main_row(main_results, "trust_index_std", "individual_itt", "registered_under_bvr")
    trust_triple = _main_row(main_results, "trust_index_std", "individual_triple_diff", "registered_under_bvr:low_ed")
    democracy_triple = _main_row(main_results, "democracy_index_std", "individual_triple_diff", "registered_under_bvr:low_ed")

    text = "\n".join(
        [
            "# LAPOP Individual Event-Time Notes",
            "",
            f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"- Input file: `{INPUT_PARQUET.relative_to(ROOT)}`",
            f"- Treatment timing file: `{TREATMENT_PARQUET.relative_to(ROOT)}`",
            f"- Output file: `{OUTPUT_PARQUET.relative_to(ROOT)}`",
            "",
            "## Design choices",
            "",
            f"- Sample years use the benchmark `year` variable and are restricted to `{MIN_YEAR} <= year <= {MAX_YEAR}`.",
            "- The sample is restricted to municipalities observed in every survey wave in that window.",
            "- Respondents younger than 18 are excluded because the exposure proxy follows the requested age-18 adult eligibility rule.",
            "- `first_eligible_year = year - floor(age) + 18`; the benchmark `year` is used as the interview year for consistency with the notebook-style LAPOP panel.",
            "- `T_im = 1` marks respondents who first became adult-eligible after municipal BVR adoption, `T_im = -1` marks adult mixed-cohort respondents who experienced a transition, and `T_im = 0` covers pre-BVR, not-yet-treated, or never-treated exposure histories.",
            "- Event-time dummies are binned to the paper window `[-8, 8]`, with endpoints absorbing earlier/later exposure and event time `-2` omitted.",
            "- All regressions cluster standard errors by municipality-year cell.",
            "- The no-hybrid event-study sample excludes rows with `is_hybrid = 1`; in the balanced-wave sample this exclusion removes no rows.",
            "",
            "## Sample support",
            "",
            f"- All sample respondents: {int(benchmark['n_obs']):,}",
            f"- All sample municipalities: {int(benchmark['n_municipalities']):,}",
            f"- Survey waves: {int(benchmark['n_waves']):,} ({int(benchmark['min_year'])}-{int(benchmark['max_year'])})",
            f"- Always-BVR respondents: {int(benchmark['n_registered_under_bvr']):,}",
            f"- Mixed-cohort respondents: {int(benchmark['n_mixed_cohort']):,}",
            f"- Low-education respondents in the always-BVR cohort: {int(benchmark['n_low_ed_registered_under_bvr']):,}",
            f"- No-hybrid respondents: {int(no_hybrid['n_obs']):,}",
            "",
            "## Headline coefficients",
            "",
            f"- Trust ITT (`registered_under_bvr`): {_fmt(trust_itt['estimate'])} ({_fmt(trust_itt['std_error'])}), p = {_fmt(trust_itt['p_value'])}",
            f"- Trust triple-difference (`registered_under_bvr x low_ed`): {_fmt(trust_triple['estimate'])} ({_fmt(trust_triple['std_error'])}), p = {_fmt(trust_triple['p_value'])}",
            f"- Democracy triple-difference (`registered_under_bvr x low_ed`): {_fmt(democracy_triple['estimate'])} ({_fmt(democracy_triple['std_error'])}), p = {_fmt(democracy_triple['p_value'])}",
            "",
            "## Event-study support",
            "",
            event_results.groupby(["outcome", "sample"])["n_obs"].max().reset_index().to_markdown(index=False),
        ]
    )
    MODEL_NOTES_MD.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    _ensure_dirs()
    build_individual_event_time_dataset()
    run_regressions()

    main_results = pd.read_csv(MAIN_RESULTS_CSV)
    event_results = pd.read_csv(EVENT_RESULTS_CSV)
    sample_summary = pd.read_csv(SAMPLE_SUMMARY_CSV)

    build_main_table(main_results, sample_summary)
    for (outcome, sample), path in EVENT_FIGURES.items():
        build_event_study_plot(event_results, outcome, sample, path)
    write_model_notes(sample_summary, main_results, event_results)

    print(sample_summary.to_string(index=False))
    print(main_results.to_string(index=False))


if __name__ == "__main__":
    main()
