from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


# ============================================================
# 14_run_main_accessibility_models.py
#
# Purpose:
# Run the four main mixed-effects models:
#
# 1. Physical accessibility
# 2. Visual accessibility
# 3. Haptic accessibility
# 4. Multidimensional accessibility
#
# Main specification:
# - BFGS optimizer
# - original site-type categories
# - Level 1 controls:
#     weekday/weekend
#     time of day
#     season
# - Level 2 controls:
#     site type
#     log site area
#     log population density
# - random intercept for park_num
# ============================================================


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

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
    / "main_models"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------

df = pd.read_csv(
    INPUT_FILE,
    dtype={"park_num": str}
)

OUTCOME = "site_activity_index"

print("\nDataset loaded.")
print("Rows:", len(df))
print("Unique parks:", df["park_num"].nunique())


# ------------------------------------------------------------
# Transform Level-2 controls
# ------------------------------------------------------------

df["log_site_area"] = np.log(
    df["site_area_m2"]
)

df["log_population_density"] = np.log1p(
    df["population_density_km2"]
)


# ------------------------------------------------------------
# Standardize continuous Level-2 variables at PARK level
# ------------------------------------------------------------

park_level = (
    df[
        [
            "park_num",
            "physical_access_score",
            "visible_water_ratio",
            "shoreline_length_to_perimeter_ratio",
            "multidimensional_access_score",
            "log_site_area",
            "log_population_density"
        ]
    ]
    .drop_duplicates("park_num")
    .copy()
)

continuous_vars = [
    "physical_access_score",
    "visible_water_ratio",
    "shoreline_length_to_perimeter_ratio",
    "multidimensional_access_score",
    "log_site_area",
    "log_population_density"
]

print("\nPark-level standardization:")

for variable in continuous_vars:

    mean = park_level[variable].mean()
    sd = park_level[variable].std()

    if sd == 0:
        raise ValueError(
            f"{variable} has zero standard deviation."
        )

    park_level[f"z_{variable}"] = (
        park_level[variable] - mean
    ) / sd

    print(
        f"{variable}: "
        f"mean = {mean:.6f}, "
        f"SD = {sd:.6f}"
    )


# ------------------------------------------------------------
# Join standardized variables back to repeated observations
# ------------------------------------------------------------

z_columns = [
    "park_num"
] + [
    f"z_{x}"
    for x in continuous_vars
]

df = df.merge(
    park_level[z_columns],
    on="park_num",
    how="left",
    validate="many_to_one"
)


# ------------------------------------------------------------
# Predictor mapping
# ------------------------------------------------------------

accessibility_predictors = {

    "physical":
        "z_physical_access_score",

    "visual":
        "z_visible_water_ratio",

    "haptic":
        "z_shoreline_length_to_perimeter_ratio",

    "multidimensional":
        "z_multidimensional_access_score"
}


# ------------------------------------------------------------
# Shared controls
# ------------------------------------------------------------

shared_controls = (
    'C(day_type, Treatment(reference="weekday")) + '
    'C(time_of_day, Treatment(reference="morning")) + '
    'C(season, Treatment(reference="winter")) + '
    'C(site_type, Treatment(reference="riverfront")) + '
    "z_log_site_area + "
    "z_log_population_density"
)


# ------------------------------------------------------------
# Fit function
# ------------------------------------------------------------

def fit_access_model(model_name, predictor):

    print("\n" + "=" * 80)
    print(f"{model_name.upper()} ACCESSIBILITY MODEL")
    print("=" * 80)

    formula = (
        f"{OUTCOME} ~ "
        f"{predictor} + "
        f"{shared_controls}"
    )

    print("\nFormula:")
    print(formula)

    model_columns = [
        OUTCOME,
        "park_num",
        predictor,
        "day_type",
        "time_of_day",
        "season",
        "site_type",
        "z_log_site_area",
        "z_log_population_density"
    ]

    model_df = (
        df[model_columns]
        .dropna()
        .copy()
    )

    print("\nRows:", len(model_df))
    print(
        "Unique parks:",
        model_df["park_num"].nunique()
    )

    print(
        "Rows removed:",
        len(df) - len(model_df)
    )


    # --------------------------------------------------------
    # Fit mixed model
    # --------------------------------------------------------

    with warnings.catch_warnings(record=True) as caught:

        warnings.simplefilter("always")

        model = smf.mixedlm(
            formula=formula,
            data=model_df,
            groups=model_df["park_num"],
            re_formula="1"
        )

        result = model.fit(
            method="bfgs",
            reml=True,
            maxiter=5000,
            disp=False
        )


    # --------------------------------------------------------
    # Variance components
    # --------------------------------------------------------

    random_var = float(
        result.cov_re.iloc[0, 0]
    )

    residual_var = float(
        result.scale
    )

    icc = (
        random_var
        /
        (
            random_var
            + residual_var
        )
    )


    # --------------------------------------------------------
    # Main accessibility coefficient
    # --------------------------------------------------------

    beta = result.params[predictor]
    se = result.bse[predictor]
    p_value = result.pvalues[predictor]

    ci = result.conf_int()

    ci_low = ci.loc[predictor].iloc[0]
    ci_high = ci.loc[predictor].iloc[1]


    # --------------------------------------------------------
    # Print key results
    # --------------------------------------------------------

    print("\nConverged:")
    print(result.converged)

    print("\nMain accessibility predictor:")
    print("Beta:", beta)
    print("SE:", se)
    print("p-value:", p_value)
    print("95% CI:", ci_low, ci_high)

    print("\nRandom-intercept variance:")
    print(random_var)

    print("\nResidual variance:")
    print(residual_var)

    print("\nICC:")
    print(icc)

    print("\nLog likelihood:")
    print(result.llf)

    print("\nWarnings:")
    print(len(caught))

    if caught:
        for warning in caught:
            print("-", warning.message)


    # --------------------------------------------------------
    # Full coefficient table
    # --------------------------------------------------------

    coef_table = pd.DataFrame(
        {
            "term": result.params.index,
            "estimate": result.params.values,
            "std_error": result.bse.values,
            "p_value": result.pvalues.values,
            "ci_lower": ci.iloc[:, 0].values,
            "ci_upper": ci.iloc[:, 1].values
        }
    )

    coef_file = (
        OUTPUT_DIR
        / f"{model_name}_model_coefficients.csv"
    )

    coef_table.to_csv(
        coef_file,
        index=False
    )


    # --------------------------------------------------------
    # Text summary
    # --------------------------------------------------------

    summary_file = (
        OUTPUT_DIR
        / f"{model_name}_model_summary.txt"
    )

    with open(
        summary_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            result.summary().as_text()
        )


    # --------------------------------------------------------
    # Return comparison row
    # --------------------------------------------------------

    return {
        "model": model_name,
        "predictor": predictor,
        "converged": result.converged,
        "n_obs": result.nobs,
        "n_parks": model_df["park_num"].nunique(),
        "beta": beta,
        "std_error": se,
        "ci_lower": ci_low,
        "ci_upper": ci_high,
        "p_value": p_value,
        "random_intercept_variance": random_var,
        "residual_variance": residual_var,
        "icc": icc,
        "log_likelihood": result.llf,
        "warning_count": len(caught)
    }


# ------------------------------------------------------------
# Run all four main models
# ------------------------------------------------------------

results = []

for model_name, predictor in accessibility_predictors.items():

    try:

        row = fit_access_model(
            model_name,
            predictor
        )

        results.append(row)

    except Exception as error:

        print(
            f"\n{model_name.upper()} MODEL FAILED:"
        )

        print(error)

        results.append(
            {
                "model": model_name,
                "predictor": predictor,
                "converged": False,
                "n_obs": np.nan,
                "n_parks": np.nan,
                "beta": np.nan,
                "std_error": np.nan,
                "ci_lower": np.nan,
                "ci_upper": np.nan,
                "p_value": np.nan,
                "random_intercept_variance": np.nan,
                "residual_variance": np.nan,
                "icc": np.nan,
                "log_likelihood": np.nan,
                "warning_count": np.nan
            }
        )


# ------------------------------------------------------------
# Main model comparison
# ------------------------------------------------------------

comparison = pd.DataFrame(
    results
)

print("\n" + "=" * 100)
print("MAIN ACCESSIBILITY MODEL COMPARISON")
print("=" * 100)

print(
    comparison.to_string(
        index=False
    )
)


# ------------------------------------------------------------
# Save comparison
# ------------------------------------------------------------

COMPARISON_FILE = (
    OUTPUT_DIR
    / "main_accessibility_model_comparison.csv"
)

comparison.to_csv(
    COMPARISON_FILE,
    index=False
)

print("\nComparison saved:")
print(COMPARISON_FILE)

print("\nDone.")