# Paper 4: canonical mixed-effects models and non-spatial sensitivities

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
  library(nlme)
  library(spdep)
})

required_packages <- c("readr", "dplyr", "tidyr", "nlme", "spdep")
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
artifact_dir <- file.path(project_root, "artifacts/mapbox/models")
table_dir <- artifact_dir
dir.create(artifact_dir, recursive = TRUE, showWarnings = FALSE)
if (!file.exists(input_path)) stop("Run 01_build_analysis_dataset.R first.")

z_with_reference <- function(x, reference) {
  reference <- reference[is.finite(reference)]
  reference_mean <- mean(reference)
  reference_sd <- sd(reference)
  if (!is.finite(reference_sd) || reference_sd == 0) {
    stop("Cannot standardize a constant or missing variable.")
  }
  (x - reference_mean) / reference_sd
}

skewness <- function(x) {
  x <- x[is.finite(x)]
  mean((x - mean(x))^3) / sd(x)^3
}

message("Reading canonical Mapbox dataset...")
raw <- read_csv(input_path, show_col_types = FALSE) %>%
  mutate(
    park_num = as.character(as.integer(park_num)),
    day_type = relevel(factor(day_type), ref = "weekday"),
    time_of_day = relevel(factor(time_of_day), ref = "morning"),
    season = relevel(factor(season), ref = "winter"),
    site_type = relevel(factor(site_type), ref = "riverfront")
  )

main_sites <- raw %>%
  filter(main_model_eligible) %>%
  distinct(park_num) %>%
  pull(park_num)
pop20_sites <- raw %>%
  filter(population20_sensitivity_eligible) %>%
  distinct(park_num) %>%
  pull(park_num)

site_level <- raw %>%
  distinct(
    park_num, physical_access_score, visible_water_ratio,
    shoreline_length_to_perimeter_ratio, multidimensional_access_score,
    log_site_area, log_population_density_10min,
    log_population_density_20min
  )
main_reference <- site_level %>% filter(park_num %in% main_sites)
pop20_reference <- site_level %>% filter(park_num %in% pop20_sites)

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

scenario_specs <- tibble::tribble(
  ~scenario, ~eligibility, ~population_control, ~model_outcome, ~include_site_type,
  "main_10min", "main_model_eligible", "z_log_population_density_10min", "log_activity_index", TRUE,
  "coverage90", "coverage90_model_eligible", "z_log_population_density_10min", "log_activity_index", TRUE,
  "population20", "population20_sensitivity_eligible", "z_log_population_density_20min", "log_activity_index", TRUE,
  "no_site_type", "main_model_eligible", "z_log_population_density_10min", "log_activity_index", FALSE,
  "raw_outcome", "main_model_eligible", "z_log_population_density_10min", "site_activity_index", TRUE
)

term_labels <- c(
  z_physical_access = "Physical accessibility",
  z_visual_access = "Visual accessibility",
  z_haptic_access = "Haptic accessibility",
  z_multidimensional_access = "Multidimensional accessibility",
  day_typeweekend = "Weekend (vs weekday)",
  time_of_dayafternoon = "Afternoon (vs morning)",
  time_of_dayevening = "Evening (vs morning)",
  seasonspring = "Spring (vs winter)",
  seasonsummer = "Summer (vs winter)",
  seasonfall = "Fall (vs winter)",
  `site_typebeach` = "Beach (vs riverfront)",
  `site_typecoastal waterfront without beach` =
    "Coastal waterfront without beach (vs riverfront)",
  site_typelakefront = "Lakefront (vs riverfront)",
  z_log_site_area = "Log site area",
  z_log_population_density_10min = "Log 10-minute population density",
  z_log_population_density_20min = "Log 20-minute population density"
)

fit_one_model <- function(dat, access_var, population_var, outcome_var,
                          include_site_type) {
  fixed_terms <- c(
    access_var, "day_type", "time_of_day", "season",
    if (include_site_type) "site_type" else NULL,
    "z_log_site_area", population_var
  )
  formula <- as.formula(
    paste(outcome_var, "~", paste(fixed_terms, collapse = " + "))
  )
  model_vars <- c(
    outcome_var, "park_num", fixed_terms, "site_point_x", "site_point_y"
  )
  model_data <- dat %>%
    select(all_of(model_vars)) %>%
    drop_na() %>%
    arrange(park_num)
  model <- nlme::lme(
    fixed = formula,
    random = ~1 | park_num,
    data = model_data,
    method = "REML",
    na.action = na.fail,
    control = lmeControl(
      opt = "optim", maxIter = 250, msMaxIter = 250,
      niterEM = 50, returnObject = TRUE
    )
  )
  list(model = model, data = model_data, formula = formula)
}

extract_coefficients <- function(model) {
  table <- summary(model)$tTable
  tibble(
    term = rownames(table),
    estimate = unname(table[, "Value"]),
    std_error = unname(table[, "Std.Error"]),
    df = unname(table[, "DF"]),
    statistic = unname(table[, "t-value"]),
    p_value = unname(table[, "p-value"]),
    conf_low = estimate - 1.96 * std_error,
    conf_high = estimate + 1.96 * std_error,
    term_label = coalesce(unname(term_labels[term]), term)
  )
}

extract_diagnostics <- function(model, model_data, outcome_var) {
  variance <- as.numeric(VarCorr(model)[, "Variance"])
  random_variance <- variance[[1]]
  residual_variance <- variance[[2]]
  normalized_residuals <- residuals(model, type = "normalized")
  tibble(
    N_observations = nrow(model_data),
    N_waterfronts = n_distinct(model_data$park_num),
    outcome = outcome_var,
    AIC = AIC(model),
    BIC = BIC(model),
    log_likelihood = as.numeric(logLik(model)),
    random_intercept_variance = random_variance,
    residual_variance = residual_variance,
    ICC = random_variance / (random_variance + residual_variance),
    normalized_residual_skewness = skewness(normalized_residuals)
  )
}

residual_moran <- function(model, model_data, k = 7L) {
  random_effects <- nlme::ranef(model)
  site_residuals <- tibble(
    park_num = rownames(random_effects),
    site_random_intercept = as.numeric(random_effects[[1]])
  ) %>%
    left_join(
      model_data %>%
        distinct(park_num, site_point_x, site_point_y),
      by = "park_num", relationship = "one-to-one"
    )
  coords <- as.matrix(site_residuals[c("site_point_x", "site_point_y")])
  nb <- suppressWarnings(
    knn2nb(knearneigh(coords, k = k), row.names = site_residuals$park_num)
  )
  if (n.comp.nb(nb)$nc != 1) stop("Paper 4 residual kNN graph is disconnected.")
  listw <- nb2listw(nb, style = "W", zero.policy = TRUE)
  test <- moran.test(
    site_residuals$site_random_intercept, listw,
    alternative = "two.sided", zero.policy = TRUE
  )
  list(
    summary = tibble(
      k_neighbors = k,
      Moran_I = unname(test$estimate[[1]]),
      expected_I = unname(test$estimate[[2]]),
      statistic = unname(test$statistic),
      p_value = test$p.value
    ),
    residuals = site_residuals
  )
}

coefficient_rows <- list()
diagnostic_rows <- list()
moran_rows <- list()
site_residual_rows <- list()
models <- list()

message("Fitting Paper 4 mixed-effects models...")
for (scenario_index in seq_len(nrow(scenario_specs))) {
  spec <- scenario_specs[scenario_index, ]
  scenario_data <- analysis %>% filter(.data[[spec$eligibility]])
  for (model_name in names(outcomes)) {
    fit <- fit_one_model(
      scenario_data, outcomes[[model_name]], spec$population_control,
      spec$model_outcome, spec$include_site_type
    )
    key <- paste(spec$scenario, model_name, sep = "_")
    models[[key]] <- fit$model
    coefficient_rows[[key]] <- extract_coefficients(fit$model) %>%
      mutate(
        scenario = spec$scenario, model = model_name,
        access_term = outcomes[[model_name]], .before = 1
      )
    diagnostic_rows[[key]] <- extract_diagnostics(
      fit$model, fit$data, spec$model_outcome
    ) %>%
      mutate(
        scenario = spec$scenario, model = model_name,
        include_site_type = spec$include_site_type,
        population_control = spec$population_control, .before = 1
      )
    moran <- residual_moran(fit$model, fit$data, k = 7L)
    moran_rows[[key]] <- moran$summary %>%
      mutate(scenario = spec$scenario, model = model_name, .before = 1)
    site_residual_rows[[key]] <- moran$residuals %>%
      mutate(scenario = spec$scenario, model = model_name, .before = 1)
    message(
      "  ", spec$scenario, " / ", model_name,
      ": ", nrow(fit$data), " observations, ",
      n_distinct(fit$data$park_num), " waterfronts"
    )
  }
}

coefficients <- bind_rows(coefficient_rows)
diagnostics <- bind_rows(diagnostic_rows)
morans <- bind_rows(moran_rows)
site_residuals <- bind_rows(site_residual_rows)

accessibility_effects <- coefficients %>%
  filter(term == access_term) %>%
  mutate(
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
  left_join(
    diagnostics %>%
      select(scenario, model, N_observations, N_waterfronts, ICC),
    by = c("scenario", "model")
  ) %>%
  left_join(
    morans %>% select(scenario, model, Moran_I, p_value) %>%
      rename(residual_Moran_p = p_value),
    by = c("scenario", "model")
  )

write_csv(
  accessibility_effects,
  file.path(table_dir, "table1_mapbox_accessibility_effects.csv")
)
write_csv(
  diagnostics,
  file.path(table_dir, "table2_mapbox_model_diagnostics.csv")
)
write_csv(
  morans,
  file.path(table_dir, "table3_mapbox_residual_spatial_tests.csv")
)
write_csv(coefficients, file.path(artifact_dir, "mapbox_all_coefficients.csv"))
write_csv(site_residuals, file.path(artifact_dir, "mapbox_site_random_effects.csv"))
saveRDS(models, file.path(artifact_dir, "mapbox_mixed_models.rds"))

main_summary <- accessibility_effects %>%
  filter(scenario == "main_10min") %>%
  select(
    model, N_waterfronts, N_observations, estimate, std_error,
    conf_low, conf_high, p_value, BH_q,
    percent_change, percent_change_low, percent_change_high,
    ICC, Moran_I, residual_Moran_p
  )
write_csv(
  main_summary,
  file.path(table_dir, "table1b_mapbox_main_model_summary.csv")
)

message("Mixed-effects modelling complete.")
print(main_summary)
