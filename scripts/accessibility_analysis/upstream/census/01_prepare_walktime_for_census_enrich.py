"""
[UBS] Prepare walk-time polygons for Census Enrich

This script prepares the walk-time polygons for Census enrichment.

It reads the full walk-time GeoPackage containing 5, 10, 20, and 30
minute polygons, then copies those records into an interim Census
geodatabase.

Original input is not modified.
"""

import arcpy
from pathlib import Path


# ------------------------------------------------------------
# 1. Set paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[4]

INPUT_GPKG = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "reach"
    / "walktime_polygons_5_10_20_30min.gpkg"
)

OUT_FOLDER = PROJECT_ROOT / "data" / "interim" / "census"
OUT_GDB = OUT_FOLDER / "census_enrich_prep.gdb"
OUT_FC = OUT_GDB / "walktime_5_10_20_30_for_census"


# ------------------------------------------------------------
# 2. Check input GeoPackage
# ------------------------------------------------------------

print("Checking input GeoPackage:")
print(INPUT_GPKG)

if not INPUT_GPKG.exists():
    raise FileNotFoundError(f"Input GeoPackage not found:\n{INPUT_GPKG}")

print("Good: input GeoPackage exists.")


# ------------------------------------------------------------
# 3. Create interim Census folder and geodatabase
# ------------------------------------------------------------

OUT_FOLDER.mkdir(parents=True, exist_ok=True)

print("\nChecking output folder:")
print(OUT_FOLDER)

if not arcpy.Exists(str(OUT_GDB)):
    arcpy.management.CreateFileGDB(str(OUT_FOLDER), OUT_GDB.name)
    print("Created geodatabase:")
    print(OUT_GDB)
else:
    print("Geodatabase already exists:")
    print(OUT_GDB)


# ------------------------------------------------------------
# 4. Read the feature class inside the GeoPackage
# ------------------------------------------------------------

arcpy.env.workspace = str(INPUT_GPKG)

INPUT_FC = "main.walktime_polygons_5_10_20_30min"

print("\nUsing input feature class:")
print(INPUT_FC)


# ------------------------------------------------------------
# 5. Select 5, 10, 20, and 30 minute polygons
# ------------------------------------------------------------

where_clause = "walktime_min IN (5, 10, 20, 30)"
TEMP_LAYER = "walktime_5_10_20_30_temp"

if arcpy.Exists(TEMP_LAYER):
    arcpy.management.Delete(TEMP_LAYER)

arcpy.management.MakeFeatureLayer(
    INPUT_FC,
    TEMP_LAYER,
    where_clause
)

selected_count = int(arcpy.management.GetCount(TEMP_LAYER)[0])

print("\nSelected records:")
print(selected_count)


# ------------------------------------------------------------
# 6. Copy selected polygons to the interim Census geodatabase
# ------------------------------------------------------------

if arcpy.Exists(str(OUT_FC)):
    arcpy.management.Delete(str(OUT_FC))
    print("\nDeleted old output feature class.")

arcpy.management.CopyFeatures(
    TEMP_LAYER,
    str(OUT_FC)
)

copied_count = int(arcpy.management.GetCount(str(OUT_FC))[0])

print("\nCopied records:")
print(copied_count)

print("\nOutput created:")
print(OUT_FC)


# ------------------------------------------------------------
# 7. Basic final check
# ------------------------------------------------------------

if copied_count != 456:
    print("\nWARNING: Expected 456 records for 114 sites x 4 walk times.")
else:
    print("\nDone. Census Enrich prep layer is ready.")
