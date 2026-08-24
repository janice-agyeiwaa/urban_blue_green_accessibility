# ============================================================
# 05_summarize_mapbox_coverage.py
#
# Purpose:
# Summarize temporal coverage for Mapbox activity by park
# ============================================================

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]

INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "mapbox"

QA_FILE = INTERIM_DIR / "mapbox_park_activity_qa_2023.csv"
COUNTS_FILE = INTERIM_DIR / "mapbox_cell_counts_by_park_2023.csv"

OUTPUT_FILE = INTERIM_DIR / "mapbox_temporal_coverage_summary_2023.csv"

# ------------------------------------------------------------
# Read inputs
# ------------------------------------------------------------

qa = pd.read_csv(
    QA_FILE,
    dtype={"park_num": str}
)

counts = pd.read_csv(
    COUNTS_FILE,
    dtype={"park_num": str}
)

df = qa.merge(
    counts,
    on="park_num",
    how="left"
)

# ------------------------------------------------------------
# Calculate coverage
# ------------------------------------------------------------

df["coverage_pct"] = (
    df["temporal_records"] / 360 * 100
)

# ------------------------------------------------------------
# Assign coverage categories
# ------------------------------------------------------------

def coverage_group(x):
    if x >= 90:
        return ">=90%"
    elif x >= 75:
        return "75-<90%"
    elif x >= 50:
        return "50-<75%"
    else:
        return "<50%"

df["coverage_group"] = df["coverage_pct"].apply(
    coverage_group
)

# ------------------------------------------------------------
# Sort parks
# ------------------------------------------------------------

df["park_num_numeric"] = pd.to_numeric(
    df["park_num"],
    errors="coerce"
)

df = (
    df
    .sort_values(
        ["coverage_pct", "park_num_numeric"]
    )
    .drop(columns="park_num_numeric")
)

# ------------------------------------------------------------
# Print overall category summary
# ------------------------------------------------------------

category_order = [
    ">=90%",
    "75-<90%",
    "50-<75%",
    "<50%"
]

summary = (
    df["coverage_group"]
    .value_counts()
    .reindex(
        category_order,
        fill_value=0
    )
)

print("\n" + "=" * 55)
print("MAPBOX TEMPORAL COVERAGE SUMMARY")
print("=" * 55)

print("\nNumber of parks in each coverage category:\n")

for category, count in summary.items():
    print(
        f"{category}: {count} parks"
    )

# ------------------------------------------------------------
# Print parks in each group
# ------------------------------------------------------------

for category in category_order:

    subset = df[
        df["coverage_group"] == category
    ]

    print("\n" + "-" * 55)
    print(f"{category} COVERAGE")
    print("-" * 55)

    if subset.empty:
        print("None")
    else:
        print(
            subset[
                [
                    "park_num",
                    "mapbox_cell_count",
                    "temporal_records",
                    "missing_temporal_records",
                    "coverage_pct",
                    "mean_activity"
                ]
            ].to_string(
                index=False,
                formatters={
                    "coverage_pct": "{:.1f}".format,
                    "mean_activity": "{:.6f}".format
                }
            )
        )

# ------------------------------------------------------------
# Extra counts for possible thresholds
# ------------------------------------------------------------

print("\n" + "=" * 55)
print("POSSIBLE COVERAGE THRESHOLDS")
print("=" * 55)

for threshold in [50, 75, 80, 90, 95]:

    retained = (
        df["coverage_pct"] >= threshold
    ).sum()

    excluded = len(df) - retained

    print(
        f"\nIf minimum coverage = {threshold}%:"
    )

    print(
        f"  retained = {retained} parks"
    )

    print(
        f"  excluded = {excluded} parks"
    )

# ------------------------------------------------------------
# Save detailed output
# ------------------------------------------------------------

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nDetailed coverage table saved to:")
print(OUTPUT_FILE)

print("\nDone.")
