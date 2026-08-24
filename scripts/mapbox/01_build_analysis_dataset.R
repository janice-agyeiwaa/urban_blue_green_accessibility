# Paper 4: build the canonical Mapbox model dataset
#
# Reuses the completed 2023 Mapbox activity extraction and joins:
# - validated Paper 3 10-minute accessibility scores;
# - site type, area, and representative coordinates;
# - 10-minute population density for the primary specification; and
# - 20-minute population density for a labelled sensitivity analysis.

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(sf)
  library(stringr)
})

required_packages <- c("readr", "dplyr", "sf", "stringr")
missing_packages <- required_packages[
  !vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)
]
if (length(missing_packages) > 0) {
  stop("Install required R packages: ", paste(missing_packages, collapse = ", "))
}

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) != 1) stop("Could not determine this script's location.")
script_path <- normalizePath(sub("^--file=", "", script_arg), winslash = "/")
project_root <- normalizePath(file.path(dirname(script_path), "../.."), winslash = "/")

activity_path <- file.path(
  project_root, "data/processed/mapbox/mapbox_park_hourly_activity_2023.csv"
)
coverage_path <- file.path(
  project_root, "data/interim/mapbox/mapbox_temporal_coverage_summary_2023.csv"
)
access_path <- file.path(
  project_root, "data/processed/paper4_handoff/all_114_sites_accessibility_scores.csv"
)
canonical_access_path <- file.path(
  project_root,
  "data/processed/accessibility_analysis/accessibility_analysis_by_catchment.csv"
)
metadata_path <- file.path(
  project_root, "data/processed/accessibility_analysis/site_metadata_114.csv"
)
census_gdb <- file.path(
  project_root, "data/interim/census/census_enrich_prep.gdb"
)
output_path <- file.path(
  project_root, "data/processed/mapbox/mapbox_model_dataset.csv"
)
artifact_dir <- file.path(project_root, "artifacts/mapbox")
dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
dir.create(artifact_dir, recursive = TRUE, showWarnings = FALSE)

for (path in c(
  activity_path, coverage_path, access_path, canonical_access_path,
  metadata_path, census_gdb
)) {
  if (!file.exists(path)) stop("Required input not found: ", path)
}

read_population_layer <- function(layer, catchment_min, prefix) {
  available_layers <- sf::st_layers(census_gdb)$name
  if (!layer %in% available_layers) {
    stop("Required Census layer not found: ", layer)
  }
  raw <- st_read(census_gdb, layer = layer, quiet = TRUE)
  raw$polygon_area_m2 <- as.numeric(st_area(raw))
  raw <- raw %>%
    mutate(park_num = as.character(as.integer(park_num)))
  required <- c(
    "park_num", "walktime_min", "HasData", "PopulationTotals_EHYPTAPOP",
    "polygon_area_m2"
  )
  missing <- setdiff(required, names(raw))
  if (length(missing) > 0) {
    stop(layer, " is missing: ", paste(missing, collapse = ", "))
  }
  if (nrow(raw) != 114 || n_distinct(raw$park_num) != 114 ||
      !all(raw$walktime_min == catchment_min)) {
    stop(layer, " must contain 114 unique ", catchment_min, "-minute records.")
  }

  raw %>%
    st_drop_geometry() %>%
    transmute(
      park_num,
      !!paste0("population_", prefix) := if_else(
        HasData == 1,
        as.numeric(PopulationTotals_EHYPTAPOP),
        NA_real_
      ),
      !!paste0("population_has_data_", prefix) := HasData == 1,
      !!paste0("catchment_area_km2_", prefix) := polygon_area_m2 / 1e6,
      !!paste0("population_density_km2_", prefix) := if_else(
        HasData == 1,
        as.numeric(PopulationTotals_EHYPTAPOP) / (polygon_area_m2 / 1e6),
        NA_real_
      )
    )
}

message("Reading stable Mapbox and Paper 3 inputs...")
activity <- read_csv(activity_path, show_col_types = FALSE) %>%
  mutate(
    park_num = as.character(as.integer(park_num)),
    start_date = as.Date(start_date),
    end_date = as.Date(end_date),
    month = as.integer(format(start_date, "%m")),
    month_name = factor(
      month.name[month], levels = month.name, ordered = TRUE
    ),
    time_of_day = case_when(
      agg_time_period >= 6 & agg_time_period <= 11 ~ "morning",
      agg_time_period >= 12 & agg_time_period <= 16 ~ "afternoon",
      agg_time_period >= 17 & agg_time_period <= 20 ~ "evening",
      TRUE ~ NA_character_
    ),
    season = case_when(
      month %in% c(12L, 1L, 2L) ~ "winter",
      month %in% 3:5 ~ "spring",
      month %in% 6:8 ~ "summer",
      month %in% 9:11 ~ "fall",
      TRUE ~ NA_character_
    )
  )

if (nrow(activity) != 32472 || n_distinct(activity$park_num) != 103) {
  stop("Expected 32,472 Mapbox observations from 103 waterfronts.")
}
if (anyNA(activity$time_of_day) || anyNA(activity$season)) {
  stop("Mapbox observations contain hours or months outside the analysis rules.")
}
if (any(activity$site_activity_index < 0, na.rm = TRUE)) {
  stop("Mapbox activity index contains negative values.")
}

coverage <- read_csv(coverage_path, show_col_types = FALSE) %>%
  mutate(park_num = as.character(as.integer(park_num))) %>%
  select(
    park_num, mapbox_cell_count, temporal_records,
    missing_temporal_records, coverage_pct, coverage_group
  )
access <- read_csv(access_path, show_col_types = FALSE) %>%
  mutate(park_num = as.character(as.integer(park_num)))
canonical_access <- read_csv(canonical_access_path, show_col_types = FALSE) %>%
  filter(walktime_min == 10) %>%
  transmute(
    park_num = as.character(as.integer(park_num)),
    physical_access_score,
    visible_water_ratio = visual_access_ratio_capped,
    shoreline_length_to_perimeter_ratio = haptic_access_avery,
    multidimensional_access_score
  )
metadata <- read_csv(metadata_path, show_col_types = FALSE) %>%
  mutate(park_num = as.character(as.integer(park_num)))

if (nrow(access) != 114 || n_distinct(access$park_num) != 114 ||
    !all(access$walktime_min == 10)) {
  stop("Paper 4 handoff must contain 114 unique 10-minute records.")
}
handoff_check <- access %>%
  select(
    park_num, physical_access_score, visible_water_ratio,
    shoreline_length_to_perimeter_ratio, multidimensional_access_score
  ) %>%
  inner_join(
    canonical_access,
    by = "park_num", suffix = c("_handoff", "_canonical"),
    relationship = "one-to-one"
  )
if (nrow(handoff_check) != 114) stop("Paper 3 to Paper 4 site IDs do not match.")
for (field in c(
  "physical_access_score", "visible_water_ratio",
  "shoreline_length_to_perimeter_ratio", "multidimensional_access_score"
)) {
  difference <- abs(
    handoff_check[[paste0(field, "_handoff")]] -
      handoff_check[[paste0(field, "_canonical")]]
  )
  if (max(difference) > 1e-12) {
    stop("Paper 4 handoff is stale for: ", field)
  }
}
if (nrow(metadata) != 114 || n_distinct(metadata$park_num) != 114) {
  stop("Site metadata must contain 114 unique records.")
}
if (nrow(coverage) != 103 || n_distinct(coverage$park_num) != 103) {
  stop("Coverage table must contain 103 unique Mapbox sites.")
}

population_10 <- read_population_layer("pop_den_10min", 10L, "10min")
population_20 <- read_population_layer("pop_den_20min", 20L, "20min")

site_table <- access %>%
  left_join(metadata, by = "park_num", relationship = "one-to-one") %>%
  left_join(population_10, by = "park_num", relationship = "one-to-one") %>%
  left_join(population_20, by = "park_num", relationship = "one-to-one")

required_site_fields <- c(
  "site_name", "municipality", "physical_access_score", "visible_water_ratio",
  "shoreline_length_to_perimeter_ratio", "multidimensional_access_score",
  "site_type", "site_area_m2", "site_point_x", "site_point_y"
)
if (anyNA(site_table[required_site_fields])) {
  stop("Unexpected missing accessibility or site-metadata values.")
}

analysis <- activity %>%
  left_join(coverage, by = "park_num", relationship = "many-to-one") %>%
  left_join(site_table, by = "park_num", relationship = "many-to-one") %>%
  mutate(
    site_name = str_squish(site_name),
    municipality = str_squish(municipality),
    log_site_area = log(site_area_m2),
    log_activity_index = log(site_activity_index),
    log_population_density_10min = log1p(population_density_km2_10min),
    log_population_density_20min = log1p(population_density_km2_20min),
    main_model_eligible = population_has_data_10min,
    coverage90_model_eligible = main_model_eligible & coverage_pct >= 90,
    population20_sensitivity_eligible = population_has_data_20min
  ) %>%
  arrange(as.integer(park_num), start_date, agg_day_period, agg_time_period)

if (nrow(analysis) != nrow(activity) ||
    anyNA(analysis[c("site_name", "coverage_pct", "site_type")])) {
  stop("Canonical Mapbox joins were incomplete.")
}

site_qa <- analysis %>%
  distinct(
    park_num, site_name, municipality, coverage_pct,
    population_10min, population_has_data_10min,
    population_density_km2_10min,
    population_20min, population_has_data_20min,
    population_density_km2_20min,
    main_model_eligible, coverage90_model_eligible,
    population20_sensitivity_eligible
  ) %>%
  arrange(as.integer(park_num))

sample_qa <- tibble(
  sample = c(
    "Mapbox activity available",
    "Primary 10-minute population complete case",
    "Primary plus at least 90% temporal coverage",
    "20-minute population-density sensitivity"
  ),
  waterfronts = c(
    n_distinct(analysis$park_num),
    n_distinct(analysis$park_num[analysis$main_model_eligible]),
    n_distinct(analysis$park_num[analysis$coverage90_model_eligible]),
    n_distinct(analysis$park_num[analysis$population20_sensitivity_eligible])
  ),
  observations = c(
    nrow(analysis),
    sum(analysis$main_model_eligible),
    sum(analysis$coverage90_model_eligible),
    sum(analysis$population20_sensitivity_eligible)
  )
)

expected_sites <- c(103L, 98L, 76L, 103L)
if (!identical(sample_qa$waterfronts, expected_sites)) {
  stop(
    "Unexpected Paper 4 samples: ",
    paste(sample_qa$waterfronts, collapse = ", ")
  )
}

write_csv(analysis, output_path)
write_csv(site_qa, file.path(artifact_dir, "mapbox_site_level_dataset_qa.csv"))
write_csv(sample_qa, file.path(artifact_dir, "mapbox_sample_qa.csv"))

message("Canonical Mapbox dataset written: ", output_path)
print(sample_qa)
