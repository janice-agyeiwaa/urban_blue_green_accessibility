from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
import pyogrio
import rasterio
from sklearn.cluster import KMeans


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[4]

PARKS_GDB = PROJECT_ROOT / "data" / "raw" / "Park_Extraction_Project.gdb"
COMPOSITE_GDB = PROJECT_ROOT / "data" / "raw" / "CompositeNetwork3.gdb"
LCC_WATER_RASTER = PROJECT_ROOT / "data" / "raw" / "LCC2020_wateronot.tif"

INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "viewshed"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "viewshed"

INTERIM_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

RAW_COMPOSITE_PATHS_OUTPUT = INTERIM_DIR / "all114_raw_composite_network_paths.gpkg"
CLIPPED_PATHS_OUTPUT = INTERIM_DIR / "all114_clipped_or_nearby_composite_network_paths.gpkg"
CANDIDATE_POINTS_OUTPUT = INTERIM_DIR / "all114_candidate_observer_points_composite.gpkg"
CLUSTERED_POINTS_OUTPUT = INTERIM_DIR / "all114_candidate_observer_points_clustered_composite.gpkg"
FINAL_OBSERVERS_OUTPUT = PROCESSED_DIR / "all114_observer_points_composite.gpkg"
OBSERVER_LOG_OUTPUT = INTERIM_DIR / "all114_observer_point_log_composite.csv"


# ============================================================
# Layers and fields
# ============================================================

LAND_BUFFER_LAYER = "allparks_land_buffer"
COMPOSITE_NETWORK_LAYER = "OSM_NA_Network_NAD_Point3"

PARK_ID_FIELD = "park_num"
PARK_NAME_FIELD = "PARK_NAME"


# ============================================================
# Settings
# ============================================================

SPACING_OPTIONS_M = [25, 10, 5]
TARGET_OBSERVERS_PER_PARK = 3
NEARBY_PATH_SEARCH_M = 15
RANDOM_STATE = 42


# ============================================================
# Helpers
# ============================================================

def find_layer(gdb_path: Path, target_layer_name: str) -> str:
    layers = pyogrio.list_layers(gdb_path)
    layer_names = [row[0] for row in layers]

    for layer in layer_names:
        if layer.lower() == target_layer_name.lower():
            return layer

    raise ValueError(
        f"Could not find layer '{target_layer_name}' in {gdb_path}.\n"
        f"Available layers:\n{layer_names}"
    )


def points_along_line(line, spacing):
    points = []

    if line is None or line.is_empty:
        return points

    if line.geom_type == "LineString":
        length = line.length

        if length == 0:
            return points

        distances = list(np.arange(0, length, spacing))

        if len(distances) == 0:
            distances = [length / 2]

        for dist in distances:
            points.append(line.interpolate(dist))

    elif line.geom_type == "MultiLineString":
        for part in line.geoms:
            points.extend(points_along_line(part, spacing))

    return points


def filter_points_not_on_water(points_gdf, raster_path):
    """
    LCC2020_wateronot:
    0 = not water
    1 = water
    """
    if len(points_gdf) == 0:
        return points_gdf

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        points_for_sample = points_gdf.to_crs(raster_crs)

        coords = [(geom.x, geom.y) for geom in points_for_sample.geometry]
        sampled_values = [val[0] for val in src.sample(coords)]

    points_gdf = points_gdf.copy()
    points_gdf["lcc_water_value"] = sampled_values

    return points_gdf[points_gdf["lcc_water_value"] == 0].copy()


def generate_candidates_from_paths(paths_gdf, park_id, park_name, crs, spacing, path_source):
    candidate_rows = []

    for _, path_row in paths_gdf.iterrows():
        pts = points_along_line(path_row.geometry, spacing)

        for pt in pts:
            candidate_rows.append({
                PARK_ID_FIELD: park_id,
                PARK_NAME_FIELD: park_name,
                "observer_method": f"{path_source}_candidate_{spacing}m",
                "path_source": path_source,
                "spacing_m": spacing,
                "geometry": pt,
            })

    if len(candidate_rows) == 0:
        return gpd.GeoDataFrame(
            columns=[
                PARK_ID_FIELD,
                PARK_NAME_FIELD,
                "observer_method",
                "path_source",
                "spacing_m",
                "geometry",
            ],
            geometry="geometry",
            crs=crs,
        )

    return gpd.GeoDataFrame(
        candidate_rows,
        geometry="geometry",
        crs=crs,
    )


def select_observers_with_kmeans(candidates, target_n=3):
    selected = []

    if len(candidates) >= target_n:
        coords = np.column_stack([
            candidates.geometry.x,
            candidates.geometry.y,
        ])

        kmeans = KMeans(
            n_clusters=target_n,
            random_state=RANDOM_STATE,
            n_init=10,
        )

        candidates = candidates.copy()
        candidates["cluster_id"] = kmeans.fit_predict(coords)

        for cluster_id in sorted(candidates["cluster_id"].unique()):
            cluster = candidates[candidates["cluster_id"] == cluster_id].copy()
            center = kmeans.cluster_centers_[cluster_id]

            cluster["dist_to_cluster_center"] = np.sqrt(
                (cluster.geometry.x - center[0]) ** 2
                + (cluster.geometry.y - center[1]) ** 2
            )

            chosen = cluster.sort_values("dist_to_cluster_center").iloc[0].copy()
            chosen["observer_method"] = "composite_path_clustered"
            selected.append(chosen)

        return selected, candidates

    candidates = candidates.copy()
    candidates["cluster_id"] = None
    candidates["dist_to_cluster_center"] = None

    for _, cand in candidates.iterrows():
        cand = cand.copy()
        cand["observer_method"] = "composite_path_available_less_than_3"
        selected.append(cand)

    return selected, candidates


def get_paths_for_park(network, park_gdf):
    """
    First tries paths inside land buffer.
    If none exist, tries paths within 15 m of land buffer.
    """
    park_geom = park_gdf.geometry.iloc[0]

    # 1. Paths inside land buffer
    inside = gpd.overlay(
        network,
        park_gdf[[PARK_ID_FIELD, PARK_NAME_FIELD, "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )

    inside = inside[
        inside.geometry.geom_type.isin(["LineString", "MultiLineString"])
    ].copy()

    if len(inside) > 0:
        inside["path_source"] = "inside_land_buffer"
        return inside, "inside_land_buffer"

    # 2. Nearby paths within 15 m, only if no inside paths
    nearby_area = park_gdf.copy()
    nearby_area["geometry"] = nearby_area.geometry.buffer(NEARBY_PATH_SEARCH_M)

    nearby = gpd.overlay(
        network,
        nearby_area[[PARK_ID_FIELD, PARK_NAME_FIELD, "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )

    nearby = nearby[
        nearby.geometry.geom_type.isin(["LineString", "MultiLineString"])
    ].copy()

    if len(nearby) > 0:
        nearby["path_source"] = f"nearby_{NEARBY_PATH_SEARCH_M}m_buffer"
        return nearby, f"nearby_{NEARBY_PATH_SEARCH_M}m_buffer"

    return inside, "no_paths_found"


# ============================================================
# Read data
# ============================================================

print("Finding composite network layer...")
network_layer = find_layer(COMPOSITE_GDB, COMPOSITE_NETWORK_LAYER)
print("Using composite network layer:", network_layer)

print("\nReading land buffers and composite network...")

land = gpd.read_file(PARKS_GDB, layer=LAND_BUFFER_LAYER)
network = gpd.read_file(COMPOSITE_GDB, layer=network_layer)

land = land[[PARK_ID_FIELD, PARK_NAME_FIELD, "geometry"]].copy()
land[PARK_NAME_FIELD] = land[PARK_NAME_FIELD].astype(str).str.strip()
land["geometry"] = land.geometry.make_valid()

network = network.to_crs(land.crs)
network = network[network.geometry.notna()].copy()
network = network[
    network.geometry.geom_type.isin(["LineString", "MultiLineString"])
].copy()

print("All land buffers:", len(land))
print("Composite network line records:", len(network))
print("CRS:", land.crs)

network.to_file(RAW_COMPOSITE_PATHS_OUTPUT, driver="GPKG")
print("\nSaved raw composite network paths:", RAW_COMPOSITE_PATHS_OUTPUT)


# ============================================================
# Containers
# ============================================================

all_clipped_paths = []
all_candidates = []
all_clustered_candidates = []
final_observers = []
log_rows = []


# ============================================================
# Process all parks
# ============================================================

for idx, park in land.iterrows():
    park_id = park[PARK_ID_FIELD]
    park_name = park[PARK_NAME_FIELD]

    print(f"\nProcessing {idx + 1}/{len(land)} | park {park_id}: {park_name}")

    park_gdf = gpd.GeoDataFrame(
        [park],
        geometry="geometry",
        crs=land.crs,
    )

    try:
        paths, path_source = get_paths_for_park(network, park_gdf)

    except Exception as e:
        print("  Path extraction failed:", e)

        log_rows.append({
            PARK_ID_FIELD: park_id,
            PARK_NAME_FIELD: park_name,
            "path_source": "error",
            "clipped_path_segment_count": 0,
            "spacing_used_m": None,
            "raw_candidate_count": 0,
            "non_water_candidate_count": 0,
            "final_observer_count": 0,
            "less_than_3_observers": "yes",
            "notes": f"Composite path extraction failed: {e}",
        })
        continue

    if len(paths) > 0:
        paths[PARK_ID_FIELD] = park_id
        paths[PARK_NAME_FIELD] = park_name
        paths["path_source"] = path_source
        all_clipped_paths.append(paths)

    print("  Path source:", path_source)
    print("  Path segments:", len(paths))

    chosen_candidates = None
    spacing_used = None
    raw_candidate_count = 0
    non_water_candidate_count = 0

    for spacing in SPACING_OPTIONS_M:
        candidates = generate_candidates_from_paths(
            paths,
            park_id,
            park_name,
            land.crs,
            spacing,
            path_source,
        )

        raw_candidate_count = len(candidates)

        candidates = filter_points_not_on_water(
            candidates,
            LCC_WATER_RASTER,
        )

        non_water_candidate_count = len(candidates)

        print(
            f"  Spacing {spacing}m: "
            f"{raw_candidate_count} raw, "
            f"{non_water_candidate_count} non-water candidates"
        )

        if non_water_candidate_count >= TARGET_OBSERVERS_PER_PARK:
            chosen_candidates = candidates
            spacing_used = spacing
            break

        if spacing == SPACING_OPTIONS_M[-1]:
            chosen_candidates = candidates
            spacing_used = spacing

    if chosen_candidates is None:
        chosen_candidates = gpd.GeoDataFrame(
            columns=[
                PARK_ID_FIELD,
                PARK_NAME_FIELD,
                "observer_method",
                "path_source",
                "spacing_m",
                "geometry",
            ],
            geometry="geometry",
            crs=land.crs,
        )

    if len(chosen_candidates) > 0:
        all_candidates.append(chosen_candidates)

    selected, clustered_candidates = select_observers_with_kmeans(
        chosen_candidates,
        target_n=TARGET_OBSERVERS_PER_PARK,
    )

    if len(clustered_candidates) > 0:
        all_clustered_candidates.append(clustered_candidates)

    for i, obs in enumerate(selected[:TARGET_OBSERVERS_PER_PARK], start=1):
        if isinstance(obs, pd.Series):
            row = obs.to_dict()
        else:
            row = obs

        row["observer_id"] = f"{park_id}_{i}"
        row["observer_number"] = i
        final_observers.append(row)

    final_count = min(len(selected), TARGET_OBSERVERS_PER_PARK)

    if final_count < TARGET_OBSERVERS_PER_PARK:
        less_than_3 = "yes"
        notes = (
            "Fewer than 3 path-based observer points available even after "
            "15m nearby-path search and 5m spacing. No polygon fallback was used."
        )
    elif path_source != "inside_land_buffer":
        less_than_3 = "no"
        notes = (
            f"No paths intersected the land buffer, so observer candidates were "
            f"generated from composite paths within {NEARBY_PATH_SEARCH_M}m of the land buffer."
        )
    elif spacing_used != SPACING_OPTIONS_M[0]:
        less_than_3 = "no"
        notes = (
            f"Used reduced spacing of {spacing_used}m to obtain at least "
            "3 path-based observer candidates."
        )
    else:
        less_than_3 = "no"
        notes = "Used default 25m spacing and selected 3 path-based observer points."

    log_rows.append({
        PARK_ID_FIELD: park_id,
        PARK_NAME_FIELD: park_name,
        "path_source": path_source,
        "clipped_path_segment_count": len(paths),
        "spacing_used_m": spacing_used,
        "raw_candidate_count": raw_candidate_count,
        "non_water_candidate_count": non_water_candidate_count,
        "final_observer_count": final_count,
        "less_than_3_observers": less_than_3,
        "notes": notes,
    })

    print("  Final observers:", final_count)
    print("  Spacing used:", spacing_used)
    print("  Less than 3 observers:", less_than_3)


# ============================================================
# Save outputs
# ============================================================

if all_clipped_paths:
    clipped_paths = pd.concat(all_clipped_paths, ignore_index=True)
    clipped_paths = gpd.GeoDataFrame(
        clipped_paths,
        geometry="geometry",
        crs=land.crs,
    )
    clipped_paths.to_file(CLIPPED_PATHS_OUTPUT, driver="GPKG")
    print("\nSaved clipped/nearby composite paths:", CLIPPED_PATHS_OUTPUT)

if all_candidates:
    candidate_points = pd.concat(all_candidates, ignore_index=True)
    candidate_points = gpd.GeoDataFrame(
        candidate_points,
        geometry="geometry",
        crs=land.crs,
    )
    candidate_points.to_file(CANDIDATE_POINTS_OUTPUT, driver="GPKG")
    print("Saved candidate observer points:", CANDIDATE_POINTS_OUTPUT)

if all_clustered_candidates:
    clustered_points = pd.concat(all_clustered_candidates, ignore_index=True)
    clustered_points = gpd.GeoDataFrame(
        clustered_points,
        geometry="geometry",
        crs=land.crs,
    )
    clustered_points.to_file(CLUSTERED_POINTS_OUTPUT, driver="GPKG")
    print("Saved clustered candidate points:", CLUSTERED_POINTS_OUTPUT)

observer_points = gpd.GeoDataFrame(
    final_observers,
    geometry="geometry",
    crs=land.crs,
)

observer_points.to_file(FINAL_OBSERVERS_OUTPUT, driver="GPKG")

observer_log = pd.DataFrame(log_rows)
observer_log.to_csv(OBSERVER_LOG_OUTPUT, index=False)

print("\nSaved final observer points:", FINAL_OBSERVERS_OUTPUT)
print("Saved observer log:", OBSERVER_LOG_OUTPUT)

print("\nObserver summary:")
print(observer_log)

print("\nTotal final observer points:", len(observer_points))
print("Expected maximum:", len(land) * TARGET_OBSERVERS_PER_PARK)
print("Parks with fewer than 3 observers:", (observer_log["less_than_3_observers"] == "yes").sum())
print("Parks using nearby 15m paths:", (observer_log["path_source"] == f"nearby_{NEARBY_PATH_SEARCH_M}m_buffer").sum())
print("Done.")
