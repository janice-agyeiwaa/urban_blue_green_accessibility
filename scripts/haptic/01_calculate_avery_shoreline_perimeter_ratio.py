# 01_calculate_avery_shoreline_perimeter_ratio.py

from pathlib import Path
import geopandas as gpd


# ============================================================
# STEP 1: AVERY-STYLE SHORELINE / PARK PERIMETER RATIO
# ============================================================
# Formula:
# shoreline_to_perimeter_ratio = shoreline_length_m / park_perimeter_m
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

PARKS_GDB = PROJECT_ROOT / "data" / "raw" / "Park_Extraction_Project.gdb"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "haptic"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = PROCESSED_DIR / "avery_shoreline_perimeter_ratio.csv"

LAND_BUFFER_LAYER = "allparks_land_buffer"
SHORELINE_LAYER = "allparks_land_buff_Intersect"

PARK_ID_FIELD = "park_num"
PARK_NAME_FIELD = "PARK_NAME"
MUNI_FIELD = "MUNI"


# ============================================================
# Read data
# ============================================================

print("Reading park land buffers...")
parks = gpd.read_file(PARKS_GDB, layer=LAND_BUFFER_LAYER)

print("Reading shoreline/intersect polyline...")
shoreline = gpd.read_file(PARKS_GDB, layer=SHORELINE_LAYER)

parks = parks[[PARK_ID_FIELD, PARK_NAME_FIELD, MUNI_FIELD, "geometry"]].copy()
parks[PARK_NAME_FIELD] = parks[PARK_NAME_FIELD].astype(str).str.strip()

shoreline = shoreline[[PARK_ID_FIELD, PARK_NAME_FIELD, "geometry"]].copy()
shoreline[PARK_NAME_FIELD] = shoreline[PARK_NAME_FIELD].astype(str).str.strip()

if shoreline.crs != parks.crs:
    print("Reprojecting shoreline to match parks CRS...")
    shoreline = shoreline.to_crs(parks.crs)

print("Parks:", len(parks))
print("Shoreline records:", len(shoreline))
print("CRS:", parks.crs)


# ============================================================
# Calculate park perimeter and shoreline length
# ============================================================

parks["park_perimeter_m"] = parks.geometry.length
shoreline["shoreline_part_length_m"] = shoreline.geometry.length

shoreline_lengths = (
    shoreline
    .groupby(PARK_ID_FIELD)["shoreline_part_length_m"]
    .sum()
    .reset_index(name="shoreline_length_m")
)

output = parks[
    [PARK_ID_FIELD, PARK_NAME_FIELD, MUNI_FIELD, "park_perimeter_m"]
].merge(
    shoreline_lengths,
    on=PARK_ID_FIELD,
    how="left"
)

output["shoreline_length_m"] = output["shoreline_length_m"].fillna(0)

output["shoreline_to_perimeter_ratio"] = (
    output["shoreline_length_m"] / output["park_perimeter_m"]
)

output["shoreline_to_perimeter_percent"] = (
    output["shoreline_to_perimeter_ratio"] * 100
)

output = output.sort_values(PARK_ID_FIELD)

output.to_csv(OUTPUT_CSV, index=False)

print("\nSaved Avery shoreline/perimeter ratio:")
print(OUTPUT_CSV)

print("\nSummary:")
print("Rows:", len(output))
print("Parks with shoreline length > 0:", (output["shoreline_length_m"] > 0).sum())

print("\nFirst 10 rows:")
print(output.head(10).to_string(index=False))

print("\nDone.")