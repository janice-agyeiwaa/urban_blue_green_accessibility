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
  full_coefficient_path, sample_path
)) {
  if (!file.exists(path)) stop("Required input not found: ", path)
}

data <- read_csv(dataset_path, show_col_types = FALSE) %>%
  mutate(park_num = as.character(as.integer(park_num)))
main_effects <- read_csv(main_effect_path, show_col_types = FALSE)
sensitivities <- read_csv(sensitivity_path, show_col_types = FALSE)
full_coefficients <- read_csv(full_coefficient_path, show_col_types = FALSE)
sample_table <- read_csv(sample_path, show_col_types = FALSE)

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

site_type_counts <- site_data %>%
  count(site_type, name = "waterfronts") %>%
  arrange(desc(waterfronts))
write_csv(
  site_type_counts,
  file.path(table_dir, "tableS2_mapbox_site_type_counts.csv")
)

message("Mapbox tables and figures generated in: ", output_dir)
