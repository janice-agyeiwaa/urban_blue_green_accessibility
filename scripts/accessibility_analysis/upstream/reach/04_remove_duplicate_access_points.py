from pathlib import Path
import geopandas as gpd

# ============================================================
# STEP 4: DEDUPE MERGED CANDIDATE ACCESS POINTS
# Output: candidate_access_points_deduped.gpkg only
# ============================================================

# -------------------------
# Paths
# -------------------------
project_root = Path(__file__).resolve().parents[4]

input_dir = project_root / "data" / "interim" / "reach"
input_points = input_dir / "candidate_access_points_with_manual.gpkg"

interim_output_dir = project_root / "data" / "interim" / "reach"
interim_output_dir.mkdir(parents=True, exist_ok=True)

deduped_output = interim_output_dir / "candidate_access_points_deduped.gpkg"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# 2 decimal places in EPSG:26910 = about 1 cm
xy_round = 2

# -------------------------
# 1. Read merged candidate access points
# -------------------------
print("Reading merged candidate access points...")
points = gpd.read_file(input_points)

print("Input points:", len(points))
print("CRS:", points.crs)

# -------------------------
# 2. Create rounded coordinate fields for duplicate check
# -------------------------
points["x_round"] = points.geometry.x.round(xy_round)
points["y_round"] = points.geometry.y.round(xy_round)

# -------------------------
# 3. Remove exact/stacked duplicates per park
# -------------------------
duplicate_mask = points.duplicated(
    subset=[park_id_field, "x_round", "y_round"],
    keep="first"
)

deduped = points[~duplicate_mask].copy()

# Remove helper fields from saved output
deduped = deduped.drop(columns=["x_round", "y_round"])

print("Deduped candidate points:", len(deduped))
print("Removed duplicate points:", duplicate_mask.sum())

# -------------------------
# 4. Save deduped candidate access points
# -------------------------
deduped.to_file(deduped_output, driver="GPKG")

print("\nSaved deduped candidate access points:")
print(deduped_output)

# -------------------------
# 5. Summary checks
# -------------------------
print("\nSummary:")
print("Total input candidate points:", len(points))
print("Total deduped candidate points:", len(deduped))
print("Total removed duplicates:", duplicate_mask.sum())
print("Total parks with deduped candidate access points:", deduped[park_id_field].nunique())

if "method" in deduped.columns:
    print("\nMethod counts after deduping:")
    print(deduped["method"].value_counts(dropna=False))

print("\nDone.")
