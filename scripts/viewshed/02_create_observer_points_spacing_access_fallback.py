# 02_create_observer_points_spacing_access_fallback.py

from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
import pyogrio
import rasterio

from shapely.ops import unary_union, linemerge


# ============================================================
# STEP 2: CREATE SPACING-BASED OBSERVER POINTS
# Hierarchical method:
# 1. Use paths inside park land buffer first.
# 2. If fewer than 3 observers, add nearby 30m network paths.
# 3. If still fewer than 3 observers, add final reach access points.
# 4. Cap large parks using spatially spread farthest-point selection.
# ============================================================


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

PARKS_GDB = PROJECT_ROOT / "data" / "raw" / "Park_Extraction_Project.gdb"
COMPOSITE_GDB = PROJECT_ROOT / "data" / "raw" / "CompositeNetwork3.gdb"
LCC_WATER_RASTER = PROJECT_ROOT / "data" / "raw" / "LCC2020_wateronot.tif"

ACCESS_POINTS_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "reach"
    / "reach_access_points.gpkg"
)

INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "viewshed"
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

FINAL_OBSERVERS_OUTPUT = (
    INTERIM_DIR
    / "observer_points_spacing_access_fallback.gpkg"
)


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

SPACING_OPTIONS_M = [100, 50, 25]

MIN_OBSERVERS_PER_PARK = 3
MAX_OBSERVERS_PER_PARK = 15

NEARBY_PATH_SEARCH_M = 30
MIN_OBSERVER_SEPARATION_M = 50

XY_ROUND = 2


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
        f"Could not find layer '{target_layer_name}' in {gdb_path}.\n"
        f"Available layers:\n{layer_names}"
    )


def points_along_line(line, spacing):
    """
    Generate points along LineString/MultiLineString.

    Starts at spacing/2 so points are centered along lines,
    not clustered at the start of every line segment.
    """
    points = []

    if line is None or line.is_empty:
        return points

    if line.geom_type == "LineString":
        length = line.length

        if length == 0:
            return points

        distances = list(np.arange(spacing / 2, length, spacing))

        if len(distances) == 0:
            distances = [length / 2]

        for dist in distances:
            points.append(line.interpolate(dist))

    elif line.geom_type == "MultiLineString":
        for part in line.geoms:
            points.extend(points_along_line(part, spacing))

    elif line.geom_type == "GeometryCollection":
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


def dedupe_points(points_gdf, xy_round=2):
    if len(points_gdf) == 0:
        return points_gdf

    points_gdf = points_gdf.copy()

    points_gdf["x_round"] = points_gdf.geometry.x.round(xy_round)
    points_gdf["y_round"] = points_gdf.geometry.y.round(xy_round)

    points_gdf = points_gdf.drop_duplicates(
        subset=[PARK_ID_FIELD, "x_round", "y_round"]
    ).copy()

    points_gdf = points_gdf.drop(columns=["x_round", "y_round"])

    return points_gdf


def thin_points_by_distance(points_gdf, min_distance_m):
    """
    Greedy thinning so final observer points are not clustered.
    """
    if len(points_gdf) <= 1:
        return points_gdf.copy()

    points_gdf = points_gdf.copy()
    points_gdf["sort_x"] = points_gdf.geometry.x
    points_gdf["sort_y"] = points_gdf.geometry.y
    points_gdf = points_gdf.sort_values(["sort_x", "sort_y"]).reset_index(drop=True)

    kept_rows = []
    kept_geoms = []

    for _, row in points_gdf.iterrows():
        geom = row.geometry

        if not kept_geoms:
            kept_rows.append(row)
            kept_geoms.append(geom)
            continue

        min_dist = min(geom.distance(existing) for existing in kept_geoms)

        if min_dist >= min_distance_m:
            kept_rows.append(row)
            kept_geoms.append(geom)

    if len(kept_rows) == 0:
        return points_gdf.head(0).copy()

    thinned = gpd.GeoDataFrame(
        kept_rows,
        geometry="geometry",
        crs=points_gdf.crs,
    )

    thinned = thinned.drop(columns=["sort_x", "sort_y"], errors="ignore")

    return thinned


def cap_observers_evenly(points_gdf, max_n):
    """
    If too many observers are created, keep a spatially spread sample.

    Uses a farthest-point approach:
    - start with one reproducible point
    - repeatedly keep the point farthest from already-kept points
    """
    if len(points_gdf) <= max_n:
        return points_gdf.copy()

    points_gdf = points_gdf.copy().reset_index(drop=True)

    points_gdf["sort_x"] = points_gdf.geometry.x
    points_gdf["sort_y"] = points_gdf.geometry.y
    points_gdf = points_gdf.sort_values(["sort_x", "sort_y"]).reset_index(drop=True)

    kept_indices = [0]
    remaining_indices = set(points_gdf.index) - set(kept_indices)

    while len(kept_indices) < max_n and remaining_indices:
        best_idx = None
        best_dist = -1

        for idx in remaining_indices:
            geom = points_gdf.loc[idx].geometry

            min_dist_to_kept = min(
                geom.distance(points_gdf.loc[kept_idx].geometry)
                for kept_idx in kept_indices
            )

            if min_dist_to_kept > best_dist:
                best_dist = min_dist_to_kept
                best_idx = idx

        kept_indices.append(best_idx)
        remaining_indices.remove(best_idx)

    capped = points_gdf.loc[kept_indices].copy()
    capped = capped.drop(columns=["sort_x", "sort_y"], errors="ignore")

    return capped


def merge_linework(paths_gdf):
    """
    Merge/nodalize linework so observer spacing is not applied separately
    to many tiny network segments.

    Handles:
    - one LineString
    - MultiLineString
    - GeometryCollection
    - multiple lines
    """
    if len(paths_gdf) == 0:
        return None

    line_geoms = [
        geom for geom in paths_gdf.geometry
        if geom is not None and not geom.is_empty
    ]

    if len(line_geoms) == 0:
        return None

    merged = unary_union(line_geoms)

    if merged.geom_type == "LineString":
        return merged

    if merged.geom_type == "MultiLineString":
        return linemerge(merged)

    if merged.geom_type == "GeometryCollection":
        lines = [
            geom for geom in merged.geoms
            if geom.geom_type in ["LineString", "MultiLineString"]
        ]

        if len(lines) == 0:
            return None

        if len(lines) == 1:
            only_line = lines[0]
            if only_line.geom_type == "LineString":
                return only_line
            return linemerge(only_line)

        return linemerge(unary_union(lines))

    return None


def generate_candidates_from_paths(
    paths_gdf,
    park_id,
    park_name,
    crs,
    spacing,
    observer_method,
    path_source,
):
    merged_geom = merge_linework(paths_gdf)

    if merged_geom is None or merged_geom.is_empty:
        return gpd.GeoDataFrame(
            columns=[
                PARK_ID_FIELD,
                PARK_NAME_FIELD,
                "observer_source",
                "observer_method",
                "path_source",
                "spacing_m",
                "geometry",
            ],
            geometry="geometry",
            crs=crs,
        )

    pts = points_along_line(merged_geom, spacing)

    rows = []

    for i, pt in enumerate(pts, start=1):
        rows.append({
            PARK_ID_FIELD: park_id,
            PARK_NAME_FIELD: park_name,
            "observer_source": "path_spacing",
            "observer_method": observer_method,
            "path_source": path_source,
            "spacing_m": spacing,
            "candidate_number": i,
            "geometry": pt,
        })

    return gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)


def prepare_candidates(points_gdf):
    """
    Filter water, dedupe, and thin points.
    """
    if len(points_gdf) == 0:
        return points_gdf

    out = filter_points_not_on_water(points_gdf, LCC_WATER_RASTER)
    out = dedupe_points(out, xy_round=XY_ROUND)
    out = thin_points_by_distance(out, min_distance_m=MIN_OBSERVER_SEPARATION_M)

    return out


def choose_spacing_candidates(
    paths_gdf,
    park_id,
    park_name,
    crs,
    observer_method_prefix,
    path_source,
):
    """
    Try 100m, then 50m, then 25m.
    Return the first spacing that gives at least MIN_OBSERVERS_PER_PARK.
    """
    logs = []
    chosen = None
    chosen_spacing = None
    raw_candidate_count = 0
    prepared_candidate_count = 0

    for spacing in SPACING_OPTIONS_M:
        raw_candidates = generate_candidates_from_paths(
            paths_gdf=paths_gdf,
            park_id=park_id,
            park_name=park_name,
            crs=crs,
            spacing=spacing,
            observer_method=f"{observer_method_prefix}_{spacing}m_spacing",
            path_source=path_source,
        )

        raw_candidate_count = len(raw_candidates)

        prepared = prepare_candidates(raw_candidates)
        prepared_candidate_count = len(prepared)

        logs.append({
            "path_source": path_source,
            "spacing_m": spacing,
            "raw_candidate_count": raw_candidate_count,
            "prepared_candidate_count": prepared_candidate_count,
        })

        print(
            f"  {path_source} | spacing {spacing}m: "
            f"{raw_candidate_count} raw, {prepared_candidate_count} prepared"
        )

        if prepared_candidate_count >= MIN_OBSERVERS_PER_PARK:
            chosen = prepared
            chosen_spacing = spacing
            break

        if spacing == SPACING_OPTIONS_M[-1]:
            chosen = prepared
            chosen_spacing = spacing

    if chosen is None:
        chosen = gpd.GeoDataFrame(
            columns=[
                PARK_ID_FIELD,
                PARK_NAME_FIELD,
                "observer_source",
                "observer_method",
                "path_source",
                "spacing_m",
                "geometry",
            ],
            geometry="geometry",
            crs=crs,
        )

    return chosen, chosen_spacing, logs, raw_candidate_count, prepared_candidate_count


def get_access_fallback_points(access_points, park_id, park_name, crs):
    fallback = access_points[access_points[PARK_ID_FIELD] == park_id].copy()

    if len(fallback) == 0:
        return gpd.GeoDataFrame(
            columns=[
                PARK_ID_FIELD,
                PARK_NAME_FIELD,
                "observer_source",
                "observer_method",
                "path_source",
                "spacing_m",
                "geometry",
            ],
            geometry="geometry",
            crs=crs,
        )

    fallback = fallback.explode(index_parts=False).reset_index(drop=True)
    fallback = fallback[fallback.geometry.notna()].copy()
    fallback = fallback[fallback.geometry.geom_type == "Point"].copy()

    fallback[PARK_ID_FIELD] = park_id
    fallback[PARK_NAME_FIELD] = park_name
    fallback["observer_source"] = "access_point_fallback"
    fallback["observer_method"] = "final_reach_access_point_fallback"
    fallback["path_source"] = "final_reach_access_points"
    fallback["spacing_m"] = None

    fallback = fallback[
        [
            PARK_ID_FIELD,
            PARK_NAME_FIELD,
            "observer_source",
            "observer_method",
            "path_source",
            "spacing_m",
            "geometry",
        ]
    ].copy()

    fallback = gpd.GeoDataFrame(fallback, geometry="geometry", crs=crs)
    fallback = filter_points_not_on_water(fallback, LCC_WATER_RASTER)
    fallback = dedupe_points(fallback, xy_round=XY_ROUND)

    return fallback


def add_supplement_points_preserve_existing(
    existing_gdf,
    supplement_gdf,
    target_count,
    min_distance_m,
):
    """
    Keep existing observer points first.
    Add supplement points only if they are far enough from already-kept points.
    This prevents nearby-road points from replacing inside-park path points.
    """
    existing_gdf = existing_gdf.copy().reset_index(drop=True)

    if len(supplement_gdf) == 0:
        return existing_gdf

    kept = existing_gdf.copy()
    kept_geoms = list(kept.geometry)

    supplement_gdf = supplement_gdf.copy().reset_index(drop=True)

    for _, row in supplement_gdf.iterrows():
        if len(kept) >= target_count:
            break

        geom = row.geometry

        if not kept_geoms:
            keep_this = True
        else:
            min_dist = min(
                geom.distance(existing_geom)
                for existing_geom in kept_geoms
            )
            keep_this = min_dist >= min_distance_m

        if keep_this:
            new_row = gpd.GeoDataFrame(
                [row],
                geometry="geometry",
                crs=supplement_gdf.crs,
            )

            kept = pd.concat(
                [kept, new_row],
                ignore_index=True,
            )

            kept_geoms.append(geom)

    return gpd.GeoDataFrame(
        kept,
        geometry="geometry",
        crs=supplement_gdf.crs,
    )


# ============================================================
# Read data
# ============================================================

print("Finding composite network layer...")
network_layer = find_layer(COMPOSITE_GDB, COMPOSITE_NETWORK_LAYER)
print("Using composite network layer:", network_layer)

print("\nReading land buffers, composite network, and access points...")

land = gpd.read_file(PARKS_GDB, layer=LAND_BUFFER_LAYER)
network = gpd.read_file(COMPOSITE_GDB, layer=network_layer)
access_points = gpd.read_file(ACCESS_POINTS_PATH)

land = land[[PARK_ID_FIELD, PARK_NAME_FIELD, "geometry"]].copy()
land[PARK_NAME_FIELD] = land[PARK_NAME_FIELD].astype(str).str.strip()

land = land[land.geometry.notna()].copy()

network = network.to_crs(land.crs)
network = network[network.geometry.notna()].copy()
network = network[
    network.geometry.geom_type.isin(["LineString", "MultiLineString"])
].copy()

access_points = access_points.to_crs(land.crs)
access_points[PARK_ID_FIELD] = access_points[PARK_ID_FIELD].astype(int)
access_points[PARK_NAME_FIELD] = access_points[PARK_NAME_FIELD].astype(str).str.strip()

print("All land buffers:", len(land))
print("Composite network line records:", len(network))
print("Final reach access points:", len(access_points))
print("CRS:", land.crs)


# ============================================================
# Containers
# ============================================================

final_observers = []
log_rows = []


# ============================================================
# Process all parks
# ============================================================

total_parks = len(land)

for park_counter, (_, park) in enumerate(land.iterrows(), start=1):
    park_id = int(park[PARK_ID_FIELD])
    park_name = str(park[PARK_NAME_FIELD]).strip()

    print("\n" + "=" * 80)
    print(f"Processing park {park_counter}/{total_parks}")
    print(f"Park {park_id}: {park_name}")

    park_gdf = gpd.GeoDataFrame(
        [park],
        geometry="geometry",
        crs=land.crs,
    )

    # ========================================================
    # 1. Inside paths only
    # ========================================================

    try:
        inside_paths = gpd.overlay(
            network,
            park_gdf[[PARK_ID_FIELD, PARK_NAME_FIELD, "geometry"]],
            how="intersection",
            keep_geom_type=False,
        )

        inside_paths = inside_paths[
            inside_paths.geometry.geom_type.isin(["LineString", "MultiLineString"])
        ].copy()

        inside_paths = inside_paths.reset_index(drop=True)
        inside_paths["path_source"] = "inside_land_buffer"

    except Exception as e:
        print("  Inside path extraction failed:", e)

        inside_paths = gpd.GeoDataFrame(
            columns=[PARK_ID_FIELD, PARK_NAME_FIELD, "path_source", "geometry"],
            geometry="geometry",
            crs=land.crs,
        )

    print("  Inside path segments:", len(inside_paths))

    inside_candidates, inside_spacing, inside_logs, inside_raw_count, inside_prepared_count = (
        choose_spacing_candidates(
            paths_gdf=inside_paths,
            park_id=park_id,
            park_name=park_name,
            crs=land.crs,
            observer_method_prefix="inside_land_buffer",
            path_source="inside_land_buffer",
        )
    )

    # ========================================================
    # 2. If inside paths are not enough, add nearby 30m points
    #    WITHOUT replacing inside-path points
    # ========================================================

    used_nearby_search = "no"
    nearby_path_segments = 0
    combined_path_segments = len(inside_paths)

    final_path_source = "inside_land_buffer"
    chosen_spacing = inside_spacing
    spacing_logs = []

    for row in inside_logs:
        row["stage"] = "inside_paths"
        spacing_logs.append(row)

    combined_candidates = inside_candidates.copy()

    if len(combined_candidates) < MIN_OBSERVERS_PER_PARK:
        print("  Inside paths produced fewer than minimum observer points.")
        print(
            f"  Keeping inside-path observers and adding nearby "
            f"{NEARBY_PATH_SEARCH_M}m observers if needed..."
        )

        used_nearby_search = "yes"

        nearby_area = park_gdf.copy()
        nearby_area["geometry"] = nearby_area.geometry.buffer(NEARBY_PATH_SEARCH_M)

        try:
            local_network = network[
                network.intersects(nearby_area.geometry.iloc[0])
            ].copy()

            nearby_paths = gpd.overlay(
                local_network,
                nearby_area[[PARK_ID_FIELD, PARK_NAME_FIELD, "geometry"]],
                how="intersection",
                keep_geom_type=False,
            )

            nearby_paths = nearby_paths[
                nearby_paths.geometry.geom_type.isin(["LineString", "MultiLineString"])
            ].copy()

            nearby_paths = nearby_paths.reset_index(drop=True)
            nearby_paths["path_source"] = f"nearby_{NEARBY_PATH_SEARCH_M}m_search_area"

        except Exception as e:
            print("  Nearby path extraction failed:", e)

            nearby_paths = gpd.GeoDataFrame(
                columns=[PARK_ID_FIELD, PARK_NAME_FIELD, "path_source", "geometry"],
                geometry="geometry",
                crs=land.crs,
            )

        nearby_path_segments = len(nearby_paths)
        combined_path_segments = len(inside_paths) + nearby_path_segments

        print("  Nearby path segments:", nearby_path_segments)

        nearby_candidates, nearby_spacing, nearby_logs, nearby_raw_count, nearby_prepared_count = (
            choose_spacing_candidates(
                paths_gdf=nearby_paths,
                park_id=park_id,
                park_name=park_name,
                crs=land.crs,
                observer_method_prefix=f"nearby_{NEARBY_PATH_SEARCH_M}m",
                path_source=f"nearby_{NEARBY_PATH_SEARCH_M}m",
            )
        )

        for row in nearby_logs:
            row["stage"] = "nearby_paths"
            spacing_logs.append(row)

        needed = MIN_OBSERVERS_PER_PARK - len(combined_candidates)

        if len(nearby_candidates) > 0 and needed > 0:
            combined_candidates = add_supplement_points_preserve_existing(
                existing_gdf=combined_candidates,
                supplement_gdf=nearby_candidates,
                target_count=MIN_OBSERVERS_PER_PARK,
                min_distance_m=MIN_OBSERVER_SEPARATION_M,
            )

        chosen_spacing = inside_spacing if len(inside_candidates) > 0 else nearby_spacing
        final_path_source = f"inside_paths_plus_nearby_{NEARBY_PATH_SEARCH_M}m_supplement"

    else:
        print("  Inside paths produced enough observer points.")
        print("  Nearby search not used.")

    # ========================================================
    # 3. Access point fallback only if still fewer than minimum
    # ========================================================

    used_access_fallback = "no"
    access_fallback_added = 0

    final_for_park = combined_candidates.copy()

    if len(final_for_park) < MIN_OBSERVERS_PER_PARK:
        print("  Still fewer than minimum observers.")
        print("  Using final reach access points as fallback...")

        fallback = get_access_fallback_points(
            access_points=access_points,
            park_id=park_id,
            park_name=park_name,
            crs=land.crs,
        )

        needed = MIN_OBSERVERS_PER_PARK - len(final_for_park)
        fallback_to_add = fallback.head(needed).copy()

        access_fallback_added = len(fallback_to_add)

        if access_fallback_added > 0:
            final_for_park = pd.concat(
                [final_for_park, fallback_to_add],
                ignore_index=True,
            )

            final_for_park = gpd.GeoDataFrame(
                final_for_park,
                geometry="geometry",
                crs=land.crs,
            )

            final_for_park = dedupe_points(final_for_park, xy_round=XY_ROUND)
            final_for_park = thin_points_by_distance(
                final_for_park,
                min_distance_m=MIN_OBSERVER_SEPARATION_M,
            )

            used_access_fallback = "yes"

        print("  Access fallback available:", len(fallback))
        print("  Access fallback added:", access_fallback_added)

    # ========================================================
    # 4. Cap large parks and add observer IDs
    # ========================================================

    before_cap_count = len(final_for_park)

    final_for_park = cap_observers_evenly(
        final_for_park,
        max_n=MAX_OBSERVERS_PER_PARK,
    )

    after_cap_count = len(final_for_park)

    capped = "yes" if before_cap_count > after_cap_count else "no"

    final_count = len(final_for_park)

    if final_count > 0:
        final_for_park = final_for_park.reset_index(drop=True)

        for obs_i, obs_idx in enumerate(final_for_park.index, start=1):
            final_for_park.loc[obs_idx, "observer_id"] = f"{park_id}_{obs_i}"
            final_for_park.loc[obs_idx, "observer_number"] = obs_i

        final_for_park["chosen_spacing_m"] = chosen_spacing
        final_for_park["min_observer_separation_m"] = MIN_OBSERVER_SEPARATION_M
        final_for_park["nearby_path_search_m"] = NEARBY_PATH_SEARCH_M
        final_for_park["used_nearby_search"] = used_nearby_search
        final_for_park["used_access_fallback"] = used_access_fallback

        final_observers.append(final_for_park)

    # ========================================================
    # 5. Logs
    # ========================================================

    if final_count < MIN_OBSERVERS_PER_PARK:
        less_than_min = "yes"
        notes = (
            "Fewer than minimum observers available even after inside paths, "
            "nearby path search, and final reach access-point fallback."
        )
    elif used_access_fallback == "yes":
        less_than_min = "no"
        notes = (
            "Used path-based observers plus final reach access-point fallback "
            "to reach minimum observer count."
        )
    elif used_nearby_search == "yes":
        less_than_min = "no"
        notes = (
            f"Inside paths were insufficient, so observers were generated from "
            f"inside paths plus nearby {NEARBY_PATH_SEARCH_M}m supplement."
        )
    elif capped == "yes":
        less_than_min = "no"
        notes = (
            f"Generated spacing-based inside-path observers and capped final "
            f"observers to {MAX_OBSERVERS_PER_PARK}."
        )
    else:
        less_than_min = "no"
        notes = "Generated spacing-based observers from inside park paths."

    log_rows.append({
        PARK_ID_FIELD: park_id,
        PARK_NAME_FIELD: park_name,
        "inside_path_segments": len(inside_paths),
        "inside_candidate_count": len(inside_candidates),
        "used_nearby_search": used_nearby_search,
        "nearby_path_segments": nearby_path_segments,
        "combined_path_segments": combined_path_segments,
        "final_path_source": final_path_source,
        "chosen_spacing_m": chosen_spacing,
        "path_candidate_count": len(combined_candidates),
        "used_access_fallback": used_access_fallback,
        "access_fallback_added_count": access_fallback_added,
        "final_observer_count_before_cap": before_cap_count,
        "final_observer_count": final_count,
        "capped_to_max": capped,
        "less_than_min_observers": less_than_min,
        "notes": notes,
    })

    for row in spacing_logs:
        row[PARK_ID_FIELD] = park_id
        row[PARK_NAME_FIELD] = park_name

    print("  Final path source:", final_path_source)
    print("  Chosen spacing:", chosen_spacing)
    print("  Path candidates kept:", len(combined_candidates))
    print("  Final observers before cap:", before_cap_count)
    print("  Final observers:", final_count)
    print("  Capped:", capped)
    print("  Less than minimum observers:", less_than_min)


# ============================================================
# Save final observer points only
# ============================================================

if FINAL_OBSERVERS_OUTPUT.exists():
    try:
        FINAL_OBSERVERS_OUTPUT.unlink()
    except PermissionError:
        raise PermissionError(
            f"\nCould not overwrite this file because it is open or locked:\n"
            f"{FINAL_OBSERVERS_OUTPUT}\n\n"
            f"Close it in ArcGIS Pro, remove it from the map, or rename the output file."
        )

if final_observers:
    observer_points = pd.concat(final_observers, ignore_index=True)
    observer_points = gpd.GeoDataFrame(
        observer_points,
        geometry="geometry",
        crs=land.crs,
    )
else:
    observer_points = gpd.GeoDataFrame(
        columns=[
            PARK_ID_FIELD,
            PARK_NAME_FIELD,
            "observer_source",
            "observer_method",
            "path_source",
            "spacing_m",
            "observer_id",
            "observer_number",
            "geometry",
        ],
        geometry="geometry",
        crs=land.crs,
    )

observer_points.to_file(FINAL_OBSERVERS_OUTPUT, driver="GPKG")

observer_log = pd.DataFrame(log_rows)

print("\nSaved final observer points:")
print(FINAL_OBSERVERS_OUTPUT)

print("\nObserver summary:")
print(observer_log.to_string(index=False))

print("\nTotal final observer points:", len(observer_points))
print("Parks processed:", len(observer_log))
print(
    "Parks with fewer than minimum observers:",
    (observer_log["less_than_min_observers"] == "yes").sum()
)
print(
    f"Parks using nearby {NEARBY_PATH_SEARCH_M}m search:",
    (observer_log["used_nearby_search"] == "yes").sum()
)
print(
    "Parks using access fallback:",
    (observer_log["used_access_fallback"] == "yes").sum()
)
print(
    "Parks capped to max:",
    (observer_log["capped_to_max"] == "yes").sum()
)

print("\nDone.")