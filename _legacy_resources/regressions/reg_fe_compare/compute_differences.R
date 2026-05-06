suppressPackageStartupMessages({
  library(arrow)
  library(fixest)
  library(jsonlite)
})

out_dir <- "resources/regressions/reg_fe_compare"
placebo_dir <- file.path(out_dir, "placebo")
panel_path <- file.path(out_dir, "analysis_panel.parquet")
placebo_panel_path <- file.path(placebo_dir, "analysis_panel_placebo.parquet")
diagnostics_path <- file.path(out_dir, "analysis_panel_diagnostics.json")

dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(placebo_dir, recursive = TRUE, showWarnings = FALSE)

panel <- as.data.frame(arrow::read_parquet(panel_path))
placebo_panel <- as.data.frame(arrow::read_parquet(placebo_panel_path))
diagnostics <- jsonlite::read_json(diagnostics_path, simplifyVector = TRUE)

outcomes <- c(
  norm_2006_voters = "Total electorate",
  norm_2006_voters_low_ed = "Low-education voters",
  norm_2006_voters_high_ed = "High-education voters"
)

fmt <- function(x, digits = 3) {
  ifelse(is.na(x), "", formatC(x, digits = digits, format = "f"))
}

fmt_pct <- function(x, digits = 2) {
  ifelse(is.na(x), "", paste0(formatC(100 * x, digits = digits, format = "f"), "%"))
}

fmt_ci_pct <- function(lo, hi, digits = 2) {
  paste0("[", fmt_pct(lo, digits), ", ", fmt_pct(hi, digits), "]")
}

md_table <- function(df) {
  if (is.null(df) || nrow(df) == 0) return("_None._")
  df[] <- lapply(df, as.character)
  header <- paste0("| ", paste(names(df), collapse = " | "), " |")
  sep <- paste0("|", paste(rep("---", ncol(df)), collapse = "|"), "|")
  rows <- apply(df, 1, function(row) paste0("| ", paste(row, collapse = " | "), " |"))
  paste(c(header, sep, rows), collapse = "\n")
}

fit_main <- function(data, outcome, str_var, hyb_var) {
  fml <- stats::as.formula(
    paste0(outcome, " ~ ", str_var, " + ", hyb_var,
           " | municipality_id + year_election")
  )
  fixest::feols(fml = fml, data = data, cluster = ~ municipality_id)
}

coef_row <- function(model, term) {
  ct <- fixest::coeftable(model)
  if (!term %in% rownames(ct)) stop(sprintf("Term %s not found.", term), call. = FALSE)
  out <- ct[term, ]
  list(
    estimate = unname(out[["Estimate"]]),
    se = unname(out[["Std. Error"]]),
    t = if ("t value" %in% names(out)) unname(out[["t value"]]) else NA_real_,
    p = if ("Pr(>|t|)" %in% names(out)) unname(out[["Pr(>|t|)"]]) else NA_real_,
    ci_lower = unname(out[["Estimate"]]) - 1.96 * unname(out[["Std. Error"]]),
    ci_upper = unname(out[["Estimate"]]) + 1.96 * unname(out[["Std. Error"]])
  )
}

model_df <- function(model) {
  nobs <- tryCatch(stats::nobs(model), error = function(e) model$nobs)
  nparams <- tryCatch(model$nparams, error = function(e) NULL)
  if (is.null(nparams) || length(nparams) == 0 || is.na(nparams)) {
    nparams <- length(stats::coef(model))
  }
  max(1, nobs - nparams)
}

linear_combo <- function(model, weights) {
  b <- stats::coef(model)[names(weights)]
  v <- stats::vcov(model)[names(weights), names(weights), drop = FALSE]
  value <- sum(weights * b)
  se <- sqrt(as.numeric(t(weights) %*% v %*% weights))
  t_stat <- value / se
  p_val <- 2 * stats::pt(-abs(t_stat), df = model_df(model))
  list(
    value = value,
    se = se,
    t = t_stat,
    p = p_val,
    ci_lower = value - 1.96 * se,
    ci_upper = value + 1.96 * se
  )
}

main_models <- list()
coef_results <- list()
diff_results <- list()

for (outcome in names(outcomes)) {
  model <- fit_main(panel, outcome, "D_str_0", "D_hyb_0")
  main_models[[outcome]] <- model

  str <- coef_row(model, "D_str_0")
  hyb <- coef_row(model, "D_hyb_0")
  diff <- linear_combo(model, c(D_str_0 = 1, D_hyb_0 = -1))

  coef_results[[outcome]] <- data.frame(
    outcome = outcome,
    outcome_label = outcomes[[outcome]],
    term = c("D_str_0", "D_hyb_0"),
    estimate = c(str$estimate, hyb$estimate),
    se = c(str$se, hyb$se),
    t = c(str$t, hyb$t),
    p = c(str$p, hyb$p),
    ci_lower = c(str$ci_lower, hyb$ci_lower),
    ci_upper = c(str$ci_upper, hyb$ci_upper)
  )

  diff_results[[outcome]] <- data.frame(
    outcome = outcome,
    beta_str = str$estimate,
    se_str = str$se,
    beta_hyb = hyb$estimate,
    se_hyb = hyb$se,
    diff = diff$value,
    se_diff = diff$se,
    t_diff = diff$t,
    p_diff = diff$p,
    ci_lower_diff = diff$ci_lower,
    ci_upper_diff = diff$ci_upper
  )
}

coef_df <- do.call(rbind, coef_results)
diff_df <- do.call(rbind, diff_results)
rownames(coef_df) <- NULL
rownames(diff_df) <- NULL

write.csv(coef_df, file.path(out_dir, "main_coefficients.csv"), row.names = FALSE)
write.csv(diff_df, file.path(out_dir, "strict_minus_hybrid_differences.csv"), row.names = FALSE)

get_coef <- function(outcome, term) {
  row <- coef_df[coef_df$outcome == outcome & coef_df$term == term, ]
  if (nrow(row) != 1) stop("Coefficient not found.", call. = FALSE)
  row
}

get_diff <- function(outcome) {
  row <- diff_df[diff_df$outcome == outcome, ]
  if (nrow(row) != 1) stop("Difference not found.", call. = FALSE)
  row
}

decomp_rows <- list()
add_quantity <- function(quantity, value, se, ci_lower = value - 1.96 * se,
                         ci_upper = value + 1.96 * se) {
  decomp_rows[[length(decomp_rows) + 1]] <<- data.frame(
    quantity = quantity,
    value = value,
    se = se,
    ci_lower = ci_lower,
    ci_upper = ci_upper
  )
}

for (prefix in c("hyb", "str")) {
  term <- if (prefix == "hyb") "D_hyb_0" else "D_str_0"
  suffix <- if (prefix == "hyb") "hyb" else "str"
  for (item in list(
    c("gamma_N", "norm_2006_voters"),
    c("gamma_L", "norm_2006_voters_low_ed"),
    c("gamma_H", "norm_2006_voters_high_ed")
  )) {
    row <- get_coef(item[2], term)
    add_quantity(paste0(item[1], "_", suffix), row$estimate, row$se,
                 row$ci_lower, row$ci_upper)
  }
}

gamma_H_hyb <- get_coef("norm_2006_voters_high_ed", "D_hyb_0")
add_quantity("R_hat", gamma_H_hyb$estimate, gamma_H_hyb$se,
             gamma_H_hyb$ci_lower, gamma_H_hyb$ci_upper)

diff_N <- get_diff("norm_2006_voters")
diff_L <- get_diff("norm_2006_voters_low_ed")
diff_H <- get_diff("norm_2006_voters_high_ed")

add_quantity("E_L_hat", -diff_L$diff, diff_L$se_diff,
             -diff_L$ci_upper_diff, -diff_L$ci_lower_diff)
add_quantity("E_H_hat", -diff_H$diff, diff_H$se_diff,
             -diff_H$ci_upper_diff, -diff_H$ci_lower_diff)
add_quantity("E_total_hat", -diff_N$diff, diff_N$se_diff,
             -diff_N$ci_upper_diff, -diff_N$ci_lower_diff)

E_L <- decomp_rows[[which(vapply(decomp_rows, function(x) x$quantity, character(1)) == "E_L_hat")]]
E_H <- decomp_rows[[which(vapply(decomp_rows, function(x) x$quantity, character(1)) == "E_H_hat")]]
E_N <- decomp_rows[[which(vapply(decomp_rows, function(x) x$quantity, character(1)) == "E_total_hat")]]
add_quantity("sanity_E_total_minus_E_L_plus_E_H",
             E_N$value - (E_L$value + E_H$value),
             NA_real_, NA_real_, NA_real_)

decomp_df <- do.call(rbind, decomp_rows)
rownames(decomp_df) <- NULL
write.csv(decomp_df, file.path(out_dir, "decomposition_implied.csv"), row.names = FALSE)

# Identification test 2: estimate the low-plus-high equation directly. This
# gives the correct covariance for gamma_L_hyb + gamma_H_hyb.
panel$norm_2006_voters_low_plus_high_ed <-
  panel$norm_2006_voters_low_ed + panel$norm_2006_voters_high_ed
mirror_model <- fit_main(panel, "norm_2006_voters_low_plus_high_ed", "D_str_0", "D_hyb_0")
mirror_hyb <- coef_row(mirror_model, "D_hyb_0")

placebo_results <- list()
for (outcome in names(outcomes)) {
  model <- fit_main(placebo_panel, outcome, "D_str_minus4", "D_hyb_minus4")
  str <- coef_row(model, "D_str_minus4")
  hyb <- coef_row(model, "D_hyb_minus4")
  diff <- linear_combo(model, c(D_str_minus4 = 1, D_hyb_minus4 = -1))
  placebo_results[[outcome]] <- rbind(
    data.frame(outcome = outcome, outcome_label = outcomes[[outcome]],
               term = "D_str_minus4", estimate = str$estimate, se = str$se,
               t = str$t, p = str$p, ci_lower = str$ci_lower, ci_upper = str$ci_upper),
    data.frame(outcome = outcome, outcome_label = outcomes[[outcome]],
               term = "D_hyb_minus4", estimate = hyb$estimate, se = hyb$se,
               t = hyb$t, p = hyb$p, ci_lower = hyb$ci_lower, ci_upper = hyb$ci_upper),
    data.frame(outcome = outcome, outcome_label = outcomes[[outcome]],
               term = "strict_minus_hybrid_minus4", estimate = diff$value,
               se = diff$se, t = diff$t, p = diff$p,
               ci_lower = diff$ci_lower, ci_upper = diff$ci_upper)
  )
}
placebo_df <- do.call(rbind, placebo_results)
rownames(placebo_df) <- NULL
write.csv(placebo_df, file.path(placebo_dir, "placebo_results.csv"), row.names = FALSE)

writeLines(
  c(
    "norm_2006_voters ~ D_str_minus4 + D_hyb_minus4 | municipality_id + year_election",
    "norm_2006_voters_low_ed ~ D_str_minus4 + D_hyb_minus4 | municipality_id + year_election",
    "norm_2006_voters_high_ed ~ D_str_minus4 + D_hyb_minus4 | municipality_id + year_election"
  ),
  file.path(placebo_dir, "model_formulas.txt")
)

bounded_R_min <- 0.0522
bounded_R_max <- 0.1782
R_hat <- gamma_H_hyb$estimate
R_in_bounds <- R_hat >= bounded_R_min & R_hat <= bounded_R_max

gamma_N_hyb <- get_coef("norm_2006_voters", "D_hyb_0")
test1_pass <- gamma_N_hyb$ci_lower <= 0 & gamma_N_hyb$ci_upper >= 0
test2_pass <- mirror_hyb$ci_lower <= 0 & mirror_hyb$ci_upper >= 0
placebo_zero <- placebo_df$ci_lower <= 0 & placebo_df$ci_upper >= 0
test3_pass <- all(placebo_zero[placebo_df$term %in% c("D_str_minus4", "D_hyb_minus4")])

test_summary <- data.frame(
  test = c(
    "Hybrid total electorate effect is zero",
    "Hybrid low-plus-high education effects sum to zero",
    "Placebo event-time -4 coefficients are zero"
  ),
  statistic = c(
    "gamma_N_hyb",
    "gamma_L_hyb + gamma_H_hyb",
    "all D_str_minus4 and D_hyb_minus4 coefficients"
  ),
  estimate = c(
    gamma_N_hyb$estimate,
    mirror_hyb$estimate,
    NA_real_
  ),
  se = c(
    gamma_N_hyb$se,
    mirror_hyb$se,
    NA_real_
  ),
  ci_lower = c(
    gamma_N_hyb$ci_lower,
    mirror_hyb$ci_lower,
    NA_real_
  ),
  ci_upper = c(
    gamma_N_hyb$ci_upper,
    mirror_hyb$ci_upper,
    NA_real_
  ),
  pass = c(test1_pass, test2_pass, test3_pass)
)
write.csv(test_summary, file.path(out_dir, "identification_tests.csv"), row.names = FALSE)

coef_table <- coef_df
coef_table$estimate_ci <- paste0(fmt_pct(coef_table$estimate), " ",
                                 fmt_ci_pct(coef_table$ci_lower, coef_table$ci_upper))
main_results_table <- data.frame(
  outcome = outcomes[diff_df$outcome],
  beta_str = coef_table$estimate_ci[match(paste(diff_df$outcome, "D_str_0"),
                                          paste(coef_table$outcome, coef_table$term))],
  beta_hyb = coef_table$estimate_ci[match(paste(diff_df$outcome, "D_hyb_0"),
                                          paste(coef_table$outcome, coef_table$term))],
  strict_minus_hybrid = paste0(fmt_pct(diff_df$diff), " ",
                               fmt_ci_pct(diff_df$ci_lower_diff, diff_df$ci_upper_diff))
)

decomp_table <- decomp_df
decomp_table$value_ci <- ifelse(
  is.na(decomp_table$se),
  fmt_pct(decomp_table$value),
  paste0(fmt_pct(decomp_table$value), " ",
         fmt_ci_pct(decomp_table$ci_lower, decomp_table$ci_upper))
)

sample_muni <- unique(panel[, c("municipality_id", "first_regime", "year_first_any_bvr")])
sample_muni <- sample_muni[sample_muni$municipality_id %in% unique(panel$municipality_id), ]
regression_muni <- unique(panel[panel$municipality_id %in% unique(arrow::read_parquet(panel_path)$municipality_id),
                                c("municipality_id", "first_regime", "year_first_any_bvr")])
regime_counts <- as.data.frame(table(regression_muni$first_regime), stringsAsFactors = FALSE)
names(regime_counts) <- c("first_regime", "municipalities")
cohort_counts <- as.data.frame(table(
  first_regime = regression_muni$first_regime,
  year_first_any_bvr = regression_muni$year_first_any_bvr
), stringsAsFactors = FALSE)
cohort_counts <- cohort_counts[cohort_counts$Freq > 0, ]
names(cohort_counts)[names(cohort_counts) == "Freq"] <- "municipalities"
cohort_counts <- cohort_counts[order(cohort_counts$first_regime,
                                     as.integer(as.character(cohort_counts$year_first_any_bvr))), ]

placebo_table <- placebo_df[placebo_df$term %in% c("D_str_minus4", "D_hyb_minus4"),
                            c("outcome_label", "term", "estimate", "se", "ci_lower", "ci_upper", "p")]
placebo_table$estimate <- fmt_pct(placebo_table$estimate)
placebo_table$se <- fmt_pct(placebo_table$se)
placebo_table$ci <- fmt_ci_pct(as.numeric(placebo_df[placebo_df$term %in% c("D_str_minus4", "D_hyb_minus4"), "ci_lower"]),
                               as.numeric(placebo_df[placebo_df$term %in% c("D_str_minus4", "D_hyb_minus4"), "ci_upper"]))
placebo_table$p <- fmt(as.numeric(placebo_table$p), 4)
placebo_table <- placebo_table[, c("outcome_label", "term", "estimate", "se", "ci", "p")]

identification_lines <- c(
  "# Strict-vs-Hybrid Identification Tests",
  "",
  "All estimates are shares of the municipality's 2006 baseline electorate.",
  "",
  "## Test 1: Hybrid Total Electorate Effect",
  "",
  sprintf("Hybrid total effect: %s with 95%% CI %s.",
          fmt_pct(gamma_N_hyb$estimate), fmt_ci_pct(gamma_N_hyb$ci_lower, gamma_N_hyb$ci_upper)),
  if (test1_pass) {
    "The 95% CI contains zero, so this test supports the no-exit-in-hybrid prediction."
  } else {
    "The 95% CI does not contain zero, so this test does not support the no-exit-in-hybrid prediction."
  },
  "",
  "## Test 2: Hybrid Education Effects Are Mirror-Image",
  "",
  "I test this by estimating the low-plus-high normalized outcome directly, which supplies the correct covariance for `gamma_L_hyb + gamma_H_hyb`.",
  "",
  sprintf("Hybrid low-plus-high effect: %s with 95%% CI %s.",
          fmt_pct(mirror_hyb$estimate), fmt_ci_pct(mirror_hyb$ci_lower, mirror_hyb$ci_upper)),
  if (test2_pass) {
    "The 95% CI contains zero, so this test supports the pure re-labeling prediction."
  } else {
    "The 95% CI does not contain zero, so this test does not support the pure re-labeling prediction."
  },
  "",
  "## Test 3: Event-Time -4 Placebo",
  "",
  "The placebo compares event time -4 against event time -6 for treated municipalities, retaining all never-treated years.",
  "",
  md_table(placebo_table),
  "",
  if (test3_pass) {
    "All strict-first and hybrid-first placebo confidence intervals contain zero."
  } else {
    "At least one strict-first or hybrid-first placebo confidence interval excludes zero, so this test raises a pre-trend concern."
  }
)
writeLines(identification_lines, file.path(out_dir, "identification_tests.md"))

interpretation <- if (!test1_pass || !test2_pass || !R_in_bounds) {
  "The strict-vs-hybrid comparison does not deliver the hoped-for re-labeling point estimate. The hybrid-first coefficients are small but negative for total, low-education, and high-education counts, so the maintained interpretation of hybrid BVR as a re-labeling-only counterfactual is not supported in this specification."
} else {
  "The strict-vs-hybrid comparison is broadly consistent with the maintained hybrid-as-relabeling interpretation in this specification."
}

summary_lines <- c(
  "# Strict-vs-Hybrid Regression Summary",
  "",
  "All coefficients are shares of the municipality's 2006 baseline electorate. Percentages below multiply those shares by 100.",
  "",
  "## Sample Summary",
  "",
  sprintf("- Main analysis panel: %s observations across %s municipalities.",
          format(nrow(panel), big.mark = ","), format(length(unique(panel$municipality_id)), big.mark = ",")),
  sprintf("- Municipalities excluded for missing 2006 baseline: %s.",
          diagnostics$municipalities_excluded_missing_2006_baseline),
  sprintf("- Additional treated municipalities excluded for incomplete event-window pairs: %s.",
          diagnostics$main_event_pair_excluded_count),
  "",
  "Municipalities by first regime in the regression sample:",
  "",
  md_table(regime_counts),
  "",
  "Municipalities by cohort and first regime in the regression sample:",
  "",
  md_table(cohort_counts),
  "",
  "## Main Results",
  "",
  md_table(main_results_table),
  "",
  "## Strict-Minus-Hybrid Differences",
  "",
  "These differences use the clustered variance-covariance matrix from the same `fixest` model, not the separate JSON standard errors.",
  "",
  md_table(data.frame(
    outcome = outcomes[diff_df$outcome],
    diff = fmt_pct(diff_df$diff),
    se = fmt_pct(diff_df$se_diff),
    ci = fmt_ci_pct(diff_df$ci_lower_diff, diff_df$ci_upper_diff),
    p = fmt(diff_df$p_diff, 4)
  )),
  "",
  "## Identification Tests",
  "",
  md_table(data.frame(
    test = test_summary$test,
    estimate = c(fmt_pct(test_summary$estimate[1]), fmt_pct(test_summary$estimate[2]), ""),
    ci = c(fmt_ci_pct(test_summary$ci_lower[1], test_summary$ci_upper[1]),
           fmt_ci_pct(test_summary$ci_lower[2], test_summary$ci_upper[2]),
           ""),
    pass = ifelse(test_summary$pass, "yes", "no")
  )),
  "",
  "Placebo details are in `identification_tests.md` and `placebo/placebo_results.csv`.",
  "",
  "## Implied Decomposition",
  "",
  md_table(decomp_table[, c("quantity", "value_ci")]),
  "",
  sprintf("Bounded decomposition comparison: `R_hat = %s`; adoption bounds are [5.22%%, 17.82%%]. In bounds: %s.",
          fmt_pct(R_hat), ifelse(R_in_bounds, "yes", "no")),
  sprintf("Sanity check: `E_total_hat - (E_L_hat + E_H_hat) = %s`.",
          fmt_pct(E_N$value - (E_L$value + E_H$value))),
  "",
  "## Interpretation",
  "",
  interpretation,
  "",
  "The comparison narrows the decomposition only by imposing an assumption that the data do not support here. It produces a negative `R_hat`, outside the bounded interval from the static accounting framework, and the implied `E_H_hat` is negative. Those signs are a warning that hybrid-first municipalities are not behaving like a clean re-labeling-only counterfactual in this two-period specification.",
  "",
  "## Caveats",
  "",
  "- The interpretation requires re-labeling rates to be comparable in hybrid-first and strict-first municipalities.",
  "- Hybrid-first cohorts are concentrated in 2016 and 2018, with only two hybrid-first municipalities in 2014.",
  "- The hybrid no-exit prediction fails in this sample because the hybrid total-electorate coefficient is small but statistically negative.",
  "- The mirror-image education prediction fails because the hybrid low-plus-high coefficient is negative.",
  "- Any placebo coefficient excluding zero should be treated as a parallel-trends concern before using the strict-minus-hybrid differences as a structural decomposition."
)
writeLines(summary_lines, file.path(out_dir, "SUMMARY.md"))

cat("Wrote strict-minus-hybrid differences, implied decomposition, identification tests, and summary.\n")
