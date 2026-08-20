# Paper 3: reproducible accessibility regressions
#
# Usage from any working directory:
#   Rscript scripts/accessibility_analysis/01_run_accessibility_models.R
#   Rscript scripts/accessibility_analysis/01_run_accessibility_models.R --main-catchment=20 --k=6
#
# The script rebuilds all access scores, applies one Census-quality rule at
# every catchment, selects the baseline model family using residual Moran's I,
# holds that family fixed when site controls are added, and exports the main
# 10-minute results plus 5/10/20/30-minute sensitivity results.

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(stringr)
  library(spdep)
  library(spatialreg)
  library(sandwich)
})

required_packages <- c(
  "readr", "dplyr", "stringr", "spdep", "spatialreg", "sandwich"
)
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

get_arg <- function(name, default) {
  prefix <- paste0("--", name, "=")
  hit <- grep(paste0("^", prefix), commandArgs(trailingOnly = TRUE), value = TRUE)
  if (length(hit) == 0) return(default)
  sub(paste0("^", prefix), "", hit[[1]])
}

main_catchment <- as.integer(get_arg("main-catchment", "10"))
k_neighbors <- as.integer(get_arg("k", "6"))
if (!main_catchment %in% c(5L, 10L, 20L, 30L)) {
  stop("--main-catchment must be one of 5, 10, 20, or 30.")
}
if (is.na(k_neighbors) || k_neighbors < 1) stop("--k must be a positive integer.")

access_input_path <- file.path(
  project_root, "data/processed/accessibility_analysis/accessibility_site_metrics_114.csv"
)
census_input_path <- file.path(
  project_root, "data/processed/census/ubs_census_by_walktime.csv"
)
site_metadata_path <- file.path(
  project_root, "data/processed/accessibility_analysis/site_metadata_114.csv"
)
processed_dir <- file.path(project_root, "data/processed/accessibility_analysis")
output_dir <- file.path(project_root, "outputs/accessibility_analysis")
table_dir <- file.path(output_dir, "tables")
artifact_dir <- file.path(project_root, "artifacts/accessibility_analysis")
artifact_table_dir <- file.path(artifact_dir, "tables")
diagnostic_dir <- file.path(artifact_dir, "diagnostics")
dir.create(processed_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(artifact_table_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(diagnostic_dir, recursive = TRUE, showWarnings = FALSE)

for (path in c(access_input_path, census_input_path, site_metadata_path)) {
  if (!file.exists(path)) stop("Required input not found: ", path)
}

minmax_scale <- function(x) {
  limits <- range(x, na.rm = TRUE)
  if (!all(is.finite(limits))) return(rep(NA_real_, length(x)))
  if (diff(limits) == 0) return(rep(0, length(x)))
  (x - limits[[1]]) / diff(limits)
}

z_scale <- function(x) {
  if (all(is.na(x)) || sd(x, na.rm = TRUE) == 0) return(rep(NA_real_, length(x)))
  as.numeric(scale(x))
}

message("Reading and validating Paper 3 inputs...")
access_data <- read_csv(access_input_path, show_col_types = FALSE) %>%
  mutate(
    park_num = as.integer(park_num),
    visual_access_ratio_capped = pmin(visual_access_ratio, 1)
  )
census_data <- read_csv(census_input_path, show_col_types = FALSE) %>%
  transmute(
    park_num = as.integer(park_num),
    walktime_min, distance_m, HasData,
    household_median_income = `household-median-income`,
    shelter_expenditures = `shelter-expenditures`,
    shelter_expenditures_principal = `shelter-expenditures-principal`,
    shelter_total_expenditures_rent = `shelter-total-expenditures-rent`,
    pct_low_income = `pct-low-income`,
    pct_no_college = `pct-no-college`,
    pct_bachelors_and_above = `pct-bachelors-and-above`,
    pct_visible_minority = `pct-visible-minority`,
    pct_indigenous_identity = `pct-indigenous-identity`
  )

raw_data <- census_data %>%
  left_join(
    access_data %>%
      select(
        park_num, site_name, municipality,
        starts_with("bus_stops_"), access_point_count,
        visual_access_viewshed_m2, haptic_access_avery,
        park_boundary_length_m, park_boundary_length_km,
        access_points_per_km_boundary, total_water_area_within_1km_m2,
        visual_access_ratio, visual_access_ratio_capped
      ),
    by = "park_num"
  ) %>%
  mutate(
    bus_stop_count = case_when(
      walktime_min == 5 ~ bus_stops_5min,
      walktime_min == 10 ~ bus_stops_10min,
      walktime_min == 20 ~ bus_stops_20min,
      walktime_min == 30 ~ bus_stops_30min,
      TRUE ~ NA_real_
    ),
    across(
      c(
        household_median_income, shelter_expenditures,
        shelter_expenditures_principal, shelter_total_expenditures_rent,
        pct_low_income, pct_no_college, pct_bachelors_and_above,
        pct_visible_minority, pct_indigenous_identity
      ),
      ~ if_else(HasData == 0, NA_real_, .x)
    )
  ) %>%
  select(-starts_with("bus_stops_")) %>%
  arrange(park_num, walktime_min)

required_columns <- c(
  "park_num", "site_name", "municipality", "walktime_min", "HasData",
  "access_points_per_km_boundary", "bus_stop_count",
  "visual_access_ratio_capped", "haptic_access_avery",
  "household_median_income", "shelter_expenditures_principal",
  "pct_low_income", "pct_no_college", "pct_bachelors_and_above",
  "pct_visible_minority", "pct_indigenous_identity"
)
missing_columns <- setdiff(required_columns, names(raw_data))
if (length(missing_columns) > 0) {
  stop("Regression input is missing: ", paste(missing_columns, collapse = ", "))
}
if (anyDuplicated(raw_data[c("park_num", "walktime_min")])) {
  stop("Regression input has duplicate park_num/walktime_min rows.")
}

site_metadata <- read_csv(site_metadata_path, show_col_types = FALSE) %>%
  mutate(park_num = as.integer(park_num))
if (nrow(site_metadata) != 114 || n_distinct(site_metadata$park_num) != 114 ||
    anyNA(site_metadata)) {
  stop("site_metadata_114.csv must contain 114 unique, complete sites.")
}

predictors <- c(
  "shelter_expenditures_principal", "pct_low_income",
  "pct_bachelors_and_above", "pct_visible_minority",
  "pct_indigenous_identity"
)

analysis_data <- raw_data %>%
  group_by(walktime_min) %>%
  mutate(
    access_point_density_scaled = minmax_scale(access_points_per_km_boundary),
    bus_stop_count_scaled = minmax_scale(bus_stop_count),
    physical_access_score = rowMeans(
      cbind(access_point_density_scaled, bus_stop_count_scaled), na.rm = TRUE
    ),
    physical_access_score_scaled = minmax_scale(physical_access_score),
    visual_access_scaled = minmax_scale(visual_access_ratio_capped),
    haptic_access_scaled = minmax_scale(haptic_access_avery),
    multidimensional_access_score = rowMeans(
      cbind(physical_access_score_scaled, visual_access_scaled, haptic_access_scaled),
      na.rm = TRUE
    )
  ) %>%
  ungroup() %>%
  mutate(
    flag_household_income_zero =
      HasData == 1 & !is.na(household_median_income) & household_median_income == 0,
    flag_visible_and_indigenous_both_very_high =
      HasData == 1 & !is.na(pct_visible_minority) & !is.na(pct_indigenous_identity) &
      pct_visible_minority >= 95 & pct_indigenous_identity >= 95,
    flag_education_extreme =
      HasData == 1 & !is.na(pct_bachelors_and_above) & !is.na(pct_no_college) &
      pct_bachelors_and_above == 0 & pct_no_college >= 95,
    flag_low_income_zero_with_other_extremes =
      HasData == 1 & !is.na(pct_low_income) & pct_low_income == 0 &
      (flag_household_income_zero |
         (!is.na(pct_visible_minority) & pct_visible_minority >= 95) |
         (!is.na(pct_indigenous_identity) & pct_indigenous_identity >= 95) |
         (!is.na(pct_bachelors_and_above) & pct_bachelors_and_above == 0)),
    critical_census_flag =
      coalesce(flag_household_income_zero, FALSE) |
      coalesce(flag_visible_and_indigenous_both_very_high, FALSE) |
      coalesce(flag_education_extreme, FALSE) |
      coalesce(flag_low_income_zero_with_other_extremes, FALSE),
    predictors_complete = if_all(all_of(predictors), ~ !is.na(.x)),
    regression_eligible = HasData == 1 & predictors_complete & !critical_census_flag,
    census_exclusion_reason = case_when(
      HasData != 1 | is.na(HasData) ~ "No Census estimate",
      critical_census_flag ~ "Critical Census-quality flag",
      !predictors_complete ~ "Incomplete predictor values",
      TRUE ~ NA_character_
    )
  ) %>%
  left_join(site_metadata, by = "park_num")

if (nrow(analysis_data) != 456 || anyNA(analysis_data$site_type)) {
  stop("Expected 456 complete site/catchment rows after joining metadata.")
}

write_csv(
  analysis_data,
  file.path(processed_dir, "accessibility_analysis_by_catchment.csv")
)
write_csv(
  analysis_data %>%
    filter(!regression_eligible) %>%
    select(
      park_num, site_name, municipality, walktime_min, HasData,
      household_median_income, critical_census_flag, census_exclusion_reason
    ),
  file.path(artifact_table_dir, "census_exclusions_by_catchment.csv")
)

sample_sizes <- analysis_data %>%
  group_by(walktime_min) %>%
  summarise(
    total_sites = n(),
    HasData_equals_1 = sum(HasData == 1, na.rm = TRUE),
    critical_flags = sum(critical_census_flag, na.rm = TRUE),
    final_regression_N = sum(regression_eligible, na.rm = TRUE),
    .groups = "drop"
  )
write_csv(
  sample_sizes,
  file.path(table_dir, "table1_sample_sizes_by_catchment.csv")
)

outcomes <- c(
  pedestrian = "access_point_density_scaled",
  transit = "bus_stop_count_scaled",
  physical = "physical_access_score",
  visual = "visual_access_ratio_capped",
  haptic = "haptic_access_avery",
  multidimensional = "multidimensional_access_score"
)
report_outcomes <- names(outcomes)

term_labels <- c(
  z_shelter = "Principal accommodation expenditure",
  z_low_income = "Low-income residents (%)",
  z_bachelors = "Bachelor's degree or higher (%)",
  z_visible_minority = "Visible-minority residents (%)",
  z_indigenous = "Indigenous identity residents (%)",
  z_log_site_area = "Log land-buffer area",
  `site_typecoastal waterfront without beach` =
    "Coastal waterfront without beach (vs beach)",
  site_typelakefront = "Lakefront (vs beach)",
  site_typeriverfront = "Riverfront (vs beach)"
)

prepare_model_data <- function(catchment, outcome_var) {
  dat <- analysis_data %>%
    filter(walktime_min == catchment, regression_eligible) %>%
    transmute(
      park_num, site_name, municipality,
      site_point_x, site_point_y,
      site_type = relevel(factor(site_type), ref = "beach"),
      z_log_site_area = z_scale(log_site_area),
      z_y = z_scale(.data[[outcome_var]]),
      z_shelter = z_scale(shelter_expenditures_principal),
      z_low_income = z_scale(pct_low_income),
      z_bachelors = z_scale(pct_bachelors_and_above),
      z_visible_minority = z_scale(pct_visible_minority),
      z_indigenous = z_scale(pct_indigenous_identity)
    )
  if (anyNA(dat)) stop("Unexpected missing values in model data.")
  dat
}

build_weights <- function(dat) {
  if (analysis_k >= nrow(dat)) stop("k must be smaller than the model sample.")
  coords <- as.matrix(dat[c("site_point_x", "site_point_y")])
  nb <- suppressWarnings(
    knn2nb(knearneigh(coords, k = analysis_k), row.names = dat$park_num)
  )
  if (n.comp.nb(nb)$nc != 1) stop("Internal error: analysis kNN graph is disconnected.")
  listw <- nb2listw(nb, style = "W", zero.policy = TRUE)
  attr(listw, "accessibility_k") <- analysis_k
  listw
}

minimum_connected_k <- function(dat, starting_k) {
  coords <- as.matrix(dat[c("site_point_x", "site_point_y")])
  for (candidate_k in seq.int(starting_k, nrow(dat) - 1L)) {
    nb <- suppressWarnings(
      knn2nb(knearneigh(coords, k = candidate_k), row.names = dat$park_num)
    )
    if (n.comp.nb(nb)$nc == 1) return(candidate_k)
  }
  stop("Could not create a connected kNN graph.")
}

baseline_formula <- z_y ~ z_shelter + z_low_income + z_bachelors +
  z_visible_minority + z_indigenous
controlled_formula <- update(
  baseline_formula, . ~ . + site_type + z_log_site_area
)

fit_model <- function(family, formula, dat, listw) {
  tryCatch(
    switch(
      family,
      OLS = lm(formula, data = dat),
      SAR_lag = lagsarlm(
        formula, data = dat, listw = listw, method = "eigen", zero.policy = TRUE
      ),
      SAR_error = errorsarlm(
        formula, data = dat, listw = listw, method = "eigen", zero.policy = TRUE
      ),
      stop("Unknown model family: ", family)
    ),
    error = function(e) structure(list(message = conditionMessage(e)), class = "model_error")
  )
}

residual_moran <- function(model, listw) {
  result <- if (inherits(model, "lm")) {
    lm.morantest(model, listw, zero.policy = TRUE, alternative = "two.sided")
  } else {
    moran.test(
      residuals(model), listw, zero.policy = TRUE, alternative = "two.sided"
    )
  }
  c(I = unname(result$estimate[[1]]), p = result$p.value)
}

model_metrics <- function(model, family, listw, n) {
  k_used <- attr(listw, "accessibility_k")
  if (inherits(model, "model_error")) {
    return(tibble(
      family, N = n, k_neighbors = k_used,
      AIC = NA_real_, log_likelihood = NA_real_,
      spatial_parameter = NA_character_, spatial_estimate = NA_real_,
      spatial_p = NA_real_, residual_Moran_I = NA_real_,
      residual_Moran_p = NA_real_, fit_error = model$message
    ))
  }
  moran <- residual_moran(model, listw)
  spatial_parameter <- NA_character_
  spatial_estimate <- NA_real_
  spatial_p <- NA_real_
  if (family == "SAR_lag") {
    spatial_parameter <- "rho"
    spatial_estimate <- unname(model$rho)
    spatial_p <- 2 * pnorm(
      abs(spatial_estimate / unname(model$rho.se)), lower.tail = FALSE
    )
  } else if (family == "SAR_error") {
    spatial_parameter <- "lambda"
    spatial_estimate <- unname(model$lambda)
    spatial_p <- 2 * pnorm(
      abs(spatial_estimate / unname(model$lambda.se)), lower.tail = FALSE
    )
  }
  tibble(
    family, N = n, k_neighbors = k_used,
    AIC = AIC(model), log_likelihood = as.numeric(logLik(model)),
    spatial_parameter, spatial_estimate, spatial_p,
    residual_Moran_I = unname(moran[["I"]]),
    residual_Moran_p = unname(moran[["p"]]),
    fit_error = NA_character_
  )
}

choose_family <- function(metrics) {
  ols <- metrics %>% filter(family == "OLS")
  if (nrow(ols) == 1 && is.finite(ols$residual_Moran_p) &&
      ols$residual_Moran_p >= 0.05) {
    return(c(family = "OLS", reason = "OLS residual Moran p >= 0.05"))
  }
  spatial <- metrics %>%
    filter(family != "OLS", is.na(fit_error), is.finite(AIC))
  cleared <- spatial %>% filter(residual_Moran_p >= 0.05)
  pool <- if (nrow(cleared) > 0) cleared else spatial
  if (nrow(pool) == 0) stop("No spatial candidate model converged.")
  choice <- pool %>% arrange(AIC) %>% slice(1)
  reason <- if (nrow(cleared) > 0) {
    "Lowest-AIC spatial model with residual Moran p >= 0.05"
  } else {
    "Lowest-AIC converged spatial model; residual autocorrelation remains"
  }
  c(family = choice$family[[1]], reason = reason)
}

extract_coefficients <- function(model, family) {
  if (inherits(model, "model_error")) return(tibble())
  if (family == "OLS") {
    estimates <- coef(model)
    vcov_hc3 <- sandwich::vcovHC(model, type = "HC3")
    se <- sqrt(diag(vcov_hc3))
    statistic <- estimates / se
    p_value <- 2 * pt(abs(statistic), df = df.residual(model), lower.tail = FALSE)
  } else {
    coef_table <- summary(model)$Coef
    estimates <- coef_table[, 1]
    se <- coef_table[, 2]
    statistic <- coef_table[, 3]
    p_value <- coef_table[, 4]
  }
  tibble(
    term = names(estimates), estimate = unname(estimates),
    std_error = unname(se), statistic = unname(statistic),
    p_value = unname(p_value),
    conf_low = estimate - 1.96 * std_error,
    conf_high = estimate + 1.96 * std_error,
    inference = if_else(family == "OLS", "HC3 robust", "SAR model-based")
  ) %>%
    mutate(term_label = coalesce(unname(term_labels[term]), term))
}

extract_lag_impacts <- function(model, family, listw) {
  if (family != "SAR_lag" || inherits(model, "model_error")) return(tibble())
  impact <- tryCatch(
    spatialreg::impacts(model, listw = listw),
    error = function(e) NULL
  )
  if (is.null(impact)) return(tibble())
  terms <- names(impact$direct)
  if (is.null(terms)) {
    terms <- names(model$coefficients)
    terms <- terms[terms != "(Intercept)"]
  }
  if (length(terms) != length(impact$direct)) {
    terms <- paste0("impact_term_", seq_along(impact$direct))
  }
  result <- tibble(
    term = terms,
    direct = as.numeric(impact$direct),
    indirect = as.numeric(impact$indirect),
    total = as.numeric(impact$total)
  )
  result$term_label <- coalesce(unname(term_labels[result$term]), result$term)
  result
}

catchment_k_requirements <- bind_rows(lapply(
  sort(unique(analysis_data$walktime_min)),
  function(catchment) {
    dat <- prepare_model_data(catchment, outcomes[["physical"]])
    tibble(
      catchment_min = catchment,
      final_regression_N = nrow(dat),
      minimum_connected_k = minimum_connected_k(dat, k_neighbors)
    )
  }
))
analysis_k <- max(catchment_k_requirements$minimum_connected_k)
catchment_k_requirements <- catchment_k_requirements %>%
  mutate(analysis_k_used_for_all_catchments = analysis_k)
write_csv(
  catchment_k_requirements,
  file.path(diagnostic_dir, "spatial_weights_connectivity.csv")
)
if (analysis_k > k_neighbors) {
  message(
    "Requested k=", k_neighbors, " does not connect every sample; using k=",
    analysis_k, " consistently for all catchments."
  )
}

# Descriptive checks help distinguish a raw relationship from a coefficient
# that appears only after multivariable adjustment.
main_raw <- analysis_data %>%
  filter(walktime_min == main_catchment, regression_eligible)
descriptive_outcomes <- c(
  pedestrian = "access_point_density_scaled",
  transit = "bus_stop_count_scaled",
  physical = "physical_access_score",
  visual = "visual_access_ratio_capped",
  haptic = "haptic_access_avery"
)
descriptive_correlations <- bind_rows(lapply(predictors, function(predictor) {
  bind_rows(lapply(names(descriptive_outcomes), function(outcome_name) {
    outcome_var <- descriptive_outcomes[[outcome_name]]
    pearson <- cor.test(main_raw[[predictor]], main_raw[[outcome_var]], method = "pearson")
    spearman <- suppressWarnings(cor.test(
      main_raw[[predictor]], main_raw[[outcome_var]], method = "spearman", exact = FALSE
    ))
    tibble(
      catchment_min = main_catchment, predictor, outcome = outcome_name,
      N = nrow(main_raw), Pearson_r = unname(pearson$estimate),
      Pearson_p = pearson$p.value, Spearman_rho = unname(spearman$estimate),
      Spearman_p = spearman$p.value
    )
  }))
}))
write_csv(
  descriptive_correlations,
  file.path(
    artifact_table_dir,
    paste0(main_catchment, "min_descriptive_correlations.csv")
  )
)

vif_data <- prepare_model_data(main_catchment, outcomes[["physical"]])
design_matrix <- model.matrix(
  delete.response(terms(controlled_formula)), data = vif_data
)[, -1, drop = FALSE]
design_vif <- vapply(seq_len(ncol(design_matrix)), function(i) {
  fit <- lm(design_matrix[, i] ~ design_matrix[, -i, drop = FALSE])
  1 / (1 - summary(fit)$r.squared)
}, numeric(1))
vif_results <- tibble(
  design_column = colnames(design_matrix), VIF = unname(design_vif)
) %>%
  arrange(desc(VIF))
write_csv(
  vif_results,
  file.path(diagnostic_dir, paste0(main_catchment, "min_design_matrix_vif.csv"))
)

candidate_rows <- list()
selection_rows <- list()
coefficient_rows <- list()
model_rows <- list()
impact_rows <- list()
controlled_spatial_check_rows <- list()
controlled_recheck_candidate_rows <- list()
controlled_recheck_coefficient_rows <- list()
selected_models <- list()
row_id <- 0L

message("Fitting baseline candidate models and controlled models...")
for (catchment in sort(unique(analysis_data$walktime_min))) {
  for (outcome_name in names(outcomes)) {
    dat <- prepare_model_data(catchment, outcomes[[outcome_name]])
    listw <- build_weights(dat)
    candidates <- lapply(
      c("OLS", "SAR_lag", "SAR_error"),
      function(family) fit_model(family, baseline_formula, dat, listw)
    )
    names(candidates) <- c("OLS", "SAR_lag", "SAR_error")
    metrics <- bind_rows(lapply(
      names(candidates),
      function(family) model_metrics(candidates[[family]], family, listw, nrow(dat))
    ))
    choice <- choose_family(metrics)
    selected_family <- unname(choice[["family"]])

    row_id <- row_id + 1L
    candidate_rows[[row_id]] <- metrics %>%
      mutate(catchment_min = catchment, outcome = outcome_name, .before = 1)
    selection_rows[[row_id]] <- tibble(
      catchment_min = catchment, outcome = outcome_name,
      selected_family, selection_reason = unname(choice[["reason"]]),
      OLS_residual_Moran_p = metrics$residual_Moran_p[metrics$family == "OLS"]
    )

    baseline_model <- candidates[[selected_family]]
    controlled_initial_model <- fit_model(
      selected_family, controlled_formula, dat, listw
    )
    if (inherits(controlled_initial_model, "model_error")) {
      stop(
        "Controlled model failed for ", catchment, " min / ", outcome_name,
        ": ", controlled_initial_model$message
      )
    }

    controlled_initial_metrics <- model_metrics(
      controlled_initial_model, selected_family, listw, nrow(dat)
    )
    needs_controlled_recheck <-
      is.finite(controlled_initial_metrics$residual_Moran_p) &&
      controlled_initial_metrics$residual_Moran_p < 0.05
    controlled_final_model <- controlled_initial_model
    controlled_final_family <- selected_family
    controlled_final_moran_p <- controlled_initial_metrics$residual_Moran_p
    if (needs_controlled_recheck) {
      controlled_candidates <- lapply(
        c("OLS", "SAR_lag", "SAR_error"),
        function(family) {
          if (family == selected_family) controlled_initial_model else
            fit_model(family, controlled_formula, dat, listw)
        }
      )
      names(controlled_candidates) <- c("OLS", "SAR_lag", "SAR_error")
      controlled_candidate_metrics <- bind_rows(lapply(
        names(controlled_candidates),
        function(family) model_metrics(
          controlled_candidates[[family]], family, listw, nrow(dat)
        )
      ))
      controlled_recheck_candidate_rows[[length(controlled_recheck_candidate_rows) + 1L]] <-
        controlled_candidate_metrics %>%
        mutate(catchment_min = catchment, outcome = outcome_name, .before = 1)
      recheck_choice <- choose_family(controlled_candidate_metrics)
      controlled_final_family <- unname(recheck_choice[["family"]])
      controlled_final_model <- controlled_candidates[[controlled_final_family]]
      controlled_final_moran_p <- controlled_candidate_metrics$residual_Moran_p[
        controlled_candidate_metrics$family == controlled_final_family
      ]
      controlled_recheck_coefficient_rows[[length(controlled_recheck_coefficient_rows) + 1L]] <-
        extract_coefficients(controlled_final_model, controlled_final_family) %>%
        mutate(
          catchment_min = catchment, outcome = outcome_name,
          family = controlled_final_family, N = nrow(dat), .before = 1
        )
    }
    controlled_spatial_check_rows[[length(controlled_spatial_check_rows) + 1L]] <-
      tibble(
        catchment_min = catchment, outcome = outcome_name,
        baseline_selected_family = selected_family,
        controlled_initial_family = selected_family,
        controlled_initial_Moran_p = controlled_initial_metrics$residual_Moran_p,
        controlled_recheck_needed = needs_controlled_recheck,
        controlled_final_family,
        controlled_final_Moran_p = controlled_final_moran_p
      )

    for (specification in c("baseline", "controlled")) {
      model <- if (specification == "baseline") {
        baseline_model
      } else {
        controlled_final_model
      }
      model_family <- if (specification == "baseline") {
        selected_family
      } else {
        controlled_final_family
      }
      coefficient_rows[[length(coefficient_rows) + 1L]] <-
        extract_coefficients(model, model_family) %>%
        mutate(
          catchment_min = catchment, outcome = outcome_name,
          specification, family = model_family, N = nrow(dat), .before = 1
        )
      model_rows[[length(model_rows) + 1L]] <-
        model_metrics(model, model_family, listw, nrow(dat)) %>%
        mutate(
          catchment_min = catchment, outcome = outcome_name,
          specification, .before = 1
        )
      impact_rows[[length(impact_rows) + 1L]] <-
        extract_lag_impacts(model, model_family, listw) %>%
        mutate(
          catchment_min = catchment, outcome = outcome_name,
          specification, family = model_family, .before = 1
        )
    }
    selected_models[[paste(catchment, outcome_name, sep = "_")]] <- list(
      baseline = baseline_model, controlled = controlled_final_model,
      baseline_family = selected_family,
      controlled_family = controlled_final_family,
      data = dat, listw = listw
    )
  }
}

candidate_results <- bind_rows(candidate_rows)
model_selection <- bind_rows(selection_rows)
coefficients <- bind_rows(coefficient_rows)
model_diagnostics <- bind_rows(model_rows)
lag_impacts <- bind_rows(impact_rows)
controlled_spatial_checks <- bind_rows(controlled_spatial_check_rows)
controlled_recheck_candidates <- bind_rows(controlled_recheck_candidate_rows)
controlled_recheck_coefficients <- bind_rows(controlled_recheck_coefficient_rows)

write_csv(candidate_results, file.path(diagnostic_dir, "baseline_candidate_models.csv"))
write_csv(
  model_selection,
  file.path(artifact_table_dir, "model_selection_by_catchment.csv")
)
write_csv(model_diagnostics, file.path(diagnostic_dir, "selected_model_diagnostics.csv"))
write_csv(
  coefficients,
  file.path(artifact_table_dir, "all_catchment_coefficients.csv")
)
write_csv(lag_impacts, file.path(artifact_table_dir, "sar_lag_impacts.csv"))
write_csv(
  controlled_spatial_checks,
  file.path(diagnostic_dir, "controlled_spatial_rechecks.csv")
)
write_csv(
  controlled_recheck_candidates,
  file.path(diagnostic_dir, "controlled_recheck_candidate_models.csv")
)
write_csv(
  controlled_recheck_coefficients,
  file.path(artifact_table_dir, "controlled_spatial_recheck_coefficients.csv")
)

main_coefficients <- coefficients %>% filter(catchment_min == main_catchment)
main_controls <- main_coefficients %>%
  filter(
    outcome %in% report_outcomes,
    specification == "controlled",
    str_starts(term, "site_type") | term == "z_log_site_area"
  )
main_diagnostics <- model_diagnostics %>% filter(catchment_min == main_catchment)

write_csv(
  main_coefficients,
  file.path(
    artifact_table_dir,
    paste0(main_catchment, "min_baseline_controlled_coefficients.csv")
  )
)
write_csv(
  main_controls,
  file.path(
    table_dir,
    paste0("table3_", main_catchment, "min_site_controls.csv")
  )
)
write_csv(
  main_diagnostics,
  file.path(
    table_dir,
    paste0("table7_", main_catchment, "min_model_diagnostics.csv")
  )
)
main_fdr <- main_coefficients %>%
  filter(
    outcome %in% report_outcomes,
    specification == "controlled",
    term %in% c(
      "z_shelter", "z_low_income", "z_bachelors",
      "z_visible_minority", "z_indigenous"
    )
  ) %>%
  mutate(
    main_test_count = n(),
    p_BH_across_main_tests = p.adjust(p_value, method = "BH"),
    survives_BH_0_05 = p_BH_across_main_tests < 0.05
  )
write_csv(
  main_fdr,
  file.path(
    table_dir,
    paste0("table6_", main_catchment, "min_multiple_testing.csv")
  )
)

significance_stars <- function(p) {
  case_when(
    p < 0.001 ~ "***", p < 0.01 ~ "**", p < 0.05 ~ "*", TRUE ~ ""
  )
}

report_half <- main_coefficients %>%
  filter(outcome %in% report_outcomes) %>%
  mutate(
    result = sprintf(
      "%.3f%s (%.3f)", estimate, significance_stars(p_value), std_error
    )
  ) %>%
  select(outcome, specification, family, N, term, term_label, result, p_value)

baseline_report <- report_half %>%
  filter(specification == "baseline") %>%
  select(
    outcome, term, term_label,
    baseline_family = family, baseline_N = N,
    baseline_beta_SE = result, baseline_p = p_value
  )
controlled_report <- report_half %>%
  filter(specification == "controlled") %>%
  select(
    outcome, term, term_label,
    controlled_family = family, controlled_N = N,
    controlled_beta_SE = result, controlled_p = p_value
  )

term_sequence <- c(
  "(Intercept)", "z_shelter", "z_low_income", "z_bachelors",
  "z_visible_minority", "z_indigenous",
  "site_typecoastal waterfront without beach", "site_typelakefront",
  "site_typeriverfront", "z_log_site_area"
)
full_regression_report <- full_join(
  baseline_report, controlled_report,
  by = c("outcome", "term", "term_label")
) %>%
  mutate(
    outcome_order = match(
      outcome, report_outcomes
    ),
    term_order = match(term, term_sequence)
  ) %>%
  arrange(outcome_order, term_order) %>%
  select(-outcome_order, -term_order)

write_csv(
  full_regression_report,
  file.path(
    table_dir,
    paste0("table2_", main_catchment, "min_full_regression.csv")
  )
)

markdown_lines <- c(
  paste0("# Paper 3: ", main_catchment, "-minute baseline and controlled models"),
  "",
  "Cells are standardized coefficient (standard error). OLS standard errors are HC3 robust; SAR standard errors are model-based.",
  "Significance: `* p < .05`, `** p < .01`, `*** p < .001`. Beach is the site-type reference.",
  ""
)
for (outcome_name in report_outcomes) {
  block <- full_regression_report %>% filter(outcome == outcome_name)
  markdown_lines <- c(
    markdown_lines,
    paste0("## ", str_to_title(outcome_name), " access"),
    "",
    paste0(
      "Baseline: ", block$baseline_family[which(!is.na(block$baseline_family))[1]],
      "; controlled: ", block$controlled_family[which(!is.na(block$controlled_family))[1]],
      "; N = ", block$controlled_N[which(!is.na(block$controlled_N))[1]], "."
    ),
    "",
    "| Predictor | Baseline beta (SE) | p | Controlled beta (SE) | p |",
    "|---|---:|---:|---:|---:|"
  )
  for (i in seq_len(nrow(block))) {
    show_value <- function(x) ifelse(is.na(x), "--", x)
    show_p <- function(x) {
      if (is.na(x)) return("--")
      if (x < 0.001) return("<.001")
      sub("^0", "", sprintf("%.3f", x))
    }
    markdown_lines <- c(
      markdown_lines,
      paste0(
        "| ", block$term_label[[i]], " | ",
        show_value(block$baseline_beta_SE[[i]]), " | ",
        show_p(block$baseline_p[[i]]), " | ",
        show_value(block$controlled_beta_SE[[i]]), " | ",
        show_p(block$controlled_p[[i]]), " |"
      )
    )
  }
  markdown_lines <- c(markdown_lines, "")
}
writeLines(
  markdown_lines,
  file.path(
    table_dir,
    paste0("table2_", main_catchment, "min_full_regression.md")
  )
)

sensitivity_key <- coefficients %>%
  filter(
    outcome %in% report_outcomes,
    specification == "controlled", term != "(Intercept)",
    !str_starts(term, "site_type"), term != "z_log_site_area"
  ) %>%
  mutate(
    significance = significance_stars(p_value)
  )
write_csv(
  sensitivity_key,
  file.path(table_dir, "table4_controlled_catchment_sensitivity.csv")
)

metadata_lines <- c(
  paste("Run time:", format(Sys.time(), tz = "UTC", usetz = TRUE)),
  paste("Project root:", project_root),
  paste("Main catchment (minutes):", main_catchment),
  paste("Requested minimum k:", k_neighbors),
  paste("Spatial weights used: row-standardized k-nearest neighbours; k =", analysis_k),
  "Spatial locations: representative inside points from allparks_land_buffer",
  "Main reported outcomes: pedestrian, transit, physical, visual, haptic, multidimensional",
  "Paper 4 handoff outcome: multidimensional accessibility at the main catchment",
  "OLS inference: HC3 heteroskedasticity-robust standard errors",
  "SAR inference: model-based standard errors; lag impacts exported separately",
  "Census QA: HasData == 1, complete predictors, no critical Census-quality flag",
  "",
  "R session:",
  capture.output(sessionInfo())
)
writeLines(metadata_lines, file.path(artifact_dir, "run_metadata.txt"))

message("Paper 3 analysis complete.")
message("Main catchment: ", main_catchment, " minutes")
message("Outputs: ", output_dir)
print(sample_sizes)
print(model_selection %>% filter(catchment_min == main_catchment))
