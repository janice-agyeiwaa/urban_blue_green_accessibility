"""
Reach accessibility helper functions.

This file contains reusable functions for reading and extracting reach/physical
accessibility variables from Avery's processed reach layer.
"""

from pathlib import Path

import arcpy
import pandas as pd


# PROJECT_ROOT is the main project folder.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Local geodatabase where the exported OneDrive layers are stored.
RAW_GDB = PROJECT_ROOT / "data" / "raw" / "project_team_subset.gdb"

# Reach input layer.
REACH_LAYER = RAW_GDB / "reachvariables"


# Reach/physical access fields.
REACH_FIELDS = [
    "park_num",
    "PARK_NAME",
    "MUNI",
    "num_access_points",
    "bus_stops_05min",
    "bus_stops_10min",
    "bus_stops_20min",
    "bus_stops_30min",
]


def read_reach_layer() -> pd.DataFrame:
    """
    Read reach variables from the ArcGIS feature class into a DataFrame.
    """

    records = []

    with arcpy.da.SearchCursor(str(REACH_LAYER), REACH_FIELDS) as cursor:
        for row in cursor:
            records.append(dict(zip(REACH_FIELDS, row)))

    df = pd.DataFrame(records)

    # Rename fields for clearer output.
    df = df.rename(
        columns={
            "PARK_NAME": "site_name",
            "MUNI": "municipality",
        }
    )

    # Clean text fields so hidden line breaks/spaces do not affect matching.
    df["site_name"] = df["site_name"].str.strip()
    df["municipality"] = df["municipality"].str.strip()

    return df


def get_sample_reach(selected_sites: list[str]) -> pd.DataFrame:
    """
    Return reach variables for selected waterfront sites.
    """

    reach_df = read_reach_layer()

    sample_df = reach_df[reach_df["site_name"].isin(selected_sites)].copy()
    sample_df = sample_df.sort_values("site_name")

    return sample_df


if __name__ == "__main__":
    # Quick check when this file is run directly.
    df = read_reach_layer()
    print("Reach records:", len(df))
    print(df.head())