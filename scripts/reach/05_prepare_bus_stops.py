from pathlib import Path
import pandas as pd
import geopandas as gpd

# -------------------------
# Paths
# -------------------------
stops_path = Path(r"data\raw\translink_gtfs\stops.txt")

output_dir = Path(r"data\interim\reach")
output_dir.mkdir(parents=True, exist_ok=True)

bus_stops_output = output_dir / "translink_bus_stops.gpkg"

# -------------------------
# Read GTFS stops
# -------------------------
stops = pd.read_csv(stops_path)

print("GTFS stop records:", len(stops))
print("Columns:", list(stops.columns))

# -------------------------
# Keep useful columns
# -------------------------
needed_cols = ["stop_id", "stop_name", "stop_lat", "stop_lon"]
stops = stops[needed_cols].copy()

# Remove rows without coordinates
stops = stops.dropna(subset=["stop_lat", "stop_lon"])

# -------------------------
# Convert to spatial points
# -------------------------
bus_stops = gpd.GeoDataFrame(
    stops,
    geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
    crs="EPSG:4326"
)

# Project to NAD 1983 UTM Zone 10N
bus_stops = bus_stops.to_crs(epsg=26910)

print("Bus stop point records:", len(bus_stops))
print("CRS:", bus_stops.crs)

# -------------------------
# Save output
# -------------------------
bus_stops.to_file(bus_stops_output, driver="GPKG")

print("Saved:", bus_stops_output)