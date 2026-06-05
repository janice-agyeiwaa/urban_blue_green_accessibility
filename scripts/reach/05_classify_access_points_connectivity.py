# 05_classify_access_points_connectivity.py

from pathlib import Path
import geopandas as gpd
import pandas as pd
import networkx as nx

from shapely.geometry import Point, MultiPoint
from shapely.ops import unary_union, split
from shapely.strtree import STRtree


# ============================================================
# STEP 5: CLASSIFY DEDUPED ACCESS POINTS BY OUTSIDE CONNECTIVITY
# ============================================================

# -------------------------
# Paths
# -------------------------
PROJECT_ROOT = Path(r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility")

PARKS_PATH = PROJECT_ROOT / "data" / "raw" / "Park_Extraction_Project.gdb"
PARKS_LAYER = "allparks_land_buffer"

NETWORK_PATH = PROJECT_ROOT / "data" / "raw" / "CompositeNetwork3.gdb"
NETWORK_LAYER = "OSM_NA_Network_NAD_Point3"

INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "reach"
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

INPUT_POINTS = INTERIM_DIR / "candidate_access_points_deduped.gpkg"

CLASSIFIED_OUTPUT = INTERIM_DIR / "candidate_access_points_connectivity_classified.gpkg"
SUMMARY_OUTPUT = INTERIM_DIR / "candidate_access_points_connectivity_summary.csv"

# -------------------------
# Config
# -------------------------
LOCAL_NETWORK_CLIP_BUFFER_M = 500

NODE_ROUND = 3
POINT_ON_LINE_TOL_M = 0.05
GRAPH_NODE_SNAP_TOL_M = 0.25

PARK_ID_FIELD = "park_num"
PARK_NAME_FIELD = "PARK_NAME"

VALID_HIGHWAYS = {
    "footway",
    "path",
    "pedestrian",
    "steps",
    "track",
    "service",
    "residential",
    "living_street",
    "cycleway",
    "unclassified",
    "tertiary",
    "tertiary_link",
    "secondary",
    "secondary_link",
    "primary",
    "primary_link",
}

BAD_HIGHWAYS = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
}

BAD_RAILWAY_VALUES = {
    "rail",
    "light_rail",
    "subway",
    "tram",
    "monorail",
}


# ============================================================
# HELPERS
# ============================================================

def explode_to_lines(geom):
    if geom is None or geom.is_empty:
        return []

    gt = geom.geom_type

    if gt == "LineString":
        return [geom]

    if gt == "MultiLineString":
        return list(geom.geoms)

    if gt == "GeometryCollection":
        lines = []
        for g in geom.geoms:
            lines.extend(explode_to_lines(g))
        return lines

    return []


def node_key(pt):
    return (round(pt.x, NODE_ROUND), round(pt.y, NODE_ROUND))


def line_endpoints(line):
    coords = list(line.coords)
    return Point(coords[0]), Point(coords[-1])


def split_line_by_points(line, points, tol=0.05):
    if line is None or line.is_empty:
        return []

    split_pts = []

    for pt in points:
        if line.distance(pt) <= tol:
            projected = line.interpolate(line.project(pt))
            d = line.project(projected)

            # Avoid splitting exactly at endpoints
            if d > tol and d < line.length - tol:
                split_pts.append(projected)

    if not split_pts:
        return [line]

    try:
        result = split(line, MultiPoint(split_pts))
        return [g for g in result.geoms if g.length > 0.001]
    except Exception:
        return [line]


def get_field(gdf, possible_names):
    lower_map = {c.lower(): c for c in gdf.columns}

    for name in possible_names:
        if name.lower() in lower_map:
            return lower_map[name.lower()]

    return None


def is_walkable(row, highway_field, railway_field):
    highway = str(row.get(highway_field, "")).lower() if highway_field else ""
    railway = str(row.get(railway_field, "")).lower() if railway_field else ""

    if railway in BAD_RAILWAY_VALUES:
        return False

    if highway in BAD_HIGHWAYS:
        return False

    if highway_field:
        return highway in VALID_HIGHWAYS

    return True


def get_method_value(row):
    if "method" in row.index:
        return str(row.get("method", "")).lower()
    return ""


# ============================================================
# LOAD DATA
# ============================================================

print("Reading parks...")
parks = gpd.read_file(PARKS_PATH, layer=PARKS_LAYER)

print("Reading network...")
network = gpd.read_file(NETWORK_PATH, layer=NETWORK_LAYER)

print("Reading deduped access points...")
access_points = gpd.read_file(INPUT_POINTS)

print(f"Parks: {len(parks)}")
print(f"Network segments: {len(network)}")
print(f"Input deduped access points: {len(access_points)}")

if network.crs != parks.crs:
    print("Reprojecting network to parks CRS...")
    network = network.to_crs(parks.crs)

if access_points.crs != parks.crs:
    print("Reprojecting access points to parks CRS...")
    access_points = access_points.to_crs(parks.crs)

park_num_field = get_field(parks, ["park_num", "PARK_NUM"])
park_name_field = get_field(parks, ["PARK_NAME", "park_name", "name"])

if park_num_field is None:
    raise ValueError("Could not find park_num field in parks layer.")

highway_field = get_field(network, ["highway", "HIGHWAY"])
railway_field = get_field(network, ["railway", "RAILWAY"])

print(f"Highway field: {highway_field}")
print(f"Railway field: {railway_field}")

# Add global AP id
access_points = access_points.reset_index(drop=True).copy()
access_points["global_ap_id"] = access_points.index + 1

classified_parts = []
summary_rows = []


# ============================================================
# PROCESS EACH PARK
# ============================================================

park_ids = sorted(access_points[PARK_ID_FIELD].dropna().unique())

print(f"\nParks to process from access-point layer: {len(park_ids)}")

for i, park_id in enumerate(park_ids, start=1):
    park_match = parks[parks[park_num_field] == park_id].copy()
    park_points = access_points[access_points[PARK_ID_FIELD] == park_id].copy()

    if park_match.empty:
        park_points["decision"] = "review"
        park_points["reason"] = "park polygon not found"
        park_points["join_type"] = "none"
        park_points["component_id"] = None
        park_points["outside_total_len_m"] = 0
        park_points["outside_edge_count"] = 0
        park_points["outside_node_count"] = 0
        park_points["outside_junction_count"] = 0
        park_points["outside_has_junction"] = False
        park_points["same_comp_ap_count"] = 0
        park_points["graph_node"] = None
        park_points["snap_dist_m"] = None

        classified_parts.append(park_points)

        summary_rows.append({
            "park_num": park_id,
            "PARK_NAME": None,
            "input_points": len(park_points),
            "keep": 0,
            "review": len(park_points),
            "remove": 0,
            "note": "park polygon not found"
        })

        print(f"{i}/{len(park_ids)} Park {park_id}: park polygon not found")
        continue

    park_row = park_match.iloc[0]
    park_name = park_row[park_name_field] if park_name_field else f"Park {park_id}"
    park_poly = park_row.geometry

    print("\n" + "-" * 80)
    print(f"{i}/{len(park_ids)} Park {park_id}: {park_name}")
    print(f"Access points: {len(park_points)}")

    # -------------------------
    # Local walkable network
    # -------------------------
    search_area = park_poly.buffer(LOCAL_NETWORK_CLIP_BUFFER_M)

    local_network = network[network.intersects(search_area)].copy()
    print(f"Local network segments before walkable filter: {len(local_network)}")

    if local_network.empty:
        park_points["decision"] = "review"
        park_points["reason"] = "no local network found within context buffer"
        park_points["join_type"] = "none"
        park_points["component_id"] = None
        park_points["outside_total_len_m"] = 0
        park_points["outside_edge_count"] = 0
        park_points["outside_node_count"] = 0
        park_points["outside_junction_count"] = 0
        park_points["outside_has_junction"] = False
        park_points["same_comp_ap_count"] = 0
        park_points["graph_node"] = None
        park_points["snap_dist_m"] = None

        classified_parts.append(park_points)

        summary_rows.append({
            "park_num": park_id,
            "PARK_NAME": park_name,
            "input_points": len(park_points),
            "keep": 0,
            "review": len(park_points),
            "remove": 0,
            "note": "no local network found"
        })

        continue

    local_network["is_walkable"] = local_network.apply(
        lambda row: is_walkable(row, highway_field, railway_field),
        axis=1
    )

    walkable = local_network[local_network["is_walkable"]].copy()
    print(f"Walkable local network segments: {len(walkable)}")

    if walkable.empty:
        park_points["decision"] = "review"
        park_points["reason"] = "no walkable local network found"
        park_points["join_type"] = "none"
        park_points["component_id"] = None
        park_points["outside_total_len_m"] = 0
        park_points["outside_edge_count"] = 0
        park_points["outside_node_count"] = 0
        park_points["outside_junction_count"] = 0
        park_points["outside_has_junction"] = False
        park_points["same_comp_ap_count"] = 0
        park_points["graph_node"] = None
        park_points["snap_dist_m"] = None

        classified_parts.append(park_points)

        summary_rows.append({
            "park_num": park_id,
            "PARK_NAME": park_name,
            "input_points": len(park_points),
            "keep": 0,
            "review": len(park_points),
            "remove": 0,
            "note": "no walkable local network found"
        })

        continue

    # -------------------------
    # Build outside graph
    # -------------------------
    outside_lines = []

    for _, row in walkable.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        outside = geom.difference(park_poly)

        for line in explode_to_lines(outside):
            if line.length > 0.001:
                outside_lines.append(line)

    print(f"Outside line pieces before noding: {len(outside_lines)}")

    if not outside_lines:
        park_points["decision"] = "review"
        park_points["reason"] = "no outside network linework found"
        park_points["join_type"] = "none"
        park_points["component_id"] = None
        park_points["outside_total_len_m"] = 0
        park_points["outside_edge_count"] = 0
        park_points["outside_node_count"] = 0
        park_points["outside_junction_count"] = 0
        park_points["outside_has_junction"] = False
        park_points["same_comp_ap_count"] = 0
        park_points["graph_node"] = None
        park_points["snap_dist_m"] = None

        classified_parts.append(park_points)

        summary_rows.append({
            "park_num": park_id,
            "PARK_NAME": park_name,
            "input_points": len(park_points),
            "keep": 0,
            "review": len(park_points),
            "remove": 0,
            "note": "no outside linework"
        })

        continue

    outside_union = unary_union(outside_lines)
    noded_lines = explode_to_lines(outside_union)

    candidate_points = list(park_points.geometry)

    final_graph_lines = []

    for line in noded_lines:
        split_parts = split_line_by_points(
            line,
            candidate_points,
            POINT_ON_LINE_TOL_M
        )
        final_graph_lines.extend(split_parts)

    print(f"Final graph line pieces: {len(final_graph_lines)}")

    # -------------------------
    # Build graph
    # -------------------------
    G = nx.Graph()

    for edge_i, line in enumerate(final_graph_lines):
        if line.length <= 0.001:
            continue

        p1, p2 = line_endpoints(line)
        n1 = node_key(p1)
        n2 = node_key(p2)

        if n1 == n2:
            continue

        G.add_node(n1, x=n1[0], y=n1[1])
        G.add_node(n2, x=n2[0], y=n2[1])
        G.add_edge(n1, n2, length=line.length, edge_id=edge_i)

    print(f"Graph nodes: {G.number_of_nodes()}")
    print(f"Graph edges: {G.number_of_edges()}")

    if G.number_of_nodes() == 0:
        park_points["decision"] = "review"
        park_points["reason"] = "outside graph could not be built"
        park_points["join_type"] = "none"
        park_points["component_id"] = None
        park_points["outside_total_len_m"] = 0
        park_points["outside_edge_count"] = 0
        park_points["outside_node_count"] = 0
        park_points["outside_junction_count"] = 0
        park_points["outside_has_junction"] = False
        park_points["same_comp_ap_count"] = 0
        park_points["graph_node"] = None
        park_points["snap_dist_m"] = None

        classified_parts.append(park_points)

        summary_rows.append({
            "park_num": park_id,
            "PARK_NAME": park_name,
            "input_points": len(park_points),
            "keep": 0,
            "review": len(park_points),
            "remove": 0,
            "note": "outside graph could not be built"
        })

        continue

    # -------------------------
    # Link APs to graph nodes
    # -------------------------
    graph_node_keys = list(G.nodes)
    graph_node_points = [Point(n[0], n[1]) for n in graph_node_keys]
    tree = STRtree(graph_node_points)

    def nearest_graph_node(pt, max_dist=GRAPH_NODE_SNAP_TOL_M):
        if len(graph_node_points) == 0:
            return None, None

        nearest_idx = tree.nearest(pt)
        nearest_pt = graph_node_points[nearest_idx]
        dist = pt.distance(nearest_pt)

        if dist <= max_dist:
            return graph_node_keys[nearest_idx], dist

        return None, dist

    ap_to_node = {}

    for idx, row in park_points.iterrows():
        ap_id = row["global_ap_id"]
        pt = row.geometry

        nkey, dist = nearest_graph_node(pt)

        park_points.loc[idx, "graph_node"] = str(nkey) if nkey else None
        park_points.loc[idx, "snap_dist_m"] = dist

        if nkey:
            ap_to_node[ap_id] = nkey

    # -------------------------
    # Component analysis
    # -------------------------
    components = list(nx.connected_components(G))

    node_to_component = {}

    for comp_id, comp_nodes in enumerate(components, start=1):
        for n in comp_nodes:
            node_to_component[n] = comp_id

    component_stats = {}

    for comp_id, comp_nodes in enumerate(components, start=1):
        sub = G.subgraph(comp_nodes)

        total_len = sum(data["length"] for _, _, data in sub.edges(data=True))
        edge_count = sub.number_of_edges()
        node_count = sub.number_of_nodes()
        junction_nodes = [n for n, deg in sub.degree() if deg >= 3]

        component_stats[comp_id] = {
            "component_id": comp_id,
            "outside_total_len_m": total_len,
            "outside_edge_count": edge_count,
            "outside_node_count": node_count,
            "outside_junction_count": len(junction_nodes),
            "outside_has_junction": len(junction_nodes) > 0,
            "same_comp_ap_count": 0
        }

    comp_to_aps = {}

    for ap_id, nkey in ap_to_node.items():
        comp_id = node_to_component.get(nkey)
        if comp_id:
            comp_to_aps.setdefault(comp_id, []).append(ap_id)

    for comp_id, aps in comp_to_aps.items():
        component_stats[comp_id]["same_comp_ap_count"] = len(aps)

    # -------------------------
    # Decision rules
    # -------------------------
    decision_rows = []

    for idx, row in park_points.iterrows():
        ap_id = row["global_ap_id"]
        nkey = ap_to_node.get(ap_id)
        method_value = get_method_value(row)

        # --------------------------------------------------------
        # MANUAL POINTS:
        # Manual access points were intentionally added for the
        # parks that had no automatic boundary/network points.
        # Keep them all.
        # --------------------------------------------------------
        if "manual" in method_value:
            comp_id = None
            stats = {
                "outside_total_len_m": 0,
                "outside_edge_count": 0,
                "outside_node_count": 0,
                "outside_junction_count": 0,
                "outside_has_junction": False,
                "same_comp_ap_count": 0
            }

            decision = "keep"
            reason = "manual access point kept"
            join_type = "manual"

        elif nkey is None:
            comp_id = None
            stats = {
                "outside_total_len_m": 0,
                "outside_edge_count": 0,
                "outside_node_count": 0,
                "outside_junction_count": 0,
                "outside_has_junction": False,
                "same_comp_ap_count": 0
            }

            decision = "remove"
            reason = "no outside graph connection found"
            join_type = "none"

        else:
            comp_id = node_to_component.get(nkey)
            stats = component_stats[comp_id]

            outside_has_junction = stats["outside_has_junction"]
            same_comp_ap_count = stats["same_comp_ap_count"]
            outside_edge_count = stats["outside_edge_count"]

            if outside_has_junction:
                decision = "keep"
                reason = "outside road/path has another walkable line joining it along the way"
                join_type = "outside_line_join"

            elif same_comp_ap_count >= 2:
                decision = "review"
                reason = "same outside road/path connects multiple access points but no other line joins it"
                join_type = "ap_to_ap_only"

            elif outside_edge_count >= 1:
                decision = "review"
                reason = "outside line exists but no joining road/path detected"
                join_type = "single_outside_line"

            else:
                decision = "remove"
                reason = "no meaningful outside edge"
                join_type = "none"

        decision_rows.append({
            "global_ap_id": ap_id,
            "component_id": comp_id,
            "decision": decision,
            "reason": reason,
            "join_type": join_type,
            **stats
        })

    decision_df = pd.DataFrame(decision_rows)

    park_points = park_points.merge(
        decision_df,
        on="global_ap_id",
        how="left"
    )

    classified_parts.append(park_points)

    decision_counts = park_points["decision"].value_counts(dropna=False).to_dict()

    summary_rows.append({
        "park_num": park_id,
        "PARK_NAME": park_name,
        "input_points": len(park_points),
        "keep": decision_counts.get("keep", 0),
        "review": decision_counts.get("review", 0),
        "remove": decision_counts.get("remove", 0),
        "note": "processed"
    })

    print("Decision counts:")
    print(park_points["decision"].value_counts(dropna=False))


# ============================================================
# SAVE OUTPUTS
# ============================================================

classified = gpd.GeoDataFrame(
    pd.concat(classified_parts, ignore_index=True),
    geometry="geometry",
    crs=access_points.crs
)

summary = pd.DataFrame(summary_rows).sort_values("park_num")

classified.to_file(
    CLASSIFIED_OUTPUT,
    layer="access_points_connectivity_classified",
    driver="GPKG"
)

summary.to_csv(SUMMARY_OUTPUT, index=False)

print("\n" + "=" * 80)
print("STEP 5 COMPLETE")
print("=" * 80)

print("\nSaved classified access points:")
print(CLASSIFIED_OUTPUT)

print("\nSaved summary CSV:")
print(SUMMARY_OUTPUT)

print("\nOverall decision counts:")
print(classified["decision"].value_counts(dropna=False))

print("\nDone.")