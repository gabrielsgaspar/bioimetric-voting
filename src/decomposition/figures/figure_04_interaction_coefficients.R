#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(arrow)
  library(dplyr)
  library(fixest)
  library(ggplot2)
  library(readr)
  library(stringr)
})

args <- commandArgs(trailingOnly = FALSE)
file_arg <- args[grepl("^--file=", args)]
script_path <- normalizePath(sub("^--file=", "", file_arg[1]))
script_dir <- dirname(script_path)
root <- normalizePath(file.path(script_dir, "..", "..", ".."))

decomp_dir <- file.path(root, "data", "clean", "decomposition")
figure_dir <- file.path(root, "resources", "decomposition", "figures")
table_dir <- file.path(root, "paper", "tables", "decomposition")
figure_data_dir <- file.path(decomp_dir, "figure_data")
dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(figure_data_dir, recursive = TRUE, showWarnings = FALSE)

filename <- "figure_04_interaction_coefficients"
title_text <- "Strict x low-ed coefficients"
paper_width <- 8
paper_height <- 5
paper_dpi <- 320
grid_color <- "#D9D9D9"
plot_family <- "serif"

normalize_id <- function(x) {
  stringr::str_pad(as.character(x), width = 7, side = "left", pad = "0")
}

build_baseline <- function(panel, final_muni) {
  by_year <- panel |>
    mutate(
      ibge_municipality_id = normalize_id(ibge_municipality_id),
      state = str_to_upper(str_trim(as.character(state))),
      low_ed_voters = num_voters * low_ed
    ) |>
    group_by(ibge_municipality_id, state, year) |>
    summarise(
      baseline_low_ed_voters_2008 = sum(low_ed_voters, na.rm = TRUE),
      baseline_total_2008_panel = sum(num_voters, na.rm = TRUE),
      .groups = "drop"
    ) |>
    mutate(
      baseline_low_ed_share_2008 = baseline_low_ed_voters_2008 / baseline_total_2008_panel
    )

  exact_2008 <- by_year |>
    filter(year == 2008) |>
    select(-year)

  out <- final_muni |>
    select(ibge_municipality_id, state, baseline_year_used) |>
    left_join(exact_2008, by = c("ibge_municipality_id", "state")) |>
    mutate(
      baseline_low_ed_year_used = 2008L,
      baseline_low_ed_is_exact_2008 = !is.na(baseline_low_ed_share_2008)
    )

  fallback <- by_year |>
    rename(
      baseline_year_used = year,
      fallback_low_ed_voters = baseline_low_ed_voters_2008,
      fallback_total_panel = baseline_total_2008_panel,
      fallback_low_ed_share = baseline_low_ed_share_2008
    )

  out <- out |>
    left_join(
      fallback,
      by = c("ibge_municipality_id", "state", "baseline_year_used")
    ) |>
    mutate(
      baseline_low_ed_voters_2008 = if_else(
        is.na(baseline_low_ed_voters_2008),
        fallback_low_ed_voters,
        baseline_low_ed_voters_2008
      ),
      baseline_total_2008_panel = if_else(
        is.na(baseline_total_2008_panel),
        fallback_total_panel,
        baseline_total_2008_panel
      ),
      baseline_low_ed_share_2008 = if_else(
        is.na(baseline_low_ed_share_2008),
        fallback_low_ed_share,
        baseline_low_ed_share_2008
      ),
      baseline_low_ed_year_used = if_else(
        baseline_low_ed_is_exact_2008,
        baseline_low_ed_year_used,
        baseline_year_used
      )
    ) |>
    select(
      ibge_municipality_id,
      state,
      baseline_low_ed_voters_2008,
      baseline_total_2008_panel,
      baseline_low_ed_share_2008,
      baseline_low_ed_year_used,
      baseline_low_ed_is_exact_2008
    )

  if (any(is.na(out$baseline_low_ed_share_2008))) {
    stop("Missing baseline low-ed composition after fallback merge")
  }
  out
}

coef_row <- function(model, spec, term) {
  ct <- as.data.frame(fixest::coeftable(model))
  ct$term <- rownames(ct)
  if (!(term %in% ct$term)) {
    stop(paste("Could not find coefficient", term, "in", spec))
  }
  row <- ct[ct$term == term, ]
  tibble::tibble(
    spec = spec,
    coefficient = as.numeric(row[["Estimate"]]),
    se = as.numeric(row[["Std. Error"]]),
    ci_lower = coefficient - 1.96 * se,
    ci_upper = coefficient + 1.96 * se,
    n_obs = as.integer(stats::nobs(model))
  )
}

tidy_coefs <- function(model, spec) {
  ct <- as.data.frame(fixest::coeftable(model))
  ct$term <- rownames(ct)
  names(ct) <- make.names(names(ct))
  tibble::as_tibble(ct) |>
    transmute(
      spec = spec,
      term = term,
      estimate = Estimate,
      std_error = Std..Error,
      statistic = t.value,
      p_value = Pr...t..,
      n_obs = as.integer(stats::nobs(model))
    )
}

final_muni <- read_parquet(file.path(decomp_dir, "decomposition_final_municipality_v2.parquet")) |>
  mutate(
    ibge_municipality_id = normalize_id(ibge_municipality_id),
    state = str_to_upper(str_trim(as.character(state)))
  ) |>
  filter(year_first_any_bvr < 9999)

panel <- read_parquet(file.path(decomp_dir, "decomposition_panel_main_v2.parquet")) |>
  mutate(
    ibge_municipality_id = normalize_id(ibge_municipality_id),
    state = str_to_upper(str_trim(as.character(state)))
  )

baseline <- build_baseline(panel, final_muni)

muni <- final_muni |>
  inner_join(baseline, by = c("ibge_municipality_id", "state")) |>
  mutate(
    strict = as.integer(first_regime == "strict"),
    strict_low_ed = strict * baseline_low_ed_share_2008,
    log_baseline = log(N_2008_total)
  )

if (nrow(muni) != 4321) {
  stop(paste("Expected 4,321 treated municipalities, found", nrow(muni)))
}

spec1 <- feols(
  exit_rate_2008 ~ baseline_low_ed_share_2008 + strict + strict_low_ed + log_baseline,
  data = muni,
  weights = ~ N_2008_total,
  cluster = ~ state
)

spec2 <- feols(
  exit_rate_2008 ~ baseline_low_ed_share_2008 + strict + strict_low_ed + log_baseline | state,
  data = muni,
  weights = ~ N_2008_total,
  cluster = ~ state
)

cohort_baseline <- panel |>
  mutate(low_ed_voters = num_voters * low_ed) |>
  group_by(ibge_municipality_id, state, year, age_cohort) |>
  summarise(
    cohort_low_ed_voters = sum(low_ed_voters, na.rm = TRUE),
    cohort_baseline = sum(num_voters, na.rm = TRUE),
    .groups = "drop"
  ) |>
  mutate(cohort_low_ed_share = cohort_low_ed_voters / cohort_baseline)

relabel <- read_parquet(file.path(decomp_dir, "decomposition_relabel_cohort_v2.parquet")) |>
  mutate(
    ibge_municipality_id = normalize_id(ibge_municipality_id),
    state = str_to_upper(str_trim(as.character(state)))
  )

cohort <- relabel |>
  select(ibge_municipality_id, state, t, age_cohort, first_regime, exit_count) |>
  inner_join(
    cohort_baseline,
    by = c("ibge_municipality_id", "state", "t" = "year", "age_cohort")
  ) |>
  filter(cohort_baseline > 0, !is.na(cohort_low_ed_share)) |>
  mutate(
    strict = as.integer(first_regime == "strict"),
    strict_cohort_low_ed = strict * cohort_low_ed_share,
    cohort_exit_rate = exit_count / cohort_baseline,
    cohort_band = age_cohort
  )

spec3 <- feols(
  cohort_exit_rate ~ cohort_low_ed_share + strict_cohort_low_ed |
    ibge_municipality_id + cohort_band,
  data = cohort,
  weights = ~ cohort_baseline,
  cluster = ~ ibge_municipality_id
)

plot_data <- bind_rows(
  coef_row(spec1, "Spec 1: Pooled", "strict_low_ed"),
  coef_row(spec2, "Spec 2: State FE", "strict_low_ed"),
  coef_row(spec3, "Spec 3: Municipality x cohort", "strict_cohort_low_ed")
) |>
  mutate(
    spec = factor(spec, levels = rev(c(
      "Spec 1: Pooled",
      "Spec 2: State FE",
      "Spec 3: Municipality x cohort"
    ))),
    label = sprintf("%.3f (%.3f)", coefficient, se)
  )

write_parquet(plot_data, file.path(figure_data_dir, "figure_04_data.parquet"))

full_coefs <- bind_rows(
  tidy_coefs(spec1, "Spec 1: Pooled"),
  tidy_coefs(spec2, "Spec 2: State FE"),
  tidy_coefs(spec3, "Spec 3: Municipality x cohort")
)
write_parquet(
  full_coefs,
  file.path(figure_data_dir, "table_compositional_regressions_coefficients.parquet")
)

table_path <- file.path(table_dir, "table_compositional_regressions.tex")
etable(
  spec1,
  spec2,
  spec3,
  tex = TRUE,
  file = table_path,
  replace = TRUE,
  dict = c(
    baseline_low_ed_share_2008 = "Low-ed share (2008)",
    strict = "Strict",
    strict_low_ed = "Strict x low-ed share",
    log_baseline = "Log 2008 baseline",
    cohort_low_ed_share = "Cohort low-ed share",
    strict_cohort_low_ed = "Strict x cohort low-ed share"
  ),
  headers = c("Pooled", "State FE", "Within municipality"),
  fitstat = ~ n + r2 + wr2
)

base_plot <- ggplot(plot_data, aes(x = coefficient, y = spec)) +
  geom_vline(xintercept = 0, linewidth = 0.4, color = "#6B7280") +
  geom_errorbarh(aes(xmin = ci_lower, xmax = ci_upper), height = 0.18, color = "#2F5D7C") +
  geom_point(size = 2.2, color = "#006D77") +
  geom_text(aes(label = label), nudge_y = 0.22, size = 3.1, color = "#111827") +
  labs(
    x = "Interaction coefficient",
    y = NULL
  ) +
  theme_minimal(base_size = 11, base_family = plot_family) +
  theme(
    text = element_text(family = plot_family),
    plot.background = element_rect(fill = "white", color = NA),
    panel.background = element_rect(fill = "white", color = NA),
    panel.grid.major = element_line(color = grid_color, linewidth = 0.4),
    panel.grid.minor = element_blank(),
    panel.border = element_rect(color = "black", fill = NA, linewidth = 0.6),
    axis.line = element_blank(),
    plot.title = element_text(size = 11, hjust = 0, face = "plain"),
    axis.text = element_text(color = "#111827"),
    axis.text.y = element_text(size = 11),
    axis.title.x = element_text(size = 11)
  )

ggsave(
  file.path(figure_dir, paste0(filename, ".pdf")),
  base_plot + ggtitle(title_text),
  device = cairo_pdf,
  width = paper_width,
  height = paper_height,
  units = "in",
  bg = "white"
)
ggsave(
  file.path(figure_dir, paste0(filename, ".png")),
  base_plot + ggtitle(title_text),
  width = paper_width,
  height = paper_height,
  units = "in",
  dpi = paper_dpi,
  bg = "white"
)
ggsave(
  file.path(figure_dir, paste0(filename, "_notitle.pdf")),
  base_plot,
  device = cairo_pdf,
  width = paper_width,
  height = paper_height,
  units = "in",
  bg = "white"
)
ggsave(
  file.path(figure_dir, paste0(filename, "_notitle.png")),
  base_plot,
  width = paper_width,
  height = paper_height,
  units = "in",
  dpi = paper_dpi,
  bg = "white"
)

cat("Saved ", filename, " and figure_04_data.parquet\n", sep = "")
cat("Figure 4 headline coefficients:\n")
for (i in seq_len(nrow(plot_data))) {
  cat(
    "- ",
    as.character(plot_data$spec[i]),
    ": ",
    sprintf("%.4f", plot_data$coefficient[i]),
    " (SE ",
    sprintf("%.4f", plot_data$se[i]),
    "), n = ",
    plot_data$n_obs[i],
    "\n",
    sep = ""
  )
}
