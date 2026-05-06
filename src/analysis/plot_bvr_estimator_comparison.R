#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)

helper_path <- "/Users/gabrielsgaspar/.codex/skills/reg-did/scripts/helpers.R"
if (!file.exists(helper_path)) {
  stop(sprintf("Could not find reg-did helper theme at %s", helper_path), call. = FALSE)
}
source(helper_path)
require_packages(c("ggplot2"))

`%||%` <- function(x, y) if (is.null(x)) y else x

estimator_order <- c("callaway_santanna", "bjs", "dcdh", "twfe_dynamic")
estimator_labels <- c(
  callaway_santanna = "Callaway-Sant'Anna",
  bjs = "Borusyak-Jaravel-Spiess",
  dcdh = "de Chaisemartin-D'Haultfoeuille",
  twfe_dynamic = "Dynamic TWFE"
)
x_breaks <- seq(-8, 8, by = 2)
offset_step <- 0.24
point_size <- 2.2
ci_linewidth <- 1.0

plot_one <- function(data_path, output_dir = dirname(data_path)) {
  data <- read.csv(data_path, stringsAsFactors = FALSE)
  data$event_time <- as.numeric(data$event_time)
  data$estimate <- as.numeric(data$estimate)
  data$conf.low <- as.numeric(data$conf.low)
  data$conf.high <- as.numeric(data$conf.high)

  present <- estimator_order[estimator_order %in% unique(data$estimator)]
  if (length(present) == 0) {
    stop(sprintf("No known estimators found in %s", data_path), call. = FALSE)
  }

  offsets <- setNames((seq_along(present) - (length(present) + 1) / 2) * offset_step, present)
  data <- data[data$estimator %in% present, , drop = FALSE]
  data$estimator <- factor(data$estimator, levels = present)
  data$x_plot <- data$event_time + offsets[as.character(data$estimator)]

  color_values <- vapply(
    present,
    function(estimator) {
      values <- unique(data$color[as.character(data$estimator) == estimator])
      values[!is.na(values) & nzchar(values)][1]
    },
    character(1)
  )
  names(color_values) <- present
  color_labels <- estimator_labels[present]

  bounds <- c(data$conf.low, data$conf.high, data$estimate)
  bounds <- bounds[is.finite(bounds)]
  max_abs_y <- if (length(bounds) > 0) max(abs(bounds)) else DID_EVENT_MIN_ABS_Y
  max_abs_y <- max(DID_EVENT_MIN_ABS_Y, ceiling(max_abs_y / DID_EVENT_Y_STEP) * DID_EVENT_Y_STEP)
  y_limits <- c(-max_abs_y, max_abs_y)
  y_breaks <- seq(y_limits[1], y_limits[2], by = DID_EVENT_Y_STEP)

  ci_data <- data[is.finite(data$conf.low) & is.finite(data$conf.high), , drop = FALSE]

  plot <- ggplot2::ggplot(data, ggplot2::aes(x = x_plot, y = estimate, color = estimator)) +
    ggplot2::geom_hline(yintercept = 0, color = "gray35", linewidth = 1.1) +
    ggplot2::geom_vline(xintercept = -2, color = "gray50", linetype = "dashed", linewidth = 0.7) +
    ggplot2::geom_linerange(
      data = ci_data,
      ggplot2::aes(ymin = conf.low, ymax = conf.high),
      linewidth = ci_linewidth,
      show.legend = FALSE
    ) +
    ggplot2::geom_point(size = point_size) +
    ggplot2::scale_color_manual(values = color_values, breaks = present, labels = color_labels) +
    ggplot2::scale_x_continuous(breaks = x_breaks, limits = c(min(x_breaks) - 0.55, max(x_breaks) + 0.55)) +
    ggplot2::scale_y_continuous(
      breaks = y_breaks,
      limits = y_limits,
      labels = function(x) sprintf("%.2f", x)
    ) +
    ggplot2::labs(x = "Distance to treatment", y = NULL, color = NULL) +
    paper_plot_theme(base_size = 11) +
    ggplot2::theme(
      panel.grid.major = ggplot2::element_line(color = DID_EVENT_GRID_COLOR, linewidth = 0.4),
      panel.border = ggplot2::element_rect(color = "black", fill = NA, linewidth = 0.6),
      legend.position = c(0.02, 0.98),
      legend.justification = c(0, 1),
      legend.direction = "horizontal",
      legend.background = ggplot2::element_rect(fill = "white", color = "gray75", linewidth = 0.4),
      legend.box.background = ggplot2::element_rect(fill = "white", color = "gray75", linewidth = 0.4),
      legend.key = ggplot2::element_rect(fill = "white", color = NA),
      legend.key.size = grid::unit(11, "pt"),
      legend.key.width = grid::unit(12, "pt"),
      legend.margin = ggplot2::margin(2, 4, 2, 4),
      legend.spacing.x = grid::unit(3, "pt"),
      legend.spacing.y = grid::unit(1, "pt"),
      legend.box.spacing = grid::unit(1, "pt"),
      legend.text = ggplot2::element_text(margin = ggplot2::margin(r = 5, l = 1))
    ) +
    ggplot2::guides(color = ggplot2::guide_legend(ncol = 2, byrow = TRUE, override.aes = list(size = point_size)))

  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  plot_family <- resolve_plot_font_family()
  ggplot2::ggsave(
    file.path(output_dir, "estimator_comparison.pdf"),
    plot = plot,
    device = grDevices::cairo_pdf,
    family = plot_family,
    width = 8,
    height = 5,
    bg = "white"
  )
  ggplot2::ggsave(
    file.path(output_dir, "estimator_comparison.png"),
    plot = plot,
    device = grDevices::png,
    type = "cairo",
    width = 8,
    height = 5,
    dpi = 320,
    bg = "white"
  )
}

if (length(args) == 1 && dir.exists(args[[1]])) {
  data_paths <- list.files(args[[1]], pattern = "^estimator_comparison_data\\.csv$", recursive = TRUE, full.names = TRUE)
  if (length(data_paths) == 0) {
    stop(sprintf("No estimator_comparison_data.csv files found under %s", args[[1]]), call. = FALSE)
  }
  for (path in data_paths) {
    plot_one(path)
  }
} else if (length(args) == 2) {
  plot_one(args[[1]], args[[2]])
} else {
  stop("Usage: Rscript src/analysis/plot_bvr_estimator_comparison.R <root-dir> OR <data-csv> <output-dir>", call. = FALSE)
}
