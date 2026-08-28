"""Run the documented park-by-park geodesic viewshed workflow.

The script resumes from its output CSV. A water cell is counted once when it
is visible from at least one observer; visibility is not summed across
observers.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

import arcpy
from arcpy.sa import Con, ExtractByMask, IsNull, Raster, Viewshed2


PROJECT_ROOT = Path(__file__).resolve().parents[4]
OBSERVER_GPKG = (
    PROJECT_ROOT / "data" / "interim" / "viewshed"
    / "observer_points_spacing_access_fallback.gpkg"
)
OBSERVER_LAYER = "observer_points_spacing_access_fallback"
OBSERVER_FC = str(OBSERVER_GPKG / OBSERVER_LAYER)
DSM = str(PROJECT_ROOT / "data" / "raw" / "dsm.tif")
WATER = str(PROJECT_ROOT / "data" / "raw" / "LCC2020_wateronot.tif")

INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "viewshed"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "viewshed"
INTERIM_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

TEMP_GDB = INTERIM_DIR / "viewshed_temp.gdb"
VISIBLE_GDB = (
    INTERIM_DIR / "viewshed_visible_water_rasters_spacing_access_fallback.gdb"
)
OUTPUT_CSV = (
    PROCESSED_DIR
    / "allparks_viewshed_visible_water_area_spacing_access_fallback.csv"
)

OBSERVER_HEIGHT = "1.6 Meters"
ANALYSIS_RADIUS = "1000 Meters"
WATER_VALUE = 1
OUTPUT_FIELDS = [
    "park_num", "PARK_NAME", "MUNI", "observer_count",
    "visible_water_cells", "visible_water_area_m2", "runtime_minutes",
]


def require(path: str, label: str) -> None:
    if not arcpy.Exists(path):
        raise FileNotFoundError(f"Missing {label}: {path}")


def create_gdb(path: Path) -> None:
    if not arcpy.Exists(str(path)):
        arcpy.management.CreateFileGDB(str(path.parent), path.name)


def delete_if_exists(path: str) -> None:
    if arcpy.Exists(path):
        arcpy.management.Delete(path)


def load_completed() -> dict[int, dict[str, str]]:
    if not OUTPUT_CSV.exists():
        return {}
    with OUTPUT_CSV.open("r", newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    completed = {}
    for row in rows:
        value = str(row.get("visible_water_area_m2", "")).strip()
        if value not in {"", "None", "NA", "nan"}:
            completed[int(float(row["park_num"]))] = row
    return completed


def write_results(rows: list[dict[str, object]]) -> None:
    ordered = sorted(rows, key=lambda row: int(row["park_num"]))
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(ordered)


def park_inventory() -> list[tuple[int, str]]:
    parks: dict[int, str] = {}
    with arcpy.da.SearchCursor(OBSERVER_FC, ["park_num", "PARK_NAME"]) as cursor:
        for park_num, park_name in cursor:
            parks[int(park_num)] = "" if park_name is None else str(park_name)
    return sorted(parks.items())


def raster_number(path: str, property_name: str) -> float:
    return float(arcpy.management.GetRasterProperties(path, property_name)[0])


def run_park(park_num: int, park_name: str) -> dict[str, object]:
    started = time.perf_counter()
    observer_layer = f"observers_{park_num}"
    arcpy.management.MakeFeatureLayer(
        OBSERVER_FC, observer_layer, f"park_num = {park_num}"
    )
    observer_count = int(arcpy.management.GetCount(observer_layer)[0])
    if observer_count == 0:
        raise ValueError(f"Park {park_num} has no observer points.")

    park_buffer = str(TEMP_GDB / f"buffer_{park_num}")
    dsm_clip = str(TEMP_GDB / f"dsm_clip_{park_num}")
    dsm_filled = str(TEMP_GDB / f"dsm_filled_{park_num}")
    water_clip = str(TEMP_GDB / f"water_clip_{park_num}")
    viewshed_path = str(TEMP_GDB / f"viewshed_{park_num}")
    visible_path = str(VISIBLE_GDB / f"visible_water_park_{park_num}")

    for item in (
        park_buffer, dsm_clip, dsm_filled, water_clip, viewshed_path,
        visible_path,
    ):
        delete_if_exists(item)

    arcpy.analysis.Buffer(
        observer_layer, park_buffer, ANALYSIS_RADIUS, dissolve_option="ALL"
    )

    with arcpy.EnvManager(
        mask=park_buffer,
        extent=park_buffer,
        snapRaster=DSM,
        cellSize=DSM,
        outputCoordinateSystem=DSM,
    ):
        ExtractByMask(DSM, park_buffer).save(dsm_clip)
        Con(IsNull(Raster(dsm_clip)), -1, Raster(dsm_clip)).save(dsm_filled)
        ExtractByMask(WATER, park_buffer).save(water_clip)

        viewshed = Viewshed2(
            dsm_filled,
            observer_layer,
            analysis_type="FREQUENCY",
            observer_offset=OBSERVER_HEIGHT,
            outer_radius=ANALYSIS_RADIUS,
            outer_radius_is_3d="GROUND",
            analysis_method="ALL_SIGHTLINES",
            analysis_target_device="GPU_THEN_CPU",
        )
        viewshed.save(viewshed_path)
        Con(
            (Raster(viewshed_path) > 0) & (Raster(water_clip) == WATER_VALUE),
            1,
        ).save(visible_path)

    visible_cells = raster_number(visible_path, "SUM")
    cell_width = raster_number(visible_path, "CELLSIZEX")
    cell_height = raster_number(visible_path, "CELLSIZEY")
    visible_area = visible_cells * abs(cell_width * cell_height)

    for item in (park_buffer, dsm_clip, dsm_filled, water_clip, viewshed_path):
        delete_if_exists(item)
    arcpy.management.Delete(observer_layer)

    return {
        "park_num": park_num,
        "PARK_NAME": park_name,
        "MUNI": "",
        "observer_count": observer_count,
        "visible_water_cells": round(visible_cells),
        "visible_water_area_m2": round(visible_area, 2),
        "runtime_minutes": round((time.perf_counter() - started) / 60, 2),
    }


def main() -> None:
    require(OBSERVER_FC, "observer-point layer")
    require(DSM, "DSM")
    require(WATER, "binary water raster")
    create_gdb(TEMP_GDB)
    create_gdb(VISIBLE_GDB)

    arcpy.env.overwriteOutput = True
    arcpy.env.scratchWorkspace = str(TEMP_GDB)
    arcpy.CheckOutExtension("Spatial")

    completed = load_completed()
    results: list[dict[str, object]] = list(completed.values())
    parks = park_inventory()
    print(f"Observer parks: {len(parks)}")
    print(f"Already completed: {len(completed)}")

    try:
        for index, (park_num, park_name) in enumerate(parks, start=1):
            if park_num in completed:
                print(f"[{index}/{len(parks)}] Skipping completed park {park_num}")
                continue
            print(f"[{index}/{len(parks)}] Running park {park_num}: {park_name}")
            result = run_park(park_num, park_name)
            results.append(result)
            write_results(results)
            print(
                "  visible water area:",
                f"{result['visible_water_area_m2']:,.2f} m2",
            )
    finally:
        arcpy.CheckInExtension("Spatial")

    print(f"Completed results: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
