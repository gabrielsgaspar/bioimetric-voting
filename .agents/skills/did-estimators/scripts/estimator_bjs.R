run_bjs <- function(data, config) {
  require_packages(c("didimputation", "dplyr", "tibble", "ggplot2"))

  event_time_step <- as.numeric(config$event_time_step %||% 1)

  horizon <- if (!is.null(config$horizon)) {
    config$horizon
  } else if (!is.null(config$lag)) {
    seq(0, as.integer(config$lag), by = event_time_step)
  } else {
    NULL
  }

  pretrends <- if (!is.null(config$pretrends)) {
    config$pretrends
  } else if (!is.null(config$lead)) {
    seq(event_time_step, as.integer(config$lead), by = event_time_step)
  } else {
    NULL
  }

  fit <- didimputation::did_imputation(
    data = data,
    yname = config$outcome,
    gname = ".__group_id_cs__",
    tname = ".__time_id__",
    idname = ".__unit_id__",
    first_stage = build_first_stage_formula(config$controls),
    cluster_var = config$cluster_var %||% NULL,
    wname = config$weights_var %||% NULL,
    horizon = horizon,
    pretrends = pretrends
  )

  estimates <- as.data.frame(fit)
  names_lower <- tolower(names(estimates))
  if (!"estimate" %in% names_lower && ncol(estimates) >= 1) names(estimates)[1] <- "estimate"
  if (!"std.error" %in% names_lower && ncol(estimates) >= 2) names(estimates)[2] <- "std.error"

  if (!"event_time" %in% names(estimates)) {
    maybe_term <- intersect(c("term", "horizon", "k"), names(estimates))
    if (length(maybe_term) > 0) {
      term_vals <- estimates[[maybe_term[1]]]
      if (is.numeric(term_vals) || is.integer(term_vals)) {
        estimates$event_time <- as.numeric(term_vals)
      } else {
        suppressWarnings(parsed_vals <- as.numeric(trimws(as.character(term_vals))))
        if (all(is.na(parsed_vals))) {
          parsed_vals <- extract_last_integer(as.character(term_vals))
        }
        estimates$event_time <- parsed_vals
      }
    }
  }
  if (all(c("estimate", "std.error") %in% names(estimates))) {
    estimates$conf.low <- estimates$estimate - 1.96 * estimates$std.error
    estimates$conf.high <- estimates$estimate + 1.96 * estimates$std.error
  }
  estimates <- subset(estimates, !is.na(estimate) & !is.na(event_time))

  event_study <- estimates
  if (!"event_time" %in% names(event_study)) {
    event_study <- NULL
  }

  event_plot <- build_generic_event_plot(
    event_study,
    title = "Borusyak-Jaravel-Spiess event study",
    subtitle = "Estimated with `didimputation::did_imputation()`",
    y_label = config$plot_y_label,
    reference_event_time = config$plot_reference_event_time %||% -2,
    lead = config$lead,
    lag = config$lag,
    omit_title = isTRUE(config$omit_plot_title)
  )

  summary_text <- paste(
    "Estimator: Borusyak-Jaravel-Spiess",
    sprintf("Outcome: %s", config$outcome),
    sprintf("Unit id: %s", config$unit_id),
    sprintf("Time id: %s", config$time_id),
    sprintf("Group id: %s", config$group_id),
    sprintf("Horizons requested: %s", if (is.null(horizon)) "none" else paste(horizon, collapse = ", ")),
    sprintf("Pretrends requested: %s", if (is.null(pretrends)) "none" else paste(pretrends, collapse = ", ")),
    "Estimated with `didimputation::did_imputation()` and a first-stage specification that includes unit and time fixed effects.",
    sep = "\n"
  )

  list(
    estimates = estimates,
    event_study = event_study,
    tables = list(),
    plot = event_plot,
    summary_text = summary_text,
    metadata = list(estimator = "bjs")
  )
}
