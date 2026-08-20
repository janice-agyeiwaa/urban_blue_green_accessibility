# ============================================================
# 02_match_mapbox_cells_to_sites.py
#
# Purpose:
# 1. Read the 114-site extraction polygons
# 2. Query unique Mapbox grid-cell centroids near Metro Vancouver
# 3. Spatially match centroids to park extraction areas
# 4. Save geography -> park_num lookup
#
# IMPORTANT:
# - No new 100 m buffer is created.
# - The extraction polygons already contain the land + water
#   areas based on the existing 100 m source layers.
# ============================================================

from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd


# ------------------------------------------------------------
# Project paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

RAW_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "mapbox"

INTERIM_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------------
# Locate Mapbox CSV
# ------------------------------------------------------------

mapbox_files = list(
    RAW_DIR.glob(
        "MapboxMovement_sample_weekday-weekend-1_CA-qk0212122_2023-01-01_2023-12-31*.csv"
    )
)

if not mapbox_files:
    raise FileNotFoundError(
        "Mapbox CSV not found in data/raw."
    )

MAPBOX_CSV = mapbox_files[0]

print("\nMapbox CSV:")
print(MAPBOX_CSV)


# ------------------------------------------------------------
# Read extraction polygons
#
# First try the GeoPackage.
# ------------------------------------------------------------

GPKG_PATH = INTERIM_DIR / "mapbox_extraction.gpkg"

if not GPKG_PATH.exists():
    raise FileNotFoundError(
        f"GeoPackage not found: {GPKG_PATH}"
    )

print("\nInspecting GeoPackage layers...")

layers = gpd.list_layers(GPKG_PATH)

print(layers)

# ------------------------------------------------------------
# Automatically use the first spatial layer
# ------------------------------------------------------------

layer_name = layers.iloc[0]["name"]

print("\nUsing layer:")
print(layer_name)

parks = gpd.read_file(
    GPKG_PATH,
    layer=layer_name
)

print("\nExtraction layer loaded.")
print("Records:", len(parks))
print("Columns:", parks.columns.tolist())
print("CRS:", parks.crs)

print("\nGeometry types:")
print(parks.geometry.geom_type.value_counts())


# ------------------------------------------------------------
# Check park_num
# ------------------------------------------------------------

if "park_num" not in parks.columns:
    raise ValueError(
        "The extraction layer does not contain park_num."
    )

parks["park_num"] = parks["park_num"].astype(str)

print(
    "\nUnique park_num:",
    parks["park_num"].nunique()
)

if len(parks) != 114:
    print(
        f"WARNING: expected 114 records, found {len(parks)}"
    )

if parks["park_num"].nunique() != 114:
    print(
        "WARNING: expected 114 unique park_num values."
    )


# ------------------------------------------------------------
# Transform polygons to WGS84
#
# Mapbox xlon/xlat are longitude/latitude.
# ------------------------------------------------------------

parks_wgs84 = parks.to_crs(
    epsg=4326
)

xmin, ymin, xmax, ymax = parks_wgs84.total_bounds

print("\nStudy-area bounding box:")
print("xmin:", xmin)
print("ymin:", ymin)
print("xmax:", xmax)
print("ymax:", ymax)


# ------------------------------------------------------------
# Query unique Mapbox cells within broad bounding box
#
# We do not load all 59 million activity rows into pandas.
# DuckDB scans the CSV directly.
# ------------------------------------------------------------

print(
    "\nExtracting unique Mapbox cells within broad bounding box..."
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
    "\nUnique Mapbox cells inside broad bounding box:",
    len(mapbox_cells)
)

print(
    "Unique geography IDs:",
    mapbox_cells["geography"].nunique()
)


# ------------------------------------------------------------
# Convert Mapbox centroid coordinates to points
#
# Each point represents the centroid of one original
# 100 m x 100 m Mapbox grid cell.
# ------------------------------------------------------------

print(
    "\nCreating Mapbox centroid points..."
)

mapbox_points = gpd.GeoDataFrame(
    mapbox_cells.copy(),
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
# Spatial join
#
# Keep a Mapbox cell when its centroid falls within one
# of the 114 extraction polygons.
# ------------------------------------------------------------

print(
    "\nMatching Mapbox centroids to extraction areas..."
)

park_geometry = parks_wgs84[
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

print(
    "\nSpatial matching complete."
)


# ------------------------------------------------------------
# Create lookup table
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
# QA 1
# ------------------------------------------------------------

print("\n" + "=" * 50)
print("QA 1: OVERALL MATCHING")
print("=" * 50)

print(
    "Total park-cell matches:",
    len(lookup)
)

print(
    "Unique Mapbox cells matched:",
    lookup["geography"].nunique()
)

print(
    "Parks receiving at least one Mapbox cell:",
    lookup["park_num"].nunique()
)


# ------------------------------------------------------------
# QA 2: cells per park
# ------------------------------------------------------------

cells_per_park = (
    lookup
    .groupby(
        "park_num"
    )
    .size()
    .reset_index(
        name="mapbox_cell_count"
    )
)

cells_per_park["park_num_numeric"] = pd.to_numeric(
    cells_per_park["park_num"],
    errors="coerce"
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

print("\n" + "=" * 50)
print("QA 2: MAPBOX CELLS PER PARK")
print("=" * 50)

print(
    cells_per_park.to_string(
        index=False
    )
)

print(
    "\nMinimum cells in a park:",
    cells_per_park["mapbox_cell_count"].min()
)

print(
    "Maximum cells in a park:",
    cells_per_park["mapbox_cell_count"].max()
)

print(
    "Median cells per park:",
    cells_per_park["mapbox_cell_count"].median()
)


# ------------------------------------------------------------
# QA 3: parks with zero cells
# ------------------------------------------------------------

all_parks = (
    parks_wgs84[
        ["park_num"]
    ]
    .drop_duplicates()
)

parks_without_cells = all_parks[
    ~all_parks["park_num"].isin(
        cells_per_park["park_num"]
    )
].copy()

print("\n" + "=" * 50)
print("QA 3: PARKS WITH ZERO MAPBOX CELLS")
print("=" * 50)

if parks_without_cells.empty:
    print("None")
else:
    print(
        parks_without_cells.to_string(
            index=False
        )
    )


# ------------------------------------------------------------
# QA 4: cells assigned to multiple parks
# ------------------------------------------------------------

cell_park_unique = lookup[
    [
        "geography",
        "park_num"
    ]
].drop_duplicates()

cells_multiple_parks = (
    cell_park_unique
    .groupby(
        "geography"
    )
    .size()
    .reset_index(
        name="park_count"
    )
)

cells_multiple_parks = (
    cells_multiple_parks[
        cells_multiple_parks["park_count"] > 1
    ]
    .sort_values(
        "park_count",
        ascending=False
    )
)

print("\n" + "=" * 50)
print("QA 4: CELLS ASSIGNED TO MULTIPLE PARKS")
print("=" * 50)

print(
    "Number of grid cells assigned to more than one park:",
    len(cells_multiple_parks)
)

if not cells_multiple_parks.empty:
    print(
        "\nFirst 20:"
    )
    print(
        cells_multiple_parks.head(20).to_string(
            index=False
        )
    )


# ------------------------------------------------------------
# Save outputs
# ------------------------------------------------------------

LOOKUP_OUTPUT = (
    INTERIM_DIR /
    "mapbox_cell_park_lookup_2023.csv"
)

COUNTS_OUTPUT = (
    INTERIM_DIR /
    "mapbox_cell_counts_by_park_2023.csv"
)

ZERO_OUTPUT = (
    INTERIM_DIR /
    "mapbox_parks_without_cells_2023.csv"
)

OVERLAP_OUTPUT = (
    INTERIM_DIR /
    "mapbox_cells_multiple_parks_2023.csv"
)

MATCHED_POINTS_OUTPUT = (
    INTERIM_DIR /
    "mapbox_matched_cell_centroids_2023.gpkg"
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

cells_multiple_parks.to_csv(
    OVERLAP_OUTPUT,
    index=False
)


# ------------------------------------------------------------
# Save spatial points for ArcGIS QA
# ------------------------------------------------------------

if MATCHED_POINTS_OUTPUT.exists():
    MATCHED_POINTS_OUTPUT.unlink()

matched[
    [
        "park_num",
        "geography",
        "xlon",
        "xlat",
        "geometry"
    ]
].to_file(
    MATCHED_POINTS_OUTPUT,
    layer="matched_mapbox_centroids",
    driver="GPKG"
)



# ============================================================
# QA zero-cell parks
# Find nearest Mapbox centroid to each park
# ============================================================

zero_ids = [
    "33", "35", "43", "75", "80",
    "83", "87", "88", "89", "119", "130"
]

zero_parks = parks_wgs84[
    parks_wgs84["park_num"].isin(zero_ids)
].copy()

# Work in the original projected CRS (UTM Zone 10N)
# so distances are measured in metres.
zero_parks_utm = zero_parks.to_crs(
    parks.crs
)

mapbox_points_utm = mapbox_points.to_crs(
    parks.crs
)

# ------------------------------------------------------------
# Find nearest centroid for each zero-cell park
# ------------------------------------------------------------

nearest = gpd.sjoin_nearest(
    zero_parks_utm[
        ["park_num", "geometry"]
    ],
    mapbox_points_utm[
        ["geography", "xlon", "xlat", "geometry"]
    ],
    how="left",
    distance_col="distance_to_nearest_centroid_m"
)

nearest = nearest[
    [
        "park_num",
        "geography",
        "xlon",
        "xlat",
        "distance_to_nearest_centroid_m",
        "geometry"
    ]
]

print("\nNearest Mapbox centroid for zero-cell parks:")
print(
    nearest[
        [
            "park_num",
            "geography",
            "distance_to_nearest_centroid_m"
        ]
    ].to_string(index=False)
)

# ------------------------------------------------------------
# Save for ArcGIS visual inspection
# ------------------------------------------------------------

zero_qa_output = (
    INTERIM_DIR /
    "mapbox_zero_cell_parks_nearest_centroid_qa.gpkg"
)

if zero_qa_output.exists():
    zero_qa_output.unlink()

nearest.to_file(
    zero_qa_output,
    layer="zero_cell_parks",
    driver="GPKG"
)

print("\nZero-cell QA layer saved to:")
print(zero_qa_output)

# ------------------------------------------------------------
# Final summary
# ------------------------------------------------------------

print("\n" + "=" * 50)
print("MAPBOX CELL MATCHING COMPLETE")
print("=" * 50)

print("\nLookup table:")
print(LOOKUP_OUTPUT)

print("\nCell counts by park:")
print(COUNTS_OUTPUT)

print("\nParks without cells:")
print(ZERO_OUTPUT)

print("\nCells assigned to multiple parks:")
print(OVERLAP_OUTPUT)

print("\nMatched centroid layer:")
print(MATCHED_POINTS_OUTPUT)

print("\nDone.")