# ============================================================
# 02_match_mapbox_cells_to_sites.R
#
# Purpose:
# 1. Read the 114-site Mapbox extraction polygons
# 2. Extract unique Mapbox grid-cell centroids near Metro Vancouver
# 3. Match Mapbox centroids to the 114 extraction areas
# 4. Save geography -> park_num lookup tables
#
# IMPORTANT:
# - No new 100 m buffer is created here.
# - The extraction polygons already contain the land + water
#   areas prepared from the existing 100 m source layers.
# ============================================================

library(sf)
library(DBI)
library(duckdb)
library(dplyr)
library(readr)

# ------------------------------------------------------------
# Project paths
# ------------------------------------------------------------

project_root <- paste0(
  "C:/Users/owusu/Desktop/work/under_lab/",
  "urban_blue_green_accessibility"
)

raw_dir <- file.path(
  project_root,
  "data/raw"
)

interim_dir <- file.path(
  project_root,
  "data/interim/mapbox"
)

dir.create(
  interim_dir,
  recursive = TRUE,
  showWarnings = FALSE
)

# ------------------------------------------------------------
# Locate Mapbox CSV
# ------------------------------------------------------------

mapbox_files <- list.files(
  raw_dir,
  pattern =
    "^MapboxMovement_sample_weekday-weekend-1_CA-qk0212122_2023-01-01_2023-12-31.*\\.csv$",
  full.names = TRUE,
  ignore.case = TRUE
)

if (length(mapbox_files) == 0) {
  stop("Mapbox CSV not found in data/raw.")
}

mapbox_file <- normalizePath(
  mapbox_files[1],
  winslash = "/",
  mustWork = TRUE
)

cat("\nMapbox CSV:\n")
cat(mapbox_file, "\n")

# ------------------------------------------------------------
# Read extraction polygons from GeoPackage
# ------------------------------------------------------------

gpkg_path <- file.path(
  interim_dir,
  "mapbox_extraction.gpkg"
)

if (!file.exists(gpkg_path)) {
  stop(
    paste(
      "Could not find GeoPackage:",
      gpkg_path
    )
  )
}

cat("\nLayers in GeoPackage:\n")

gpkg_layers <- st_layers(gpkg_path)

print(
  gpkg_layers$name
)

# From your ArcGIS screenshot, the layer is:
# main.mapbox_extraction

parks <- st_read(
  dsn = gpkg_path,
  layer = "main.mapbox_extraction",
  quiet = TRUE
)

cat("\nExtraction layer loaded.\n")
cat("Number of records:", nrow(parks), "\n")

cat("\nColumns:\n")
print(names(parks))

cat("\nGeometry types:\n")
print(
  table(
    st_geometry_type(parks)
  )
)

# ------------------------------------------------------------
# Check park_num
# ------------------------------------------------------------

if (!"park_num" %in% names(parks)) {
  stop(
    paste(
      "The GeoPackage layer does not contain park_num.",
      "Columns found:",
      paste(names(parks), collapse = ", ")
    )
  )
}

parks <- parks %>%
  mutate(
    park_num = as.character(park_num)
  )

cat(
  "\nUnique park_num:",
  n_distinct(parks$park_num),
  "\n"
)

if (nrow(parks) != 114) {
  warning(
    paste(
      "Expected 114 records but found",
      nrow(parks)
    )
  )
}

if (n_distinct(parks$park_num) != 114) {
  warning(
    paste(
      "Expected 114 unique park numbers but found",
      n_distinct(parks$park_num)
    )
  )
}

# ------------------------------------------------------------
# Check CRS
# ------------------------------------------------------------

cat("\nOriginal CRS:\n")
print(st_crs(parks))

# Transform to WGS84 because Mapbox xlon/xlat are
# longitude/latitude coordinates.

parks_wgs84 <- st_transform(
  parks,
  4326
)

cat("\nTransformed CRS:\n")
print(st_crs(parks_wgs84))

# ------------------------------------------------------------
# Overall study-area bounding box
# ------------------------------------------------------------

study_bbox <- st_bbox(
  parks_wgs84
)

xmin <- as.numeric(
  study_bbox["xmin"]
)

ymin <- as.numeric(
  study_bbox["ymin"]
)

xmax <- as.numeric(
  study_bbox["xmax"]
)

ymax <- as.numeric(
  study_bbox["ymax"]
)

cat("\nStudy-area bounding box:\n")

cat(
  "xmin:",
  xmin,
  "\n"
)

cat(
  "ymin:",
  ymin,
  "\n"
)

cat(
  "xmax:",
  xmax,
  "\n"
)

cat(
  "ymax:",
  ymax,
  "\n"
)

# ------------------------------------------------------------
# Connect to DuckDB
# ------------------------------------------------------------

con <- dbConnect(
  duckdb::duckdb(),
  dbdir = ":memory:"
)

# ------------------------------------------------------------
# Extract UNIQUE Mapbox cells within broad study bbox
#
# We do NOT load all 59 million activity rows.
#
# geography is explicitly read as VARCHAR so leading zeros
# remain intact.
# ------------------------------------------------------------

cat(
  "\nExtracting unique Mapbox cells within the study bounding box...\n"
)

cell_query <- sprintf(
  "
  SELECT DISTINCT
    CAST(geography AS VARCHAR) AS geography,
    xlon,
    xlat

  FROM read_csv_auto(
    '%s',
    header = true,
    types = {'geography': 'VARCHAR'}
  )

  WHERE
    xlon BETWEEN %.10f AND %.10f
    AND
    xlat BETWEEN %.10f AND %.10f
  ",
  mapbox_file,
  xmin,
  xmax,
  ymin,
  ymax
)

mapbox_cells <- dbGetQuery(
  con,
  cell_query
)

cat(
  "\nUnique Mapbox cells inside broad bounding box:",
  nrow(mapbox_cells),
  "\n"
)

cat(
  "Unique geography IDs:",
  n_distinct(mapbox_cells$geography),
  "\n"
)

# ------------------------------------------------------------
# Disconnect DuckDB for now
# ------------------------------------------------------------

dbDisconnect(
  con,
  shutdown = TRUE
)

# ------------------------------------------------------------
# Convert Mapbox centroid coordinates to sf points
#
# xlon/xlat represent the centroid of each original
# 100 m x 100 m Mapbox grid cell.
# ------------------------------------------------------------

cat(
  "\nConverting Mapbox cell centroids to spatial points...\n"
)

mapbox_points <- st_as_sf(
  mapbox_cells,
  coords = c(
    "xlon",
    "xlat"
  ),
  crs = 4326,
  remove = FALSE
)

cat(
  "\nMapbox points created:",
  nrow(mapbox_points),
  "\n"
)

# ------------------------------------------------------------
# Keep only park_num + geometry
# ------------------------------------------------------------

park_geometry <- parks_wgs84 %>%
  select(
    park_num
  )

# ------------------------------------------------------------
# Spatial matching
#
# The point is the centroid of the original Mapbox grid cell.
#
# We retain a grid cell when its centroid point falls within
# one of the extraction polygons.
# ------------------------------------------------------------

cat(
  "\nMatching Mapbox grid-cell centroids to the 114 extraction areas...\n"
)

matched_points <- st_join(
  mapbox_points,
  park_geometry,
  join = st_within,
  left = FALSE
)

cat(
  "\nSpatial matching complete.\n"
)

# ------------------------------------------------------------
# Create lookup table
# ------------------------------------------------------------

cell_park_lookup <- matched_points %>%
  st_drop_geometry() %>%
  select(
    park_num,
    geography,
    xlon,
    xlat
  ) %>%
  distinct()

# ------------------------------------------------------------
# QA 1: Overall matching
# ------------------------------------------------------------

cat("\n============================================\n")
cat("QA 1: OVERALL MATCHING\n")
cat("============================================\n")

cat(
  "\nTotal park-cell matches:",
  nrow(cell_park_lookup),
  "\n"
)

cat(
  "Unique Mapbox cells matched:",
  n_distinct(cell_park_lookup$geography),
  "\n"
)

cat(
  "Parks receiving at least one Mapbox cell:",
  n_distinct(cell_park_lookup$park_num),
  "\n"
)

# ------------------------------------------------------------
# QA 2: Cells per park
# ------------------------------------------------------------

cells_per_park <- cell_park_lookup %>%
  count(
    park_num,
    name = "mapbox_cell_count"
  ) %>%
  arrange(
    as.numeric(park_num)
  )

cat("\n============================================\n")
cat("QA 2: MAPBOX CELLS PER PARK\n")
cat("============================================\n")

print(
  cells_per_park,
  n = nrow(cells_per_park)
)

cat(
  "\nMinimum cells in a park:",
  min(cells_per_park$mapbox_cell_count),
  "\n"
)

cat(
  "Maximum cells in a park:",
  max(cells_per_park$mapbox_cell_count),
  "\n"
)

cat(
  "Median cells per park:",
  median(cells_per_park$mapbox_cell_count),
  "\n"
)

# ------------------------------------------------------------
# QA 3: Parks with no matched Mapbox cells
# ------------------------------------------------------------

all_parks <- parks_wgs84 %>%
  st_drop_geometry() %>%
  distinct(
    park_num
  )

parks_without_cells <- all_parks %>%
  anti_join(
    cells_per_park,
    by = "park_num"
  )

cat("\n============================================\n")
cat("QA 3: PARKS WITH ZERO MAPBOX CELLS\n")
cat("============================================\n")

if (nrow(parks_without_cells) == 0) {

  cat("\nNone\n")

} else {

  print(
    parks_without_cells
  )
}

# ------------------------------------------------------------
# QA 4: Grid cells assigned to more than one park
#
# This may happen if extraction areas overlap.
# It is not automatically an error.
# ------------------------------------------------------------

cells_multiple_parks <- cell_park_lookup %>%
  distinct(
    geography,
    park_num
  ) %>%
  count(
    geography,
    name = "park_count"
  ) %>%
  filter(
    park_count > 1
  ) %>%
  arrange(
    desc(park_count)
  )

cat("\n============================================\n")
cat("QA 4: CELLS ASSIGNED TO MULTIPLE PARKS\n")
cat("============================================\n")

cat(
  "\nNumber of grid cells assigned to more than one park:",
  nrow(cells_multiple_parks),
  "\n"
)

if (nrow(cells_multiple_parks) > 0) {

  cat(
    "\nFirst 20 overlapping grid cells:\n"
  )

  print(
    head(
      cells_multiple_parks,
      20
    )
  )
}

# ------------------------------------------------------------
# QA 5: Check duplicated lookup rows
# ------------------------------------------------------------

duplicate_lookup_rows <- cell_park_lookup %>%
  count(
    park_num,
    geography
  ) %>%
  filter(
    n > 1
  )

cat("\n============================================\n")
cat("QA 5: DUPLICATE LOOKUP ROWS\n")
cat("============================================\n")

cat(
  "\nDuplicate park_num + geography combinations:",
  nrow(duplicate_lookup_rows),
  "\n"
)

# ------------------------------------------------------------
# Save outputs
# ------------------------------------------------------------

lookup_output <- file.path(
  interim_dir,
  "mapbox_cell_park_lookup_2023.csv"
)

counts_output <- file.path(
  interim_dir,
  "mapbox_cell_counts_by_park_2023.csv"
)

zero_output <- file.path(
  interim_dir,
  "mapbox_parks_without_cells_2023.csv"
)

overlap_output <- file.path(
  interim_dir,
  "mapbox_cells_multiple_parks_2023.csv"
)

write_csv(
  cell_park_lookup,
  lookup_output
)

write_csv(
  cells_per_park,
  counts_output
)

write_csv(
  parks_without_cells,
  zero_output
)

write_csv(
  cells_multiple_parks,
  overlap_output
)

# ------------------------------------------------------------
# Also save matched points as GeoPackage for visual QA
# ------------------------------------------------------------

matched_points_output <- file.path(
  interim_dir,
  "mapbox_matched_cell_centroids_2023.gpkg"
)

if (file.exists(matched_points_output)) {
  file.remove(
    matched_points_output
  )
}

st_write(
  matched_points,
  dsn = matched_points_output,
  layer = "matched_mapbox_centroids",
  quiet = TRUE
)

# ------------------------------------------------------------
# Final output summary
# ------------------------------------------------------------

cat("\n============================================\n")
cat("MAPBOX CELL MATCHING COMPLETE\n")
cat("============================================\n")

cat(
  "\nLookup table:\n",
  lookup_output,
  "\n",
  sep = ""
)

cat(
  "\nCell counts by park:\n",
  counts_output,
  "\n",
  sep = ""
)

cat(
  "\nParks without Mapbox cells:\n",
  zero_output,
  "\n",
  sep = ""
)

cat(
  "\nCells assigned to multiple parks:\n",
  overlap_output,
  "\n",
  sep = ""
)

cat(
  "\nMatched centroid spatial layer:\n",
  matched_points_output,
  "\n",
  sep = ""
)

cat("\nDone.\n")
