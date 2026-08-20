"""
[UBS] Run ArcGIS Census Enrich on walk-time polygons

This script enriches the 5, 10, 20, and 30 minute walk-time polygons
with Census and household spending variables using ArcGIS Enrich.

The script is written for the full 456 records, but it has a test mode.

When RUN_TEST = True:
    only the first few records are enriched.

When RUN_TEST = False:
    all 456 records are enriched.

Input:
data/interim/census/census_enrich_prep.gdb/walktime_5_10_20_30_for_census

Output:
data/interim/census/census_enrich_prep.gdb/walktime_5_10_20_30_census_enriched
"""

import arcpy
from pathlib import Path


# ------------------------------------------------------------
# 1. Set paths
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[4]

IN_GDB = PROJECT_ROOT / "data" / "interim" / "census" / "census_enrich_prep.gdb"

INPUT_FC = IN_GDB / "walktime_5_10_20_30_for_census"

OUT_FC = IN_GDB / "walktime_5_10_20_30_census_enriched"


# ------------------------------------------------------------
# 2. Test settings
# ------------------------------------------------------------
# Keep this as True first.
# This lets us test on only 2 records before spending credits on all 456.

RUN_TEST = False
TEST_RECORD_LIMIT = 2


# ------------------------------------------------------------
# 3. ArcGIS Enrich variables
# ------------------------------------------------------------
# These variable codes came from the ArcGIS Pro Enrich tool history.

ENRICH_VARIABLES = (
    "HouseholdIncomeConstantYear.EHYHRIMED;"
    "Shelter.HSSH001_A;"
    "Shelter.HSSH002_A;"
    "Shelter.HSSH004_A;"
    "HouseholdIncAfterTaxCensusYear.A21HAT3540_P;"
    "HouseholdIncAfterTaxCensusYear.A21HAT3035_P;"
    "HouseholdIncAfterTaxCensusYear.A21HAT2530_P;"
    "HouseholdIncAfterTaxCensusYear.A21HAT2025_P;"
    "HouseholdIncAfterTaxCensusYear.A21HAT1015_P;"
    "HouseholdIncAfterTaxCensusYear.A21HAT0510_P;"
    "HouseholdIncAfterTaxCensusYear.A21HAT_5_P;"
    "HouseholdIncAfterTaxCensusYear.A21HAT1520_P;"
    "EducationalAttainment.EHYEDUNCDD_P;"
    "EducationalAttainment.EHYEDUHSCE_P;"
    "EducationalAttainment.EHYEDUUDBP_P;"
    "EducationalAttainment.EHYEDUUDBD_P;"
    "VisibleMinorityStatus.EHYVISVM_P;"
    "IndigenousIdentity.A21AIDABOR_P"
)


# ------------------------------------------------------------
# 4. Check input
# ------------------------------------------------------------

print("Checking input feature class:")
print(INPUT_FC)

if not arcpy.Exists(str(INPUT_FC)):
    raise FileNotFoundError(
        f"Input feature class not found:\n{INPUT_FC}\n"
        "Run 01_prepare_walktime_for_census_enrich.py first."
    )

input_count = int(arcpy.management.GetCount(str(INPUT_FC))[0])

print("\nInput records:")
print(input_count)

if input_count != 456:
    print("WARNING: Expected 456 records for 114 sites x 4 walk times.")


# ------------------------------------------------------------
# 5. Create temporary layer for Enrich
# ------------------------------------------------------------
# ArcGIS Enrich will use this layer.
# If RUN_TEST is True, we select only the first 2 records.
# If RUN_TEST is False, we leave all 456 records selected.

TEMP_LAYER = "walktime_for_census_enrich_layer"

if arcpy.Exists(TEMP_LAYER):
    arcpy.management.Delete(TEMP_LAYER)

arcpy.management.MakeFeatureLayer(
    str(INPUT_FC),
    TEMP_LAYER
)

oid_field = arcpy.Describe(TEMP_LAYER).OIDFieldName

if RUN_TEST:
    test_oids = []

    with arcpy.da.SearchCursor(TEMP_LAYER, [oid_field]) as cursor:
        for row in cursor:
            test_oids.append(row[0])

            if len(test_oids) == TEST_RECORD_LIMIT:
                break

    oid_text = ", ".join(str(oid) for oid in test_oids)
    where_clause = f"{oid_field} IN ({oid_text})"

    arcpy.management.SelectLayerByAttribute(
        TEMP_LAYER,
        "NEW_SELECTION",
        where_clause
    )

    selected_count = int(arcpy.management.GetCount(TEMP_LAYER)[0])

    print("\nRUN_TEST is True.")
    print("Selected test ObjectIDs:")
    print(test_oids)
    print("Selected records:")
    print(selected_count)

else:
    selected_count = int(arcpy.management.GetCount(TEMP_LAYER)[0])

    print("\nRUN_TEST is False.")
    print("Running Enrich on all records:")
    print(selected_count)


# ------------------------------------------------------------
# 6. Delete old output if it exists
# ------------------------------------------------------------

if arcpy.Exists(str(OUT_FC)):
    arcpy.management.Delete(str(OUT_FC))
    print("\nDeleted old output feature class.")


# ------------------------------------------------------------
# 7. Run ArcGIS Enrich
# ------------------------------------------------------------
# This uses ArcGIS credits.
# Since the input features are already polygons, we are not adding buffers.

print("\nRunning ArcGIS Enrich...")

arcpy.analysis.Enrich(
    in_features=TEMP_LAYER,
    out_feature_class=str(OUT_FC),
    variables=ENRICH_VARIABLES,
    buffer_type="",
    distance=1,
    unit=""
)

print("\nEnrich complete.")

out_count = int(arcpy.management.GetCount(str(OUT_FC))[0])

print("\nOutput created:")
print(OUT_FC)

print("\nOutput records:")
print(out_count)


# ------------------------------------------------------------
# 8. Final message
# ------------------------------------------------------------

if RUN_TEST:
    print(
        "\nTest run finished. Check the output in ArcGIS Pro. "
        "If the enriched fields look correct, set RUN_TEST = False "
        "and rerun for all 456 records."
    )
else:
    print("\nFull Census Enrich run finished.")
