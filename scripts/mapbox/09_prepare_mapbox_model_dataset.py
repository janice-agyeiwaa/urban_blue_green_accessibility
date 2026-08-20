from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


# ============================================================
# 09_prepare_mapbox_model_dataset.py
#
# Purpose:
# Add final model-preparation variables to the 103-site
# Mapbox analysis dataset:
#
# - 2021 population from 20-minute Census Enrich catchments
# - 20-minute catchment area (km2)
# - population density (people/km2)
# - log-transformed site area
# - season
#
# Keeps original variables unchanged.
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
    / "mapbox_analysis_dataset_103_sites_final.csv"
)

CENSUS_GDB = (
    PROJECT_ROOT
    / "data"
    / "interim"
    / "census"
    / "census_enrich_prep.gdb"
)

CENSUS_LAYER = "pop_den"

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "mapbox"
    / "mapbox_model_dataset_103_sites.csv"
)


# ------------------------------------------------------------
# Editable season definition
#
# Meteorological seasons:
# winter = Dec-Feb
# spring = Mar-May
# summer = Jun-Aug
# fall   = Sep-Nov
# ------------------------------------------------------------

def classify_season(month):

    if month in [12, 1, 2]:
        return "winter"

    elif month in [3, 4, 5]:
        return "spring"

    elif month in [6, 7, 8]:
        return "summer"

    elif month in [9, 10, 11]:
        return "fall"

    else:
        return None


# ------------------------------------------------------------
# Read existing 103-site analysis dataset
# ------------------------------------------------------------

analysis = pd.read_csv(
    INPUT_FILE,
    dtype={
        "park_num": str
    }
)

print("\nMain analysis dataset loaded.")
print("Rows:", len(analysis))
print(
    "Unique parks:",
    analysis["park_num"].nunique()
)


# ------------------------------------------------------------
# Read Census Enrich population layer
# ------------------------------------------------------------

pop = gpd.read_file(
    CENSUS_GDB,
    layer=CENSUS_LAYER
)

print("\nPopulation layer loaded.")
print("Rows:", len(pop))
print(
    "Unique parks:",
    pop["park_num"].nunique()
)
print("CRS:", pop.crs)


# ------------------------------------------------------------
# Basic QA
# ------------------------------------------------------------

required_pop_fields = [
    "park_num",
    "PARK_NAME",
    "walktime_min",
    "HasData",
    "PopulationTotals_EHYPTAPOP",
    "geom_Area"
]

missing_fields = [
    field
    for field in required_pop_fields
    if field not in pop.columns
]

if missing_fields:
    raise ValueError(
        f"Missing Census fields: {missing_fields}"
    )


# ------------------------------------------------------------
# Confirm these are 20-minute catchments
# ------------------------------------------------------------

print("\nWalking-time values present:")
print(
    sorted(
        pop["walktime_min"].dropna().unique()
    )
)

if not (
    pop["walktime_min"]
    .dropna()
    .eq(20)
    .all()
):
    raise ValueError(
        "Population layer contains records other than 20-minute catchments."
    )


# ------------------------------------------------------------
# Convert park_num to consistent type
# ------------------------------------------------------------

pop["park_num"] = (
    pop["park_num"]
    .astype(int)
    .astype(str)
)


# ------------------------------------------------------------
# Create population-density table
# ------------------------------------------------------------

pop_table = pop[
    [
        "park_num",
        "PARK_NAME",
        "HasData",
        "PopulationTotals_EHYPTAPOP",
        "geom_Area"
    ]
].copy()

pop_table = (
    pop_table
    .drop_duplicates(
        subset="park_num"
    )
)

pop_table = pop_table.rename(
    columns={
        "PopulationTotals_EHYPTAPOP": "population_2021",
        "geom_Area": "catchment_area_m2"
    }
)


# ------------------------------------------------------------
# Convert catchment area to km2
# ------------------------------------------------------------

pop_table["catchment_area_km2"] = (
    pop_table["catchment_area_m2"]
    / 1_000_000
)


# ------------------------------------------------------------
# Population density
#
# people per square kilometre
# ------------------------------------------------------------

pop_table["population_density_km2"] = (
    pop_table["population_2021"]
    / pop_table["catchment_area_km2"]
)


# ------------------------------------------------------------
# QA population-density values
# ------------------------------------------------------------

print("\nPopulation summary:")
print(
    pop_table[
        "population_2021"
    ].describe()
)

print("\n20-minute catchment area summary (km2):")
print(
    pop_table[
        "catchment_area_km2"
    ].describe()
)

print("\nPopulation density summary (people/km2):")
print(
    pop_table[
        "population_density_km2"
    ].describe()
)


# ------------------------------------------------------------
# Check for invalid density calculations
# ------------------------------------------------------------

invalid_density = pop_table[
    (
        pop_table["catchment_area_km2"].isna()
    )
    |
    (
        pop_table["catchment_area_km2"] <= 0
    )
    |
    (
        pop_table["population_density_km2"].isna()
    )
]

print(
    "\nInvalid population-density records:",
    len(invalid_density)
)

if not invalid_density.empty:

    print(
        invalid_density[
            [
                "park_num",
                "PARK_NAME",
                "population_2021",
                "catchment_area_km2",
                "population_density_km2"
            ]
        ].to_string(
            index=False
        )
    )


# ------------------------------------------------------------
# Join population variables to Mapbox dataset
# ------------------------------------------------------------

analysis = analysis.merge(
    pop_table[
        [
            "park_num",
            "population_2021",
            "catchment_area_km2",
            "population_density_km2"
        ]
    ],
    on="park_num",
    how="left",
    validate="many_to_one"
)


# ------------------------------------------------------------
# Log-transform site area
#
# Keep original site_area_m2 unchanged.
# ------------------------------------------------------------

if "site_area_m2" not in analysis.columns:
    raise ValueError(
        "site_area_m2 not found in analysis dataset."
    )

if (analysis["site_area_m2"] <= 0).any():
    raise ValueError(
        "site_area_m2 contains zero or negative values."
    )

analysis["log_site_area"] = np.log(
    analysis["site_area_m2"]
)


# ------------------------------------------------------------
# Season
# ------------------------------------------------------------

if "month" not in analysis.columns:
    raise ValueError(
        "month field not found in analysis dataset."
    )

analysis["season"] = (
    analysis["month"]
    .apply(
        classify_season
    )
)


# ------------------------------------------------------------
# QA joined variables
# ------------------------------------------------------------

print("\n" + "=" * 60)
print("JOIN QA")
print("=" * 60)

print(
    "\nMissing population_2021:",
    analysis["population_2021"].isna().sum()
)

print(
    "Missing population_density_km2:",
    analysis["population_density_km2"].isna().sum()
)

print(
    "Missing log_site_area:",
    analysis["log_site_area"].isna().sum()
)

print(
    "Missing season:",
    analysis["season"].isna().sum()
)


# ------------------------------------------------------------
# QA at PARK level
# ------------------------------------------------------------

park_qa = (
    analysis[
        [
            "park_num",
            "site_name",
            "site_type",
            "site_area_m2",
            "log_site_area",
            "population_2021",
            "catchment_area_km2",
            "population_density_km2"
        ]
    ]
    .drop_duplicates(
        subset="park_num"
    )
)

print(
    "\nUnique parks in final model dataset:",
    len(park_qa)
)

print("\nPopulation density by park:")
print(
    park_qa[
        "population_density_km2"
    ].describe()
)


# ------------------------------------------------------------
# Print lowest and highest population-density parks
# ------------------------------------------------------------

print("\nLowest population-density parks:")

print(
    park_qa[
        [
            "park_num",
            "site_name",
            "population_2021",
            "catchment_area_km2",
            "population_density_km2"
        ]
    ]
    .sort_values(
        "population_density_km2"
    )
    .head(10)
    .to_string(
        index=False
    )
)

print("\nHighest population-density parks:")

print(
    park_qa[
        [
            "park_num",
            "site_name",
            "population_2021",
            "catchment_area_km2",
            "population_density_km2"
        ]
    ]
    .sort_values(
        "population_density_km2",
        ascending=False
    )
    .head(10)
    .to_string(
        index=False
    )
)


# ------------------------------------------------------------
# Season counts
# ------------------------------------------------------------

print("\nSeason row counts:")

print(
    analysis[
        "season"
    ].value_counts()
)


# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

analysis.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\n" + "=" * 60)
print("FINAL MODEL DATASET")
print("=" * 60)

print("\nSaved to:")
print(OUTPUT_FILE)

print(
    "\nRows:",
    len(analysis)
)

print(
    "Unique parks:",
    analysis["park_num"].nunique()
)

print("\nDone.")