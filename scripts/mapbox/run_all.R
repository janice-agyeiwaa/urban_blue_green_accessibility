# Run the complete canonical Paper 4 analysis from any working directory.

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) != 1) stop("Could not determine this script's location.")
script_path <- normalizePath(sub("^--file=", "", script_arg), winslash = "/")
script_dir <- dirname(script_path)

run_script <- function(filename) {
  message("\n===== ", filename, " =====")
  status <- system2(
    file.path(R.home("bin"), "Rscript.exe"),
    args = shQuote(file.path(script_dir, filename))
  )
  if (status != 0) stop(filename, " failed with exit status ", status)
}

run_script("01_build_analysis_dataset.R")
run_script("02_run_mixed_models.R")
run_script("03_run_spatial_filtering.R")
run_script("04_run_spatial_sensitivities.R")
run_script("05_make_outputs.R")
