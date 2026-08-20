# Urban blue-green accessibility

This repository contains the reproducible spatial-accessibility workflows and
analyses for two related studies:

- **Paper 3:** socioeconomic patterning of pedestrian, transit, combined
  physical, visual, haptic, and multidimensional access to 114 blue-green
  sites;
- **Paper 4:** Mapbox activity analysis using the validated Paper 3 site
  measures. Its former 20-minute results are archived locally and will be
  regenerated from the confirmed 10-minute handoff in the Paper 4 phase.

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
  scripts/
    accessibility_analysis/
      upstream/
        census/
        haptic/
        reach/
        viewshed/
    mapbox/                       # Paper 4
```

The entire `data/` folder is local-only and excluded from Git. Reproducibility
diagnostics are written to ignored `artifacts/`; private Word deliverables are
written to ignored `deliverables/`. Only scripts, documentation, and the
presentation-ready tables and PNG figures in `outputs/accessibility_analysis/` are intended
for GitHub. Paper 3 maps will be prepared manually in ArcGIS and inserted into
the private Word draft; no generated map is committed.
