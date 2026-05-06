#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(arrow)
  library(dplyr)
})

input_path <- "data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.parquet"
output_path <- "data/interim/tse/tse_clean_panel_2000_2018_bvr_status_updated_norm_2006.csv"
diagnostics_path <- "data/interim/tse/norm_2006_voter_outcomes_diagnostics.csv"

required_columns <- c(
  "municipality_id",
  "year_election",
  "num_voters",
  "num_voters_high_ed",
  "num_voters_low_ed"
)

panel <- read_parquet(input_path)

missing_columns <- setdiff(required_columns, names(panel))
if (length(missing_columns) > 0) {
  stop("Missing required columns: ", paste(missing_columns, collapse = ", "))
}

denominators <- panel %>%
  filter(year_election == 2006) %>%
  count(municipality_id, name = "n_2006_rows")

duplicate_2006 <- denominators %>%
  filter(n_2006_rows > 1)

if (nrow(duplicate_2006) > 0) {
  stop("Duplicate municipality_id x 2006 rows found in the clean panel.")
}

denominators <- panel %>%
  filter(year_election == 2006) %>%
  transmute(
    municipality_id,
    num_voters_2006 = num_voters
  )

panel_norm <- panel %>%
  mutate(
    num_voters_unk_ed = num_voters - num_voters_high_ed - num_voters_low_ed
  )

negative_unknown <- panel_norm %>%
  filter(!is.na(num_voters_unk_ed), num_voters_unk_ed < 0)

if (nrow(negative_unknown) > 0) {
  stop("Found negative unknown-education voter counts after residual construction.")
}

panel_norm <- panel_norm %>%
  left_join(denominators, by = "municipality_id") %>%
  mutate(
    norm_2006_voters = if_else(
      !is.na(num_voters_2006) & num_voters_2006 > 0,
      num_voters / num_voters_2006,
      NA_real_
    ),
    norm_2006_voters_high_ed = if_else(
      !is.na(num_voters_2006) & num_voters_2006 > 0,
      num_voters_high_ed / num_voters_2006,
      NA_real_
    ),
    norm_2006_voters_low_ed = if_else(
      !is.na(num_voters_2006) & num_voters_2006 > 0,
      num_voters_low_ed / num_voters_2006,
      NA_real_
    ),
    norm_2006_voters_unk_ed = if_else(
      !is.na(num_voters_2006) & num_voters_2006 > 0,
      num_voters_unk_ed / num_voters_2006,
      NA_real_
    )
  )

check_2006 <- panel_norm %>%
  filter(year_election == 2006, !is.na(num_voters_2006), num_voters_2006 > 0) %>%
  mutate(
    total_norm_error = abs(norm_2006_voters - 1),
    component_identity_error = abs(
      norm_2006_voters -
        norm_2006_voters_high_ed -
        norm_2006_voters_low_ed -
        norm_2006_voters_unk_ed
    )
  )

diagnostics <- tibble(
  metric = c(
    "input_rows",
    "input_municipalities",
    "municipalities_with_2006_denominator",
    "municipalities_without_2006_denominator",
    "rows_missing_2006_denominator",
    "negative_unknown_education_rows",
    "max_abs_2006_total_norm_error",
    "max_abs_2006_component_identity_error"
  ),
  value = c(
    nrow(panel),
    n_distinct(panel$municipality_id),
    nrow(denominators),
    n_distinct(panel$municipality_id) - nrow(denominators),
    sum(is.na(panel_norm$num_voters_2006)),
    nrow(negative_unknown),
    max(check_2006$total_norm_error, na.rm = TRUE),
    max(check_2006$component_identity_error, na.rm = TRUE)
  )
)

write.csv(panel_norm, output_path, row.names = FALSE, na = "")
write.csv(diagnostics, diagnostics_path, row.names = FALSE, na = "")

message("Wrote normalized panel to ", output_path)
message("Wrote diagnostics to ", diagnostics_path)
