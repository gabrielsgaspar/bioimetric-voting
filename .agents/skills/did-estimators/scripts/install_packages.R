packages_needed <- c(
  "did",
  "fixest",
  "didimputation",
  "DIDmultiplegt",
  "DIDmultiplegtDYN",
  "data.table",
  "arrow",
  "yaml",
  "broom",
  "ggplot2",
  "stringr",
  "dplyr",
  "tibble",
  "readr"
)

installed <- rownames(installed.packages())
missing_pkgs <- setdiff(packages_needed, installed)

if (length(missing_pkgs) == 0) {
  message("All required packages are already installed.")
} else {
  message("Installing missing packages: ", paste(missing_pkgs, collapse = ", "))
  install.packages(missing_pkgs, repos = "https://cloud.r-project.org")
}
