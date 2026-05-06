#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(broom)
  library(dplyr)
  library(fixest)
  library(ggplot2)
  library(HonestDiD)
  library(readr)
  library(tibble)
  library(TwoWayFEWeights)
})

fixest::setFixest_notes(FALSE)

`%||%` <- function(x, y) {
  if (is.null(x)) y else x
}

SCRIPT_PATH <- {
  file_arg <- commandArgs(trailingOnly = FALSE)
  file_arg <- file_arg[grepl("^--file=", file_arg)]
  candidate <- if (length(file_arg) == 0) "" else sub("^--file=", "", file_arg[1])
  if (nzchar(candidate) && candidate != "-" && file.exists(candidate)) {
    normalizePath(candidate, winslash = "/", mustWork = TRUE)
  } else {
    normalizePath(file.path(getwd(), "src", "analysis", "run_registry_identification_robustness.R"), winslash = "/", mustWork = TRUE)
  }
}

ROOT <- normalizePath(file.path(dirname(SCRIPT_PATH), "..", ".."), winslash = "/", mustWork = TRUE)
INPUT_PANEL <- file.path(ROOT, "data", "clean", "tse", "tse_clean_panel_2000_2018.csv")
IBGE_COVARIATES <- file.path(ROOT, "data", "clean", "ibge", "municipality_gdp_population_survey_years.csv")
ROBUSTNESS_ROOT <- file.path(ROOT, "resources", "robustness")
HONEST_ROOT <- file.path(ROBUSTNESS_ROOT, "honestdid")
STATE_YEAR_ROOT <- file.path(ROBUSTNESS_ROOT, "state_year_fe")
PERMUTATION_ROOT <- file.path(ROBUSTNESS_ROOT, "permutation")
BALANCE_ROOT <- file.path(ROBUSTNESS_ROOT, "balance")
DCDH_ROOT <- file.path(ROBUSTNESS_ROOT, "dcdh_diagnostic")

OUTCOMES <- c(
  "log_num_voters",
  "pct_voters_low_ed",
  "pct_voters_high_ed"
)

OUTCOME_LABELS <- c(
  log_num_voters = "Log registered voters",
  pct_voters_low_ed = "Low-education share",
  pct_voters_high_ed = "High-education share"
)

HONEST_M_VALUES <- c(0, 0.5, 1, 1.5, 2)
EVENT_TIMES <- c(-8, -6, -4, -2, 0, 2, 4, 6, 8)
EVENT_TIMES_NO_REF <- EVENT_TIMES[EVENT_TIMES != -2]
PERMUTATIONS <- 500L
PLOT_COLORS <- c(
  baseline = "#2C5A8A",
  state_year = "#2F7D32",
  within_state = "#B23A48"
)
SPEC_LABELS <- c(
  baseline = "Baseline TWFE",
  state_year = "State x election-year FE",
  within_state = "State x election-year FE, within-state support"
)

dir.create(ROBUSTNESS_ROOT, recursive = TRUE, showWarnings = FALSE)

ensure_dir <- function(path) {
  dir.create(path, recursive = TRUE, showWarnings = FALSE)
  invisible(path)
}

fmt_num <- function(x, digits = 3) {
  ifelse(is.na(x), "", formatC(x, format = "f", digits = digits))
}

fmt_int <- function(x) {
  ifelse(is.na(x), "", formatC(as.integer(round(x)), format = "d", big.mark = ","))
}

add_stars <- function(estimate, p_value) {
  if (is.na(estimate)) {
    return("")
  }
  stars <- ifelse(
    is.na(p_value),
    "",
    ifelse(p_value < 0.01, "***", ifelse(p_value < 0.05, "**", ifelse(p_value < 0.10, "*", "")))
  )
  paste0(fmt_num(estimate, 3), stars)
}

load_panel <- function() {
  read_csv(
    INPUT_PANEL,
    col_types = cols(
      .default = col_double(),
      municipality_id = col_character(),
      municipality_name = col_character(),
      state = col_character()
    ),
    progress = FALSE
  ) %>%
    mutate(
      ever_treated = ifelse(year_treated != 9999, 1, 0),
      treated_now = ifelse(ever_treated == 1 & year_election >= year_treated, 1, 0),
      control_now = ifelse(ever_treated == 0 | year_election < year_treated, 1, 0),
      event_time_trimmed = ifelse(
        ever_treated == 1,
        pmin(pmax(dist_treatment, min(EVENT_TIMES_NO_REF)), max(EVENT_TIMES_NO_REF)),
        NA_real_
      ),
      event_time_for_formula = ifelse(is.na(event_time_trimmed), -2, event_time_trimmed),
      state_year = interaction(state, year_election, drop = TRUE)
    ) %>%
    group_by(state, year_election) %>%
    mutate(
      state_year_has_treated_and_control = as.integer(sum(treated_now, na.rm = TRUE) > 0 & sum(control_now, na.rm = TRUE) > 0)
    ) %>%
    ungroup()
}

build_event_formula <- function(outcome, event_var = "event_time_for_formula", ever_var = "ever_treated", fixed_effects) {
  as.formula(
    sprintf(
      "%s ~ fixest::i(%s, %s, ref = -2) | %s",
      outcome,
      event_var,
      ever_var,
      fixed_effects
    )
  )
}

extract_event_study <- function(model, event_var = "event_time_for_formula", spec_name = NULL) {
  tidy_df <- broom::tidy(model, conf.int = TRUE) %>%
    mutate(event_time = as.numeric(sub(".*::(-?[0-9]+):.*", "\\1", term))) %>%
    filter(grepl(event_var, term), event_time %in% EVENT_TIMES_NO_REF) %>%
    arrange(event_time)

  ref_row <- tibble(
    term = "(reference period)",
    estimate = 0,
    std.error = NA_real_,
    statistic = NA_real_,
    p.value = NA_real_,
    conf.low = NA_real_,
    conf.high = NA_real_,
    event_time = -2
  )

  bind_rows(tidy_df, ref_row) %>%
    mutate(specification = spec_name %||% NA_character_) %>%
    arrange(event_time)
}

run_twfe_spec <- function(panel, outcome, specification = c("baseline", "state_year", "within_state")) {
  specification <- match.arg(specification)
  sample_df <- panel
  fixed_effects <- "municipality_id + year_election"

  if (specification == "state_year") {
    fixed_effects <- "municipality_id + state_year"
  }

  if (specification == "within_state") {
    fixed_effects <- "municipality_id + state_year"
    sample_df <- sample_df %>% filter(state_year_has_treated_and_control == 1)
  }

  model <- feols(
    build_event_formula(outcome, fixed_effects = fixed_effects),
    data = sample_df,
    vcov = ~ municipality_id + year_election,
    notes = FALSE
  )

  list(
    specification = specification,
    sample = sample_df,
    model = model,
    event_study = extract_event_study(model, spec_name = specification)
  )
}

write_csv_if_possible <- function(df, path) {
  write_csv(df, path, na = "")
}

plot_state_year_comparison <- function(event_df, outcome, output_path) {
  plot_df <- event_df %>%
    filter(event_time %in% EVENT_TIMES_NO_REF) %>%
    mutate(
      x_offset = case_when(
        specification == "baseline" ~ -0.18,
        specification == "state_year" ~ 0,
        TRUE ~ 0.18
      ),
      spec_label = SPEC_LABELS[specification]
    )

  y_bounds <- range(c(plot_df$conf.low, plot_df$conf.high), na.rm = TRUE)
  max_abs <- max(0.15, ceiling(max(abs(y_bounds)) / 0.05) * 0.05)

  fig <- ggplot(plot_df, aes(x = event_time + x_offset, y = estimate, color = specification)) +
    geom_hline(yintercept = 0, linewidth = 0.9, color = "gray35") +
    geom_errorbar(aes(ymin = conf.low, ymax = conf.high), width = 0, linewidth = 1.05) +
    geom_point(size = 2.4) +
    scale_color_manual(values = PLOT_COLORS, labels = SPEC_LABELS, name = NULL) +
    scale_x_continuous(breaks = EVENT_TIMES_NO_REF, limits = c(min(EVENT_TIMES_NO_REF) - 0.5, max(EVENT_TIMES_NO_REF) + 0.5)) +
    scale_y_continuous(
      breaks = seq(-max_abs, max_abs, by = 0.05),
      limits = c(-max_abs, max_abs),
      labels = function(x) sprintf("%.2f", x)
    ) +
    labs(x = "Distance to treatment", y = NULL) +
    theme_minimal(base_size = 11) +
    theme(
      panel.grid.minor = element_blank(),
      legend.position = "top",
      legend.justification = "left",
      panel.grid.major.x = element_blank(),
      plot.margin = margin(10, 14, 10, 10)
    )

  ggsave(output_path, fig, width = 7.2, height = 4.8, units = "in", device = cairo_pdf)
}

prepare_honestdid_inputs <- function(model) {
  coef_vec <- coef(model)
  vcov_mat <- vcov(model)
  coef_names <- names(coef_vec)
  event_time <- as.numeric(sub(".*::(-?[0-9]+):.*", "\\1", coef_names))
  keep <- event_time %in% EVENT_TIMES_NO_REF
  ordering <- order(event_time[keep])
  kept_names <- coef_names[keep][ordering]
  kept_times <- event_time[keep][ordering]
  list(
    betahat = unname(coef_vec[kept_names]),
    sigma = unname(as.matrix(vcov_mat[kept_names, kept_names])),
    event_time = kept_times
  )
}

normalize_honestdid_df <- function(obj) {
  out <- as.data.frame(obj)
  for (col in names(out)) {
    if (is.matrix(out[[col]]) || is.array(out[[col]])) {
      out[[col]] <- as.numeric(out[[col]])
    }
  }
  out <- as_tibble(out)
  names(out) <- gsub("\\[,1\\]", "", names(out))
  names(out) <- gsub("^Mvec$", "M", names(out))
  out
}

compute_breakdown_value <- function(rel_df) {
  crossing <- rel_df %>% filter(lb <= 0, ub >= 0)
  if (nrow(crossing) == 0) {
    return(sprintf(">%.1f", max(HONEST_M_VALUES)))
  }
  fmt_num(crossing$Mbar[1], 1)
}

write_honestdid_table <- function(outcome, smooth_df, rel_df, breakdown_value, output_path) {
  lines <- c(
    "\\begin{table}[htbp]",
    sprintf("    \\caption{HonestDiD Sensitivity for %s}", OUTCOME_LABELS[[outcome]]),
    sprintf("    \\label{tab:honestdid-%s}", outcome),
    "    \\centering",
    "    \\small",
    "    \\renewcommand{\\arraystretch}{1.08}",
    "    \\begin{tabular*}{0.94\\textwidth}{@{\\extracolsep{\\fill}}lcccc}",
    "        \\doubletoprule",
    "        Restriction & Violation bound & Lower bound & Upper bound & Rejects zero \\\\",
    "        \\midrule"
  )

  for (i in seq_len(nrow(smooth_df))) {
    lines <- c(
      lines,
      sprintf(
        "        Smoothness & %s & %s & %s & %s \\\\",
        fmt_num(smooth_df$M[i], 1),
        fmt_num(smooth_df$lb[i], 3),
        fmt_num(smooth_df$ub[i], 3),
        ifelse(smooth_df$lb[i] > 0 | smooth_df$ub[i] < 0, "Yes", "No")
      )
    )
  }

  lines <- c(lines, "        \\midrule")

  for (i in seq_len(nrow(rel_df))) {
    lines <- c(
      lines,
      sprintf(
        "        Relative magnitudes & %s & %s & %s & %s \\\\",
        fmt_num(rel_df$Mbar[i], 1),
        fmt_num(rel_df$lb[i], 3),
        fmt_num(rel_df$ub[i], 3),
        ifelse(rel_df$lb[i] > 0 | rel_df$ub[i] < 0, "Yes", "No")
      )
    )
  }

  lines <- c(
    lines,
    "        \\midrule",
    sprintf("        Breakdown $\\bar{M}$ & \\multicolumn{4}{c}{%s} \\\\", breakdown_value),
    "        \\doublebottomrule",
    "    \\end{tabular*}",
    "    \\vspace{1.0em}",
    "    \\begin{minipage}{0.94\\textwidth}",
    "        {\\footnotesize \\textbf{Note:} The table reports Rambachan-Roth sensitivity intervals for the event-time $0$ effect using the baseline dynamic TWFE specification. The smoothness rows impose bounds on second differences in latent violations of parallel trends. The relative-magnitudes rows bound post-treatment deviations relative to the largest pre-treatment deviation. The breakdown value is the smallest relative-magnitude violation at which the 95\\% identified set contains zero; entries above the search grid are reported as lower bounds. \\par}",
    "    \\end{minipage}",
    "\\end{table}"
  )

  writeLines(lines, output_path)
}

run_honestdid <- function(outcome, twfe_result) {
  outdir <- ensure_dir(file.path(HONEST_ROOT, outcome))
  hd_inputs <- prepare_honestdid_inputs(twfe_result$model)
  impact_estimate <- hd_inputs$betahat[which(hd_inputs$event_time == 0)][1]
  grid_radius <- max(0.5, 2 * max(abs(hd_inputs$betahat), na.rm = TRUE))
  original <- HonestDiD::constructOriginalCS(
    betahat = hd_inputs$betahat,
    sigma = hd_inputs$sigma,
    numPrePeriods = 3,
    numPostPeriods = 5,
    l_vec = c(1, 0, 0, 0, 0)
  )
  smooth <- HonestDiD::createSensitivityResults(
    betahat = hd_inputs$betahat,
    sigma = hd_inputs$sigma,
    numPrePeriods = 3,
    numPostPeriods = 5,
    l_vec = c(1, 0, 0, 0, 0),
    Mvec = HONEST_M_VALUES,
    method = "C-LF",
    parallel = FALSE
  )
  relative <- HonestDiD::createSensitivityResults_relativeMagnitudes(
    betahat = hd_inputs$betahat,
    sigma = hd_inputs$sigma,
    numPrePeriods = 3,
    numPostPeriods = 5,
    l_vec = c(1, 0, 0, 0, 0),
    Mbarvec = HONEST_M_VALUES,
    grid.lb = impact_estimate - grid_radius,
    grid.ub = impact_estimate + grid_radius
  )

  original_df <- normalize_honestdid_df(original) %>% mutate(restriction = "Original")
  smooth_df <- normalize_honestdid_df(smooth) %>% mutate(restriction = "Smoothness")
  relative_df <- normalize_honestdid_df(relative) %>% mutate(restriction = "Relative magnitudes")
  if (nrow(smooth_df) > 0 && any(smooth_df$M == 0 & (!is.finite(smooth_df$lb) | !is.finite(smooth_df$ub)))) {
    smooth_df <- smooth_df %>%
      mutate(
        lb = ifelse(M == 0 & !is.finite(lb), original_df$lb[1], lb),
        ub = ifelse(M == 0 & !is.finite(ub), original_df$ub[1], ub)
      )
  }
  breakdown_value <- compute_breakdown_value(relative_df)

  plot_df <- bind_rows(
    smooth_df %>% transmute(restriction = "Smoothness", violation = M, lb, ub),
    relative_df %>% transmute(restriction = "Relative magnitudes", violation = Mbar, lb, ub)
  )

  fig <- ggplot(plot_df, aes(x = violation, y = (lb + ub) / 2)) +
    geom_hline(yintercept = 0, color = "gray35", linewidth = 0.9) +
    geom_errorbar(aes(ymin = lb, ymax = ub), width = 0.06, linewidth = 1.0, color = "#2C5A8A") +
    geom_point(size = 2.5, color = "#2C5A8A") +
    facet_wrap(~restriction, scales = "free_x") +
    labs(x = "Allowed violation magnitude", y = "Identified set for event-time 0 effect") +
    theme_minimal(base_size = 11) +
    theme(
      panel.grid.minor = element_blank(),
      strip.text = element_text(face = "bold"),
      plot.margin = margin(10, 10, 10, 10)
    )

  ggsave(
    file.path(outdir, "sensitivity_plot.pdf"),
    fig,
    width = 7.4,
    height = 4.8,
    units = "in",
    device = cairo_pdf
  )

  write_csv_if_possible(original_df, file.path(outdir, "original_results.csv"))
  write_csv_if_possible(smooth_df, file.path(outdir, "smoothness_results.csv"))
  write_csv_if_possible(relative_df, file.path(outdir, "relative_magnitudes_results.csv"))
  write_honestdid_table(outcome, smooth_df, relative_df, breakdown_value, file.path(outdir, "results_table.tex"))

  tibble(
    outcome = outcome,
    baseline_lb = original_df$lb[1],
    baseline_ub = original_df$ub[1],
    breakdown_mbar = breakdown_value
  )
}

extract_event_zero <- function(model, event_var = "event_time_for_formula") {
  tidy_df <- broom::tidy(model, conf.int = TRUE)
  zero_row <- tidy_df %>%
    filter(grepl(event_var, term)) %>%
    mutate(event_time = as.numeric(sub(".*::(-?[0-9]+):.*", "\\1", term))) %>%
    filter(event_time == 0)
  if (nrow(zero_row) == 0) {
    stop("Could not find event-time zero coefficient.")
  }
  zero_row[1, ]
}

run_permutation_for_outcome <- function(panel, outcome, actual_beta) {
  outdir <- ensure_dir(file.path(PERMUTATION_ROOT, outcome))
  muni_timing <- panel %>%
    distinct(municipality_id, year_treated)

  permuted_betas <- numeric(PERMUTATIONS)
  set.seed(20260423L)

  for (i in seq_len(PERMUTATIONS)) {
    if (i %% 100 == 0) {
      message(sprintf("  Permutation %s/%s for %s", i, PERMUTATIONS, outcome))
    }
    permuted_map <- muni_timing %>%
      mutate(year_treated_perm = sample(year_treated, size = n(), replace = FALSE))

    perm_df <- panel %>%
      select(-year_treated, -ever_treated, -treated_now, -control_now, -event_time_trimmed, -event_time_for_formula, -state_year, -state_year_has_treated_and_control, -dist_treatment) %>%
      left_join(permuted_map, by = "municipality_id") %>%
      mutate(
        year_treated = year_treated_perm,
        dist_treatment = ifelse(year_treated == 9999, -9999, year_election - year_treated),
        ever_treated = ifelse(year_treated != 9999, 1, 0),
        treated_now = ifelse(ever_treated == 1 & year_election >= year_treated, 1, 0),
        control_now = ifelse(ever_treated == 0 | year_election < year_treated, 1, 0),
        event_time_trimmed = ifelse(
          ever_treated == 1,
          pmin(pmax(dist_treatment, min(EVENT_TIMES_NO_REF)), max(EVENT_TIMES_NO_REF)),
          NA_real_
        ),
        event_time_for_formula = ifelse(is.na(event_time_trimmed), -2, event_time_trimmed),
        state_year = interaction(state, year_election, drop = TRUE)
      ) %>%
      select(-year_treated_perm)

    perm_model <- feols(
      build_event_formula(outcome, fixed_effects = "municipality_id + year_election"),
      data = perm_df,
      vcov = ~ municipality_id + year_election,
      notes = FALSE
    )
    permuted_betas[i] <- extract_event_zero(perm_model)$estimate
  }

  perm_df <- tibble(draw = seq_len(PERMUTATIONS), beta_event_0 = permuted_betas)
  p_value <- (1 + sum(abs(permuted_betas) >= abs(actual_beta), na.rm = TRUE)) / (PERMUTATIONS + 1)
  write_csv_if_possible(perm_df, file.path(outdir, "permutation_draws.csv"))

  fig <- ggplot(perm_df, aes(x = beta_event_0)) +
    geom_histogram(fill = "#D9D9D9", color = "white", bins = 30) +
    geom_vline(xintercept = actual_beta, color = "#B23A48", linewidth = 1.1) +
    labs(x = "Permutation event-time 0 coefficient", y = "Count") +
    theme_minimal(base_size = 11) +
    theme(panel.grid.minor = element_blank())

  ggsave(
    file.path(outdir, "permutation_distribution.pdf"),
    fig,
    width = 7.0,
    height = 4.6,
    units = "in",
    device = cairo_pdf
  )

  tibble(
    outcome = outcome,
    actual_beta = actual_beta,
    permutation_mean = mean(permuted_betas, na.rm = TRUE),
    permutation_sd = sd(permuted_betas, na.rm = TRUE),
    permutation_p_value = p_value
  )
}

run_negative_weight_diagnostic <- function(panel) {
  ensure_dir(DCDH_ROOT)
  subset_df <- read_csv(INPUT_PANEL, show_col_types = FALSE, progress = FALSE)
  subset_df$treat <- ifelse(
    subset_df$year_treated != 9999 & subset_df$year_election >= subset_df$year_treated,
    1,
    0
  )
  weight_obj <- TwoWayFEWeights::twowayfeweights(
    data = subset_df,
    Y = "log_num_voters",
    G = "municipality_id",
    T = "year_election",
    D = "treat",
    type = "feTR",
    summary_measures = TRUE
  )
  diagnostic_df <- tibble(
    outcome = OUTCOMES,
    negative_components = weight_obj$nr_minus,
    total_components = weight_obj$nr_weights,
    share_negative_components = weight_obj$nr_minus / weight_obj$nr_weights,
    negative_weight_mass = abs(weight_obj$sum_minus),
    positive_weight_mass = weight_obj$sum_plus
  )
  write_csv_if_possible(diagnostic_df, file.path(DCDH_ROOT, "negative_weights_summary.csv"))

  lines <- c(
    "\\begin{table}[htbp]",
    "    \\caption{Negative-Weight Diagnostic for the Baseline TWFE Design}",
    "    \\label{tab:negative-weights}",
    "    \\centering",
    "    \\small",
    "    \\renewcommand{\\arraystretch}{1.08}",
    "    \\resizebox{0.92\\textwidth}{!}{%",
    "    \\begin{tabular}{lcccc}",
    "        \\doubletoprule",
    "        Outcome & Negative components & Total components & Share negative & Negative weight mass \\\\",
    "        \\midrule"
  )

  for (i in seq_len(nrow(diagnostic_df))) {
    lines <- c(
      lines,
      sprintf(
        "        %s & %s & %s & %s & %s \\\\",
        OUTCOME_LABELS[[diagnostic_df$outcome[i]]],
        fmt_int(diagnostic_df$negative_components[i]),
        fmt_int(diagnostic_df$total_components[i]),
        paste0(fmt_num(100 * diagnostic_df$share_negative_components[i], 3), "\\%"),
        fmt_num(diagnostic_df$negative_weight_mass[i], 6)
      )
    )
  }

  lines <- c(
    lines,
    "        \\doublebottomrule",
    "    \\end{tabular}}",
    "    \\vspace{1.0em}",
    "    \\begin{minipage}{0.92\\textwidth}",
    "        {\\footnotesize \\textbf{Note:} The table reports the de Chaisemartin-D'Haultfoeuille negative-weight diagnostic using \\texttt{TwoWayFEWeights} for the absorbing-treatment version of the baseline BVR design. The reported share negative is the fraction of ATT components receiving negative weight under the implied two-way fixed-effects aggregation; the final column reports the absolute mass of those negative weights. \\par}",
    "    \\end{minipage}",
    "\\end{table}"
  )
  writeLines(lines, file.path(DCDH_ROOT, "negative_weights_table.tex"))
  diagnostic_df
}

run_balance_table <- function(panel) {
  ensure_dir(BALANCE_ROOT)
  covariates <- read_csv(
    IBGE_COVARIATES,
    col_types = cols(
      municipality_id = col_character(),
      year = col_double(),
      gdp_current_mil_reais = col_double(),
      total_pop = col_double(),
      gdp_current_reais = col_double(),
      gdp_pc = col_double(),
      log_gdp_pc = col_double(),
      log_total_pop = col_double()
    ),
    progress = FALSE
  )

  baseline_df <- panel %>%
    select(municipality_id, year_election, year_treated, pct_voters_low_ed, pct_voters_high_ed) %>%
    left_join(covariates, by = c("municipality_id" = "municipality_id", "year_election" = "year"))

  cohorts <- sort(unique(panel$year_treated[panel$year_treated != 9999]))
  balance_rows <- lapply(cohorts, function(cohort) {
    baseline_year <- cohort - 2
    treated <- baseline_df %>% filter(year_treated == cohort, year_election == baseline_year)
    never <- baseline_df %>% filter(year_treated == 9999, year_election == baseline_year)
    tibble(
      cohort = cohort,
      baseline_year = baseline_year,
      treated_n = nrow(treated),
      never_n = nrow(never),
      treated_population = mean(treated$total_pop, na.rm = TRUE),
      never_population = mean(never$total_pop, na.rm = TRUE),
      treated_log_gdp_pc = mean(treated$log_gdp_pc, na.rm = TRUE),
      never_log_gdp_pc = mean(never$log_gdp_pc, na.rm = TRUE),
      treated_low_ed = mean(treated$pct_voters_low_ed, na.rm = TRUE),
      never_low_ed = mean(never$pct_voters_low_ed, na.rm = TRUE),
      treated_high_ed = mean(treated$pct_voters_high_ed, na.rm = TRUE),
      never_high_ed = mean(never$pct_voters_high_ed, na.rm = TRUE)
    )
  })

  balance_df <- bind_rows(balance_rows)
  write_csv_if_possible(balance_df, file.path(BALANCE_ROOT, "cohort_balance_summary.csv"))

  lines <- c(
    "\\begin{table}[htbp]",
    "    \\caption{Pre-Treatment Covariate Balance by Treatment Cohort}",
    "    \\label{tab:cohort-balance}",
    "    \\centering",
    "    \\scriptsize",
    "    \\renewcommand{\\arraystretch}{1.08}",
    "    \\resizebox{\\textwidth}{!}{%",
    "    \\begin{tabular}{lcccccccc}",
    "        \\doubletoprule",
    "        Cohort & $N_T$ & $N_N$ & Pop. (T) & Pop. (N) & log GDP pc (T) & log GDP pc (N) & Low ed. share (T) & Low ed. share (N) \\\\",
    "        \\midrule"
  )

  for (i in seq_len(nrow(balance_df))) {
    lines <- c(
      lines,
      sprintf(
        "        %s & %s & %s & %s & %s & %s & %s & %s & %s \\\\",
        balance_df$cohort[i],
        fmt_int(balance_df$treated_n[i]),
        fmt_int(balance_df$never_n[i]),
        fmt_int(round(balance_df$treated_population[i])),
        fmt_int(round(balance_df$never_population[i])),
        fmt_num(balance_df$treated_log_gdp_pc[i], 3),
        fmt_num(balance_df$never_log_gdp_pc[i], 3),
        fmt_num(balance_df$treated_low_ed[i], 3),
        fmt_num(balance_df$never_low_ed[i], 3)
      )
    )
  }

  lines <- c(
    lines,
    "        \\doublebottomrule",
    "    \\end{tabular}}",
    "    \\vspace{1.0em}",
    "    \\begin{minipage}{\\textwidth}",
    "        {\\footnotesize \\textbf{Note:} Each row compares municipalities first treated in the indicated cohort to never-treated municipalities in the same pre-treatment election year $g-2$. Population and GDP per capita come from IBGE municipal covariates, and education shares come from the TSE electorate panel used in the main analysis. \\par}",
    "    \\end{minipage}",
    "\\end{table}"
  )
  writeLines(lines, file.path(BALANCE_ROOT, "cohort_balance_table.tex"))
  balance_df
}

write_state_year_summary <- function(summary_df) {
  write_csv_if_possible(summary_df, file.path(STATE_YEAR_ROOT, "state_year_fe_summary.csv"))
}

main <- function() {
  panel <- load_panel()
  honest_summaries <- list()
  state_year_rows <- list()
  permutation_rows <- list()

  for (outcome in OUTCOMES) {
    message(sprintf("Running robustness stack for %s", outcome))

    baseline <- run_twfe_spec(panel, outcome, "baseline")
    state_year <- run_twfe_spec(panel, outcome, "state_year")
    within_state <- run_twfe_spec(panel, outcome, "within_state")

    state_dir <- ensure_dir(file.path(STATE_YEAR_ROOT, outcome))
    combined_events <- bind_rows(
      baseline$event_study,
      state_year$event_study,
      within_state$event_study
    )
    write_csv_if_possible(combined_events, file.path(state_dir, "event_study_estimates.csv"))
    plot_state_year_comparison(combined_events, outcome, file.path(state_dir, "event_study_plot.pdf"))

    baseline_zero <- baseline$event_study %>% filter(event_time == 0)
    state_year_zero <- state_year$event_study %>% filter(event_time == 0)
    within_state_zero <- within_state$event_study %>% filter(event_time == 0)
    state_year_rows[[outcome]] <- tibble(
      outcome = outcome,
      baseline_beta = baseline_zero$estimate[1],
      baseline_se = baseline_zero$std.error[1],
      state_year_beta = state_year_zero$estimate[1],
      state_year_se = state_year_zero$std.error[1],
      within_state_beta = within_state_zero$estimate[1],
      within_state_se = within_state_zero$std.error[1],
      state_year_pct_diff = abs(state_year_zero$estimate[1] - baseline_zero$estimate[1]) / abs(baseline_zero$estimate[1]),
      within_state_pct_diff = abs(within_state_zero$estimate[1] - baseline_zero$estimate[1]) / abs(baseline_zero$estimate[1])
    )

    message(sprintf("  HonestDiD sensitivity for %s", outcome))
    honest_summaries[[outcome]] <- run_honestdid(outcome, baseline)
    message(sprintf("  Permutation test for %s", outcome))
    permutation_rows[[outcome]] <- run_permutation_for_outcome(panel, outcome, baseline_zero$estimate[1])
    message(sprintf("Completed robustness stack for %s", outcome))
  }

  honest_summary_df <- bind_rows(honest_summaries)
  write_csv_if_possible(honest_summary_df, file.path(HONEST_ROOT, "breakdown_summary.csv"))
  write_state_year_summary(bind_rows(state_year_rows))
  write_csv_if_possible(bind_rows(permutation_rows), file.path(PERMUTATION_ROOT, "permutation_summary.csv"))

  run_negative_weight_diagnostic(panel)
  run_balance_table(panel)
}

if (sys.nframe() == 0) {
  main()
}
