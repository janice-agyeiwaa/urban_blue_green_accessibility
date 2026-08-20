# 00_create_dtm_slope_raster.py

from pathlib import Path
import arcpy
from arcpy.sa import Slope


# ============================================================
# STEP 0: CREATE DTM SLOPE RASTER FOR HAPTIC WORKFLOW
# ============================================================
# Creates one full-area DTM-derived slope raster in degrees.
# This can be reused by the haptic full script and test scripts.
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[4]

DTM = PROJECT_ROOT / "data" / "raw" / "dtm.tif"

INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "haptic"
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

SLOPE_GDB = INTERIM_DIR / "haptic_slope_rasters.gdb"

if not arcpy.Exists(str(SLOPE_GDB)):
    arcpy.management.CreateFileGDB(
        out_folder_path=str(INTERIM_DIR),
        out_name="haptic_slope_rasters.gdb"
    )

SLOPE_RASTER = str(SLOPE_GDB / "dtm_slope_degrees")


# ============================================================
# ArcPy setup
# ============================================================

arcpy.env.overwriteOutput = True
arcpy.env.workspace = str(SLOPE_GDB)
arcpy.env.scratchWorkspace = str(SLOPE_GDB)

arcpy.CheckOutExtension("Spatial")


# ============================================================
# Check input
# ============================================================

if not arcpy.Exists(str(DTM)):
    raise FileNotFoundError(f"DTM not found: {DTM}")

print("DTM found:")
print(DTM)


# ============================================================
# Create slope raster
# ============================================================

print("\nCreating DTM slope raster in degrees...")

if arcpy.Exists(SLOPE_RASTER):
    arcpy.management.Delete(SLOPE_RASTER)

slope = Slope(
    in_raster=str(DTM),
    output_measurement="DEGREE"
)

slope.save(SLOPE_RASTER)

print("\nSaved DTM slope raster:")
print(SLOPE_RASTER)

print("\nDone.")
