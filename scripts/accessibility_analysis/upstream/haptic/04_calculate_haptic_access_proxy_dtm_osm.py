# 04_calculate_haptic_access_proxy_dtm_osm_geopandas.py

from pathlib import Path

import geopandas as gpd
import pandas as pd


# ============================================================
# STEP 4: DTM + OSM HAPTIC ACCESS PROXY
# GeoPandas version, no ArcPy
# ============================================================
# Uses:
# - terrain_based_haptic_proxy_dtm.csv
# - terrain_based_haptic_segments_dtm.csv
# - haptic_shoreline_landside_buffers_dtm from haptic_temp.gdb
# - OSM barriers/bridges/beach/sand from script 03
#
# Logic:
# approachable shoreline = gentle slope shoreline OR beach/sand shoreline
# unobstructed approachable shoreline = approachable shoreline with no mapped barrier
#
# Final score:
# haptic_access_proxy_score =
# unobstructed_approachable_shoreline_length_m / shoreline_length_m
#
# Bridges are reported for review but not penalized for now.
# ============================================================


# -------------------------
# Paths
# -------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[4]

INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "haptic"
OSM_INTERIM_DIR = INTERIM_DIR / "osm"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "haptic"

OSM_INTERIM_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

LANDSIDE_BUFFERS_GDB = INTERIM_DIR / "haptic_temp.gdb"
LANDSIDE_BUFFERS_LAYER = "haptic_shoreline_landside_buffers_dtm"

DTM_HAPTIC_CSV = PROCESSED_DIR / "terrain_based_haptic_proxy_dtm.csv"
DTM_SEGMENT_CSV = PROCESSED_DIR / "terrain_based_haptic_segments_dtm.csv"

OSM_BARRIER_POINTS = OSM_INTERIM_DIR / "osm_barrier_points.geojson"
OSM_BARRIER_LINES = OSM_INTERIM_DIR / "osm_barrier_lines.geojson"
OSM_BRIDGE_LINES = OSM_INTERIM_DIR / "osm_bridge_lines.geojson"

OSM_BEACH_POLYGONS = OSM_INTERIM_DIR / "osm_beach_sand_polygons.geojson"
OSM_BEACH_LINES = OSM_INTERIM_DIR / "osm_beach_sand_lines.geojson"

BARRIER_POINTS_NEAR_OUT = OSM_INTERIM_DIR / "osm_barrier_points_near_shoreline.gpkg"
BARRIER_LINES_NEAR_OUT = OSM_INTERIM_DIR / "osm_barrier_lines_near_shoreline.gpkg"
BRIDGE_LINES_NEAR_OUT = OSM_INTERIM_DIR / "osm_bridge_lines_near_shoreline.gpkg"

BEACH_POLYGONS_NEAR_OUT = OSM_INTERIM_DIR / "osm_beach_sand_polygons_near_shoreline.gpkg"
BEACH_LINES_NEAR_OUT = OSM_INTERIM_DIR / "osm_beach_sand_lines_near_shoreline.gpkg"

OSM_PROXY_CSV = OSM_INTERIM_DIR / "osm_barrier_beach_obstruction_proxy.csv"
FINAL_HAPTIC_CSV = PROCESSED_DIR / "haptic_access_proxy_dtm_osm.csv"


# -------------------------
# Fields
# -------------------------
PARK_ID_FIELD = "park_num"
PARK_NAME_FIELD = "PARK_NAME"
MUNI_FIELD = "MUNI"

SEGMENT_ID_FIELD = "global_segment_id"
SEGMENT_LENGTH_FIELD = "segment_length_m"

PROJECT_CRS = "EPSG:26910"


# ============================================================
# Helper functions
# ============================================================

def require_file(path: Path, label: str):
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def read_vector(path: Path, label: str, layer: str | None = None) -> gpd.GeoDataFrame:
    print(f"\nReading {label}:")
    print(path)

    try:
        if layer is None:
            gdf = gpd.read_file(path)
        else:
            gdf = gpd.read_file(path, layer=layer)
    except Exception as e:
        raise FileNotFoundError(
            f"Could not read {label}: {path}\n"
            f"Layer: {layer}\n"
            f"Original error: {e}"
        )

    if gdf.crs is None:
        print(f"{label} has no CRS. Assuming EPSG:26910.")
        gdf = gdf.set_crs(epsg=26910)

    print(f"{label} features:", len(gdf))
    print(f"{label} CRS:", gdf.crs)

    return gdf


def clean_park_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if PARK_NAME_FIELD in df.columns:
        df[PARK_NAME_FIELD] = (
            df[PARK_NAME_FIELD]
            .astype(str)
            .str.replace(r"[\r\n]+", " ", regex=True)
            .str.strip()
        )

    return df


def make_valid(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()

    if gdf.empty:
        return gdf

    gdf = gdf[~gdf.geometry.isna()].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    if gdf.empty:
        return gdf

    try:
        gdf["geometry"] = gdf.geometry.make_valid()
    except Exception:
        gdf["geometry"] = gdf.geometry.buffer(0)

    gdf = gdf[~gdf.geometry.is_empty].copy()

    return gdf


def delete_file_if_exists(path: Path):
    if path.exists():
        try:
            path.unlink()
        except PermissionError:
            raise PermissionError(
                f"\nCould not overwrite this file because it is open or locked:\n"
                f"{path}\n\n"
                f"Close it in ArcGIS Pro, remove it from the map, or rename the output."
            )


def spatial_intersect_with_buffers(
    osm_gdf: gpd.GeoDataFrame,
    buffers: gpd.GeoDataFrame,
    label: str,
    output_path: Path | None = None,
) -> gpd.GeoDataFrame:
    """
    Intersects OSM features with shoreline segment buffers.

    Output contains segment attributes from buffers and OSM attributes.
    """
    empty_output = gpd.GeoDataFrame(
        columns=list(buffers.columns),
        geometry=[],
        crs=buffers.crs
    )

    if osm_gdf.empty:
        print(f"{label}: no input features.")
        return empty_output

    osm_gdf = osm_gdf.to_crs(buffers.crs)
    osm_gdf = make_valid(osm_gdf)

    if osm_gdf.empty:
        print(f"{label}: no valid features.")
        return empty_output

    print(f"\nFiltering {label} to shoreline buffer area...")

    buffer_union = buffers.union_all()
    osm_gdf = osm_gdf[osm_gdf.intersects(buffer_union)].copy()

    if osm_gdf.empty:
        print(f"{label}: no features intersect shoreline buffers.")
        return empty_output

    print(f"Overlaying {label} with shoreline buffers...")

    osm_keep_cols = [
        c for c in osm_gdf.columns
        if c != "geometry"
        and c in [
            "osm_type",
            "osm_id",
            "osm_category",
            "barrier",
            "access",
            "bridge",
            "highway",
            "footway",
            "natural",
            "surface",
            "landcover",
            "name",
        ]
    ]

    osm_small = osm_gdf[osm_keep_cols + ["geometry"]].copy()

    buffer_keep_cols = [
        PARK_ID_FIELD,
        PARK_NAME_FIELD,
        MUNI_FIELD,
        SEGMENT_ID_FIELD,
        SEGMENT_LENGTH_FIELD,
        "geometry",
    ]

    missing = [c for c in buffer_keep_cols if c not in buffers.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in shoreline buffers: {missing}"
        )

    buffers_small = buffers[buffer_keep_cols].copy()

    intersected = gpd.overlay(
        buffers_small,
        osm_small,
        how="intersection",
        keep_geom_type=False
    )

    intersected = make_valid(intersected)

    print(f"{label} near shoreline features:", len(intersected))

    if output_path is not None and not intersected.empty:
        delete_file_if_exists(output_path)
        intersected.to_file(output_path, driver="GPKG")
        print(f"Saved review layer: {output_path}")

    return intersected


def summarize_affected_segments(
    intersected: gpd.GeoDataFrame,
    prefix: str,
) -> pd.DataFrame:
    """
    Segment-level summary.

    If any feature intersects a segment buffer, the full shoreline
    segment is treated as affected/present for that feature class.

    This avoids double-counting exact overlay lengths from points,
    diagonal lines, or overlapping OSM features.
    """
    output_cols = [
        PARK_ID_FIELD,
        f"{prefix}_affected_segment_count",
        f"{prefix}_affected_shoreline_length_m",
        f"{prefix}_feature_count",
        f"{prefix}_intersect_length_m",
    ]

    if intersected.empty:
        return pd.DataFrame(columns=output_cols)

    required = [
        PARK_ID_FIELD,
        SEGMENT_ID_FIELD,
        SEGMENT_LENGTH_FIELD,
        "geometry",
    ]

    missing = [c for c in required if c not in intersected.columns]
    if missing:
        raise ValueError(f"Missing required fields in intersected {prefix}: {missing}")

    df = intersected.copy()

    df[f"{prefix}_intersect_length_m"] = df.geometry.length
    df[f"{prefix}_feature_count"] = 1

    unique_segments = (
        df[[PARK_ID_FIELD, SEGMENT_ID_FIELD, SEGMENT_LENGTH_FIELD]]
        .drop_duplicates(subset=[PARK_ID_FIELD, SEGMENT_ID_FIELD])
        .groupby(PARK_ID_FIELD, as_index=False)
        .agg(
            **{
                f"{prefix}_affected_segment_count": (SEGMENT_ID_FIELD, "count"),
                f"{prefix}_affected_shoreline_length_m": (
                    SEGMENT_LENGTH_FIELD,
                    "sum",
                ),
            }
        )
    )

    feature_summary = (
        df
        .groupby(PARK_ID_FIELD, as_index=False)
        .agg(
            **{
                f"{prefix}_feature_count": (f"{prefix}_feature_count", "sum"),
                f"{prefix}_intersect_length_m": (
                    f"{prefix}_intersect_length_m",
                    "sum",
                ),
            }
        )
    )

    summary = unique_segments.merge(
        feature_summary,
        on=PARK_ID_FIELD,
        how="left"
    )

    return summary[output_cols]


# ============================================================
# Main
# ============================================================

def main():
    # --------------------------------------------------------
    # Read shoreline buffers
    # --------------------------------------------------------
    buffers = read_vector(
        LANDSIDE_BUFFERS_GDB,
        "shoreline land-side buffers",
        layer=LANDSIDE_BUFFERS_LAYER
    )

    buffers = buffers.to_crs(PROJECT_CRS)
    buffers = make_valid(buffers)
    buffers = clean_park_names(buffers)

    print("\nBuffer fields:")
    print(list(buffers.columns))

    if buffers.empty:
        raise ValueError("Shoreline land-side buffers are empty.")

    # --------------------------------------------------------
    # Read OSM features
    # --------------------------------------------------------
    barrier_points = read_vector(OSM_BARRIER_POINTS, "OSM barrier points")
    barrier_lines = read_vector(OSM_BARRIER_LINES, "OSM barrier lines")
    bridge_lines = read_vector(OSM_BRIDGE_LINES, "OSM bridge lines")

    beach_polygons = read_vector(OSM_BEACH_POLYGONS, "OSM beach/sand polygons")
    beach_lines = read_vector(OSM_BEACH_LINES, "OSM beach/sand lines")

    barrier_points = make_valid(barrier_points)
    barrier_lines = make_valid(barrier_lines)
    bridge_lines = make_valid(bridge_lines)
    beach_polygons = make_valid(beach_polygons)
    beach_lines = make_valid(beach_lines)

    # --------------------------------------------------------
    # Intersect OSM features with shoreline buffers
    # --------------------------------------------------------
    barrier_points_near = spatial_intersect_with_buffers(
        barrier_points,
        buffers,
        label="barrier points",
        output_path=BARRIER_POINTS_NEAR_OUT
    )

    barrier_lines_near = spatial_intersect_with_buffers(
        barrier_lines,
        buffers,
        label="barrier lines",
        output_path=BARRIER_LINES_NEAR_OUT
    )

    bridge_lines_near = spatial_intersect_with_buffers(
        bridge_lines,
        buffers,
        label="bridge lines",
        output_path=BRIDGE_LINES_NEAR_OUT
    )

    beach_polygons_near = spatial_intersect_with_buffers(
        beach_polygons,
        buffers,
        label="beach/sand polygons",
        output_path=BEACH_POLYGONS_NEAR_OUT
    )

    beach_lines_near = spatial_intersect_with_buffers(
        beach_lines,
        buffers,
        label="beach/sand lines",
        output_path=BEACH_LINES_NEAR_OUT
    )

    # --------------------------------------------------------
    # Summarize affected/present shoreline segments
    # --------------------------------------------------------
    barrier_combined = pd.concat(
        [barrier_points_near, barrier_lines_near],
        ignore_index=True
    )

    beach_combined = pd.concat(
        [beach_polygons_near, beach_lines_near],
        ignore_index=True
    )

    barrier_summary = summarize_affected_segments(
        barrier_combined,
        prefix="barrier"
    )

    bridge_summary = summarize_affected_segments(
        bridge_lines_near,
        prefix="bridge"
    )

    beach_summary = summarize_affected_segments(
        beach_combined,
        prefix="beach_sand"
    )

    print("\nBarrier summary rows:", len(barrier_summary))
    print("Bridge summary rows:", len(bridge_summary))
    print("Beach/sand summary rows:", len(beach_summary))

    # --------------------------------------------------------
    # Read DTM haptic park-level table
    # --------------------------------------------------------
    require_file(DTM_HAPTIC_CSV, "DTM haptic CSV")

    haptic = pd.read_csv(DTM_HAPTIC_CSV)
    haptic = clean_park_names(haptic)

    required_haptic_cols = [
        PARK_ID_FIELD,
        PARK_NAME_FIELD,
        MUNI_FIELD,
        "shoreline_length_m",
        "segment_count",
        "gentle_shoreline_ratio",
        "mean_shoreline_slope_degrees",
    ]

    missing = [c for c in required_haptic_cols if c not in haptic.columns]
    if missing:
        raise ValueError(
            f"Missing required fields in DTM haptic CSV: {missing}"
        )

    # Keep slope threshold fields if script 02 created them.
    optional_haptic_cols = [
        "slope_threshold_percent",
        "slope_threshold_degrees",
        "slope_data_coverage_ratio",
    ]

    keep_haptic_cols = required_haptic_cols + [
        c for c in optional_haptic_cols if c in haptic.columns
    ]

    out = haptic[keep_haptic_cols].copy()

    # --------------------------------------------------------
    # Read DTM segment-level table
    # --------------------------------------------------------
    require_file(DTM_SEGMENT_CSV, "DTM segment-level haptic CSV")

    segments = pd.read_csv(DTM_SEGMENT_CSV)
    segments = clean_park_names(segments)

    required_segment_cols = [
        PARK_ID_FIELD,
        SEGMENT_ID_FIELD,
        SEGMENT_LENGTH_FIELD,
        "gentle_shoreline",
    ]

    missing = [c for c in required_segment_cols if c not in segments.columns]
    if missing:
        raise ValueError(
            f"Missing required fields in DTM segment-level CSV: {missing}"
        )

    # --------------------------------------------------------
    # Create segment-level beach/sand and barrier flags
    # --------------------------------------------------------

    # Beach/sand segments
    if beach_combined.empty:
        beach_segment_ids = pd.DataFrame(
            columns=[PARK_ID_FIELD, SEGMENT_ID_FIELD]
        )
    else:
        beach_segment_ids = (
            beach_combined[[PARK_ID_FIELD, SEGMENT_ID_FIELD]]
            .drop_duplicates()
            .copy()
        )

    beach_segment_ids["beach_sand_shoreline"] = 1

    # Barrier-affected segments
    if barrier_combined.empty:
        barrier_segment_ids = pd.DataFrame(
            columns=[PARK_ID_FIELD, SEGMENT_ID_FIELD]
        )
    else:
        barrier_segment_ids = (
            barrier_combined[[PARK_ID_FIELD, SEGMENT_ID_FIELD]]
            .drop_duplicates()
            .copy()
        )

    barrier_segment_ids["barrier_affected_shoreline"] = 1

    # Join beach/sand and barrier flags to shoreline segments
    segments = segments.merge(
        beach_segment_ids,
        on=[PARK_ID_FIELD, SEGMENT_ID_FIELD],
        how="left"
    )

    segments = segments.merge(
        barrier_segment_ids,
        on=[PARK_ID_FIELD, SEGMENT_ID_FIELD],
        how="left"
    )

    segments["beach_sand_shoreline"] = (
        segments["beach_sand_shoreline"]
        .fillna(0)
        .astype(int)
    )

    segments["barrier_affected_shoreline"] = (
        segments["barrier_affected_shoreline"]
        .fillna(0)
        .astype(int)
    )

    segments["gentle_shoreline"] = (
        segments["gentle_shoreline"]
        .fillna(0)
        .astype(int)
    )

    # Approachable shoreline = gentle slope OR beach/sand
    segments["approachable_shoreline"] = (
        (segments["gentle_shoreline"] == 1)
        | (segments["beach_sand_shoreline"] == 1)
    ).astype(int)

    # Final haptic shoreline = approachable AND not barrier-affected
    segments["unobstructed_approachable_shoreline"] = (
        (segments["approachable_shoreline"] == 1)
        & (segments["barrier_affected_shoreline"] == 0)
    ).astype(int)

    # QA flag: approachable shoreline affected by barrier
    segments["barrier_on_approachable_shoreline"] = (
        (segments["approachable_shoreline"] == 1)
        & (segments["barrier_affected_shoreline"] == 1)
    ).astype(int)

    # Length fields
    segments["approachable_length_m"] = segments.apply(
        lambda row: row[SEGMENT_LENGTH_FIELD]
        if row["approachable_shoreline"] == 1
        else 0,
        axis=1
    )

    segments["beach_sand_length_m"] = segments.apply(
        lambda row: row[SEGMENT_LENGTH_FIELD]
        if row["beach_sand_shoreline"] == 1
        else 0,
        axis=1
    )

    segments["unobstructed_approachable_length_m"] = segments.apply(
        lambda row: row[SEGMENT_LENGTH_FIELD]
        if row["unobstructed_approachable_shoreline"] == 1
        else 0,
        axis=1
    )

    segments["barrier_on_approachable_length_m"] = segments.apply(
        lambda row: row[SEGMENT_LENGTH_FIELD]
        if row["barrier_on_approachable_shoreline"] == 1
        else 0,
        axis=1
    )

    approachable_summary = (
        segments
        .groupby(PARK_ID_FIELD, as_index=False)
        .agg(
            approachable_shoreline_length_m=(
                "approachable_length_m",
                "sum"
            ),
            beach_sand_shoreline_length_m=(
                "beach_sand_length_m",
                "sum"
            ),
            unobstructed_approachable_shoreline_length_m=(
                "unobstructed_approachable_length_m",
                "sum"
            ),
            barrier_on_approachable_shoreline_length_m=(
                "barrier_on_approachable_length_m",
                "sum"
            ),
            approachable_segment_count=(
                "approachable_shoreline",
                "sum"
            ),
            beach_sand_segment_count=(
                "beach_sand_shoreline",
                "sum"
            ),
            unobstructed_approachable_segment_count=(
                "unobstructed_approachable_shoreline",
                "sum"
            ),
            barrier_on_approachable_segment_count=(
                "barrier_on_approachable_shoreline",
                "sum"
            ),
        )
    )

    # --------------------------------------------------------
    # Merge OSM and approachable summaries
    # --------------------------------------------------------
    out = out.merge(
        barrier_summary,
        on=PARK_ID_FIELD,
        how="left"
    )

    out = out.merge(
        bridge_summary,
        on=PARK_ID_FIELD,
        how="left"
    )

    out = out.merge(
        beach_summary,
        on=PARK_ID_FIELD,
        how="left"
    )

    out = out.merge(
        approachable_summary,
        on=PARK_ID_FIELD,
        how="left"
    )

    fill_zero_cols = [
        "barrier_affected_segment_count",
        "barrier_affected_shoreline_length_m",
        "barrier_feature_count",
        "barrier_intersect_length_m",

        "bridge_affected_segment_count",
        "bridge_affected_shoreline_length_m",
        "bridge_feature_count",
        "bridge_intersect_length_m",

        "beach_sand_affected_segment_count",
        "beach_sand_affected_shoreline_length_m",
        "beach_sand_feature_count",
        "beach_sand_intersect_length_m",

        "approachable_shoreline_length_m",
        "beach_sand_shoreline_length_m",
        "approachable_segment_count",
        "beach_sand_segment_count",

        "unobstructed_approachable_shoreline_length_m",
        "barrier_on_approachable_shoreline_length_m",
        "unobstructed_approachable_segment_count",
        "barrier_on_approachable_segment_count",
    ]

    for col in fill_zero_cols:
        if col not in out.columns:
            out[col] = 0
        out[col] = out[col].fillna(0)

    # --------------------------------------------------------
    # Calculate obstruction, beach/sand, and haptic variables
    # --------------------------------------------------------
    out["has_barrier_near_shoreline"] = (
        out["barrier_affected_segment_count"] > 0
    ).astype(int)

    out["has_bridge_near_shoreline"] = (
        out["bridge_affected_segment_count"] > 0
    ).astype(int)

    out["has_beach_sand_near_shoreline"] = (
        out["beach_sand_affected_segment_count"] > 0
    ).astype(int)

    out["barrier_affected_segment_ratio"] = (
        out["barrier_affected_segment_count"] / out["segment_count"]
    )

    out["bridge_affected_segment_ratio"] = (
        out["bridge_affected_segment_count"] / out["segment_count"]
    )

    out["beach_sand_segment_ratio"] = (
        out["beach_sand_segment_count"] / out["segment_count"]
    )

    out["approachable_segment_ratio"] = (
        out["approachable_segment_count"] / out["segment_count"]
    )

    out["unobstructed_approachable_segment_ratio"] = (
        out["unobstructed_approachable_segment_count"] / out["segment_count"]
    )

    out["barrier_on_approachable_segment_ratio"] = (
        out["barrier_on_approachable_segment_count"] / out["segment_count"]
    )

    out["barrier_affected_shoreline_ratio"] = (
        out["barrier_affected_shoreline_length_m"]
        / out["shoreline_length_m"]
    )

    out["bridge_affected_shoreline_ratio"] = (
        out["bridge_affected_shoreline_length_m"]
        / out["shoreline_length_m"]
    )

    out["beach_sand_shoreline_ratio"] = (
        out["beach_sand_shoreline_length_m"]
        / out["shoreline_length_m"]
    )

    out["approachable_shoreline_ratio"] = (
        out["approachable_shoreline_length_m"]
        / out["shoreline_length_m"]
    )

    out["unobstructed_approachable_shoreline_ratio"] = (
        out["unobstructed_approachable_shoreline_length_m"]
        / out["shoreline_length_m"]
    )

    out["barrier_on_approachable_shoreline_ratio"] = (
        out["barrier_on_approachable_shoreline_length_m"]
        / out["shoreline_length_m"]
    )

    ratio_cols = [
        "barrier_affected_segment_ratio",
        "bridge_affected_segment_ratio",
        "beach_sand_segment_ratio",
        "approachable_segment_ratio",
        "unobstructed_approachable_segment_ratio",
        "barrier_on_approachable_segment_ratio",
        "barrier_affected_shoreline_ratio",
        "bridge_affected_shoreline_ratio",
        "beach_sand_shoreline_ratio",
        "approachable_shoreline_ratio",
        "unobstructed_approachable_shoreline_ratio",
        "barrier_on_approachable_shoreline_ratio",
    ]

    for col in ratio_cols:
        out[col] = out[col].fillna(0).clip(lower=0, upper=1)

    # --------------------------------------------------------
    # Final DTM + OSM haptic score
    # --------------------------------------------------------
    out["haptic_access_proxy_score"] = (
        out["unobstructed_approachable_shoreline_ratio"]
    )

    out["haptic_access_proxy_score"] = out[
        "haptic_access_proxy_score"
    ].clip(lower=0, upper=1)

    out["score_method"] = (
        "unobstructed_approachable_shoreline_length_m / shoreline_length_m; "
        "approachable = gentle_slope OR beach_sand; "
        "unobstructed = approachable AND not barrier_affected"
    )

    out["bridge_used_in_score"] = 0

    # --------------------------------------------------------
    # Save outputs
    # --------------------------------------------------------
    osm_cols = [
        PARK_ID_FIELD,
        PARK_NAME_FIELD,
        MUNI_FIELD,
        "shoreline_length_m",
        "segment_count",

        "barrier_affected_segment_count",
        "barrier_affected_segment_ratio",
        "barrier_affected_shoreline_length_m",
        "barrier_affected_shoreline_ratio",
        "barrier_feature_count",
        "barrier_intersect_length_m",
        "has_barrier_near_shoreline",

        "bridge_affected_segment_count",
        "bridge_affected_segment_ratio",
        "bridge_affected_shoreline_length_m",
        "bridge_affected_shoreline_ratio",
        "bridge_feature_count",
        "bridge_intersect_length_m",
        "has_bridge_near_shoreline",

        "beach_sand_affected_segment_count",
        "beach_sand_segment_ratio",
        "beach_sand_affected_shoreline_length_m",
        "beach_sand_shoreline_ratio",
        "beach_sand_feature_count",
        "beach_sand_intersect_length_m",
        "has_beach_sand_near_shoreline",
    ]

    optional_final_cols = [
        "slope_threshold_percent",
        "slope_threshold_degrees",
        "slope_data_coverage_ratio",
    ]

    optional_final_cols = [
        c for c in optional_final_cols if c in out.columns
    ]

    final_cols = osm_cols + optional_final_cols + [
        "gentle_shoreline_ratio",
        "mean_shoreline_slope_degrees",

        "approachable_shoreline_length_m",
        "approachable_shoreline_ratio",
        "approachable_segment_count",
        "approachable_segment_ratio",

        "beach_sand_shoreline_length_m",
        "beach_sand_segment_count",

        "unobstructed_approachable_shoreline_length_m",
        "unobstructed_approachable_shoreline_ratio",
        "unobstructed_approachable_segment_count",
        "unobstructed_approachable_segment_ratio",

        "barrier_on_approachable_shoreline_length_m",
        "barrier_on_approachable_shoreline_ratio",
        "barrier_on_approachable_segment_count",
        "barrier_on_approachable_segment_ratio",

        "haptic_access_proxy_score",
        "score_method",
        "bridge_used_in_score",
    ]

    out[osm_cols].to_csv(OSM_PROXY_CSV, index=False)
    out[final_cols].to_csv(FINAL_HAPTIC_CSV, index=False)

    print("\nSaved OSM obstruction/beach proxy:")
    print(OSM_PROXY_CSV)

    print("\nSaved final DTM + OSM haptic proxy:")
    print(FINAL_HAPTIC_CSV)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------
    print("\nSummary:")
    print("Rows:", len(out))
    print("Parks with barriers:", int(out["has_barrier_near_shoreline"].sum()))
    print("Parks with bridges:", int(out["has_bridge_near_shoreline"].sum()))
    print("Parks with beach/sand:", int(out["has_beach_sand_near_shoreline"].sum()))
    print("Mean gentle shoreline ratio:", round(out["gentle_shoreline_ratio"].mean(), 4))
    print("Mean beach/sand shoreline ratio:", round(out["beach_sand_shoreline_ratio"].mean(), 4))
    print("Mean approachable shoreline ratio:", round(out["approachable_shoreline_ratio"].mean(), 4))
    print(
        "Mean unobstructed approachable shoreline ratio:",
        round(out["unobstructed_approachable_shoreline_ratio"].mean(), 4)
    )
    print(
        "Mean barrier affected shoreline ratio:",
        round(out["barrier_affected_shoreline_ratio"].mean(), 4)
    )
    print(
        "Mean barrier on approachable shoreline ratio:",
        round(out["barrier_on_approachable_shoreline_ratio"].mean(), 4)
    )
    print(
        "Mean haptic access proxy score:",
        round(out["haptic_access_proxy_score"].mean(), 4)
    )

    print("\nFirst 10 rows:")
    print(out[final_cols].head(10).to_string(index=False))

    print("\nDone.")


if __name__ == "__main__":
    main()
