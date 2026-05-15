from pathlib import Path
import geopandas as gpd
import pandas as pd
import osmnx as ox
from shapely.geometry import Point
from sklearn.cluster import KMeans
import numpy as np

# -------------------------
# Paths
# -------------------------
land_buffer_path = r"data\raw\Park_Extraction_Project.gdb"
land_buffer_layer = "allparks_land_buffer"

pilot_parks_path = Path(r"data\processed\reach\pilot_10_parks.csv")

interim_dir = Path(r"data\interim\viewshed")
processed_dir = Path(r"data\processed\viewshed")

interim_dir.mkdir(parents=True, exist_ok=True)
processed_dir.mkdir(parents=True, exist_ok=True)

raw_osm_paths_output = interim_dir / "pilot_10_raw_osm_walk_paths.gpkg"
clipped_paths_output = interim_dir / "pilot_10_clipped_osm_paths.gpkg"
candidate_points_output = interim_dir / "pilot_10_candidate_observer_points.gpkg"
clustered_points_output = interim_dir / "pilot_10_candidate_observer_points_clustered.gpkg"
final_observers_output = processed_dir / "pilot_10_observer_points.gpkg"
observer_log_output = interim_dir / "pilot_10_observer_point_log.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# Settings
# -------------------------
candidate_spacing_m = 25
target_observers_per_park = 3
osm_buffer_degrees = 0.005
random_state = 42

# -------------------------
# Read data
# -------------------------
land = gpd.read_file(land_buffer_path, layer=land_buffer_layer)
pilot = pd.read_csv(pilot_parks_path)

land = land[[park_id_field, park_name_field, "geometry"]].copy()
land[park_name_field] = land[park_name_field].astype(str).str.strip()

pilot_ids = pilot[park_id_field].tolist()
pilot_land = land[land[park_id_field].isin(pilot_ids)].copy()

print("Pilot land buffers:", len(pilot_land))
print("CRS:", pilot_land.crs)

# -------------------------
# Helper: generate points along a line
# -------------------------
def points_along_line(line, spacing):
    points = []

    if line is None or line.is_empty:
        return points

    if line.geom_type == "LineString":
        length = line.length

        if length == 0:
            return points

        distances = list(np.arange(0, length, spacing))

        # Make sure each usable segment gets at least one middle point
        if len(distances) == 0:
            distances = [length / 2]

        for dist in distances:
            points.append(line.interpolate(dist))

    elif line.geom_type == "MultiLineString":
        for part in line.geoms:
            points.extend(points_along_line(part, spacing))

    return points

# -------------------------
# Containers
# -------------------------
all_clipped_paths = []
all_candidates = []
all_clustered_candidates = []
final_observers = []
log_rows = []

# -------------------------
# Process each pilot park
# -------------------------
all_raw_osm_paths = []
for _, park in pilot_land.iterrows():
    park_id = park[park_id_field]
    park_name = park[park_name_field]

    print(f"\nProcessing park {park_id}: {park_name}")

    park_gdf = gpd.GeoDataFrame([park], geometry="geometry", crs=pilot_land.crs)
    park_geom = park_gdf.geometry.iloc[0]

    # Download OSM walking network
    park_wgs84 = park_gdf.to_crs(epsg=4326)
    study_area = park_wgs84.geometry.iloc[0].buffer(osm_buffer_degrees)

    try:
        G = ox.graph_from_polygon(
            study_area,
            network_type="walk",
            simplify=True
        )

        edges = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index()
        edges = edges.to_crs(pilot_land.crs)

        edges_copy = edges.copy()
        edges_copy[park_id_field] = park_id
        edges_copy[park_name_field] = park_name
        all_raw_osm_paths.append(edges_copy)

    except Exception as e:
        print("  OSM download failed:", e)
        log_rows.append({
            park_id_field: park_id,
            park_name_field: park_name,
            "candidate_count": 0,
            "final_observer_count": 0,
            "fallback_used": "yes",
            "notes": f"OSM download failed: {e}"
        })
        continue

    # Clip OSM paths to the land buffer
    clipped = gpd.overlay(
        edges,
        park_gdf[[park_id_field, park_name_field, "geometry"]],
        how="intersection",
        keep_geom_type=False
    )

    clipped = clipped[
        clipped.geom_type.isin(["LineString", "MultiLineString"])
    ].copy()

    if len(clipped) > 0:
        clipped[park_id_field] = park_id
        clipped[park_name_field] = park_name
        all_clipped_paths.append(clipped)

    # Generate candidate points along clipped paths
    candidate_rows = []

    for _, path_row in clipped.iterrows():
        pts = points_along_line(path_row.geometry, candidate_spacing_m)

        for pt in pts:
            candidate_rows.append({
                park_id_field: park_id,
                park_name_field: park_name,
                "observer_method": "path_candidate",
                "geometry": pt
            })

    candidates = gpd.GeoDataFrame(
        candidate_rows,
        geometry="geometry",
        crs=pilot_land.crs
    ) if len(candidate_rows) > 0 else gpd.GeoDataFrame(
        columns=[park_id_field, park_name_field, "observer_method", "geometry"],
        geometry="geometry",
        crs=pilot_land.crs
    )

    print("  Candidate points:", len(candidates))

    if len(candidates) > 0:
        all_candidates.append(candidates)

    # -------------------------
    # Select final observers
    # -------------------------
    selected = []

    if len(candidates) >= target_observers_per_park:
        coords = np.column_stack([
            candidates.geometry.x,
            candidates.geometry.y
        ])

        kmeans = KMeans(
            n_clusters=target_observers_per_park,
            random_state=random_state,
            n_init=10
        )

        candidates["cluster_id"] = kmeans.fit_predict(coords)

        # Pick the candidate closest to each cluster center
        for cluster_id in sorted(candidates["cluster_id"].unique()):
            cluster = candidates[candidates["cluster_id"] == cluster_id].copy()
            center = kmeans.cluster_centers_[cluster_id]

            cluster["dist_to_cluster_center"] = np.sqrt(
                (cluster.geometry.x - center[0]) ** 2 +
                (cluster.geometry.y - center[1]) ** 2
            )

            chosen = cluster.sort_values("dist_to_cluster_center").iloc[0].copy()
            chosen["observer_method"] = "path_clustered"
            selected.append(chosen)

        all_clustered_candidates.append(candidates)

        fallback_used = "no"
        notes = "Selected one observer point from each of 3 spatial clusters."

    else:
        # Fallback: use available path candidates first, then add polygon representative points
        fallback_used = "yes"
        notes = "Fewer than 3 path candidates; used available path candidates and polygon fallback points."

        if len(candidates) > 0:
            candidates["cluster_id"] = None
            candidates["dist_to_cluster_center"] = None

            for _, cand in candidates.iterrows():
                cand = cand.copy()
                cand["observer_method"] = "path_candidate_fallback"
                selected.append(cand)

            all_clustered_candidates.append(candidates)

        # Add fallback points using representative point, centroid, and buffer boundary point
        needed = target_observers_per_park - len(selected)

        fallback_points = []

        rep = park_geom.representative_point()
        fallback_points.append(rep)

        centroid = park_geom.centroid
        if park_geom.contains(centroid):
            fallback_points.append(centroid)

        # Add a point on the boundary if needed
        boundary_point = park_geom.boundary.interpolate(park_geom.boundary.length / 2)
        fallback_points.append(boundary_point)

        for pt in fallback_points:
            if needed <= 0:
                break

            if park_geom.contains(pt) or park_geom.touches(pt):
                selected.append({
                    park_id_field: park_id,
                    park_name_field: park_name,
                    "observer_method": "polygon_fallback",
                    "cluster_id": None,
                    "dist_to_cluster_center": None,
                    "geometry": pt
                })
                needed -= 1

    # Build final observer rows
    for i, obs in enumerate(selected[:target_observers_per_park], start=1):
        if isinstance(obs, pd.Series):
            row = obs.to_dict()
        else:
            row = obs

        row["observer_id"] = f"{park_id}_{i}"
        row["observer_number"] = i
        final_observers.append(row)

    log_rows.append({
        park_id_field: park_id,
        park_name_field: park_name,
        "candidate_count": len(candidates),
        "final_observer_count": min(len(selected), target_observers_per_park),
        "fallback_used": fallback_used,
        "notes": notes
    })

    print("  Final observers:", min(len(selected), target_observers_per_park))
    print("  Fallback used:", fallback_used)

# -------------------------
# Save outputs
# -------------------------
if all_raw_osm_paths:
    raw_osm_paths = pd.concat(all_raw_osm_paths, ignore_index=True)
    raw_osm_paths = gpd.GeoDataFrame(raw_osm_paths, geometry="geometry", crs=pilot_land.crs)
    raw_osm_paths.to_file(raw_osm_paths_output, driver="GPKG")
    print("\nSaved raw OSM paths:", raw_osm_paths_output)

if all_clipped_paths:
    clipped_paths = pd.concat(all_clipped_paths, ignore_index=True)
    clipped_paths = gpd.GeoDataFrame(clipped_paths, geometry="geometry", crs=pilot_land.crs)
    clipped_paths.to_file(clipped_paths_output, driver="GPKG")
    print("\nSaved clipped paths:", clipped_paths_output)

if all_candidates:
    candidate_points = pd.concat(all_candidates, ignore_index=True)
    candidate_points = gpd.GeoDataFrame(candidate_points, geometry="geometry", crs=pilot_land.crs)
    candidate_points.to_file(candidate_points_output, driver="GPKG")
    print("Saved candidate points:", candidate_points_output)

if all_clustered_candidates:
    clustered_points = pd.concat(all_clustered_candidates, ignore_index=True)
    clustered_points = gpd.GeoDataFrame(clustered_points, geometry="geometry", crs=pilot_land.crs)
    clustered_points.to_file(clustered_points_output, driver="GPKG")
    print("Saved clustered candidate points:", clustered_points_output)

observer_points = gpd.GeoDataFrame(final_observers, geometry="geometry", crs=pilot_land.crs)
observer_points.to_file(final_observers_output, driver="GPKG")

observer_log = pd.DataFrame(log_rows)
observer_log.to_csv(observer_log_output, index=False)

print("Saved final observer points:", final_observers_output)
print("Saved observer log:", observer_log_output)

print("\nObserver summary:")
print(observer_log)