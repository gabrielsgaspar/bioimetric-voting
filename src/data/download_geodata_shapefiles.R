#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(purrr)
  library(sf)
})

cmd_args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", cmd_args, value = TRUE)
if (length(file_arg) > 0) {
  script_path <- sub("^--file=", "", file_arg[[1]])
  project_root <- normalizePath(file.path(dirname(script_path), "..", ".."), mustWork = FALSE)
} else {
  project_root <- getwd()
}
if (!dir.exists(file.path(project_root, "data"))) {
  project_root <- normalizePath(getwd(), mustWork = TRUE)
}

raw_ibge_dir <- file.path(project_root, "data", "raw", "ibge", "shapefiles", "municipio_2010")
raw_ne_dir <- file.path(project_root, "data", "raw", "natural_earth")
clean_geodata_dir <- file.path(project_root, "data", "clean", "geodata")
clean_ibge_dir <- file.path(clean_geodata_dir, "ibge_municipalities_2010")
clean_ibge_uf_dir <- file.path(clean_ibge_dir, "by_uf")
clean_ne_full_dir <- file.path(clean_geodata_dir, "natural_earth_admin0_countries_10m")
clean_ne_americas_dir <- file.path(clean_geodata_dir, "natural_earth_americas_10m")
diagnostics_dir <- file.path(project_root, "data", "interim", "geodata")

dir.create(raw_ibge_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(raw_ne_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(clean_ibge_uf_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(clean_ne_full_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(clean_ne_americas_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(diagnostics_dir, recursive = TRUE, showWarnings = FALSE)

download_if_needed <- function(url, destfile) {
  if (file.exists(destfile) && file.info(destfile)$size > 0) {
    message("Already downloaded: ", destfile)
    return(invisible(destfile))
  }
  message("Downloading: ", url)
  result <- try(
    utils::download.file(
      url,
      destfile = destfile,
      mode = "wb",
      method = "libcurl",
      quiet = FALSE
    ),
    silent = TRUE
  )
  if (inherits(result, "try-error")) {
    curl_bin <- Sys.which("curl")
    if (!nzchar(curl_bin)) {
      stop(result)
    }
    status <- system2(
      curl_bin,
      args = c("-k", "-L", "--fail", "--show-error", "--output", destfile, url)
    )
    if (!identical(status, 0L)) {
      stop("curl fallback failed for ", url)
    }
  }
  invisible(destfile)
}

unzip_fresh <- function(zipfile, exdir) {
  if (dir.exists(exdir)) {
    unlink(exdir, recursive = TRUE)
  }
  dir.create(exdir, recursive = TRUE, showWarnings = FALSE)
  utils::unzip(zipfile, exdir = exdir)
  invisible(exdir)
}

remove_shapefile_sidecars <- function(shp_path) {
  stem <- tools::file_path_sans_ext(shp_path)
  files <- Sys.glob(paste0(stem, ".*"))
  if (length(files) > 0) {
    unlink(files)
  }
  invisible(shp_path)
}

uf_codes <- c(
  "ac", "al", "am", "ap", "ba", "ce", "df", "es", "go",
  "ma", "mg", "ms", "mt", "pa", "pb", "pe", "pi", "pr",
  "rj", "rn", "ro", "rr", "rs", "sc", "se", "sp", "to"
)

ibge_base_url <- "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2010"
ibge_readme_url <- file.path(ibge_base_url, "1_leia_me", "Malha_Municipal_2010.pdf")

ibge_sources <- tibble(
  uf = uf_codes,
  url = file.path(ibge_base_url, uf, paste0(uf, "_municipios.zip")),
  raw_zip = file.path(raw_ibge_dir, paste0(uf, "_municipios.zip")),
  clean_dir = file.path(clean_ibge_uf_dir, toupper(uf))
)

download_if_needed(ibge_readme_url, file.path(raw_ibge_dir, "Malha_Municipal_2010.pdf"))

walk2(ibge_sources$url, ibge_sources$raw_zip, download_if_needed)
walk2(ibge_sources$raw_zip, ibge_sources$clean_dir, unzip_fresh)

ibge_shapefiles <- map_chr(ibge_sources$clean_dir, function(path) {
  shp <- list.files(path, pattern = "\\.shp$", recursive = TRUE, full.names = TRUE)
  if (length(shp) != 1) {
    stop("Expected exactly one municipality shapefile in ", path, "; found ", length(shp))
  }
  shp
})

municipalities_2010 <- map2(ibge_shapefiles, ibge_sources$uf, function(shp, uf) {
  st_read(shp, quiet = TRUE, options = "ENCODING=LATIN1") %>%
    mutate(uf_source = toupper(uf))
}) %>%
  bind_rows()

non_municipality_codes <- c("4300001", "4300002")
excluded_non_municipality <- municipalities_2010 %>%
  filter(as.character(CD_GEOCODM) %in% non_municipality_codes)

municipalities_2010 <- municipalities_2010 %>%
  filter(!as.character(CD_GEOCODM) %in% non_municipality_codes)

excluded_path <- file.path(diagnostics_dir, "ibge_municipalities_2010_excluded_nonmunicipality_features.csv")
write.csv(
  st_drop_geometry(excluded_non_municipality),
  excluded_path,
  row.names = FALSE,
  na = ""
)

merged_ibge_path <- file.path(clean_ibge_dir, "br_municipios_2010.shp")
remove_shapefile_sidecars(merged_ibge_path)
st_write(municipalities_2010, merged_ibge_path, quiet = TRUE)

natural_earth_url <- "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip"
natural_earth_zip <- file.path(raw_ne_dir, "ne_10m_admin_0_countries.zip")
download_if_needed(natural_earth_url, natural_earth_zip)
unzip_fresh(natural_earth_zip, clean_ne_full_dir)

ne_shp <- list.files(clean_ne_full_dir, pattern = "\\.shp$", full.names = TRUE)
if (length(ne_shp) != 1) {
  stop("Expected exactly one Natural Earth shapefile; found ", length(ne_shp))
}

ne_countries <- st_read(ne_shp, quiet = TRUE)
ne_americas <- ne_countries %>%
  filter(CONTINENT %in% c("North America", "South America"))

americas_path <- file.path(clean_ne_americas_dir, "ne_10m_admin_0_countries_americas.shp")
remove_shapefile_sidecars(americas_path)
st_write(ne_americas, americas_path, quiet = TRUE)

diagnostics <- bind_rows(
  tibble(
    dataset = "ibge_municipalities_2010_by_uf",
    file = ibge_shapefiles,
    feature_count = map_int(ibge_shapefiles, ~ nrow(st_read(.x, quiet = TRUE))),
    source_url = ibge_sources$url
  ),
  tibble(
    dataset = "ibge_municipalities_2010_merged_brazil",
    file = merged_ibge_path,
    feature_count = nrow(municipalities_2010),
    source_url = paste(ibge_sources$url, collapse = " ; ")
  ),
  tibble(
    dataset = "ibge_municipalities_2010_excluded_nonmunicipality_features",
    file = excluded_path,
    feature_count = nrow(excluded_non_municipality),
    source_url = file.path(ibge_base_url, "rs", "rs_municipios.zip")
  ),
  tibble(
    dataset = "natural_earth_admin0_countries_10m",
    file = ne_shp,
    feature_count = nrow(ne_countries),
    source_url = natural_earth_url
  ),
  tibble(
    dataset = "natural_earth_americas_10m",
    file = americas_path,
    feature_count = nrow(ne_americas),
    source_url = natural_earth_url
  )
)

write.csv(
  diagnostics,
  file.path(diagnostics_dir, "shapefile_download_diagnostics.csv"),
  row.names = FALSE,
  na = ""
)

message("Wrote IBGE 2010 merged municipality shapefile: ", merged_ibge_path)
message("Wrote Natural Earth Americas shapefile: ", americas_path)
message("Wrote diagnostics: ", file.path(diagnostics_dir, "shapefile_download_diagnostics.csv"))
