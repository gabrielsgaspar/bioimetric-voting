#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(sf)
})

sf_use_s2(FALSE)

cmd_args <- commandArgs(FALSE)
file_arg <- grep("^--file=", cmd_args, value = TRUE)
if (length(file_arg) > 0) {
  script_path <- sub("^--file=", "", file_arg[[1]])
  project_root <- normalizePath(file.path(dirname(script_path), "..", ".."), mustWork = FALSE)
} else {
  project_root <- normalizePath(getwd(), mustWork = TRUE)
}
if (!dir.exists(file.path(project_root, "resources"))) {
  project_root <- normalizePath(getwd(), mustWork = TRUE)
}

municipality_path <- file.path(
  project_root,
  "data",
  "clean",
  "geodata",
  "ibge_municipalities_2010",
  "br_municipios_2010.shp"
)
americas_path <- file.path(
  project_root,
  "data",
  "clean",
  "geodata",
  "natural_earth_americas_10m",
  "ne_10m_admin_0_countries_americas.shp"
)
bvr_panel_path <- file.path(
  project_root,
  "data",
  "clean",
  "tse",
  "tse_clean_panel_2000_2018_bvr_status_updated.csv"
)
output_dir <- file.path(project_root, "resources", "maps")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

treatment_years <- c(2008L, 2010L, 2012L, 2014L, 2016L, 2018L)
treatment_palette <- c(
  "2008" = "#e5d6f8",
  "2010" = "#c7a5ee",
  "2012" = "#a978df",
  "2014" = "#894cc7",
  "2016" = "#682ca2",
  "2018" = "#44145f"
)
neutral_municipality_fill <- "#f8f5ec"
hybrid_hatch_color <- neutral_municipality_fill

make_diagonal_lines <- function(xlim, ylim, spacing = 0.55, slope = 1) {
  intercepts <- seq(
    from = ylim[[1]] - slope * xlim[[2]],
    to = ylim[[2]] - slope * xlim[[1]],
    by = spacing
  )

  lines <- lapply(intercepts, function(intercept) {
    candidates <- rbind(
      c(xlim[[1]], slope * xlim[[1]] + intercept),
      c(xlim[[2]], slope * xlim[[2]] + intercept),
      c((ylim[[1]] - intercept) / slope, ylim[[1]]),
      c((ylim[[2]] - intercept) / slope, ylim[[2]])
    )
    inside <- candidates[
      candidates[, 1] >= xlim[[1]] - 1e-8 &
        candidates[, 1] <= xlim[[2]] + 1e-8 &
        candidates[, 2] >= ylim[[1]] - 1e-8 &
        candidates[, 2] <= ylim[[2]] + 1e-8,
      ,
      drop = FALSE
    ]
    inside <- unique(round(inside, digits = 8))
    if (nrow(inside) < 2) {
      return(NULL)
    }

    distances <- as.matrix(dist(inside))
    endpoints <- which(distances == max(distances), arr.ind = TRUE)[1, ]
    st_linestring(inside[endpoints, , drop = FALSE])
  })

  st_sfc(Filter(Negate(is.null), lines), crs = 4326)
}

americas <- st_read(americas_path, quiet = TRUE) %>%
  st_make_valid() %>%
  st_transform(4326)

brazil_municipalities <- st_read(municipality_path, quiet = TRUE) %>%
  filter(as.character(CD_GEOCODM) != "2605459") %>%
  mutate(municipality_id = as.character(CD_GEOCODM)) %>%
  st_make_valid() %>%
  st_transform(4326)
st_geometry(brazil_municipalities) <- st_simplify(
  st_geometry(brazil_municipalities),
  dTolerance = 0.025,
  preserveTopology = TRUE
)

bvr_timing <- read.csv(bvr_panel_path, stringsAsFactors = FALSE) %>%
  mutate(
    municipality_id = as.character(municipality_id),
    year_first_any_bvr = as.integer(year_first_any_bvr),
    hybrid = as.integer(hybrid)
  ) %>%
  group_by(municipality_id) %>%
  summarise(
    municipality_name = first(municipality_name),
    state = first(state),
    first_treatment_year = if (any(year_first_any_bvr %in% treatment_years, na.rm = TRUE)) {
      min(year_first_any_bvr[year_first_any_bvr %in% treatment_years], na.rm = TRUE)
    } else {
      NA_integer_
    },
    ever_hybrid = any(hybrid == 1, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  mutate(
    treatment_year_label = factor(
      first_treatment_year,
      levels = treatment_years,
      labels = as.character(treatment_years)
    )
  )

not_plotted <- bvr_timing %>%
  anti_join(
    brazil_municipalities %>%
      st_drop_geometry() %>%
      distinct(municipality_id),
    by = "municipality_id"
  ) %>%
  arrange(state, municipality_name)

not_plotted_path <- file.path(
  output_dir,
  "brazil_municipalities_bvr_treatment_year_not_plotted.csv"
)
write.csv(not_plotted, not_plotted_path, row.names = FALSE)

brazil_municipalities <- brazil_municipalities %>%
  left_join(bvr_timing, by = "municipality_id")

treated_municipalities <- brazil_municipalities %>%
  filter(!is.na(treatment_year_label))

hybrid_municipalities <- brazil_municipalities %>%
  filter(ever_hybrid)

south_america_context <- americas %>%
  filter(CONTINENT == "South America", ADMIN != "Brazil")

brazil_outline <- americas %>%
  filter(ADMIN == "Brazil")

map_xlim <- c(-76.1, -32.7)
map_ylim <- c(-34.45, 5.95)
map_mean_lat <- mean(map_ylim) * pi / 180
export_width <- 8.4
export_height <- export_width * diff(map_ylim) / (diff(map_xlim) * cos(map_mean_lat))
map_frame <- st_as_sfc(
  st_bbox(
    c(
      xmin = map_xlim[[1]],
      xmax = map_xlim[[2]],
      ymin = map_ylim[[1]],
      ymax = map_ylim[[2]]
    ),
    crs = st_crs(4326)
  )
)

diagonal_lines <- st_sf(geometry = make_diagonal_lines(map_xlim, map_ylim, spacing = 0.32))
hybrid_union <- st_sf(geometry = st_union(st_geometry(hybrid_municipalities)))
hybrid_hatches <- suppressWarnings(st_intersection(diagonal_lines, hybrid_union))
hybrid_hatches <- st_sf(
  geometry = st_collection_extract(st_geometry(hybrid_hatches), "LINESTRING")
)

plot <- ggplot() +
  geom_sf(
    data = south_america_context,
    fill = "#d8d6cc",
    color = "#ffffff",
    linewidth = 0.22
  ) +
  geom_sf(
    data = brazil_municipalities,
    fill = neutral_municipality_fill,
    color = "#8d9294",
    linewidth = 0.014
  ) +
  geom_sf(
    data = treated_municipalities,
    aes(fill = treatment_year_label),
    color = "#7a7281",
    linewidth = 0.014
  ) +
  geom_sf(
    data = hybrid_hatches,
    color = hybrid_hatch_color,
    linewidth = 0.075,
    alpha = 0.85
  ) +
  geom_sf(
    data = hybrid_municipalities,
    fill = NA,
    color = "#201126",
    linewidth = 0.025
  ) +
  geom_sf(
    data = brazil_outline,
    fill = NA,
    color = "#29383d",
    linewidth = 0.38
  ) +
  geom_sf(
    data = map_frame,
    fill = NA,
    color = "#111111",
    linewidth = 0.9
  ) +
  scale_fill_manual(
    values = treatment_palette,
    breaks = names(treatment_palette),
    drop = FALSE,
    name = "First BVR year"
  ) +
  coord_sf(
    xlim = map_xlim,
    ylim = map_ylim,
    expand = FALSE,
    datum = NA,
    clip = "on"
  ) +
  guides(
    fill = guide_legend(
      title.position = "top",
      ncol = 2,
      byrow = TRUE,
      override.aes = list(color = "#7a7281", linewidth = 0.2)
    )
  ) +
  theme_void(base_size = 11) +
  theme(
    plot.background = element_rect(fill = "#d9eef8", color = NA),
    panel.background = element_rect(fill = "#d9eef8", color = NA),
    panel.border = element_rect(fill = NA, color = "#111111", linewidth = 0.9),
    legend.position = c(0.965, 0.965),
    legend.justification = c("right", "top"),
    legend.background = element_rect(fill = "#ffffff", color = "#111111", linewidth = 0.35),
    legend.margin = margin(5, 6, 5, 6),
    legend.key = element_rect(fill = "#ffffff", color = NA),
    legend.key.size = unit(0.36, "cm"),
    legend.title = element_text(size = 8.5, face = "bold", color = "#111111"),
    legend.text = element_text(size = 8, color = "#111111"),
    plot.margin = margin(0, 0, 0, 0)
  )

png_path <- file.path(output_dir, "brazil_municipalities_bvr_treatment_year.png")
pdf_path <- file.path(output_dir, "brazil_municipalities_bvr_treatment_year.pdf")

ggsave(
  filename = png_path,
  plot = plot,
  width = export_width,
  height = export_height,
  dpi = 360,
  bg = "#d9eef8"
)
ggsave(
  filename = pdf_path,
  plot = plot,
  width = export_width,
  height = export_height,
  bg = "#d9eef8"
)

message("Treated municipalities by first BVR year:")
print(table(treated_municipalities$treatment_year_label, useNA = "ifany"))
message("Hybrid municipalities hatched: ", nrow(hybrid_municipalities))
message("Panel municipalities not plotted: ", nrow(not_plotted))
message("Wrote ", not_plotted_path)
message("Wrote ", png_path)
message("Wrote ", pdf_path)
