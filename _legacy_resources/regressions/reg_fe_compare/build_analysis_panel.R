suppressPackageStartupMessages({
  library(arrow)
  library(jsonlite)
  library(yaml)
})

input_path <- "data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.parquet"
out_dir <- "resources/regressions/reg_fe_compare"
placebo_dir <- file.path(out_dir, "placebo")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(placebo_dir, recursive = TRUE, showWarnings = FALSE)

panel_raw <- as.data.frame(arrow::read_parquet(input_path))

format_num <- function(x, digits = 4) {
  ifelse(is.na(x), "", formatC(x, digits = digits, format = "f"))
}

md_table <- function(df) {
  if (is.null(df) || nrow(df) == 0) return("_None._")
  df[] <- lapply(df, as.character)
  header <- paste0("| ", paste(names(df), collapse = " | "), " |")
  sep <- paste0("|", paste(rep("---", ncol(df)), collapse = "|"), "|")
  rows <- apply(df, 1, function(row) paste0("| ", paste(row, collapse = " | "), " |"))
  paste(c(header, sep, rows), collapse = "\n")
}

finite_year <- function(x) !is.na(x) & x != 9999

make_config <- function(outcome, output_subdir) {
  list(
    data = list(path = file.path(out_dir, "analysis_panel.parquet")),
    regression = list(
      outcome = outcome,
      regressors = c("D_str_0", "D_hyb_0"),
      fixed_effects = c("municipality_id", "year_election"),
      cluster = c("municipality_id")
    ),
    output = list(dir = file.path(out_dir, output_subdir))
  )
}

input_rows <- nrow(panel_raw)
input_municipalities <- length(unique(panel_raw$municipality_id))

baseline <- panel_raw[panel_raw$year_election == 2006,
                      c("municipality_id", "municipality_name", "state", "num_voters")]
baseline_duplicates <- unique(baseline$municipality_id[duplicated(baseline$municipality_id)])
baseline <- baseline[!duplicated(baseline$municipality_id), ]
names(baseline)[names(baseline) == "num_voters"] <- "N_m_2006"

all_municipalities <- unique(panel_raw$municipality_id)
missing_baseline_ids <- sort(setdiff(all_municipalities, baseline$municipality_id))
excluded_rows <- panel_raw[panel_raw$municipality_id %in% missing_baseline_ids,
                           c("municipality_id", "municipality_name", "state")]
excluded_municipalities <- unique(excluded_rows)
excluded_municipalities <- excluded_municipalities[order(excluded_municipalities$state,
                                                         excluded_municipalities$municipality_id), ]

panel <- panel_raw[!(panel_raw$municipality_id %in% missing_baseline_ids), ]
panel <- merge(panel, baseline[, c("municipality_id", "N_m_2006")],
               by = "municipality_id", all.x = TRUE, sort = FALSE)

if (any(is.na(panel$N_m_2006))) {
  stop("Internal error: baseline denominator missing after exclusion.", call. = FALSE)
}
if (any(panel$N_m_2006 <= 0)) {
  stop("Internal error: non-positive 2006 baseline denominator.", call. = FALSE)
}

panel$norm_2006_voters <- panel$num_voters / panel$N_m_2006
panel$norm_2006_voters_low_ed <- panel$num_voters_low_ed / panel$N_m_2006
panel$norm_2006_voters_high_ed <- panel$num_voters_high_ed / panel$N_m_2006

treatment_cols <- c(
  "municipality_id",
  "year_first_strict_bvr",
  "year_first_hybrid_bvr",
  "year_first_any_bvr"
)
treatment_raw <- unique(panel[, treatment_cols])
treatment_split <- split(treatment_raw, treatment_raw$municipality_id)
nonconstant_ids <- names(treatment_split)[vapply(treatment_split, nrow, integer(1)) > 1]
treatment <- do.call(rbind, lapply(treatment_split, function(x) x[1, ]))
rownames(treatment) <- NULL

strict_finite <- finite_year(treatment$year_first_strict_bvr)
hybrid_finite <- finite_year(treatment$year_first_hybrid_bvr)
strict_for_min <- ifelse(strict_finite, treatment$year_first_strict_bvr, Inf)
hybrid_for_min <- ifelse(hybrid_finite, treatment$year_first_hybrid_bvr, Inf)
expected_any <- ifelse(strict_finite | hybrid_finite,
                       pmin(strict_for_min, hybrid_for_min),
                       9999)

treatment$expected_year_first_any_bvr <- expected_any
treatment$first_any_inconsistent <- treatment$year_first_any_bvr != expected_any
treatment$first_regime <- "never_treated"
treatment$first_regime[hybrid_finite & (!strict_finite | treatment$year_first_hybrid_bvr < treatment$year_first_strict_bvr)] <- "hybrid"
treatment$first_regime[strict_finite & (!hybrid_finite | treatment$year_first_strict_bvr <= treatment$year_first_hybrid_bvr)] <- "strict"
treatment$first_regime <- factor(treatment$first_regime,
                                 levels = c("strict", "hybrid", "never_treated"))

finite_ties <- strict_finite & hybrid_finite &
  treatment$year_first_strict_bvr == treatment$year_first_hybrid_bvr

treatment_for_join <- treatment[, c("municipality_id", "first_regime",
                                    "expected_year_first_any_bvr",
                                    "first_any_inconsistent")]
panel <- merge(panel, treatment_for_join, by = "municipality_id", all.x = TRUE, sort = FALSE)
panel$first_regime <- as.character(panel$first_regime)

panel$D_str_0 <- as.integer(
  panel$first_regime == "strict" &
    panel$year_election == panel$year_first_any_bvr
)
panel$D_hyb_0 <- as.integer(
  panel$first_regime == "hybrid" &
    panel$year_election == panel$year_first_any_bvr
)

is_treated <- panel$first_regime %in% c("strict", "hybrid")
keep_main <- (!is_treated) |
  (is_treated &
     (panel$year_election == panel$year_first_any_bvr - 2 |
        panel$year_election == panel$year_first_any_bvr))

required_cols <- c(
  "municipality_id", "year_election", "first_regime", "year_first_any_bvr",
  "D_str_0", "D_hyb_0",
  "norm_2006_voters", "norm_2006_voters_low_ed", "norm_2006_voters_high_ed",
  "pct_with_bvr", "pct_low_ed_with_bvr", "pct_high_ed_with_bvr",
  "bvr_status"
)
analysis_panel_candidate <- panel[keep_main, required_cols]
main_treated_counts_candidate <- aggregate(
  year_election ~ municipality_id + first_regime + year_first_any_bvr,
  data = analysis_panel_candidate[analysis_panel_candidate$first_regime %in% c("strict", "hybrid"), ],
  FUN = length
)
names(main_treated_counts_candidate)[names(main_treated_counts_candidate) == "year_election"] <- "main_obs_kept"
main_invalid_treated <- main_treated_counts_candidate[main_treated_counts_candidate$main_obs_kept != 2, ]
main_invalid_ids <- unique(main_invalid_treated$municipality_id)
analysis_panel <- analysis_panel_candidate[
  analysis_panel_candidate$first_regime == "never_treated" |
    !(analysis_panel_candidate$municipality_id %in% main_invalid_ids),
]

panel$D_str_minus4 <- as.integer(
  panel$first_regime == "strict" &
    panel$year_election == panel$year_first_any_bvr - 4
)
panel$D_hyb_minus4 <- as.integer(
  panel$first_regime == "hybrid" &
    panel$year_election == panel$year_first_any_bvr - 4
)
keep_placebo <- (!is_treated) |
  (is_treated &
     (panel$year_election == panel$year_first_any_bvr - 6 |
        panel$year_election == panel$year_first_any_bvr - 4))
placebo_cols <- c(
  "municipality_id", "year_election", "first_regime", "year_first_any_bvr",
  "D_str_minus4", "D_hyb_minus4",
  "norm_2006_voters", "norm_2006_voters_low_ed", "norm_2006_voters_high_ed",
  "pct_with_bvr", "pct_low_ed_with_bvr", "pct_high_ed_with_bvr",
  "bvr_status"
)
placebo_panel_candidate <- panel[keep_placebo, placebo_cols]
placebo_treated_counts_candidate <- aggregate(
  year_election ~ municipality_id + first_regime + year_first_any_bvr,
  data = placebo_panel_candidate[placebo_panel_candidate$first_regime %in% c("strict", "hybrid"), ],
  FUN = length
)
names(placebo_treated_counts_candidate)[names(placebo_treated_counts_candidate) == "year_election"] <- "placebo_obs_kept"
placebo_invalid_treated <- placebo_treated_counts_candidate[placebo_treated_counts_candidate$placebo_obs_kept != 2, ]
placebo_invalid_ids <- unique(placebo_invalid_treated$municipality_id)
placebo_panel <- placebo_panel_candidate[
  placebo_panel_candidate$first_regime == "never_treated" |
    !(placebo_panel_candidate$municipality_id %in% placebo_invalid_ids),
]

arrow::write_parquet(analysis_panel, file.path(out_dir, "analysis_panel.parquet"))
arrow::write_parquet(placebo_panel, file.path(placebo_dir, "analysis_panel_placebo.parquet"))

yaml::write_yaml(make_config("norm_2006_voters", "norm_voters"),
                 file.path(out_dir, "config_norm_voters.yml"))
yaml::write_yaml(make_config("norm_2006_voters_low_ed", "norm_voters_low_ed"),
                 file.path(out_dir, "config_norm_voters_low_ed.yml"))
yaml::write_yaml(make_config("norm_2006_voters_high_ed", "norm_voters_high_ed"),
                 file.path(out_dir, "config_norm_voters_high_ed.yml"))

municipality_summary <- unique(panel[, c("municipality_id", "first_regime",
                                         "year_first_any_bvr")])
regime_counts <- as.data.frame(table(municipality_summary$first_regime),
                               stringsAsFactors = FALSE)
names(regime_counts) <- c("first_regime", "municipalities")
regime_counts <- regime_counts[regime_counts$first_regime != "", ]

cohort_counts <- as.data.frame(table(
  first_regime = municipality_summary$first_regime,
  year_first_any_bvr = municipality_summary$year_first_any_bvr
), stringsAsFactors = FALSE)
cohort_counts <- cohort_counts[cohort_counts$Freq > 0, ]
names(cohort_counts)[names(cohort_counts) == "Freq"] <- "municipalities"
cohort_counts <- cohort_counts[order(cohort_counts$first_regime,
                                     as.integer(as.character(cohort_counts$year_first_any_bvr))), ]

obs_by_regime <- as.data.frame(table(analysis_panel$first_regime),
                               stringsAsFactors = FALSE)
names(obs_by_regime) <- c("first_regime", "observations")

main_treated_counts <- aggregate(
  year_election ~ municipality_id + first_regime + year_first_any_bvr,
  data = analysis_panel[analysis_panel$first_regime %in% c("strict", "hybrid"), ],
  FUN = length
)
names(main_treated_counts)[names(main_treated_counts) == "year_election"] <- "main_obs_kept"
treated_missing_two_obs <- main_treated_counts[main_treated_counts$main_obs_kept != 2, ]

placebo_treated_counts <- aggregate(
  year_election ~ municipality_id + first_regime + year_first_any_bvr,
  data = placebo_panel[placebo_panel$first_regime %in% c("strict", "hybrid"), ],
  FUN = length
)
names(placebo_treated_counts)[names(placebo_treated_counts) == "year_election"] <- "placebo_obs_kept"
placebo_missing_two_obs <- placebo_treated_counts[placebo_treated_counts$placebo_obs_kept != 2, ]

outcome_summary <- data.frame(
  variable = c("norm_2006_voters", "norm_2006_voters_low_ed", "norm_2006_voters_high_ed"),
  n = NA_integer_,
  mean = NA_real_,
  sd = NA_real_,
  min = NA_real_,
  p25 = NA_real_,
  median = NA_real_,
  p75 = NA_real_,
  max = NA_real_
)
for (i in seq_len(nrow(outcome_summary))) {
  x <- analysis_panel[[outcome_summary$variable[i]]]
  outcome_summary$n[i] <- sum(!is.na(x))
  outcome_summary$mean[i] <- mean(x, na.rm = TRUE)
  outcome_summary$sd[i] <- stats::sd(x, na.rm = TRUE)
  outcome_summary$min[i] <- min(x, na.rm = TRUE)
  outcome_summary$p25[i] <- unname(stats::quantile(x, 0.25, na.rm = TRUE))
  outcome_summary$median[i] <- stats::median(x, na.rm = TRUE)
  outcome_summary$p75[i] <- unname(stats::quantile(x, 0.75, na.rm = TRUE))
  outcome_summary$max[i] <- max(x, na.rm = TRUE)
}
outcome_summary_fmt <- outcome_summary
for (nm in setdiff(names(outcome_summary_fmt), c("variable", "n"))) {
  outcome_summary_fmt[[nm]] <- format_num(outcome_summary_fmt[[nm]])
}

inconsistencies <- treatment[treatment$first_any_inconsistent,
                             c("municipality_id", "year_first_strict_bvr",
                               "year_first_hybrid_bvr", "year_first_any_bvr",
                               "expected_year_first_any_bvr", "first_regime")]

diagnostics <- list(
  input_path = input_path,
  input_rows = input_rows,
  input_municipalities = input_municipalities,
  baseline_year = 2006,
  municipalities_with_2006_baseline = length(unique(panel$municipality_id)),
  municipalities_excluded_missing_2006_baseline = length(missing_baseline_ids),
  missing_2006_baseline_ids = as.character(missing_baseline_ids),
  baseline_duplicate_count = length(baseline_duplicates),
  baseline_duplicate_ids = as.character(baseline_duplicates),
  treatment_nonconstant_municipality_count = length(nonconstant_ids),
  treatment_nonconstant_municipality_ids = as.character(nonconstant_ids),
  first_any_inconsistency_count = nrow(inconsistencies),
  first_any_inconsistencies = inconsistencies,
  finite_strict_hybrid_tie_count = sum(finite_ties),
  finite_strict_hybrid_tie_ids = as.character(treatment$municipality_id[finite_ties]),
  regime_counts = regime_counts,
  cohort_counts = cohort_counts,
  analysis_panel_rows = nrow(analysis_panel),
  analysis_panel_municipalities = length(unique(analysis_panel$municipality_id)),
  placebo_panel_rows = nrow(placebo_panel),
  placebo_panel_municipalities = length(unique(placebo_panel$municipality_id)),
  D_str_0_count = sum(analysis_panel$D_str_0, na.rm = TRUE),
  D_hyb_0_count = sum(analysis_panel$D_hyb_0, na.rm = TRUE),
  D_str_minus4_count = sum(placebo_panel$D_str_minus4, na.rm = TRUE),
  D_hyb_minus4_count = sum(placebo_panel$D_hyb_minus4, na.rm = TRUE),
  main_event_pair_excluded_count = length(main_invalid_ids),
  main_event_pair_excluded = main_invalid_treated,
  placebo_event_pair_excluded_count = length(placebo_invalid_ids),
  placebo_event_pair_excluded = placebo_invalid_treated,
  treated_missing_two_main_observations = treated_missing_two_obs,
  treated_missing_two_placebo_observations = placebo_missing_two_obs
)
jsonlite::write_json(diagnostics, file.path(out_dir, "analysis_panel_diagnostics.json"),
                     pretty = TRUE, auto_unbox = TRUE, null = "null", na = "null")

summary_lines <- c(
  "# Strict-vs-Hybrid Analysis Panel",
  "",
  sprintf("Input panel: `%s`", input_path),
  "",
  sprintf("Output panel: `%s`", file.path(out_dir, "analysis_panel.parquet")),
  sprintf("Placebo panel: `%s`", file.path(placebo_dir, "analysis_panel_placebo.parquet")),
  "",
  "## Baseline Denominator",
  "",
  "The normalized outcomes divide each municipality-year count by the municipality's total 2006 electorate.",
  "",
  sprintf("- Input rows: %s", format(input_rows, big.mark = ",")),
  sprintf("- Input municipalities: %s", format(input_municipalities, big.mark = ",")),
  sprintf("- Municipalities with 2006 baseline: %s", format(length(unique(panel$municipality_id)), big.mark = ",")),
  sprintf("- Municipalities excluded because 2006 baseline is missing: %s", length(missing_baseline_ids)),
  sprintf("- Duplicate 2006 baseline municipality IDs: %s", length(baseline_duplicates)),
  "",
  "Excluded municipalities:",
  "",
  md_table(excluded_municipalities),
  "",
  "## Treatment Regime Classification",
  "",
  "First regime is assigned by comparing `year_first_hybrid_bvr` and `year_first_strict_bvr`. Strict wins finite ties, as specified in the prompt. `year_first_any_bvr` is retained as the canonical first-exposure year.",
  "",
  sprintf("- Municipalities with non-constant treatment-year fields across rows: %s", length(nonconstant_ids)),
  sprintf("- Municipalities where `year_first_any_bvr` differs from `min(strict, hybrid)`: %s", nrow(inconsistencies)),
  sprintf("- Finite strict/hybrid treatment-year ties assigned to strict: %s", sum(finite_ties)),
  "",
  "Municipality counts by first regime:",
  "",
  md_table(regime_counts),
  "",
  "Cohort counts by first regime:",
  "",
  md_table(cohort_counts),
  "",
  "Inconsistent first-exposure records:",
  "",
  md_table(inconsistencies),
  "",
  "## Main Regression Panel",
  "",
  "Treated municipalities are restricted to event time -2 and event time 0. Never-treated municipalities keep all years.",
  "",
  sprintf("- Rows: %s", format(nrow(analysis_panel), big.mark = ",")),
  sprintf("- Municipalities: %s", format(length(unique(analysis_panel$municipality_id)), big.mark = ",")),
  sprintf("- Strict event-time-0 observations (`D_str_0 == 1`): %s", sum(analysis_panel$D_str_0, na.rm = TRUE)),
  sprintf("- Hybrid event-time-0 observations (`D_hyb_0 == 1`): %s", sum(analysis_panel$D_hyb_0, na.rm = TRUE)),
  sprintf("- Treated municipalities excluded because the event-time -2/0 pair is incomplete: %s", length(main_invalid_ids)),
  "",
  "Observations by first regime:",
  "",
  md_table(obs_by_regime),
  "",
  "Treated municipalities excluded for an incomplete event-time -2/0 pair:",
  "",
  md_table(main_invalid_treated),
  "",
  "Treated municipalities without exactly two kept observations after this exclusion:",
  "",
  md_table(treated_missing_two_obs),
  "",
  "Outcome summary statistics in the main regression panel:",
  "",
  md_table(outcome_summary_fmt),
  "",
  "## Placebo Panel",
  "",
  "For the event-time -4 placebo, treated municipalities are restricted to event time -6 and event time -4. Never-treated municipalities keep all years.",
  "",
  sprintf("- Rows: %s", format(nrow(placebo_panel), big.mark = ",")),
  sprintf("- Municipalities: %s", format(length(unique(placebo_panel$municipality_id)), big.mark = ",")),
  sprintf("- Strict placebo observations (`D_str_minus4 == 1`): %s", sum(placebo_panel$D_str_minus4, na.rm = TRUE)),
  sprintf("- Hybrid placebo observations (`D_hyb_minus4 == 1`): %s", sum(placebo_panel$D_hyb_minus4, na.rm = TRUE)),
  sprintf("- Treated municipalities excluded because the event-time -6/-4 pair is incomplete: %s", length(placebo_invalid_ids)),
  "",
  "Treated municipalities excluded for an incomplete event-time -6/-4 pair:",
  "",
  md_table(placebo_invalid_treated),
  "",
  "Treated municipalities without exactly two kept observations in the placebo panel:",
  "",
  md_table(placebo_missing_two_obs)
)
writeLines(summary_lines, file.path(out_dir, "analysis_panel_summary.md"))

cat(sprintf("Wrote analysis panel with %s rows to %s\n",
            format(nrow(analysis_panel), big.mark = ","),
            file.path(out_dir, "analysis_panel.parquet")))
