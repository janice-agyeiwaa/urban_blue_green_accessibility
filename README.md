## Project Purpose

The project examines how public waterfront and blue-green spaces are accessed and used. It builds on existing GIS work and layers completed in ArcGIS Pro and aims to make parts of the workflow more reproducible using Python.

The main purpose of this repository is to:

- organize and document the project workflow
- automate repeatable data extraction and cleaning steps
- validate existing processed GIS layers
- prepare clean accessibility tables for statistical analysis
- track decisions, issues, and assumptions clearly

This repository does not currently recreate all original GIS processing from scratch. Instead, it uses Avery’s processed GIS layers as inputs and automates extraction, checking, and preparation of analysis-ready outputs.


The core processed accessibility layers include:

- `allparks_land_buffer_reachvariables`
- `allparks_land_buffer_hapticvariables`
- visual/viewshed outputs to be reviewed
- Census extraction/enrichment outputs to be reviewed
- Mapbox activity outputs to be reviewed

Initial checks showed that the reach and haptic layers both contain 114 unique records and match by:

- `park_num`
- `PARK_NAME`
- `MUNI`

Therefore, `park_num` is treated as the main linking field between the current reach and haptic layers.

## Repository Structure

```text
urban_blue_green_accessibility/
├── data/
│   ├── raw/          # Local copies of selected project data; not committed
│   ├── interim/      # Working/intermediate outputs; not committed
│   ├── processed/    # Final processed datasets; not committed
│   └── metadata/     # Data inventories and field summaries
├── docs/
│   ├── summary_notes.md
│   ├── workflow_notes.md
│   └── decisions_log.md
├── outputs/
│   ├── tables/       # CSV tables and summary outputs
│   ├── maps/         # Exported maps
│   └── figures/      # Charts and figures
├── scripts/
│   ├── reach.py      # Reach/physical access workflow
│   ├── haptic.py     # Haptic/touch access workflow
│   └── week1.py      # Week-specific reproduction/checking script
├── README.md
└── .gitignore