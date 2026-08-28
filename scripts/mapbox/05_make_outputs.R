# Paper 4: presentation-ready tables and figures

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
  library(ggplot2)
})

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) != 1) stop("Could not determine this script's location.")
script_path <- normalizePath(sub("^--file=", "", script_arg), winslash = "/")
project_root <- normalizePath(file.path(dirname(script_path), "../.."), winslash = "/")

dataset_path <- file.path(
  project_root, "data/processed/mapbox/mapbox_model_dataset.csv"
)
main_effect_path <- file.path(
  project_root, "outputs/mapbox/tables/table4_mapbox_spatially_filtered_effects.csv"
)
sensitivity_path <- file.path(
  project_root, "outputs/mapbox/tables/table6_mapbox_spatial_sensitivity_effects.csv"
)
spatial_diagnostic_path <- file.path(
  project_root, "outputs/mapbox/tables/tableB1_mapbox_spatial_diagnostics.csv"
)
full_coefficient_path <- file.path(
  project_root, "artifacts/mapbox/spatial_filtering/mapbox_reesf_all_coefficients.csv"
)
sample_path <- file.path(project_root, "artifacts/mapbox/mapbox_sample_qa.csv")
output_dir <- file.path(project_root, "outputs/mapbox")
table_dir <- file.path(output_dir, "tables")
figure_dir <- file.path(output_dir, "figures")
dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)

for (path in c(
  dataset_path, main_effect_path, sensitivity_path,
  spatial_diagnostic_path, full_coefficient_path, sample_path
)) {
  if (!file.exists(path)) stop("Required input not found: ", path)
}

data <- read_csv(dataset_path, show_col_types = FALSE) %>%
  mutate(park_num = as.character(as.integer(park_num)))
main_effects <- read_csv(main_effect_path, show_col_types = FALSE)
sensitivities <- read_csv(sensitivity_path, show_col_types = FALSE)
spatial_diagnostics <- read_csv(spatial_diagnostic_path, show_col_types = FALSE)
full_coefficients <- read_csv(full_coefficient_path, show_col_types = FALSE)
sample_table <- read_csv(sample_path, show_col_types = FALSE)

format_report_p <- function(p) {
  ifelse(p < 0.001, "<.001", sub("^0", "", sprintf("%.3f", p)))
}

write_csv(sample_table, file.path(table_dir, "table1_mapbox_sample.csv"))

site_data <- data %>%
  group_by(park_num) %>%
  summarise(
    site_name = first(site_name), municipality = first(municipality),
    site_type = first(site_type), coverage_pct = first(coverage_pct),
    mean_activity_index = mean(site_activity_index),
    median_activity_index = median(site_activity_index),
    physical_access_score = first(physical_access_score),
    visual_access_score = first(visible_water_ratio),
    haptic_access_score = first(shoreline_length_to_perimeter_ratio),
    multidimensional_access_score = first(multidimensional_access_score),
    site_area_m2 = first(site_area_m2),
    population_density_km2_10min = first(population_density_km2_10min),
    main_model_eligible = first(main_model_eligible),
    .groups = "drop"
  )

descriptive_variables <- c(
  "mean_activity_index", "physical_access_score", "visual_access_score",
  "haptic_access_score", "multidimensional_access_score", "site_area_m2",
  "population_density_km2_10min", "coverage_pct"
)
variable_labels <- c(
  mean_activity_index = "Mean Mapbox activity index",
  physical_access_score = "Physical accessibility",
  visual_access_score = "Visual accessibility",
  haptic_access_score = "Haptic accessibility",
  multidimensional_access_score = "Multidimensional accessibility",
  site_area_m2 = "Site area (m2)",
  population_density_km2_10min = "10-minute population density (people/km2)",
  coverage_pct = "Temporal coverage (%)"
)
site_descriptives <- bind_rows(lapply(descriptive_variables, function(variable) {
  x <- site_data[[variable]]
  tibble(
    variable, variable_label = unname(variable_labels[[variable]]),
    N = sum(!is.na(x)), mean = mean(x, na.rm = TRUE),
    SD = sd(x, na.rm = TRUE), median = median(x, na.rm = TRUE),
    Q1 = quantile(x, 0.25, na.rm = TRUE),
    Q3 = quantile(x, 0.75, na.rm = TRUE),
    minimum = min(x, na.rm = TRUE), maximum = max(x, na.rm = TRUE)
  )
}))
write_csv(
  site_descriptives,
  file.path(table_dir, "table2_mapbox_site_descriptives.csv")
)

# Give every waterfront equal weight in descriptive temporal summaries.
temporal_specs <- list(
  day_type = c("weekday", "weekend"),
  time_of_day = c("morning", "afternoon", "evening"),
  season = c("winter", "spring", "summer", "fall")
)
temporal_rows <- list()
for (dimension in names(temporal_specs)) {
  levels_in_order <- temporal_specs[[dimension]]
  site_category <- data %>%
    group_by(park_num, category = .data[[dimension]]) %>%
    summarise(site_mean_activity = mean(site_activity_index), .groups = "drop")
  temporal_rows[[dimension]] <- site_category %>%
    group_by(category) %>%
    summarise(
      N_waterfronts = n(), mean_activity = mean(site_mean_activity),
      SD = sd(site_mean_activity), median_activity = median(site_mean_activity),
      SE = SD / sqrt(N_waterfronts),
      conf_low = mean_activity - 1.96 * SE,
      conf_high = mean_activity + 1.96 * SE,
      .groups = "drop"
    ) %>%
    mutate(
      dimension,
      category = factor(category, levels = levels_in_order),
      .before = 1
    )
}
temporal_summary <- bind_rows(temporal_rows) %>%
  arrange(match(dimension, names(temporal_specs)), category) %>%
  mutate(category = as.character(category))
write_csv(
  temporal_summary,
  file.path(table_dir, "table3_mapbox_temporal_activity.csv")
)

term_labels <- c(
  `(Intercept)` = "Intercept",
  z_physical_access = "Physical accessibility",
  z_visual_access = "Visual accessibility",
  z_haptic_access = "Haptic accessibility",
  z_multidimensional_access = "Multidimensional accessibility",
  day_typeweekend = "Weekend (vs weekday)",
  time_of_dayafternoon = "Afternoon (vs morning)",
  time_of_dayevening = "Evening (vs morning)",
  seasonfall = "Fall (vs winter)",
  seasonspring = "Spring (vs winter)",
  seasonsummer = "Summer (vs winter)",
  site_typebeach = "Beach (vs riverfront)",
  `site_typecoastal waterfront without beach` =
    "Coastal waterfront without beach (vs riverfront)",
  site_typelakefront = "Lakefront (vs riverfront)",
  z_log_site_area = "Log site area",
  z_log_population_density_10min = "Log 10-minute population density"
)
main_full_table <- full_coefficients %>%
  transmute(
    model, term,
    term_label = coalesce(unname(term_labels[term]), term),
    estimate = Estimate, std_error = SE, statistic = t_value, p_value,
    conf_low = estimate - 1.96 * std_error,
    conf_high = estimate + 1.96 * std_error,
    percent_change = 100 * (exp(estimate) - 1),
    percent_change_low = 100 * (exp(conf_low) - 1),
    percent_change_high = 100 * (exp(conf_high) - 1)
  )
write_csv(
  main_full_table,
  file.path(table_dir, "table5_mapbox_main_reesf_coefficients.csv")
)

main_effects_formatted <- main_effects %>%
  transmute(
    `Accessibility measure` = recode(
      model,
      physical = "Physical", visual = "Visual", haptic = "Haptic",
      multidimensional = "Multidimensional"
    ),
    `beta (SE)` = sprintf("%.3f (%.3f)", estimate, std_error),
    p = format_report_p(p_value),
    `BH q` = format_report_p(BH_q),
    `Estimated difference in activity (95% CI)` = sprintf(
      "%+.1f%% (%+.1f%%, %+.1f%%)",
      percent_change, percent_change_low, percent_change_high
    )
  )
write_csv(
  main_effects_formatted,
  file.path(table_dir, "table4_mapbox_spatially_filtered_effects_formatted.csv")
)

spatial_diagnostics_formatted <- spatial_diagnostics %>%
  transmute(
    `Accessibility model` = recode(
      model,
      physical = "Physical", visual = "Visual", haptic = "Haptic",
      multidimensional = "Multidimensional"
    ),
    Waterfronts = N_waterfronts,
    Observations = N_observations,
    k = k_neighbors,
    `Residual Moran I` = sprintf("%.3f", residual_Moran_I),
    p = format_report_p(residual_Moran_p)
  )
write_csv(
  spatial_diagnostics_formatted,
  file.path(table_dir, "tableB1_mapbox_spatial_diagnostics_formatted.csv")
)

logged_sensitivity_formatted <- sensitivities %>%
  filter(scenario != "raw_outcome") %>%
  transmute(
    Specification = recode(
      scenario,
      coverage90 = "At least 90% coverage",
      population20 = "20-minute population density",
      no_site_type = "Without site type"
    ),
    `Accessibility measure` = recode(
      model,
      physical = "Physical", visual = "Visual", haptic = "Haptic",
      multidimensional = "Multidimensional"
    ),
    Sites = N_waterfronts,
    Observations = N_observations,
    `Difference in activity (95% CI)` = sprintf(
      "%+.1f%% (%+.1f%%, %+.1f%%)",
      percent_change, percent_change_low, percent_change_high
    ),
    p = format_report_p(p_value),
    `BH q` = format_report_p(BH_q),
    `Residual Moran p` = format_report_p(residual_Moran_p)
  )
write_csv(
  logged_sensitivity_formatted,
  file.path(table_dir, "table6a_mapbox_logged_sensitivity_formatted.csv")
)

raw_sensitivity_formatted <- sensitivities %>%
  filter(scenario == "raw_outcome") %>%
  transmute(
    `Accessibility measure` = recode(
      model,
      physical = "Physical", visual = "Visual", haptic = "Haptic",
      multidimensional = "Multidimensional"
    ),
    Sites = N_waterfronts,
    Observations = N_observations,
    `Raw-scale coefficient (95% CI)` = sprintf(
      "%.3f (%.3f, %.3f)", estimate, conf_low, conf_high
    ),
    p = format_report_p(p_value),
    `BH q` = format_report_p(BH_q),
    `Residual Moran p` = format_report_p(residual_Moran_p)
  )
write_csv(
  raw_sensitivity_formatted,
  file.path(table_dir, "table6b_mapbox_raw_outcome_sensitivity_formatted.csv")
)

full_coefficients_formatted <- main_full_table %>%
  transmute(
    Model = recode(
      model,
      physical = "Physical", visual = "Visual", haptic = "Haptic",
      multidimensional = "Multidimensional"
    ),
    Predictor = term_label,
    `beta (SE)` = sprintf("%.3f (%.3f)", estimate, std_error),
    `95% CI` = sprintf("%.3f, %.3f", conf_low, conf_high),
    p = format_report_p(p_value)
  )
write_csv(
  full_coefficients_formatted,
  file.path(table_dir, "table5_mapbox_main_reesf_coefficients_formatted.csv")
)

outcome_labels <- c(
  physical = "Physical", visual = "Visual", haptic = "Haptic",
  multidimensional = "Multidimensional"
)
outcome_order <- c("Physical", "Visual", "Haptic", "Multidimensional")

main_plot_data <- main_effects %>%
  mutate(
    outcome = factor(unname(outcome_labels[model]), levels = rev(outcome_order))
  )
main_plot <- ggplot(
  main_plot_data,
  aes(x = percent_change, y = outcome)
) +
  geom_vline(xintercept = 0, linetype = "dashed", colour = "grey45") +
  geom_errorbar(
    aes(xmin = percent_change_low, xmax = percent_change_high),
    width = 0.16, orientation = "y", colour = "#285C55", linewidth = 0.7
  ) +
  geom_point(colour = "#285C55", size = 3) +
  labs(
    title = "Accessibility and waterfront activity",
    subtitle = "Spatially filtered mixed-effects models; 98 waterfronts",
    x = "Estimated change in activity for a 1-SD increase (%)",
    y = NULL
  ) +
  theme_minimal(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold", size = 15),
    panel.grid.major.y = element_blank(), panel.grid.minor = element_blank()
  )
ggsave(
  file.path(figure_dir, "figure1_mapbox_main_accessibility_effects.png"),
  main_plot, width = 8, height = 5.2, units = "in", dpi = 320, bg = "white"
)

scenario_labels <- c(
  main_10min = "Primary: 10-min density",
  coverage90 = "At least 90% coverage",
  population20 = "20-min density",
  no_site_type = "Without site type"
)
sensitivity_plot_data <- bind_rows(
  main_effects %>% mutate(scenario = "main_10min"),
  sensitivities %>% filter(scenario != "raw_outcome")
) %>%
  mutate(
    outcome = factor(unname(outcome_labels[model]), levels = outcome_order),
    specification = factor(
      unname(scenario_labels[scenario]), levels = unname(scenario_labels)
    )
  )
sensitivity_plot <- ggplot(
  sensitivity_plot_data,
  aes(x = percent_change, y = specification, colour = specification)
) +
  geom_vline(xintercept = 0, linetype = "dashed", colour = "grey45") +
  geom_errorbar(
    aes(xmin = percent_change_low, xmax = percent_change_high),
    width = 0.13, orientation = "y", linewidth = 0.6
  ) +
  geom_point(size = 2.3) +
  facet_wrap(~outcome, ncol = 2, scales = "free_x") +
  scale_colour_brewer(palette = "Dark2", guide = "none") +
  labs(
    title = "Accessibility estimates across sensitivity specifications",
    subtitle = "Spatially filtered models; log activity outcome",
    x = "Estimated change in activity for a 1-SD increase (%)",
    y = NULL
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 14),
    panel.grid.major.y = element_blank(), panel.grid.minor = element_blank(),
    strip.text = element_text(face = "bold")
  )
ggsave(
  file.path(figure_dir, "figure2_mapbox_sensitivity_effects.png"),
  sensitivity_plot, width = 10, height = 7, units = "in", dpi = 320, bg = "white"
)

temporal_plot_data <- temporal_summary %>%
  mutate(
    panel = factor(
      recode(
        dimension,
        day_type = "Day type", time_of_day = "Time of day", season = "Season"
      ),
      levels = c("Day type", "Time of day", "Season")
    ),
    category_label = factor(
      recode(
        category,
        weekday = "Weekday", weekend = "Weekend", morning = "Morning",
        afternoon = "Afternoon", evening = "Evening", winter = "Winter",
        spring = "Spring", summer = "Summer", fall = "Fall"
      ),
      levels = c(
        "Weekday", "Weekend", "Morning", "Afternoon", "Evening",
        "Winter", "Spring", "Summer", "Fall"
      )
    )
  )
temporal_plot <- ggplot(
  temporal_plot_data,
  aes(x = category_label, y = mean_activity, group = 1)
) +
  geom_errorbar(
    aes(ymin = conf_low, ymax = conf_high),
    width = 0.12, colour = "#3E7C73", linewidth = 0.6
  ) +
  geom_point(colour = "#3E7C73", size = 2.8) +
  facet_wrap(~panel, scales = "free_x") +
  labs(
    title = "Observed waterfront activity by temporal period",
    subtitle = "Site-balanced means and 95% confidence intervals",
    x = NULL, y = "Mean Mapbox activity index"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 14),
    panel.grid.major.x = element_blank(), panel.grid.minor = element_blank(),
    axis.text.x = element_text(angle = 25, hjust = 1),
    strip.text = element_text(face = "bold")
  )
ggsave(
  file.path(figure_dir, "figure3_mapbox_temporal_activity.png"),
  temporal_plot, width = 10, height = 4.8, units = "in", dpi = 320, bg = "white"
)

# Summarize the complete Paper 4 workflow in one reproducible methods figure.
# The report may number this as Figure 6; the filename follows the output-package
# sequence used by this script.
workflow_boxes <- tribble(
  ~xmin, ~xmax, ~ymin, ~ymax, ~title, ~detail,
  2.0, 8.0, 14.4, 15.5,
  "Metro Vancouver waterfront sites",
  "114 urban blue-green waterfront sites",
  1.3, 8.7, 12.4, 13.7,
  "Accessibility measures",
  "Multidimensional accessibility: proposal-specified primary predictor\nPhysical, visual and haptic: dimension-specific predictors",
  1.3, 8.7, 10.3, 11.6,
  "Mapbox activity data",
  "2023 Mapbox Movement activity extracted for grid-cell centroids\nwithin site extraction areas",
  1.3, 8.7, 8.1, 9.6,
  "Temporal classification and coverage assessment",
  "Day type: weekday / weekend\nTime of day: morning / afternoon / evening\nSeason: winter / spring / summer / fall",
  1.3, 8.7, 6.0, 7.4,
  "Analytical samples",
  "103 sites with usable activity data (32,472 observations)\nPrimary complete case: 98 sites (30,946 observations)",
  0.3, 4.6, 3.9, 5.3,
  "Temporal covariates",
  "Day type\nTime of day\nSeason",
  5.4, 9.7, 3.9, 5.3,
  "Site-level covariates",
  "Site type\nLog land area\nLog 10-minute population density",
  1.3, 8.7, 1.9, 3.2,
  "Spatially filtered mixed-effects regression",
  "Log Mapbox activity index as outcome\nRepeated observations nested within sites; site random intercept\nResidual eigenvector spatial filtering",
  0.3, 4.8, 0.1, 1.2,
  "Accessibility models",
  "Multidimensional, physical, visual and haptic",
  5.2, 9.7, 0.1, 1.2,
  "Sensitivity analyses",
  "At least 90% coverage: 76 sites / 27,013 observations\n20-minute density; no site type; untransformed outcome"
) %>%
  mutate(
    x = (xmin + xmax) / 2,
    title_y = ymax - 0.32,
    detail_y = ymin + (ymax - ymin) * 0.34
  )

workflow_arrows <- tribble(
  ~x, ~y, ~xend, ~yend,
  5.0, 14.4, 5.0, 13.7,
  5.0, 12.4, 5.0, 11.6,
  5.0, 10.3, 5.0, 9.6,
  5.0, 8.1, 5.0, 7.4,
  4.2, 6.0, 2.5, 5.3,
  5.8, 6.0, 7.5, 5.3,
  2.5, 3.9, 4.3, 3.2,
  7.5, 3.9, 5.7, 3.2,
  4.3, 1.9, 2.6, 1.2,
  5.7, 1.9, 7.4, 1.2
)

workflow_plot <- ggplot() +
  geom_rect(
    data = workflow_boxes,
    aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax),
    fill = "white", colour = "grey15", linewidth = 0.6
  ) +
  geom_segment(
    data = workflow_arrows,
    aes(x = x, y = y, xend = xend, yend = yend),
    linewidth = 0.55, colour = "grey15",
    arrow = grid::arrow(length = grid::unit(0.12, "inches"), type = "open")
  ) +
  geom_text(
    data = workflow_boxes,
    aes(x = x, y = title_y, label = title),
    fontface = "bold", size = 4.0, lineheight = 0.95
  ) +
  geom_text(
    data = workflow_boxes,
    aes(x = x, y = detail_y, label = detail),
    size = 3.35, lineheight = 0.95
  ) +
  coord_cartesian(xlim = c(0, 10), ylim = c(0, 16), expand = FALSE) +
  theme_void() +
  theme(plot.margin = margin(10, 10, 10, 10))

ggsave(
  file.path(figure_dir, "figure4_mapbox_analysis_workflow.png"),
  workflow_plot, width = 11, height = 14, units = "in", dpi = 320,
  bg = "white"
)

site_type_counts <- site_data %>%
  count(site_type, name = "waterfronts") %>%
  arrange(desc(waterfronts))
write_csv(
  site_type_counts,
  file.path(table_dir, "tableS2_mapbox_site_type_counts.csv")
)

message("Mapbox tables and figures generated in: ", output_dir)
