# ============================================================
# 04_check_mapbox_missingness.py
# Compare temporal completeness with number of Mapbox cells
# ============================================================

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]

INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "mapbox"

qa_file = INTERIM_DIR / "mapbox_park_activity_qa_2023.csv"
counts_file = INTERIM_DIR / "mapbox_cell_counts_by_park_2023.csv"

qa = pd.read_csv(
    qa_file,
    dtype={"park_num": str}
)

counts = pd.read_csv(
    counts_file,
    dtype={"park_num": str}
)

check = qa.merge(
    counts,
    on="park_num",
    how="left"
)

check["coverage_pct"] = (
    check["temporal_records"] / 360 * 100
)

check = check.sort_values(
    ["coverage_pct", "mapbox_cell_count"]
)

print("\nLowest temporal coverage parks:\n")

print(
    check[
        [
            "park_num",
            "mapbox_cell_count",
            "temporal_records",
            "missing_temporal_records",
            "coverage_pct",
            "mean_activity"
        ]
    ]
    .head(30)
    .to_string(
        index=False
    )
)

print("\nCorrelation between cell count and temporal coverage:")

print(
    check[
        [
            "mapbox_cell_count",
            "temporal_records"
        ]
    ].corr()
)

print("\nCoverage summary:")

print(
    check["coverage_pct"].describe()
)
