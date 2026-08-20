# 06_export_final_kept_access_points.py

from pathlib import Path
import geopandas as gpd

# ============================================================
# STEP 6: EXPORT FINAL KEPT ACCESS POINTS
# ============================================================

# -------------------------
# Paths
# -------------------------
project_root = Path(__file__).resolve().parents[4]

interim_dir = project_root / "data" / "interim" / "reach"
processed_dir = project_root / "data" / "processed" / "reach"
processed_dir.mkdir(parents=True, exist_ok=True)

input_points = interim_dir / "candidate_access_points_connectivity_classified.gpkg"

final_points_output = processed_dir / "reach_access_points.gpkg"
final_counts_output = processed_dir / "reach_access_point_counts.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"
decision_field = "decision"

# -------------------------
# 1. Read classified access points
# -------------------------
print("Reading connectivity-classified access points...")
points = gpd.read_file(input_points)

print("Input classified points:", len(points))
print("CRS:", points.crs)

if decision_field not in points.columns:
    raise ValueError(f"'{decision_field}' field not found. Run Step 5 first.")

# -------------------------
# 2. Keep only final accepted access points
# -------------------------
kept = points[points[decision_field].str.lower() == "keep"].copy()

print("Kept final access points:", len(kept))
print("Removed/review points excluded:", len(points) - len(kept))

# -------------------------
# 3. Optional: remove review/classification helper fields from final layer
# -------------------------
# Keep this simple for now: we keep the decision fields in the final output
# so you can trace why each point was kept.

# -------------------------
# 4. Save final kept access points
# -------------------------
kept.to_file(final_points_output, driver="GPKG")

print("\nSaved final kept access points:")
print(final_points_output)

# -------------------------
# 5. Create final access point counts per park
# -------------------------
counts = (
    kept
    .groupby([park_id_field, park_name_field])
    .size()
    .reset_index(name="access_point_count")
    .sort_values(park_id_field)
)

counts.to_csv(final_counts_output, index=False)

print("\nSaved final access point counts:")
print(final_counts_output)

# -------------------------
# 6. Summary
# -------------------------
print("\nSummary:")
print("Total classified candidate points:", len(points))
print("Total final kept access points:", len(kept))
print("Total parks with final kept access points:", counts[park_id_field].nunique())

print("\nDecision counts from classified input:")
print(points[decision_field].value_counts(dropna=False))

print("\nDone.")
