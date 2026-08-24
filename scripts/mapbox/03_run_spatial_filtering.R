# Paper 4: spatially filtered mixed-effects models (RE-ESF)
#
# The ordinary random-intercept models retain spatial structure in their
# waterfront effects. This script fits one proposal-aligned RE-ESF model for
# each accessibility outcome and verifies residual Moran's I afterward.

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
  library(spmoran)
  library(spdep)
})

required_packages <- c("readr", "dplyr", "tidyr", "spmoran", "spdep")
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

input_path <- file.path(
  project_root, "data/processed/mapbox/mapbox_model_dataset.csv"
)
artifact_dir <- file.path(project_root, "artifacts/mapbox/spatial_filtering")
table_dir <- file.path(project_root, "outputs/mapbox/tables")
dir.create(artifact_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)
if (!file.exists(input_path)) stop("Run 01_build_analysis_dataset.R first.")

z_scale <- function(x) {
  if (anyNA(x) || sd(x) == 0) stop("Cannot standardize incomplete or constant data.")
  as.numeric(scale(x))
}

message("Preparing the primary 10-minute spatial model sample...")
raw <- read_csv(input_path, show_col_types = FALSE) %>%
  filter(main_model_eligible) %>%
  mutate(
    park_num = as.character(as.integer(park_num)),
    day_type = relevel(factor(day_type), ref = "weekday"),
    time_of_day = relevel(factor(time_of_day), ref = "morning"),
    season = relevel(factor(season), ref = "winter"),
    site_type = relevel(factor(site_type), ref = "riverfront")
  )

site_level <- raw %>%
  distinct(
    park_num, physical_access_score, visible_water_ratio,
    shoreline_length_to_perimeter_ratio, multidimensional_access_score,
    log_site_area, log_population_density_10min
  ) %>%
  mutate(
    z_physical_access = z_scale(physical_access_score),
    z_visual_access = z_scale(visible_water_ratio),
    z_haptic_access = z_scale(shoreline_length_to_perimeter_ratio),
    z_multidimensional_access = z_scale(multidimensional_access_score),
    z_log_site_area = z_scale(log_site_area),
    z_log_population_density_10min = z_scale(log_population_density_10min)
  )

analysis <- raw %>%
  left_join(
    site_level %>%
      select(
        park_num, starts_with("z_")
      ),
    by = "park_num", relationship = "many-to-one"
  )

if (nrow(analysis) != 30946 || n_distinct(analysis$park_num) != 98) {
  stop("Expected 30,946 observations from 98 primary-sample waterfronts.")
}

outcomes <- c(
  physical = "z_physical_access",
  visual = "z_visual_access",
  haptic = "z_haptic_access",
  multidimensional = "z_multidimensional_access"
)

required_common <- c(
  "park_num", "log_activity_index", "day_type", "time_of_day", "season",
  "site_type", "z_log_site_area", "z_log_population_density_10min",
  "site_point_x", "site_point_y"
)
if (anyNA(analysis[c(required_common, unname(outcomes))])) {
  stop("Unexpected missing values in the spatial model data.")
}

# Generate the site-level Moran basis only once; all four models use the same
# observations, sites, and spatial structure.
coords_repeated <- as.matrix(analysis[c("site_point_x", "site_point_y")])
site_id <- analysis$park_num
message("Generating the shared waterfront-level Moran eigenvectors...")
meig_site <- spmoran::meigen_f(
  coords = coords_repeated,
  enum = 200,
  s_id = site_id
)

coefficient_rows <- list()
diagnostic_rows <- list()
residual_rows <- list()
model_summaries <- character()

for (model_name in names(outcomes)) {
  access_var <- outcomes[[model_name]]
  formula_text <- paste0(
    "~ ", access_var,
    " + day_type + time_of_day + season + site_type",
    " + z_log_site_area + z_log_population_density_10min"
  )
  x <- model.matrix(as.formula(formula_text), data = analysis)
  x <- x[, colnames(x) != "(Intercept)", drop = FALSE]

  message("Fitting RE-ESF model: ", model_name)
  model <- spmoran::resf(
    y = analysis$log_activity_index,
    x = x,
    meig = meig_site,
    xgroup = site_id,
    method = "reml"
  )

  coefficient_table <- as.data.frame(model$b)
  coefficient_table$term <- rownames(coefficient_table)
  rownames(coefficient_table) <- NULL
  coefficient_table <- as_tibble(coefficient_table) %>%
    select(term, everything()) %>%
    mutate(model = model_name, access_term = access_var, .before = 1)
  coefficient_rows[[model_name]] <- coefficient_table

  model_data_with_residual <- analysis %>%
    transmute(
      park_num, site_point_x, site_point_y,
      residual = as.numeric(model$resid)
    )
  park_residuals <- model_data_with_residual %>%
    group_by(park_num) %>%
    summarise(
      mean_residual = mean(residual),
      n_temporal_observations = n(),
      site_point_x = first(site_point_x),
      site_point_y = first(site_point_y),
      .groups = "drop"
    ) %>%
    arrange(as.integer(park_num))

  coords <- as.matrix(park_residuals[c("site_point_x", "site_point_y")])
  nb <- suppressWarnings(
    knn2nb(knearneigh(coords, k = 7), row.names = park_residuals$park_num)
  )
  if (n.comp.nb(nb)$nc != 1) stop("RE-ESF residual kNN graph is disconnected.")
  listw <- nb2listw(nb, style = "W", zero.policy = TRUE)
  moran <- moran.test(
    park_residuals$mean_residual, listw,
    alternative = "two.sided", zero.policy = TRUE
  )

  diagnostic_rows[[model_name]] <- tibble(
    model = model_name,
    N_waterfronts = nrow(park_residuals),
    N_observations = nrow(analysis),
    k_neighbors = 7L,
    residual_Moran_I = unname(moran$estimate[[1]]),
    expected_I = unname(moran$estimate[[2]]),
    statistic = unname(moran$statistic),
    residual_Moran_p = moran$p.value
  )
  residual_rows[[model_name]] <- park_residuals %>%
    mutate(model = model_name, .before = 1)
  model_summaries <- c(
    model_summaries,
    paste0("===== ", toupper(model_name), " ====="),
    capture.output(print(model)), ""
  )
}

coefficients <- bind_rows(coefficient_rows)
diagnostics <- bind_rows(diagnostic_rows)
park_residuals <- bind_rows(residual_rows)

required_coefficient_fields <- c("Estimate", "SE", "t_value", "p_value")
missing_coefficient_fields <- setdiff(required_coefficient_fields, names(coefficients))
if (length(missing_coefficient_fields) > 0) {
  stop(
    "Unexpected spmoran coefficient fields: ",
    paste(names(coefficients), collapse = ", ")
  )
}

accessibility_effects <- coefficients %>%
  filter(term == access_term) %>%
  transmute(
    model, term,
    estimate = Estimate,
    std_error = SE,
    statistic = t_value,
    p_value,
    conf_low = estimate - 1.96 * std_error,
    conf_high = estimate + 1.96 * std_error,
    percent_change = 100 * (exp(estimate) - 1),
    percent_change_low = 100 * (exp(conf_low) - 1),
    percent_change_high = 100 * (exp(conf_high) - 1)
  ) %>%
  mutate(BH_q = p.adjust(p_value, method = "BH")) %>%
  left_join(diagnostics, by = "model")

write_csv(
  accessibility_effects,
  file.path(table_dir, "table4_mapbox_spatially_filtered_effects.csv")
)
write_csv(
  diagnostics,
  file.path(table_dir, "table5_mapbox_spatial_diagnostics.csv")
)
write_csv(coefficients, file.path(artifact_dir, "mapbox_reesf_all_coefficients.csv"))
write_csv(park_residuals, file.path(artifact_dir, "mapbox_reesf_park_residuals.csv"))
writeLines(
  model_summaries,
  file.path(artifact_dir, "mapbox_reesf_model_summaries.txt"),
  useBytes = TRUE
)

message("Spatial filtering complete.")
print(accessibility_effects)
