from pathlib import Path
import geopandas as gpd
import pandas as pd

# -------------------------
# Paths
# -------------------------
project_root = Path(r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility")

parks_gdb = project_root / "data" / "raw" / "Park_Extraction_Project.gdb"
land_buffer_layer = "allparks_land_buffer"

counts_path = project_root / "data" / "interim" / "reach" / "access_point_counts_raw.csv"

output_dir = project_root / "data" / "interim" / "reach"
missing_output = output_dir / "parks_without_access_points.csv"
missing_gpkg_output = output_dir / "parks_without_access_points.gpkg"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# 1. Read all parks
# -------------------------
land = gpd.read_file(parks_gdb, layer=land_buffer_layer)

all_parks = land[[park_id_field, park_name_field, "geometry"]].copy()
all_parks[park_id_field] = all_parks[park_id_field].astype(int)

print("Total parks:", len(all_parks))

# -------------------------
# 2. Read raw access point counts
# -------------------------
counts = pd.read_csv(counts_path)
counts[park_id_field] = counts[park_id_field].astype(int)

print("Parks with access points:", counts[park_id_field].nunique())

# -------------------------
# 3. Find parks missing access points
# -------------------------
missing_parks = all_parks[
    ~all_parks[park_id_field].isin(counts[park_id_field])
].copy()

print("Parks without access points:", len(missing_parks))

print("\nMissing parks:")
print(missing_parks[[park_id_field, park_name_field]].to_string(index=False))

# -------------------------
# 4. Save outputs
# -------------------------
missing_parks[[park_id_field, park_name_field]].to_csv(missing_output, index=False)

missing_parks.to_file(missing_gpkg_output, driver="GPKG")

print("\nSaved CSV:")
print(missing_output)

print("\nSaved GPKG:")
print(missing_gpkg_output)

print("\nDone.")