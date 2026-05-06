#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(datasus)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
  stop("Usage: Rscript src/analysis/export_datasus_downstream_outcomes.R path/to/output.csv")
}

output_path <- args[[1]]
years <- c(2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022)

extract_code_name <- function(x) {
  x <- trimws(as.character(x))
  code6 <- sub("^([0-9]{6}).*$", "\\1", x)
  name <- sub("^[0-9]{6}\\s+", "", x)
  data.frame(code6 = code6, municipality_name_datasus = name, stringsAsFactors = FALSE)
}

get_value_column <- function(df) {
  if (ncol(df) < 2) {
    stop("Expected at least two columns in DATASUS table.")
  }
  names(df)[2]
}

normalize_datasus_table <- function(df, value_name, year) {
  if (nrow(df) == 0) {
    return(data.frame())
  }

  first_col <- names(df)[1]
  value_col <- get_value_column(df)
  out <- cbind(extract_code_name(df[[first_col]]), value = as.numeric(df[[value_col]]))
  out <- out[!is.na(out$value), , drop = FALSE]
  out <- out[out$code6 != "TOTAL" & grepl("^[0-9]{6}$", out$code6), , drop = FALSE]
  names(out)[names(out) == "value"] <- value_name
  out$year <- year
  out
}

normalize_prenatal_table <- function(df, year) {
  if (nrow(df) == 0) {
    return(data.frame())
  }

  first_col <- names(df)[1]
  prenatal_col <- grep("^7 ou mais consultas$", names(df), value = TRUE)
  total_col <- grep("^Total$", names(df), value = TRUE)
  if (length(prenatal_col) == 0 || length(total_col) == 0) {
    stop("Could not find prenatal or total columns in SINASC prenatal table.")
  }

  out <- cbind(
    extract_code_name(df[[first_col]]),
    births_prenatal_7plus = as.numeric(df[[prenatal_col[1]]])
  )
  out <- out[grepl("^[0-9]{6}$", out$code6), , drop = FALSE]
  out$year <- year
  out
}

safe_query <- function(expr) {
  tryCatch(expr, error = function(e) NULL)
}

message("Downloading DATASUS SIM/SINASC tables...")

rows <- list()

for (year in years) {
  year_chr <- as.character(year)
  message(sprintf("  Year %s", year_chr))

  infant_df <- safe_query(sim_inf10_mun(periodo = year_chr))
  neonatal_df <- safe_query(sim_inf10_mun(periodo = year_chr, faixa_etaria_detalhada = as.character(1:111)))
  births_df <- safe_query(sinasc_nv_mun(periodo = year_chr))
  prenatal7_df <- safe_query(sinasc_nv_mun(periodo = year_chr, coluna = "Consult_pr\u00e9-natal"))

  infant_norm <- if (!is.null(infant_df)) normalize_datasus_table(infant_df, "deaths_under_1", year) else data.frame()
  neonatal_norm <- if (!is.null(neonatal_df)) normalize_datasus_table(neonatal_df, "deaths_neonatal_0_27d", year) else data.frame()
  births_norm <- if (!is.null(births_df)) normalize_datasus_table(births_df, "live_births", year) else data.frame()
  prenatal7_norm <- if (!is.null(prenatal7_df)) normalize_prenatal_table(prenatal7_df, year) else data.frame()

  merged <- Reduce(
    function(x, y) merge(x, y, by = c("code6", "municipality_name_datasus", "year"), all = TRUE),
    Filter(function(x) nrow(x) > 0, list(infant_norm, neonatal_norm, births_norm, prenatal7_norm))
  )

  if (is.null(merged) || nrow(merged) == 0) {
    next
  }

  rows[[length(rows) + 1]] <- merged
}

if (length(rows) == 0) {
  stop("No DATASUS data could be downloaded.")
}

out <- do.call(rbind, rows)
dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
write.csv(out, output_path, row.names = FALSE, na = "")
message(sprintf("Wrote %s with %s rows.", output_path, nrow(out)))
