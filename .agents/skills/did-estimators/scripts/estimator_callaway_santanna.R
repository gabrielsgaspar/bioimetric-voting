aggte_to_df <- function(obj, index_name = "term") {
  if (is.null(obj)) {
    return(NULL)
  }

  if (!is.null(obj$egt) && !is.null(obj$att.egt)) {
    out <- data.frame(estimate = obj$att.egt, std.error = obj$se.egt)
    out[[index_name]] <- obj$egt
    out <- out[, c(index_name, "estimate", "std.error")]
    out$conf.low <- out$estimate - 1.96 * out$std.error
    out$conf.high <- out$estimate + 1.96 * out$std.error
    return(out)
  }

  if (!is.null(obj$overall.att)) {
    out <- data.frame(
      term = "overall",
      estimate = obj$overall.att,
      std.error = obj$overall.se
    )
    out$conf.low <- out$estimate - 1.96 * out$std.error
    out$conf.high <- out$estimate + 1.96 * out$std.error
    return(out)
  }

  matrix_to_tidy_df(obj, index_name = index_name)
}

run_callaway_santanna <- function(data, config) {
  require_packages(c("did", "dplyr", "tibble", "ggplot2"))

  data$.__unit_id_numeric__ <- as.numeric(as.factor(data$.__unit_id__))

  att_args <- list(
    yname = config$outcome,
    tname = ".__time_id__",
    idname = ".__unit_id_numeric__",
    gname = ".__group_id_cs__",
    xformla = build_xformla(config$controls),
    data = data,
    panel = TRUE,
    allow_unbalanced_panel = !isTRUE(config$balanced_panel_required),
    control_group = config$control_group %||% "nevertreated",
    base_period = config$base_period %||% "varying",
    anticipation = as.integer(config$anticipation %||% 0),
    weightsname = config$weights_var %||% NULL,
    clustervars = if (!is.null(config$cluster_var)) c(config$cluster_var) else NULL
  )

  mp <- do.call(did::att_gt, att_args)

  group_time_tbl <- tibble::tibble(
    group = mp$group,
    time = mp$t,
    estimate = mp$att,
    std.error = mp$se
  ) |>
    dplyr::mutate(
      conf.low = estimate - 1.96 * std.error,
      conf.high = estimate + 1.96 * std.error
    )

  dynamic_args <- list(MP = mp, type = "dynamic")
  if (!is.null(config$lead)) dynamic_args$min_e <- -as.integer(config$lead)
  if (!is.null(config$lag)) dynamic_args$max_e <- as.integer(config$lag)
  dynamic_res <- do.call(did::aggte, dynamic_args)

  dynamic_tbl <- tibble::tibble(
    event_time = dynamic_res$egt,
    estimate = dynamic_res$att.egt,
    std.error = dynamic_res$se.egt
  ) |>
    dplyr::mutate(
      conf.low = estimate - 1.96 * std.error,
      conf.high = estimate + 1.96 * std.error
    )

  simple_tbl <- aggte_to_df(did::aggte(mp, type = "simple"))
  calendar_tbl <- aggte_to_df(did::aggte(mp, type = "calendar"))
  group_tbl <- aggte_to_df(did::aggte(mp, type = "group"))

  event_plot <- build_generic_event_plot(
    dynamic_tbl,
    title = "Callaway-Sant'Anna event-study aggregation",
    subtitle = sprintf("Control group: %s", config$control_group %||% "nevertreated"),
    y_label = config$plot_y_label,
    reference_event_time = config$plot_reference_event_time %||% -2,
    lead = config$lead,
    lag = config$lag,
    omit_title = isTRUE(config$omit_plot_title)
  )

  summary_text <- paste(
    "Estimator: Callaway-Sant'Anna",
    sprintf("Outcome: %s", config$outcome),
    sprintf("Unit id: %s", config$unit_id),
    sprintf("Time id: %s", config$time_id),
    sprintf("Group id: %s", config$group_id),
    sprintf("Control group: %s", config$control_group %||% "nevertreated"),
    sprintf("Base period: %s", config$base_period %||% "varying"),
    sprintf("Anticipation periods: %s", config$anticipation %||% 0),
    "Estimated group-time ATT(g,t) with `did::att_gt()` and dynamic, simple, calendar, and group aggregations via `did::aggte()`.",
    sep = "\n"
  )

  list(
    estimates = group_time_tbl,
    event_study = dynamic_tbl,
    tables = list(
      group_time_att = group_time_tbl,
      aggregate_simple = simple_tbl,
      aggregate_calendar = calendar_tbl,
      aggregate_group = group_tbl
    ),
    plot = event_plot,
    summary_text = summary_text,
    metadata = list(estimator = "callaway_santanna")
  )
}
