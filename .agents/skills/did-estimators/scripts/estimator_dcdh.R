extract_dcdh_results <- function(fit) {
  tables <- extract_tables_from_object(fit)
  preferred <- intersect(
    c("results", "coef", "coefficients", "dynamic", "placebo", "estimates"),
    names(tables)
  )
  estimates <- if (length(preferred) > 0) tables[[preferred[1]]] else {
    if (length(tables) > 0) tables[[1]] else NULL
  }

  event_study <- NULL
  event_candidates <- intersect(c("dynamic", "placebo", "effects"), names(tables))
  if (length(event_candidates) > 0) {
    event_study <- tables[[event_candidates[1]]]
  }

  list(estimates = estimates, tables = tables, event_study = event_study)
}

run_dcdh <- function(data, config) {
  require_packages(c("dplyr", "tibble", "ggplot2"))

  mode <- tolower(config$dcdh_mode %||% "dyn")
  dcdh_treatment_var <- config$treatment_var
  used_group_translation <- FALSE

  if (is.null(dcdh_treatment_var)) {
    data$.__dcdh_treatment__ <- ifelse(!is.na(data$.__group_id__) & data$.__time_id__ >= data$.__group_id__, 1, 0)
    dcdh_treatment_var <- ".__dcdh_treatment__"
    used_group_translation <- TRUE
  }

  if (mode == "old") {
    require_packages("DIDmultiplegt")
    fit <- DIDmultiplegt::did_multiplegt_old(
      df = data,
      Y = config$outcome,
      G = ".__unit_id__",
      T = ".__time_id__",
      D = dcdh_treatment_var,
      controls = config$controls,
      placebo = as.integer(config$placebo %||% config$lead %||% 0),
      dynamic = as.integer(config$effects %||% config$lag %||% 0),
      cluster = config$cluster_var %||% NULL,
      trends_nonparam = config$trends_nonparam %||% NULL,
      trends_lin = config$trends_lin %||% NULL
    )
    extracted <- extract_dcdh_results(fit)
  } else {
    require_packages("DIDmultiplegtDYN")
    fit <- DIDmultiplegtDYN::did_multiplegt_dyn(
      df = data,
      outcome = config$outcome,
      group = ".__unit_id__",
      time = ".__time_id__",
      treatment = dcdh_treatment_var,
      effects = as.integer(config$effects %||% config$lag %||% 1),
      placebo = as.integer(config$placebo %||% config$lead %||% 0),
      controls = config$controls,
      cluster = config$cluster_var %||% NULL,
      weight = config$weights_var %||% NULL,
      trends_nonparam = config$trends_nonparam %||% NULL,
      trends_lin = isTRUE(config$trends_lin),
      graph_off = TRUE
    )
    extracted <- extract_dcdh_results(fit)
  }

  event_study <- extracted$event_study
  if (!is.null(event_study) && !"event_time" %in% names(event_study)) {
    maybe_term <- intersect(c("term", "effect", "k"), names(event_study))
    if (length(maybe_term) > 0) {
      event_study$event_time <- safe_numeric_vector(event_study[[maybe_term[1]]], maybe_term[1], allow_na = TRUE)
    }
  }

  event_plot <- build_generic_event_plot(
    event_study,
    title = "de Chaisemartin-D'Haultfoeuille dynamic effects",
    subtitle = sprintf("Mode: %s", mode),
    y_label = config$plot_y_label,
    reference_event_time = config$plot_reference_event_time %||% -2,
    lead = config$lead,
    lag = config$lag,
    omit_title = isTRUE(config$omit_plot_title)
  )

  summary_text <- paste(
    "Estimator: de Chaisemartin-D'Haultfoeuille",
    sprintf("Mode: %s", mode),
    sprintf("Outcome: %s", config$outcome),
    sprintf("Unit id: %s", config$unit_id),
    sprintf("Time id: %s", config$time_id),
    sprintf("Treatment variable used: %s", dcdh_treatment_var),
    sprintf("Treatment translated from `group_id`: %s", used_group_translation),
    "The default modern pathway uses `DIDmultiplegtDYN::did_multiplegt_dyn()`. The legacy pathway uses `DIDmultiplegt::did_multiplegt_old()` only when explicitly requested.",
    sep = "\n"
  )

  list(
    estimates = extracted$estimates,
    event_study = event_study,
    tables = extracted$tables,
    plot = event_plot,
    summary_text = summary_text,
    metadata = list(
      estimator = "dcdh",
      mode = mode,
      used_group_translation = used_group_translation
    )
  )
}
