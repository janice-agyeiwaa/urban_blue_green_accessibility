from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


# ============================================================
# 11_diagnose_mixed_model.py
#
# Diagnose the random-intercept structure before proceeding
# with the final accessibility models.
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
    / "diagnostics"
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

print("\nDataset:")
print("Rows:", len(df))
print("Parks:", df["park_num"].nunique())


# ------------------------------------------------------------
# Transform site-level controls
# ------------------------------------------------------------

df["log_site_area"] = np.log(
    df["site_area_m2"]
)

df["log_population_density"] = np.log1p(
    df["population_density_km2"]
)


# ------------------------------------------------------------
# Standardize SITE-LEVEL variables using one row per park
# ------------------------------------------------------------

park_df = (
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

continuous = [
    "physical_access_score",
    "log_site_area",
    "log_population_density"
]

for variable in continuous:

    mean = park_df[variable].mean()
    sd = park_df[variable].std()

    park_df[f"z_{variable}"] = (
        park_df[variable] - mean
    ) / sd


df = df.merge(
    park_df[
        [
            "park_num",
            "z_physical_access_score",
            "z_log_site_area",
            "z_log_population_density"
        ]
    ],
    on="park_num",
    how="left",
    validate="many_to_one"
)


# ------------------------------------------------------------
# Define progressive models
# ------------------------------------------------------------

models = {

    # --------------------------------
    # Model 0:
    # Does activity cluster by park?
    # --------------------------------

    "M0_null":
        f"{OUTCOME} ~ 1",

    # --------------------------------
    # Model 1:
    # Add temporal controls
    # --------------------------------

    "M1_temporal":
        (
            f"{OUTCOME} ~ "
            'C(day_type, Treatment(reference="weekday")) + '
            'C(time_of_day, Treatment(reference="morning")) + '
            'C(season, Treatment(reference="winter"))'
        ),

    # --------------------------------
    # Model 2:
    # Add site-level controls
    # --------------------------------

    "M2_site_controls":
        (
            f"{OUTCOME} ~ "
            'C(day_type, Treatment(reference="weekday")) + '
            'C(time_of_day, Treatment(reference="morning")) + '
            'C(season, Treatment(reference="winter")) + '
            'C(site_type, Treatment(reference="riverfront")) + '
            "z_log_site_area + "
            "z_log_population_density"
        ),

    # --------------------------------
    # Model 3:
    # Add physical accessibility
    # --------------------------------

    "M3_physical":
        (
            f"{OUTCOME} ~ "
            "z_physical_access_score + "
            'C(day_type, Treatment(reference="weekday")) + '
            'C(time_of_day, Treatment(reference="morning")) + '
            'C(season, Treatment(reference="winter")) + '
            'C(site_type, Treatment(reference="riverfront")) + '
            "z_log_site_area + "
            "z_log_population_density"
        )
}


# ------------------------------------------------------------
# Function to fit one model
# ------------------------------------------------------------

def fit_model(name, formula):

    print("\n")
    print("=" * 70)
    print(name)
    print("=" * 70)

    print("\nFormula:")
    print(formula)

    with warnings.catch_warnings(record=True) as caught:

        warnings.simplefilter("always")

        model = smf.mixedlm(
            formula=formula,
            data=df,
            groups=df["park_num"],
            re_formula="1"
        )

        result = model.fit(
            reml=True,
            method="lbfgs",
            maxiter=2000
        )

    random_variance = float(
        result.cov_re.iloc[0, 0]
    )

    residual_variance = float(
        result.scale
    )

    total_variance = (
        random_variance
        + residual_variance
    )

    if total_variance > 0:

        icc = (
            random_variance
            / total_variance
        )

    else:
        icc = np.nan


    print("\nConverged:")
    print(result.converged)

    print("\nPark random-intercept variance:")
    print(random_variance)

    print("\nResidual variance:")
    print(residual_variance)

    print("\nICC:")
    print(icc)

    print("\nLog likelihood:")
    print(result.llf)

    print("\nWarnings:")

    if caught:

        for w in caught:
            print("-", str(w.message))

    else:
        print("None")


    # Save complete model summary

    summary_file = (
        OUTPUT_DIR
        / f"{name}_summary.txt"
    )

    with open(
        summary_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            result.summary().as_text()
        )


    return {
        "model": name,
        "converged": result.converged,
        "n_obs": result.nobs,
        "n_parks": df["park_num"].nunique(),
        "random_intercept_variance": random_variance,
        "residual_variance": residual_variance,
        "icc": icc,
        "log_likelihood": result.llf,
        "warning_count": len(caught)
    }


# ------------------------------------------------------------
# Fit models
# ------------------------------------------------------------

results = []

for name, formula in models.items():

    try:

        model_result = fit_model(
            name,
            formula
        )

        results.append(
            model_result
        )

    except Exception as error:

        print("\nMODEL FAILED:")
        print(error)

        results.append(
            {
                "model": name,
                "converged": False,
                "n_obs": np.nan,
                "n_parks": np.nan,
                "random_intercept_variance": np.nan,
                "residual_variance": np.nan,
                "icc": np.nan,
                "log_likelihood": np.nan,
                "warning_count": np.nan
            }
        )


# ------------------------------------------------------------
# Comparison table
# ------------------------------------------------------------

comparison = pd.DataFrame(
    results
)

print("\n")
print("=" * 70)
print("MODEL COMPARISON")
print("=" * 70)

print(
    comparison.to_string(
        index=False
    )
)


# ------------------------------------------------------------
# Save comparison
# ------------------------------------------------------------

OUTPUT_FILE = (
    OUTPUT_DIR
    / "mixed_model_diagnostic_comparison.csv"
)

comparison.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nSaved:")
print(OUTPUT_FILE)

print("\nDone.")