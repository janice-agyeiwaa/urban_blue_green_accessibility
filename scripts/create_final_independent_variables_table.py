# 09_create_final_independent_variables_table.py

from pathlib import Path
import pandas as pd


# ============================================================
# CREATE FINAL INDEPENDENT VARIABLES TABLE
# One row per park/site
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

# -------------------------
# Input files
# -------------------------

REACH_INPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "reach"
    / "reach_independent_variables.csv"
)

HAPTIC_INPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "haptic"
    / "avery_shoreline_perimeter_ratio.csv"
)

VIEWSHED_INPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "viewshed"
    / "allparks_viewshed_visible_water_area_spacing_access_fallback.csv"
)

# -------------------------
# Output file
# -------------------------

OUTPUT_CSV = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "final_independent_variables.csv"
)

OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# Read inputs
# ============================================================

print("Reading reach variables...")
reach = pd.read_csv(REACH_INPUT)

print("Reading haptic variables...")
haptic = pd.read_csv(HAPTIC_INPUT)

print("Reading viewshed variables...")
viewshed = pd.read_csv(VIEWSHED_INPUT)


# ============================================================
# Standardize key fields
# ============================================================

for df_name, df in {
    "reach": reach,
    "haptic": haptic,
    "viewshed": viewshed,
}.items():
    if "park_num" not in df.columns:
        raise ValueError(f"'park_num' field missing from {df_name} input.")

    df["park_num"] = df["park_num"].astype(int)


# ============================================================
# Keep only needed fields from each table
# ============================================================

reach_keep = reach[
    [
        "park_num",
        "PARK_NAME",
        "access_point_count",
        "bus_stops_05min",
        "bus_stops_10min",
        "bus_stops_20min",
        "bus_stops_30min",
    ]
].copy()

# Some reach tables may not have MUNI, so use haptic/viewshed later if available
if "MUNI" in reach.columns:
    reach_keep["MUNI"] = reach["MUNI"]

haptic_keep = haptic[
    [
        "park_num",
        "shoreline_to_perimeter_ratio",
    ]
].copy()

if "MUNI" in haptic.columns:
    haptic_keep["MUNI_haptic"] = haptic["MUNI"]

viewshed_keep = viewshed[
    [
        "park_num",
        "visible_water_area_m2",
    ]
].copy()

if "MUNI" in viewshed.columns:
    viewshed_keep["MUNI_viewshed"] = viewshed["MUNI"]


# ============================================================
# Merge tables
# ============================================================

final = reach_keep.merge(
    haptic_keep,
    on="park_num",
    how="left"
)

final = final.merge(
    viewshed_keep,
    on="park_num",
    how="left"
)


# ============================================================
# Create municipality field
# ============================================================

if "MUNI" in final.columns:
    final["municipal"] = final["MUNI"]
elif "MUNI_haptic" in final.columns:
    final["municipal"] = final["MUNI_haptic"]
elif "MUNI_viewshed" in final.columns:
    final["municipal"] = final["MUNI_viewshed"]
else:
    final["municipal"] = None


# ============================================================
# Rename fields to requested headers
# ============================================================

final_output = pd.DataFrame({
    "Park num": final["park_num"],
    "Site name": final["PARK_NAME"],
    "Municipal": final["municipal"],
    "Bus stops 5mins": final["bus_stops_05min"],
    "Bus stops 10mins": final["bus_stops_10min"],
    "Bus stops 20mins": final["bus_stops_20min"],
    "Bus stops 30mins": final["bus_stops_30min"],
    "Number of access points": final["access_point_count"],
    "Haptic access": final["shoreline_to_perimeter_ratio"],
    "Visual Access (Viewshed area in m2)": final["visible_water_area_m2"],
})


# ============================================================
# Sort and save
# ============================================================

final_output = final_output.sort_values("Park num")

final_output.to_csv(OUTPUT_CSV, index=False)

print("\nSaved final independent variables table:")
print(OUTPUT_CSV)

print("\nRows:", len(final_output))

print("\nMissing values by field:")
print(final_output.isna().sum())

print("\nFirst 10 rows:")
print(final_output.head(10).to_string(index=False))

print("\nDone.")