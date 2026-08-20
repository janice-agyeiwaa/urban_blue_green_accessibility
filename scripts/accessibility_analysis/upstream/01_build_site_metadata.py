"""Build the 114-row Paper 3 site metadata table with ArcPy.

The spatial location is an inside representative point created by
FeatureToPoint(..., "INSIDE"). It is deliberately not called a centroid.
The output also contains land-buffer area and the four-category site-type
control used in the regressions.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import arcpy
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PARK_FC = str(
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Park_Extraction_Project.gdb"
    / "allparks_land_buffer"
)
SITE_TYPE_CSV = PROJECT_ROOT / "data" / "raw" / "site_type_lookup_114.csv"
ACCESS_CSV = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "accessibility_analysis"
    / "accessibility_site_metrics_114.csv"
)
OUTPUT_CSV = (
    PROJECT_ROOT / "data" / "processed" / "accessibility_analysis" / "site_metadata_114.csv"
)
TEMP_POINT_FC = r"in_memory\accessibility_representative_site_points"


def clean_site_name(value: object) -> str:
    text = str(value).lower().replace("&", " and ")
    text = re.sub(r"[\r\n]", " ", text)
    text = re.sub(
        r"\s*\((riverfront|lakefront|beach|coastal waterfront without beach|coastal promenade)\)\s*",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_park_id_field(feature_class: str) -> str:
    available = {field.name for field in arcpy.ListFields(feature_class)}
    candidates = (
        "park_num",
        "PARK_NUM",
        "Park_num",
        "ParkNum",
        "parknum",
        "PARKNUM",
        "Park num",
        "Park_Num",
        "PARK_ID",
        "park_id",
    )
    for candidate in candidates:
        if candidate in available:
            return candidate
    raise ValueError(f"Could not find a park ID field. Available fields: {sorted(available)}")


def main() -> None:
    if not arcpy.Exists(PARK_FC):
        raise FileNotFoundError(f"Park feature class not found: {PARK_FC}")
    for path in (SITE_TYPE_CSV, ACCESS_CSV):
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    arcpy.env.overwriteOutput = True
    park_id_field = find_park_id_field(PARK_FC)

    if arcpy.Exists(TEMP_POINT_FC):
        arcpy.management.Delete(TEMP_POINT_FC)
    arcpy.management.FeatureToPoint(PARK_FC, TEMP_POINT_FC, "INSIDE")

    spatial_rows: list[dict[str, float | int]] = []
    cursor_fields = [park_id_field, "SHAPE@XY", "SHAPE@AREA"]
    with arcpy.da.SearchCursor(TEMP_POINT_FC, cursor_fields) as cursor:
        for park_num, xy, area in cursor:
            if park_num is None or xy is None or area is None or area <= 0:
                raise ValueError(f"Invalid geometry metadata for park {park_num!r}")
            spatial_rows.append(
                {
                    "park_num": int(park_num),
                    "site_area_m2": float(area),
                    "log_site_area": math.log(float(area)),
                    "site_point_x": float(xy[0]),
                    "site_point_y": float(xy[1]),
                }
            )

    spatial = pd.DataFrame(spatial_rows)
    if len(spatial) != 114 or spatial["park_num"].nunique() != 114:
        raise ValueError("Expected exactly 114 unique park geometries.")

    access_names = pd.read_csv(ACCESS_CSV, usecols=["park_num", "site_name"])
    access_names["park_num"] = access_names["park_num"].astype(int)
    access_names["join_name"] = access_names["site_name"].map(clean_site_name)

    site_types = pd.read_csv(SITE_TYPE_CSV)
    site_types["join_name"] = site_types["proposal_site_name"].map(clean_site_name)
    site_types["site_type"] = site_types["site_type"].replace(
        {
            "beach + coastal promenade": "beach",
            "coastal promenade": "coastal waterfront without beach",
        }
    )

    metadata = (
        access_names[["park_num", "join_name"]]
        .merge(site_types[["join_name", "site_type"]], on="join_name", how="left", validate="one_to_one")
        .merge(spatial, on="park_num", how="left", validate="one_to_one")
        .drop(columns="join_name")
        .sort_values("park_num")
    )
    if len(metadata) != 114 or metadata.isna().any().any():
        missing = metadata.loc[metadata.isna().any(axis=1), "park_num"].tolist()
        raise ValueError(f"Site metadata is incomplete; affected park IDs: {missing}")

    metadata.to_csv(OUTPUT_CSV, index=False)
    arcpy.management.Delete(TEMP_POINT_FC)
    print(f"Saved {len(metadata)} sites to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
