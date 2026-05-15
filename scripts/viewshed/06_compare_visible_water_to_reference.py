from pathlib import Path
import pandas as pd

# -------------------------
# Project paths
# -------------------------
project_folder = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\weekly_reports\urban_blue_green_accessibility"
)

# Inputs
our_summary_path = project_folder / "data" / "processed" / "viewshed" / "pilot_10_visible_water_summary.csv"

avery_excel_path = project_folder / "data" / "raw" / "All_UBS_Socio-demographic_+_Access-metrics_Feb-2026.xlsx"
avery_sheet = "Dependent_variables"

# Output
output_path = project_folder / "data" / "processed" / "viewshed" / "pilot_10_visible_water_comparison.csv"

# -------------------------
# Columns
# -------------------------
avery_park_id_col = "Park num"
avery_park_name_col = "Site name"
avery_visual_col = "Visual Access (Viewshed area in m2)"

# -------------------------
# Read data
# -------------------------
our = pd.read_csv(our_summary_path)

avery = pd.read_excel(
    avery_excel_path,
    sheet_name=avery_sheet
)

# -------------------------
# Clean/select fields
# -------------------------
our = our[
    [
        "park_num",
        "PARK_NAME",
        "observer_count",
        "observer_height_m",
        "analysis_buffer_m",
        "visible_water_cells",
        "cell_area_m2",
        "visible_water_area_m2",
        "visible_water_raster",
    ]
].copy()

avery = avery[
    [
        avery_park_id_col,
        avery_park_name_col,
        avery_visual_col,
    ]
].copy()

avery = avery.rename(
    columns={
        avery_park_id_col: "park_num",
        avery_park_name_col: "avery_PARK_NAME",
        avery_visual_col: "avery_visual_access_m2",
    }
)

# Make sure park_num types match
our["park_num"] = our["park_num"].astype(int)
avery["park_num"] = avery["park_num"].astype(int)

# Clean numeric values
our["visible_water_area_m2"] = pd.to_numeric(
    our["visible_water_area_m2"],
    errors="coerce"
)

avery["avery_visual_access_m2"] = pd.to_numeric(
    avery["avery_visual_access_m2"],
    errors="coerce"
)

# -------------------------
# Join comparison
# -------------------------
comparison = our.merge(
    avery,
    on="park_num",
    how="left"
)

# -------------------------
# Calculate differences
# -------------------------
comparison["diff_m2"] = (
    comparison["visible_water_area_m2"] -
    comparison["avery_visual_access_m2"]
)

comparison["percent_diff"] = comparison.apply(
    lambda row: None if row["avery_visual_access_m2"] == 0
    else (row["diff_m2"] / row["avery_visual_access_m2"]) * 100,
    axis=1
)

# Round values
round_cols = [
    "visible_water_area_m2",
    "avery_visual_access_m2",
    "diff_m2",
    "percent_diff",
]

for col in round_cols:
    comparison[col] = comparison[col].round(2)

# -------------------------
# Reorder columns
# -------------------------
comparison = comparison[
    [
        "park_num",
        "PARK_NAME",
        "visible_water_area_m2",
        "avery_visual_access_m2",
        "diff_m2",
        "percent_diff",
    ]
]

comparison = comparison.sort_values("park_num")

# -------------------------
# Save
# -------------------------
comparison.to_csv(output_path, index=False)

print("Saved:", output_path)

print("\nComparison preview:")

print(comparison)