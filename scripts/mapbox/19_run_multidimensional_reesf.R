# ============================================================
# 19_run_multidimensional_reesf.R
#
# Study 4 - proposal-aligned multilevel spatial filtering model
#
# PRIMARY MODEL ONLY:
# Multidimensional accessibility -> Mapbox activity
#
# Method:
# - Random-effects Eigenvector Spatial Filtering (RE-ESF)
# - Spatial dependence defined at waterfront/site level
# - Random intercept/group effect for waterfront
# - REML estimation
#
# Residual spatial autocorrelation is checked afterward using
# Moran's I with the same 5-nearest-neighbour setup used in
# Study 3.
# ============================================================


library(readr)
library(dplyr)
library(spmoran)
library(spdep)


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

project_root <- paste0(
  "C:/Users/owusu/Desktop/work/under_lab/",
  "urban_blue_green_accessibility"
)

input_path <- file.path(
  project_root,
  "data/processed/mapbox/mapbox_model_dataset_103_sites.csv"
)

park_points_path <- file.path(
  project_root,
  "data/interim/regression/spatial_autocorrelation/",
  "park_points_for_morans.csv"
)

output_dir <- file.path(
  project_root,
  "data/interim/mapbox/spatial_filtering"
)

dir.create(
  output_dir,
  recursive = TRUE,
  showWarnings = FALSE
)

coef_output_path <- file.path(
  output_dir,
  "multidimensional_reesf_coefficients.csv"
)

moran_output_path <- file.path(
  output_dir,
  "multidimensional_reesf_residual_morans_i.csv"
)

park_residual_output_path <- file.path(
  output_dir,
  "multidimensional_reesf_park_residuals.csv"
)

model_summary_output_path <- file.path(
  output_dir,
  "multidimensional_reesf_model_summary.txt"
)


# ------------------------------------------------------------
# Read Mapbox model dataset
# ------------------------------------------------------------

df <- read_csv(
  input_path,
  show_col_types = FALSE
) %>%
  mutate(
    park_num = as.character(park_num)
  )

cat("\nMapbox rows:", nrow(df), "\n")
cat("Unique waterfronts:", n_distinct(df$park_num), "\n")


if (n_distinct(df$park_num) != 103) {
  stop(
    paste(
      "Expected 103 waterfronts but found",
      n_distinct(df$park_num)
    )
  )
}


# ------------------------------------------------------------
# Read waterfront coordinates
# ------------------------------------------------------------

park_points <- read_csv(
  park_points_path,
  show_col_types = FALSE
) %>%
  mutate(
    park_num = as.character(park_num),
    x_coord = as.numeric(x_coord),
    y_coord = as.numeric(y_coord)
  ) %>%
  select(
    park_num,
    x_coord,
    y_coord
  )


# Check duplicate coordinate records
park_point_dupes <- park_points %>%
  count(park_num) %>%
  filter(n > 1)

if (nrow(park_point_dupes) > 0) {
  print(park_point_dupes)
  stop("Duplicate park_num values found in coordinate table.")
}


# ------------------------------------------------------------
# Create transformations
# ------------------------------------------------------------

# Site area was already calculated from the land polygon.
# Recreate the transformation if necessary.

if (!"log_site_area" %in% names(df)) {

  if (!"site_area_m2" %in% names(df)) {
    stop(
      "Neither log_site_area nor site_area_m2 exists in dataset."
    )
  }

  df <- df %>%
    mutate(
      log_site_area = log(site_area_m2)
    )
}


# Population density transformation used in the existing models
df <- df %>%
  mutate(
    log_population_density =
      log1p(population_density_km2)
  )


# ------------------------------------------------------------
# Standardize Level-2 continuous variables
#
# IMPORTANT:
# Standardization is based on ONE ROW PER WATERFRONT,
# not all 32,472 repeated temporal observations.
# ------------------------------------------------------------

park_level <- df %>%
  select(
    park_num,
    multidimensional_access_score,
    log_site_area,
    log_population_density
  ) %>%
  distinct(
    park_num,
    .keep_all = TRUE
  )


park_level <- park_level %>%
  mutate(
    z_multidimensional_access_score =
      as.numeric(
        scale(multidimensional_access_score)
      ),

    z_log_site_area =
      as.numeric(
        scale(log_site_area)
      ),

    z_log_population_density =
      as.numeric(
        scale(log_population_density)
      )
  )


df <- df %>%
  select(
    -any_of(
      c(
        "z_multidimensional_access_score",
        "z_log_site_area",
        "z_log_population_density"
      )
    )
  ) %>%
  left_join(
    park_level %>%
      select(
        park_num,
        z_multidimensional_access_score,
        z_log_site_area,
        z_log_population_density
      ),
    by = "park_num"
  )


# ------------------------------------------------------------
# Set categorical reference groups
# ------------------------------------------------------------

df <- df %>%
  mutate(
    day_type = relevel(
      factor(day_type),
      ref = "weekday"
    ),

    time_of_day = relevel(
      factor(time_of_day),
      ref = "morning"
    ),

    season = relevel(
      factor(season),
      ref = "winter"
    ),

    site_type = relevel(
      factor(site_type),
      ref = "riverfront"
    )
  )


# ------------------------------------------------------------
# Join coordinates to every temporal observation
# ------------------------------------------------------------

df <- df %>%
  left_join(
    park_points,
    by = "park_num"
  )


missing_coords <- df %>%
  filter(
    is.na(x_coord) |
      is.na(y_coord)
  )

if (nrow(missing_coords) > 0) {

  cat("\nWaterfronts missing coordinates:\n")

  print(
    missing_coords %>%
      distinct(park_num)
  )

  stop(
    "Some Study 4 waterfronts have missing coordinates."
  )
}


# ------------------------------------------------------------
# QA
# ------------------------------------------------------------

required_vars <- c(
  "site_activity_index",
  "z_multidimensional_access_score",
  "day_type",
  "time_of_day",
  "season",
  "site_type",
  "z_log_site_area",
  "z_log_population_density",
  "x_coord",
  "y_coord"
)

missing_vars <- setdiff(
  required_vars,
  names(df)
)

if (length(missing_vars) > 0) {
  stop(
    paste(
      "Missing model variables:",
      paste(missing_vars, collapse = ", ")
    )
  )
}


# Remove incomplete model records
model_df <- df %>%
  select(
    park_num,
    all_of(required_vars)
  ) %>%
  na.omit()


cat("\nModel rows:", nrow(model_df), "\n")
cat(
  "Model waterfronts:",
  n_distinct(model_df$park_num),
  "\n"
)


# ------------------------------------------------------------
# Dependent variable
# ------------------------------------------------------------

y <- model_df$site_activity_index


# ------------------------------------------------------------
# Fixed-effect design matrix
#
# resf() estimates its own intercept, so remove the
# model.matrix intercept column.
# ------------------------------------------------------------

x <- model.matrix(
  ~
    z_multidimensional_access_score +
    day_type +
    time_of_day +
    season +
    site_type +
    z_log_site_area +
    z_log_population_density,
  data = model_df
)

x <- x[
  ,
  colnames(x) != "(Intercept)",
  drop = FALSE
]


cat(
  "\nFixed-effect predictors:",
  ncol(x),
  "\n"
)

print(
  colnames(x)
)


# ------------------------------------------------------------
# Spatial coordinates and site/group ID
# ------------------------------------------------------------

coords <- as.matrix(
  model_df %>%
    select(
      x_coord,
      y_coord
    )
)

site_id <- model_df$park_num


# ------------------------------------------------------------
# Generate Moran eigenvectors at WATERFRONT level
#
# s_id tells spmoran that repeated observations belong
# to the same spatial site.
#
# meigen_f is used because the temporal dataset contains
# >32,000 observations.
# ------------------------------------------------------------

cat(
  "\nGenerating Moran eigenvectors by waterfront...\n"
)

meig_site <- meigen_f(
  coords = coords,
  enum = 200,
  s_id = site_id
)


cat(
  "Moran eigenvectors generated.\n"
)


# ------------------------------------------------------------
# Fit proposal-aligned multilevel RE-ESF model
#
# Spatially dependent site effects:
#   meig_site
#
# Spatially independent site random effects:
#   xgroup = site_id
#
# REML matches the estimation approach used for the
# main mixed-effects models.
# ------------------------------------------------------------

cat(
  "\nFitting multidimensional RE-ESF model...\n"
)


reesf_model <- resf(
  y = y,
  x = x,
  meig = meig_site,
  xgroup = site_id,
  method = "reml"
)


cat("\nModel complete.\n\n")

print(
  reesf_model
)


# ------------------------------------------------------------
# Save full model summary
# ------------------------------------------------------------

capture.output(
  print(reesf_model),
  file = model_summary_output_path
)


# ------------------------------------------------------------
# Extract fixed-effect coefficients
# ------------------------------------------------------------

coef_table <- as.data.frame(
  reesf_model$b
)

coef_table$term <- rownames(
  coef_table
)

rownames(
  coef_table
) <- NULL


coef_table <- coef_table %>%
  select(
    term,
    everything()
  )


write_csv(
  coef_table,
  coef_output_path
)


# ------------------------------------------------------------
# Extract residuals
# ------------------------------------------------------------

model_df$residual <- as.numeric(
  reesf_model$resid
)


# ------------------------------------------------------------
# Aggregate residuals to ONE residual value per waterfront
#
# Spatial units are waterfronts, not the 32,472 repeated
# temporal observations.
# ------------------------------------------------------------

park_residuals <- model_df %>%
  group_by(
    park_num
  ) %>%
  summarise(
    mean_residual = mean(
      residual,
      na.rm = TRUE
    ),
    n_temporal_observations = n(),
    .groups = "drop"
  ) %>%
  left_join(
    park_points,
    by = "park_num"
  )


# Sort by numeric park ID for stable ordering
park_residuals <- park_residuals %>%
  mutate(
    park_num_numeric =
      as.numeric(park_num)
  ) %>%
  arrange(
    park_num_numeric
  ) %>%
  select(
    -park_num_numeric
  )


write_csv(
  park_residuals,
  park_residual_output_path
)


# ------------------------------------------------------------
# Moran's I diagnostic
#
# Same setup used in Study 3:
# - 5 nearest neighbours
# - row-standardized weights
# ------------------------------------------------------------

coords_park <- as.matrix(
  park_residuals %>%
    select(
      x_coord,
      y_coord
    )
)


k_neighbors <- 5


knn <- knearneigh(
  coords_park,
  k = k_neighbors
)

nb <- knn2nb(
  knn
)

listw <- nb2listw(
  nb,
  style = "W",
  zero.policy = TRUE
)


moran_result <- moran.test(
  park_residuals$mean_residual,
  listw,
  zero.policy = TRUE
)


moran_table <- tibble(
  model = "multidimensional_REESF",
  n_waterfronts = nrow(
    park_residuals
  ),
  k_neighbors = k_neighbors,

  morans_i = unname(
    moran_result$estimate[["Moran I statistic"]]
  ),

  expected_i = unname(
    moran_result$estimate[["Expectation"]]
  ),

  variance = unname(
    moran_result$estimate[["Variance"]]
  ),

  statistic = unname(
    moran_result$statistic
  ),

  p_value = moran_result$p.value
) %>%
  mutate(
    spatial_autocorrelation =
      case_when(
        p_value < 0.05 &
          morans_i > 0
        ~ "significant_positive",

        p_value < 0.05 &
          morans_i < 0
        ~ "significant_negative",

        TRUE
        ~ "not_significant"
      )
  )


write_csv(
  moran_table,
  moran_output_path
)


# ------------------------------------------------------------
# Console summary
# ------------------------------------------------------------

cat(
  "\n============================================\n"
)

cat(
  "MULTIDIMENSIONAL RE-ESF RESULTS\n"
)

cat(
  "============================================\n"
)


cat(
  "\nFixed-effect coefficients:\n"
)

print(
  coef_table
)


cat(
  "\nResidual Moran's I:\n"
)

print(
  moran_table
)


cat(
  "\nOutputs:\n"
)

cat(
  model_summary_output_path,
  "\n"
)

cat(
  coef_output_path,
  "\n"
)

cat(
  moran_output_path,
  "\n"
)

cat(
  park_residual_output_path,
  "\n"
)


cat(
  "\nDone.\n"
)
