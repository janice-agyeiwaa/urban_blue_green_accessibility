from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# 16_generate_descriptives_and_temporal_figures.py
#
# Purpose:
# 1. Create descriptive statistics for the 103-site sample
# 2. Create site-type counts
# 3. Summarize observed Mapbox activity by:
#    - weekday/weekend
#    - time of day
#    - season
# 4. Save publication-ready figures and CSV summaries
# ============================================================


# ------------------------------------------------------------
# Project paths
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
    / "outputs"
    / "mapbox"
    / "descriptives"
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

print("\nDataset loaded.")
print("Rows:", len(df))
print(
    "Unique parks:",
    df["park_num"].nunique()
)


# ------------------------------------------------------------
# One-row-per-park table
# ------------------------------------------------------------

park = (
    df.sort_values(
        [
            "park_num",
            "start_date",
            "agg_time_period"
        ]
    )
    .groupby(
        "park_num",
        as_index=False
    )
    .agg(
        site_name=(
            "site_name",
            "first"
        ),
        municipality=(
            "municipality",
            "first"
        ),
        site_type=(
            "site_type",
            "first"
        ),
        physical_access_score=(
            "physical_access_score",
            "first"
        ),
        visible_water_ratio=(
            "visible_water_ratio",
            "first"
        ),
        shoreline_length_to_perimeter_ratio=(
            "shoreline_length_to_perimeter_ratio",
            "first"
        ),
        multidimensional_access_score=(
            "multidimensional_access_score",
            "first"
        ),
        site_area_m2=(
            "site_area_m2",
            "first"
        ),
        population_density_km2=(
            "population_density_km2",
            "first"
        ),
        coverage_pct=(
            "coverage_pct",
            "first"
        ),
        mapbox_cell_count=(
            "mapbox_cell_count",
            "first"
        ),
        temporal_records=(
            "temporal_records",
            "first"
        ),
        mean_site_activity=(
            "site_activity_index",
            "mean"
        )
    )
)


# ------------------------------------------------------------
# Table 1: descriptive statistics
# ------------------------------------------------------------

summary_vars = [

    (
        "Mean site activity index",
        "mean_site_activity"
    ),

    (
        "Physical accessibility score",
        "physical_access_score"
    ),

    (
        "Visual accessibility ratio",
        "visible_water_ratio"
    ),

    (
        "Haptic accessibility ratio",
        "shoreline_length_to_perimeter_ratio"
    ),

    (
        "Multidimensional accessibility score",
        "multidimensional_access_score"
    ),

    (
        "Site area (m²)",
        "site_area_m2"
    ),

    (
        "20-min population density (people/km²)",
        "population_density_km2"
    ),

    (
        "Mapbox temporal coverage (%)",
        "coverage_pct"
    ),

    (
        "Matched Mapbox cells",
        "mapbox_cell_count"
    ),

    (
        "Available temporal records",
        "temporal_records"
    )
]


rows = []

for label, col in summary_vars:

    values = pd.to_numeric(
        park[col],
        errors="coerce"
    ).dropna()

    rows.append(
        {
            "Variable": label,
            "N_parks": int(
                values.count()
            ),
            "Mean": values.mean(),
            "SD": values.std(
                ddof=1
            ),
            "Median": values.median(),
            "Minimum": values.min(),
            "Maximum": values.max()
        }
    )


table1 = pd.DataFrame(
    rows
)

TABLE1_FILE = (
    OUTPUT_DIR
    / "table1_descriptive_statistics.csv"
)

table1.to_csv(
    TABLE1_FILE,
    index=False
)


# ------------------------------------------------------------
# Site-type counts
# ------------------------------------------------------------

site_type_counts = (
    park[
        "site_type"
    ]
    .value_counts(
        dropna=False
    )
    .rename_axis(
        "site_type"
    )
    .reset_index(
        name="n_parks"
    )
)

site_type_counts["percent"] = (
    site_type_counts[
        "n_parks"
    ]
    / len(park)
    * 100
)


SITE_TYPE_FILE = (
    OUTPUT_DIR
    / "table1_site_type_counts.csv"
)

site_type_counts.to_csv(
    SITE_TYPE_FILE,
    index=False
)


# ------------------------------------------------------------
# Temporal summary helper
#
# IMPORTANT:
# First average within park x category.
#
# Then average across parks.
#
# This prevents parks with more available Mapbox temporal
# observations from receiving greater weight in the
# descriptive figures.
# ------------------------------------------------------------

def temporal_summary(
    data,
    category
):

    per_park = (
        data
        .groupby(
            [
                "park_num",
                category
            ],
            as_index=False
        )
        .agg(
            mean_activity=(
                "site_activity_index",
                "mean"
            )
        )
    )

    summary = (
        per_park
        .groupby(
            category,
            as_index=False
        )
        .agg(
            n_parks=(
                "park_num",
                "nunique"
            ),
            mean_activity=(
                "mean_activity",
                "mean"
            ),
            sd_activity=(
                "mean_activity",
                "std"
            )
        )
    )

    summary[
        "se_activity"
    ] = (
        summary[
            "sd_activity"
        ]
        / np.sqrt(
            summary[
                "n_parks"
            ]
        )
    )

    summary[
        "ci95_lower"
    ] = (
        summary[
            "mean_activity"
        ]
        - 1.96
        * summary[
            "se_activity"
        ]
    )

    summary[
        "ci95_upper"
    ] = (
        summary[
            "mean_activity"
        ]
        + 1.96
        * summary[
            "se_activity"
        ]
    )

    return summary


# ------------------------------------------------------------
# Temporal summaries
# ------------------------------------------------------------

day_summary = temporal_summary(
    df,
    "day_type"
)

tod_summary = temporal_summary(
    df,
    "time_of_day"
)

season_summary = temporal_summary(
    df,
    "season"
)


DAY_FILE = (
    OUTPUT_DIR
    / "temporal_activity_day_type_summary.csv"
)

TOD_FILE = (
    OUTPUT_DIR
    / "temporal_activity_time_of_day_summary.csv"
)

SEASON_FILE = (
    OUTPUT_DIR
    / "temporal_activity_season_summary.csv"
)


day_summary.to_csv(
    DAY_FILE,
    index=False
)

tod_summary.to_csv(
    TOD_FILE,
    index=False
)

season_summary.to_csv(
    SEASON_FILE,
    index=False
)


# ------------------------------------------------------------
# Figure helper
# ------------------------------------------------------------

def save_bar_with_ci(
    summary,
    category,
    order,
    title,
    xlabel,
    filename
):

    plot_df = (
        summary
        .set_index(
            category
        )
        .loc[
            order
        ]
        .reset_index()
    )

    x = np.arange(
        len(
            plot_df
        )
    )

    y = (
        plot_df[
            "mean_activity"
        ]
        .to_numpy()
    )

    yerr = np.vstack(
        [
            (
                y
                - plot_df[
                    "ci95_lower"
                ].to_numpy()
            ),
            (
                plot_df[
                    "ci95_upper"
                ].to_numpy()
                - y
            )
        ]
    )

    fig, ax = plt.subplots(
        figsize=(
            7.5,
            5.2
        )
    )

    ax.bar(
        x,
        y
    )

    ax.errorbar(
        x,
        y,
        yerr=yerr,
        fmt="none",
        capsize=4,
        linewidth=1.2
    )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        plot_df[
            category
        ]
        .astype(
            str
        )
        .tolist()
    )

    ax.set_ylabel(
        "Mean site activity index"
    )

    ax.set_xlabel(
        xlabel
    )

    ax.set_title(
        title
    )

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

    fig.savefig(
        OUTPUT_DIR
        / filename,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(
        fig
    )


# ------------------------------------------------------------
# Figure 1: weekday/weekend
# ------------------------------------------------------------

save_bar_with_ci(
    day_summary,
    "day_type",
    [
        "weekday",
        "weekend"
    ],
    "Observed waterfront activity by day type",
    "Day type",
    "figure_temporal_day_type.png"
)


# ------------------------------------------------------------
# Figure 2: time of day
# ------------------------------------------------------------

save_bar_with_ci(
    tod_summary,
    "time_of_day",
    [
        "morning",
        "afternoon",
        "evening"
    ],
    "Observed waterfront activity by time of day",
    "Time of day",
    "figure_temporal_time_of_day.png"
)


# ------------------------------------------------------------
# Figure 3: season
# ------------------------------------------------------------

save_bar_with_ci(
    season_summary,
    "season",
    [
        "winter",
        "spring",
        "summer",
        "fall"
    ],
    "Observed waterfront activity by season",
    "Season",
    "figure_temporal_season.png"
)


# ------------------------------------------------------------
# Console output
# ------------------------------------------------------------

print("\n" + "=" * 80)
print("TABLE 1")
print("=" * 80)

print(
    table1
    .round(
        4
    )
    .to_string(
        index=False
    )
)


print("\n" + "=" * 80)
print("SITE TYPE COUNTS")
print("=" * 80)

print(
    site_type_counts
    .to_string(
        index=False
    )
)


print("\n" + "=" * 80)
print("DAY-TYPE ACTIVITY")
print("=" * 80)

print(
    day_summary
    .round(
        4
    )
    .to_string(
        index=False
    )
)


print("\n" + "=" * 80)
print("TIME-OF-DAY ACTIVITY")
print("=" * 80)

print(
    tod_summary
    .round(
        4
    )
    .to_string(
        index=False
    )
)


print("\n" + "=" * 80)
print("SEASON ACTIVITY")
print("=" * 80)

print(
    season_summary
    .round(
        4
    )
    .to_string(
        index=False
    )
)


print("\n" + "=" * 80)
print("FILES CREATED")
print("=" * 80)

for path in sorted(
    OUTPUT_DIR.iterdir()
):

    print(
        path
    )


print("\nDone.")