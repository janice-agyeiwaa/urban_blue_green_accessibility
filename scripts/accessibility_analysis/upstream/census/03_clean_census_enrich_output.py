"""
[UBS] Clean ArcGIS Census Enrich output

This script takes the raw ArcGIS Enrich output and creates cleaned
socio-demographic fields that match the Excel-style variables.

Input:
data/interim/census/census_enrich_prep.gdb/walktime_5_10_20_30_census_enriched

Outputs:
data/processed/census/census_processed.gdb/walktime_5_10_20_30_census_cleaned

Also exports CSV files:
- walktime_5_10_20_30_census_cleaned.csv
- 05min_census_cleaned.csv
- 10min_census_cleaned.csv
- 20min_census_cleaned.csv
- 30min_census_cleaned.csv
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
OUT_FC = OUT_GDB / "walktime_5_10_20_30_census_cleaned"


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
    print("Deleted old cleaned output.")

arcpy.management.CopyFeatures(str(INPUT_FC), str(OUT_FC))

print("\nCopied enriched layer to:")
print(OUT_FC)


# ------------------------------------------------------------
# 5. Add cleaned fields
# ------------------------------------------------------------
# These are the final easier-to-read Census fields.
# They are created from the raw ArcGIS Enrich fields.

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
# 6. Calculate cleaned fields
# ------------------------------------------------------------
# The Excel created some fields by combining raw variables.
#
# pct_low_income:
# sum of household after-tax income brackets from <$5,000 to $35,000-$39,999
#
# pct_no_college:
# no certificate + high school
#
# pct_bachelors_and_above:
# bachelor's degree + above bachelor degree

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
    # raw direct fields
    "HouseholdIncomeConstantYear_EHYHRIMED",
    "Shelter_HSSH001_A",
    "Shelter_HSSH002_A",
    "Shelter_HSSH004_A",

    # low-income fields
    *LOW_INCOME_FIELDS,

    # education fields
    "EducationalAttainment_EHYEDUNCDD_P",
    "EducationalAttainment_EHYEDUHSCE_P",
    "EducationalAttainment_EHYEDUUDBP_P",
    "EducationalAttainment_EHYEDUUDBD_P",

    # identity fields
    "VisibleMinorityStatus_EHYVISVM_P",
    "IndigenousIdentity_A21AIDABOR_P",

    # cleaned output fields
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

print("\nCleaned fields calculated.")


# ------------------------------------------------------------
# 7. Export cleaned CSV files
# ------------------------------------------------------------
# These CSVs are easier to inspect and use outside ArcGIS.
# The geodatabase fields use underscores.
# The CSV headers use Excel-style hyphens.

CSV_FIELD_MAP = [
    ("park_num", "park_num"),
    ("PARK_NAME", "PARK_NAME"),
    ("MUNI", "MUNI"),
    ("walktime_min", "walktime_min"),
    ("distance_m", "distance_m"),
    ("access_point_count", "access_point_count"),
    ("HasData", "HasData"),
    ("apportionmentConfidence", "apportionmentConfidence"),
    ("populationToPolygonSizeRating", "populationToPolygonSizeRating"),

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


def export_clean_csv(output_csv, where_clause=None):
    """Export selected cleaned fields to CSV."""

    temp_layer = "census_cleaned_export_layer"

    if arcpy.Exists(temp_layer):
        arcpy.management.Delete(temp_layer)

    arcpy.management.MakeFeatureLayer(
        str(OUT_FC),
        temp_layer,
        where_clause
    )

    field_names = [item[0] for item in CSV_FIELD_MAP]
    csv_headers = [item[1] for item in CSV_FIELD_MAP]

    with open(output_csv, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(csv_headers)

        with arcpy.da.SearchCursor(temp_layer, field_names) as cursor:
            for row in cursor:
                writer.writerow(row)

    row_count = int(arcpy.management.GetCount(temp_layer)[0])
    print(f"Exported {row_count} records to: {output_csv}")


# Export one full CSV
all_csv = OUT_FOLDER / "walktime_5_10_20_30_census_cleaned.csv"
export_clean_csv(all_csv)

# Export one CSV per walk-time band
for walktime in [5, 10, 20, 30]:
    csv_path = OUT_FOLDER / f"{walktime:02d}min_census_cleaned.csv"
    export_clean_csv(csv_path, f"walktime_min = {walktime}")


# ------------------------------------------------------------
# 8. Final check
# ------------------------------------------------------------

out_count = int(arcpy.management.GetCount(str(OUT_FC))[0])

print("\nFinal cleaned feature class records:")
print(out_count)

if out_count == 456:
    print("\nDone. Cleaned Census output is ready.")
else:
    print("\nWARNING: Cleaned output does not have 456 records.")
