"""
[UBS] Clean ArcGIS Census Enrich output

This script takes the raw ArcGIS Enrich output and creates processed
socio-demographic fields that match the Excel-style variables.

Input:
data/interim/census/census_enrich_prep.gdb/walktime_5_10_20_30_census_enriched

Outputs:
data/processed/census/census_processed.gdb/ubs_census_by_walktime
data/processed/census/ubs_census_by_walktime.csv
"""

import arcpy
from pathlib import Path
import csv


# ------------------------------------------------------------
# 1. Set paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[4]

INPUT_GDB = PROJECT_ROOT / "data" / "interim" / "census" / "census_enrich_prep.gdb"
INPUT_FC = INPUT_GDB / "walktime_5_10_20_30_census_enriched"

OUT_FOLDER = PROJECT_ROOT / "data" / "processed" / "census"
OUT_GDB = OUT_FOLDER / "census_processed.gdb"
OUT_FC = OUT_GDB / "ubs_census_by_walktime"

OUT_CSV = OUT_FOLDER / "ubs_census_by_walktime.csv"


# Keep QA fields while reviewing.
# Later, change this to False and rerun to remove QA fields from the CSV.
INCLUDE_QA_FIELDS = True


# ------------------------------------------------------------
# 2. Check input
# ------------------------------------------------------------

print("Checking input:")
print(INPUT_FC)

if not arcpy.Exists(str(INPUT_FC)):
    raise FileNotFoundError(
        f"Input feature class not found:\n{INPUT_FC}\n"
        "Run 02_run_arcgis_census_enrich.py first."
    )

input_count = int(arcpy.management.GetCount(str(INPUT_FC))[0])
print(f"Input records: {input_count}")

if input_count != 456:
    print("WARNING: Expected 456 records for 114 sites x 4 walk times.")


# ------------------------------------------------------------
# 3. Create processed Census folder and geodatabase
# ------------------------------------------------------------

OUT_FOLDER.mkdir(parents=True, exist_ok=True)

if not arcpy.Exists(str(OUT_GDB)):
    arcpy.management.CreateFileGDB(str(OUT_FOLDER), OUT_GDB.name)
    print(f"Created geodatabase: {OUT_GDB}")
else:
    print(f"Geodatabase already exists: {OUT_GDB}")


# ------------------------------------------------------------
# 4. Copy raw enriched layer to processed output
# ------------------------------------------------------------

if arcpy.Exists(str(OUT_FC)):
    arcpy.management.Delete(str(OUT_FC))
    print("Deleted old processed output.")

arcpy.management.CopyFeatures(str(INPUT_FC), str(OUT_FC))

print("\nCopied enriched layer to:")
print(OUT_FC)


# ------------------------------------------------------------
# 5. Add processed Census fields
# ------------------------------------------------------------

CLEAN_FIELDS = [
    ("household_median_income", "DOUBLE"),
    ("shelter_expenditures", "DOUBLE"),
    ("shelter_expenditures_principal", "DOUBLE"),
    ("shelter_total_expenditures_rent", "DOUBLE"),
    ("pct_low_income", "DOUBLE"),
    ("pct_no_college", "DOUBLE"),
    ("pct_bachelors_and_above", "DOUBLE"),
    ("pct_visible_minority", "DOUBLE"),
    ("pct_indigenous_identity", "DOUBLE"),
]

existing_fields = [field.name for field in arcpy.ListFields(str(OUT_FC))]

for field_name, field_type in CLEAN_FIELDS:
    if field_name not in existing_fields:
        arcpy.management.AddField(str(OUT_FC), field_name, field_type)
        print(f"Added field: {field_name}")


# ------------------------------------------------------------
# 6. Calculate processed Census fields
# ------------------------------------------------------------

LOW_INCOME_FIELDS = [
    "HouseholdIncAfterTaxCensusYear_A21HAT_5_P",
    "HouseholdIncAfterTaxCensusYear_A21HAT0510_P",
    "HouseholdIncAfterTaxCensusYear_A21HAT1015_P",
    "HouseholdIncAfterTaxCensusYear_A21HAT1520_P",
    "HouseholdIncAfterTaxCensusYear_A21HAT2025_P",
    "HouseholdIncAfterTaxCensusYear_A21HAT2530_P",
    "HouseholdIncAfterTaxCensusYear_A21HAT3035_P",
    "HouseholdIncAfterTaxCensusYear_A21HAT3540_P",
]

UPDATE_FIELDS = [
    # Raw direct fields
    "HouseholdIncomeConstantYear_EHYHRIMED",
    "Shelter_HSSH001_A",
    "Shelter_HSSH002_A",
    "Shelter_HSSH004_A",

    # Low-income bracket fields
    *LOW_INCOME_FIELDS,

    # Education fields
    "EducationalAttainment_EHYEDUNCDD_P",
    "EducationalAttainment_EHYEDUHSCE_P",
    "EducationalAttainment_EHYEDUUDBP_P",
    "EducationalAttainment_EHYEDUUDBD_P",

    # Identity fields
    "VisibleMinorityStatus_EHYVISVM_P",
    "IndigenousIdentity_A21AIDABOR_P",

    # Processed output fields
    "household_median_income",
    "shelter_expenditures",
    "shelter_expenditures_principal",
    "shelter_total_expenditures_rent",
    "pct_low_income",
    "pct_no_college",
    "pct_bachelors_and_above",
    "pct_visible_minority",
    "pct_indigenous_identity",
]


# Check that all needed fields exist before calculating
available_fields = [field.name for field in arcpy.ListFields(str(OUT_FC))]
missing_fields = [field for field in UPDATE_FIELDS if field not in available_fields]

if missing_fields:
    print("\nERROR: These fields are missing:")
    for field in missing_fields:
        print("-", field)
    raise ValueError("Missing required fields. Check the Enrich output.")
else:
    print("\nGood: all required fields exist.")


def safe_sum(values):
    """Sum values while ignoring None values."""
    valid_values = [value for value in values if value is not None]

    if not valid_values:
        return None

    return sum(valid_values)


with arcpy.da.UpdateCursor(str(OUT_FC), UPDATE_FIELDS) as cursor:
    field_index = {field: i for i, field in enumerate(cursor.fields)}

    for row in cursor:
        # Direct fields
        row[field_index["household_median_income"]] = row[
            field_index["HouseholdIncomeConstantYear_EHYHRIMED"]
        ]

        row[field_index["shelter_expenditures"]] = row[
            field_index["Shelter_HSSH001_A"]
        ]

        row[field_index["shelter_expenditures_principal"]] = row[
            field_index["Shelter_HSSH002_A"]
        ]

        row[field_index["shelter_total_expenditures_rent"]] = row[
            field_index["Shelter_HSSH004_A"]
        ]

        # Combined low-income field
        low_income_values = [
            row[field_index[field_name]] for field_name in LOW_INCOME_FIELDS
        ]

        row[field_index["pct_low_income"]] = safe_sum(low_income_values)

        # Combined education fields
        no_certificate = row[field_index["EducationalAttainment_EHYEDUNCDD_P"]]
        high_school = row[field_index["EducationalAttainment_EHYEDUHSCE_P"]]
        bachelors = row[field_index["EducationalAttainment_EHYEDUUDBP_P"]]
        above_bachelors = row[field_index["EducationalAttainment_EHYEDUUDBD_P"]]

        row[field_index["pct_no_college"]] = safe_sum(
            [no_certificate, high_school]
        )

        row[field_index["pct_bachelors_and_above"]] = safe_sum(
            [bachelors, above_bachelors]
        )

        # Direct identity fields
        row[field_index["pct_visible_minority"]] = row[
            field_index["VisibleMinorityStatus_EHYVISVM_P"]
        ]

        row[field_index["pct_indigenous_identity"]] = row[
            field_index["IndigenousIdentity_A21AIDABOR_P"]
        ]

        cursor.updateRow(row)

print("\nProcessed Census fields calculated.")


# ------------------------------------------------------------
# 7. Export one processed CSV
# ------------------------------------------------------------

BASE_CSV_FIELD_MAP = [
    ("park_num", "park_num"),
    ("PARK_NAME", "PARK_NAME"),
    ("MUNI", "MUNI"),
    ("walktime_min", "walktime_min"),
    ("distance_m", "distance_m"),
    ("access_point_count", "access_point_count"),

    ("household_median_income", "household-median-income"),
    ("shelter_expenditures", "shelter-expenditures"),
    ("shelter_expenditures_principal", "shelter-expenditures-principal"),
    ("shelter_total_expenditures_rent", "shelter-total-expenditures-rent"),
    ("pct_low_income", "pct-low-income"),
    ("pct_no_college", "pct-no-college"),
    ("pct_bachelors_and_above", "pct-bachelors-and-above"),
    ("pct_visible_minority", "pct-visible-minority"),
    ("pct_indigenous_identity", "pct-indigenous-identity"),
]

QA_FIELD_MAP = [
    ("HasData", "HasData"),
    ("apportionmentConfidence", "apportionmentConfidence"),
    ("populationToPolygonSizeRating", "populationToPolygonSizeRating"),
]

if INCLUDE_QA_FIELDS:
    CSV_FIELD_MAP = BASE_CSV_FIELD_MAP + QA_FIELD_MAP
else:
    CSV_FIELD_MAP = BASE_CSV_FIELD_MAP


def export_processed_csv(output_csv):
    """Export selected processed Census fields to one CSV."""

    field_names = [item[0] for item in CSV_FIELD_MAP]
    csv_headers = [item[1] for item in CSV_FIELD_MAP]

    with open(output_csv, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(csv_headers)

        with arcpy.da.SearchCursor(str(OUT_FC), field_names) as cursor:
            for row in cursor:
                writer.writerow(row)

    print(f"\nExported processed Census CSV:")
    print(output_csv)


# Delete older extra CSVs from the previous version if they exist
old_csvs = [
    OUT_FOLDER / "walktime_5_10_20_30_census_cleaned.csv",
    OUT_FOLDER / "05min_census_cleaned.csv",
    OUT_FOLDER / "10min_census_cleaned.csv",
    OUT_FOLDER / "20min_census_cleaned.csv",
    OUT_FOLDER / "30min_census_cleaned.csv",
]

for old_csv in old_csvs:
    if old_csv.exists():
        old_csv.unlink()
        print(f"Deleted old CSV: {old_csv}")


export_processed_csv(OUT_CSV)


# ------------------------------------------------------------
# 8. Final check
# ------------------------------------------------------------

out_count = int(arcpy.management.GetCount(str(OUT_FC))[0])

print("\nFinal processed feature class records:")
print(out_count)

if out_count == 456:
    print("\nDone. Census output is ready.")
else:
    print("\nWARNING: Output does not have 456 records.")
