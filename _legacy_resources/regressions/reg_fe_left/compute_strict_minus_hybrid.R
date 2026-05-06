suppressPackageStartupMessages({
  library(arrow)
  library(fixest)
})

out_dir <- "resources/regressions/reg_fe_left"

model_specs <- list(
  list(
    test = "test1",
    data = file.path(out_dir, "regression_data", "test1.parquet"),
    outcome = "delta_pt_2010_2014",
    strict = "bvr_by_2014_strict",
    hybrid = "bvr_by_2014_hybrid"
  ),
  list(
    test = "test2",
    data = file.path(out_dir, "regression_data", "test2.parquet"),
    outcome = "delta_pt_2014_2018",
    strict = "bvr_by_2018_strict",
    hybrid = "bvr_by_2018_hybrid"
  ),
  list(
    test = "test2_left_coalition",
    data = file.path(out_dir, "regression_data", "test2.parquet"),
    outcome = "delta_left_2014_2018",
    strict = "bvr_by_2018_strict",
    hybrid = "bvr_by_2018_hybrid"
  )
)

coef_row <- function(model, term) {
  ct <- fixest::coeftable(model)
  if (!term %in% rownames(ct)) {
    stop(sprintf("Term `%s` not found in model.", term), call. = FALSE)
  }
  row <- ct[term, ]
  list(
    estimate = unname(row[["Estimate"]]),
    se = unname(row[["Std. Error"]])
  )
}

diff_row <- function(model, strict_term, hybrid_term, data, spec) {
  terms <- c(strict_term, hybrid_term)
  b <- stats::coef(model)[terms]
  v <- stats::vcov(model)[terms, terms, drop = FALSE]
  weights <- c(1, -1)
  names(weights) <- terms
  diff <- sum(weights * b)
  se <- sqrt(as.numeric(t(weights) %*% v %*% weights))
  t_stat <- diff / se
  complete <- stats::complete.cases(data[, c(spec$outcome, strict_term, hybrid_term, "log_population_2010", "log_gdp_per_capita_2010", "state")])
  state_counts <- table(data$state[complete])
  n_clusters <- sum(state_counts > 1)
  df <- max(1, n_clusters - 1)
  p_val <- 2 * stats::pt(-abs(t_stat), df = df)
  list(
    diff = diff,
    se_diff = se,
    t_diff = t_stat,
    p_diff = p_val,
    ci_lower_diff = diff - 1.96 * se,
    ci_upper_diff = diff + 1.96 * se,
    n_clusters = n_clusters
  )
}

rows <- list()

for (spec in model_specs) {
  data <- as.data.frame(arrow::read_parquet(spec$data))
  fml <- stats::as.formula(
    paste0(
      spec$outcome, " ~ ", spec$strict, " + ", spec$hybrid,
      " + log_population_2010 + log_gdp_per_capita_2010 | state"
    )
  )
  model <- fixest::feols(fml = fml, data = data, cluster = ~ state)
  strict <- coef_row(model, spec$strict)
  hybrid <- coef_row(model, spec$hybrid)
  diff <- diff_row(model, spec$strict, spec$hybrid, data, spec)
  rows[[length(rows) + 1]] <- data.frame(
    test = spec$test,
    beta_str = strict$estimate,
    se_str = strict$se,
    beta_hyb = hybrid$estimate,
    se_hyb = hybrid$se,
    diff = diff$diff,
    se_diff = diff$se_diff,
    t_diff = diff$t_diff,
    p_diff = diff$p_diff,
    ci_lower_diff = diff$ci_lower_diff,
    ci_upper_diff = diff$ci_upper_diff,
    n_clusters = diff$n_clusters
  )
}

results <- do.call(rbind, rows)
write.csv(
  results,
  file.path(out_dir, "strict_minus_hybrid_differences.csv"),
  row.names = FALSE
)

print(results)
