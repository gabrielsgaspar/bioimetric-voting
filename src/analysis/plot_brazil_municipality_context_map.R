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
output_dir <- file.path(project_root, "resources", "maps")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

americas <- st_read(americas_path, quiet = TRUE) %>%
  st_make_valid() %>%
  st_transform(4326)

brazil_municipalities <- st_read(municipality_path, quiet = TRUE) %>%
  filter(as.character(CD_GEOCODM) != "2605459") %>%
  st_make_valid() %>%
  st_transform(4326)
st_geometry(brazil_municipalities) <- st_simplify(
  st_geometry(brazil_municipalities),
  dTolerance = 0.025,
  preserveTopology = TRUE
)

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

plot <- ggplot() +
  geom_sf(
    data = south_america_context,
    fill = "#d8d6cc",
    color = "#ffffff",
    linewidth = 0.22
  ) +
  geom_sf(
    data = brazil_municipalities,
    fill = "#f8f5ec",
    color = "#7f8789",
    linewidth = 0.018
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
  coord_sf(
    xlim = map_xlim,
    ylim = map_ylim,
    expand = FALSE,
    datum = NA,
    clip = "on"
  ) +
  theme_void(base_size = 11) +
  theme(
    plot.background = element_rect(fill = "#d9eef8", color = NA),
    panel.background = element_rect(fill = "#d9eef8", color = NA),
    panel.border = element_rect(fill = NA, color = "#111111", linewidth = 0.9),
    plot.margin = margin(0, 0, 0, 0)
  )

png_path <- file.path(output_dir, "brazil_municipalities.png")
pdf_path <- file.path(output_dir, "brazil_municipalities.pdf")

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

message("Wrote ", png_path)
message("Wrote ", pdf_path)
