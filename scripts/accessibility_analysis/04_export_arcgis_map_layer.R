# Export a clean, local ArcGIS map table and GeoPackage for one catchment.
# Usage: Rscript scripts/accessibility_analysis/04_export_arcgis_map_layer.R --main-catchment=10

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(sf)
})

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) != 1) stop("Could not determine this script's location.")
script_path <- normalizePath(sub("^--file=", "", script_arg), winslash = "/")
project_root <- normalizePath(file.path(dirname(script_path), "../.."), winslash = "/")

get_arg <- function(name, default) {
  prefix <- paste0("--", name, "=")
  hit <- grep(paste0("^", prefix), commandArgs(trailingOnly = TRUE), value = TRUE)
  if (length(hit) == 0) return(default)
  sub(paste0("^", prefix), "", hit[[1]])
}

main_catchment <- as.integer(get_arg("main-catchment", "10"))
if (!main_catchment %in% c(5L, 10L, 20L, 30L)) {
  stop("--main-catchment must be one of 5, 10, 20, or 30.")
}

analysis_path <- file.path(
  project_root,
  "data/processed/accessibility_analysis/accessibility_analysis_by_catchment.csv"
)
park_gdb <- file.path(project_root, "data/raw/Park_Extraction_Project.gdb")
output_dir <- file.path(project_root, "data/processed/accessibility_analysis")
output_csv <- file.path(
  output_dir,
  paste0("accessibility_scores_", main_catchment, "min_arcgis.csv")
)
output_gpkg <- file.path(
  output_dir,
  paste0("accessibility_scores_", main_catchment, "min_arcgis.gpkg")
)

if (!file.exists(analysis_path)) stop("Analysis table not found: ", analysis_path)
if (!dir.exists(park_gdb)) stop("Park geodatabase not found: ", park_gdb)
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

scores <- read_csv(analysis_path, show_col_types = FALSE) %>%
  filter(walktime_min == main_catchment) %>%
  transmute(
    park_num = as.character(park_num),
    site_name,
    municipality,
    site_type,
    walktime_min,
    pedestrian_access_score = access_point_density_scaled,
    transit_access_score = bus_stop_count_scaled,
    physical_access_score,
    physical_access_score_scaled,
    visual_access_score = visual_access_ratio_capped,
    visual_access_scaled,
    haptic_access_score = haptic_access_avery,
    haptic_access_scaled,
    multidimensional_access_score,
    access_point_count,
    bus_stop_count,
    site_area_m2,
    site_point_x,
    site_point_y
  )

if (nrow(scores) != 114L || n_distinct(scores$park_num) != 114L) {
  stop("Expected 114 unique sites; found ", nrow(scores), " rows and ",
       n_distinct(scores$park_num), " site IDs.")
}
if (any(!complete.cases(
  scores[, c(
    "physical_access_score", "visual_access_score",
    "haptic_access_score", "multidimensional_access_score",
    "site_point_x", "site_point_y"
  )]
))) {
  stop("The ArcGIS export contains missing scores or representative coordinates.")
}

write_csv(scores, output_csv)

parks <- st_read(
  park_gdb,
  layer = "allparks_land_buffer",
  quiet = TRUE
) %>%
  mutate(park_num = as.character(park_num)) %>%
  select(park_num)

if (nrow(parks) != 114L || n_distinct(parks$park_num) != 114L) {
  stop("Expected 114 unique land-buffer polygons in allparks_land_buffer.")
}

polygons <- parks %>% left_join(scores, by = "park_num")
if (any(is.na(polygons$multidimensional_access_score))) {
  stop("At least one park polygon did not match the accessibility table.")
}

points <- st_as_sf(
  scores,
  coords = c("site_point_x", "site_point_y"),
  crs = st_crs(parks),
  remove = FALSE
)

st_write(
  polygons,
  output_gpkg,
  layer = paste0("accessibility_scores_", main_catchment, "min_polygons"),
  delete_dsn = TRUE,
  quiet = TRUE
)
st_write(
  points,
  output_gpkg,
  layer = paste0("accessibility_scores_", main_catchment, "min_points"),
  append = TRUE,
  quiet = TRUE
)

message("ArcGIS table: ", output_csv)
message("ArcGIS GeoPackage: ", output_gpkg)
message("Rows/sites: ", nrow(scores))
