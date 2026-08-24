# Paper 4 Mapbox Workflow

## Reproduce the analysis

From the repository root, run:

```powershell
Rscript scripts/mapbox/run_all.R
```

The complete run uses processed Mapbox activity and local Enrich layers. It
does not repeat the large raw Mapbox extraction and does not spend ArcGIS
credits.

## Canonical scripts

1. `01_build_analysis_dataset.R`
   - validates the Paper 3 handoff against the canonical 10-minute scores;
   - reads the completed 2023 Mapbox activity extraction;
   - calculates 10- and 20-minute population density from the Enrich polygons;
   - treats `HasData = 0` as missing; and
   - exports the canonical model dataset and sample audit.
2. `02_run_mixed_models.R`
   - fits the ordinary random-intercept models;
   - runs coverage, population-density, site-type, and outcome-scale checks;
   - documents residual skewness and site-level spatial autocorrelation.
3. `03_run_spatial_filtering.R`
   - fits the four primary RE-ESF models; and
   - verifies that residual spatial autocorrelation has been removed.
4. `04_run_spatial_sensitivities.R`
   - applies the same spatial filtering to every sensitivity specification.
5. `05_make_outputs.R`
   - creates presentation-ready tables and PNG figures.

The original large-file inspection, cell matching, activity extraction, and
coverage scripts are retained under `scripts/mapbox/upstream/`. They are not
part of the normal analysis rerun because their stable processed outputs
already exist. Superseded test and modelling scripts are stored locally under
`archive/mapbox_legacy_2026-08-24/` and are not committed.

## Stable local inputs

- `data/processed/mapbox/mapbox_park_hourly_activity_2023.csv`
- `data/interim/mapbox/mapbox_temporal_coverage_summary_2023.csv`
- `data/processed/paper4_handoff/all_114_sites_accessibility_scores.csv`
- `data/processed/accessibility_analysis/accessibility_analysis_by_catchment.csv`
- `data/processed/accessibility_analysis/site_metadata_114.csv`
- `data/interim/census/census_enrich_prep.gdb/pop_den_10min`
- `data/interim/census/census_enrich_prep.gdb/pop_den_20min`

The complete `data/` directory remains local and is not uploaded to GitHub.

## Generated locations

- canonical local dataset: `data/processed/mapbox/mapbox_model_dataset.csv`;
- detailed diagnostics and model objects: `artifacts/mapbox/`;
- public tables and figures: `outputs/mapbox/`.

Only the scripts, documentation, and presentation-ready `outputs/mapbox/`
files are intended for GitHub.

## Analytical samples

| Specification | Waterfronts | Observations |
|---|---:|---:|
| Mapbox activity available | 103 | 32,472 |
| Primary 10-minute population complete case | 98 | 30,946 |
| At least 90% temporal coverage | 76 | 27,013 |
| 20-minute population-density sensitivity | 103 | 32,472 |

## Quality gates

A successful run must confirm:

- exactly 114 validated Paper 3 handoff rows at 10 minutes;
- exactly 103 waterfronts and 32,472 observations before model exclusions;
- primary and high-coverage samples of 98 and 76 waterfronts;
- no missing accessibility, site-type, area, or coordinate values;
- `HasData = 0` population values are not interpreted as zero population;
- all primary RE-ESF residual Moran p-values are at least .05; and
- the public tables and figures regenerate without manual editing.
