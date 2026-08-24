# Paper 4: RE-ESF sensitivity models

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
  library(spmoran)
  library(spdep)
})

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) != 1) stop("Could not determine this script's location.")
script_path <- normalizePath(sub("^--file=", "", script_arg), winslash = "/")
project_root <- normalizePath(file.path(dirname(script_path), "../.."), winslash = "/")

input_path <- file.path(
  project_root, "data/processed/mapbox/mapbox_model_dataset.csv"
)
artifact_dir <- file.path(project_root, "artifacts/mapbox/spatial_sensitivities")
table_dir <- file.path(project_root, "outputs/mapbox/tables")
dir.create(artifact_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)
if (!file.exists(input_path)) stop("Run 01_build_analysis_dataset.R first.")

z_with_reference <- function(x, reference) {
  (x - mean(reference, na.rm = TRUE)) / sd(reference, na.rm = TRUE)
}

raw <- read_csv(input_path, show_col_types = FALSE) %>%
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
    log_site_area, log_population_density_10min,
    log_population_density_20min, main_model_eligible,
    population20_sensitivity_eligible
  )
main_reference <- site_level %>% filter(main_model_eligible)
pop20_reference <- site_level %>% filter(population20_sensitivity_eligible)

analysis <- raw %>%
  mutate(
    z_physical_access = z_with_reference(
      physical_access_score, main_reference$physical_access_score
    ),
    z_visual_access = z_with_reference(
      visible_water_ratio, main_reference$visible_water_ratio
    ),
    z_haptic_access = z_with_reference(
      shoreline_length_to_perimeter_ratio,
      main_reference$shoreline_length_to_perimeter_ratio
    ),
    z_multidimensional_access = z_with_reference(
      multidimensional_access_score,
      main_reference$multidimensional_access_score
    ),
    z_log_site_area = z_with_reference(
      log_site_area, main_reference$log_site_area
    ),
    z_log_population_density_10min = z_with_reference(
      log_population_density_10min,
      main_reference$log_population_density_10min
    ),
    z_log_population_density_20min = z_with_reference(
      log_population_density_20min,
      pop20_reference$log_population_density_20min
    )
  )

outcomes <- c(
  physical = "z_physical_access",
  visual = "z_visual_access",
  haptic = "z_haptic_access",
  multidimensional = "z_multidimensional_access"
)
scenarios <- tibble::tribble(
  ~scenario, ~eligibility, ~population_var, ~outcome_var, ~include_site_type,
  "coverage90", "coverage90_model_eligible", "z_log_population_density_10min", "log_activity_index", TRUE,
  "population20", "population20_sensitivity_eligible", "z_log_population_density_20min", "log_activity_index", TRUE,
  "no_site_type", "main_model_eligible", "z_log_population_density_10min", "log_activity_index", FALSE,
  "raw_outcome", "main_model_eligible", "z_log_population_density_10min", "site_activity_index", TRUE
)

coefficient_rows <- list()
diagnostic_rows <- list()
residual_rows <- list()

for (scenario_index in seq_len(nrow(scenarios))) {
  spec <- scenarios[scenario_index, ]
  scenario_name <- spec$scenario[[1]]
  population_var <- spec$population_var[[1]]
  outcome_var <- spec$outcome_var[[1]]
  include_site_type <- spec$include_site_type[[1]]
  dat <- analysis %>% filter(.data[[spec$eligibility[[1]]]])

  coords_repeated <- as.matrix(dat[c("site_point_x", "site_point_y")])
  site_id <- dat$park_num
  message("Generating Moran basis: ", scenario_name)
  meig <- spmoran::meigen_f(
    coords = coords_repeated, enum = 200, s_id = site_id
  )

  for (model_name in names(outcomes)) {
    access_var <- outcomes[[model_name]]
    fixed_terms <- c(
      access_var, "day_type", "time_of_day", "season",
      if (include_site_type) "site_type" else NULL,
      "z_log_site_area", population_var
    )
    x <- model.matrix(
      as.formula(paste("~", paste(fixed_terms, collapse = " + "))),
      data = dat
    )
    x <- x[, colnames(x) != "(Intercept)", drop = FALSE]

    message("  Fitting ", scenario_name, " / ", model_name)
    model <- spmoran::resf(
      y = dat[[outcome_var]], x = x, meig = meig,
      xgroup = site_id, method = "reml"
    )
    coefficients <- as.data.frame(model$b)
    coefficients$term <- rownames(coefficients)
    rownames(coefficients) <- NULL
    coefficient_rows[[paste(scenario_name, model_name)]] <-
      as_tibble(coefficients) %>%
      select(term, everything()) %>%
      mutate(
        scenario = scenario_name, model = model_name,
        access_term = access_var, .before = 1
      )

    park_residuals <- tibble(
      park_num = dat$park_num,
      residual = as.numeric(model$resid),
      site_point_x = dat$site_point_x,
      site_point_y = dat$site_point_y
    ) %>%
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
    if (n.comp.nb(nb)$nc != 1) stop("Sensitivity residual graph is disconnected.")
    listw <- nb2listw(nb, style = "W", zero.policy = TRUE)
    moran <- moran.test(
      park_residuals$mean_residual, listw,
      alternative = "two.sided", zero.policy = TRUE
    )
    diagnostic_rows[[paste(scenario_name, model_name)]] <- tibble(
      scenario = scenario_name, model = model_name,
      N_waterfronts = nrow(park_residuals), N_observations = nrow(dat),
      k_neighbors = 7L, residual_Moran_I = unname(moran$estimate[[1]]),
      expected_I = unname(moran$estimate[[2]]),
      statistic = unname(moran$statistic), residual_Moran_p = moran$p.value
    )
    residual_rows[[paste(scenario_name, model_name)]] <- park_residuals %>%
      mutate(scenario = scenario_name, model = model_name, .before = 1)
  }
}

all_coefficients <- bind_rows(coefficient_rows)
diagnostics <- bind_rows(diagnostic_rows)
park_residuals <- bind_rows(residual_rows)

effects <- all_coefficients %>%
  filter(term == access_term) %>%
  transmute(
    scenario, model, term, estimate = Estimate, std_error = SE,
    statistic = t_value, p_value,
    conf_low = estimate - 1.96 * std_error,
    conf_high = estimate + 1.96 * std_error,
    percent_change = if_else(
      scenario == "raw_outcome", NA_real_, 100 * (exp(estimate) - 1)
    ),
    percent_change_low = if_else(
      scenario == "raw_outcome", NA_real_, 100 * (exp(conf_low) - 1)
    ),
    percent_change_high = if_else(
      scenario == "raw_outcome", NA_real_, 100 * (exp(conf_high) - 1)
    )
  ) %>%
  group_by(scenario) %>%
  mutate(BH_q = p.adjust(p_value, method = "BH")) %>%
  ungroup() %>%
  left_join(diagnostics, by = c("scenario", "model"))

write_csv(
  effects,
  file.path(table_dir, "table6_mapbox_spatial_sensitivity_effects.csv")
)
write_csv(
  diagnostics,
  file.path(table_dir, "tableS1_mapbox_spatial_sensitivity_diagnostics.csv")
)
write_csv(
  all_coefficients,
  file.path(artifact_dir, "mapbox_spatial_sensitivity_all_coefficients.csv")
)
write_csv(
  park_residuals,
  file.path(artifact_dir, "mapbox_spatial_sensitivity_residuals.csv")
)

message("Spatial sensitivity analyses complete.")
print(effects)
