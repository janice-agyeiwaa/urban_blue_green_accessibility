from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


# ============================================================
# 18_generate_paper4_workflow_figure.py
#
# Purpose:
# Create the analytical workflow figure for Paper 4:
# accessibility -> Mapbox activity -> analytical sample ->
# mixed-effects models -> sensitivity analyses
# ============================================================


PROJECT_ROOT = Path(
    r"C:\Users\owusu\Desktop\work\under_lab\urban_blue_green_accessibility"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "mapbox"
    / "workflow"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------------
# Figure setup
# ------------------------------------------------------------

fig, ax = plt.subplots(
    figsize=(11, 14)
)

ax.set_xlim(0, 10)
ax.set_ylim(0, 16)
ax.axis("off")


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def add_box(
    x,
    y,
    width,
    height,
    title,
    text,
    title_size=11,
    text_size=9.5
):

    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.04",
        linewidth=1.2,
        fill=False
    )

    ax.add_patch(box)

    ax.text(
        x + width / 2,
        y + height * 0.68,
        title,
        ha="center",
        va="center",
        fontsize=title_size,
        fontweight="bold"
    )

    ax.text(
        x + width / 2,
        y + height * 0.34,
        text,
        ha="center",
        va="center",
        fontsize=text_size,
        wrap=True
    )


def arrow(
    x1,
    y1,
    x2,
    y2
):

    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="->",
            linewidth=1.3
        )
    )


# ------------------------------------------------------------
# 1. Study sites
# ------------------------------------------------------------

add_box(
    2,
    14.3,
    6,
    1.1,
    "Metro Vancouver waterfront sites",
    "114 urban blue-green waterfront sites"
)


# ------------------------------------------------------------
# 2. Accessibility measures
# ------------------------------------------------------------

add_box(
    1.3,
    12.3,
    7.4,
    1.3,
    "Accessibility measures",
    "Multidimensional accessibility = primary predictor\n"
    "Physical • Visual • Haptic = dimension-specific predictors"
)

arrow(
    5,
    14.3,
    5,
    13.6
)


# ------------------------------------------------------------
# 3. Mapbox activity
# ------------------------------------------------------------

add_box(
    1.3,
    10.2,
    7.4,
    1.3,
    "Mapbox activity data",
    "2023 Mapbox Movement activity extracted for grid-cell centroids within site extraction areas"
)

arrow(
    5,
    12.3,
    5,
    11.5
)


# ------------------------------------------------------------
# 4. Temporal processing
# ------------------------------------------------------------

add_box(
    1.3,
    8.1,
    7.4,
    1.4,
    "Temporal classification and coverage assessment",
    "Day type: weekday / weekend\n"
    "Time of day: morning / afternoon / evening\n"
    "Season: winter / spring / summer / fall\n"
)

arrow(
    5,
    10.2,
    5,
    9.5
)


# ------------------------------------------------------------
# 5. Analytical sample
# ------------------------------------------------------------

add_box(
    1.3,
    6.2,
    7.4,
    1.2,
    "Main analytical sample",
    "103 sites with usable Mapbox activity data\n"
    "32,472 site-time observations"
)

arrow(
    5,
    8.1,
    5,
    7.4
)


# ------------------------------------------------------------
# 6. Covariates
# ------------------------------------------------------------

add_box(
    0.3,
    4.1,
    4.3,
    1.35,
    "Temporal covariates",
    "Day type\n"
    "Time of day\n"
    "Season"
)

add_box(
    5.4,
    4.1,
    4.3,
    1.35,
    "Site-level covariates",
    "Site type\n"
    "Log land area\n"
    "Log 20-min population density"
)

arrow(
    4.2,
    6.2,
    2.5,
    5.45
)

arrow(
    5.8,
    6.2,
    7.5,
    5.45
)


# ------------------------------------------------------------
# 7. Mixed-effects model
# ------------------------------------------------------------

add_box(
    1.3,
    2.1,
    7.4,
    1.3,
    "Mixed-effects regression",
    "Mapbox site activity index as outcome\n"
    "Repeated temporal observations nested within sites\n"
    "Random intercept for waterfront site"
)

arrow(
    2.5,
    4.1,
    4.3,
    3.4
)

arrow(
    7.5,
    4.1,
    5.7,
    3.4
)


# ------------------------------------------------------------
# 8. Models + sensitivity
# ------------------------------------------------------------

add_box(
    0.3,
    0.2,
    4.5,
    1.2,
    "Accessibility models",
    "Primary: multidimensional accessibility\n"
    "Dimension-specific: physical, visual, haptic"
)

add_box(
    5.2,
    0.2,
    4.5,
    1.2,
    "Sensitivity analyses",
    "≥90% temporal coverage:\n"
    "78 sites / 27,706 observations\n"
    "Alternative site-type specifications"
)

arrow(
    4.3,
    2.1,
    2.6,
    1.4
)

arrow(
    5.7,
    2.1,
    7.4,
    1.4
)


# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

fig.tight_layout()

PNG_FILE = (
    OUTPUT_DIR
    / "figure_paper4_analysis_workflow.png"
)

PDF_FILE = (
    OUTPUT_DIR
    / "figure_paper4_analysis_workflow.pdf"
)

fig.savefig(
    PNG_FILE,
    dpi=300,
    bbox_inches="tight"
)

fig.savefig(
    PDF_FILE,
    bbox_inches="tight"
)

plt.close(fig)


print("\nWorkflow figure created:")
print(PNG_FILE)
print(PDF_FILE)

print("\nDone.")