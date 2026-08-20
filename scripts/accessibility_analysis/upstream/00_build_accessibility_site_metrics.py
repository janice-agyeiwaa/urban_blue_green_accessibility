# ============================================================
# Build the 114-row accessibility site-metrics input for Paper 3.
#
# Outputs:
# - data/processed/accessibility_analysis/accessibility_site_metrics_114.csv
#
# Notes:
# - access_points_per_km_boundary uses park perimeter.
# - visual_access_ratio uses visible water area divided by total
#   water area within the same 1 km visual-analysis area.
# - This version uses the binary LCC water raster:
#   0 = non-water
#   1 = water
# ============================================================

import os
from pathlib import Path
import pandas as pd
import arcpy
from arcpy.sa import Raster, Con, ZonalStatisticsAsTable

arcpy.env.overwriteOutput = True
arcpy.CheckOutExtension("Spatial")

# ------------------------------------------------------------
# Project root
# ------------------------------------------------------------
project_root = str(Path(__file__).resolve().parents[3])

# ------------------------------------------------------------
# Input paths
# ------------------------------------------------------------

reach_csv = os.path.join(
    project_root, "data", "processed", "reach", "reach_independent_variables.csv"
)
haptic_csv = os.path.join(
    project_root,
    "data",
    "processed",
    "haptic",
    "avery_shoreline_perimeter_ratio.csv",
)
viewshed_csv = os.path.join(
    project_root,
    "data",
    "processed",
    "viewshed",
    "allparks_viewshed_visible_water_area_spacing_access_fallback.csv",
)

park_polygon_fc = os.path.join(
    project_root, "data", "raw", "Park_Extraction_Project.gdb", "allparks_land_buffer"
)

observer_points_fc = os.path.join(
    project_root,
    "data",
    "interim",
    "viewshed",
    "observer_points_spacing_access_fallback.gpkg",
    "main.observer_points_spacing_access_fallback",
)

# Your raster path
landcover_water_raster_path = os.path.join(
    project_root, "data", "raw", "LCC2020_wateronot.tif", "Band_1"
)

# Fallback path, in case ArcPy does not accept the Band_1 path
landcover_water_raster_fallback_path = os.path.join(
    project_root, "data", "raw", "LCC2020_wateronot.tif"
)

# From your raster table:
# 0 = non-water
# 1 = water
water_class_value = 1

# ------------------------------------------------------------
# Field names
# ------------------------------------------------------------
park_polygon_id_field = "park_num"
observer_id_field = "park_num"

# ------------------------------------------------------------
# Output paths
# ------------------------------------------------------------
output_dir = os.path.join(
    project_root,
    "data",
    "processed",
    "accessibility_analysis"
)

os.makedirs(output_dir, exist_ok=True)

output_csv = os.path.join(
    output_dir,
    "accessibility_site_metrics_114.csv"
)

scratch_dir = os.path.join(project_root, "data", "interim", "accessibility_analysis")
os.makedirs(scratch_dir, exist_ok=True)
scratch_gdb = os.path.join(
    scratch_dir,
    "access_adjustment_scratch.gdb"
)

if not arcpy.Exists(scratch_gdb):
    arcpy.management.CreateFileGDB(
        scratch_dir,
        "access_adjustment_scratch.gdb"
    )

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def field_exists(table, field_name):
    return field_name in [f.name for f in arcpy.ListFields(table)]


def clean_park_num_for_merge(df, field="park_num"):
    """
    Forces park_num to a consistent text format for pandas merges.
    """
    df[field] = (
        df[field]
        .astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
    )
    return df


def sql_value(value):
    """
    Format a value safely for ArcGIS SQL.
    """
    return str(value).replace("'", "''")


def load_source_metrics():
    """Merge the reach, haptic, and viewshed tables in memory."""
    reach = pd.read_csv(reach_csv)
    haptic = pd.read_csv(haptic_csv)
    viewshed = pd.read_csv(viewshed_csv)

    for label, frame in {
        "reach": reach,
        "haptic": haptic,
        "viewshed": viewshed,
    }.items():
        if "park_num" not in frame.columns:
            raise ValueError(f"park_num is missing from the {label} source table.")
        frame["park_num"] = frame["park_num"].astype(int)

    reach_fields = [
        "park_num",
        "PARK_NAME",
        "access_point_count",
        "bus_stops_05min",
        "bus_stops_10min",
        "bus_stops_20min",
        "bus_stops_30min",
    ]
    if "MUNI" in reach.columns:
        reach_fields.append("MUNI")

    haptic_fields = ["park_num", "shoreline_to_perimeter_ratio"]
    if "MUNI" in haptic.columns:
        haptic_fields.append("MUNI")

    viewshed_fields = ["park_num", "visible_water_area_m2"]
    if "MUNI" in viewshed.columns:
        viewshed_fields.append("MUNI")

    merged = reach[reach_fields].merge(
        haptic[haptic_fields].rename(columns={"MUNI": "MUNI_haptic"}),
        on="park_num",
        how="left",
        validate="one_to_one",
    )
    merged = merged.merge(
        viewshed[viewshed_fields].rename(columns={"MUNI": "MUNI_viewshed"}),
        on="park_num",
        how="left",
        validate="one_to_one",
    )

    municipality = pd.Series(index=merged.index, dtype="object")
    for field in ["MUNI", "MUNI_haptic", "MUNI_viewshed"]:
        if field in merged.columns:
            municipality = municipality.fillna(merged[field])

    return pd.DataFrame(
        {
            "park_num": merged["park_num"],
            "site_name": merged["PARK_NAME"],
            "municipality": municipality,
            "access_point_count": merged["access_point_count"],
            "haptic_access_avery": merged["shoreline_to_perimeter_ratio"],
            "visual_access_viewshed_m2": merged["visible_water_area_m2"],
            "bus_stops_5min": merged["bus_stops_05min"],
            "bus_stops_10min": merged["bus_stops_10min"],
            "bus_stops_20min": merged["bus_stops_20min"],
            "bus_stops_30min": merged["bus_stops_30min"],
        }
    )


# ------------------------------------------------------------
# 0. Check raster path
# ------------------------------------------------------------
print("\nChecking water raster...")

if arcpy.Exists(landcover_water_raster_path):
    water_raster_input = landcover_water_raster_path
elif arcpy.Exists(landcover_water_raster_fallback_path):
    water_raster_input = landcover_water_raster_fallback_path
else:
    raise FileNotFoundError(
        "Could not find the water raster using either path:\n"
        f"{landcover_water_raster_path}\n"
        f"{landcover_water_raster_fallback_path}"
    )

print("Using water raster:")
print(water_raster_input)

# ------------------------------------------------------------
# 1. Calculate park boundary length
# ------------------------------------------------------------
print("\nCalculating park boundary length...")

park_perimeter_fc = os.path.join(
    scratch_gdb,
    "park_boundary_length"
)

if arcpy.Exists(park_perimeter_fc):
    arcpy.management.Delete(park_perimeter_fc)

arcpy.management.CopyFeatures(
    park_polygon_fc,
    park_perimeter_fc
)

if not field_exists(park_perimeter_fc, "park_boundary_length_m"):
    arcpy.management.AddField(
        park_perimeter_fc,
        "park_boundary_length_m",
        "DOUBLE"
    )

arcpy.management.CalculateGeometryAttributes(
    park_perimeter_fc,
    [["park_boundary_length_m", "PERIMETER_LENGTH"]],
    length_unit="METERS"
)

perimeter_records = []

with arcpy.da.SearchCursor(
    park_perimeter_fc,
    [park_polygon_id_field, "park_boundary_length_m"]
) as cursor:
    for park_num, perimeter_m in cursor:
        perimeter_records.append(
            {
                "park_num": park_num,
                "park_boundary_length_m": perimeter_m,
                "park_boundary_length_km": perimeter_m / 1000 if perimeter_m else None
            }
        )

perimeter_df = pd.DataFrame(perimeter_records)
perimeter_df = clean_park_num_for_merge(perimeter_df, "park_num")

print("Perimeter records:", len(perimeter_df))
print("Unique parks in perimeter table:", perimeter_df["park_num"].nunique())

# ------------------------------------------------------------
# 2. Create 1 km visual-analysis area from observer points
# ------------------------------------------------------------
print("\nCreating 1 km visual-analysis areas from observer points...")

observer_buffer_fc = os.path.join(
    scratch_gdb,
    "observer_points_1000m_buffer"
)

visual_area_fc = os.path.join(
    scratch_gdb,
    "visual_analysis_area_1km_by_park"
)

if arcpy.Exists(observer_buffer_fc):
    arcpy.management.Delete(observer_buffer_fc)

if arcpy.Exists(visual_area_fc):
    arcpy.management.Delete(visual_area_fc)

arcpy.analysis.Buffer(
    observer_points_fc,
    observer_buffer_fc,
    "1000 Meters",
    dissolve_option="NONE"
)

arcpy.analysis.PairwiseDissolve(
    observer_buffer_fc,
    visual_area_fc,
    dissolve_field=observer_id_field
)

print("Visual-analysis areas created.")

# ------------------------------------------------------------
# 3. Create binary water raster
# ------------------------------------------------------------
print("\nCreating binary water raster...")

water_binary_path = os.path.join(
    scratch_gdb,
    "water_binary_for_ratio"
)

if arcpy.Exists(water_binary_path):
    arcpy.management.Delete(water_binary_path)

water_binary = Con(
    Raster(water_raster_input) == water_class_value,
    1,
    0
)

water_binary.save(water_binary_path)

cell_width = float(
    arcpy.management.GetRasterProperties(
        water_binary_path,
        "CELLSIZEX"
    ).getOutput(0)
)

cell_height = float(
    arcpy.management.GetRasterProperties(
        water_binary_path,
        "CELLSIZEY"
    ).getOutput(0)
)

cell_area_m2 = abs(cell_width * cell_height)

print("Raster cell size:", cell_width, "x", cell_height)
print("Cell area m2:", cell_area_m2)

# ------------------------------------------------------------
# 4. Calculate total water area within 1 km area by park
# ------------------------------------------------------------
print("\nCalculating total water area within 1 km visual-analysis areas...")

# NOTE:
# We calculate this park-by-park instead of using one zonal table for all parks.
# This avoids problems if 1 km visual-analysis polygons overlap.

visual_area_layer = "visual_area_layer"

if arcpy.Exists(visual_area_layer):
    arcpy.management.Delete(visual_area_layer)

arcpy.management.MakeFeatureLayer(
    visual_area_fc,
    visual_area_layer
)

water_area_records = []

park_values = []

with arcpy.da.SearchCursor(
    visual_area_fc,
    [observer_id_field]
) as cursor:
    for row in cursor:
        park_values.append(row[0])

park_values = sorted(set(park_values), key=lambda x: str(x))

for park_num in park_values:
    park_num_text = sql_value(park_num)

    where_clause = (
        f"{arcpy.AddFieldDelimiters(visual_area_fc, observer_id_field)} = '{park_num_text}'"
    )

    arcpy.management.SelectLayerByAttribute(
        visual_area_layer,
        "NEW_SELECTION",
        where_clause
    )

    selected_count = int(arcpy.management.GetCount(visual_area_layer)[0])

    if selected_count == 0:
        water_area_records.append(
            {
                "park_num": park_num,
                "total_water_area_within_1km_m2": 0
            }
        )
        continue

    temp_zonal_table = os.path.join(
        scratch_gdb,
        f"zonal_water_{str(park_num).replace('-', '_')}"
    )

    if arcpy.Exists(temp_zonal_table):
        arcpy.management.Delete(temp_zonal_table)

    ZonalStatisticsAsTable(
        in_zone_data=visual_area_layer,
        zone_field=observer_id_field,
        in_value_raster=water_binary_path,
        out_table=temp_zonal_table,
        ignore_nodata="DATA",
        statistics_type="SUM"
    )

    total_water_area_m2 = 0

    if int(arcpy.management.GetCount(temp_zonal_table)[0]) > 0:
        with arcpy.da.SearchCursor(
            temp_zonal_table,
            ["SUM"]
        ) as cursor:
            for row in cursor:
                water_cell_sum = row[0]

                if water_cell_sum is not None:
                    total_water_area_m2 = water_cell_sum * cell_area_m2

    water_area_records.append(
        {
            "park_num": park_num,
            "total_water_area_within_1km_m2": total_water_area_m2
        }
    )

arcpy.management.SelectLayerByAttribute(
    visual_area_layer,
    "CLEAR_SELECTION"
)

water_area_df = pd.DataFrame(water_area_records)
water_area_df = clean_park_num_for_merge(water_area_df, "park_num")

print("Water-area records:", len(water_area_df))
print("Unique parks in water-area table:", water_area_df["park_num"].nunique())

# ------------------------------------------------------------
# 5. Compile reach, haptic, and viewshed source metrics
# ------------------------------------------------------------
print("\nCompiling reach, haptic, and viewshed metrics...")

access_df = load_source_metrics()

access_df = clean_park_num_for_merge(access_df, "park_num")

print("Access table rows:", len(access_df))
print("Unique parks in access table:", access_df["park_num"].nunique())

# ------------------------------------------------------------
# 6. Merge perimeter and total water area
# ------------------------------------------------------------
print("\nMerging adjusted variables...")

out_df = (
    access_df
    .merge(perimeter_df, on="park_num", how="left")
    .merge(water_area_df, on="park_num", how="left")
)

out_df["total_water_area_within_1km_m2"] = (
    out_df["total_water_area_within_1km_m2"].fillna(0)
)

# ------------------------------------------------------------
# 7. Calculate adjusted access variables
# ------------------------------------------------------------
out_df["access_points_per_km_boundary"] = (
    out_df["access_point_count"] / out_df["park_boundary_length_km"]
)

out_df["visual_access_ratio"] = (
    out_df["visual_access_viewshed_m2"] / out_df["total_water_area_within_1km_m2"]
)

# Avoid infinite values if denominator is 0
out_df.loc[
    out_df["total_water_area_within_1km_m2"] == 0,
    "visual_access_ratio"
] = None

# ------------------------------------------------------------
# 8. Save output
# ------------------------------------------------------------
out_df.to_csv(output_csv, index=False)

print("\nSaved updated access table:")
print(output_csv)

# ------------------------------------------------------------
# 9. QA checks
# ------------------------------------------------------------
print("\nQA summary")
print("Rows:", len(out_df))
print("Unique parks:", out_df["park_num"].nunique())

print("\nMissing values in new fields:")
print(
    out_df[
        [
            "park_boundary_length_m",
            "park_boundary_length_km",
            "access_points_per_km_boundary",
            "total_water_area_within_1km_m2",
            "visual_access_ratio"
        ]
    ].isna().sum()
)

print("\nVisual ratio values greater than 1:")
ratio_gt_1 = out_df.loc[
    out_df["visual_access_ratio"] > 1,
    [
        "park_num",
        "site_name",
        "visual_access_viewshed_m2",
        "total_water_area_within_1km_m2",
        "visual_access_ratio"
    ]
]

print(ratio_gt_1)
print("Count greater than 1:", len(ratio_gt_1))

print("\nFirst few rows:")
print(
    out_df[
        [
            "park_num",
            "site_name",
            "access_point_count",
            "park_boundary_length_km",
            "access_points_per_km_boundary",
            "visual_access_viewshed_m2",
            "total_water_area_within_1km_m2",
            "visual_access_ratio"
        ]
    ].head()
)

print("\nDone.")
