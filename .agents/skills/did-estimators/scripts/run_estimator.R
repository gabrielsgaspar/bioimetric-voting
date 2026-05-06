#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
  stop("Usage: Rscript .agents/skills/did-estimators/scripts/run_estimator.R path/to/config.yml", call. = FALSE)
}

script_dir <- normalizePath(".agents/skills/did-estimators/scripts", winslash = "/", mustWork = TRUE)

source(file.path(script_dir, "helpers.R"))
source(file.path(script_dir, "validate_inputs.R"))
source(file.path(script_dir, "build_event_time.R"))
source(file.path(script_dir, "save_outputs.R"))
source(file.path(script_dir, "estimator_callaway_santanna.R"))
source(file.path(script_dir, "estimator_sun_abraham.R"))
source(file.path(script_dir, "estimator_bjs.R"))
source(file.path(script_dir, "estimator_dcdh.R"))
source(file.path(script_dir, "estimator_twfe_dynamic.R"))

config_path <- args[1]
config <- parse_config(config_path)
if (!is.null(config$seed)) {
  set.seed(as.integer(config$seed))
}
config$output_dir <- ensure_output_dir(config$output_dir)

data <- read_input_data(config$data_path, config$file_format)
validated <- prepare_analysis_data(data, config)

runner <- switch(
  config$estimator,
  callaway_santanna = run_callaway_santanna,
  sun_abraham = run_sun_abraham,
  bjs = run_bjs,
  dcdh = run_dcdh,
  twfe_dynamic = run_twfe_dynamic,
  stopf("Unsupported estimator `%s`.", config$estimator)
)

result <- runner(validated$data, config)
save_run_outputs(result, config, validated$diagnostics)

message(sprintf("Finished `%s`. Outputs written to %s", config$estimator, config$output_dir))
