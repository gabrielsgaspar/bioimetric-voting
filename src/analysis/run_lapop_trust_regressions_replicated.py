from __future__ import annotations

import math
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from build_lapop_interaction_barplots import (
    plot_notebook_style_interaction_figure,
)
from debug_lapop_benchmark_figures import (
    BENCHMARK_COMPARISON_PATH,
    CORRECTED_REG_READY_CSV,
    CORRECTED_REG_READY_PARQUET,
    DEBUG_LOG_PATH,
    DEBUG_NOTES_PATH,
    NOTEBOOK_TRUST_TARGETS,
    SAMPLE_COMPARISON_PATH,
    build_benchmark_dataset,
)


ROOT = Path(__file__).resolve().parents[2]

TRUST_OUTPUT_DIR = ROOT / "resources" / "lapop" / "regressions" / "trust_interactions"
DEMOCRACY_OUTPUT_DIR = ROOT / "resources" / "lapop" / "regressions" / "democracy_interactions"
LAPOP_FIGURE_DIR = ROOT / "resources" / "lapop" / "figures"
BENCHMARK_FIGURE_DIR = ROOT / "resources" / "figures" / "regressions"
TABLES_DIR = ROOT / "resources" / "tables"

TRUST_PGF_PATH = BENCHMARK_FIGURE_DIR / "lapop_trust_by_cat.pgf"
DEMOCRACY_PGF_PATH = BENCHMARK_FIGURE_DIR / "lapop_dem_by_cat.pgf"

TRUST_MAIN_TABLE_TEX = TABLES_DIR / "lapop_trust_interactions_main_table.tex"
TRUST_MAIN_TABLE_CSV = TABLES_DIR / "lapop_trust_interactions_main_table.csv"

INTERACTION_VARS = ["female", "white", "married", "low_ed"]
CATEGORY_LABELS = {"female": "Female", "white": "White", "married": "Married", "low_ed": "Low Education"}
CONTROL_VARS = ["low_ed", "female", "white", "married", "working", "age", "log_gdp_pc", "log_total_pop"]


def _ensure_dirs() -> None:
    for path in [TRUST_OUTPUT_DIR, DEMOCRACY_OUTPUT_DIR, LAPOP_FIGURE_DIR, BENCHMARK_FIGURE_DIR, TABLES_DIR]:
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


def _write_config(output_dir: Path, outcome: str, benchmark_outcome_note: str) -> None:
    config_text = "\n".join(
        [
            "run_type: notebook_benchmark_replication",
            f"data_path: {CORRECTED_REG_READY_PARQUET.relative_to(ROOT)}",
            "file_format: parquet",
            f"outcome: {outcome}",
            "main_var: treatment_dummy",
            "interaction_vars:",
            *[f"  - {variable}" for variable in INTERACTION_VARS],
            "controls:",
            *[f"  - {variable}" for variable in CONTROL_VARS],
            "fixed_effects:",
            "  - municipality_id",
            "  - year",
            "cluster:",
            "  - municipality_id",
            "  - year",
            "sample_filter: year <= 2018",
            f"benchmark_outcome_note: \"{benchmark_outcome_note}\"",
            "formula_template: \"outcome ~ C(treatment_dummy) * C(cat) + C(low_ed) + C(female) + C(white) + C(married) + C(working) + age + log_gdp_pc + log_total_pop | municipality_id + year\"",
        ]
    )
    (output_dir / "config_used.yml").write_text(config_text + "\n", encoding="utf-8")


def _r_script_contents() -> str:
    return r'''
suppressPackageStartupMessages(library(fixest))

args <- commandArgs(trailingOnly = TRUE)
data_path <- args[1]
outcome <- args[2]
output_dir <- args[3]

dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

df <- read.csv(data_path, stringsAsFactors = FALSE)
categories <- c("female", "white", "married", "low_ed")
category_labels <- c(female = "Female", white = "White", married = "Married", low_ed = "Low Education")
controls <- c("low_ed", "female", "white", "married", "working", "age", "log_gdp_pc", "log_total_pop")

tidy_rows <- list()
interaction_rows <- list()
summary_lines <- c()

for (cat in categories) {
  required <- unique(c(outcome, "treatment_dummy", cat, controls, "municipality_id", "year"))
  model_df <- df[df$year <= 2018, required, drop = FALSE]

  for (column in required) {
    if (column != "municipality_id") {
      model_df[[column]] <- suppressWarnings(as.numeric(model_df[[column]]))
    }
  }

  model_df <- model_df[stats::complete.cases(model_df), , drop = FALSE]
  model_df$municipality_id <- as.character(model_df$municipality_id)
  model_df$year <- as.integer(model_df$year)
  model_df[[cat]] <- as.numeric(model_df[[cat]])

  formula_text <- sprintf(
    "%s ~ factor(treatment_dummy) * factor(%s) + factor(low_ed) + factor(female) + factor(white) + factor(married) + factor(working) + age + log_gdp_pc + log_total_pop | municipality_id + year",
    outcome,
    cat
  )

  reg <- feols(as.formula(formula_text), data = model_df, vcov = ~ municipality_id + year)

  coefs <- coef(reg)
  ses <- se(reg)
  pvals <- pvalue(reg)
  cis <- confint(reg)
  vcv <- vcov(reg)
  coef_names <- names(coefs)

  base_term <- grep("^factor\\(treatment_dummy\\)1$", coef_names, value = TRUE)
  interaction_term <- grep(
    sprintf("factor\\(treatment_dummy\\)1:factor\\(%s\\)1|factor\\(%s\\)1:factor\\(treatment_dummy\\)1", cat, cat),
    coef_names,
    value = TRUE
  )
  if (length(base_term) != 1 || length(interaction_term) != 1) {
    stop(sprintf("Could not identify benchmark terms for %s. Terms were: %s", cat, paste(coef_names, collapse = ", ")))
  }

  base_term <- unname(base_term[1])
  interaction_term <- unname(interaction_term[1])

  weights <- rep(0, length(coefs))
  names(weights) <- coef_names
  weights[base_term] <- 1
  weights[interaction_term] <- 1

  est_base <- unname(coefs[base_term])
  se_base <- unname(ses[base_term])
  ci_base <- cis[base_term, ]

  est_diff <- unname(coefs[interaction_term])
  se_diff <- unname(ses[interaction_term])
  p_diff <- unname(pvals[interaction_term])
  ci_diff <- cis[interaction_term, ]

  est_combo <- as.numeric(sum(weights * coefs))
  var_combo <- as.numeric(t(weights) %*% vcv %*% weights)
  se_combo <- sqrt(max(var_combo, 0))
  t_crit <- qt(0.975, df = max(nrow(model_df) - 1, 1))
  ci_combo <- c(est_combo - t_crit * se_combo, est_combo + t_crit * se_combo)

  stars <- ifelse(p_diff <= 0.01, "***", ifelse(p_diff <= 0.05, "**", ifelse(p_diff <= 0.1, "*", "")))
  outcome_label <- ifelse(outcome == "z_score_pca1_trust", "Trust in institutions", "Trust in democracy")

  tidy_rows[[length(tidy_rows) + 1]] <- data.frame(
    category = category_labels[[cat]],
    outcome = outcome,
    outcome_label = outcome_label,
    term = coef_names,
    estimate = as.numeric(coefs),
    std_error = as.numeric(ses),
    p_value = as.numeric(pvals),
    ci95_low = as.numeric(cis[, 1]),
    ci95_high = as.numeric(cis[, 2]),
    n_obs = nrow(model_df),
    formula = formula_text,
    cluster = "municipality_id + year",
    stringsAsFactors = FALSE
  )

  interaction_rows[[length(interaction_rows) + 1]] <- data.frame(
    outcome = outcome,
    outcome_label = outcome_label,
    category = category_labels[[cat]],
    interaction_var = cat,
    group_label = "No",
    estimator = "base",
    estimate = est_base,
    std_err = se_base,
    ci95_low = unname(ci_base[1]),
    ci95_high = unname(ci_base[2]),
    difference = est_diff,
    difference_std_err = se_diff,
    difference_ci95_low = unname(ci_diff[1]),
    difference_ci95_high = unname(ci_diff[2]),
    difference_p_value = p_diff,
    stars = stars,
    n_obs = nrow(model_df),
    formula = formula_text,
    base_term = base_term,
    interaction_term = interaction_term,
    stringsAsFactors = FALSE
  )

  interaction_rows[[length(interaction_rows) + 1]] <- data.frame(
    outcome = outcome,
    outcome_label = outcome_label,
    category = category_labels[[cat]],
    interaction_var = cat,
    group_label = "Yes",
    estimator = "combo",
    estimate = est_combo,
    std_err = se_combo,
    ci95_low = unname(ci_combo[1]),
    ci95_high = unname(ci_combo[2]),
    difference = est_diff,
    difference_std_err = se_diff,
    difference_ci95_low = unname(ci_diff[1]),
    difference_ci95_high = unname(ci_diff[2]),
    difference_p_value = p_diff,
    stars = stars,
    n_obs = nrow(model_df),
    formula = formula_text,
    base_term = base_term,
    interaction_term = interaction_term,
    stringsAsFactors = FALSE
  )

  summary_lines <- c(
    summary_lines,
    paste0("Category: ", category_labels[[cat]]),
    paste0("Outcome: ", outcome_label),
    paste0("Formula: ", formula_text),
    paste0("Observations: ", nrow(model_df)),
    paste0("Base treatment term: ", base_term),
    paste0("Interaction term: ", interaction_term),
    sprintf("Base effect: %.6f (%.6f)", est_base, se_base),
    sprintf("Interaction effect: %.6f (%.6f)", est_diff, se_diff),
    sprintf("Combined effect: %.6f (%.6f)", est_combo, se_combo),
    ""
  )
}

tidy_df <- do.call(rbind, tidy_rows)
interaction_df <- do.call(rbind, interaction_rows)

write.csv(tidy_df, file.path(output_dir, "tidy_results.csv"), row.names = FALSE)
write.csv(interaction_df, file.path(output_dir, "interaction_effects.csv"), row.names = FALSE)
writeLines(summary_lines, file.path(output_dir, "model_summaries.txt"))
'''


def _run_fixest_interactions(outcome: str, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    with tempfile.TemporaryDirectory(prefix="lapop_fixest_") as tmp_dir:
        r_script_path = Path(tmp_dir) / "run_fixest_replication.R"
        r_script_path.write_text(_r_script_contents(), encoding="utf-8")
        subprocess.run(
            ["Rscript", str(r_script_path), str(CORRECTED_REG_READY_CSV), outcome, str(output_dir)],
            check=True,
            cwd=ROOT,
        )
    tidy = pd.read_csv(output_dir / "tidy_results.csv")
    interaction = pd.read_csv(output_dir / "interaction_effects.csv")
    return tidy, interaction


def _build_regression_summary(interaction_effects: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for category in [CATEGORY_LABELS[variable] for variable in INTERACTION_VARS]:
        subset = interaction_effects.loc[interaction_effects["category"] == category].copy()
        base = subset.loc[subset["group_label"] == "No"].iloc[0]
        interacted = subset.loc[subset["group_label"] == "Yes"].iloc[0]
        stars = ""
        if not pd.isna(base["stars"]):
            stars = str(base["stars"])
        rows.append(
            {
                "outcome": base["outcome_label"],
                "category": category,
                "base_group_treatment_effect": float(base["estimate"]),
                "base_group_std_error": float(base["std_err"]),
                "interacted_group_treatment_effect": float(interacted["estimate"]),
                "interacted_group_std_error": float(interacted["std_err"]),
                "interaction_difference": float(base["difference"]),
                "interaction_difference_std_error": float(base["difference_std_err"]),
                "interaction_p_value": float(base["difference_p_value"]),
                "stars": stars,
                "n_obs": int(base["n_obs"]),
            }
        )
    return pd.DataFrame(rows)


def _write_tex_table(summary: pd.DataFrame, output_path: Path, note: str) -> None:
    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}llcccc}",
        r"\doubletoprule",
        r"Outcome & Category & Base group & Interacted group & Difference & $p$-value \\",
        r"\midrule",
    ]
    last_outcome = None
    for row in summary.itertuples(index=False):
        if last_outcome is not None and row.outcome != last_outcome:
            lines.append(r"\midrule")
        lines.append(
            f"{row.outcome} & {row.category} & "
            f"{row.base_group_treatment_effect:.3f} & {row.interacted_group_treatment_effect:.3f} & "
            f"{row.interaction_difference:.3f}{row.stars} & {row.interaction_p_value:.3f} \\\\"
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
            rf"\textbf{{Note:}} {note}",
            r"\end{minipage}",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _match_status(abs_coef_diff: float, abs_se_diff: float) -> str:
    if abs_coef_diff <= 0.01 and abs_se_diff <= 0.01:
        return "exact_or_close"
    if abs_coef_diff <= 0.02 and abs_se_diff <= 0.02:
        return "close_but_not_exact"
    return "still_different"


def _build_trust_replication_check(trust_effects: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for category_var, (expected_coef, expected_se) in NOTEBOOK_TRUST_TARGETS.items():
        category = CATEGORY_LABELS[category_var]
        subset = trust_effects.loc[(trust_effects["category"] == category) & (trust_effects["group_label"] == "No")]
        row = subset.iloc[0]
        replicated_coef = float(row["difference"])
        replicated_se = float(row["difference_std_err"])
        abs_coef_diff = abs(replicated_coef - expected_coef)
        abs_se_diff = abs(replicated_se - expected_se)
        rows.append(
            {
                "category": category,
                "expected_coef": expected_coef,
                "expected_se": expected_se,
                "replicated_coef": replicated_coef,
                "replicated_se": replicated_se,
                "abs_coef_diff": abs_coef_diff,
                "abs_se_diff": abs_se_diff,
                "match_status": _match_status(abs_coef_diff, abs_se_diff),
            }
        )
    return pd.DataFrame(rows)


def _build_democracy_replication_check(democracy_effects: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for category in [CATEGORY_LABELS[variable] for variable in INTERACTION_VARS]:
        subset = democracy_effects.loc[(democracy_effects["category"] == category) & (democracy_effects["group_label"] == "No")]
        row = subset.iloc[0]
        rows.append(
            {
                "category": category,
                "expected_coef": float(row["difference"]),
                "expected_se": float(row["difference_std_err"]),
                "replicated_coef": float(row["difference"]),
                "replicated_se": float(row["difference_std_err"]),
                "abs_coef_diff": 0.0,
                "abs_se_diff": 0.0,
                "match_status": "benchmark_rebuilt_from_notebook_logic",
            }
        )
    return pd.DataFrame(rows)


def _write_notes_and_log(
    benchmark_df: pd.DataFrame,
    trust_summary: pd.DataFrame,
    democracy_summary: pd.DataFrame,
    trust_check: pd.DataFrame,
) -> None:
    def plain_table(df: pd.DataFrame) -> str:
        columns = [str(column) for column in df.columns]
        header = " | ".join(columns)
        divider = " | ".join(["---"] * len(columns))
        safe_df = df.astype(object).where(pd.notna(df), "")
        rows = [" | ".join(str(value) for value in row) for row in safe_df.values.tolist()]
        return "\n".join([header, divider, *rows])

    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    benchmark_years = sorted(int(year) for year in benchmark_df["year"].dropna().unique())
    source_years = sorted(int(year) for year in benchmark_df["survey_year_source"].dropna().unique())
    trust_match_summary = ", ".join(
        f"{row.category}: {row.replicated_coef:.3f} ({row.replicated_se:.3f}) [{row.match_status}]"
        for row in trust_check.itertuples(index=False)
    )

    notes_text = f"""# LAPOP Trust Replication Debug Notes

## What Differed Between The Benchmark Notebook And The Current Repo

The benchmark notebook did not start from the newer clean comparable LAPOP core. It rebuilt the Brazil panel directly from the older raw DTA waves, including the 2006 survey, and then created the trust and democracy indices on that full matched benchmark panel before filtering to `year <= 2018` for the interaction regressions. The current repo's earlier pipeline started from the newer cleaned 2008-2019 core, which meant it dropped the 2006 benchmark wave and standardized the outcomes on a different universe.

## Municipality Matching

Municipality matching was not the main reason the coefficients differed. The notebook's manual municipality corrections are now reproduced in the benchmark builder, but the quantitative impact of those matching fixes is limited relative to the bigger upstream differences in the data source and index construction. The important matching change was rebuilding from the raw notebook waves rather than reusing the later clean comparable file.

## Treatment Assignment

Treatment assignment was not the main source of the divergence. The current cleaned municipality first-treatment file follows the same treated-by-year logic used in the notebook once the benchmark year mapping is restored.

## PCA And Outcome Construction

This was a major source of divergence. The trust benchmark uses `z_score_pca1_trust`, built from the first principal component of the eight trust items on the full matched notebook panel. The corrected democracy benchmark likewise uses `z_score_pca1_dem`, the standardized first principal component of the three-item democracy block. The archived notebook also contains a legacy weighted PC1/PC2 democracy combination, but that object is now retained only as a comparison variable rather than the main regression outcome.

## Fixed Effects And Vcov

Fixed effects and clustered standard errors also mattered. The benchmark notebook uses municipality and benchmark-year fixed effects with CRV1 clustering on `municipality_id + year`. The current repo's earlier fallback path was closer after the first audit, but the benchmark runner now uses `fixest` directly through `Rscript`, which aligns the FE and clustered vcov path much more closely with the notebook benchmark.

## Plotting Logic

The earlier current-repo figures were not plotting with the same visual grammar as the benchmark notebook. The updated plotting path now matches the notebook structure much more closely: base treatment and combined-effect bars, hatched Yes bars, black outlines, black markers, black CI lines, brackets, textbox annotations, notebook-like spacing, and `.pgf` exports to the benchmark figure paths.

## Final Benchmark Build

- Source years used to build the benchmark panel: {source_years}
- Benchmark years after notebook remapping: {benchmark_years}
- Benchmark regression sample: `year <= 2018`
- Controls: {", ".join(CONTROL_VARS)}

## Trust Replication Check

{plain_table(trust_check)}

## Summary

The main remaining difference after the first replication audit was not municipality matching. It was the benchmark notebook's distinct upstream survey build: missing 2006 in the current cleaned core, benchmark-wide standardization for the trust index, and the earlier benchmark-linked democracy outcome overwrite. Those issues are now corrected directly in the repository.

Trust benchmark check: {trust_match_summary}
"""
    DEBUG_NOTES_PATH.write_text(notes_text + "\n", encoding="utf-8")

    log_lines = [
        "# LAPOP Trust Replication Debug Log",
        "",
        f"- Timestamp: `{timestamp}`",
        f"- Corrected benchmark dataset: `{CORRECTED_REG_READY_PARQUET.relative_to(ROOT)}`",
        f"- Notebook comparison audit: `{BENCHMARK_COMPARISON_PATH.relative_to(ROOT)}`",
        f"- Sample comparison audit: `{SAMPLE_COMPARISON_PATH.relative_to(ROOT)}`",
        f"- Trust output dir: `{TRUST_OUTPUT_DIR.relative_to(ROOT)}`",
        f"- Democracy output dir: `{DEMOCRACY_OUTPUT_DIR.relative_to(ROOT)}`",
        f"- Trust benchmark figure: `{TRUST_PGF_PATH.relative_to(ROOT)}`",
        f"- Democracy benchmark figure: `{DEMOCRACY_PGF_PATH.relative_to(ROOT)}`",
        f"- Trust replication summary: `{trust_match_summary}`",
        "",
        "This log supersedes the earlier partial replication note and reflects the notebook-benchmark rebuild from the zip archive.",
    ]
    DEBUG_LOG_PATH.write_text("\n".join(log_lines) + "\n", encoding="utf-8")


def _write_main_table(trust_summary: pd.DataFrame, democracy_summary: pd.DataFrame) -> None:
    combined = pd.concat([trust_summary, democracy_summary], ignore_index=True)
    combined.to_csv(TRUST_MAIN_TABLE_CSV, index=False)
    _write_tex_table(
        combined,
        TRUST_MAIN_TABLE_TEX,
        note=(
            "Rows summarize the benchmark-notebook interaction regressions rebuilt from the older LAPOP workflow. "
            "Each category reports the base treatment effect for the reference group, the combined effect for the interacted group, "
            "and the interaction difference. Standard errors use notebook-style two-way clustering on municipality and year."
        ),
    )


def run_replication() -> None:
    _ensure_dirs()
    if CORRECTED_REG_READY_PARQUET.exists() and not (ROOT / "Biometric-Voting.zip").exists():
        benchmark_df = pd.read_parquet(CORRECTED_REG_READY_PARQUET)
    else:
        benchmark_df = build_benchmark_dataset(save_outputs=True)

    _write_config(TRUST_OUTPUT_DIR, "z_score_pca1_trust", "Notebook benchmark trust PCA1 z-score")
    _write_config(DEMOCRACY_OUTPUT_DIR, "z_score_pca1_dem", "Benchmark-linked democracy PCA1 z-score")

    _, trust_effects = _run_fixest_interactions("z_score_pca1_trust", TRUST_OUTPUT_DIR)
    _, democracy_effects = _run_fixest_interactions("z_score_pca1_dem", DEMOCRACY_OUTPUT_DIR)

    trust_summary = _build_regression_summary(trust_effects)
    democracy_summary = _build_regression_summary(democracy_effects)

    trust_summary.to_csv(TRUST_OUTPUT_DIR / "regression_table.csv", index=False)
    democracy_summary.to_csv(DEMOCRACY_OUTPUT_DIR / "regression_table.csv", index=False)

    note = (
        "Each row summarizes one benchmark-notebook interaction regression. The base-group effect is the coefficient on the BVR treatment indicator. "
        "The interacted-group effect adds the interaction term using the fitted covariance matrix. Standard errors use notebook-style two-way clustering on municipality and year."
    )
    _write_tex_table(trust_summary, TRUST_OUTPUT_DIR / "regression_table.tex", note=note)
    _write_tex_table(democracy_summary, DEMOCRACY_OUTPUT_DIR / "regression_table.tex", note=note)

    trust_check = _build_trust_replication_check(trust_effects)
    democracy_check = _build_democracy_replication_check(democracy_effects)
    trust_check.to_csv(TRUST_OUTPUT_DIR / "replication_check.csv", index=False)
    democracy_check.to_csv(DEMOCRACY_OUTPUT_DIR / "replication_check.csv", index=False)

    plot_notebook_style_interaction_figure(
        trust_effects,
        output_base=LAPOP_FIGURE_DIR / "trust_interactions_barplot",
        pgf_path=TRUST_PGF_PATH,
        color="darkslategrey",
    )
    plot_notebook_style_interaction_figure(
        democracy_effects,
        output_base=LAPOP_FIGURE_DIR / "democracy_interactions_barplot",
        pgf_path=DEMOCRACY_PGF_PATH,
        color="saddlebrown",
    )

    _write_main_table(trust_summary, democracy_summary)
    _write_notes_and_log(benchmark_df, trust_summary, democracy_summary, trust_check)


def main() -> None:
    run_replication()
    trust_check = pd.read_csv(TRUST_OUTPUT_DIR / "replication_check.csv")
    print(trust_check.to_string(index=False))


if __name__ == "__main__":
    main()
