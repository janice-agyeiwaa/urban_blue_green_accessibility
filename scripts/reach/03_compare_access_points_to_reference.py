from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.ops import nearest_points

# -------------------------
# Paths
# -------------------------
my_points_path = Path(r"data\interim\reach\candidate_access_points_cleaned.gpkg")

reference_gdb_path = r"data\raw\Park_Extraction_Project.gdb"
reference_layer = "allparks_access_points"  # change if needed

output_dir = Path(r"data\interim\reach")
output_dir.mkdir(parents=True, exist_ok=True)

comparison_output = output_dir / "access_point_comparison_by_park.csv"
best_parks_output = output_dir / "best_matching_parks_for_pilot.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# Read layers
# -------------------------
my_pts = gpd.read_file(my_points_path)
ref_pts = gpd.read_file(reference_gdb_path, layer=reference_layer)

print("My points before explode:", len(my_pts))
print("Reference points before explode:", len(ref_pts))

print("\nMy geometry types:")
print(my_pts.geom_type.value_counts())

print("\nReference geometry types:")
print(ref_pts.geom_type.value_counts())

# -------------------------
# Keep needed fields
# -------------------------
my_pts = my_pts[[park_id_field, park_name_field, "geometry"]].copy()
ref_pts = ref_pts[[park_id_field, park_name_field, "geometry"]].copy()

# -------------------------
# Clean park names
# -------------------------
my_pts[park_name_field] = my_pts[park_name_field].astype(str).str.strip()
ref_pts[park_name_field] = ref_pts[park_name_field].astype(str).str.strip()

# -------------------------
# Explode multipoints into individual points
# -------------------------
my_pts = my_pts.explode(index_parts=False).reset_index(drop=True)
ref_pts = ref_pts.explode(index_parts=False).reset_index(drop=True)

print("\nMy points after explode:", len(my_pts))
print("Reference points after explode:", len(ref_pts))

# -------------------------
# Match CRS
# -------------------------
ref_pts = ref_pts.to_crs(my_pts.crs)

# -------------------------
# Compare park by park
# -------------------------
rows = []

all_park_ids = sorted(
    set(my_pts[park_id_field]).union(set(ref_pts[park_id_field]))
)

for park_id in all_park_ids:
    my_group = my_pts[my_pts[park_id_field] == park_id]
    ref_group = ref_pts[ref_pts[park_id_field] == park_id]

    if len(ref_group) > 0:
        park_name = ref_group[park_name_field].iloc[0]
    elif len(my_group) > 0:
        park_name = my_group[park_name_field].iloc[0]
    else:
        park_name = None

    my_count = len(my_group)
    ref_count = len(ref_group)

    distances = []

    if my_count > 0 and ref_count > 0:
        ref_union = ref_group.geometry.union_all()

        for geom in my_group.geometry:
            nearest_my, nearest_ref = nearest_points(geom, ref_union)
            distances.append(nearest_my.distance(nearest_ref))

    mean_dist = round(sum(distances) / len(distances), 2) if distances else None
    median_dist = round(pd.Series(distances).median(), 2) if distances else None
    max_dist = round(max(distances), 2) if distances else None

    rows.append({
        park_id_field: park_id,
        park_name_field: park_name,
        "my_count": my_count,
        "reference_count": ref_count,
        "count_difference": my_count - ref_count,
        "abs_count_difference": abs(my_count - ref_count),
        "mean_nearest_distance_m": mean_dist,
        "median_nearest_distance_m": median_dist,
        "max_nearest_distance_m": max_dist
    })

comparison = pd.DataFrame(rows)

# -------------------------
# Select possible pilot parks
# -------------------------
best = comparison[
    (comparison["my_count"] > 0) &
    (comparison["reference_count"] > 0) &
    (comparison["abs_count_difference"] <= 2) &
    (comparison["mean_nearest_distance_m"] <= 15)
].copy()

best = best.sort_values(
    by=[
        "abs_count_difference",
        "mean_nearest_distance_m",
        "max_nearest_distance_m"
    ]
)

# -------------------------
# Save outputs
# -------------------------
comparison.to_csv(comparison_output, index=False)
best.to_csv(best_parks_output, index=False)

print("\nSaved comparison:", comparison_output)
print("Saved best pilot parks:", best_parks_output)

print("\nTop pilot candidates:")
print(best.head(15))



# import geopandas as gpd

# ref = gpd.read_file(
#     r"data\raw\Park_Extraction_Project.gdb",
#     layer="allparks_access_points"
# )

# print(ref.geom_type.value_counts())
# print("Rows before explode:", len(ref))

# ref_exploded = ref.explode(index_parts=False).reset_index(drop=True)

# print("Rows after explode:", len(ref_exploded))



