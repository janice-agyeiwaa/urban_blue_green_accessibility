"""
Week 1 reproducible task.

This script extracts reach and haptic accessibility variables for five selected
waterfront sites, joins them by park_num, and exports one combined CSV table.
"""

from pathlib import Path

import pandas as pd

from reach import get_sample_reach
from haptic import get_sample_haptic


# PROJECT_ROOT is the main project folder.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Output folder for Week 1 tables.
OUTPUT_TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"

# Final Week 1 output table.
WEEK1_OUTPUT_CSV = OUTPUT_TABLE_DIR / "week1_reach_haptic_5_sites.csv"


# Selected waterfront sites for the Week 1 sample.
SELECTED_SITES = [
    "Ambleside Park 1",
    "Cates Park",
    "Spanish Banks Beach Park and Extension",
    "Stanley Park (Seawall, Second Beach, Third Beach)",
    "Pacific Spirit Regional Park (Acadia, Tower, and Wreck Beaches combined)",
]


def combine_reach_haptic() -> pd.DataFrame:
    """
    Get reach and haptic variables for selected sites and join them by park_num.
    """

    # Get selected reach and haptic records.
    reach_df = get_sample_reach(SELECTED_SITES)
    haptic_df = get_sample_haptic(SELECTED_SITES)

    # Join using park_num, which was confirmed to match across both layers.
    combined_df = reach_df.merge(
        haptic_df,
        on="park_num",
        how="inner",
        suffixes=("_reach", "_haptic"),
    )

    # Keep a clean set of fields for the Week 1 output.
    final_df = combined_df[
        [
            "park_num",
            "site_name_reach",
            "municipality_reach",
            "num_access_points",
            "bus_stops_05min",
            "bus_stops_10min",
            "bus_stops_20min",
            "bus_stops_30min",
            "perimeter",
            "shoreline_length_m",
            "haptic_length_to_perimeter",
        ]
    ].copy()

    # Rename final output fields.
    final_df = final_df.rename(
        columns={
            "site_name_reach": "site_name",
            "municipality_reach": "municipality",
        }
    )

    return final_df


def main():
    """
    Run the Week 1 workflow and export the combined table.
    """

    OUTPUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)

    final_df = combine_reach_haptic()

    final_df.to_csv(WEEK1_OUTPUT_CSV, index=False)

    print("Selected sites requested:", len(SELECTED_SITES))
    print("Combined records exported:", len(final_df))
    print("\nWeek 1 reach + haptic table:")
    print(final_df)


if __name__ == "__main__":
    main()