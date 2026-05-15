from pathlib import Path
import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point
from shapely.ops import nearest_points

# -------------------------
# Paths
# -------------------------
land_buffer_path = r"data\raw\Park_Extraction_Project.gdb"
land_buffer_layer = "allparks_land_buffer"

output_dir = Path(r"data\interim\reach")
output_dir.mkdir(parents=True, exist_ok=True)

raw_output = output_dir / "candidate_access_points_raw.gpkg"
failed_output = output_dir / "candidate_access_points_failed_parks.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# Settings
# -------------------------
osm_buffer_degrees = 0.01
fallback_tolerances_m = [3, 5]

# -------------------------
# Read land buffer
# -------------------------
land = gpd.read_file(land_buffer_path, layer=land_buffer_layer)

print("Land buffer records:", len(land))
print("CRS:", land.crs)

land = land[[park_id_field, park_name_field, "geometry"]].copy()
land["geometry"] = land.geometry.make_valid()

# -------------------------
# Helper: extract points from intersection geometry
# -------------------------
def extract_points(geom):
    points = []

    if geom is None or geom.is_empty:
        return points

    if geom.geom_type == "Point":
        points.append(geom)

    elif geom.geom_type == "MultiPoint":
        points.extend(list(geom.geoms))

    elif geom.geom_type == "LineString":
        coords = list(geom.coords)
        if len(coords) >= 2:
            points.append(Point(coords[0]))
            points.append(Point(coords[-1]))

    elif geom.geom_type == "MultiLineString":
        for line in geom.geoms:
            coords = list(line.coords)
            if len(coords) >= 2:
                points.append(Point(coords[0]))
                points.append(Point(coords[-1]))

    elif geom.geom_type == "GeometryCollection":
        for part in geom.geoms:
            points.extend(extract_points(part))

    return points

# -------------------------
# Process parks one by one
# -------------------------
all_access_rows = []
failed_parks = []

for idx, park in land.iterrows():
    park_id = park[park_id_field]
    park_name = str(park[park_name_field]).strip()

    print(f"\nProcessing {idx + 1}/{len(land)} | {park_id} | {park_name}")

    park_gdf = gpd.GeoDataFrame([park], geometry="geometry", crs=land.crs)

    # OSMnx needs WGS84
    park_wgs84 = park_gdf.to_crs(epsg=4326)
    study_area = park_wgs84.geometry.iloc[0].buffer(osm_buffer_degrees)

    try:
        G = ox.graph_from_polygon(
            study_area,
            network_type="walk",
            simplify=True
        )

        edges = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index()

        if len(edges) == 0:
            print("  No OSM edges found.")
            failed_parks.append((park_id, park_name, "No OSM edges"))
            continue

        edges = edges.to_crs(land.crs)

    except Exception as e:
        print("  OSM download failed:", e)
        failed_parks.append((park_id, park_name, f"OSM download failed: {e}"))
        continue

    # Create land buffer boundary
    park_boundary = park_gdf.copy()
    park_boundary["geometry"] = park_boundary.geometry.boundary
    boundary_geom = park_boundary.geometry.iloc[0]

    # -------------------------
    # 1. Exact intersection
    # -------------------------
    intersections = gpd.overlay(
        edges,
        park_boundary[[park_id_field, park_name_field, "geometry"]],
        how="intersection",
        keep_geom_type=False
    )

    exact_point_count = 0

    for _, row in intersections.iterrows():
        pts = extract_points(row.geometry)

        for pt in pts:
            all_access_rows.append({
                park_id_field: park_id,
                park_name_field: park_name,
                "method": "exact_intersection",
                "snap_distance_m": 0,
                "geometry": pt
            })
            exact_point_count += 1

    if exact_point_count > 0:
        print("  Exact candidate points:", exact_point_count)
        continue

    print("  No exact intersections. Trying tolerance fallback...")

    # -------------------------
    # 2. Tolerance fallback: 3 m, then 5 m
    # -------------------------
    fallback_found = False

    for tolerance in fallback_tolerances_m:
        nearby_edges = edges[edges.geometry.distance(boundary_geom) <= tolerance].copy()

        print(f"  Nearby OSM edges within {tolerance} m:", len(nearby_edges))

        if len(nearby_edges) == 0:
            continue

        fallback_point_count = 0

        for _, edge in nearby_edges.iterrows():
            point_on_boundary, point_on_edge = nearest_points(
                boundary_geom,
                edge.geometry
            )

            dist = point_on_boundary.distance(point_on_edge)

            all_access_rows.append({
                park_id_field: park_id,
                park_name_field: park_name,
                "method": f"nearest_osm_within_{tolerance}m",
                "snap_distance_m": round(dist, 2),
                "geometry": point_on_boundary
            })

            fallback_point_count += 1

        print(f"  Fallback candidate points:", fallback_point_count)
        fallback_found = True
        break

    if not fallback_found:
        print("  Still no candidates.")
        failed_parks.append((park_id, park_name, "No exact or fallback candidates"))

# -------------------------
# Save candidate access points
# -------------------------
if len(all_access_rows) == 0:
    print("\nNo candidate access points were created.")
    raise SystemExit

access_raw = gpd.GeoDataFrame(
    all_access_rows,
    geometry="geometry",
    crs=land.crs
)

print("\nTotal candidate access points:", len(access_raw))

access_raw.to_file(raw_output, driver="GPKG")
print("Saved access points:", raw_output)

# -------------------------
# Save failed parks log
# -------------------------
if len(failed_parks) > 0:
    failed_df = gpd.pd.DataFrame(
        failed_parks,
        columns=[park_id_field, park_name_field, "reason"]
    )

    failed_df.to_csv(failed_output, index=False)
    print("Saved failed parks log:", failed_output)

print("\nDone.")