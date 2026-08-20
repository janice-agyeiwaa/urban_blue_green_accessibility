from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


# ============================================================
# 10_model_physical_accessibility.py
#
# Model 1:
# Mapbox activity ~ physical accessibility + temporal controls
#                  + site type + site area + population density
#                  + random intercept for park
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "mapbox"
    / "mapbox_model_dataset_103_sites.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "mapbox"
    / "models"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------------
# Read data
# ------------------------------------------------------------

df = pd.read_csv(
    INPUT_FILE,
    dtype={"park_num": str}
)

print("\nDataset loaded.")
print("Rows:", len(df))
print("Unique parks:", df["park_num"].nunique())


# ------------------------------------------------------------
# Identify activity outcome
# ------------------------------------------------------------

possible_outcomes = [
    "mean_activity",
    "activity_index_total",
    "site_activity_index",
    "activity_index"
]

outcome = next(
    (
        col
        for col in possible_outcomes
        if col in df.columns
    ),
    None
)

if outcome is None:
    raise ValueError(
        "Could not identify the Mapbox activity outcome.\n"
        f"Columns available:\n{df.columns.tolist()}"
    )

print("\nOutcome variable:")
print(outcome)


# ------------------------------------------------------------
# Required variables
# ------------------------------------------------------------

required = [
    "park_num",
    "physical_access_score",
    "site_area_m2",
    "population_density_km2",
    "day_type",
    "time_of_day",
    "season",
    "site_type"
]

missing = [
    x for x in required
    if x not in df.columns
]

if missing:
    raise ValueError(
        f"Missing required variables: {missing}"
    )


# ------------------------------------------------------------
# Transform skewed controls
# ------------------------------------------------------------

df["log_site_area"] = np.log(
    df["site_area_m2"]
)

df["log_population_density"] = np.log1p(
    df["population_density_km2"]
)


# ------------------------------------------------------------
# Standardize continuous site-level predictors
#
# IMPORTANT:
# Standardize at PARK level, not across all repeated rows.
#
# Otherwise parks with more temporal observations would
# contribute more heavily to the mean and SD.
# ------------------------------------------------------------

park_vars = (
    df[
        [
            "park_num",
            "physical_access_score",
            "log_site_area",
            "log_population_density"
        ]
    ]
    .drop_duplicates("park_num")
    .copy()
)

variables_to_standardize = [
    "physical_access_score",
    "log_site_area",
    "log_population_density"
]

for variable in variables_to_standardize:

    mean = park_vars[variable].mean()
    sd = park_vars[variable].std()

    print(
        f"\n{variable}: "
        f"mean = {mean:.6f}, "
        f"SD = {sd:.6f}"
    )

    park_vars[f"z_{variable}"] = (
        park_vars[variable] - mean
    ) / sd


# ------------------------------------------------------------
# Join standardized values back to repeated observations
# ------------------------------------------------------------

z_columns = [
    "park_num",
    "z_physical_access_score",
    "z_log_site_area",
    "z_log_population_density"
]

df = df.merge(
    park_vars[z_columns],
    on="park_num",
    how="left",
    validate="many_to_one"
)


# ------------------------------------------------------------
# Model dataset
# ------------------------------------------------------------

model_columns = [
    outcome,
    "park_num",
    "z_physical_access_score",
    "z_log_site_area",
    "z_log_population_density",
    "day_type",
    "time_of_day",
    "season",
    "site_type"
]

model_df = (
    df[model_columns]
    .dropna()
    .copy()
)

print("\n" + "=" * 65)
print("MODEL DATA")
print("=" * 65)

print("Rows available:", len(model_df))
print(
    "Unique parks:",
    model_df["park_num"].nunique()
)

print(
    "Rows removed due to missing model variables:",
    len(df) - len(model_df)
)


# ------------------------------------------------------------
# Reference categories
#
# Explicit reference categories make interpretation stable
# across reruns.
# ------------------------------------------------------------

print("\nDay types:")
print(model_df["day_type"].value_counts())

print("\nTimes of day:")
print(model_df["time_of_day"].value_counts())

print("\nSeasons:")
print(model_df["season"].value_counts())

print("\nSite types:")
print(model_df["site_type"].value_counts())


# ------------------------------------------------------------
# Mixed-effects model
#
# Random intercept:
# one intercept per park
#
# Reference categories:
# weekday
# morning
# winter
# riverfront
# ------------------------------------------------------------

formula = (
    f"{outcome} ~ "
    "z_physical_access_score + "
    'C(day_type, Treatment(reference="weekday")) + '
    'C(time_of_day, Treatment(reference="morning")) + '
    'C(season, Treatment(reference="winter")) + '
    'C(site_type, Treatment(reference="riverfront")) + '
    "z_log_site_area + "
    "z_log_population_density"
)

print("\n" + "=" * 65)
print("MODEL FORMULA")
print("=" * 65)

print(formula)


# ------------------------------------------------------------
# Fit model
# ------------------------------------------------------------

print("\nFitting mixed-effects model...")

with warnings.catch_warnings(record=True) as caught_warnings:

    warnings.simplefilter("always")

    model = smf.mixedlm(
        formula=formula,
        data=model_df,
        groups=model_df["park_num"],
        re_formula="1"
    )

    result = model.fit(
        method="lbfgs",
        reml=True,
        maxiter=2000
    )


# ------------------------------------------------------------
# Print results
# ------------------------------------------------------------

print("\n" + "=" * 65)
print("MODEL 1: PHYSICAL ACCESSIBILITY")
print("=" * 65)

print(result.summary())

print("\nConverged:")
print(result.converged)


# ------------------------------------------------------------
# Warnings
# ------------------------------------------------------------

print("\nModel warnings:")

if caught_warnings:

    for warning in caught_warnings:
        print("-", warning.message)

else:
    print("None")


# ------------------------------------------------------------
# Variance components
# ------------------------------------------------------------

random_intercept_variance = float(
    result.cov_re.iloc[0, 0]
)

residual_variance = float(
    result.scale
)

icc = (
    random_intercept_variance
    /
    (
        random_intercept_variance
        + residual_variance
    )
)

print("\n" + "=" * 65)
print("VARIANCE COMPONENTS")
print("=" * 65)

print(
    "Park random-intercept variance:",
    random_intercept_variance
)

print(
    "Residual variance:",
    residual_variance
)

print(
    "ICC:",
    icc
)


# ------------------------------------------------------------
# Coefficient table
# ------------------------------------------------------------

conf = result.conf_int()

coefficients = pd.DataFrame({
    "term": result.params.index,
    "estimate": result.params.values,
    "std_error": result.bse.values,
    "p_value": result.pvalues.values,
    "ci_lower": conf.iloc[:, 0].values,
    "ci_upper": conf.iloc[:, 1].values
})

COEF_FILE = (
    OUTPUT_DIR
    / "physical_accessibility_coefficients.csv"
)

coefficients.to_csv(
    COEF_FILE,
    index=False
)


# ------------------------------------------------------------
# Model information
# ------------------------------------------------------------

model_info = pd.DataFrame(
    {
        "metric": [
            "n_observations",
            "n_parks",
            "converged",
            "log_likelihood",
            "aic",
            "bic",
            "random_intercept_variance",
            "residual_variance",
            "icc"
        ],
        "value": [
            result.nobs,
            model_df["park_num"].nunique(),
            result.converged,
            result.llf,
            result.aic,
            result.bic,
            random_intercept_variance,
            residual_variance,
            icc
        ]
    }
)

INFO_FILE = (
    OUTPUT_DIR
    / "physical_accessibility_model_info.csv"
)

model_info.to_csv(
    INFO_FILE,
    index=False
)


# ------------------------------------------------------------
# Save complete text summary
# ------------------------------------------------------------

SUMMARY_FILE = (
    OUTPUT_DIR
    / "physical_accessibility_model_summary.txt"
)

with open(
    SUMMARY_FILE,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        result.summary().as_text()
    )


# ------------------------------------------------------------
# Done
# ------------------------------------------------------------

print("\n" + "=" * 65)
print("OUTPUTS")
print("=" * 65)

print("\nCoefficient table:")
print(COEF_FILE)

print("\nModel information:")
print(INFO_FILE)

print("\nFull model summary:")
print(SUMMARY_FILE)

print("\nDone.")