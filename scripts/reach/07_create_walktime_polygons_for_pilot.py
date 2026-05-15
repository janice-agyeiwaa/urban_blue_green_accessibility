from pathlib import Path
import geopandas as gpd
import pandas as pd
import osmnx as ox
import networkx as nx

# -------------------------
# Paths
# -------------------------
pilot_access_points_path = Path(r"data\processed\reach\pilot_10_access_points.gpkg")
bus_stops_path = Path(r"data\interim\reach\translink_bus_stops.gpkg")

output_dir = Path(r"data\processed\reach")
output_dir.mkdir(parents=True, exist_ok=True)

walktime_polygons_output = output_dir / "pilot_10_walktime_polygons.gpkg"
bus_counts_output = output_dir / "pilot_10_bus_stop_counts_from_walktime_polygons.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# Settings
# -------------------------
walking_speed_m_per_min = 80  # 4.8 km/h

time_thresholds = {
    5: 5 * walking_speed_m_per_min,
    10: 10 * walking_speed_m_per_min,
    20: 20 * walking_speed_m_per_min,
    30: 30 * walking_speed_m_per_min,
}

edge_buffer_m = 15
search_margin_m = 250
max_distance_m = max(time_thresholds.values())
search_buffer_m = max_distance_m + search_margin_m

# -------------------------
# Read inputs
# -------------------------
access = gpd.read_file(pilot_access_points_path)
bus_stops = gpd.read_file(bus_stops_path)

access[park_name_field] = access[park_name_field].astype(str).str.strip()
bus_stops = bus_stops.to_crs(access.crs)

if "stop_id" in bus_stops.columns:
    bus_stops = bus_stops.drop_duplicates(subset=["stop_id"]).copy()

print("Pilot access points:", len(access))
print("Bus stops:", len(bus_stops))
print("CRS:", access.crs)

# -------------------------
# Outputs collected here
# -------------------------
polygon_rows = []
count_rows = []

# -------------------------
# Process park by park
# -------------------------
for park_id, access_group in access.groupby(park_id_field):
    park_name = access_group[park_name_field].iloc[0]

    print(f"\nProcessing park {park_id}: {park_name}")

    # Search area around access points
    search_area_utm = access_group.geometry.union_all().buffer(search_buffer_m)

    search_area_wgs84 = (
        gpd.GeoSeries([search_area_utm], crs=access.crs)
        .to_crs(epsg=4326)
        .iloc[0]
    )

    # Download OSM walking network
    try:
        G = ox.graph_from_polygon(
            search_area_wgs84,
            network_type="walk",
            simplify=True
        )
    except Exception as e:
        print("  OSM download failed:", e)
        continue

    # Convert graph edges to GeoDataFrame for polygon creation
    edges = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index()

    # Access points to WGS84 for nearest node matching
    access_wgs84 = access_group.to_crs(epsg=4326)

    access_nodes = ox.distance.nearest_nodes(
        G,
        X=access_wgs84.geometry.x,
        Y=access_wgs84.geometry.y
    )

    access_nodes = list(set(access_nodes))

    # Dijkstra: distance from any access point along OSM network
    lengths = nx.multi_source_dijkstra_path_length(
        G,
        sources=access_nodes,
        cutoff=max_distance_m,
        weight="length"
    )

    reachable_nodes = set(lengths.keys())

    # Select edges where both ends are reachable
    reachable_edges = edges[
        edges["u"].isin(reachable_nodes) &
        edges["v"].isin(reachable_nodes)
    ].copy()

    if len(reachable_edges) == 0:
        print("  No reachable edges.")
        continue

    reachable_edges = reachable_edges.to_crs(access.crs)

    # Count bus stops for each threshold
    park_counts = {
        park_id_field: park_id,
        park_name_field: park_name,
    }

    for minutes, distance_m in time_thresholds.items():
        # Nodes reachable within this time threshold
        threshold_nodes = {
            node for node, dist in lengths.items()
            if dist <= distance_m
        }

        # Edges reachable within this time threshold
        threshold_edges = reachable_edges[
            reachable_edges["u"].isin(threshold_nodes) &
            reachable_edges["v"].isin(threshold_nodes)
        ].copy()

        if len(threshold_edges) == 0:
            park_counts[f"bus_stops_{minutes:02d}min"] = 0
            continue

        # Buffer reachable edges to create approximate walk-time polygon
        buffered = threshold_edges.geometry.buffer(edge_buffer_m)
        dissolved_polygon = buffered.union_all()

        polygon_rows.append({
            park_id_field: park_id,
            park_name_field: park_name,
            "walktime_min": minutes,
            "distance_m": distance_m,
            "edge_buffer_m": edge_buffer_m,
            "geometry": dissolved_polygon
        })

        # Count bus stops inside polygon
        bus_count = int(bus_stops.geometry.within(dissolved_polygon).sum())
        park_counts[f"bus_stops_{minutes:02d}min"] = bus_count

        print(f"  {minutes} min: {bus_count} bus stops")

    count_rows.append(park_counts)

# -------------------------
# Save outputs
# -------------------------
walktime_polygons = gpd.GeoDataFrame(
    polygon_rows,
    geometry="geometry",
    crs=access.crs
)

bus_counts = pd.DataFrame(count_rows)

walktime_polygons.to_file(walktime_polygons_output, driver="GPKG")
bus_counts.to_csv(bus_counts_output, index=False)

print("\nSaved walk-time polygons:", walktime_polygons_output)
print("Saved bus stop counts:", bus_counts_output)
print("Done.")