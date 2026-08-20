from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


# ============================================================
# 13_compare_site_type_specifications.py
#
# Compare physical-access mixed models using:
#
# 1. Original site-type categories
# 2. No site-type control
# 3. Collapsed site-type categories
#
# Models are fitted with ML (REML = False) because their
# fixed-effect structures differ.
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
    / "site_type_sensitivity"
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
# Transform continuous controls
# ------------------------------------------------------------

df["log_site_area"] = np.log(
    df["site_area_m2"]
)

df["log_population_density"] = np.log1p(
    df["population_density_km2"]
)


# ------------------------------------------------------------
# Standardize site-level continuous variables
#
# Use one row per park so parks with more Mapbox records
# do not receive extra weight.
# ------------------------------------------------------------

park_level = (
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

    mean = park_level[variable].mean()
    sd = park_level[variable].std()

    park_level[f"z_{variable}"] = (
        park_level[variable] - mean
    ) / sd


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
# Create collapsed site type
#
# Broader category:
#
# coastal waterfront without beach
# coastal promenade
# beach + coastal promenade
#
#            ↓
#
# coastal waterfront
# ------------------------------------------------------------

coastal_types = [
    "coastal waterfront without beach",
    "coastal promenade",
    "beach + coastal promenade"
]

df["site_type_collapsed"] = np.where(
    df["site_type"].isin(coastal_types),
    "coastal waterfront",
    df["site_type"]
)


# ------------------------------------------------------------
# Check PARK-level site-type counts
# ------------------------------------------------------------

park_types = (
    df[
        [
            "park_num",
            "site_type",
            "site_type_collapsed"
        ]
    ]
    .drop_duplicates("park_num")
)

print("\n" + "=" * 70)
print("ORIGINAL SITE-TYPE COUNTS")
print("=" * 70)

print(
    park_types[
        "site_type"
    ].value_counts()
)

print("\n" + "=" * 70)
print("COLLAPSED SITE-TYPE COUNTS")
print("=" * 70)

print(
    park_types[
        "site_type_collapsed"
    ].value_counts()
)


# ------------------------------------------------------------
# Shared model components
# ------------------------------------------------------------

temporal_controls = (
    'C(day_type, Treatment(reference="weekday")) + '
    'C(time_of_day, Treatment(reference="morning")) + '
    'C(season, Treatment(reference="winter"))'
)

continuous_controls = (
    "z_log_site_area + "
    "z_log_population_density"
)


# ------------------------------------------------------------
# Three model specifications
# ------------------------------------------------------------

formulas = {

    # --------------------------------------------------------
    # A. Original six-category site type
    # --------------------------------------------------------

    "original_site_type": (
        f"{OUTCOME} ~ "
        "z_physical_access_score + "
        f"{temporal_controls} + "
        'C(site_type, Treatment(reference="riverfront")) + '
        f"{continuous_controls}"
    ),

    # --------------------------------------------------------
    # B. No site-type control
    # --------------------------------------------------------

    "no_site_type": (
        f"{OUTCOME} ~ "
        "z_physical_access_score + "
        f"{temporal_controls} + "
        f"{continuous_controls}"
    ),

    # --------------------------------------------------------
    # C. Broader site-type grouping
    # --------------------------------------------------------

    "collapsed_site_type": (
        f"{OUTCOME} ~ "
        "z_physical_access_score + "
        f"{temporal_controls} + "
        'C(site_type_collapsed, Treatment(reference="riverfront")) + '
        f"{continuous_controls}"
    )
}


# ------------------------------------------------------------
# Fit function
# ------------------------------------------------------------

def fit_model(name, formula):

    print("\n" + "=" * 70)
    print(name.upper())
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

        # IMPORTANT:
        # ML rather than REML because fixed-effect structures
        # differ across these three models.
        result = model.fit(
            reml=False,
            method="bfgs",
            maxiter=5000,
            disp=False
        )

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

    physical_term = (
        "z_physical_access_score"
    )

    physical_beta = (
        result.params[
            physical_term
        ]
    )

    physical_se = (
        result.bse[
            physical_term
        ]
    )

    physical_p = (
        result.pvalues[
            physical_term
        ]
    )

    ci = result.conf_int()

    physical_ci_low = (
        ci.loc[
            physical_term
        ].iloc[0]
    )

    physical_ci_high = (
        ci.loc[
            physical_term
        ].iloc[1]
    )


    print("\nConverged:")
    print(result.converged)

    print("\nPhysical accessibility:")
    print(
        "Beta:",
        physical_beta
    )

    print(
        "SE:",
        physical_se
    )

    print(
        "p:",
        physical_p
    )

    print(
        "95% CI:",
        physical_ci_low,
        physical_ci_high
    )

    print("\nRandom-intercept variance:")
    print(random_var)

    print("\nICC:")
    print(icc)

    print("\nLog likelihood:")
    print(result.llf)

    print("\nAIC:")
    print(result.aic)

    print("\nBIC:")
    print(result.bic)

    print("\nWarnings:")
    print(len(caught))

    if caught:

        for warning in caught:
            print(
                "-",
                warning.message
            )


    # --------------------------------------------------------
    # Save full model summary
    # --------------------------------------------------------

    summary_file = (
        OUTPUT_DIR
        / f"{name}_summary.txt"
    )

    with open(
        summary_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            result.summary().as_text()
        )


    return {
        "model": name,
        "converged": result.converged,
        "n_obs": result.nobs,
        "n_parks": df["park_num"].nunique(),

        "physical_beta": physical_beta,
        "physical_se": physical_se,
        "physical_ci_low": physical_ci_low,
        "physical_ci_high": physical_ci_high,
        "physical_p": physical_p,

        "random_intercept_variance": random_var,
        "residual_variance": residual_var,
        "icc": icc,

        "log_likelihood": result.llf,
        "aic": result.aic,
        "bic": result.bic,

        "warning_count": len(caught)
    }


# ------------------------------------------------------------
# Fit all three
# ------------------------------------------------------------

results = []

for name, formula in formulas.items():

    try:

        results.append(
            fit_model(
                name,
                formula
            )
        )

    except Exception as error:

        print(
            f"\n{name} FAILED:"
        )

        print(error)

        results.append(
            {
                "model": name,
                "converged": False
            }
        )


# ------------------------------------------------------------
# Comparison table
# ------------------------------------------------------------

comparison = pd.DataFrame(
    results
)

print("\n" + "=" * 90)
print("SITE-TYPE SPECIFICATION COMPARISON")
print("=" * 90)

columns_to_show = [
    "model",
    "converged",
    "physical_beta",
    "physical_se",
    "physical_ci_low",
    "physical_ci_high",
    "physical_p",
    "icc",
    "log_likelihood",
    "aic",
    "bic",
    "warning_count"
]

print(
    comparison[
        columns_to_show
    ].to_string(
        index=False
    )
)


# ------------------------------------------------------------
# Quantify change in physical-access coefficient
# ------------------------------------------------------------

if (
    "physical_beta"
    in comparison.columns
):

    base_row = comparison[
        comparison["model"]
        == "original_site_type"
    ]

    if not base_row.empty:

        base_beta = (
            base_row[
                "physical_beta"
            ].iloc[0]
        )

        comparison[
            "physical_beta_change_from_original"
        ] = (
            comparison["physical_beta"]
            - base_beta
        )

        comparison[
            "physical_beta_pct_change"
        ] = (
            (
                comparison["physical_beta"]
                - base_beta
            )
            / abs(base_beta)
            * 100
        )


# ------------------------------------------------------------
# Save comparison
# ------------------------------------------------------------

OUTPUT_FILE = (
    OUTPUT_DIR
    / "site_type_specification_comparison.csv"
)

comparison.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nSaved comparison:")
print(OUTPUT_FILE)

print("\nDone.")