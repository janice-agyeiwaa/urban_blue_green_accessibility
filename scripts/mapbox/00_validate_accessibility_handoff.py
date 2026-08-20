"""Validate the final Paper 3 scores and export the Paper 4 handoff table.

The script is read-only unless ``--write`` is supplied. It reconstructs the
accessibility scores from the canonical Paper 3 analysis input and
checks any existing Paper 4 handoff file against those reconstructed values.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACCESSIBILITY_INPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "accessibility_analysis"
    / "accessibility_analysis_by_catchment.csv"
)
PAPER4_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "paper4_handoff"
    / "all_114_sites_accessibility_scores.csv"
)

EXPECTED_WALKTIMES = {5, 10, 20, 30}
PAPER4_ACCESS_CATCHMENT_MIN = 10
SCORE_TOLERANCE = 1e-12


def minmax(series: pd.Series) -> pd.Series:
    minimum = series.min()
    maximum = series.max()
    if pd.isna(minimum) or pd.isna(maximum):
        return pd.Series(np.nan, index=series.index)
    if maximum == minimum:
        return pd.Series(0.0, index=series.index)
    return (series - minimum) / (maximum - minimum)


def assert_close(label: str, actual: pd.Series, expected: pd.Series) -> None:
    actual_values = pd.to_numeric(actual, errors="coerce").to_numpy()
    expected_values = pd.to_numeric(expected, errors="coerce").to_numpy()

    if not np.allclose(
        actual_values,
        expected_values,
        rtol=0,
        atol=SCORE_TOLERANCE,
        equal_nan=True,
    ):
        differences = np.abs(actual_values - expected_values)
        raise AssertionError(
            f"{label} does not reproduce; maximum absolute difference is "
            f"{np.nanmax(differences):.16g}."
        )


def load_and_validate_accessibility() -> pd.DataFrame:
    data = pd.read_csv(ACCESSIBILITY_INPUT, dtype={"park_num": str})

    required = {
        "park_num",
        "site_name",
        "municipality",
        "walktime_min",
        "access_points_per_km_boundary",
        "bus_stop_count",
        "visual_access_ratio_capped",
        "haptic_access_avery",
        "physical_access_score",
        "multidimensional_access_score",
    }
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Paper 3 input is missing fields: {missing}")

    walktimes = set(data["walktime_min"].dropna().astype(int))
    if walktimes != EXPECTED_WALKTIMES:
        raise ValueError(
            f"Expected walk times {sorted(EXPECTED_WALKTIMES)}, found "
            f"{sorted(walktimes)}."
        )

    counts = data.groupby("walktime_min")["park_num"].nunique()
    if not counts.eq(114).all():
        raise ValueError(f"Expected 114 sites at every walk time; found {counts.to_dict()}.")

    if data.duplicated(["park_num", "walktime_min"]).any():
        raise ValueError("Duplicate park/walk-time rows are present in Paper 3 input.")

    score_fields = [
        "access_points_per_km_boundary",
        "bus_stop_count",
        "visual_access_ratio_capped",
        "haptic_access_avery",
        "physical_access_score",
        "multidimensional_access_score",
    ]
    if data[score_fields].isna().any().any():
        raise ValueError("Paper 3 accessibility fields contain missing values.")

    reconstructed_groups = []
    for _, group in data.groupby("walktime_min", sort=False):
        check = group.copy()
        access_scaled = minmax(check["access_points_per_km_boundary"])
        bus_scaled = minmax(check["bus_stop_count"])
        physical = (access_scaled + bus_scaled) / 2
        multidimensional = (
            minmax(physical)
            + minmax(check["visual_access_ratio_capped"])
            + minmax(check["haptic_access_avery"])
        ) / 3

        assert_close(
            "physical_access_score",
            check["physical_access_score"],
            physical,
        )
        assert_close(
            "multidimensional_access_score",
            check["multidimensional_access_score"],
            multidimensional,
        )
        reconstructed_groups.append(check)

    return pd.concat(reconstructed_groups, ignore_index=True)


def build_paper4_handoff(data: pd.DataFrame) -> pd.DataFrame:
    handoff = (
        data.loc[data["walktime_min"].eq(PAPER4_ACCESS_CATCHMENT_MIN)]
        .rename(
            columns={
                "visual_access_ratio_capped": "visible_water_ratio",
                "haptic_access_avery": "shoreline_length_to_perimeter_ratio",
            }
        )[
            [
                "park_num",
                "site_name",
                "municipality",
                "walktime_min",
                "physical_access_score",
                "visible_water_ratio",
                "shoreline_length_to_perimeter_ratio",
                "multidimensional_access_score",
            ]
        ]
        .copy()
    )
    handoff["park_num_numeric"] = pd.to_numeric(handoff["park_num"])
    return (
        handoff.sort_values("park_num_numeric")
        .drop(columns="park_num_numeric")
        .reset_index(drop=True)
    )


def validate_existing(expected: pd.DataFrame) -> None:
    if not PAPER4_OUTPUT.exists():
        print(f"No existing handoff file to compare: {PAPER4_OUTPUT}")
        return

    existing = pd.read_csv(PAPER4_OUTPUT, dtype={"park_num": str})
    if existing.columns.tolist() != expected.columns.tolist():
        raise AssertionError("Existing Paper 4 handoff columns do not match the canonical export.")

    merged = expected.merge(
        existing,
        on="park_num",
        how="outer",
        suffixes=("_expected", "_existing"),
        indicator=True,
        validate="one_to_one",
    )
    if not merged["_merge"].eq("both").all():
        raise AssertionError("Existing Paper 4 handoff does not contain the same 114 sites.")

    for field in [
        "physical_access_score",
        "visible_water_ratio",
        "shoreline_length_to_perimeter_ratio",
        "multidimensional_access_score",
    ]:
        assert_close(
            field,
            merged[f"{field}_existing"],
            merged[f"{field}_expected"],
        )

    for field in ["site_name", "municipality"]:
        if not merged[f"{field}_existing"].fillna("").eq(
            merged[f"{field}_expected"].fillna("")
        ).all():
            raise AssertionError(f"Existing handoff has mismatched {field} values.")

    print(
        "Existing Paper 4 handoff matches the final Paper 3 "
        f"{PAPER4_ACCESS_CATCHMENT_MIN}-minute scores."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the validated 114-site Paper 4 handoff CSV.",
    )
    args = parser.parse_args()

    accessibility = load_and_validate_accessibility()
    handoff = build_paper4_handoff(accessibility)

    if args.write:
        PAPER4_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        handoff.to_csv(PAPER4_OUTPUT, index=False)
        print(f"Wrote validated Paper 4 handoff: {PAPER4_OUTPUT}")
        validate_existing(handoff)
    else:
        validate_existing(handoff)
        print("Validation passed. Re-run with --write to recreate the handoff file.")

    print(f"Sites: {len(handoff)}")
    print(
        "Paper 4 accessibility uses the Paper 3 "
        f"{PAPER4_ACCESS_CATCHMENT_MIN}-minute catchment scores."
    )


if __name__ == "__main__":
    main()
