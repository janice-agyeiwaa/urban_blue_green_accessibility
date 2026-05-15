from pathlib import Path
import pandas as pd
import geopandas as gpd

# -------------------------
# Paths
# -------------------------
best_parks_path = Path(r"data\interim\reach\best_matching_parks_for_pilot.csv")
access_points_path = Path(r"data\interim\reach\candidate_access_points_cleaned.gpkg")

output_dir = Path(r"data\processed\reach")
output_dir.mkdir(parents=True, exist_ok=True)

pilot_parks_output = output_dir / "pilot_10_parks.csv"
pilot_access_points_output = output_dir / "pilot_10_access_points.gpkg"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"

# -------------------------
# Read data
# -------------------------
best = pd.read_csv(best_parks_path)
access_points = gpd.read_file(access_points_path)

# -------------------------
# Select top 10
# -------------------------
pilot_10 = best.head(10).copy()
pilot_park_nums = pilot_10[park_id_field].tolist()

pilot_access_points = access_points[
    access_points[park_id_field].isin(pilot_park_nums)
].copy()

# -------------------------
# Save outputs
# -------------------------
pilot_10.to_csv(pilot_parks_output, index=False)
pilot_access_points.to_file(pilot_access_points_output, driver="GPKG")

print("Selected pilot parks:", pilot_park_nums)
print("Saved pilot parks:", pilot_parks_output)
print("Saved pilot access points:", pilot_access_points_output)
print("Pilot access point records:", len(pilot_access_points))