# 03_run_viewshed_all_parks.py

from pathlib import Path
import arcpy
from arcpy.sa import Viewshed2, Raster, Con, IsNull
import pandas as pd
import time
import uuid


# ============================================================
# STEP 3: RUN VIEWSHED FOR ALL PARKS
# Uses spacing-based + access-fallback observer points
# Saves progress after each park and supports resume
# ============================================================

# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

PARKS_GDB = PROJECT_ROOT / "data" / "raw" / "Park_Extraction_Project.gdb"

DSM = PROJECT_ROOT / "data" / "raw" / "dsm.tif"
LCC_WATER_RASTER = PROJECT_ROOT / "data" / "raw" / "LCC2020_wateronot.tif"

OBSERVER_GPKG = (
    PROJECT_ROOT
    / "data"
    / "interim"
    / "viewshed"
    / "observer_points_spacing_access_fallback.gpkg"
)

INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "viewshed"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "viewshed"

INTERIM_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Optional selected parks
# ============================================================

# Use None for all parks
# Example:
# SELECTED_PARK_IDS = None

# SELECTED_PARK_IDS = [86]
SELECTED_PARK_IDS = None


if SELECTED_PARK_IDS is None:
    OUTPUT_CSV = (
        PROCESSED_DIR
        / "allparks_viewshed_visible_water_area_spacing_access_fallback.csv"
    )
else:
    selected_label = "_".join(str(pid) for pid in SELECTED_PARK_IDS)
    OUTPUT_CSV = (
        PROCESSED_DIR
        / f"selected_parks_viewshed_visible_water_area_spacing_access_fallback_{selected_label}.csv"
    )


# ============================================================
# Resume settings
# ============================================================

RESUME_FROM_EXISTING_CSV = True


# ============================================================
# Geodatabases
# ============================================================

TEMP_GDB = INTERIM_DIR / "viewshed_temp.gdb"

if not arcpy.Exists(str(TEMP_GDB)):
    arcpy.management.CreateFileGDB(str(INTERIM_DIR), "viewshed_temp.gdb")

RASTER_OUTPUT_GDB = INTERIM_DIR / "viewshed_visible_water_rasters_spacing_access_fallback.gdb"

if not arcpy.Exists(str(RASTER_OUTPUT_GDB)):
    arcpy.management.CreateFileGDB(
        str(INTERIM_DIR),
        "viewshed_visible_water_rasters_spacing_access_fallback.gdb"
    )


# ============================================================
# Inputs / settings
# ============================================================

LAND_BUFFER = str(PARKS_GDB / "allparks_land_buffer")

PARK_ID_FIELD = "park_num"
PARK_NAME_FIELD = "PARK_NAME"

OBSERVER_HEIGHT_M = 1.6
ANALYSIS_BUFFER_M = 1000

# Set this to False if you only want the CSV and want faster run time.
SAVE_VISIBLE_WATER_RASTERS = True

arcpy.env.overwriteOutput = True
arcpy.CheckOutExtension("Spatial")
arcpy.env.parallelProcessingFactor = "100%"


# ============================================================
# Helper functions
# ============================================================

def find_gpkg_layer(gpkg_path):
    """
    Finds the first feature class/layer inside a GeoPackage.
    """
    arcpy.env.workspace = str(gpkg_path)
    layers = arcpy.ListFeatureClasses()

    if not layers:
        raise ValueError(f"No feature layers found inside {gpkg_path}")

    return str(gpkg_path / layers[0])


def raster_value_count(raster_path, target_value):
    """
    Counts raster cells where VALUE == target_value.
    """
    arcpy.management.BuildRasterAttributeTable(
        in_raster=raster_path,
        overwrite="Overwrite"
    )

    fields = [f.name for f in arcpy.ListFields(raster_path)]

    value_field = "VALUE" if "VALUE" in fields else "Value"
    count_field = "COUNT" if "COUNT" in fields else "Count"

    total = 0

    with arcpy.da.SearchCursor(raster_path, [value_field, count_field]) as cursor:
        for value, count in cursor:
            if int(value) == target_value:
                total += int(count)

    return total


def clean_temp(items):
    for item in items:
        try:
            if arcpy.Exists(item):
                arcpy.management.Delete(item)
        except Exception:
            pass


def clear_envs():
    arcpy.ClearEnvironment("extent")
    arcpy.ClearEnvironment("snapRaster")
    arcpy.ClearEnvironment("cellSize")
    arcpy.ClearEnvironment("outputCoordinateSystem")
    arcpy.ClearEnvironment("workspace")
    arcpy.ClearEnvironment("scratchWorkspace")


def build_where_clause(feature_class, field_name, value):
    """
    Builds safe SQL depending on the actual field type.
    Handles cases where park_num is stored as text in the GeoPackage.
    """
    fields = {field.name: field for field in arcpy.ListFields(feature_class)}

    if field_name not in fields:
        raise ValueError(
            f"Field '{field_name}' not found in {feature_class}. "
            f"Available fields: {list(fields.keys())}"
        )

    field_obj = fields[field_name]
    field_name_sql = arcpy.AddFieldDelimiters(feature_class, field_name)

    if field_obj.type in ["String", "Guid"]:
        return f"{field_name_sql} = '{value}'"

    return f"{field_name_sql} = {value}"


def read_existing_csv(csv_path):
    """
    Reads existing progress CSV safely.
    Handles Excel/Windows-encoded CSV files.
    """
    if not csv_path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(csv_path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(csv_path, encoding="cp1252")


def save_progress(result_rows, output_csv):
    """
    Save progress after each park so the run can resume if interrupted.
    """
    if len(result_rows) == 0:
        return

    progress_df = pd.DataFrame(result_rows)

    # If a park appears more than once, keep the latest result
    progress_df = progress_df.drop_duplicates(
        subset=[PARK_ID_FIELD],
        keep="last"
    )

    progress_df = progress_df.sort_values(PARK_ID_FIELD)

    keep_cols = [
        PARK_ID_FIELD,
        PARK_NAME_FIELD,
        "MUNI",
        "observer_count",
        "visible_water_cells",
        "visible_water_area_m2",
        "runtime_minutes",
    ]

    for col in keep_cols:
        if col not in progress_df.columns:
            progress_df[col] = None

    progress_df = progress_df[keep_cols]
    progress_df.to_csv(output_csv, index=False, encoding="utf-8")


# ============================================================
# Check inputs
# ============================================================

for name, path in {
    "DSM": str(DSM),
    "LCC water raster": str(LCC_WATER_RASTER),
    "Observer GeoPackage": str(OBSERVER_GPKG),
    "Land buffer": LAND_BUFFER,
}.items():
    if not arcpy.Exists(path):
        raise FileNotFoundError(f"Missing input: {name} -> {path}")

    print(f"{name}: found")


# ============================================================
# Prepare observer layer
# ============================================================

observer_layer = find_gpkg_layer(OBSERVER_GPKG)

arcpy.env.workspace = str(TEMP_GDB)
arcpy.env.scratchWorkspace = str(TEMP_GDB)

print("\nObserver layer:")
print(observer_layer)

observers_fc = str(TEMP_GDB / "all114_observers")

if arcpy.Exists(observers_fc):
    arcpy.management.Delete(observers_fc)

arcpy.management.CopyFeatures(observer_layer, observers_fc)

print("Observer count:", arcpy.management.GetCount(observers_fc)[0])


# ============================================================
# Build base park list
# ============================================================

park_rows = []

with arcpy.da.SearchCursor(
    LAND_BUFFER,
    [PARK_ID_FIELD, PARK_NAME_FIELD, "MUNI"]
) as cursor:
    for park_num, park_name, muni in cursor:
        park_rows.append({
            PARK_ID_FIELD: int(park_num),
            PARK_NAME_FIELD: park_name,
            "MUNI": muni,
        })

parks_df = pd.DataFrame(park_rows).drop_duplicates(subset=[PARK_ID_FIELD])
parks_df = parks_df.sort_values(PARK_ID_FIELD)

if SELECTED_PARK_IDS is not None:
    parks_df = parks_df[parks_df[PARK_ID_FIELD].isin(SELECTED_PARK_IDS)].copy()


# ============================================================
# Resume from existing CSV
# ============================================================

existing_results = pd.DataFrame()

if RESUME_FROM_EXISTING_CSV and OUTPUT_CSV.exists():
    existing_results = read_existing_csv(OUTPUT_CSV)

    if (
        PARK_ID_FIELD in existing_results.columns
        and "visible_water_area_m2" in existing_results.columns
    ):
        completed_park_ids = set(
            existing_results[
                existing_results["visible_water_area_m2"].notna()
            ][PARK_ID_FIELD].astype(int)
        )

        before_skip = len(parks_df)

        parks_df = parks_df[
            ~parks_df[PARK_ID_FIELD].astype(int).isin(completed_park_ids)
        ].copy()

        print("\nResume mode ON")
        print("Existing CSV:", OUTPUT_CSV)
        print("Existing completed parks:", len(completed_park_ids))
        print("Parks skipped:", before_skip - len(parks_df))
        print("Parks remaining:", len(parks_df))
    else:
        print("\nExisting CSV found, but required fields are missing. Resume skipped.")

print("\nTotal parks to process this run:", len(parks_df))


# ============================================================
# Run viewshed park by park
# ============================================================

if len(existing_results) > 0:
    result_rows = existing_results.to_dict("records")
else:
    result_rows = []

failed_rows = []

total_parks = len(parks_df)

for count, (_, park) in enumerate(parks_df.iterrows(), start=1):
    park_id = int(park[PARK_ID_FIELD])
    park_name = str(park[PARK_NAME_FIELD]).strip()
    muni = park["MUNI"]

    print("\n" + "=" * 80)
    print(f"{count}/{total_parks} Processing park {park_id}: {park_name}")

    clear_envs()
    arcpy.env.workspace = str(TEMP_GDB)
    arcpy.env.scratchWorkspace = str(TEMP_GDB)

    park_start_time = time.perf_counter()
    run_id = uuid.uuid4().hex[:8]

    # Temporary outputs
    viewshed_raster = str(TEMP_GDB / f"tmp_vs_{park_id}_{run_id}")
    visible_water_raster = str(TEMP_GDB / f"tmp_vw_{park_id}_{run_id}")
    dsm_clip = str(TEMP_GDB / f"tmp_dsm_{park_id}_{run_id}")
    dsm_filled = str(TEMP_GDB / f"tmp_dsm_filled_{park_id}_{run_id}")
    lcc_clip = str(TEMP_GDB / f"tmp_lcc_{park_id}_{run_id}")
    analysis_area = str(TEMP_GDB / f"tmp_area_{park_id}_{run_id}")
    park_observers = str(TEMP_GDB / f"tmp_obs_{park_id}_{run_id}")

    temp_items = [
        park_observers,
        analysis_area,
        dsm_clip,
        dsm_filled,
        lcc_clip,
        viewshed_raster,
        visible_water_raster,
    ]

    clean_temp(temp_items)

    # --------------------------------------------------------
    # Select observers for this park
    # --------------------------------------------------------
    where_clause = build_where_clause(
        observers_fc,
        PARK_ID_FIELD,
        park_id,
    )

    print("  Observer SQL:", where_clause)

    arcpy.conversion.ExportFeatures(
        in_features=observers_fc,
        out_features=park_observers,
        where_clause=where_clause,
    )

    observer_count = int(arcpy.management.GetCount(park_observers)[0])

    print("  Observer count:", observer_count)

    if observer_count == 0:
        elapsed_sec = time.perf_counter() - park_start_time

        result_rows.append({
            PARK_ID_FIELD: park_id,
            PARK_NAME_FIELD: park_name,
            "MUNI": muni,
            "observer_count": 0,
            "visible_water_cells": None,
            "visible_water_area_m2": None,
            "runtime_minutes": round(elapsed_sec / 60, 2),
        })

        failed_rows.append({
            PARK_ID_FIELD: park_id,
            PARK_NAME_FIELD: park_name,
            "reason": "no_observer_points",
        })

        save_progress(result_rows, OUTPUT_CSV)
        print("  Progress saved to:", OUTPUT_CSV)

        continue

    try:
        # ----------------------------------------------------
        # Create analysis area around observer points
        # ----------------------------------------------------
        arcpy.analysis.Buffer(
            in_features=park_observers,
            out_feature_class=analysis_area,
            buffer_distance_or_field=f"{ANALYSIS_BUFFER_M} Meters",
            dissolve_option="ALL",
        )

        # ----------------------------------------------------
        # Clip DSM to analysis area
        # ----------------------------------------------------
        arcpy.management.Clip(
            in_raster=str(DSM),
            rectangle="#",
            out_raster=dsm_clip,
            in_template_dataset=analysis_area,
            nodata_value="#",
            clipping_geometry="ClippingGeometry",
            maintain_clipping_extent="MAINTAIN_EXTENT",
        )

        # Fill DSM NoData cells with -1 m
        dsm_filled_raster = Con(IsNull(Raster(dsm_clip)), -1, Raster(dsm_clip))
        dsm_filled_raster.save(dsm_filled)

        # ----------------------------------------------------
        # Clip water raster to analysis area
        # ----------------------------------------------------
        arcpy.management.Clip(
            in_raster=str(LCC_WATER_RASTER),
            rectangle="#",
            out_raster=lcc_clip,
            in_template_dataset=analysis_area,
            nodata_value="#",
            clipping_geometry="ClippingGeometry",
            maintain_clipping_extent="MAINTAIN_EXTENT",
        )

        # Set raster environment using filled DSM
        arcpy.env.snapRaster = dsm_filled
        arcpy.env.cellSize = dsm_filled
        arcpy.env.extent = dsm_filled
        arcpy.env.outputCoordinateSystem = arcpy.Describe(dsm_filled).spatialReference

        # ----------------------------------------------------
        # Run Geodesic Viewshed
        # ----------------------------------------------------
        print("  Running viewshed...")

        out_vs = Viewshed2(
            in_raster=dsm_filled,
            in_observer_features=park_observers,
            out_agl_raster="",
            analysis_type="FREQUENCY",
            vertical_error="",
            out_observer_region_relationship_table="",
            observer_offset=OBSERVER_HEIGHT_M,
            analysis_method="ALL_SIGHTLINES",
            analysis_target_device="GPU_THEN_CPU",
        )

        out_vs.save(viewshed_raster)

        # ----------------------------------------------------
        # Visible water calculation
        # LCC water raster: 1 = water, 0 = not water
        # ----------------------------------------------------
        vs = Raster(viewshed_raster)
        lcc = Raster(lcc_clip)

        visible_water = Con((vs > 0) & (lcc == 1), 1, 0)
        visible_water.save(visible_water_raster)

        # ----------------------------------------------------
        # Save visible water raster for review
        # ----------------------------------------------------
        if SAVE_VISIBLE_WATER_RASTERS:
            saved_visible_water_raster = str(
                RASTER_OUTPUT_GDB / f"visible_water_park_{park_id}"
            )

            if arcpy.Exists(saved_visible_water_raster):
                arcpy.management.Delete(saved_visible_water_raster)

            arcpy.management.CopyRaster(
                in_raster=visible_water_raster,
                out_rasterdataset=saved_visible_water_raster
            )

            print("  Saved visible water raster:", saved_visible_water_raster)

        # ----------------------------------------------------
        # Area summary
        # ----------------------------------------------------
        cell_size_x = float(arcpy.Describe(dsm_filled).meanCellWidth)
        cell_size_y = float(arcpy.Describe(dsm_filled).meanCellHeight)
        cell_area_m2 = cell_size_x * cell_size_y

        visible_water_cells = raster_value_count(visible_water_raster, 1)
        visible_water_area_m2 = visible_water_cells * cell_area_m2

        elapsed_sec = time.perf_counter() - park_start_time

        print("  Visible water area m²:", round(visible_water_area_m2, 2))
        print("  Runtime minutes:", round(elapsed_sec / 60, 2))

        result_rows.append({
            PARK_ID_FIELD: park_id,
            PARK_NAME_FIELD: park_name,
            "MUNI": muni,
            "observer_count": observer_count,
            "visible_water_cells": visible_water_cells,
            "visible_water_area_m2": round(visible_water_area_m2, 2),
            "runtime_minutes": round(elapsed_sec / 60, 2),
        })

        save_progress(result_rows, OUTPUT_CSV)
        print("  Progress saved to:", OUTPUT_CSV)

    except Exception as e:
        print("  Viewshed failed:", e)

        elapsed_sec = time.perf_counter() - park_start_time

        result_rows.append({
            PARK_ID_FIELD: park_id,
            PARK_NAME_FIELD: park_name,
            "MUNI": muni,
            "observer_count": observer_count,
            "visible_water_cells": None,
            "visible_water_area_m2": None,
            "runtime_minutes": round(elapsed_sec / 60, 2),
        })

        failed_rows.append({
            PARK_ID_FIELD: park_id,
            PARK_NAME_FIELD: park_name,
            "reason": str(e),
        })

        save_progress(result_rows, OUTPUT_CSV)
        print("  Progress saved to:", OUTPUT_CSV)

    finally:
        clear_envs()
        arcpy.env.workspace = str(TEMP_GDB)
        arcpy.env.scratchWorkspace = str(TEMP_GDB)
        clean_temp(temp_items)


# ============================================================
# Final summary
# ============================================================

results = pd.DataFrame(result_rows)

if len(results) > 0:
    results = results.drop_duplicates(
        subset=[PARK_ID_FIELD],
        keep="last"
    )

    results = results.sort_values(PARK_ID_FIELD)

    print("\nSaved / updated viewshed visible water results:")
    print(OUTPUT_CSV)

    print("\nSummary:")
    print("Rows:", len(results))
    print("Parks with computed viewshed value:", results["visible_water_area_m2"].notna().sum())
    print("Parks with visible water area > 0:", (results["visible_water_area_m2"] > 0).sum())
    print("Parks with visible water area = 0:", (results["visible_water_area_m2"] == 0).sum())
    print("Parks without computed viewshed value:", results["visible_water_area_m2"].isna().sum())
    print("Total runtime minutes:", round(results["runtime_minutes"].sum(), 2))
else:
    print("\nNo results created.")

if failed_rows:
    print("\nFailed / missing parks:")
    failed_df = pd.DataFrame(failed_rows)
    print(failed_df.to_string(index=False))

print("\nDone.")