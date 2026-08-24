# Run the complete Paper 3 analysis from any working directory.
# Optional arguments are forwarded, for example --main-catchment=20 --k=6.

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) != 1) stop("Could not determine this script's location.")
script_path <- normalizePath(sub("^--file=", "", script_arg), winslash = "/")
script_dir <- dirname(script_path)
extra_args <- commandArgs(trailingOnly = TRUE)

run_script <- function(filename) {
  status <- system2(
    file.path(R.home("bin"), "Rscript.exe"),
    args = c(shQuote(file.path(script_dir, filename)), extra_args)
  )
  if (status != 0) stop(filename, " failed with exit status ", status)
}

run_script("01_run_accessibility_models.R")
run_script("02_make_accessibility_figures.R")
run_script("05_run_haptic_sensitivity.R")
