# ============================================================
# 01_inspect_mapbox_csv.R
# Safely inspect the large Mapbox Movement CSV
# without loading the full file into memory
# ============================================================

library(readr)

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) != 1) stop("Could not determine this script's location.")
script_path <- normalizePath(sub("^--file=", "", script_arg), winslash = "/")
project_root <- normalizePath(file.path(dirname(script_path), "../../.."), winslash = "/")

raw_dir <- file.path(
  project_root,
  "data/raw"
)

output_dir <- file.path(
  project_root,
  "data/interim/mapbox"
)


# Find the Mapbox CSV automatically
mapbox_files <- list.files(
  raw_dir,
  pattern = "^MapboxMovement_sample_weekday-weekend-1_CA-qk0212122_2023-01-01_2023-12-31.*\\.csv$",
  full.names = TRUE,
  ignore.case = TRUE
)

cat("\nMatching Mapbox files:\n")
print(mapbox_files)

if (length(mapbox_files) == 0) {
  stop("Mapbox CSV not found in data/raw.")
}

mapbox_file <- mapbox_files[1]

# ------------------------------------------------------------
# File information
# ------------------------------------------------------------

info <- file.info(mapbox_file)

cat("\nUsing file:\n")
cat(mapbox_file, "\n")

cat("\nFile size:\n")
cat(round(info$size / 1024^3, 2), "GB\n")

# ------------------------------------------------------------
# Read only header
# ------------------------------------------------------------

header <- read_csv(
  mapbox_file,
  n_max = 0,
  show_col_types = FALSE
)

cat("\nCOLUMN NAMES:\n")
print(names(header))

# ------------------------------------------------------------
# Read only first 20 rows
# ------------------------------------------------------------

sample_rows <- read_csv(
  mapbox_file,
  n_max = 20,
  show_col_types = FALSE
)

cat("\nFIRST 20 ROWS:\n")
print(sample_rows, width = Inf)

cat("\nCOLUMN TYPES:\n")
str(sample_rows)

# ------------------------------------------------------------
# Save small sample for easy inspection
# ------------------------------------------------------------

sample_output <- file.path(
  output_dir,
  "mapbox_sample_first20.csv"
)

write_csv(
  sample_rows,
  sample_output
)

cat("\nSample saved to:\n")
cat(sample_output, "\n")

cat("\nDone.\n")
