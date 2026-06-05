# 02_calculate_terrain_based_haptic_proxy_arcpy.py

from pathlib import Path
import arcpy
from arcpy.sa import Slope, ZonalStatisticsAsTable
import pandas as pd


# ============================================================
# STEP 2: TERRAIN-BASED HAPTIC ACCESS PROXY
# ArcPy version
# ============================================================
# Metric:
# gentle_shoreline_ratio = gentle_shoreline_length_m / shoreline_length_m
#
# Method:
# 1. Split shoreline into 20 m segments.
# 2. Create 10 m buffers around shoreline segments.
# 3. Clip/intersect buffers with park land buffer to approximate land-side area.
# 4. Derive slope from DSM.
# 5. Calculate mean slope per shoreline segment buffer.
# 6. Classify shoreline segment as gentle if mean slope <= 10 degrees.
# 7. Summarize gentle shoreline length by park.
# ============================================================


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

PARKS_GDB = PROJECT_ROOT / "data" / "raw" / "Park_Extraction_Project.gdb"
DSM = PROJECT_ROOT / "data" / "raw" / "dsm.tif"

INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "haptic"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "haptic"

INTERIM_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

TEMP_GDB = INTERIM_DIR / "haptic_temp.gdb"

if not arcpy.Exists(str(TEMP_GDB)):
    arcpy.management.CreateFileGDB(str(INTERIM_DIR), "haptic_temp.gdb")


# ============================================================
# Input layers
# ============================================================

LAND_BUFFER = str(PARKS_GDB / "allparks_land_buffer")
SHORELINE = str(PARKS_GDB / "allparks_land_buff_Intersect")


# ============================================================
# Output paths
# ============================================================

SHORELINE_SEGMENTS = str(TEMP_GDB / "haptic_shoreline_segments")
SEGMENT_BUFFERS_RAW = str(TEMP_GDB / "haptic_segment_buffers_raw")
LANDSIDE_BUFFERS = str(TEMP_GDB / "haptic_shoreline_landside_buffers")

SLOPE_RASTER = str(TEMP_GDB / "dsm_slope_degrees")
ZONAL_TABLE = str(TEMP_GDB / "segment_slope_stats")

SEGMENTS_REVIEW_OUTPUT = str(INTERIM_DIR / "haptic_shoreline_segments.gpkg")
BUFFERS_REVIEW_OUTPUT = str(INTERIM_DIR / "haptic_shoreline_landside_buffers.gpkg")

OUTPUT_CSV = PROCESSED_DIR / "terrain_based_haptic_proxy.csv"


# ============================================================
# Fields and settings
# ============================================================

PARK_ID_FIELD = "park_num"
PARK_NAME_FIELD = "PARK_NAME"
MUNI_FIELD = "MUNI"

SEGMENT_LENGTH_M = 20
LANDSIDE_BUFFER_M = 10
GENTLE_SLOPE_THRESHOLD_DEGREES = 10


# ============================================================
# ArcPy setup
# ============================================================

arcpy.env.overwriteOutput = True
arcpy.env.workspace = str(TEMP_GDB)
arcpy.env.scratchWorkspace = str(TEMP_GDB)

arcpy.CheckOutExtension("Spatial")


# ============================================================
# Check inputs
# ============================================================

for name, path in {
    "Land buffer": LAND_BUFFER,
    "Shoreline polyline": SHORELINE,
    "DSM": str(DSM),
}.items():
    if not arcpy.Exists(path):
        raise FileNotFoundError(f"Missing input: {name} -> {path}")
    print(f"{name}: found")


# ============================================================
# Clean old temp outputs
# ============================================================

for item in [
    SHORELINE_SEGMENTS,
    SEGMENT_BUFFERS_RAW,
    LANDSIDE_BUFFERS,
    SLOPE_RASTER,
    ZONAL_TABLE,
]:
    if arcpy.Exists(item):
        arcpy.management.Delete(item)


# ============================================================
# Step 1: Create shoreline segments
# ============================================================

print("\nCreating shoreline segments...")

# Copy shoreline to temp feature class
shoreline_temp = str(TEMP_GDB / "shoreline_temp")

if arcpy.Exists(shoreline_temp):
    arcpy.management.Delete(shoreline_temp)

arcpy.management.CopyFeatures(SHORELINE, shoreline_temp)

# Add unique shoreline feature ID
if "shoreline_oid" not in [f.name for f in arcpy.ListFields(shoreline_temp)]:
    arcpy.management.AddField(shoreline_temp, "shoreline_oid", "LONG")

with arcpy.da.UpdateCursor(shoreline_temp, ["OID@", "shoreline_oid"]) as cursor:
    for oid, _ in cursor:
        cursor.updateRow([oid, oid])

# Split shoreline lines every 20 m
arcpy.management.GeneratePointsAlongLines(
    Input_Features=shoreline_temp,
    Output_Feature_Class=str(TEMP_GDB / "tmp_split_points"),
    Point_Placement="DISTANCE",
    Distance=f"{SEGMENT_LENGTH_M} Meters",
    Include_End_Points="END_POINTS"
)

# Split line at generated points
split_points = str(TEMP_GDB / "tmp_split_points")

arcpy.management.SplitLineAtPoint(
    in_features=shoreline_temp,
    point_features=split_points,
    out_feature_class=SHORELINE_SEGMENTS,
    search_radius="1 Meters"
)

# Add global segment ID and segment length
fields = [f.name for f in arcpy.ListFields(SHORELINE_SEGMENTS)]

if "global_segment_id" not in fields:
    arcpy.management.AddField(SHORELINE_SEGMENTS, "global_segment_id", "LONG")

if "segment_length_m" not in fields:
    arcpy.management.AddField(SHORELINE_SEGMENTS, "segment_length_m", "DOUBLE")

with arcpy.da.UpdateCursor(
    SHORELINE_SEGMENTS,
    ["OID@", "global_segment_id", "segment_length_m", "SHAPE@"]
) as cursor:
    for oid, _, _, geom in cursor:
        cursor.updateRow([oid, oid, geom.length, geom])

segment_count = int(arcpy.management.GetCount(SHORELINE_SEGMENTS)[0])
print("Shoreline segments:", segment_count)


# ============================================================
# Step 2: Create segment buffers and clip to park land buffer
# ============================================================

print("\nCreating 10 m segment buffers...")

arcpy.analysis.Buffer(
    in_features=SHORELINE_SEGMENTS,
    out_feature_class=SEGMENT_BUFFERS_RAW,
    buffer_distance_or_field=f"{LANDSIDE_BUFFER_M} Meters",
    dissolve_option="NONE"
)

print("Clipping/intersecting buffers with park land buffer...")

# Intersect keeps only buffer area that overlaps park land buffer
arcpy.analysis.Intersect(
    in_features=[SEGMENT_BUFFERS_RAW, LAND_BUFFER],
    out_feature_class=LANDSIDE_BUFFERS,
    join_attributes="ALL",
    output_type="INPUT"
)

buffer_count = int(arcpy.management.GetCount(LANDSIDE_BUFFERS)[0])
print("Land-side buffers:", buffer_count)


# ============================================================
# Step 3: Calculate DSM slope
# ============================================================

print("\nCalculating DSM slope in degrees...")

if arcpy.Exists(SLOPE_RASTER):
    arcpy.management.Delete(SLOPE_RASTER)

slope = Slope(
    in_raster=str(DSM),
    output_measurement="DEGREE"
)

slope.save(SLOPE_RASTER)

print("Saved slope raster:")
print(SLOPE_RASTER)


# ============================================================
# Step 4: Zonal statistics by shoreline segment buffer
# ============================================================

print("\nCalculating mean slope by shoreline segment buffer...")

if arcpy.Exists(ZONAL_TABLE):
    arcpy.management.Delete(ZONAL_TABLE)

ZonalStatisticsAsTable(
    in_zone_data=LANDSIDE_BUFFERS,
    zone_field="global_segment_id",
    in_value_raster=SLOPE_RASTER,
    out_table=ZONAL_TABLE,
    ignore_nodata="DATA",
    statistics_type="MEAN"
)

print("Saved zonal table:")
print(ZONAL_TABLE)


# ============================================================
# Step 5: Read segment attributes
# ============================================================

print("\nReading segment attributes...")

segment_rows = []

segment_fields = [
    "global_segment_id",
    PARK_ID_FIELD,
    PARK_NAME_FIELD,
    "segment_length_m",
]

available_segment_fields = [f.name for f in arcpy.ListFields(SHORELINE_SEGMENTS)]

# MUNI may not be on shoreline layer, so we join it later from land buffer.
with arcpy.da.SearchCursor(SHORELINE_SEGMENTS, segment_fields) as cursor:
    for global_segment_id, park_num, park_name, segment_length_m in cursor:
        segment_rows.append({
            "global_segment_id": int(global_segment_id),
            PARK_ID_FIELD: int(park_num),
            PARK_NAME_FIELD: park_name,
            "segment_length_m": float(segment_length_m),
        })

segments_df = pd.DataFrame(segment_rows)


# ============================================================
# Step 6: Read MUNI from land buffer
# ============================================================

print("Reading municipality from land buffer...")

park_rows = []

with arcpy.da.SearchCursor(
    LAND_BUFFER,
    [PARK_ID_FIELD, PARK_NAME_FIELD, MUNI_FIELD]
) as cursor:
    for park_num, park_name, muni in cursor:
        park_rows.append({
            PARK_ID_FIELD: int(park_num),
            PARK_NAME_FIELD: park_name,
            MUNI_FIELD: muni,
        })

parks_df = pd.DataFrame(park_rows).drop_duplicates(subset=[PARK_ID_FIELD])


# ============================================================
# Step 7: Read zonal slope table
# ============================================================

print("Reading zonal slope results...")

zonal_rows = []

with arcpy.da.SearchCursor(
    ZONAL_TABLE,
    ["global_segment_id", "MEAN"]
) as cursor:
    for global_segment_id, mean_slope in cursor:
        zonal_rows.append({
            "global_segment_id": int(global_segment_id),
            "mean_slope_degrees": mean_slope,
        })

zonal_df = pd.DataFrame(zonal_rows)

print("Zonal rows:", len(zonal_df))


# ============================================================
# Step 8: Join slope to segments and classify
# ============================================================

print("\nClassifying gentle shoreline segments...")

segments_df = segments_df.merge(
    zonal_df,
    on="global_segment_id",
    how="left"
)

segments_df = segments_df.merge(
    parks_df[[PARK_ID_FIELD, MUNI_FIELD]],
    on=PARK_ID_FIELD,
    how="left"
)

segments_df["gentle_shoreline"] = (
    segments_df["mean_slope_degrees"] <= GENTLE_SLOPE_THRESHOLD_DEGREES
)

# If mean_slope is missing, treat as steep/unknown
segments_df["gentle_shoreline"] = segments_df["gentle_shoreline"].fillna(False)

segments_df["gentle_length_m"] = segments_df.apply(
    lambda row: row["segment_length_m"]
    if row["gentle_shoreline"]
    else 0,
    axis=1
)

segments_df["steep_or_unknown_length_m"] = segments_df.apply(
    lambda row: row["segment_length_m"]
    if not row["gentle_shoreline"]
    else 0,
    axis=1
)


# ============================================================
# Step 9: Summarize by park
# ============================================================

print("Summarizing by park...")

summary = (
    segments_df
    .groupby([PARK_ID_FIELD, PARK_NAME_FIELD, MUNI_FIELD], dropna=False)
    .agg(
        shoreline_length_m=("segment_length_m", "sum"),
        gentle_shoreline_length_m=("gentle_length_m", "sum"),
        steep_or_unknown_shoreline_length_m=("steep_or_unknown_length_m", "sum"),
        mean_shoreline_slope_degrees=("mean_slope_degrees", "mean"),
        segment_count=("global_segment_id", "count"),
    )
    .reset_index()
)

summary["gentle_shoreline_ratio"] = (
    summary["gentle_shoreline_length_m"] / summary["shoreline_length_m"]
)

summary["gentle_shoreline_percent"] = (
    summary["gentle_shoreline_ratio"] * 100
)

summary["slope_threshold_degrees"] = GENTLE_SLOPE_THRESHOLD_DEGREES
summary["segment_length_m_used"] = SEGMENT_LENGTH_M
summary["landside_buffer_m_used"] = LANDSIDE_BUFFER_M

summary = summary.sort_values(PARK_ID_FIELD)

summary.to_csv(OUTPUT_CSV, index=False)

print("\nSaved terrain-based haptic proxy:")
print(OUTPUT_CSV)


# ============================================================
# Step 10: Save review layers to interim
# ============================================================

print("\nSaving review layers...")

for output in [SEGMENTS_REVIEW_OUTPUT, BUFFERS_REVIEW_OUTPUT]:
    output_path = Path(output)
    if output_path.exists():
        try:
            output_path.unlink()
        except PermissionError:
            print(f"Could not overwrite because file is open: {output_path}")

if not Path(SEGMENTS_REVIEW_OUTPUT).exists():
    arcpy.conversion.ExportFeatures(
        in_features=SHORELINE_SEGMENTS,
        out_features=SEGMENTS_REVIEW_OUTPUT,
    )

if not Path(BUFFERS_REVIEW_OUTPUT).exists():
    arcpy.conversion.ExportFeatures(
        in_features=LANDSIDE_BUFFERS,
        out_features=BUFFERS_REVIEW_OUTPUT,
    )

print("Saved shoreline segments review layer:")
print(SEGMENTS_REVIEW_OUTPUT)

print("Saved land-side buffers review layer:")
print(BUFFERS_REVIEW_OUTPUT)


# ============================================================
# Summary
# ============================================================

print("\nSummary:")
print("Rows:", len(summary))
print("Parks with shoreline:", len(summary))
print("Slope threshold degrees:", GENTLE_SLOPE_THRESHOLD_DEGREES)
print("Segment length m:", SEGMENT_LENGTH_M)
print("Land-side buffer m:", LANDSIDE_BUFFER_M)

print("\nFirst 10 rows:")
print(summary.head(10).to_string(index=False))

print("\nDone.")