from pathlib import Path
import geopandas as gpd
import pandas as pd
import re

PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

# ------------------------------------------------------------
# Inputs
# ------------------------------------------------------------

ANALYSIS_FILE = (
    PROJECT_ROOT /
    "data" /
    "processed" /
    "mapbox" /
    "mapbox_analysis_dataset_103_sites.csv"
)

TYPE_FILE = (
    PROJECT_ROOT /
    "data" /
    "raw" /
    "site_type_lookup_114.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT /
    "data" /
    "processed" /
    "mapbox" /
    "mapbox_analysis_dataset_103_sites_final.csv"
)

# ------------------------------------------------------------
# Find Park Extraction Project.gdb
# ------------------------------------------------------------

gdb_matches = list(
    PROJECT_ROOT.rglob("Park_Extraction_Project.gdb")
)

if not gdb_matches:
    raise FileNotFoundError(
        "Could not find Park Extraction Project.gdb."
    )

gdb = gdb_matches[0]

print("\nUsing geodatabase:")
print(gdb)

# ------------------------------------------------------------
# Find land-buffer layer
# ------------------------------------------------------------

layers = gpd.list_layers(gdb)

land_matches = [
    name for name in layers["name"].tolist()
    if "land" in name.lower()
    and "buffer" in name.lower()
]

if not land_matches:
    raise ValueError(
        "Could not identify the land-buffer layer."
    )

land_layer = land_matches[0]

print("\nUsing land layer:")
print(land_layer)

parks = gpd.read_file(
    gdb,
    layer=land_layer
)

print("\nLand layer records:", len(parks))
print("CRS:", parks.crs)

# ------------------------------------------------------------
# Calculate LAND-ONLY site area
# ------------------------------------------------------------

# EPSG:26910 is in metres
if parks.crs.to_epsg() != 26910:
    parks = parks.to_crs(26910)

parks["site_area_m2"] = parks.geometry.area

area_table = (
    parks[
        [
            "park_num",
            "PARK_NAME",
            "site_area_m2"
        ]
    ]
    .drop_duplicates("park_num")
    .copy()
)

area_table["park_num"] = (
    area_table["park_num"]
    .astype(int)
    .astype(str)
)

print(
    "\nUnique parks with calculated land area:",
    area_table["park_num"].nunique()
)

# ------------------------------------------------------------
# Read analysis dataset
# ------------------------------------------------------------

analysis = pd.read_csv(
    ANALYSIS_FILE,
    dtype={"park_num": str}
)

print("\nAnalysis dataset:")
print("Rows:", len(analysis))
print(
    "Unique parks:",
    analysis["park_num"].nunique()
)

# ------------------------------------------------------------
# Read proposal site-type lookup
# ------------------------------------------------------------

types = pd.read_csv(
    TYPE_FILE
)

print("\nProposal lookup:")
print("Rows:", len(types))

print("\nSite-type counts:")
print(
    types["site_type"].value_counts()
)

# ------------------------------------------------------------
# Normalize names for matching
# ------------------------------------------------------------

def normalize_name(value):

    value = str(value).lower().strip()

    value = value.replace("’", "'")
    value = value.replace("–", "-")
    value = value.replace("—", "-")

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


analysis["name_key"] = (
    analysis["site_name"]
    .apply(normalize_name)
)

types["name_key"] = (
    types["proposal_site_name"]
    .apply(normalize_name)
)

# ------------------------------------------------------------
# Join site type
# ------------------------------------------------------------

analysis = analysis.merge(
    types[
        [
            "name_key",
            "site_type",
            "proposal_site_name",
            "proposal_jurisdiction"
        ]
    ],
    on="name_key",
    how="left",
    validate="many_to_one"
)

# ------------------------------------------------------------
# Join land area by park_num
# ------------------------------------------------------------

analysis = analysis.merge(
    area_table[
        [
            "park_num",
            "site_area_m2"
        ]
    ],
    on="park_num",
    how="left",
    validate="many_to_one"
)

# ------------------------------------------------------------
# QA
# ------------------------------------------------------------

missing_type = (
    analysis.loc[
        analysis["site_type"].isna(),
        [
            "park_num",
            "site_name"
        ]
    ]
    .drop_duplicates()
)

missing_area = (
    analysis.loc[
        analysis["site_area_m2"].isna(),
        [
            "park_num",
            "site_name"
        ]
    ]
    .drop_duplicates()
)

print("\n" + "=" * 60)
print("QA")
print("=" * 60)

print(
    "\nParks missing site_type:",
    len(missing_type)
)

if not missing_type.empty:
    print(
        missing_type.to_string(
            index=False
        )
    )

print(
    "\nParks missing site_area_m2:",
    len(missing_area)
)

if not missing_area.empty:
    print(
        missing_area.to_string(
            index=False
        )
    )

print("\nSite types represented in the 103-site sample:")

site_type_counts = (
    analysis[
        [
            "park_num",
            "site_type"
        ]
    ]
    .drop_duplicates()
    ["site_type"]
    .value_counts(
        dropna=False
    )
)

print(site_type_counts)

# ------------------------------------------------------------
# Area summary
# ------------------------------------------------------------

park_area_summary = (
    analysis[
        [
            "park_num",
            "site_name",
            "site_area_m2"
        ]
    ]
    .drop_duplicates()
)

print("\nLand-area summary (m²):")
print(
    park_area_summary[
        "site_area_m2"
    ].describe()
)

# ------------------------------------------------------------
# Drop temporary matching key
# ------------------------------------------------------------

analysis = analysis.drop(
    columns=[
        "name_key",
        "proposal_site_name",
        "proposal_jurisdiction"
    ]
)

# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

analysis.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nFinal modeling dataset saved:")
print(OUTPUT_FILE)

print("\nRows:", len(analysis))
print(
    "Unique parks:",
    analysis["park_num"].nunique()
)

print("\nDone.")