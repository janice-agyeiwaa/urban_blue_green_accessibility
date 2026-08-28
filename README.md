# Urban blue-green accessibility

This repository contains the reproducible spatial-accessibility workflows and
analyses for two related studies:

- **Paper 3:** socioeconomic patterning of pedestrian, transit, combined
  physical, visual, haptic, and multidimensional access to 114 blue-green
  sites;
- **Paper 4:** spatially filtered mixed-effects analysis of 2023 Mapbox
  waterfront activity using the validated Paper 3 10-minute accessibility
  measures and a matching 10-minute population-density control.

## Run Paper 3

The main analysis defaults to the requested 10-minute catchment and evaluates
5, 20, and 30 minutes as sensitivity analyses:

```powershell
Rscript scripts/accessibility_analysis/run_all.R
```

To change the main reporting catchment without editing code:

```powershell
Rscript scripts/accessibility_analysis/run_all.R --main-catchment=20 --k=6
```

Operational details and fixed analysis rules are in
`docs/accessibility_workflow.md`; the final analytical definitions are in
`docs/accessibility_methodology.md`.

The GitHub documentation also includes `docs/reach_workflow.md`,
`docs/viewshed_workflow.md`, `docs/haptic_workflow.md`, and
`docs/decisions_log.md`. Internal cleanup, audit, supervisor-update, and
repository-planning notes remain local and are Git-ignored.

## Run Paper 4

Paper 4 reuses the completed Mapbox activity extraction and does not repeat the
large raw-data step:

```powershell
Rscript scripts/mapbox/run_all.R
```

The analytical definitions and results are documented in
`docs/mapbox_methodology.md`; the run order and quality gates are in
`docs/mapbox_workflow.md`.

## Repository structure

```text
urban_blue_green_accessibility/
  data/
    raw/
    interim/
    processed/
      accessibility_analysis/
      paper4_handoff/
      mapbox/
  docs/
  outputs/
    accessibility_analysis/
    mapbox/
  scripts/
    accessibility_analysis/
      upstream/
        census/
        haptic/
        reach/
        viewshed/
    mapbox/                       # Paper 4
```

The entire `data/` folder is local-only and excluded from Git. The private-data
handoff and the boundary between end-to-end and analytical reproducibility are
documented in `docs/data_reproducibility.md`. Reproducibility diagnostics are
written to ignored `artifacts/`; private Word deliverables are written to
ignored `deliverables/`. Only scripts, documentation, and the presentation-ready
tables and PNG figures under `outputs/` are intended for
GitHub. Paper 3 maps are prepared manually in ArcGIS and inserted into the
private Word draft; no generated map is committed.
