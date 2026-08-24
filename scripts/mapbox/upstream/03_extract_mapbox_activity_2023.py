# ============================================================
# 03_extract_mapbox_activity_2023.py
#
# Purpose:
# 1. Read matched Mapbox cell -> park lookup
# 2. Query the large Mapbox CSV with DuckDB
# 3. Keep only matched cells
# 4. Keep analysis hours 6-20
# 5. Aggregate activity_index_total to park level
#
# Output:
# One row per:
# park_num x month x day_type x hour
# ============================================================

from pathlib import Path

import duckdb
import pandas as pd


# ------------------------------------------------------------
# Project paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "mapbox"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "mapbox"

PROCESSED_DIR.mkdir(
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


# ------------------------------------------------------------
# Cell -> park lookup
# ------------------------------------------------------------

LOOKUP_FILE = (
    INTERIM_DIR /
    "mapbox_cell_park_lookup_2023.csv"
)

if not LOOKUP_FILE.exists():
    raise FileNotFoundError(
        f"Lookup file not found: {LOOKUP_FILE}"
    )


# ------------------------------------------------------------
# Outputs
# ------------------------------------------------------------

CELL_ACTIVITY_OUTPUT = (
    INTERIM_DIR /
    "mapbox_matched_cell_activity_2023.csv"
)

PARK_ACTIVITY_OUTPUT = (
    PROCESSED_DIR /
    "mapbox_park_hourly_activity_2023.csv"
)

QA_OUTPUT = (
    INTERIM_DIR /
    "mapbox_park_activity_qa_2023.csv"
)


# ------------------------------------------------------------
# Inspect lookup
# ------------------------------------------------------------

lookup = pd.read_csv(
    LOOKUP_FILE,
    dtype={
        "park_num": str,
        "geography": str
    }
)

print("\nLookup loaded.")
print("Rows:", len(lookup))
print(
    "Unique Mapbox cells:",
    lookup["geography"].nunique()
)
print(
    "Unique parks:",
    lookup["park_num"].nunique()
)


# ------------------------------------------------------------
# DuckDB connection
# ------------------------------------------------------------

con = duckdb.connect()

# Register lookup dataframe directly inside DuckDB
con.register(
    "cell_lookup",
    lookup[
        [
            "park_num",
            "geography"
        ]
    ]
)


# ------------------------------------------------------------
# Extract matched activity records
#
# Important:
# - geography is read as VARCHAR
# - hours limited to 6-20 inclusive
# - only matched Mapbox cells retained
# ------------------------------------------------------------

print(
    "\nExtracting activity records for matched cells..."
)

query = f"""
SELECT
    l.park_num,
    CAST(m.geography AS VARCHAR) AS geography,
    m.xlon,
    m.xlat,
    m.start_date,
    m.end_date,
    m.agg_day_period,
    m.agg_time_period,
    m.activity_index_total

FROM read_csv_auto(
    '{MAPBOX_CSV.as_posix()}',
    header = true,
    types = {{'geography': 'VARCHAR'}}
) AS m

INNER JOIN cell_lookup AS l
    ON CAST(m.geography AS VARCHAR) = l.geography

WHERE
    m.agg_time_period BETWEEN 6 AND 20
"""

matched_activity = con.execute(
    query
).fetchdf()

print(
    "\nMatched activity rows:",
    len(matched_activity)
)

print(
    "Unique parks:",
    matched_activity["park_num"].nunique()
)

print(
    "Unique Mapbox cells:",
    matched_activity["geography"].nunique()
)


# ------------------------------------------------------------
# Save cell-level matched activity
#
# This is useful for QA and reproducibility.
# ------------------------------------------------------------

print(
    "\nSaving matched cell-level activity..."
)

matched_activity.to_csv(
    CELL_ACTIVITY_OUTPUT,
    index=False
)


# ------------------------------------------------------------
# Aggregate to park level
#
# Proposal method:
# For each site, activity_index_total across suitable
# Mapbox grid cells is averaged for each temporal period.
# ------------------------------------------------------------

print(
    "\nAggregating activity to park level..."
)

park_activity = (
    matched_activity
    .groupby(
        [
            "park_num",
            "start_date",
            "end_date",
            "agg_day_period",
            "agg_time_period"
        ],
        as_index=False
    )
    .agg(
        site_activity_index=(
            "activity_index_total",
            "mean"
        ),
        contributing_cell_records=(
            "geography",
            "count"
        ),
        unique_cells_used=(
            "geography",
            "nunique"
        )
    )
)


# ------------------------------------------------------------
# Add readable labels
# ------------------------------------------------------------

park_activity["day_type"] = (
    park_activity["agg_day_period"]
    .map(
        {
            0: "weekday",
            1: "weekend"
        }
    )
)

park_activity["hour_start"] = (
    park_activity["agg_time_period"]
)

park_activity["hour_end"] = (
    park_activity["agg_time_period"] + 1
)

# Example:
# 15 -> 15:00-16:00

park_activity["hour_label"] = (
    park_activity["hour_start"]
    .astype(str)
    .str.zfill(2)
    + ":00-"
    +
    park_activity["hour_end"]
    .astype(str)
    .str.zfill(2)
    + ":00"
)


# ------------------------------------------------------------
# Reorder columns
# ------------------------------------------------------------

park_activity = park_activity[
    [
        "park_num",
        "start_date",
        "end_date",
        "agg_day_period",
        "day_type",
        "agg_time_period",
        "hour_label",
        "site_activity_index",
        "unique_cells_used",
        "contributing_cell_records"
    ]
]


# ------------------------------------------------------------
# Sort
# ------------------------------------------------------------

park_activity["park_num_numeric"] = pd.to_numeric(
    park_activity["park_num"],
    errors="coerce"
)

park_activity = (
    park_activity
    .sort_values(
        [
            "park_num_numeric",
            "start_date",
            "agg_day_period",
            "agg_time_period"
        ]
    )
    .drop(
        columns="park_num_numeric"
    )
)


# ------------------------------------------------------------
# Save processed park-level activity
# ------------------------------------------------------------

park_activity.to_csv(
    PARK_ACTIVITY_OUTPUT,
    index=False
)

print(
    "\nPark-level activity rows:",
    len(park_activity)
)


# ------------------------------------------------------------
# QA 1:
# Number of temporal observations per park
#
# Maximum possible:
# 12 months x 2 day types x 15 hours = 360
# ------------------------------------------------------------

qa_by_park = (
    park_activity
    .groupby(
        "park_num"
    )
    .agg(
        temporal_records=(
            "site_activity_index",
            "size"
        ),
        min_activity=(
            "site_activity_index",
            "min"
        ),
        mean_activity=(
            "site_activity_index",
            "mean"
        ),
        max_activity=(
            "site_activity_index",
            "max"
        ),
        min_cells_used=(
            "unique_cells_used",
            "min"
        ),
        max_cells_used=(
            "unique_cells_used",
            "max"
        )
    )
    .reset_index()
)


qa_by_park["missing_temporal_records"] = (
    360 -
    qa_by_park["temporal_records"]
)

qa_by_park.to_csv(
    QA_OUTPUT,
    index=False
)


# ------------------------------------------------------------
# QA 2:
# Overall summary
# ------------------------------------------------------------

print("\n" + "=" * 55)
print("QA SUMMARY")
print("=" * 55)

print(
    "Parks represented:",
    park_activity["park_num"].nunique()
)

print(
    "Expected currently:",
    lookup["park_num"].nunique()
)

print(
    "Total park-level temporal rows:",
    len(park_activity)
)

print(
    "Maximum possible per park:",
    360
)

print(
    "\nTemporal records per park:"
)

print(
    qa_by_park[
        "temporal_records"
    ].describe()
)


# ------------------------------------------------------------
# Parks with fewer than 360 temporal records
# ------------------------------------------------------------

incomplete_parks = qa_by_park[
    qa_by_park[
        "temporal_records"
    ] < 360
].copy()

print(
    "\nParks with fewer than 360 temporal combinations:",
    len(incomplete_parks)
)

if not incomplete_parks.empty:

    print(
        incomplete_parks[
            [
                "park_num",
                "temporal_records",
                "missing_temporal_records"
            ]
        ].to_string(
            index=False
        )
    )


# ------------------------------------------------------------
# Check month coverage
# ------------------------------------------------------------

print(
    "\nMonths represented:"
)

print(
    sorted(
        park_activity[
            "start_date"
        ].astype(str).unique()
    )
)


# ------------------------------------------------------------
# Check day types
# ------------------------------------------------------------

print(
    "\nDay types represented:"
)

print(
    park_activity[
        [
            "agg_day_period",
            "day_type"
        ]
    ]
    .drop_duplicates()
    .sort_values(
        "agg_day_period"
    )
    .to_string(
        index=False
    )
)


# ------------------------------------------------------------
# Check hours
# ------------------------------------------------------------

print(
    "\nHours represented:"
)

print(
    sorted(
        park_activity[
            "agg_time_period"
        ].unique()
    )
)


# ------------------------------------------------------------
# Close DuckDB
# ------------------------------------------------------------

con.close()


# ------------------------------------------------------------
# Final paths
# ------------------------------------------------------------

print("\n" + "=" * 55)
print("MAPBOX ACTIVITY EXTRACTION COMPLETE")
print("=" * 55)

print("\nCell-level matched activity:")
print(CELL_ACTIVITY_OUTPUT)

print("\nFinal park-level hourly activity:")
print(PARK_ACTIVITY_OUTPUT)

print("\nQA summary:")
print(QA_OUTPUT)

print("\nDone.")
