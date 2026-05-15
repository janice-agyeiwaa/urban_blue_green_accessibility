from pathlib import Path
import geopandas as gpd
import pandas as pd
import osmnx as ox

# -------------------------
# Paths
# -------------------------
land_buffer_path = r"data\raw\Park_Extraction_Project.gdb"
land_buffer_layer = "allparks_land_buffer"

pilot_parks_path = Path(r"data\processed\reach\pilot_10_parks.csv")

output_dir = Path(r"data\interim\viewshed")
output_dir.mkdir(parents=True, exist_ok=True)

summary_output = output_dir / "pilot_10_land_buffer_path_summary.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# Settings
# -------------------------
osm_buffer_degrees = 0.005
spacing_options = [50, 25]

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
# Summarize each pilot park
# -------------------------
rows = []

for idx, park in pilot_land.iterrows():
    park_id = park[park_id_field]
    park_name = park[park_name_field]

    print(f"\nProcessing park {park_id}: {park_name}")

    park_gdf = gpd.GeoDataFrame([park], geometry="geometry", crs=pilot_land.crs)

    area_m2 = park_gdf.geometry.area.iloc[0]
    perimeter_m = park_gdf.geometry.length.iloc[0]

    # OSMnx needs WGS84
    park_wgs84 = park_gdf.to_crs(epsg=4326)
    study_area = park_wgs84.geometry.iloc[0].buffer(osm_buffer_degrees)

    path_length_inside_m = 0
    osm_edge_count_inside = 0
    osm_status = "ok"

    try:
        G = ox.graph_from_polygon(
            study_area,
            network_type="walk",
            simplify=True
        )

        edges = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index()
        edges = edges.to_crs(pilot_land.crs)

        # Clip/intersect OSM walking edges to the land buffer
        clipped_edges = gpd.overlay(
            edges,
            park_gdf[[park_id_field, park_name_field, "geometry"]],
            how="intersection",
            keep_geom_type=False
        )

        # Keep only line geometries
        clipped_edges = clipped_edges[
            clipped_edges.geom_type.isin(["LineString", "MultiLineString"])
        ].copy()

        osm_edge_count_inside = len(clipped_edges)

        if len(clipped_edges) > 0:
            path_length_inside_m = clipped_edges.geometry.length.sum()
        else:
            osm_status = "no_osm_paths_inside_buffer"

    except Exception as e:
        osm_status = f"failed: {e}"

    row = {
        park_id_field: park_id,
        park_name_field: park_name,
        "land_buffer_area_m2": round(area_m2, 2),
        "land_buffer_perimeter_m": round(perimeter_m, 2),
        "osm_path_length_inside_buffer_m": round(path_length_inside_m, 2),
        "osm_edge_count_inside_buffer": osm_edge_count_inside,
        "osm_status": osm_status,
    }

    for spacing in spacing_options:
        if path_length_inside_m > 0:
            estimated_count = max(1, int(path_length_inside_m // spacing) + 1)
        else:
            estimated_count = 0

        row[f"estimated_observer_count_{spacing}m"] = estimated_count

    rows.append(row)

# -------------------------
# Save output
# -------------------------
summary = pd.DataFrame(rows)
summary = summary.sort_values(park_id_field)

summary.to_csv(summary_output, index=False)

print("\nSaved:", summary_output)
print(summary)