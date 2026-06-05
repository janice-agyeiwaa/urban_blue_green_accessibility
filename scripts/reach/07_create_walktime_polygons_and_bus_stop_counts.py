# 07_create_walktime_polygons_bus_counts.py

from pathlib import Path
import geopandas as gpd
import pandas as pd
import networkx as nx
import pyogrio
from shapely.geometry import LineString


# ============================================================
# STEP 7: CREATE WALKTIME POLYGONS AND BUS STOP COUNTS
# ============================================================

# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

PARKS_GDB = PROJECT_ROOT / "data" / "raw" / "Park_Extraction_Project.gdb"
COMPOSITE_GDB = PROJECT_ROOT / "data" / "raw" / "CompositeNetwork3.gdb"

ACCESS_POINTS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "reach"
    / "reach_access_points.gpkg"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "reach"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BUS_COUNTS_OUTPUT = OUTPUT_DIR / "bus_stop_counts_5_10_20_30min.csv"
WALKTIME_POLYGONS_OUTPUT = OUTPUT_DIR / "walktime_polygons_5_10_20_30min.gpkg"


# ============================================================
# Layer names
# ============================================================

LAND_BUFFER_LAYER = "allparks_land_buffer"
COMPOSITE_NETWORK_LAYER = "OSM_NA_Network_NAD_Point3"
BUS_STOPS_LAYER = "Stops"


# ============================================================
# Settings
# ============================================================

PARK_ID_FIELD = "park_num"
PARK_NAME_FIELD = "PARK_NAME"
TARGET_CRS = "EPSG:26910"

WALKING_SPEED_M_PER_MIN = 80

TIME_THRESHOLDS = {
    5: 5 * WALKING_SPEED_M_PER_MIN,
    10: 10 * WALKING_SPEED_M_PER_MIN,
    20: 20 * WALKING_SPEED_M_PER_MIN,
    30: 30 * WALKING_SPEED_M_PER_MIN,
}

MAX_DISTANCE_M = max(TIME_THRESHOLDS.values())

EDGE_BUFFER_M = 15
NODE_ROUND = 3
XY_ROUND = 2
SNAP_WARNING_DISTANCE_M = 50


# ============================================================
# Helper functions
# ============================================================

def find_layer(gdb_path: Path, target_layer_name: str) -> str:
    layers = pyogrio.list_layers(gdb_path)
    layer_names = [row[0] for row in layers]

    for layer in layer_names:
        if layer.lower() == target_layer_name.lower():
            return layer

    raise ValueError(
        f"Could not find layer '{target_layer_name}'. Available layers:\n{layer_names}"
    )


def build_graph_from_lines(lines_gdf: gpd.GeoDataFrame, node_round: int = 3):
    """
    Build a NetworkX graph from the composite network line vertices.
    Each line segment becomes an edge weighted by length in metres.
    """
    G = nx.Graph()
    edge_records = []
    edge_id = 0

    for _, row in lines_gdf.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        if geom.geom_type == "LineString":
            parts = [geom]
        elif geom.geom_type == "MultiLineString":
            parts = list(geom.geoms)
        else:
            continue

        for line in parts:
            coords = list(line.coords)

            if len(coords) < 2:
                continue

            for start, end in zip(coords[:-1], coords[1:]):
                u = (round(start[0], node_round), round(start[1], node_round))
                v = (round(end[0], node_round), round(end[1], node_round))

                segment = LineString([start, end])
                length_m = float(segment.length)

                if length_m <= 0:
                    continue

                G.add_node(u, x=u[0], y=u[1])
                G.add_node(v, x=v[0], y=v[1])

                # If duplicate edge exists, keep the shorter one
                if G.has_edge(u, v):
                    old_weight = G[u][v]["weight"]
                    if length_m >= old_weight:
                        continue

                G.add_edge(
                    u,
                    v,
                    weight=length_m,
                    geometry=segment,
                    edge_id=edge_id,
                )

                edge_records.append({
                    "u": u,
                    "v": v,
                    "geometry": segment,
                    "length_m": length_m,
                    "edge_id": edge_id,
                })

                edge_id += 1

    edges_gdf = gpd.GeoDataFrame(edge_records, geometry="geometry", crs=TARGET_CRS)

    return G, edges_gdf


def insert_origin_nodes_for_park(
    base_graph,
    edges_gdf,
    access_group,
    park_id,
    node_round=3,
):
    """
    For each final access point:
    - find the nearest composite network edge
    - project the access point onto that edge
    - insert the projected point as an origin node
    - connect the origin node to both ends of the edge
    """
    G = base_graph.copy()

    origin_nodes = []
    snap_rows = []

    sindex = edges_gdf.sindex

    for idx, access_row in access_group.reset_index(drop=True).iterrows():
        point = access_row.geometry

        if point is None or point.is_empty:
            continue

        nearest_idx = list(sindex.nearest(point, return_all=False))[1][0]
        edge = edges_gdf.iloc[nearest_idx]

        line = edge.geometry
        projected_distance = line.project(point)
        projected_point = line.interpolate(projected_distance)

        snap_distance = point.distance(projected_point)

        origin_node = (
            round(projected_point.x, node_round),
            round(projected_point.y, node_round),
        )

        u = edge["u"]
        v = edge["v"]

        origin_nodes.append(origin_node)

        G.add_node(origin_node, x=origin_node[0], y=origin_node[1])

        dist_to_u = LineString([origin_node, u]).length
        dist_to_v = LineString([origin_node, v]).length

        if dist_to_u > 0:
            G.add_edge(
                origin_node,
                u,
                weight=dist_to_u,
                geometry=LineString([origin_node, u]),
            )

        if dist_to_v > 0:
            G.add_edge(
                origin_node,
                v,
                weight=dist_to_v,
                geometry=LineString([origin_node, v]),
            )

        snap_rows.append({
            PARK_ID_FIELD: park_id,
            "routing_origin_index": idx,
            "snap_distance_m": round(snap_distance, 2),
            "snap_warning_gt_50m": snap_distance > SNAP_WARNING_DISTANCE_M,
        })

    origin_nodes = list(set(origin_nodes))

    return G, origin_nodes, snap_rows


def empty_count_row(
    park_id,
    park_name,
    muni,
    access_point_count,
    routing_origin_count,
    status,
):
    row = {
        PARK_ID_FIELD: park_id,
        PARK_NAME_FIELD: park_name,
        "MUNI": muni,
        "access_point_count": access_point_count,
        "routing_origin_point_count": routing_origin_count,
        "origin_node_count": 0,
        "avg_snap_distance_m": None,
        "max_snap_distance_m": None,
        "far_snap_count_gt_50m": None,
        "reachable_node_count_30min": 0,
        "status": status,
    }

    for minutes in TIME_THRESHOLDS:
        row[f"bus_stops_{minutes:02d}min"] = 0

    return row


# ============================================================
# Read data
# ============================================================

print("Finding composite network layer...")
network_layer = find_layer(COMPOSITE_GDB, COMPOSITE_NETWORK_LAYER)
print("Using composite network layer:", network_layer)

print("\nReading data...")

parks = gpd.read_file(PARKS_GDB, layer=LAND_BUFFER_LAYER)
access_raw = gpd.read_file(ACCESS_POINTS_PATH)
network = gpd.read_file(COMPOSITE_GDB, layer=network_layer)
bus_stops = gpd.read_file(COMPOSITE_GDB, layer=BUS_STOPS_LAYER)

parks = parks.to_crs(TARGET_CRS)
access_raw = access_raw.to_crs(TARGET_CRS)
network = network.to_crs(TARGET_CRS)
bus_stops = bus_stops.to_crs(TARGET_CRS)

base = parks[[PARK_ID_FIELD, PARK_NAME_FIELD, "MUNI"]].drop_duplicates(
    subset=[PARK_ID_FIELD]
).copy()

base[PARK_NAME_FIELD] = base[PARK_NAME_FIELD].astype(str).str.strip()

access_raw[PARK_ID_FIELD] = access_raw[PARK_ID_FIELD].astype(int)
access_raw[PARK_NAME_FIELD] = access_raw[PARK_NAME_FIELD].astype(str).str.strip()

# Access point count from final kept access points
access_counts = (
    access_raw.groupby(PARK_ID_FIELD)
    .size()
    .reset_index(name="access_point_count")
)

# Routing origins: make sure only point geometries are used
access_routing = access_raw.explode(index_parts=False).reset_index(drop=True)
access_routing = access_routing[access_routing.geometry.notna()].copy()
access_routing = access_routing[access_routing.geometry.geom_type == "Point"].copy()

# Remove stacked routing origins only
access_routing["x_round"] = access_routing.geometry.x.round(XY_ROUND)
access_routing["y_round"] = access_routing.geometry.y.round(XY_ROUND)

before_routing_dedup = len(access_routing)

access_routing = access_routing.drop_duplicates(
    subset=[PARK_ID_FIELD, "x_round", "y_round"]
).copy()

after_routing_dedup = len(access_routing)

access_routing = access_routing.drop(columns=["x_round", "y_round"])

# Remove duplicate stops if stop_id exists
if "stop_id" in bus_stops.columns:
    bus_stops = bus_stops.drop_duplicates(subset=["stop_id"]).copy()

print("Base parks:", len(base))
print("Final kept access points:", len(access_raw))
print("Routing origins before dedup:", before_routing_dedup)
print("Routing origins after dedup:", after_routing_dedup)
print("Composite network records:", len(network))
print("Composite bus stops:", len(bus_stops))


# ============================================================
# Build graph
# ============================================================

print("\nBuilding composite network graph...")

base_graph, edges_gdf = build_graph_from_lines(network, node_round=NODE_ROUND)

print("Graph nodes:", base_graph.number_of_nodes())
print("Graph edges:", base_graph.number_of_edges())

if base_graph.number_of_nodes() == 0:
    raise ValueError("Graph has no nodes. Check the composite network layer.")


# ============================================================
# Process parks
# ============================================================

count_rows = []
polygon_rows = []

total_parks = len(base)

for park_counter, (_, park_row) in enumerate(base.iterrows(), start=1):
    park_id = int(park_row[PARK_ID_FIELD])
    park_name = str(park_row[PARK_NAME_FIELD]).strip()
    muni = park_row["MUNI"]

    access_count_match = access_counts[access_counts[PARK_ID_FIELD] == park_id]

    if len(access_count_match) == 0:
        access_point_count = 0
    else:
        access_point_count = int(access_count_match["access_point_count"].iloc[0])

    access_group = access_routing[access_routing[PARK_ID_FIELD] == park_id].copy()

    print("\n" + "=" * 80)
    print(f"Processing park {park_counter}/{total_parks}")
    print(f"Park {park_id}: {park_name}")
    print("  Access point count:", access_point_count)
    print("  Routing origin points:", len(access_group))

    if len(access_group) == 0:
        count_rows.append(
            empty_count_row(
                park_id,
                park_name,
                muni,
                access_point_count,
                routing_origin_count=0,
                status="no_routing_origin_points",
            )
        )
        continue

    G, origin_nodes, snap_rows = insert_origin_nodes_for_park(
        base_graph,
        edges_gdf,
        access_group,
        park_id,
        node_round=NODE_ROUND,
    )

    snap_distances = [row["snap_distance_m"] for row in snap_rows]

    if len(origin_nodes) == 0:
        count_rows.append(
            empty_count_row(
                park_id,
                park_name,
                muni,
                access_point_count,
                routing_origin_count=len(access_group),
                status="no_origin_nodes",
            )
        )
        continue

    avg_snap = sum(snap_distances) / len(snap_distances)
    max_snap = max(snap_distances)
    far_snap_count = sum(d > SNAP_WARNING_DISTANCE_M for d in snap_distances)

    print("  Origin nodes inserted:", len(origin_nodes))
    print("  Max snap distance:", round(max_snap, 2), "m")

    try:
        lengths = nx.multi_source_dijkstra_path_length(
            G,
            sources=origin_nodes,
            cutoff=MAX_DISTANCE_M,
            weight="weight",
        )
    except Exception as e:
        count_rows.append(
            empty_count_row(
                park_id,
                park_name,
                muni,
                access_point_count,
                routing_origin_count=len(access_group),
                status=f"dijkstra_failed: {e}",
            )
        )
        continue

    park_counts = {
        PARK_ID_FIELD: park_id,
        PARK_NAME_FIELD: park_name,
        "MUNI": muni,
        "access_point_count": access_point_count,
        "routing_origin_point_count": len(access_group),
        "origin_node_count": len(origin_nodes),
        "avg_snap_distance_m": round(avg_snap, 2),
        "max_snap_distance_m": round(max_snap, 2),
        "far_snap_count_gt_50m": int(far_snap_count),
        "reachable_node_count_30min": len(lengths),
        "status": "success",
    }

    for minutes, distance_m in TIME_THRESHOLDS.items():
        reachable_nodes = {
            node for node, dist in lengths.items()
            if dist <= distance_m
        }

        reachable_edges = []

        for u, v, data in G.edges(data=True):
            if u in reachable_nodes and v in reachable_nodes:
                geom = data.get("geometry")
                if geom is not None:
                    reachable_edges.append(geom)

        count_field = f"bus_stops_{minutes:02d}min"

        if len(reachable_edges) == 0:
            park_counts[count_field] = 0
            print(f"  {minutes} min: 0 bus stops")
            continue

        reachable_lines = gpd.GeoSeries(reachable_edges, crs=TARGET_CRS)
        walktime_polygon = reachable_lines.buffer(EDGE_BUFFER_M).union_all()

        bus_count = int(bus_stops.geometry.intersects(walktime_polygon).sum())
        park_counts[count_field] = bus_count

        polygon_rows.append({
            PARK_ID_FIELD: park_id,
            PARK_NAME_FIELD: park_name,
            "MUNI": muni,
            "walktime_min": minutes,
            "distance_m": distance_m,
            "edge_buffer_m": EDGE_BUFFER_M,
            "access_point_count": access_point_count,
            "routing_origin_point_count": len(access_group),
            "origin_node_count": len(origin_nodes),
            "geometry": walktime_polygon,
        })

        print(f"  {minutes} min: {bus_count} bus stops")

    count_rows.append(park_counts)


# ============================================================
# Save outputs
# ============================================================

# Remove existing outputs so reruns do not fail
for output_path in [
    BUS_COUNTS_OUTPUT,
    WALKTIME_POLYGONS_OUTPUT,
]:
    if output_path.exists():
        output_path.unlink()

bus_counts = pd.DataFrame(count_rows)

for minutes in TIME_THRESHOLDS:
    col = f"bus_stops_{minutes:02d}min"
    if col not in bus_counts.columns:
        bus_counts[col] = 0

bus_counts = bus_counts.sort_values(PARK_ID_FIELD)
bus_counts.to_csv(BUS_COUNTS_OUTPUT, index=False)

print("\nSaved bus stop counts:")
print(BUS_COUNTS_OUTPUT)

if len(polygon_rows) > 0:
    walktime_polygons = gpd.GeoDataFrame(
        polygon_rows,
        geometry="geometry",
        crs=TARGET_CRS,
    )

    walktime_polygons.to_file(WALKTIME_POLYGONS_OUTPUT, driver="GPKG")

    print("Saved walk-time polygons:")
    print(WALKTIME_POLYGONS_OUTPUT)
else:
    print("No walk-time polygons created.")


# ============================================================
# Summary
# ============================================================

print("\nSummary")
print("Rows in bus count table:", len(bus_counts))
print("Successful parks:", (bus_counts["status"] == "success").sum())
print("Parks without routing origins:", (bus_counts["status"] == "no_routing_origin_points").sum())
print("Total final kept access point count:", bus_counts["access_point_count"].sum())

print("\nFirst 10 rows:")
print(bus_counts.head(10).to_string(index=False))

print("\nDone.")