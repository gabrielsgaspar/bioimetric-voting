run_twfe_dynamic <- function(data, config) {
  require_packages(c("fixest", "broom", "dplyr", "tibble", "ggplot2"))

  event_info <- build_event_time(data, config)
  data <- event_info$data
  reference_period <- config$reference_event_time %||% -1
  data$.__ever_treated__ <- ifelse(!is.na(data$.__group_id__), 1, 0)

  # Keep never-treated units in the estimation sample: with ever-treated == 0,
  # the specific placeholder event-time value is irrelevant for the interaction.
  data$.__event_time_plot__[is.na(data$.__event_time_plot__) & data$.__ever_treated__ == 0] <- reference_period
  extra_fixed_effects <- unlist(config$extra_fixed_effects %||% character(0))
  extra_fixed_effects <- extra_fixed_effects[!is.na(extra_fixed_effects) & nzchar(extra_fixed_effects)]
  fixed_effects <- paste(c(".__unit_id__", ".__time_id__", extra_fixed_effects), collapse = " + ")

  model_formula <- build_fixest_formula(
    outcome = config$outcome,
    treatment_term = sprintf("fixest::i(.__event_time_plot__, .__ever_treated__, ref = %s)", reference_period),
    controls = config$controls,
    fixed_effects = fixed_effects
  )

  feols_args <- list(
    fml = model_formula,
    data = data
  )
  if (!is.null(config$weights_var)) {
    feols_args$weights <- as_weights_formula(config$weights_var)
  }
  vcov_spec <- as_vcov_spec(config$cluster_var)
  if (!is.null(vcov_spec)) {
    feols_args$vcov <- vcov_spec
  }

  model <- do.call(fixest::feols, feols_args)

  estimates <- broom::tidy(model, conf.int = TRUE)
  event_study <- subset(estimates, grepl("event_time_plot", term))
  supported_event_times <- sort(unique(stats::na.omit(data$.__event_time_plot__[data$.__ever_treated__ == 1])))
  if (nrow(event_study) > 0) {
    event_study$event_time <- extract_last_integer(event_study$term)
    event_study <- subset(event_study, event_time != reference_period)
    event_study <- merge(
      data.frame(event_time = supported_event_times),
      event_study,
      by = "event_time",
      all.x = TRUE,
      sort = TRUE
    )
    event_study <- event_study[order(event_study$event_time), ]
  } else {
    event_study <- data.frame(event_time = supported_event_times)
  }

  if (reference_period %in% supported_event_times) {
    ref_mask <- event_study$event_time == reference_period
    if (any(ref_mask)) {
      event_study$term[ref_mask] <- "(reference period)"
      event_study$estimate[ref_mask] <- 0
      event_study$std.error[ref_mask] <- NA_real_
      event_study$statistic[ref_mask] <- NA_real_
      event_study$p.value[ref_mask] <- NA_real_
      event_study$conf.low[ref_mask] <- NA_real_
      event_study$conf.high[ref_mask] <- NA_real_
    }
  }

  y_label <- switch(
    config$outcome,
    log_num_voters = "Effect on log registered voters",
    log_num_voters_low_ed = "Effect on log low-education registered voters",
    log_num_voters_high_ed = "Effect on log high-education registered voters",
    log_num_voters_men = "Effect on log male registered voters",
    log_num_voters_women = "Effect on log female registered voters",
    pct_voters_low_ed = "Effect on share of low-education voters",
    pct_voters_high_ed = "Effect on share of high-education voters",
    pct_voters_men = "Effect on share of male voters",
    pct_voters_women = "Effect on share of female voters",
    "Coefficient"
  )

  plot_title <- switch(
    config$outcome,
    log_num_voters = "Dynamic TWFE: Log Registered Voters",
    log_num_voters_low_ed = "Dynamic TWFE: Log Low-Education Registered Voters",
    log_num_voters_high_ed = "Dynamic TWFE: Log High-Education Registered Voters",
    log_num_voters_men = "Dynamic TWFE: Log Male Registered Voters",
    log_num_voters_women = "Dynamic TWFE: Log Female Registered Voters",
    pct_voters_low_ed = "Dynamic TWFE: Low-Education Share",
    pct_voters_high_ed = "Dynamic TWFE: High-Education Share",
    pct_voters_men = "Dynamic TWFE: Male Share",
    pct_voters_women = "Dynamic TWFE: Female Share",
    sprintf("Dynamic TWFE: %s", config$outcome)
  )
  if (!is.null(config$plot_title)) {
    plot_title <- config$plot_title
  }
  if (isTRUE(config$omit_plot_title)) {
    plot_title <- NULL
  }

  event_plot <- NULL
  if (!is.null(event_study) && nrow(event_study) > 0) {
    ci_event_study <- subset(event_study, !is.na(conf.low) & !is.na(conf.high))
    plot_color <- "#2C5A8A"
    x_breaks <- seq(-8, 8, by = 2)
    x_limits <- range(x_breaks)
    max_abs_y <- max(abs(c(ci_event_study$conf.low, ci_event_study$conf.high)), na.rm = TRUE)
    if (!is.finite(max_abs_y)) {
      max_abs_y <- max(abs(event_study$estimate), na.rm = TRUE)
    }
    max_abs_y <- max(0.15, ceiling(max_abs_y / 0.05) * 0.05)
    y_limits <- c(-max_abs_y, max_abs_y)
    y_breaks <- seq(-max_abs_y, max_abs_y, by = 0.05)

    event_plot <- ggplot2::ggplot(event_study, ggplot2::aes(x = event_time, y = estimate)) +
      ggplot2::geom_hline(yintercept = 0, linetype = "solid", color = "gray35", linewidth = 0.9) +
      ggplot2::geom_vline(xintercept = reference_period, linetype = "dotted", color = "gray50") +
      ggplot2::geom_linerange(
        data = ci_event_study,
        ggplot2::aes(ymin = conf.low, ymax = conf.high),
        color = plot_color,
        linewidth = 1.1
      ) +
      ggplot2::geom_line(color = plot_color, linewidth = 1.1) +
      ggplot2::geom_point(color = plot_color, size = 2.4) +
      ggplot2::scale_x_continuous(breaks = x_breaks, limits = x_limits) +
      ggplot2::scale_y_continuous(
        breaks = y_breaks,
        limits = y_limits,
        labels = function(x) sprintf("%.2f", x)
      ) +
      ggplot2::labs(
        title = NULL,
        subtitle = NULL,
        x = "Distance to treatment",
        y = NULL
      ) +
      paper_plot_theme(base_size = 11) +
      ggplot2::theme(
        plot.title = ggplot2::element_blank(),
        plot.subtitle = ggplot2::element_blank(),
        axis.title = ggplot2::element_text(family = resolve_plot_font_family()),
        axis.text = ggplot2::element_text(family = resolve_plot_font_family())
      )
  }

  summary_text <- paste(
    "Estimator: Dynamic TWFE",
    sprintf("Outcome: %s", config$outcome),
    sprintf("Unit id: %s", config$unit_id),
    sprintf("Time id: %s", config$time_id),
    sprintf("Clustered SEs: %s", paste(config$cluster_var %||% "default", collapse = ", ")),
    sprintf("Event-time source: %s", event_info$source),
    sprintf("Reference event time: %s", reference_period),
    "Warning: dynamic TWFE can be misleading under staggered adoption with heterogeneous treatment effects.",
    "This estimator is included as a baseline or comparability check, not as the preferred staggered-DID design.",
    sep = "\n"
  )

  list(
    estimates = estimates,
    event_study = event_study,
    tables = list(),
    plot = event_plot,
    summary_text = summary_text,
    metadata = list(
      estimator = "twfe_dynamic",
      warning = "TWFE may be misleading under staggered timing with heterogeneous effects."
    )
  )
}
