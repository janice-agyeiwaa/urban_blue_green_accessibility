from pathlib import Path
import geopandas as gpd

# -------------------------
# Paths
# -------------------------
project_root = Path(__file__).resolve().parents[4]

parks_gdb = project_root / "data" / "raw" / "Park_Extraction_Project.gdb"
composite_gdb = project_root / "data" / "raw" / "CompositeNetwork3.gdb"

land_buffer_layer = "allparks_land_buffer"
network_layer = "OSM_NA_Network_NAD_Point3"

output_dir = project_root / "data" / "interim" / "reach"
output_dir.mkdir(parents=True, exist_ok=True)

access_points_output = output_dir / "candidate_access_points_raw.gpkg"
counts_output = output_dir / "access_point_counts_raw.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# 1. Read land buffers
# -------------------------
print("Reading land buffer...")
land = gpd.read_file(parks_gdb, layer=land_buffer_layer)

land = land[[park_id_field, park_name_field, "geometry"]].copy()
land["geometry"] = land.geometry.make_valid()

print("Land buffer records:", len(land))
print("Land buffer CRS:", land.crs)

# -------------------------
# 2. Read composite network
# -------------------------
print("\nReading composite network...")
network = gpd.read_file(composite_gdb, layer=network_layer)

network = network[["geometry"]].copy()
network["geometry"] = network.geometry.make_valid()

print("Network records:", len(network))
print("Network CRS:", network.crs)

# -------------------------
# 3. Match CRS
# -------------------------
if network.crs != land.crs:
    print("\nReprojecting network to match land buffer CRS...")
    network = network.to_crs(land.crs)

# -------------------------
# 4. Create land buffer boundary
# -------------------------
print("\nCreating land buffer boundaries...")
land_boundary = land.copy()
land_boundary["geometry"] = land_boundary.geometry.boundary

# -------------------------
# 5. Intersect network with land buffer boundary
# -------------------------
print("\nCreating candidate access points...")

access_points = gpd.overlay(
    network,
    land_boundary,
    how="intersection",
    keep_geom_type=False
)

# Keep only point geometries
access_points = access_points[
    access_points.geometry.geom_type.isin(["Point", "MultiPoint"])
].copy()

# Explode MultiPoints into individual Points
access_points = access_points.explode(index_parts=False).reset_index(drop=True)

# Add method field
access_points["method"] = "composite_network_boundary_intersection"

print("Raw access points created:", len(access_points))

# -------------------------
# 6. Save raw access points
# -------------------------
access_points.to_file(access_points_output, driver="GPKG")
print("\nSaved raw access points:")
print(access_points_output)

# -------------------------
# 7. Count access points per park
# -------------------------
counts = (
    access_points
    .groupby([park_id_field, park_name_field])
    .size()
    .reset_index(name="raw_access_point_count")
    .sort_values(park_id_field)
)

counts.to_csv(counts_output, index=False)

print("\nSaved access point counts:")
print(counts_output)

print("\nSummary:")
print("Total parks with access points:", counts[park_id_field].nunique())
print("Total raw access points:", len(access_points))

print("\nDone.")




