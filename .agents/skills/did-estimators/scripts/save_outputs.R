write_table_outputs <- function(df, stem, output_dir, save_csv = TRUE, save_parquet = FALSE) {
  require_packages("readr")
  if (is.null(df) || nrow(df) == 0) {
    return(invisible(NULL))
  }

  paths <- list()

  if (isTRUE(save_csv)) {
    csv_path <- file.path(output_dir, paste0(stem, ".csv"))
    readr::write_csv(df, csv_path)
    paths$csv <- csv_path
  }

  if (isTRUE(save_parquet)) {
    require_packages("arrow")
    parquet_path <- file.path(output_dir, paste0(stem, ".parquet"))
    arrow::write_parquet(df, parquet_path)
    paths$parquet <- parquet_path
  }

  invisible(paths)
}

prepare_table_for_output <- function(df) {
  if (is.null(df) || nrow(df) == 0) {
    return(df)
  }

  out <- as.data.frame(df)
  if (all(c("group", "time") %in% names(out)) && !"term" %in% names(out)) {
    out$term <- seq_len(nrow(out))
  }
  if (all(c("estimate", "std.error") %in% names(out))) {
    out$statistic <- out$estimate / out$std.error
    out$p.value <- 2 * stats::pnorm(abs(out$statistic), lower.tail = FALSE)
  }

  out
}

write_results_json <- function(result, config, diagnostics, outdir, estimates, event_study, tables) {
  require_packages("jsonlite")

  simple_tbl <- tables$aggregate_simple
  model_stats <- list(
    estimator = config$estimator,
    nobs = if (!is.null(diagnostics) && "metric" %in% names(diagnostics)) {
      value <- diagnostics$value[diagnostics$metric == "n_rows"]
      if (length(value) > 0) value[[1]] else NULL
    } else {
      NULL
    },
    control_group = config$control_group %||% NULL,
    anticipation = config$anticipation %||% NULL
  )
  if (!is.null(simple_tbl) && nrow(simple_tbl) > 0 && "estimate" %in% names(simple_tbl)) {
    model_stats$overall_att <- simple_tbl$estimate[[1]]
    if ("std.error" %in% names(simple_tbl)) {
      model_stats$overall_se <- simple_tbl$std.error[[1]]
    }
  }

  run_info <- list(
    estimator = config$estimator,
    data_path = config$data_path,
    output_dir = config$output_dir,
    outcome = config$outcome,
    unit_id = config$unit_id,
    time_id = config$time_id,
    group_id = config$group_id,
    treatment_var = config$treatment_var %||% NULL,
    controls = config$controls %||% character(0),
    cluster_var = config$cluster_var %||% NULL,
    weights_var = config$weights_var %||% NULL,
    notes = config$notes %||% NULL
  )

  jsonlite::write_json(
    list(
      run = run_info,
      model_stats = model_stats,
      diagnostics = diagnostics,
      estimates = estimates,
      event_study = event_study,
      extra_tables = tables
    ),
    file.path(outdir, "results.json"),
    dataframe = "rows",
    na = "null",
    digits = NA,
    auto_unbox = TRUE,
    pretty = TRUE
  )
}

save_run_outputs <- function(result, config, diagnostics) {
  require_packages(c("yaml", "ggplot2", "readr"))

  outdir <- ensure_output_dir(config$output_dir)
  yaml::write_yaml(config, file.path(outdir, "config_used.yml"))

  output_options <- config$output %||% list()
  save_csv <- if (is.null(output_options$save_csv)) TRUE else isTRUE(output_options$save_csv)
  save_parquet <- if (is.null(output_options$save_parquet)) FALSE else isTRUE(output_options$save_parquet)
  save_json <- if (is.null(output_options$save_json)) FALSE else isTRUE(output_options$save_json)

  estimates <- prepare_table_for_output(result$estimates)
  event_study <- prepare_table_for_output(result$event_study)
  tables <- list()
  if (!is.null(result$tables) && length(result$tables) > 0) {
    for (nm in names(result$tables)) {
      tables[[nm]] <- prepare_table_for_output(result$tables[[nm]])
    }
  }

  if (!is.null(estimates)) {
    write_table_outputs(estimates, "tidy_estimates", outdir, save_csv, save_parquet)
  }

  if (!is.null(event_study)) {
    write_table_outputs(event_study, "event_study_estimates", outdir, save_csv, save_parquet)
  }

  if (length(tables) > 0) {
    for (nm in names(tables)) {
      write_table_outputs(tables[[nm]], nm, outdir, save_csv, save_parquet)
    }
  }

  if (is.null(diagnostics)) {
    diagnostics <- data.frame(metric = character(0), value = character(0), notes = character(0))
  }
  readr::write_csv(diagnostics, file.path(outdir, "sample_diagnostics.csv"))

  summary_text <- result$summary_text %||% sprintf("Estimator run completed for `%s`.", config$estimator)
  write_summary_text(file.path(outdir, "model_summary.txt"), summary_text)

  metadata <- make_run_metadata(config, result, diagnostics)
  yaml::write_yaml(metadata, file.path(outdir, "run_metadata.yml"))

  if (isTRUE(save_json)) {
    write_results_json(result, config, diagnostics, outdir, estimates, event_study, tables)
  }

  if (!is.null(result$plot)) {
    save_plot_exports(
      plot = result$plot,
      outdir = outdir,
      stem = "event_study_plot",
      width = 8,
      height = 5,
      dpi = 320
    )
    mirror_regression_plot_exports(
      outdir = outdir,
      stem = "event_study_plot"
    )
  }

  invisible(outdir)
}
