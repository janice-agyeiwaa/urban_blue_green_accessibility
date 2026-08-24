# ============================================================
# 06_match_mapbox_cells_5m_buffer.py
#
# Purpose:
# Apply a 5 m buffer to ALL 114 Mapbox extraction areas,
# then redo the Mapbox grid-cell centroid matching.
#
# IMPORTANT:
# - The existing extraction areas already represent the
#   combined land + water extraction areas.
# - This script adds ONLY the new 5 m buffer requested by Asim.
# - Original outputs are NOT overwritten.
# ============================================================

from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd


# ------------------------------------------------------------
# Project paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "mapbox"

INTERIM_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------------
# Inputs
# ------------------------------------------------------------

GPKG_PATH = INTERIM_DIR / "mapbox_extraction.gpkg"

mapbox_files = list(
    RAW_DIR.glob(
        "MapboxMovement_sample_weekday-weekend-1_CA-qk0212122_2023-01-01_2023-12-31*.csv"
    )
)

if not mapbox_files:
    raise FileNotFoundError(
        "Mapbox CSV not found."
    )

MAPBOX_CSV = mapbox_files[0]


# ------------------------------------------------------------
# Read original 114 extraction areas
# ------------------------------------------------------------

layers = gpd.list_layers(GPKG_PATH)

print("\nGeoPackage layers:")
print(layers)

layer_name = "mapbox_extraction"

parks = gpd.read_file(
    GPKG_PATH,
    layer=layer_name
)

print("\nOriginal extraction layer:")
print("Records:", len(parks))
print("Unique park_num:", parks["park_num"].nunique())
print("CRS:", parks.crs)

if len(parks) != 114:
    raise ValueError(
        f"Expected 114 parks, found {len(parks)}."
    )

parks["park_num"] = parks["park_num"].astype(str)


# ------------------------------------------------------------
# Confirm projected CRS
# ------------------------------------------------------------

if parks.crs is None:
    raise ValueError(
        "Park layer has no CRS."
    )

print("\nOriginal CRS:")
print(parks.crs)

# EPSG:26910 uses metres.
# If needed, force projection before buffering.

if parks.crs.to_epsg() != 26910:
    print(
        "\nTransforming extraction areas to EPSG:26910..."
    )

    parks = parks.to_crs(
        epsg=26910
    )


# ------------------------------------------------------------
# Apply 5 m buffer to ALL 114 sites
# ------------------------------------------------------------

print("\nApplying 5 m buffer to all 114 sites...")

parks_5m = parks.copy()

parks_5m["geometry"] = (
    parks_5m.geometry.buffer(5)
)

print(
    "Buffered records:",
    len(parks_5m)
)

print(
    "Unique buffered park_num:",
    parks_5m["park_num"].nunique()
)


# ------------------------------------------------------------
# Save buffered extraction areas for QA
# ------------------------------------------------------------

BUFFER_OUTPUT = (
    INTERIM_DIR /
    "mapbox_extraction_areas_114_buffer5m.gpkg"
)

if BUFFER_OUTPUT.exists():
    BUFFER_OUTPUT.unlink()

parks_5m.to_file(
    BUFFER_OUTPUT,
    layer="mapbox_extraction_buffer5m",
    driver="GPKG"
)

print("\nBuffered extraction layer saved:")
print(BUFFER_OUTPUT)


# ------------------------------------------------------------
# Transform buffered parks to WGS84
# ------------------------------------------------------------

parks_5m_wgs84 = parks_5m.to_crs(
    epsg=4326
)

xmin, ymin, xmax, ymax = (
    parks_5m_wgs84.total_bounds
)

print("\nBuffered study-area bounding box:")
print("xmin:", xmin)
print("ymin:", ymin)
print("xmax:", xmax)
print("ymax:", ymax)


# ------------------------------------------------------------
# Extract unique Mapbox cells in study bbox
# ------------------------------------------------------------

print(
    "\nQuerying unique Mapbox cells in study bounding box..."
)

con = duckdb.connect()

query = f"""
SELECT DISTINCT
    CAST(geography AS VARCHAR) AS geography,
    xlon,
    xlat

FROM read_csv_auto(
    '{MAPBOX_CSV.as_posix()}',
    header = true,
    types = {{'geography': 'VARCHAR'}}
)

WHERE
    xlon BETWEEN {xmin} AND {xmax}
    AND
    xlat BETWEEN {ymin} AND {ymax}
"""

mapbox_cells = con.execute(
    query
).fetchdf()

con.close()

print(
    "\nUnique Mapbox cells in bounding box:",
    len(mapbox_cells)
)


# ------------------------------------------------------------
# Convert Mapbox cell centroids to points
# ------------------------------------------------------------

mapbox_points = gpd.GeoDataFrame(
    mapbox_cells,
    geometry=gpd.points_from_xy(
        mapbox_cells["xlon"],
        mapbox_cells["xlat"]
    ),
    crs="EPSG:4326"
)

print(
    "Mapbox centroid points:",
    len(mapbox_points)
)


# ------------------------------------------------------------
# Spatial match
# ------------------------------------------------------------

print(
    "\nMatching centroids to 5 m buffered extraction areas..."
)

park_geometry = parks_5m_wgs84[
    [
        "park_num",
        "geometry"
    ]
].copy()

matched = gpd.sjoin(
    mapbox_points,
    park_geometry,
    how="inner",
    predicate="within"
)

print("\nSpatial matching complete.")


# ------------------------------------------------------------
# Lookup table
# ------------------------------------------------------------

lookup = (
    matched[
        [
            "park_num",
            "geography",
            "xlon",
            "xlat"
        ]
    ]
    .drop_duplicates()
    .copy()
)


# ------------------------------------------------------------
# Cells per park
# ------------------------------------------------------------

cells_per_park = (
    lookup
    .groupby("park_num")
    .size()
    .reset_index(
        name="mapbox_cell_count"
    )
)

cells_per_park["park_num_numeric"] = (
    pd.to_numeric(
        cells_per_park["park_num"],
        errors="coerce"
    )
)

cells_per_park = (
    cells_per_park
    .sort_values(
        "park_num_numeric"
    )
    .drop(
        columns="park_num_numeric"
    )
)


# ------------------------------------------------------------
# Parks with no centroid
# ------------------------------------------------------------

all_parks = (
    parks_5m_wgs84[
        ["park_num"]
    ]
    .drop_duplicates()
)

parks_without_cells = all_parks[
    ~all_parks["park_num"].isin(
        cells_per_park["park_num"]
    )
].copy()


# ------------------------------------------------------------
# Multiple-park assignments
# ------------------------------------------------------------

multiple = (
    lookup[
        [
            "geography",
            "park_num"
        ]
    ]
    .drop_duplicates()
    .groupby("geography")
    .size()
    .reset_index(
        name="park_count"
    )
)

multiple = multiple[
    multiple["park_count"] > 1
]


# ------------------------------------------------------------
# QA summary
# ------------------------------------------------------------

print("\n" + "=" * 55)
print("5 M BUFFER MAPBOX MATCHING RESULTS")
print("=" * 55)

print(
    "\nTotal park-cell matches:",
    len(lookup)
)

print(
    "Unique Mapbox cells matched:",
    lookup["geography"].nunique()
)

print(
    "Parks receiving >=1 Mapbox cell:",
    lookup["park_num"].nunique()
)

print(
    "Parks with zero Mapbox cells:",
    len(parks_without_cells)
)

if not parks_without_cells.empty:

    print("\nRemaining zero-cell park IDs:")

    print(
        parks_without_cells[
            ["park_num"]
        ].to_string(
            index=False
        )
    )

print(
    "\nMinimum cells per represented park:",
    cells_per_park[
        "mapbox_cell_count"
    ].min()
)

print(
    "Maximum cells per represented park:",
    cells_per_park[
        "mapbox_cell_count"
    ].max()
)

print(
    "Median cells per represented park:",
    cells_per_park[
        "mapbox_cell_count"
    ].median()
)

print(
    "\nMapbox cells assigned to multiple parks:",
    len(multiple)
)


# ------------------------------------------------------------
# Save new 5 m outputs
# ------------------------------------------------------------

LOOKUP_OUTPUT = (
    INTERIM_DIR /
    "mapbox_cell_park_lookup_2023_buffer5m.csv"
)

COUNTS_OUTPUT = (
    INTERIM_DIR /
    "mapbox_cell_counts_by_park_2023_buffer5m.csv"
)

ZERO_OUTPUT = (
    INTERIM_DIR /
    "mapbox_parks_without_cells_2023_buffer5m.csv"
)

POINTS_OUTPUT = (
    INTERIM_DIR /
    "mapbox_matched_cell_centroids_2023_buffer5m.gpkg"
)

lookup.to_csv(
    LOOKUP_OUTPUT,
    index=False
)

cells_per_park.to_csv(
    COUNTS_OUTPUT,
    index=False
)

parks_without_cells.to_csv(
    ZERO_OUTPUT,
    index=False
)

if POINTS_OUTPUT.exists():
    POINTS_OUTPUT.unlink()

matched[
    [
        "park_num",
        "geography",
        "xlon",
        "xlat",
        "geometry"
    ]
].to_file(
    POINTS_OUTPUT,
    layer="matched_centroids_buffer5m",
    driver="GPKG"
)


# ------------------------------------------------------------
# Final paths
# ------------------------------------------------------------

print("\n" + "=" * 55)
print("OUTPUT FILES")
print("=" * 55)

print("\n5 m buffered extraction polygons:")
print(BUFFER_OUTPUT)

print("\n5 m cell-to-park lookup:")
print(LOOKUP_OUTPUT)

print("\n5 m cell counts:")
print(COUNTS_OUTPUT)

print("\nRemaining zero-cell parks:")
print(ZERO_OUTPUT)

print("\nMatched Mapbox centroids:")
print(POINTS_OUTPUT)

print("\nDone.")
