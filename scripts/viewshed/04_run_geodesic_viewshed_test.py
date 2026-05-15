from pathlib import Path
import arcpy
from arcpy.sa import Viewshed2, Raster, Con

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

# Outputs
output_folder = project_folder / "data" / "processed" / "viewshed"
output_gdb = output_folder / "viewshed_outputs.gdb"

park_id = 129  # Marina Park
observer_height_m = 1.6
analysis_buffer_m = 1000

park_observers = output_gdb / f"tmp_observers_park_{park_id}"
analysis_area = output_gdb / f"tmp_analysis_area_park_{park_id}"
dsm_clip = output_gdb / f"tmp_dsm_clip_park_{park_id}"
viewshed_raster = output_gdb / f"tmp_viewshed_park_{park_id}"

# Final output to keep
visible_water_raster = output_gdb / f"visible_water_park_test_{park_id}"

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
}.items():
    print(f"\nChecking {name}:")
    print(path)

    if not arcpy.Exists(str(path)):
        raise FileNotFoundError(f"Missing input: {path}")

    print("Found.")

# -------------------------
# Select Marina observers
# -------------------------
where_clause = f"park_num = {park_id}"

print(f"\nSelecting observers for park {park_id}...")

arcpy.conversion.ExportFeatures(
    in_features=str(observer_points),
    out_features=str(park_observers),
    where_clause=where_clause
)

observer_count = int(arcpy.management.GetCount(str(park_observers))[0])
print("Observer count:", observer_count)

if observer_count == 0:
    raise ValueError("No observer points found for this park.")

# -------------------------
# Create local analysis area from observers
# -------------------------
# This limits the DSM/viewshed processing area around Marina observers.
print("\nCreating local analysis area...")

arcpy.analysis.Buffer(
    in_features=str(park_observers),
    out_feature_class=str(analysis_area),
    buffer_distance_or_field=f"{analysis_buffer_m} Meters",
    dissolve_option="ALL"
)

# -------------------------
# Clip DSM to local analysis area
# -------------------------
print("Clipping DSM...")

arcpy.management.Clip(
    in_raster=str(dsm),
    rectangle="#",
    out_raster=str(dsm_clip),
    in_template_dataset=str(analysis_area),
    nodata_value="#",
    clipping_geometry="ClippingGeometry",
    maintain_clipping_extent="MAINTAIN_EXTENT"
)

# Set raster environment to local DSM clip
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
print("Saved temporary viewshed raster:", viewshed_raster)

# -------------------------
# Visible water using LCC2020 water/not-water raster
# -------------------------
print("\nCalculating visible water using LCC2020 water raster...")

vs = Raster(str(viewshed_raster))
lcc = Raster(str(lcc_water_raster))

# LCC2020_wateronot:
# 0 = not water
# 1 = water
visible_water = Con((vs > 0) & (lcc == 1), 1, 0)
visible_water.save(str(visible_water_raster))

print("Saved visible water raster:", visible_water_raster)

# -------------------------
# Area summary
# -------------------------
print("\nSummarizing visible water area...")

cell_size_x = float(arcpy.Describe(str(dsm_clip)).meanCellWidth)
cell_size_y = float(arcpy.Describe(str(dsm_clip)).meanCellHeight)
cell_area_m2 = cell_size_x * cell_size_y

arcpy.management.BuildRasterAttributeTable(
    in_raster=str(visible_water_raster),
    overwrite="Overwrite"
)

fields = [f.name for f in arcpy.ListFields(str(visible_water_raster))]
value_field = "VALUE" if "VALUE" in fields else "Value"
count_field = "COUNT" if "COUNT" in fields else "Count"

visible_water_cells = 0

with arcpy.da.SearchCursor(str(visible_water_raster), [value_field, count_field]) as cursor:
    for value, count in cursor:
        if int(value) == 1:
            visible_water_cells = count

visible_water_area_m2 = visible_water_cells * cell_area_m2

print("\nRESULT")
print("Park:", park_id)
print("Observer height m:", observer_height_m)
print("Visible water cells:", visible_water_cells)
print("Cell area m²:", cell_area_m2)
print("Visible water area m²:", round(visible_water_area_m2, 2))
print("Avery Marina reference m²:", 204565)

print("\nOutputs kept:")
print("Visible water raster:", visible_water_raster)

# -------------------------
# Clean temporary outputs
# -------------------------
for item in [park_observers, analysis_area, dsm_clip, viewshed_raster]:
    try:
        if arcpy.Exists(str(item)):
            arcpy.management.Delete(str(item))
    except Exception:
        pass

print("\nDone.")