# Urban Blue-Green Accessibility Workflow

This repository rebuilds accessibility workflows for the urban blue-green spaces project using Python-based spatial analysis.

## Current focus

The current focus is the **reach access workflow**.

Reach access is being rebuilt from spatial inputs using:

- edited land buffer polygons
- OpenStreetMap walking network data downloaded with OSMnx
- Python spatial processing with GeoPandas and Shapely

## Data structure
```text
urban_blue_green_accessibility/
  data/
    raw/
      Park_Extraction_Project.gdb
    interim/
      reach/
    processed/
      reach/

  scripts/
    reach/
      01_create_candidate_access_points.py
      02_clean_candidate_access_points.py

  docs/
    reach_workflow.md
    decision_log.md
    archive/

  outputs/
    maps/
    tables/