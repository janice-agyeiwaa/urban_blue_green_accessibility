# Paper 3: 10-minute haptic-measure sensitivity analysis
#
# Compares the primary shoreline-to-perimeter measure with the exploratory
# DTM-OSM unobstructed-approachable-shoreline proxy. The alternate proxy is a
# sensitivity analysis only; it does not replace the primary haptic component
# in the multidimensional access score.

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(spdep)
  library(spatialreg)
  library(sandwich)
  library(ggplot2)
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
requested_k <- as.integer(get_arg("k", "6"))
if (!main_catchment %in% c(5L, 10L, 20L, 30L)) {
  stop("--main-catchment must be one of 5, 10, 20, or 30.")
}
if (is.na(requested_k) || requested_k < 1) stop("--k must be positive.")

analysis_path <- file.path(
  project_root, "data/processed/accessibility_analysis/accessibility_analysis_by_catchment.csv"
)
proxy_path <- file.path(
  project_root, "data/processed/haptic/haptic_access_proxy_dtm_osm.csv"
)
table_dir <- file.path(project_root, "outputs/accessibility_analysis/tables")
figure_dir <- file.path(project_root, "outputs/accessibility_analysis/figures")
diagnostic_dir <- file.path(
  project_root, "artifacts/accessibility_analysis/diagnostics"
)
dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(diagnostic_dir, recursive = TRUE, showWarnings = FALSE)

for (path in c(analysis_path, proxy_path)) {
  if (!file.exists(path)) stop("Required input not found: ", path)
}

z_scale <- function(x) {
  if (all(is.na(x)) || sd(x, na.rm = TRUE) == 0) return(rep(NA_real_, length(x)))
  as.numeric(scale(x))
}

analysis <- read_csv(analysis_path, show_col_types = FALSE)
proxy <- read_csv(proxy_path, show_col_types = FALSE) %>%
  transmute(
    park_num = as.integer(park_num),
    haptic_dtm_osm = haptic_access_proxy_score
  )

if (nrow(proxy) != 114 || n_distinct(proxy$park_num) != 114 ||
    anyNA(proxy$haptic_dtm_osm) ||
    any(proxy$haptic_dtm_osm < 0 | proxy$haptic_dtm_osm > 1)) {
  stop("The DTM-OSM proxy must contain one complete 0-1 value for each of 114 sites.")
}

site_data <- analysis %>%
  filter(walktime_min == main_catchment) %>%
  left_join(proxy, by = "park_num")
if (nrow(site_data) != 114 || anyNA(site_data$haptic_dtm_osm)) {
  stop("The haptic proxy did not join completely to the 114-site analysis file.")
}

measure_labels <- c(
  shoreline_perimeter = "Shoreline-to-perimeter measure",
  dtm_osm = "DTM-OSM approachability proxy"
)

cor_data <- site_data %>%
  transmute(
    park_num, site_name, municipality,
    shoreline_perimeter = haptic_access_avery,
    dtm_osm = haptic_dtm_osm
  )
pearson <- cor.test(
  cor_data$shoreline_perimeter, cor_data$dtm_osm, method = "pearson"
)
spearman <- suppressWarnings(cor.test(
  cor_data$shoreline_perimeter, cor_data$dtm_osm,
  method = "spearman", exact = FALSE
))
correlation_result <- tibble(
  catchment_min = main_catchment,
  N = nrow(cor_data),
  Pearson_r = unname(pearson$estimate),
  Pearson_p = pearson$p.value,
  Spearman_rho = unname(spearman$estimate),
  Spearman_p = spearman$p.value
)
write_csv(
  correlation_result,
  file.path(table_dir, "tableS5_10min_haptic_measure_correlation.csv")
)

model_source <- site_data %>% filter(regression_eligible)
if (nrow(model_source) != 105) {
  stop("Expected the canonical 10-minute regression sample of 105 sites.")
}

prepare_model_data <- function(outcome) {
  model_source %>%
    transmute(
      park_num, site_name, municipality, site_point_x, site_point_y,
      site_type = relevel(factor(site_type), ref = "beach"),
      z_log_site_area = z_scale(log_site_area),
      z_y = z_scale(.data[[outcome]]),
      z_shelter = z_scale(shelter_expenditures_principal),
      z_low_income = z_scale(pct_low_income),
      z_bachelors = z_scale(pct_bachelors_and_above),
      z_visible_minority = z_scale(pct_visible_minority),
      z_indigenous = z_scale(pct_indigenous_identity)
    )
}

minimum_connected_k <- function(dat, starting_k) {
  coords <- as.matrix(dat[c("site_point_x", "site_point_y")])
  for (candidate_k in seq.int(starting_k, nrow(dat) - 1L)) {
    nb <- suppressWarnings(knn2nb(
      knearneigh(coords, k = candidate_k), row.names = dat$park_num
    ))
    if (n.comp.nb(nb)$nc == 1) return(candidate_k)
  }
  stop("Could not create a connected kNN graph.")
}

# Match the main analysis: find the smallest common k that connects the
# eligible site graph at every catchment, rather than optimizing k for the
# 10-minute sample alone.
catchment_k <- vapply(
  sort(unique(analysis$walktime_min)),
  function(catchment) {
    dat <- analysis %>%
      filter(walktime_min == catchment, regression_eligible) %>%
      transmute(park_num, site_point_x, site_point_y)
    minimum_connected_k(dat, requested_k)
  },
  integer(1)
)
analysis_k <- max(catchment_k)
build_weights <- function(dat) {
  coords <- as.matrix(dat[c("site_point_x", "site_point_y")])
  nb <- suppressWarnings(knn2nb(
    knearneigh(coords, k = analysis_k), row.names = dat$park_num
  ))
  listw <- nb2listw(nb, style = "W", zero.policy = TRUE)
  attr(listw, "accessibility_k") <- analysis_k
  listw
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
  test <- if (inherits(model, "lm")) {
    lm.morantest(model, listw, zero.policy = TRUE, alternative = "two.sided")
  } else {
    moran.test(residuals(model), listw, zero.policy = TRUE, alternative = "two.sided")
  }
  c(I = unname(test$estimate[[1]]), p = test$p.value)
}

model_metrics <- function(model, family, listw, n) {
  if (inherits(model, "model_error")) {
    return(tibble(
      family, N = n, k_neighbors = analysis_k, AIC = NA_real_,
      log_likelihood = NA_real_, residual_Moran_I = NA_real_,
      residual_Moran_p = NA_real_, fit_error = model$message
    ))
  }
  moran <- residual_moran(model, listw)
  tibble(
    family, N = n, k_neighbors = analysis_k, AIC = AIC(model),
    log_likelihood = as.numeric(logLik(model)),
    residual_Moran_I = unname(moran[["I"]]),
    residual_Moran_p = unname(moran[["p"]]), fit_error = NA_character_
  )
}

choose_family <- function(metrics) {
  ols <- metrics %>% filter(family == "OLS")
  if (nrow(ols) == 1 && is.finite(ols$residual_Moran_p) &&
      ols$residual_Moran_p >= 0.05) return("OLS")
  spatial <- metrics %>%
    filter(family != "OLS", is.na(fit_error), is.finite(AIC))
  cleared <- spatial %>% filter(residual_Moran_p >= 0.05)
  pool <- if (nrow(cleared) > 0) cleared else spatial
  if (nrow(pool) == 0) stop("No spatial candidate model converged.")
  pool %>% arrange(AIC) %>% slice(1) %>% pull(family)
}

extract_coefficients <- function(model, family) {
  if (family == "OLS") {
    estimates <- coef(model)
    se <- sqrt(diag(sandwich::vcovHC(model, type = "HC3")))
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
  )
}

outcomes <- c(
  shoreline_perimeter = "haptic_access_avery",
  dtm_osm = "haptic_dtm_osm"
)
candidate_rows <- list()
diagnostic_rows <- list()
coefficient_rows <- list()

for (measure_id in names(outcomes)) {
  dat <- prepare_model_data(outcomes[[measure_id]])
  if (anyNA(dat)) stop("Unexpected missing values for ", measure_id, ".")
  listw <- build_weights(dat)

  baseline_candidates <- lapply(
    c("OLS", "SAR_lag", "SAR_error"),
    function(family) fit_model(family, baseline_formula, dat, listw)
  )
  names(baseline_candidates) <- c("OLS", "SAR_lag", "SAR_error")
  baseline_metrics <- bind_rows(lapply(
    names(baseline_candidates),
    function(family) model_metrics(
      baseline_candidates[[family]], family, listw, nrow(dat)
    )
  ))
  baseline_family <- choose_family(baseline_metrics)

  controlled_initial <- fit_model(
    baseline_family, controlled_formula, dat, listw
  )
  controlled_initial_metrics <- model_metrics(
    controlled_initial, baseline_family, listw, nrow(dat)
  )
  controlled_family <- baseline_family
  controlled_model <- controlled_initial
  controlled_candidates_metrics <- controlled_initial_metrics
  if (controlled_initial_metrics$residual_Moran_p < 0.05) {
    controlled_candidates <- lapply(
      c("OLS", "SAR_lag", "SAR_error"),
      function(family) fit_model(family, controlled_formula, dat, listw)
    )
    names(controlled_candidates) <- c("OLS", "SAR_lag", "SAR_error")
    controlled_candidates_metrics <- bind_rows(lapply(
      names(controlled_candidates),
      function(family) model_metrics(
        controlled_candidates[[family]], family, listw, nrow(dat)
      )
    ))
    controlled_family <- choose_family(controlled_candidates_metrics)
    controlled_model <- controlled_candidates[[controlled_family]]
  }

  candidate_rows[[measure_id]] <- bind_rows(
    baseline_metrics %>% mutate(specification = "baseline"),
    controlled_candidates_metrics %>% mutate(specification = "controlled")
  ) %>% mutate(
    measure = measure_id,
    measure_label = unname(measure_labels[[measure_id]]), .before = 1
  )

  for (specification in c("baseline", "controlled")) {
    model <- if (specification == "baseline") {
      baseline_candidates[[baseline_family]]
    } else controlled_model
    family <- if (specification == "baseline") baseline_family else controlled_family
    diagnostic_rows[[paste(measure_id, specification)]] <-
      model_metrics(model, family, listw, nrow(dat)) %>%
      mutate(
        measure = measure_id,
        measure_label = unname(measure_labels[[measure_id]]),
        specification, .before = 1
      )
    coefficient_rows[[paste(measure_id, specification)]] <-
      extract_coefficients(model, family) %>%
      mutate(
        measure = measure_id,
        measure_label = unname(measure_labels[[measure_id]]), specification,
        family, N = nrow(dat), k_neighbors = analysis_k, .before = 1
      )
  }
}

candidates <- bind_rows(candidate_rows)
diagnostics <- bind_rows(diagnostic_rows)
coefficients <- bind_rows(coefficient_rows)

predictor_terms <- c(
  "z_shelter", "z_low_income", "z_bachelors", "z_visible_minority", "z_indigenous"
)
term_labels <- c(
  z_shelter = "Principal accommodation expenditure",
  z_low_income = "Low-income residents (%)",
  z_bachelors = "Bachelor's degree or higher (%)",
  z_visible_minority = "Visible-minority residents (%)",
  z_indigenous = "Indigenous identity residents (%)"
)

comparison_table <- coefficients %>%
  filter(specification == "controlled", term %in% predictor_terms) %>%
  mutate(
    term_label = unname(term_labels[term]),
    BH_q = p.adjust(p_value, method = "BH")
  ) %>%
  select(
    measure, measure_label, specification, family, N, k_neighbors,
    term, term_label, estimate, std_error, p_value, BH_q, conf_low, conf_high,
    inference
  )
write_csv(
  comparison_table,
  file.path(table_dir, "table8_10min_haptic_sensitivity.csv")
)

format_number <- function(x) sprintf("%.3f", x)
primary_display <- comparison_table %>%
  filter(measure == "shoreline_perimeter") %>%
  transmute(
    term, Predictor = term_label,
    `Shoreline-to-perimeter beta (SE)` = paste0(
      format_number(estimate), " (", format_number(std_error), ")"
    ),
    `Primary p` = format_number(p_value),
    `Primary BH q` = format_number(BH_q)
  )
proxy_display <- comparison_table %>%
  filter(measure == "dtm_osm") %>%
  transmute(
    term,
    `DTM-OSM beta (SE)` = paste0(
      format_number(estimate), " (", format_number(std_error), ")"
    ),
    `Proxy p` = format_number(p_value),
    `Proxy BH q` = format_number(BH_q)
  )
formatted_table <- primary_display %>%
  left_join(proxy_display, by = "term") %>%
  select(-term)
write_csv(
  formatted_table,
  file.path(table_dir, "table8_10min_haptic_sensitivity_formatted.csv")
)
markdown_header <- paste0("| ", paste(names(formatted_table), collapse = " | "), " |")
markdown_rule <- paste0("| ", paste(rep("---", ncol(formatted_table)), collapse = " | "), " |")
markdown_rows <- apply(formatted_table, 1, function(row) {
  paste0("| ", paste(row, collapse = " | "), " |")
})
writeLines(
  c(
    "# Ten-minute haptic sensitivity",
    "",
    markdown_header, markdown_rule, markdown_rows,
    "",
    paste0(
      "Note. N = 105. The shoreline-to-perimeter model is OLS with HC3 robust ",
      "standard errors; the DTM-OSM model is a spatial-lag model. Both include ",
      "waterfront type and standardized log land-buffer area. BH q-values are ",
      "adjusted across the ten socioeconomic comparisons in this sensitivity table."
    )
  ),
  file.path(table_dir, "table8_10min_haptic_sensitivity.md"),
  useBytes = TRUE
)
write_csv(
  diagnostics,
  file.path(table_dir, "table8b_10min_haptic_model_diagnostics.csv")
)
site_control_table <- coefficients %>%
  filter(
    specification == "controlled",
    grepl("^site_type", term) | term == "z_log_site_area"
  ) %>%
  select(
    measure, measure_label, specification, family, N, k_neighbors,
    term, estimate, std_error, p_value, conf_low, conf_high, inference
  )
write_csv(
  site_control_table,
  file.path(table_dir, "table8c_10min_haptic_sensitivity_site_controls.csv")
)
write_csv(
  coefficients,
  file.path(diagnostic_dir, "10min_haptic_sensitivity_all_coefficients.csv")
)
write_csv(
  candidates,
  file.path(diagnostic_dir, "10min_haptic_sensitivity_candidates.csv")
)

format_p <- function(p) {
  if (p < 0.001) "< 0.001" else paste0("= ", formatC(p, 3, format = "f"))
}
annotation <- correlation_result %>%
  transmute(label = sprintf(
    "Pearson r = %.3f (p %s)\nSpearman rho = %.3f (p %s)\nn = %d",
    Pearson_r, format_p(Pearson_p), Spearman_rho, format_p(Spearman_p), N
  )) %>% pull(label)

plot <- ggplot(
  cor_data, aes(x = shoreline_perimeter, y = dtm_osm)
) +
  geom_point(colour = "#3E7C73", alpha = 0.68, size = 2.4) +
  geom_smooth(method = "lm", se = TRUE, colour = "#285C55", fill = "#B8D5D0", linewidth = 0.7) +
  labs(
    title = "Comparison of haptic access measures",
    subtitle = paste0("All 114 waterfront sites\n", gsub("\n", "; ", annotation)),
    x = "Shoreline-to-perimeter haptic score",
    y = "DTM-OSM unobstructed approachability proxy"
  ) +
  coord_cartesian(xlim = c(0, 1), ylim = c(0, 1)) +
  theme_minimal(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold", size = 15),
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour = "grey88", linewidth = 0.35),
    panel.grid.minor = element_blank()
  )

ggsave(
  file.path(figure_dir, "figure6_10min_haptic_sensitivity.png"),
  plot, width = 8, height = 6, units = "in", dpi = 320, bg = "white"
)

message(
  "Haptic sensitivity complete: N=", nrow(model_source),
  "; k=", analysis_k,
  "; Pearson r=", round(correlation_result$Pearson_r, 3),
  "; Spearman rho=", round(correlation_result$Spearman_rho, 3), "."
)
