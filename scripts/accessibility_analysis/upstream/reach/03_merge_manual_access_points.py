from pathlib import Path
import geopandas as gpd

# -------------------------
# Paths
# -------------------------
project_root = Path(__file__).resolve().parents[4]

input_dir = project_root / "data" / "interim" / "reach"

raw_points_path = input_dir / "candidate_access_points_raw.gpkg"
manual_points_path = input_dir / "manual_access_points.gpkg"

merged_output = input_dir / "candidate_access_points_with_manual.gpkg"
counts_output = input_dir / "access_point_counts_with_manual.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# 1. Read generated raw points
# -------------------------
print("Reading raw candidate access points...")
raw_points = gpd.read_file(raw_points_path)

print("Raw points:", len(raw_points))
print("Raw CRS:", raw_points.crs)

# -------------------------
# 2. Read manual points
# -------------------------
print("\nReading manual access points...")
manual_points = gpd.read_file(manual_points_path)

print("Manual points:", len(manual_points))
print("Manual CRS:", manual_points.crs)

# -------------------------
# 3. Match CRS
# -------------------------
if manual_points.crs != raw_points.crs:
    print("\nReprojecting manual points to match raw points CRS...")
    manual_points = manual_points.to_crs(raw_points.crs)

# -------------------------
# 4. Keep matching fields
# -------------------------
required_fields = [park_id_field, park_name_field, "method", "geometry"]

raw_points = raw_points[required_fields].copy()
manual_points = manual_points[required_fields].copy()

# Make sure manual points are labelled correctly
manual_points["method"] = "manual_review"

# -------------------------
# 5. Merge points
# -------------------------
merged = gpd.GeoDataFrame(
    gpd.pd.concat([raw_points, manual_points], ignore_index=True),
    geometry="geometry",
    crs=raw_points.crs
)

print("\nMerged candidate access points:", len(merged))

# -------------------------
# 6. Save merged points
# -------------------------
merged.to_file(merged_output, driver="GPKG")

print("\nSaved merged access points:")
print(merged_output)

# -------------------------
# 7. Count by park
# -------------------------
counts = (
    merged
    .groupby([park_id_field, park_name_field])
    .size()
    .reset_index(name="candidate_access_point_count_with_manual")
    .sort_values(park_id_field)
)

counts.to_csv(counts_output, index=False)

print("\nSaved counts:")
print(counts_output)

print("\nSummary:")
print("Total merged candidate access points:", len(merged))
print("Total parks with candidate access points:", counts[park_id_field].nunique())

print("\nDone.")
