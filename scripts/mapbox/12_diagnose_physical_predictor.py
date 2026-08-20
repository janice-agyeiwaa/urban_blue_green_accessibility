from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


# ============================================================
# 12_diagnose_physical_predictor.py
#
# Purpose:
# 1. Check park-level relationships involving physical access
# 2. Fit the same physical-access mixed model with multiple
#    optimizers
# 3. Compare convergence, likelihood, random-effect variance,
#    ICC, and warnings
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

print("\nDataset loaded.")
print("Rows:", len(df))
print("Unique parks:", df["park_num"].nunique())


# ------------------------------------------------------------
# Transform controls
# ------------------------------------------------------------

df["log_site_area"] = np.log(
    df["site_area_m2"]
)

df["log_population_density"] = np.log1p(
    df["population_density_km2"]
)


# ------------------------------------------------------------
# Build one-row-per-park table
# ------------------------------------------------------------

park_level = (
    df.groupby(
        "park_num",
        as_index=False
    )
    .agg(
        site_name=("site_name", "first"),
        site_type=("site_type", "first"),
        physical_access_score=("physical_access_score", "first"),
        site_area_m2=("site_area_m2", "first"),
        log_site_area=("log_site_area", "first"),
        population_density_km2=("population_density_km2", "first"),
        log_population_density=("log_population_density", "first"),
        mean_activity=(OUTCOME, "mean"),
        median_activity=(OUTCOME, "median"),
        activity_records=(OUTCOME, "size")
    )
)

print("\nPark-level table:")
print("Rows:", len(park_level))


# ------------------------------------------------------------
# Standardize continuous Level-2 variables at park level
# ------------------------------------------------------------

continuous = [
    "physical_access_score",
    "log_site_area",
    "log_population_density"
]

for variable in continuous:

    mean = park_level[variable].mean()
    sd = park_level[variable].std()

    park_level[f"z_{variable}"] = (
        park_level[variable] - mean
    ) / sd

    print(
        f"\n{variable}: "
        f"mean = {mean:.6f}, "
        f"SD = {sd:.6f}"
    )


# ------------------------------------------------------------
# Join standardized values back to repeated observations
# ------------------------------------------------------------

df = df.merge(
    park_level[
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
# PART 1: park-level correlations
# ------------------------------------------------------------

print("\n" + "=" * 70)
print("PARK-LEVEL CONTINUOUS CORRELATIONS")
print("=" * 70)

correlation_vars = [
    "mean_activity",
    "physical_access_score",
    "log_site_area",
    "log_population_density"
]

corr = (
    park_level[
        correlation_vars
    ]
    .corr(
        method="pearson"
    )
)

print("\nPearson correlation matrix:\n")
print(
    corr.round(3).to_string()
)


# ------------------------------------------------------------
# Specific correlations with physical access
# ------------------------------------------------------------

print("\nPhysical access correlations:")

for variable in [
    "mean_activity",
    "log_site_area",
    "log_population_density"
]:

    r = (
        park_level[
            "physical_access_score"
        ]
        .corr(
            park_level[variable]
        )
    )

    print(
        f"physical_access_score vs {variable}: "
        f"r = {r:.4f}"
    )


# ------------------------------------------------------------
# Site-type summaries
# ------------------------------------------------------------

print("\n" + "=" * 70)
print("PHYSICAL ACCESS BY SITE TYPE")
print("=" * 70)

site_type_summary = (
    park_level
    .groupby(
        "site_type"
    )
    .agg(
        n_parks=("park_num", "size"),
        mean_physical_access=(
            "physical_access_score",
            "mean"
        ),
        sd_physical_access=(
            "physical_access_score",
            "std"
        ),
        mean_activity=(
            "mean_activity",
            "mean"
        )
    )
    .reset_index()
)

print(
    site_type_summary.to_string(
        index=False
    )
)


# ------------------------------------------------------------
# Identify physical-access extremes
# ------------------------------------------------------------

print("\nLowest physical-access parks:")

print(
    park_level[
        [
            "park_num",
            "site_name",
            "site_type",
            "physical_access_score",
            "mean_activity"
        ]
    ]
    .sort_values(
        "physical_access_score"
    )
    .head(10)
    .to_string(
        index=False
    )
)

print("\nHighest physical-access parks:")

print(
    park_level[
        [
            "park_num",
            "site_name",
            "site_type",
            "physical_access_score",
            "mean_activity"
        ]
    ]
    .sort_values(
        "physical_access_score",
        ascending=False
    )
    .head(10)
    .to_string(
        index=False
    )
)


# ------------------------------------------------------------
# PART 2: fit same mixed model with multiple optimizers
# ------------------------------------------------------------

formula = (
    f"{OUTCOME} ~ "
    "z_physical_access_score + "
    'C(day_type, Treatment(reference="weekday")) + '
    'C(time_of_day, Treatment(reference="morning")) + '
    'C(season, Treatment(reference="winter")) + '
    'C(site_type, Treatment(reference="riverfront")) + '
    "z_log_site_area + "
    "z_log_population_density"
)

print("\n" + "=" * 70)
print("PHYSICAL-ACCESS MODEL FORMULA")
print("=" * 70)

print(formula)


# ------------------------------------------------------------
# Fit function
# ------------------------------------------------------------

def fit_with_optimizer(optimizer):

    print("\n" + "-" * 70)
    print(f"OPTIMIZER: {optimizer}")
    print("-" * 70)

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
            method=optimizer,
            maxiter=5000,
            disp=False
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


    print("Converged:", result.converged)

    print(
        "Random-intercept variance:",
        random_variance
    )

    print(
        "Residual variance:",
        residual_variance
    )

    print(
        "ICC:",
        icc
    )

    print(
        "Log likelihood:",
        result.llf
    )

    print(
        "Warnings:",
        len(caught)
    )

    if caught:

        for w in caught:
            print("-", str(w.message))


    # Physical-access coefficient

    term = "z_physical_access_score"

    if term in result.params.index:

        print(
            "\nPhysical-access coefficient:",
            result.params[term]
        )

        print(
            "Physical-access SE:",
            result.bse[term]
        )

        print(
            "Physical-access p-value:",
            result.pvalues[term]
        )


    # Save summary

    summary_path = (
        OUTPUT_DIR
        / f"physical_access_{optimizer}_summary.txt"
    )

    with open(
        summary_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            result.summary().as_text()
        )


    return {
        "optimizer": optimizer,
        "converged": result.converged,
        "random_intercept_variance": random_variance,
        "residual_variance": residual_variance,
        "icc": icc,
        "log_likelihood": result.llf,
        "physical_coefficient": (
            result.params.get(
                "z_physical_access_score",
                np.nan
            )
        ),
        "physical_se": (
            result.bse.get(
                "z_physical_access_score",
                np.nan
            )
        ),
        "physical_p_value": (
            result.pvalues.get(
                "z_physical_access_score",
                np.nan
            )
        ),
        "warning_count": len(caught)
    }


# ------------------------------------------------------------
# Optimizers to test
# ------------------------------------------------------------

optimizers = [
    "lbfgs",
    "bfgs",
    "powell",
    "cg"
]

optimizer_results = []


for optimizer in optimizers:

    try:

        result_row = fit_with_optimizer(
            optimizer
        )

        optimizer_results.append(
            result_row
        )

    except Exception as error:

        print(
            f"\n{optimizer} FAILED:"
        )

        print(error)

        optimizer_results.append(
            {
                "optimizer": optimizer,
                "converged": False,
                "random_intercept_variance": np.nan,
                "residual_variance": np.nan,
                "icc": np.nan,
                "log_likelihood": np.nan,
                "physical_coefficient": np.nan,
                "physical_se": np.nan,
                "physical_p_value": np.nan,
                "warning_count": np.nan
            }
        )


# ------------------------------------------------------------
# Optimizer comparison table
# ------------------------------------------------------------

optimizer_comparison = pd.DataFrame(
    optimizer_results
)

print("\n" + "=" * 70)
print("OPTIMIZER COMPARISON")
print("=" * 70)

print(
    optimizer_comparison.to_string(
        index=False
    )
)


# ------------------------------------------------------------
# Save outputs
# ------------------------------------------------------------

CORR_FILE = (
    OUTPUT_DIR
    / "physical_predictor_correlations.csv"
)

corr.to_csv(
    CORR_FILE
)

SITE_TYPE_FILE = (
    OUTPUT_DIR
    / "physical_access_by_site_type.csv"
)

site_type_summary.to_csv(
    SITE_TYPE_FILE,
    index=False
)

OPTIMIZER_FILE = (
    OUTPUT_DIR
    / "physical_access_optimizer_comparison.csv"
)

optimizer_comparison.to_csv(
    OPTIMIZER_FILE,
    index=False
)

PARK_LEVEL_FILE = (
    OUTPUT_DIR
    / "physical_access_park_level_diagnostics.csv"
)

park_level.to_csv(
    PARK_LEVEL_FILE,
    index=False
)


print("\n" + "=" * 70)
print("OUTPUTS")
print("=" * 70)

print("\nCorrelation matrix:")
print(CORR_FILE)

print("\nSite-type summary:")
print(SITE_TYPE_FILE)

print("\nOptimizer comparison:")
print(OPTIMIZER_FILE)

print("\nPark-level diagnostics:")
print(PARK_LEVEL_FILE)

print("\nDone.")