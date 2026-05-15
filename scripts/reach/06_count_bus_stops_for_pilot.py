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

counts_output = output_dir / "pilot_10_bus_stop_counts.csv"
bus_stop_details_output = output_dir / "pilot_10_bus_stop_reach_details.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# Settings
# -------------------------
walking_speed_m_per_min = 80  # 5 km/h

time_thresholds = {
    "bus_stops_05min": 5 * walking_speed_m_per_min,
    "bus_stops_10min": 10 * walking_speed_m_per_min,
    "bus_stops_20min": 20 * walking_speed_m_per_min,
    "bus_stops_30min": 30 * walking_speed_m_per_min,
}

max_distance_m = max(time_thresholds.values())
search_margin_m = 0
search_buffer_m = max_distance_m + search_margin_m

# -------------------------
# Read data
# -------------------------
access = gpd.read_file(pilot_access_points_path)
bus_stops = gpd.read_file(bus_stops_path)

access[park_name_field] = access[park_name_field].astype(str).str.strip()

# Make sure CRS matches
bus_stops = bus_stops.to_crs(access.crs)

# Optional: remove duplicate GTFS stops if stop_id exists
if "stop_id" in bus_stops.columns:
    bus_stops = bus_stops.drop_duplicates(subset=["stop_id"]).copy()

print("Pilot access points:", len(access))
print("Bus stops:", len(bus_stops))
print("CRS:", access.crs)

# -------------------------
# Process each pilot park
# -------------------------
count_rows = []
detail_rows = []

for park_id, access_group in access.groupby(park_id_field):
    park_name = access_group[park_name_field].iloc[0]

    print(f"\nProcessing park {park_id}: {park_name}")

    # Create search area around park access points
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

    # Access points to WGS84 for nearest network nodes
    access_wgs84 = access_group.to_crs(epsg=4326)

    access_nodes = ox.distance.nearest_nodes(
        G,
        X=access_wgs84.geometry.x,
        Y=access_wgs84.geometry.y
    )

    access_nodes = list(set(access_nodes))

    # Calculate shortest walking distance from any access point
    lengths = nx.multi_source_dijkstra_path_length(
        G,
        sources=access_nodes,
        cutoff=max_distance_m,
        weight="length"
    )

    # Select nearby bus stops using Euclidean pre-filter
    nearby_bus_stops = bus_stops[
        bus_stops.geometry.within(search_area_utm)
    ].copy()

    if len(nearby_bus_stops) == 0:
        print("  No nearby bus stops found.")
        count_rows.append({
            park_id_field: park_id,
            park_name_field: park_name,
            "bus_stops_05min": 0,
            "bus_stops_10min": 0,
            "bus_stops_20min": 0,
            "bus_stops_30min": 0,
        })
        continue

    nearby_bus_stops_wgs84 = nearby_bus_stops.to_crs(epsg=4326)

    bus_nodes = ox.distance.nearest_nodes(
        G,
        X=nearby_bus_stops_wgs84.geometry.x,
        Y=nearby_bus_stops_wgs84.geometry.y
    )

    nearby_bus_stops["nearest_node"] = bus_nodes
    nearby_bus_stops["network_distance_m"] = nearby_bus_stops["nearest_node"].map(lengths)

    reachable = nearby_bus_stops.dropna(subset=["network_distance_m"]).copy()

    counts = {
        park_id_field: park_id,
        park_name_field: park_name,
    }

    for field, distance_m in time_thresholds.items():
        counts[field] = int((reachable["network_distance_m"] <= distance_m).sum())

    count_rows.append(counts)

    print(" ", counts)

    # Save bus stop detail rows
    for _, stop in reachable.iterrows():
        detail_rows.append({
            park_id_field: park_id,
            park_name_field: park_name,
            "stop_id": stop.get("stop_id", None),
            "stop_name": stop.get("stop_name", None),
            "network_distance_m": round(stop["network_distance_m"], 2),
            "within_05min": stop["network_distance_m"] <= time_thresholds["bus_stops_05min"],
            "within_10min": stop["network_distance_m"] <= time_thresholds["bus_stops_10min"],
            "within_20min": stop["network_distance_m"] <= time_thresholds["bus_stops_20min"],
            "within_30min": stop["network_distance_m"] <= time_thresholds["bus_stops_30min"],
        })

# -------------------------
# Save outputs
# -------------------------
counts_df = pd.DataFrame(count_rows)
details_df = pd.DataFrame(detail_rows)

counts_df.to_csv(counts_output, index=False)
details_df.to_csv(bus_stop_details_output, index=False)

print("\nSaved bus stop counts:", counts_output)
print("Saved bus stop details:", bus_stop_details_output)
print("Done.")