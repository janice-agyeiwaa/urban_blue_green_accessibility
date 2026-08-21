# Paper 3 figures requested for the 10-minute results update.
# Usage: Rscript scripts/accessibility_analysis/02_make_accessibility_figures.R --main-catchment=10

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
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

analysis_path <- file.path(
  project_root, "data/processed/accessibility_analysis/accessibility_analysis_by_catchment.csv"
)
coef_path <- file.path(
  project_root, "artifacts/accessibility_analysis/tables/all_catchment_coefficients.csv"
)
figure_dir <- file.path(project_root, "outputs/accessibility_analysis/figures")
table_dir <- file.path(project_root, "outputs/accessibility_analysis/tables")
dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)
if (!file.exists(analysis_path) || !file.exists(coef_path)) {
  stop("Run 01_run_accessibility_models.R before making figures.")
}

dat <- read_csv(analysis_path, show_col_types = FALSE) %>%
  filter(walktime_min == main_catchment)
coefficients <- read_csv(coef_path, show_col_types = FALSE)

pairs <- list(
  list(
    pair = "Physical vs visual",
    x = "physical_access_score", y = "visual_access_ratio_capped",
    x_label = "Physical access", y_label = "Visual access"
  ),
  list(
    pair = "Physical vs haptic",
    x = "physical_access_score", y = "haptic_access_avery",
    x_label = "Physical access", y_label = "Haptic access"
  ),
  list(
    pair = "Visual vs haptic",
    x = "visual_access_ratio_capped", y = "haptic_access_avery",
    x_label = "Visual access", y_label = "Haptic access"
  )
)

pair_data <- bind_rows(lapply(pairs, function(spec) {
  tibble(
    park_num = dat$park_num,
    site_name = dat$site_name,
    pair = spec$pair,
    x = dat[[spec$x]], y = dat[[spec$y]],
    x_dimension = spec$x_label, y_dimension = spec$y_label
  )
}))

pair_stats <- pair_data %>%
  group_by(pair, x_dimension, y_dimension) %>%
  summarise(
    n = sum(complete.cases(x, y)),
    Pearson_r = cor(x, y, method = "pearson", use = "complete.obs"),
    Pearson_p = cor.test(x, y, method = "pearson")$p.value,
    Spearman_rho = cor(x, y, method = "spearman", use = "complete.obs"),
    Spearman_p = suppressWarnings(cor.test(x, y, method = "spearman", exact = FALSE)$p.value),
    x_median = median(x, na.rm = TRUE),
    y_median = median(y, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  mutate(
    annotation = sprintf(
      "Pearson r = %.3f (p %s)\nSpearman rho = %.3f (p %s)\nn = %d",
      Pearson_r,
      ifelse(Pearson_p < 0.001, "< 0.001", paste0("= ", formatC(Pearson_p, 3, format = "f"))),
      Spearman_rho,
      ifelse(Spearman_p < 0.001, "< 0.001", paste0("= ", formatC(Spearman_p, 3, format = "f"))),
      n
    ),
    facet_label = paste(pair, annotation, sep = "\n")
  )

quadrant_levels <- c("High-high", "High-low", "Low-high", "Low-low")
quadrant_code_colours <- c(
  "HH" = "#5DA5DA",
  "LL" = "#9AD9CF",
  "LH" = "#E85AAD",
  "HL" = "#F28E2B"
)

# Median splits are descriptive, not inferential. For each ordered pair, the
# first label refers to the horizontal dimension and the second to the vertical
# dimension. Values equal to a sample median are classified as high.
pair_classifications <- pair_data %>%
  left_join(
    pair_stats %>% select(pair, x_median, y_median),
    by = "pair"
  ) %>%
  group_by(pair) %>%
  mutate(
    x_z = as.numeric(scale(x)), y_z = as.numeric(scale(y)),
    absolute_standardized_difference = abs(x_z - y_z),
    x_level = case_when(
      is.na(x) ~ NA_character_,
      x >= x_median ~ "High",
      TRUE ~ "Low"
    ),
    y_level = case_when(
      is.na(y) ~ NA_character_,
      y >= y_median ~ "High",
      TRUE ~ "Low"
    ),
    quadrant_code = case_when(
      x_level == "High" & y_level == "High" ~ "HH",
      x_level == "High" & y_level == "Low" ~ "HL",
      x_level == "Low" & y_level == "High" ~ "LH",
      x_level == "Low" & y_level == "Low" ~ "LL",
      TRUE ~ NA_character_
    ),
    quadrant = case_when(
      quadrant_code == "HH" ~ "High-high",
      quadrant_code == "HL" ~ "High-low",
      quadrant_code == "LH" ~ "Low-high",
      quadrant_code == "LL" ~ "Low-low",
      TRUE ~ NA_character_
    ),
    divergence_rank = row_number(desc(absolute_standardized_difference)),
    is_top5_divergence = divergence_rank <= 5
  ) %>%
  ungroup() %>%
  mutate(quadrant = factor(quadrant, levels = quadrant_levels))

quadrant_summary <- pair_classifications %>%
  filter(!is.na(quadrant)) %>%
  count(
    pair, x_dimension, y_dimension, quadrant_code, quadrant,
    name = "site_count"
  ) %>%
  group_by(pair) %>%
  mutate(
    pair_n = sum(site_count),
    percent = 100 * site_count / pair_n
  ) %>%
  ungroup() %>%
  arrange(pair, quadrant)

extreme_sites <- pair_classifications %>%
  filter(!is.na(absolute_standardized_difference)) %>%
  arrange(pair, desc(absolute_standardized_difference)) %>%
  group_by(pair) %>%
  slice_head(n = 5) %>%
  mutate(rank = row_number()) %>%
  ungroup()

write_csv(
  pair_stats %>%
    select(
      pair, x_dimension, y_dimension, n, Pearson_r, Pearson_p,
      Spearman_rho, Spearman_p, x_median, y_median
    ),
  file.path(
    table_dir,
    paste0("table5_", main_catchment, "min_pairwise_correlations.csv")
  )
)
write_csv(
  extreme_sites %>%
    select(
      pair, rank, park_num, site_name, x, y, x_z, y_z,
      absolute_standardized_difference
    ),
  file.path(
    table_dir,
    paste0("tableS1_", main_catchment, "min_pairwise_extreme_sites.csv")
  )
)
write_csv(
  quadrant_summary %>%
    mutate(quadrant = as.character(quadrant)) %>%
    select(
      pair, x_dimension, y_dimension, quadrant_code, quadrant,
      site_count, pair_n, percent
    ),
  file.path(
    table_dir,
    paste0("table5b_", main_catchment, "min_quadrant_summary.csv")
  )
)
write_csv(
  pair_classifications %>%
    mutate(quadrant = as.character(quadrant)) %>%
    arrange(pair, park_num) %>%
    select(
      pair, park_num, site_name, x_dimension, y_dimension, x, y,
      x_median, y_median, x_level, y_level, quadrant_code, quadrant,
      x_z, y_z, absolute_standardized_difference, divergence_rank,
      is_top5_divergence
    ),
  file.path(
    table_dir,
    paste0("tableS4_", main_catchment, "min_quadrant_classifications.csv")
  )
)

pair_plot_data <- pair_data %>%
  left_join(pair_stats %>% select(pair, facet_label), by = "pair")

pair_plot <- ggplot(pair_plot_data, aes(x, y)) +
  geom_point(alpha = 0.68, size = 2.0, colour = "#256B63") +
  geom_vline(
    data = pair_stats, aes(xintercept = x_median),
    linetype = "dashed", linewidth = 0.45, colour = "grey45"
  ) +
  geom_hline(
    data = pair_stats, aes(yintercept = y_median),
    linetype = "dashed", linewidth = 0.45, colour = "grey45"
  ) +
  facet_wrap(~ facet_label, nrow = 1, scales = "free") +
  labs(
    title = paste0("Pairwise accessibility dimensions — ", main_catchment, "-minute specification"),
    subtitle = "Pearson and Spearman statistics are shown above each panel",
    x = "Horizontal-dimension score", y = "Vertical-dimension score",
    caption = "Dashed lines show sample medians; all 114 sites are shown."
  ) +
  theme_minimal(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold", size = 16),
    strip.text = element_text(face = "bold", lineheight = 1.05),
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour = "grey88", linewidth = 0.35),
    panel.grid.minor = element_blank()
  )

ggsave(
  file.path(
    figure_dir,
    paste0("figure2_", main_catchment, "min_pairwise_accessibility.png")
  ),
  pair_plot, width = 13.5, height = 5.2, dpi = 320, bg = "white"
)

quadrant_figure_path <- file.path(
  figure_dir,
  paste0("figure2b_", main_catchment, "min_quadrant_classification.png")
)
png(quadrant_figure_path, width = 13.5, height = 5.2, units = "in", res = 320)
par(
  mfrow = c(1, 3), mar = c(4.3, 4.3, 3.0, 1.0),
  oma = c(1.5, 0, 2.2, 0), mgp = c(2.5, 0.8, 0),
  family = "sans"
)
quadrant_legend_order <- c("HH", "LL", "LH", "HL")
for (spec in pairs) {
  panel_data <- pair_classifications %>% filter(pair == spec$pair)
  panel_counts <- setNames(
    quadrant_summary$site_count[quadrant_summary$pair == spec$pair],
    quadrant_summary$quadrant_code[quadrant_summary$pair == spec$pair]
  )
  x_padding <- 0.05 * diff(range(panel_data$x, na.rm = TRUE))
  y_padding <- 0.05 * diff(range(panel_data$y, na.rm = TRUE))
  plot(
    panel_data$x, panel_data$y,
    pch = 16, cex = 0.82,
    col = unname(quadrant_code_colours[panel_data$quadrant_code]),
    xlab = paste0(spec$x_label, " score"),
    ylab = paste0(spec$y_label, " score"),
    main = paste0(spec$pair, " (median split)"),
    xlim = range(panel_data$x, na.rm = TRUE) + c(-x_padding, x_padding),
    ylim = range(panel_data$y, na.rm = TRUE) + c(-y_padding, y_padding),
    bty = "o"
  )
  abline(v = unique(panel_data$x_median), lty = 2, lwd = 1.1, col = "grey30")
  abline(h = unique(panel_data$y_median), lty = 2, lwd = 1.1, col = "grey30")
  legend(
    "topright",
    legend = sprintf(
      "%s (n=%d)",
      quadrant_legend_order,
      as.integer(panel_counts[quadrant_legend_order])
    ),
    col = unname(quadrant_code_colours[quadrant_legend_order]),
    pch = 16, pt.cex = 0.85, cex = 0.75,
    title = "Quadrant", bg = "white", box.col = "grey70"
  )
}
mtext(
  paste0(
    "Median-based accessibility quadrants — ",
    main_catchment, "-minute specification"
  ),
  outer = TRUE, side = 3, line = 0.6, font = 2, cex = 1.25
)
mtext(
  "Codes follow horizontal-vertical order; values equal to a median are high.",
  outer = TRUE, side = 1, line = 0.1, cex = 0.76
)
dev.off()
# Spider profiles provide the requested case-level view of the sites with the
# largest disagreements among physical, visual, and haptic access.
profile_sites <- extreme_sites %>%
  group_by(park_num, site_name) %>%
  summarise(
    maximum_standardized_divergence = max(absolute_standardized_difference),
    .groups = "drop"
  ) %>%
  arrange(desc(maximum_standardized_divergence), park_num) %>%
  slice_head(n = 6)

profile_data <- dat %>%
  inner_join(profile_sites, by = c("park_num", "site_name")) %>%
  transmute(
    park_num, site_name, maximum_standardized_divergence,
    physical = physical_access_score,
    visual = visual_access_ratio_capped,
    haptic = haptic_access_avery
  )

profile_long <- bind_rows(
  profile_data %>% transmute(
    park_num, site_name, maximum_standardized_divergence,
    dimension = "Physical", score = physical
  ),
  profile_data %>% transmute(
    park_num, site_name, maximum_standardized_divergence,
    dimension = "Visual", score = visual
  ),
  profile_data %>% transmute(
    park_num, site_name, maximum_standardized_divergence,
    dimension = "Haptic", score = haptic
  )
) %>%
  mutate(
    dimension = factor(dimension, levels = c("Physical", "Visual", "Haptic")),
    site_label = paste0(park_num, ". ", site_name)
  )

write_csv(
  profile_long %>%
    select(
      park_num, site_name, dimension, score,
      maximum_standardized_divergence
    ),
  file.path(
    table_dir,
    paste0("tableS2_", main_catchment, "min_extreme_site_profiles.csv")
  )
)

profile_plot <- ggplot(
  profile_long,
  aes(x = dimension, y = score, group = site_label)
) +
  geom_polygon(fill = "#2d7f76", alpha = 0.25, colour = "#256b63", linewidth = 0.8) +
  geom_point(colour = "#7a2f25", size = 2.0) +
  coord_polar(start = -pi / 2) +
  facet_wrap(~ site_label, ncol = 3) +
  scale_y_continuous(limits = c(0, 1), breaks = c(0.25, 0.50, 0.75, 1.00)) +
  labs(
    title = paste0("Extreme accessibility profiles — ", main_catchment, "-minute specification"),
    subtitle = "Six sites with the largest standardized divergence between accessibility dimensions",
    x = NULL, y = NULL,
    caption = "All three dimensions range from 0 to 1; selection is documented in the companion CSV."
  ) +
  theme_minimal(base_size = 10) +
  theme(
    plot.title = element_text(face = "bold", size = 15),
    strip.text = element_text(face = "bold", size = 9),
    axis.text.y = element_text(size = 7),
    panel.grid.major.x = element_blank(),
    panel.grid.minor = element_blank()
  )

ggsave(
  file.path(
    figure_dir,
    paste0("figure3_", main_catchment, "min_extreme_site_profiles.png")
  ),
  profile_plot, width = 11.5, height = 7.5, dpi = 320, bg = "white"
)
# Asim's exploratory ternary plot is retained in updated, reproducible form.
# Coordinates show relative composition after the three scaled dimensions are
# normalized to sum to one; they do not represent total accessibility.
triangle_height <- sqrt(3) / 2
composition_data <- dat %>%
  transmute(
    park_num, site_name,
    physical = physical_access_score_scaled,
    visual = visual_access_scaled,
    haptic = haptic_access_scaled
  ) %>%
  mutate(
    component_sum = physical + visual + haptic,
    physical_share = if_else(component_sum > 0, physical / component_sum, NA_real_),
    visual_share = if_else(component_sum > 0, visual / component_sum, NA_real_),
    haptic_share = if_else(component_sum > 0, haptic / component_sum, NA_real_),
    ternary_x = visual_share + 0.5 * haptic_share,
    ternary_y = triangle_height * haptic_share
  )

write_csv(
  composition_data,
  file.path(
    table_dir,
    paste0("tableS3_", main_catchment, "min_accessibility_composition.csv")
  )
)

triangle_outline <- tibble(
  x = c(0, 1, 0.5, 0),
  y = c(0, 0, triangle_height, 0)
)
composition_plot <- ggplot(composition_data, aes(ternary_x, ternary_y)) +
  geom_path(
    data = triangle_outline, aes(x, y),
    inherit.aes = FALSE, colour = "grey25", linewidth = 0.8
  ) +
  geom_point(colour = "#2d7f76", alpha = 0.68, size = 2.1) +
  annotate("text", x = -0.035, y = -0.035, label = "Physical", hjust = 1) +
  annotate("text", x = 1.035, y = -0.035, label = "Visual", hjust = 0) +
  annotate(
    "text", x = 0.5, y = triangle_height + 0.035,
    label = "Haptic", fontface = "bold"
  ) +
  coord_equal(xlim = c(-0.10, 1.10), ylim = c(-0.08, 0.94), clip = "off") +
  labs(
    title = paste0(
      "Relative composition of accessibility dimensions — ",
      main_catchment, "-minute specification"
    ),
    subtitle = "Site identifiers and component shares are provided in the companion table",
    caption = paste(
      "Shares are calculated after separately scaling physical, visual, and",
      "haptic access; position represents composition, not total accessibility."
    )
  ) +
  theme_void(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold", size = 15),
    plot.subtitle = element_text(size = 11),
    plot.caption = element_text(size = 9, hjust = 0)
  )

ggsave(
  file.path(
    figure_dir,
    paste0("figure4_", main_catchment, "min_accessibility_composition.png")
  ),
  composition_plot, width = 8.5, height = 7.2, dpi = 320, bg = "white"
)
term_order <- c(
  "Principal accommodation expenditure",
  "Low-income residents (%)",
  "Bachelor's degree or higher (%)",
  "Visible-minority residents (%)",
  "Indigenous identity residents (%)"
)
coef_plot_data <- coefficients %>%
  filter(
    catchment_min == main_catchment,
    specification == "controlled",
    outcome %in% c(
      "pedestrian", "transit", "physical", "visual", "haptic",
      "multidimensional"
    ),
    term %in% c(
      "z_shelter", "z_low_income", "z_bachelors",
      "z_visible_minority", "z_indigenous"
    )
  ) %>%
  mutate(
    term_label = factor(term_label, levels = rev(term_order)),
    outcome = factor(
      outcome,
      levels = c(
        "pedestrian", "transit", "physical", "visual", "haptic",
        "multidimensional"
      )
    )
  )

coefficient_plot <- ggplot(
  coef_plot_data,
  aes(x = estimate, y = term_label, colour = outcome)
) +
  geom_vline(xintercept = 0, colour = "grey55", linewidth = 0.5) +
  geom_errorbar(
    aes(xmin = conf_low, xmax = conf_high), width = 0.12, orientation = "y"
  ) +
  geom_point(size = 2.4) +
  facet_wrap(~ outcome, ncol = 3) +
  scale_colour_brewer(palette = "Dark2", guide = "none") +
  labs(
    title = paste0("Controlled Paper 3 models — ", main_catchment, "-minute catchment"),
    subtitle = "Standardized coefficients and 95% intervals; site type and land-buffer area included",
    x = "Standardized coefficient", y = NULL,
    caption = "OLS intervals use HC3 robust standard errors; SAR intervals are model-based."
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 15),
    strip.text = element_text(face = "bold"),
    panel.grid.major.x = element_blank(),
    panel.grid.minor = element_blank()
  )

ggsave(
  file.path(
    figure_dir,
    paste0("figure5_", main_catchment, "min_controlled_coefficients.png")
  ),
  coefficient_plot, width = 11.5, height = 7.8, dpi = 320, bg = "white"
)
message("Paper 3 figures complete: ", figure_dir)
