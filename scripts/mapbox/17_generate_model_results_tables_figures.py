from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 17_generate_model_results_tables_figures.py
#
# Purpose:
# Create publication-ready tables and figures from the
# completed Mapbox mixed-effects model outputs.
#
# Outputs:
# 1. Main four-model coefficient table
# 2. Main accessibility coefficient figure
# 3. Main vs >=90% coverage coefficient figure
# 4. Coverage sensitivity comparison table
# 5. Site-type sensitivity comparison table
# ============================================================


# ------------------------------------------------------------
# Project paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

MAIN_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "mapbox"
    / "models"
    / "main_models"
)

SENS90_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "mapbox"
    / "models"
    / "sensitivity_90pct"
)

SITE_SENS_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "mapbox"
    / "models"
    / "site_type_sensitivity"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "mapbox"
    / "model_results"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------------
# Input model files
# ------------------------------------------------------------

main_coef_files = {
    "Physical": MAIN_DIR / "physical_model_coefficients.csv",
    "Visual": MAIN_DIR / "visual_model_coefficients.csv",
    "Haptic": MAIN_DIR / "haptic_model_coefficients.csv",
    "Multidimensional": MAIN_DIR / "multidimensional_model_coefficients.csv",
}

main_comparison_file = (
    MAIN_DIR
    / "main_accessibility_model_comparison.csv"
)

sens90_comparison_file = (
    SENS90_DIR
    / "sensitivity_90pct_model_comparison.csv"
)

site_type_sensitivity_file = (
    SITE_SENS_DIR
    / "site_type_specification_comparison.csv"
)


# ------------------------------------------------------------
# Check required files
# ------------------------------------------------------------

all_required_files = (
    list(main_coef_files.values())
    + [
        main_comparison_file,
        sens90_comparison_file,
        site_type_sensitivity_file
    ]
)

missing_files = [
    file
    for file in all_required_files
    if not file.exists()
]

if missing_files:

    print("\nMissing files:")

    for file in missing_files:
        print(file)

    raise FileNotFoundError(
        "One or more required model-output files are missing."
    )


# ------------------------------------------------------------
# Friendly term labels
# ------------------------------------------------------------

def clean_term(term):

    mapping = {

        "Intercept":
            "Intercept",

        "z_physical_access_score":
            "Physical accessibility",

        "z_visible_water_ratio":
            "Visual accessibility",

        "z_shoreline_length_to_perimeter_ratio":
            "Haptic accessibility",

        "z_multidimensional_access_score":
            "Multidimensional accessibility",

        'C(day_type, Treatment(reference="weekday"))[T.weekend]':
            "Weekend (ref: weekday)",

        'C(time_of_day, Treatment(reference="morning"))[T.afternoon]':
            "Afternoon (ref: morning)",

        'C(time_of_day, Treatment(reference="morning"))[T.evening]':
            "Evening (ref: morning)",

        'C(season, Treatment(reference="winter"))[T.spring]':
            "Spring (ref: winter)",

        'C(season, Treatment(reference="winter"))[T.summer]':
            "Summer (ref: winter)",

        'C(season, Treatment(reference="winter"))[T.fall]':
            "Fall (ref: winter)",

        'C(site_type, Treatment(reference="riverfront"))[T.beach]':
            "Beach (ref: riverfront)",

        'C(site_type, Treatment(reference="riverfront"))[T.beach + coastal promenade]':
            "Beach + coastal promenade (ref: riverfront)",

        'C(site_type, Treatment(reference="riverfront"))[T.coastal promenade]':
            "Coastal promenade (ref: riverfront)",

        'C(site_type, Treatment(reference="riverfront"))[T.coastal waterfront without beach]':
            "Coastal waterfront without beach (ref: riverfront)",

        'C(site_type, Treatment(reference="riverfront"))[T.lakefront]':
            "Lakefront (ref: riverfront)",

        "z_log_site_area":
            "Log site area",

        "z_log_population_density":
            "Log population density",

        "Group Var":
            "Park random-intercept variance"
    }

    return mapping.get(
        term,
        term
    )


# ------------------------------------------------------------
# Read all main coefficient tables
# ------------------------------------------------------------

main_long = []

for model_name, file in main_coef_files.items():

    temp = pd.read_csv(
        file
    )

    temp["model"] = model_name

    temp["term_label"] = (
        temp["term"]
        .apply(
            clean_term
        )
    )

    main_long.append(
        temp
    )

main_long = pd.concat(
    main_long,
    ignore_index=True
)


# ------------------------------------------------------------
# Save raw combined coefficient table
# ------------------------------------------------------------

RAW_MAIN_FILE = (
    OUTPUT_DIR
    / "main_models_all_coefficients_raw.csv"
)

main_long.to_csv(
    RAW_MAIN_FILE,
    index=False
)


# ------------------------------------------------------------
# Create formatted coefficient strings
# ------------------------------------------------------------

def format_p(p):

    if pd.isna(p):
        return ""

    if p < 0.001:
        return "<0.001"

    return f"{p:.3f}"


def format_effect(row):

    estimate = row["estimate"]

    ci_lower = row["ci_lower"]

    ci_upper = row["ci_upper"]

    p = row["p_value"]

    return (
        f"{estimate:.3f} "
        f"({ci_lower:.3f}, {ci_upper:.3f}); "
        f"p={format_p(p)}"
    )


main_long[
    "formatted_effect"
] = (
    main_long
    .apply(
        format_effect,
        axis=1
    )
)


# ------------------------------------------------------------
# Desired row order
# ------------------------------------------------------------

row_order = [

    "Physical accessibility",
    "Visual accessibility",
    "Haptic accessibility",
    "Multidimensional accessibility",

    "Weekend (ref: weekday)",

    "Afternoon (ref: morning)",
    "Evening (ref: morning)",

    "Spring (ref: winter)",
    "Summer (ref: winter)",
    "Fall (ref: winter)",

    "Beach (ref: riverfront)",
    "Beach + coastal promenade (ref: riverfront)",
    "Coastal promenade (ref: riverfront)",
    "Coastal waterfront without beach (ref: riverfront)",
    "Lakefront (ref: riverfront)",

    "Log site area",
    "Log population density"
]


# ------------------------------------------------------------
# Pivot main table
# ------------------------------------------------------------

main_table = (
    main_long[
        ~main_long[
            "term_label"
        ].isin(
            [
                "Intercept",
                "Park random-intercept variance"
            ]
        )
    ]
    .pivot_table(
        index="term_label",
        columns="model",
        values="formatted_effect",
        aggfunc="first"
    )
    .reindex(
        row_order
    )
    .reset_index()
    .rename(
        columns={
            "term_label": "Predictor"
        }
    )
)


# ------------------------------------------------------------
# Reorder model columns
# ------------------------------------------------------------

desired_model_columns = [
    "Predictor",
    "Physical",
    "Visual",
    "Haptic",
    "Multidimensional"
]

main_table = main_table[
    desired_model_columns
]


# ------------------------------------------------------------
# Save publication table
# ------------------------------------------------------------

MAIN_TABLE_FILE = (
    OUTPUT_DIR
    / "table_main_mixed_models.csv"
)

main_table.to_csv(
    MAIN_TABLE_FILE,
    index=False
)


# ------------------------------------------------------------
# Read main comparison
# ------------------------------------------------------------

main_comp = pd.read_csv(
    main_comparison_file
)

sens90 = pd.read_csv(
    sens90_comparison_file
)


# ------------------------------------------------------------
# Friendly model names
# ------------------------------------------------------------

model_name_map = {
    "physical": "Physical",
    "visual": "Visual",
    "haptic": "Haptic",
    "multidimensional": "Multidimensional"
}

main_comp[
    "model_label"
] = (
    main_comp[
        "model"
    ]
    .map(
        model_name_map
    )
)

sens90[
    "model_label"
] = (
    sens90[
        "model"
    ]
    .map(
        model_name_map
    )
)


# ------------------------------------------------------------
# Table: main model accessibility effects
# ------------------------------------------------------------

main_effects = (
    main_comp[
        [
            "model_label",
            "n_obs",
            "n_parks",
            "beta",
            "std_error",
            "ci_lower",
            "ci_upper",
            "p_value",
            "icc",
            "log_likelihood"
        ]
    ]
    .copy()
)

main_effects = main_effects.rename(
    columns={
        "model_label": "Accessibility",
        "n_obs": "N_observations",
        "n_parks": "N_parks",
        "beta": "Beta",
        "std_error": "SE",
        "ci_lower": "CI_lower",
        "ci_upper": "CI_upper",
        "p_value": "p_value",
        "icc": "ICC",
        "log_likelihood": "Log_likelihood"
    }
)

MAIN_EFFECT_FILE = (
    OUTPUT_DIR
    / "table_main_accessibility_effects.csv"
)

main_effects.to_csv(
    MAIN_EFFECT_FILE,
    index=False
)


# ------------------------------------------------------------
# Figure: main accessibility coefficients
# ------------------------------------------------------------

plot_main = (
    main_comp
    .set_index(
        "model_label"
    )
    .loc[
        [
            "Physical",
            "Visual",
            "Haptic",
            "Multidimensional"
        ]
    ]
    .reset_index()
)

y = np.arange(
    len(
        plot_main
    )
)

x = plot_main[
    "beta"
].to_numpy()

xerr = np.vstack(
    [
        x
        - plot_main[
            "ci_lower"
        ].to_numpy(),

        plot_main[
            "ci_upper"
        ].to_numpy()
        - x
    ]
)

fig, ax = plt.subplots(
    figsize=(
        8,
        5.5
    )
)

ax.errorbar(
    x,
    y,
    xerr=xerr,
    fmt="o",
    capsize=4,
    linewidth=1.3
)

ax.axvline(
    0,
    linestyle="--",
    linewidth=1
)

ax.set_yticks(
    y
)

ax.set_yticklabels(
    plot_main[
        "model_label"
    ]
)

ax.set_xlabel(
    "Standardized accessibility coefficient"
)

ax.set_ylabel(
    "Accessibility dimension"
)

ax.set_title(
    "Association between accessibility and waterfront activity"
)

ax.invert_yaxis()

ax.spines[
    "top"
].set_visible(
    False
)

ax.spines[
    "right"
].set_visible(
    False
)

fig.tight_layout()

MAIN_FIGURE = (
    OUTPUT_DIR
    / "figure_main_accessibility_coefficients.png"
)

fig.savefig(
    MAIN_FIGURE,
    dpi=300,
    bbox_inches="tight"
)

plt.close(
    fig
)


# ------------------------------------------------------------
# Main vs >=90% sensitivity table
# ------------------------------------------------------------

main_sens = main_comp[
    [
        "model_label",
        "beta",
        "std_error",
        "ci_lower",
        "ci_upper",
        "p_value",
        "icc",
        "n_parks",
        "n_obs"
    ]
].copy()

main_sens[
    "sample"
] = "Main sample"

sens90_table = sens90[
    [
        "model_label",
        "beta",
        "std_error",
        "ci_lower",
        "ci_upper",
        "p_value",
        "icc",
        "n_parks",
        "n_obs"
    ]
].copy()

sens90_table[
    "sample"
] = ">=90% coverage"

coverage_comparison = pd.concat(
    [
        main_sens,
        sens90_table
    ],
    ignore_index=True
)

coverage_comparison = (
    coverage_comparison
    .rename(
        columns={
            "model_label": "Accessibility",
            "beta": "Beta",
            "std_error": "SE",
            "ci_lower": "CI_lower",
            "ci_upper": "CI_upper",
            "p_value": "p_value",
            "icc": "ICC",
            "n_parks": "N_parks",
            "n_obs": "N_observations",
            "sample": "Sample"
        }
    )
)

COVERAGE_TABLE_FILE = (
    OUTPUT_DIR
    / "table_main_vs_90pct_sensitivity.csv"
)

coverage_comparison.to_csv(
    COVERAGE_TABLE_FILE,
    index=False
)


# ------------------------------------------------------------
# Figure: main vs >=90% coefficients
# ------------------------------------------------------------

order = [
    "Physical",
    "Visual",
    "Haptic",
    "Multidimensional"
]

main_plot = (
    main_comp
    .set_index(
        "model_label"
    )
    .loc[
        order
    ]
    .reset_index()
)

sens_plot = (
    sens90
    .set_index(
        "model_label"
    )
    .loc[
        order
    ]
    .reset_index()
)

y = np.arange(
    len(
        order
    )
)

offset = 0.12

fig, ax = plt.subplots(
    figsize=(
        8.5,
        5.8
    )
)


# Main sample
main_x = main_plot[
    "beta"
].to_numpy()

main_err = np.vstack(
    [
        main_x
        - main_plot[
            "ci_lower"
        ].to_numpy(),

        main_plot[
            "ci_upper"
        ].to_numpy()
        - main_x
    ]
)

ax.errorbar(
    main_x,
    y - offset,
    xerr=main_err,
    fmt="o",
    capsize=4,
    linewidth=1.2,
    label="Main sample (103 parks)"
)


# >=90% sample
sens_x = sens_plot[
    "beta"
].to_numpy()

sens_err = np.vstack(
    [
        sens_x
        - sens_plot[
            "ci_lower"
        ].to_numpy(),

        sens_plot[
            "ci_upper"
        ].to_numpy()
        - sens_x
    ]
)

ax.errorbar(
    sens_x,
    y + offset,
    xerr=sens_err,
    fmt="s",
    capsize=4,
    linewidth=1.2,
    label="≥90% coverage (78 parks)"
)


ax.axvline(
    0,
    linestyle="--",
    linewidth=1
)

ax.set_yticks(
    y
)

ax.set_yticklabels(
    order
)

ax.set_xlabel(
    "Standardized accessibility coefficient"
)

ax.set_ylabel(
    "Accessibility dimension"
)

ax.set_title(
    "Main and high-coverage sensitivity estimates"
)

ax.legend(
    frameon=False
)

ax.invert_yaxis()

ax.spines[
    "top"
].set_visible(
    False
)

ax.spines[
    "right"
].set_visible(
    False
)

fig.tight_layout()

SENSITIVITY_FIGURE = (
    OUTPUT_DIR
    / "figure_main_vs_90pct_accessibility_coefficients.png"
)

fig.savefig(
    SENSITIVITY_FIGURE,
    dpi=300,
    bbox_inches="tight"
)

plt.close(
    fig
)


# ------------------------------------------------------------
# Site-type sensitivity table
# ------------------------------------------------------------

site_sens = pd.read_csv(
    site_type_sensitivity_file
)

site_sens[
    "model_label"
] = (
    site_sens[
        "model"
    ]
    .map(
        {
            "original_site_type":
                "Original site type",

            "no_site_type":
                "No site-type control",

            "collapsed_site_type":
                "Collapsed site type"
        }
    )
)

site_sens_table = site_sens[
    [
        "model_label",
        "physical_beta",
        "physical_se",
        "physical_ci_low",
        "physical_ci_high",
        "physical_p",
        "icc",
        "log_likelihood",
        "aic",
        "bic"
    ]
].copy()

site_sens_table = (
    site_sens_table
    .rename(
        columns={
            "model_label":
                "Specification",

            "physical_beta":
                "Physical_Beta",

            "physical_se":
                "SE",

            "physical_ci_low":
                "CI_lower",

            "physical_ci_high":
                "CI_upper",

            "physical_p":
                "p_value",

            "icc":
                "ICC",

            "log_likelihood":
                "Log_likelihood",

            "aic":
                "AIC",

            "bic":
                "BIC"
        }
    )
)

SITE_SENS_TABLE_FILE = (
    OUTPUT_DIR
    / "table_physical_site_type_sensitivity.csv"
)

site_sens_table.to_csv(
    SITE_SENS_TABLE_FILE,
    index=False
)


# ------------------------------------------------------------
# Console output
# ------------------------------------------------------------

print("\n" + "=" * 100)
print("MAIN ACCESSIBILITY EFFECTS")
print("=" * 100)

print(
    main_effects
    .round(
        4
    )
    .to_string(
        index=False
    )
)


print("\n" + "=" * 100)
print("MAIN VS >=90% COVERAGE")
print("=" * 100)

print(
    coverage_comparison
    .round(
        4
    )
    .to_string(
        index=False
    )
)


print("\n" + "=" * 100)
print("SITE-TYPE SENSITIVITY")
print("=" * 100)

print(
    site_sens_table
    .round(
        4
    )
    .to_string(
        index=False
    )
)


print("\n" + "=" * 100)
print("FILES CREATED")
print("=" * 100)

for file in sorted(
    OUTPUT_DIR.iterdir()
):
    print(file)


print("\nDone.")