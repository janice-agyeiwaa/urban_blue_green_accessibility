from pathlib import Path
import arcpy
from arcpy.sa import Viewshed2, Raster, Con
import csv

# -------------------------
# Project paths
# -------------------------
project_folder = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\weekly_reports\urban_blue_green_accessibility"
)

# Inputs
dsm = project_folder / "data" / "raw" / "dsm.tif"
lcc_water_raster = project_folder / "data" / "raw" / "LCC2020_wateronot.tif"

viewshed_inputs_gdb = project_folder / "data" / "processed" / "viewshed" / "viewshed_inputs.gdb"
observer_points = viewshed_inputs_gdb / "pilot_10_observer_points_projected"

pilot_parks_csv = project_folder / "data" / "processed" / "reach" / "pilot_10_parks.csv"

# Outputs
output_folder = project_folder / "data" / "processed" / "viewshed"
output_gdb = output_folder / "viewshed_outputs.gdb"
summary_csv = output_folder / "pilot_10_visible_water_summary.csv"

# Settings
observer_height_m = 1.6
analysis_buffer_m = 1000

# -------------------------
# Environment
# -------------------------
arcpy.env.overwriteOutput = True
arcpy.CheckOutExtension("Spatial")

if not arcpy.Exists(str(output_gdb)):
    arcpy.management.CreateFileGDB(str(output_folder), "viewshed_outputs.gdb")

# -------------------------
# Check inputs
# -------------------------
for name, path in {
    "DSM": dsm,
    "LCC water raster": lcc_water_raster,
    "Observer points": observer_points,
    "Pilot parks CSV": pilot_parks_csv,
}.items():
    print(f"\nChecking {name}:")
    print(path)

    if not arcpy.Exists(str(path)):
        raise FileNotFoundError(f"Missing input: {path}")

    print("Found.")

# -------------------------
# Read pilot parks
# -------------------------
pilot_parks = []

with open(pilot_parks_csv, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        pilot_parks.append({
            "park_num": int(row["park_num"]),
            "PARK_NAME": row["PARK_NAME"].strip()
        })

print("\nPilot parks:", len(pilot_parks))

summary_rows = []

# -------------------------
# Helper function
# -------------------------
def clear_envs():
    arcpy.ClearEnvironment("extent")
    arcpy.ClearEnvironment("snapRaster")
    arcpy.ClearEnvironment("cellSize")
    arcpy.ClearEnvironment("outputCoordinateSystem")


def delete_if_exists(items):
    for item in items:
        try:
            if arcpy.Exists(str(item)):
                arcpy.management.Delete(str(item))
        except Exception:
            pass


def count_value_1_cells(raster_path):
    arcpy.management.BuildRasterAttributeTable(
        in_raster=str(raster_path),
        overwrite="Overwrite"
    )

    fields = [f.name for f in arcpy.ListFields(str(raster_path))]
    value_field = "VALUE" if "VALUE" in fields else "Value"
    count_field = "COUNT" if "COUNT" in fields else "Count"

    value_1_cells = 0

    with arcpy.da.SearchCursor(str(raster_path), [value_field, count_field]) as cursor:
        for value, count in cursor:
            if int(value) == 1:
                value_1_cells = count

    return value_1_cells

# -------------------------
# Process each park
# -------------------------
for park in pilot_parks:
    park_id = park["park_num"]
    park_name = park["PARK_NAME"]

    print("\n" + "=" * 70)
    print(f"Processing park {park_id}: {park_name}")
    print("=" * 70)

    # Clear previous park raster environments before selecting features
    clear_envs()

    park_field = arcpy.AddFieldDelimiters(str(observer_points), "park_num")
    where_clause = f"{park_field} = {park_id}"

    # Temporary outputs
    park_observers = output_gdb / f"tmp_observers_park_{park_id}"
    analysis_area = output_gdb / f"tmp_analysis_area_park_{park_id}"
    dsm_clip = output_gdb / f"tmp_dsm_clip_park_{park_id}"
    viewshed_raster = output_gdb / f"tmp_viewshed_park_{park_id}"

    # Final output to keep
    visible_water_raster = output_gdb / f"visible_water_park_{park_id}"

    # Delete leftovers before creating outputs
    delete_if_exists([
        park_observers,
        analysis_area,
        dsm_clip,
        viewshed_raster,
        visible_water_raster
    ])

    try:
        # -------------------------
        # Select park observers
        # -------------------------
        arcpy.conversion.ExportFeatures(
            in_features=str(observer_points),
            out_features=str(park_observers),
            where_clause=where_clause
        )

        observer_count = int(arcpy.management.GetCount(str(park_observers))[0])
        print("Observer count:", observer_count)

        if observer_count == 0:
            raise ValueError(f"No observer points found for park {park_id}.")

        # -------------------------
        # Create local analysis area
        # -------------------------
        arcpy.analysis.Buffer(
            in_features=str(park_observers),
            out_feature_class=str(analysis_area),
            buffer_distance_or_field=f"{analysis_buffer_m} Meters",
            dissolve_option="ALL"
        )

        # -------------------------
        # Clip DSM
        # -------------------------
        arcpy.management.Clip(
            in_raster=str(dsm),
            rectangle="#",
            out_raster=str(dsm_clip),
            in_template_dataset=str(analysis_area),
            nodata_value="#",
            clipping_geometry="ClippingGeometry",
            maintain_clipping_extent="MAINTAIN_EXTENT"
        )

        # Set raster environment only after DSM clip is created
        arcpy.env.snapRaster = str(dsm_clip)
        arcpy.env.cellSize = str(dsm_clip)
        arcpy.env.extent = str(dsm_clip)
        arcpy.env.outputCoordinateSystem = arcpy.Describe(str(dsm_clip)).spatialReference

        # -------------------------
        # Run Geodesic Viewshed
        # -------------------------
        print("Running Geodesic Viewshed...")

        out_vs = Viewshed2(
            in_raster=str(dsm_clip),
            in_observer_features=str(park_observers),
            out_agl_raster="",
            analysis_type="FREQUENCY",
            vertical_error="",
            out_observer_region_relationship_table="",
            observer_offset=observer_height_m,
            analysis_method="ALL_SIGHTLINES"
        )

        out_vs.save(str(viewshed_raster))

        # -------------------------
        # Calculate visible water using LCC2020 water raster
        # -------------------------
        print("Calculating visible water...")

        vs = Raster(str(viewshed_raster))
        lcc = Raster(str(lcc_water_raster))

        # LCC2020_wateronot:
        # 0 = not water
        # 1 = water
        visible_water = Con((vs > 0) & (lcc == 1), 1, 0)
        visible_water.save(str(visible_water_raster))

        # -------------------------
        # Area summary
        # -------------------------
        cell_size_x = float(arcpy.Describe(str(dsm_clip)).meanCellWidth)
        cell_size_y = float(arcpy.Describe(str(dsm_clip)).meanCellHeight)
        cell_area_m2 = cell_size_x * cell_size_y

        visible_water_cells = count_value_1_cells(visible_water_raster)
        visible_water_area_m2 = visible_water_cells * cell_area_m2

        print("Visible water cells:", visible_water_cells)
        print("Cell area m²:", round(cell_area_m2, 4))
        print("Visible water area m²:", round(visible_water_area_m2, 2))

        summary_rows.append({
            "park_num": park_id,
            "PARK_NAME": park_name,
            "observer_count": observer_count,
            "observer_height_m": observer_height_m,
            "analysis_buffer_m": analysis_buffer_m,
            "visible_water_cells": visible_water_cells,
            "cell_area_m2": round(cell_area_m2, 4),
            "visible_water_area_m2": round(visible_water_area_m2, 2),
            "visible_water_raster": str(visible_water_raster)
        })

    finally:
        # Clear environments before deleting temporary rasters
        clear_envs()

        # Delete temporary outputs only
        delete_if_exists([
            park_observers,
            analysis_area,
            dsm_clip,
            viewshed_raster
        ])

# -------------------------
# Save summary table
# -------------------------
fieldnames = [
    "park_num",
    "PARK_NAME",
    "observer_count",
    "observer_height_m",
    "analysis_buffer_m",
    "visible_water_cells",
    "cell_area_m2",
    "visible_water_area_m2",
    "visible_water_raster"
]

with open(summary_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(summary_rows)

print("\nDone.")
print("Saved summary:", summary_csv)
print("Kept final visible-water rasters in:", output_gdb)