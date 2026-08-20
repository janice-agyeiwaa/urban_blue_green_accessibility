# ============================================================
# 07_build_mapbox_analysis_dataset.py
#
# Purpose:
# Build the main Mapbox analysis dataset using:
# - original 103-site Mapbox extraction
# - accessibility measures
# - temporal coverage information
# - editable time-of-day categories
#
# Also creates a >=90% temporal-coverage sensitivity dataset.
# ============================================================

from pathlib import Path
import pandas as pd


# ------------------------------------------------------------
# Project paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"


# ------------------------------------------------------------
# Editable time-of-day definitions
# ------------------------------------------------------------

MORNING_HOURS = range(6, 12)       # 6-11
AFTERNOON_HOURS = range(12, 17)    # 12-16
EVENING_HOURS = range(17, 21)      # 17-20


def classify_time_of_day(hour):

    if hour in MORNING_HOURS:
        return "morning"

    elif hour in AFTERNOON_HOURS:
        return "afternoon"

    elif hour in EVENING_HOURS:
        return "evening"

    else:
        return None


# ------------------------------------------------------------
# Input files
# ------------------------------------------------------------

MAPBOX_FILE = (
    PROCESSED_DIR /
    "mapbox" /
    "mapbox_park_hourly_activity_2023.csv"
)

ACCESS_FILE = (
    PROCESSED_DIR /
    "accessibility" /
    "all_114_sites_accessibility_scores.csv"
)

COVERAGE_FILE = (
    INTERIM_DIR /
    "mapbox" /
    "mapbox_temporal_coverage_summary_2023.csv"
)


# ------------------------------------------------------------
# Output files
# ------------------------------------------------------------

OUTPUT_DIR = (
    PROCESSED_DIR /
    "mapbox"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

MAIN_OUTPUT = (
    OUTPUT_DIR /
    "mapbox_analysis_dataset_103_sites.csv"
)

SENSITIVITY_OUTPUT = (
    OUTPUT_DIR /
    "mapbox_analysis_dataset_90pct_coverage.csv"
)


# ------------------------------------------------------------
# Read Mapbox activity
# ------------------------------------------------------------

activity = pd.read_csv(
    MAPBOX_FILE,
    dtype={
        "park_num": str
    }
)

print("\nMapbox activity loaded.")
print("Rows:", len(activity))
print(
    "Unique parks:",
    activity["park_num"].nunique()
)


# ------------------------------------------------------------
# Read accessibility measures
# ------------------------------------------------------------

access = pd.read_csv(
    ACCESS_FILE,
    dtype={
        "park_num": str
    }
)

print("\nAccessibility table loaded.")
print("Rows:", len(access))
print(
    "Unique parks:",
    access["park_num"].nunique()
)

print("\nAccessibility columns:")
print(access.columns.tolist())


# ------------------------------------------------------------
# Expected accessibility fields
# ------------------------------------------------------------

required_access_fields = [
    "park_num",
    "site_name",
    "municipality",
    "walktime_min",
    "physical_access_score",
    "visible_water_ratio",
    "shoreline_length_to_perimeter_ratio",
    "multidimensional_access_score"
]

missing_access_fields = [
    col
    for col in required_access_fields
    if col not in access.columns
]

if missing_access_fields:
    raise ValueError(
        f"Missing accessibility fields: {missing_access_fields}"
    )

if not access["walktime_min"].eq(10).all():
    raise ValueError(
        "Paper 4 accessibility handoff must contain only 10-minute scores."
    )


# ------------------------------------------------------------
# Read temporal coverage
# ------------------------------------------------------------

coverage = pd.read_csv(
    COVERAGE_FILE,
    dtype={
        "park_num": str
    }
)

print("\nCoverage table loaded.")
print("Rows:", len(coverage))
print(
    "Unique parks:",
    coverage["park_num"].nunique()
)


# ------------------------------------------------------------
# Keep required coverage fields
# ------------------------------------------------------------

coverage_keep = coverage[
    [
        "park_num",
        "mapbox_cell_count",
        "temporal_records",
        "missing_temporal_records",
        "coverage_pct",
        "coverage_group"
    ]
].copy()


# ------------------------------------------------------------
# Join activity + accessibility
# ------------------------------------------------------------

analysis = activity.merge(
    access[
        required_access_fields
    ],
    on="park_num",
    how="left",
    validate="many_to_one"
)

print("\nAfter accessibility join:")
print("Rows:", len(analysis))
print(
    "Unique parks:",
    analysis["park_num"].nunique()
)


# ------------------------------------------------------------
# Join coverage metadata
# ------------------------------------------------------------

analysis = analysis.merge(
    coverage_keep,
    on="park_num",
    how="left",
    validate="many_to_one"
)

print("\nAfter coverage join:")
print("Rows:", len(analysis))
print(
    "Unique parks:",
    analysis["park_num"].nunique()
)


# ------------------------------------------------------------
# Add time-of-day categories
# ------------------------------------------------------------

analysis["time_of_day"] = (
    analysis["agg_time_period"]
    .apply(
        classify_time_of_day
    )
)


# ------------------------------------------------------------
# Add readable month field
# ------------------------------------------------------------

analysis["start_date"] = pd.to_datetime(
    analysis["start_date"]
)

analysis["month"] = (
    analysis["start_date"]
    .dt.month
)

analysis["month_name"] = (
    analysis["start_date"]
    .dt.month_name()
)


# ------------------------------------------------------------
# QA: missing accessibility variables
# ------------------------------------------------------------

accessibility_vars = [
    "physical_access_score",
    "visible_water_ratio",
    "shoreline_length_to_perimeter_ratio",
    "multidimensional_access_score"
]

print("\nMissing accessibility values:")

print(
    analysis[
        accessibility_vars
    ].isna().sum()
)


# ------------------------------------------------------------
# QA: parks without matched accessibility records
# ------------------------------------------------------------

missing_access_parks = (
    analysis.loc[
        analysis[
            accessibility_vars
        ].isna().any(axis=1),
        [
            "park_num",
            "site_name"
        ]
    ]
    .drop_duplicates()
)

print(
    "\nParks with missing accessibility measures:",
    len(missing_access_parks)
)

if not missing_access_parks.empty:
    print(
        missing_access_parks.to_string(
            index=False
        )
    )


# ------------------------------------------------------------
# QA: time-of-day categories
# ------------------------------------------------------------

print("\nTime-of-day counts:")

print(
    analysis[
        "time_of_day"
    ].value_counts(
        dropna=False
    )
)


# ------------------------------------------------------------
# Reorder columns
# ------------------------------------------------------------

column_order = [
    "park_num",
    "site_name",
    "municipality",

    "start_date",
    "end_date",
    "month",
    "month_name",

    "agg_day_period",
    "day_type",

    "agg_time_period",
    "hour_label",
    "time_of_day",

    "site_activity_index",
    "unique_cells_used",
    "contributing_cell_records",

    "physical_access_score",
    "visible_water_ratio",
    "shoreline_length_to_perimeter_ratio",
    "multidimensional_access_score",
    "walktime_min",

    "mapbox_cell_count",
    "temporal_records",
    "missing_temporal_records",
    "coverage_pct",
    "coverage_group"
]

analysis = analysis[
    column_order
]


# ------------------------------------------------------------
# Sort
# ------------------------------------------------------------

analysis["park_num_numeric"] = pd.to_numeric(
    analysis["park_num"],
    errors="coerce"
)

analysis = (
    analysis
    .sort_values(
        [
            "park_num_numeric",
            "start_date",
            "agg_day_period",
            "agg_time_period"
        ]
    )
    .drop(
        columns="park_num_numeric"
    )
)


# ------------------------------------------------------------
# Save MAIN dataset
#
# This keeps all 103 parks currently represented in the
# original Mapbox extraction.
# ------------------------------------------------------------

analysis.to_csv(
    MAIN_OUTPUT,
    index=False
)

print("\nMain analysis dataset saved:")
print(MAIN_OUTPUT)


# ------------------------------------------------------------
# Create Keun >=90% sensitivity dataset
# ------------------------------------------------------------

sensitivity_90 = analysis[
    analysis["coverage_pct"] >= 90
].copy()

sensitivity_90.to_csv(
    SENSITIVITY_OUTPUT,
    index=False
)

print("\n>=90% sensitivity dataset saved:")
print(SENSITIVITY_OUTPUT)


# ------------------------------------------------------------
# Final QA summary
# ------------------------------------------------------------

print("\n" + "=" * 60)
print("FINAL QA SUMMARY")
print("=" * 60)

print(
    "\nMAIN DATASET"
)

print(
    "Rows:",
    len(analysis)
)

print(
    "Unique parks:",
    analysis["park_num"].nunique()
)

print(
    "\n>=90% SENSITIVITY DATASET"
)

print(
    "Rows:",
    len(sensitivity_90)
)

print(
    "Unique parks:",
    sensitivity_90["park_num"].nunique()
)

print(
    "\nDay types:"
)

print(
    analysis[
        [
            "agg_day_period",
            "day_type"
        ]
    ]
    .drop_duplicates()
    .sort_values(
        "agg_day_period"
    )
    .to_string(
        index=False
    )
)

print(
    "\nTime-of-day mapping:"
)

print(
    analysis[
        [
            "agg_time_period",
            "time_of_day"
        ]
    ]
    .drop_duplicates()
    .sort_values(
        "agg_time_period"
    )
    .to_string(
        index=False
    )
)

print("\nDone.")
