from pathlib import Path
import geopandas as gpd
import pandas as pd

# -------------------------
# Paths
# -------------------------
project_folder = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\weekly_reports\urban_blue_green_accessibility"
)

clipped_paths_path = (
    project_folder
    / "data"
    / "interim"
    / "viewshed"
    / "pilot_10_clipped_osm_paths.gpkg"
)

output_dir = project_folder / "data" / "interim" / "viewshed" / "qa"
output_dir.mkdir(parents=True, exist_ok=True)

path_labels_output = output_dir / "pilot_10_osm_path_label_points.gpkg"
path_attributes_csv = output_dir / "pilot_10_osm_path_attributes.csv"

# -------------------------
# Read clipped OSM paths
# -------------------------
paths = gpd.read_file(clipped_paths_path)

print("Clipped path records:", len(paths))
print("CRS:", paths.crs)
print("\nAvailable columns:")
print(paths.columns.tolist())

# -------------------------
# Keep useful OSM QA fields if available
# -------------------------
possible_fields = [
    "park_num",
    "PARK_NAME",
    "osmid",
    "name",
    "highway",
    "footway",
    "bridge",
    "tunnel",
    "surface",
    "access",
    "service",
    "sidewalk",
    "geometry",
]

keep_fields = [field for field in possible_fields if field in paths.columns]

qa_paths = paths[keep_fields].copy()

# -------------------------
# Clean text fields for easier viewing
# -------------------------
for col in qa_paths.columns:
    if col != "geometry":
        qa_paths[col] = qa_paths[col].astype(str)

# -------------------------
# Create label points at path midpoints
# -------------------------
label_rows = []

for idx, row in qa_paths.iterrows():
    geom = row.geometry

    if geom is None or geom.is_empty:
        continue

    # For LineString/MultiLineString, interpolate midpoint along geometry length
    try:
        midpoint = geom.interpolate(geom.length / 2)
    except Exception:
        midpoint = geom.representative_point()

    new_row = row.drop(labels="geometry").to_dict()
    new_row["path_record_id"] = idx

        # Create a simple label text
    def clean_value(value):
        if pd.isna(value):
            return ""
        value = str(value).strip()
        if value.lower() in ["", "nan", "none", "<na>"]:
            return ""
        return value

    name = clean_value(new_row.get("name", ""))
    highway = clean_value(new_row.get("highway", ""))
    bridge = clean_value(new_row.get("bridge", ""))
    access = clean_value(new_row.get("access", ""))
    service = clean_value(new_row.get("service", ""))

    label_parts = []

    if name:
        label_parts.append(f"name={name}")

    if highway:
        label_parts.append(f"highway={highway}")

    if bridge:
        label_parts.append(f"bridge={bridge}")

    if access:
        label_parts.append(f"access={access}")

    if service:
        label_parts.append(f"service={service}")

    if not label_parts:
        label_parts.append("unnamed OSM path")

    new_row["label_text"] = " | ".join(label_parts)
    
    new_row["geometry"] = midpoint

    label_rows.append(new_row)

labels = gpd.GeoDataFrame(label_rows, geometry="geometry", crs=paths.crs)

# -------------------------
# Save outputs
# -------------------------
labels.to_file(path_labels_output, driver="GPKG")

# Save attributes table without geometry
attrs = pd.DataFrame(labels.drop(columns="geometry"))
attrs.to_csv(path_attributes_csv, index=False)

print("\nSaved path label points:")
print(path_labels_output)

print("\nSaved path attributes CSV:")
print(path_attributes_csv)

print("\nPreview:")
print(labels[["park_num", "PARK_NAME", "label_text"]].head(20))