`%||%` <- function(x, y) {
  if (is.null(x)) y else x
}

DID_EVENT_PLOT_COLOR <- "#2C5A8A"
DID_EVENT_GRID_COLOR <- "#D9D9D9"
DID_EVENT_Y_STEP <- 0.05
DID_EVENT_MIN_ABS_Y <- 0.15

stopf <- function(fmt, ...) {
  stop(sprintf(fmt, ...), call. = FALSE)
}

warnf <- function(fmt, ...) {
  warning(sprintf(fmt, ...), call. = FALSE)
}

resolve_plot_font_family <- local({
  cached_family <- NULL

  function() {
    if (!is.null(cached_family)) {
      return(cached_family)
    }

    cached_family <<- "serif"
    if (requireNamespace("systemfonts", quietly = TRUE)) {
      fonts <- try(systemfonts::system_fonts(), silent = TRUE)
      if (!inherits(fonts, "try-error") && "family" %in% names(fonts)) {
        if (any(fonts$family == "Latin Modern Roman")) {
          cached_family <<- "Latin Modern Roman"
        } else {
          lm_candidates <- unique(fonts$family[grepl("^LM Roman", fonts$family)])
          if (length(lm_candidates) > 0) {
            cached_family <<- lm_candidates[[1]]
          }
        }
      }
    }

    cached_family
  }
})

paper_plot_theme <- function(base_size = 11) {
  require_packages("ggplot2")
  plot_family <- resolve_plot_font_family()

  ggplot2::theme_minimal(base_size = base_size, base_family = plot_family) +
    ggplot2::theme(
      text = ggplot2::element_text(family = plot_family),
      panel.grid.minor = ggplot2::element_blank(),
      panel.grid.major = ggplot2::element_line(color = DID_EVENT_GRID_COLOR, linewidth = 0.4),
      panel.border = ggplot2::element_rect(color = "black", fill = NA, linewidth = 0.6),
      axis.line = ggplot2::element_blank(),
      plot.title = ggplot2::element_text(family = plot_family),
      plot.subtitle = ggplot2::element_text(family = plot_family),
      axis.title = ggplot2::element_text(family = plot_family),
      axis.text = ggplot2::element_text(family = plot_family)
    )
}

save_plot_exports <- function(plot, outdir, stem, width = 8, height = 5, dpi = 320) {
  require_packages("ggplot2")

  plot_family <- resolve_plot_font_family()
  pdf_path <- file.path(outdir, paste0(stem, ".pdf"))
  png_path <- file.path(outdir, paste0(stem, ".png"))

  ggplot2::ggsave(
    filename = pdf_path,
    plot = plot,
    device = grDevices::cairo_pdf,
    family = plot_family,
    width = width,
    height = height,
    bg = "white"
  )
  ggplot2::ggsave(
    filename = png_path,
    plot = plot,
    device = grDevices::png,
    width = width,
    height = height,
    dpi = dpi,
    type = "cairo",
    bg = "white"
  )

  invisible(list(pdf = pdf_path, png = png_path))
}

mirror_regression_plot_exports <- function(outdir, stem) {
  normalized_outdir <- normalizePath(outdir, winslash = "/", mustWork = FALSE)
  did_anchor <- "/resources/did/"
  if (!grepl(did_anchor, normalized_outdir, fixed = TRUE)) {
    return(invisible(NULL))
  }

  relative_dir <- sub(paste0("^.*", did_anchor), "", normalized_outdir)
  mirror_dir <- file.path(dirname(dirname(dirname(normalized_outdir))), "images", "regressions", relative_dir)
  dir.create(mirror_dir, recursive = TRUE, showWarnings = FALSE)

  pdf_src <- file.path(normalized_outdir, paste0(stem, ".pdf"))
  png_src <- file.path(normalized_outdir, paste0(stem, ".png"))
  pdf_dst <- file.path(mirror_dir, paste0(stem, ".pdf"))
  png_dst <- file.path(mirror_dir, paste0(stem, ".png"))

  if (file.exists(pdf_src)) {
    file.copy(pdf_src, pdf_dst, overwrite = TRUE)
  }
  if (file.exists(png_src)) {
    file.copy(png_src, png_dst, overwrite = TRUE)
  }

  invisible(list(pdf = pdf_dst, png = png_dst))
}

require_packages <- function(pkgs) {
  missing_pkgs <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing_pkgs) > 0) {
    stopf(
      "Missing R packages: %s. Run install_packages.R first.",
      paste(missing_pkgs, collapse = ", ")
    )
  }
}

parse_config <- function(config_path) {
  require_packages("yaml")
  if (!file.exists(config_path)) {
    stopf("Config file does not exist: %s", config_path)
  }

  cfg <- yaml::read_yaml(config_path)
  if (is.null(cfg) || !is.list(cfg)) {
    stopf("Config file did not parse into a list: %s", config_path)
  }

  defaults <- list(
    file_format = NULL,
    treatment_var = NULL,
    controls = character(0),
    cluster_var = NULL,
    weights_var = NULL,
    event_time_var = NULL,
    event_time_never_value = NULL,
    lead = NULL,
    lag = NULL,
    reference_event_time = -1,
    anticipation = 0,
    control_group = "nevertreated",
    base_period = NULL,
    balanced_panel_required = FALSE,
    output_dir = file.path("resources", "did", "run"),
    notes = NULL,
    effects = NULL,
    placebo = NULL,
    horizon = NULL,
    pretrends = NULL,
    event_time_step = 1,
    dcdh_mode = "dyn",
    never_treated_value = NULL,
    trends_nonparam = NULL,
    trends_lin = FALSE,
    plot_title = NULL,
    plot_reference_event_time = NULL,
    plot_y_label = NULL,
    omit_plot_title = TRUE
  )

  cfg <- modifyList(defaults, cfg)

  if (is.null(cfg$file_format)) {
    ext <- tools::file_ext(cfg$data_path %||% "")
    cfg$file_format <- tolower(ext)
  }

  if (is.null(cfg$controls)) {
    cfg$controls <- character(0)
  }
  cfg$controls <- unlist(cfg$controls)

  if (!is.null(cfg$cluster_var)) {
    cfg$cluster_var <- unlist(cfg$cluster_var)
    if (length(cfg$cluster_var) == 0) {
      cfg$cluster_var <- NULL
    }
  }

  cfg
}

ensure_output_dir <- function(path) {
  dir.create(path, recursive = TRUE, showWarnings = FALSE)
  normalizePath(path, winslash = "/", mustWork = FALSE)
}

read_input_data <- function(path, file_format = NULL) {
  if (!file.exists(path)) {
    stopf("Data file does not exist: %s", path)
  }

  fmt <- tolower(file_format %||% tools::file_ext(path))
  if (fmt == "csv") {
    require_packages("data.table")
  } else if (fmt %in% c("parquet", "feather")) {
    require_packages("arrow")
  }
  out <- switch(
    fmt,
    csv = data.table::fread(path, data.table = FALSE),
    parquet = as.data.frame(arrow::read_parquet(path)),
    feather = as.data.frame(arrow::read_feather(path)),
    rds = readRDS(path),
    stopf("Unsupported file format: %s", fmt)
  )

  as.data.frame(out)
}

build_controls_rhs <- function(controls) {
  controls <- controls %||% character(0)
  controls <- controls[nzchar(controls)]
  if (length(controls) == 0) {
    "1"
  } else {
    paste(controls, collapse = " + ")
  }
}

build_xformla <- function(controls) {
  stats::as.formula(paste("~", build_controls_rhs(controls)))
}

build_fixest_formula <- function(outcome, treatment_term, controls, fixed_effects) {
  rhs_terms <- c(treatment_term, controls)
  rhs_terms <- rhs_terms[!is.null(rhs_terms) & nzchar(rhs_terms)]
  rhs <- if (length(rhs_terms) == 0) "1" else paste(rhs_terms, collapse = " + ")
  stats::as.formula(sprintf("%s ~ %s | %s", outcome, rhs, fixed_effects))
}

build_first_stage_formula <- function(controls, unit_fe = ".__unit_id__", time_fe = ".__time_id__") {
  rhs <- build_controls_rhs(controls)
  stats::as.formula(sprintf("~ %s | %s + %s", rhs, unit_fe, time_fe))
}

as_vcov_spec <- function(cluster_var = NULL) {
  if (is.null(cluster_var) || identical(cluster_var, "") || identical(cluster_var, FALSE)) {
    return(NULL)
  }
  cluster_var <- unlist(cluster_var)
  cluster_var <- cluster_var[!is.na(cluster_var) & nzchar(cluster_var)]
  if (length(cluster_var) == 0) {
    return(NULL)
  }
  stats::as.formula(paste0("~", paste(cluster_var, collapse = " + ")))
}

as_weights_formula <- function(weights_var = NULL) {
  if (is.null(weights_var) || identical(weights_var, "")) {
    return(NULL)
  }
  stats::as.formula(paste0("~", weights_var))
}

safe_numeric_vector <- function(x, var_name, allow_na = TRUE) {
  if (is.numeric(x) || is.integer(x)) {
    return(as.numeric(x))
  }

  x_chr <- as.character(x)
  x_chr <- trimws(x_chr)
  x_chr[x_chr == ""] <- NA_character_

  suppressWarnings(x_num <- as.numeric(x_chr))
  bad <- !is.na(x_chr) & is.na(x_num)
  if (any(bad)) {
    stopf("Variable `%s` could not be safely coerced to numeric.", var_name)
  }
  if (!allow_na && any(is.na(x_num))) {
    stopf("Variable `%s` contains missing values after coercion.", var_name)
  }

  x_num
}

coerce_group_timing <- function(x, var_name = "group_id", never_treated_value = NULL) {
  g <- safe_numeric_vector(x, var_name = var_name, allow_na = TRUE)
  g[g == 0] <- NA_real_
  if (!is.null(never_treated_value)) {
    g[g == never_treated_value] <- NA_real_
  }
  g
}

coerce_binary_treatment <- function(x, var_name = "treatment_var") {
  if (is.logical(x)) {
    return(as.integer(x))
  }

  if (is.factor(x)) {
    x <- as.character(x)
  }

  if (is.character(x)) {
    xl <- tolower(trimws(x))
    out <- rep(NA_real_, length(xl))
    out[xl %in% c("1", "true", "treated", "yes")] <- 1
    out[xl %in% c("0", "false", "untreated", "no")] <- 0
    if (any(is.na(out) & !is.na(xl) & nzchar(xl))) {
      stopf("Treatment variable `%s` is not safely coercible to binary 0/1.", var_name)
    }
    return(out)
  }

  x_num <- safe_numeric_vector(x, var_name = var_name, allow_na = TRUE)
  values <- sort(unique(stats::na.omit(x_num)))
  if (!all(values %in% c(0, 1))) {
    stopf("Treatment variable `%s` must be binary 0/1 for this pathway.", var_name)
  }
  x_num
}

coerce_weights <- function(x, var_name = "weights_var") {
  w <- safe_numeric_vector(x, var_name = var_name, allow_na = TRUE)
  if (any(w < 0, na.rm = TRUE)) {
    stopf("Weights variable `%s` contains negative values.", var_name)
  }
  w
}

extract_last_integer <- function(x) {
  require_packages("stringr")
  out <- stringr::str_extract(x, "-?\\d+(?!.*-?\\d)")
  suppressWarnings(as.numeric(out))
}

make_reference_event_row <- function(event_df, reference_event_time) {
  ref_row <- event_df[1, , drop = FALSE]
  for (nm in names(ref_row)) {
    if (is.numeric(ref_row[[nm]]) || is.integer(ref_row[[nm]])) {
      ref_row[[nm]] <- NA_real_
    } else {
      ref_row[[nm]] <- NA
    }
  }
  ref_row$event_time <- reference_event_time
  ref_row$estimate <- 0
  if ("std.error" %in% names(ref_row)) ref_row$std.error <- NA_real_
  if ("conf.low" %in% names(ref_row)) ref_row$conf.low <- NA_real_
  if ("conf.high" %in% names(ref_row)) ref_row$conf.high <- NA_real_
  ref_row
}

build_generic_event_plot <- function(event_df,
                                     title = NULL,
                                     subtitle = NULL,
                                     y_label = NULL,
                                     reference_event_time = -2,
                                     lead = NULL,
                                     lag = NULL,
                                     omit_title = TRUE,
                                     plot_color = DID_EVENT_PLOT_COLOR) {
  require_packages(c("ggplot2", "dplyr"))
  if (is.null(event_df) || nrow(event_df) == 0) {
    return(NULL)
  }

  if (!all(c("event_time", "estimate") %in% names(event_df))) {
    return(NULL)
  }

  if (!all(c("conf.low", "conf.high") %in% names(event_df))) {
    if ("std.error" %in% names(event_df)) {
      event_df$conf.low <- event_df$estimate - 1.96 * event_df$std.error
      event_df$conf.high <- event_df$estimate + 1.96 * event_df$std.error
    } else {
      event_df$conf.low <- NA_real_
      event_df$conf.high <- NA_real_
    }
  }

  event_df$event_time <- safe_numeric_vector(event_df$event_time, "event_time", allow_na = TRUE)
  event_df$estimate <- safe_numeric_vector(event_df$estimate, "estimate", allow_na = TRUE)
  event_df <- subset(event_df, !is.na(event_time) & !is.na(estimate))
  if (nrow(event_df) == 0) {
    return(NULL)
  }

  if (!is.null(lead)) {
    event_df <- subset(event_df, event_time >= -as.integer(lead))
  }
  if (!is.null(lag)) {
    event_df <- subset(event_df, event_time <= as.integer(lag))
  }
  if (nrow(event_df) == 0) {
    return(NULL)
  }

  if (!is.null(reference_event_time)) {
    reference_event_time <- as.numeric(reference_event_time)
    if (is.finite(reference_event_time) && !(reference_event_time %in% event_df$event_time)) {
      event_df <- rbind(event_df, make_reference_event_row(event_df, reference_event_time))
    }
  }

  event_df <- event_df[order(event_df$event_time), ]
  ci_event_df <- subset(event_df, !is.na(conf.low) & !is.na(conf.high))

  if (!is.null(lead) && !is.null(lag)) {
    x_breaks <- seq(-as.integer(lead), as.integer(lag), by = 2)
  } else {
    x_range <- range(c(event_df$event_time, reference_event_time), na.rm = TRUE)
    x_breaks <- seq(floor(x_range[1] / 2) * 2, ceiling(x_range[2] / 2) * 2, by = 2)
  }
  if (length(x_breaks) == 0 || any(!is.finite(x_breaks))) {
    x_breaks <- pretty(range(event_df$event_time, na.rm = TRUE), n = 6)
  }

  max_abs_y <- max(abs(c(ci_event_df$conf.low, ci_event_df$conf.high, event_df$estimate)), na.rm = TRUE)
  if (!is.finite(max_abs_y)) {
    max_abs_y <- DID_EVENT_MIN_ABS_Y
  }
  max_abs_y <- max(DID_EVENT_MIN_ABS_Y, ceiling(max_abs_y / DID_EVENT_Y_STEP) * DID_EVENT_Y_STEP)
  y_limits <- c(-max_abs_y, max_abs_y)
  y_breaks <- seq(-max_abs_y, max_abs_y, by = DID_EVENT_Y_STEP)

  event_plot <- ggplot2::ggplot(event_df, ggplot2::aes(x = event_time, y = estimate)) +
    ggplot2::geom_hline(yintercept = 0, linetype = "solid", color = "gray35", linewidth = 0.9)

  if (!is.null(reference_event_time) && is.finite(reference_event_time)) {
    event_plot <- event_plot +
      ggplot2::geom_vline(xintercept = reference_event_time, linetype = "dotted", color = "gray50")
  }

  event_plot <- event_plot +
    ggplot2::geom_linerange(
      data = ci_event_df,
      ggplot2::aes(ymin = conf.low, ymax = conf.high),
      color = plot_color,
      linewidth = 1.1
    ) +
    ggplot2::geom_line(color = plot_color, linewidth = 1.1) +
    ggplot2::geom_point(color = plot_color, size = 2.4) +
    ggplot2::scale_x_continuous(breaks = x_breaks) +
    ggplot2::scale_y_continuous(
      breaks = y_breaks,
      limits = y_limits,
      labels = function(x) sprintf("%.2f", x)
    ) +
    ggplot2::labs(
      title = if (isTRUE(omit_title)) NULL else title,
      subtitle = if (isTRUE(omit_title)) NULL else subtitle,
      x = "Distance to treatment",
      y = y_label
    ) +
    paper_plot_theme(base_size = 11) +
    ggplot2::theme(
      plot.title = if (isTRUE(omit_title)) ggplot2::element_blank() else ggplot2::element_text(family = resolve_plot_font_family()),
      plot.subtitle = if (isTRUE(omit_title)) ggplot2::element_blank() else ggplot2::element_text(family = resolve_plot_font_family()),
      axis.title = ggplot2::element_text(family = resolve_plot_font_family()),
      axis.text = ggplot2::element_text(family = resolve_plot_font_family())
    )

  event_plot
}

matrix_to_tidy_df <- function(x, index_name = "term") {
  if (is.null(x)) {
    return(NULL)
  }

  if (is.data.frame(x)) {
    out <- as.data.frame(x)
  } else if (is.matrix(x)) {
    out <- as.data.frame(x)
  } else {
    return(NULL)
  }

  if (is.null(rownames(out))) {
    out[[index_name]] <- seq_len(nrow(out))
  } else {
    out[[index_name]] <- rownames(out)
    rownames(out) <- NULL
  }

  out
}

extract_tables_from_object <- function(x) {
  out <- list()
  if (!is.list(x)) {
    return(out)
  }

  for (nm in names(x)) {
    obj <- x[[nm]]
    if (is.data.frame(obj) || is.matrix(obj)) {
      out[[nm]] <- as.data.frame(obj)
    }
  }

  out
}

make_run_metadata <- function(config, result, diagnostics) {
  list(
    timestamp = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
    estimator = config$estimator,
    data_path = config$data_path,
    output_dir = config$output_dir,
    notes = config$notes,
    n_estimates = if (!is.null(result$estimates)) nrow(result$estimates) else 0L,
    n_event_study = if (!is.null(result$event_study)) nrow(result$event_study) else 0L,
    diagnostics = diagnostics
  )
}

write_summary_text <- function(path, text) {
  writeLines(text, con = path, useBytes = TRUE)
}
