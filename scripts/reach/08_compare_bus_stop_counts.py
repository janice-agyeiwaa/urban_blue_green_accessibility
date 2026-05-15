from pathlib import Path
import geopandas as gpd
import pandas as pd

# -------------------------
# Paths
# -------------------------
my_counts_path = Path(
    r"data\processed\reach\pilot_10_bus_stop_counts_from_walktime_polygons.csv"
)

reference_gdb_path = r"data\raw\Park_Extraction_Project.gdb"
reference_layer = "allparks_land_buffer_reachvariables"

output_dir = Path(r"data\processed\reach")
output_dir.mkdir(parents=True, exist_ok=True)

comparison_output = output_dir / "pilot_10_bus_stop_count_comparison.csv"

# -------------------------
# Fields
# -------------------------
park_id_field = "park_num"
park_name_field = "PARK_NAME"

# -------------------------
# Read data
# -------------------------
my_counts = pd.read_csv(my_counts_path)

reference = gpd.read_file(reference_gdb_path, layer=reference_layer)
reference = pd.DataFrame(reference.drop(columns="geometry", errors="ignore"))

# -------------------------
# Keep needed fields
# -------------------------
my_counts = my_counts[
    [
        park_id_field,
        park_name_field,
        "bus_stops_05min",
        "bus_stops_10min",
        "bus_stops_20min",
        "bus_stops_30min",
    ]
].copy()

reference = reference[
    [
        park_id_field,
        "bus_stops_05min",
        "bus_stops_10min",
        "bus_stops_20min",
        "bus_stops_30min",
    ]
].copy()

# -------------------------
# Clean names
# -------------------------
my_counts[park_name_field] = my_counts[park_name_field].astype(str).str.strip()

# -------------------------
# Rename Avery/reference fields
# -------------------------
reference = reference.rename(
    columns={
        "bus_stops_05min": "avery_05min",
        "bus_stops_10min": "avery_10min",
        "bus_stops_20min": "avery_20min",
        "bus_stops_30min": "avery_30min",
    }
)

# -------------------------
# Join by park_num
# -------------------------
comparison = my_counts.merge(
    reference,
    on=park_id_field,
    how="left"
)

# -------------------------
# Calculate differences
# diff = my Python result - Avery/reference result
# -------------------------
for t in ["05", "10", "20", "30"]:
    comparison[f"diff_{t}min"] = (
        comparison[f"bus_stops_{t}min"] - comparison[f"avery_{t}min"]
    )

# -------------------------
# Final column order
# -------------------------
comparison = comparison[
    [
        park_id_field,
        park_name_field,
        "bus_stops_05min", "avery_05min", "diff_05min",
        "bus_stops_10min", "avery_10min", "diff_10min",
        "bus_stops_20min", "avery_20min", "diff_20min",
        "bus_stops_30min", "avery_30min", "diff_30min",
    ]
]

comparison = comparison.sort_values(park_id_field)

# -------------------------
# Save
# -------------------------
comparison.to_csv(comparison_output, index=False)

print("Saved:", comparison_output)
print("\nFinal columns:")
print(list(comparison.columns))

print("\nPreview:")
print(comparison.head(10))