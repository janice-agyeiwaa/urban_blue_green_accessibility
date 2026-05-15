from pathlib import Path
import geopandas as gpd
import pandas as pd

# -------------------------
# Paths
# -------------------------
input_points = Path(r"data\interim\reach\candidate_access_points_raw.gpkg")

output_dir = Path(r"data\interim\reach")
output_dir.mkdir(parents=True, exist_ok=True)

cleaned_output = output_dir / "candidate_access_points_cleaned.gpkg"
removed_duplicates_output = output_dir / "candidate_access_points_removed_exact_duplicates.csv"
counts_output = output_dir / "candidate_access_point_counts_cleaned.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# Read raw candidate access points
# -------------------------
points = gpd.read_file(input_points)

print("Raw candidate points:", len(points))
print("CRS:", points.crs)

# Clean park names
points[park_name_field] = points[park_name_field].astype(str).str.strip()

# -------------------------
# Stage 1: remove exact stacked duplicates
# -------------------------
# We round coordinates to 2 decimals = centimetre precision in EPSG:26910.
# This removes points that are effectively at the same exact location.
points["x_round"] = points.geometry.x.round(2)
points["y_round"] = points.geometry.y.round(2)

# Mark duplicates within the same park and same rounded coordinate
duplicate_mask = points.duplicated(
    subset=[park_id_field, "x_round", "y_round"],
    keep="first"
)

removed_duplicates = points[duplicate_mask].copy()
cleaned = points[~duplicate_mask].copy()

print("Exact stacked duplicates removed:", len(removed_duplicates))
print("Cleaned candidate points:", len(cleaned))

# -------------------------
# Add cleaning notes
# -------------------------
cleaned["cleaning_stage"] = "exact_deduped"
cleaned["cleaning_note"] = "Exact stacked duplicates removed by park_num and rounded x/y coordinate."

# Drop helper coordinate fields from spatial output if you want cleaner layer
cleaned_for_output = cleaned.drop(columns=["x_round", "y_round"])

# -------------------------
# Count cleaned access points per park
# -------------------------
counts = (
    cleaned
    .groupby([park_id_field, park_name_field])
    .size()
    .reset_index(name="cleaned_candidate_access_point_count")
)

# -------------------------
# Save outputs
# -------------------------
cleaned_for_output.to_file(cleaned_output, driver="GPKG")

# Save removed duplicates as CSV for documentation
if len(removed_duplicates) > 0:
    removed_duplicates_table = removed_duplicates.drop(columns="geometry")
    removed_duplicates_table.to_csv(removed_duplicates_output, index=False)

counts.to_csv(counts_output, index=False)

print("Saved cleaned points:", cleaned_output)
print("Saved removed duplicate log:", removed_duplicates_output)
print("Saved cleaned count table:", counts_output)
print("Done.")