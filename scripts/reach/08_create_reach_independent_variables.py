# 08_create_reach_independent_variables.py

from pathlib import Path
import pandas as pd


# ============================================================
# STEP 8: CREATE REACH INDEPENDENT VARIABLES TABLE
# One row per park, 5 independent variables total
# ============================================================

# -------------------------
# Paths
# -------------------------
PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "reach"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

BUS_COUNTS_INPUT = PROCESSED_DIR / "bus_stop_counts_5_10_20_30min.csv"

OUTPUT_CSV = PROCESSED_DIR / "reach_independent_variables.csv"


# -------------------------
# Fields
# -------------------------
PARK_ID_FIELD = "park_num"
PARK_NAME_FIELD = "PARK_NAME"

INDEPENDENT_VARIABLES = [
    "access_point_count",
    "bus_stops_05min",
    "bus_stops_10min",
    "bus_stops_20min",
    "bus_stops_30min",
]


# ============================================================
# Read data
# ============================================================

print("Reading bus stop/access point counts...")
reach = pd.read_csv(BUS_COUNTS_INPUT)

print("Input rows:", len(reach))
print("Input columns:")
print(list(reach.columns))


# ============================================================
# Check required fields
# ============================================================

required_fields = [
    PARK_ID_FIELD,
    PARK_NAME_FIELD,
    "MUNI",
] + INDEPENDENT_VARIABLES

missing_fields = [field for field in required_fields if field not in reach.columns]

if missing_fields:
    raise ValueError(
        "Missing required fields in input CSV:\n"
        + "\n".join(missing_fields)
    )


# ============================================================
# Keep only one row per park with the 5 independent variables
# ============================================================

iv_table = reach[
    [
        PARK_ID_FIELD,
        PARK_NAME_FIELD,
        "MUNI",
    ] + INDEPENDENT_VARIABLES
].copy()

# Ensure one row per park
iv_table = iv_table.drop_duplicates(subset=[PARK_ID_FIELD]).copy()

# Sort by park number
iv_table = iv_table.sort_values(PARK_ID_FIELD)

# Make count fields integers
for col in INDEPENDENT_VARIABLES:
    iv_table[col] = iv_table[col].fillna(0).astype(int)


# ============================================================
# Save output
# ============================================================

iv_table.to_csv(OUTPUT_CSV, index=False)

print("\nSaved reach independent variables table:")
print(OUTPUT_CSV)


# ============================================================
# Summary
# ============================================================

print("\nSummary:")
print("Rows/parks:", len(iv_table))
print("Independent variables:", len(INDEPENDENT_VARIABLES))
print("Variables:")
for var in INDEPENDENT_VARIABLES:
    print(f" - {var}")


print("\nFirst 10 rows:")
print(iv_table.head(10).to_string(index=False))

print("\nDone.") 