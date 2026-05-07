"""
Haptic accessibility helper functions.

This file contains reusable functions for reading and extracting haptic/touch
accessibility variables from Avery's processed haptic layer.
"""

from pathlib import Path

import arcpy
import pandas as pd


# PROJECT_ROOT is the main project folder.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Local geodatabase where the exported OneDrive layers are stored.
RAW_GDB = PROJECT_ROOT / "data" / "raw" / "project_team_subset.gdb"

# Haptic input layer.
HAPTIC_LAYER = RAW_GDB / "hapticvariables"


# Haptic/touch access fields.
HAPTIC_FIELDS = [
    "park_num",
    "PARK_NAME",
    "MUNI",
    "perimeter",
    "shoreline_length_m",
    "length_to_perimeter",
]


def read_haptic_layer() -> pd.DataFrame:
    """
    Read haptic variables from the ArcGIS feature class into a DataFrame.
    """

    records = []

    with arcpy.da.SearchCursor(str(HAPTIC_LAYER), HAPTIC_FIELDS) as cursor:
        for row in cursor:
            records.append(dict(zip(HAPTIC_FIELDS, row)))

    df = pd.DataFrame(records)

    # Rename fields for clearer output.
    df = df.rename(
        columns={
            "PARK_NAME": "site_name",
            "MUNI": "municipality",
            "length_to_perimeter": "haptic_length_to_perimeter",
        }
    )

    # Clean text fields so hidden line breaks/spaces do not affect matching.
    df["site_name"] = df["site_name"].str.strip()
    df["municipality"] = df["municipality"].str.strip()

    return df


def get_sample_haptic(selected_sites: list[str]) -> pd.DataFrame:
    """
    Return haptic variables for selected waterfront sites.
    """

    haptic_df = read_haptic_layer()

    sample_df = haptic_df[haptic_df["site_name"].isin(selected_sites)].copy()
    sample_df = sample_df.sort_values("site_name")

    return sample_df


if __name__ == "__main__":
    # Quick check when this file is run directly.
    df = read_haptic_layer()
    print("Haptic records:", len(df))
    print(df.head())