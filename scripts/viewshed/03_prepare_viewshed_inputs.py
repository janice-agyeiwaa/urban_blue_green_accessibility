from pathlib import Path
import arcpy

# -------------------------
# Project paths
# -------------------------
project_folder = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\weekly_reports\urban_blue_green_accessibility"
)

# Inputs
dsm = project_folder / "data" / "raw" / "dsm.tif"

observer_points = (
    project_folder
    / "data"
    / "processed"
    / "viewshed"
    / "pilot_10_observer_points.gpkg"
    / "pilot_10_observer_points"
)

# Outputs
output_folder = project_folder / "data" / "processed" / "viewshed"
output_gdb = output_folder / "viewshed_inputs.gdb"

observer_projected = output_gdb / "pilot_10_observer_points_projected"

# -------------------------
# Environment
# -------------------------
arcpy.env.overwriteOutput = True

output_folder.mkdir(parents=True, exist_ok=True)

if not arcpy.Exists(str(output_gdb)):
    arcpy.management.CreateFileGDB(
        out_folder_path=str(output_folder),
        out_name="viewshed_inputs.gdb"
    )

print("Output GDB:", output_gdb)

# -------------------------
# Check inputs
# -------------------------
inputs = {
    "DSM": dsm,
    "Observer points": observer_points,
}

print("\nChecking inputs...")

for name, path in inputs.items():
    print(f"\n{name}:")
    print(path)

    if not arcpy.Exists(str(path)):
        raise FileNotFoundError(f"Missing input: {path}")

    print("Found.")

# -------------------------
# Get DSM spatial reference
# -------------------------
dsm_desc = arcpy.Describe(str(dsm))
dsm_sr = dsm_desc.spatialReference

print("\nDSM information:")
print("Spatial reference:", dsm_sr.name)
print("Cell size X:", dsm_desc.meanCellWidth)
print("Cell size Y:", dsm_desc.meanCellHeight)
print("Pixel type:", dsm_desc.pixelType)
print("Extent:", dsm_desc.extent)

# -------------------------
# Project observer points to DSM CRS
# -------------------------
print("\nProjecting observer points to DSM CRS...")

arcpy.management.Project(
    in_dataset=str(observer_points),
    out_dataset=str(observer_projected),
    out_coor_system=dsm_sr
)

print("Saved:", observer_projected)

# -------------------------
# Final check
# -------------------------
desc = arcpy.Describe(str(observer_projected))

print("\nPrepared observer points:")
print("Path:", observer_projected)
print("Data type:", desc.dataType)
print("Spatial reference:", desc.spatialReference.name)
print("Extent:", desc.extent)

count = int(arcpy.management.GetCount(str(observer_projected))[0])
print("Observer point count:", count)

print("\nDone.")