from pathlib import Path
import json
import time
import urllib.parse
import urllib.request

import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon


# ============================================================
# STEP 3: DOWNLOAD OSM HAPTIC FEATURES
# GeoPandas version, no ArcPy
# ============================================================
# Downloads:
# - OSM barriers/access restrictions
# - OSM bridges
# - OSM beach/sand features
#
# Outputs:
# data/interim/haptic/osm/osm_barrier_points.geojson
# data/interim/haptic/osm/osm_barrier_lines.geojson
# data/interim/haptic/osm/osm_bridge_lines.geojson
# data/interim/haptic/osm/osm_beach_sand_polygons.geojson
# data/interim/haptic/osm/osm_beach_sand_lines.geojson
# ============================================================


# -------------------------
# Paths
# -------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[4]

PARKS_GDB = PROJECT_ROOT / "data" / "raw" / "Park_Extraction_Project.gdb"

OSM_INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "haptic" / "osm"
OSM_INTERIM_DIR.mkdir(parents=True, exist_ok=True)

RAW_BARRIER_JSON = OSM_INTERIM_DIR / "osm_barriers_raw_overpass.json"
RAW_BRIDGE_JSON = OSM_INTERIM_DIR / "osm_bridges_raw_overpass.json"
RAW_BEACH_JSON = OSM_INTERIM_DIR / "osm_beach_sand_raw_overpass.json"

BARRIER_POINTS_OUT = OSM_INTERIM_DIR / "osm_barrier_points.geojson"
BARRIER_LINES_OUT = OSM_INTERIM_DIR / "osm_barrier_lines.geojson"
BRIDGE_LINES_OUT = OSM_INTERIM_DIR / "osm_bridge_lines.geojson"

BEACH_POLYGONS_OUT = OSM_INTERIM_DIR / "osm_beach_sand_polygons.geojson"
BEACH_LINES_OUT = OSM_INTERIM_DIR / "osm_beach_sand_lines.geojson"


# -------------------------
# Settings
# -------------------------
PARK_LAYER_NAME = "allparks_land_buffer"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 240

BBOX_PADDING_DEG = 0.02


# ============================================================
# Helper functions
# ============================================================

def read_parks() -> gpd.GeoDataFrame:
    print("Reading park layer...")

    parks = gpd.read_file(PARKS_GDB, layer=PARK_LAYER_NAME)

    if parks.empty:
        raise ValueError("Park layer is empty.")

    if parks.crs is None:
        raise ValueError("Park layer has no CRS.")

    print("Parks:", len(parks))
    print("CRS:", parks.crs)

    return parks


def get_bbox_wgs84(gdf: gpd.GeoDataFrame, padding_deg: float = 0.02):
    gdf_wgs84 = gdf.to_crs(epsg=4326)

    minx, miny, maxx, maxy = gdf_wgs84.total_bounds

    west = minx - padding_deg
    south = miny - padding_deg
    east = maxx + padding_deg
    north = maxy + padding_deg

    return south, west, north, east


def run_overpass(query: str, output_json: Path) -> dict:
    print("\nSubmitting Overpass query...")

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")

    request = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={
            "User-Agent": "urban-blue-green-accessibility-haptic-osm/1.0"
        },
    )

    with urllib.request.urlopen(request, timeout=OVERPASS_TIMEOUT) as response:
        text = response.read().decode("utf-8")

    output_json.write_text(text, encoding="utf-8")
    print("Saved raw Overpass JSON:", output_json)

    return json.loads(text)


def osm_element_to_record(element: dict, osm_category: str):
    osm_type = element.get("type")
    osm_id = element.get("id")
    tags = element.get("tags", {}) or {}

    props = {
        "osm_type": osm_type,
        "osm_id": osm_id,
        "osm_category": osm_category,
    }

    for key, value in tags.items():
        safe_key = str(key).replace(":", "_")
        props[safe_key] = value

    if osm_type == "node":
        lat = element.get("lat")
        lon = element.get("lon")

        if lat is None or lon is None:
            return None

        props["geometry"] = Point(lon, lat)
        return props

    if osm_type == "way":
        geom = element.get("geometry", [])

        coords = [
            (p["lon"], p["lat"])
            for p in geom
            if "lon" in p and "lat" in p
        ]

        if len(coords) < 2:
            return None

        props["geometry"] = LineString(coords)
        return props

    return None


def overpass_to_gdfs(overpass_data: dict, osm_category: str):
    point_records = []
    line_records = []

    for element in overpass_data.get("elements", []):
        record = osm_element_to_record(element, osm_category)

        if record is None:
            continue

        geom = record["geometry"]

        if geom.geom_type == "Point":
            point_records.append(record)
        elif geom.geom_type == "LineString":
            line_records.append(record)

    if len(point_records) > 0:
        points = gpd.GeoDataFrame(
            point_records,
            geometry="geometry",
            crs="EPSG:4326"
        )
    else:
        points = gpd.GeoDataFrame(
            {"geometry": []},
            geometry="geometry",
            crs="EPSG:4326"
        )

    if len(line_records) > 0:
        lines = gpd.GeoDataFrame(
            line_records,
            geometry="geometry",
            crs="EPSG:4326"
        )
    else:
        lines = gpd.GeoDataFrame(
            {"geometry": []},
            geometry="geometry",
            crs="EPSG:4326"
        )

    return points, lines


def overpass_to_beach_gdfs(overpass_data: dict):
    polygon_records = []
    line_records = []

    for element in overpass_data.get("elements", []):
        osm_type = element.get("type")
        osm_id = element.get("id")
        tags = element.get("tags", {}) or {}

        if osm_type != "way":
            continue

        geom = element.get("geometry", [])

        coords = [
            (p["lon"], p["lat"])
            for p in geom
            if "lon" in p and "lat" in p
        ]

        if len(coords) < 2:
            continue

        props = {
            "osm_type": osm_type,
            "osm_id": osm_id,
            "osm_category": "beach_or_sand",
        }

        for key, value in tags.items():
            safe_key = str(key).replace(":", "_")
            props[safe_key] = value

        if len(coords) >= 4 and coords[0] == coords[-1]:
            try:
                props["geometry"] = Polygon(coords)
                polygon_records.append(props)
            except Exception:
                props["geometry"] = LineString(coords)
                line_records.append(props)
        else:
            props["geometry"] = LineString(coords)
            line_records.append(props)

    if len(polygon_records) > 0:
        polygons = gpd.GeoDataFrame(
            polygon_records,
            geometry="geometry",
            crs="EPSG:4326"
        )
    else:
        polygons = gpd.GeoDataFrame(
            {"geometry": []},
            geometry="geometry",
            crs="EPSG:4326"
        )

    if len(line_records) > 0:
        lines = gpd.GeoDataFrame(
            line_records,
            geometry="geometry",
            crs="EPSG:4326"
        )
    else:
        lines = gpd.GeoDataFrame(
            {"geometry": []},
            geometry="geometry",
            crs="EPSG:4326"
        )

    return polygons, lines


def save_gdf(gdf: gpd.GeoDataFrame, output_path: Path):
    if output_path.exists():
        output_path.unlink()

    if gdf.empty:
        print("No features to save:", output_path)
        empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        empty.to_file(output_path, driver="GeoJSON")
        return

    gdf.to_file(output_path, driver="GeoJSON")
    print("Saved:", output_path)
    print("Features:", len(gdf))


# ============================================================
# Main
# ============================================================

def main():
    parks = read_parks()

    south, west, north, east = get_bbox_wgs84(
        parks,
        padding_deg=BBOX_PADDING_DEG
    )

    print("\nOverpass bbox:")
    print(f"south={south}")
    print(f"west={west}")
    print(f"north={north}")
    print(f"east={east}")

    # --------------------------------------------------------
    # Barriers and access restrictions
    # --------------------------------------------------------
    barrier_query = f"""
    [out:json][timeout:240];
    (
      node["barrier"]({south},{west},{north},{east});
      way["barrier"]({south},{west},{north},{east});

      node["access"~"^(no|private)$"]({south},{west},{north},{east});
      way["access"~"^(no|private)$"]({south},{west},{north},{east});
    );
    out tags geom;
    """

    barrier_data = run_overpass(barrier_query, RAW_BARRIER_JSON)

    barrier_points, barrier_lines = overpass_to_gdfs(
        barrier_data,
        osm_category="barrier_or_access_restriction"
    )

    save_gdf(barrier_points, BARRIER_POINTS_OUT)
    save_gdf(barrier_lines, BARRIER_LINES_OUT)

    time.sleep(5)

    # --------------------------------------------------------
    # Bridges
    # --------------------------------------------------------
    bridge_query = f"""
    [out:json][timeout:240];
    (
      way["bridge"]["bridge"!="no"]({south},{west},{north},{east});
    );
    out tags geom;
    """

    bridge_data = run_overpass(bridge_query, RAW_BRIDGE_JSON)

    _, bridge_lines = overpass_to_gdfs(
        bridge_data,
        osm_category="bridge"
    )

    save_gdf(bridge_lines, BRIDGE_LINES_OUT)

    time.sleep(5)

    # --------------------------------------------------------
    # Beach / sand features
    # --------------------------------------------------------
    beach_query = f"""
    [out:json][timeout:240];
    (
      way["natural"~"^(beach|sand)$"]({south},{west},{north},{east});
      way["surface"="sand"]({south},{west},{north},{east});
      way["landcover"="sand"]({south},{west},{north},{east});
    );
    out tags geom;
    """

    beach_data = run_overpass(beach_query, RAW_BEACH_JSON)

    beach_polygons, beach_lines = overpass_to_beach_gdfs(beach_data)

    save_gdf(beach_polygons, BEACH_POLYGONS_OUT)
    save_gdf(beach_lines, BEACH_LINES_OUT)

    print("\nDone.")


if __name__ == "__main__":
    main()
