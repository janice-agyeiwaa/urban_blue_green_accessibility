# Paper 3 workflow

## Purpose

This is the operational guide for rebuilding and checking Paper 3. It replaces
the earlier sequence of console commands and numbered exploratory regression
scripts with one traceable path.

```text
Raw spatial workflows
        |
        v
accessibility_site_metrics_114.csv   site_metadata_114.csv
        |                                  |
        +----------------+-----------------+
                         |
2021 Census walk-time table
                         |
                         v
       accessibility_analysis_by_catchment.csv
                         |
                         v
       QA -> OLS Moran test -> OLS/SAR selection
                         |
                         v
       baseline + site-controlled models
                         |
                         v
       tables, diagnostics, and figures
```

## Environments

Routine statistical reruns use R. The required packages are `readr`, `dplyr`,
`stringr`, `ggplot2`, `spdep`, `spatialreg`, and `sandwich`.

The upstream spatial builders use the ArcGIS Pro environment installed at:

```text
C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe
```

ArcPy also needs an initialized ArcGIS Pro licence. Both this executable and
Esri's `propy.bat` wrapper are present, but a test from the ordinary Codex
PowerShell session returned `The Product License has not been initialized`.
The path is therefore valid, but this shell is not currently licensed to run
ArcPy. Sign in/start ArcGIS Pro and run the upstream commands from the **ArcGIS
Pro Python Command Prompt** (or another ArcGIS Pro-licensed session):

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat" `
  scripts/accessibility_analysis/upstream/00_build_accessibility_site_metrics.py

& "C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat" `
  scripts/accessibility_analysis/upstream/01_build_site_metadata.py
```

If `propy.bat` still reports the licence error there, confirm that ArcGIS Pro
opens under the signed-in account and that its licence is available before
regenerating the two processed site files. Routine R model reruns do not need
ArcPy or an ArcGIS licence.

## Normal Paper 3 run

The processed 114-site spatial inputs are already present, so most reruns only
need this command from the repository root:

```powershell
Rscript scripts/accessibility_analysis/run_all.R
```

This uses 10 minutes for the main reported table and figures and evaluates 5,
10, 20, and 30 minutes in the sensitivity analysis.

The runner also executes `05_run_haptic_sensitivity.R`. That script compares
the primary shoreline-to-perimeter haptic measure with the exploratory DTM-OSM
unobstructed-approachability proxy. It uses the same 10-minute regression
sample (N = 105), predictors, controls, seven-nearest-neighbour weights, and
model-selection rule as the main analysis. The proxy does not replace the
primary haptic component or alter the Paper 4 accessibility handoff.

To switch the main reporting catchment without editing source code:

```powershell
Rscript scripts/accessibility_analysis/run_all.R --main-catchment=20 --k=6
```

`--k=6` is the requested minimum, not a promise that six neighbours will be
used. The workflow finds the smallest single k that connects every analytical
sample. The current data require k=7, which is then used consistently.

## Active scripts

### `scripts/accessibility_analysis/01_run_accessibility_models.R`

This script:

1. joins site accessibility metrics to the four Census catchments;
2. reconstructs pedestrian, transit, combined physical, visual, haptic, and
   multidimensional scores;
3. applies the same Census-quality rule to every catchment;
4. joins site type, land-buffer area, and representative coordinates;
5. standardizes regression variables within each analytical sample;
6. checks spatial-weights connectivity;
7. fits OLS, SAR lag, and SAR error baseline candidates;
8. selects the model family using residual Moran's I and AIC;
9. starts the controlled model with the baseline family for comparability;
10. reselects the controlled family when that model still has residual spatial
    autocorrelation; and
11. exports unrounded tables, model diagnostics, FDR results, VIF, SAR-lag
    impacts, and sensitivity results.

### `scripts/accessibility_analysis/02_make_accessibility_figures.R`

This creates:

- the single-colour Physical–Visual–Haptic pairwise figure with Pearson and
  Spearman correlations, p-values, n, dashed median lines, and horizontal
  background gridlines;
- site-level and aggregate median-based quadrant tables and a presentation-ready
  quadrant scatterplot with median lines, no grid, and in-panel count legends;
- spider profiles for the six most divergent sites; and
- the six-outcome controlled coefficient figure, including multidimensional
  access.

### `scripts/accessibility_analysis/03_build_methods_results_docx.py`

This builds the private `deliverables/Paper_3_Methods_and_Results_2.0.docx`
after the analysis finishes. It reads the canonical tables, PNG figures, and
site inventory; it does not rerun any model. The deliverable is Git-ignored and
contains a placeholder for the manually prepared ArcGIS accessibility maps.

### `scripts/accessibility_analysis/04_export_arcgis_map_layer.R`

This creates a local 114-row CSV and a GeoPackage containing both polygon and
representative-point layers for the selected catchment. The export includes
pedestrian, transit, physical, visual, haptic, and multidimensional scores and
is intended for manual ArcGIS map production. It is written under ignored
`data/processed/accessibility_analysis/` and is not uploaded to GitHub.

### `scripts/accessibility_analysis/05_run_haptic_sensitivity.R`

This compares the primary shoreline-to-perimeter haptic measure with the
exploratory DTM-OSM unobstructed-approachability proxy. It exports the
measure-correlation figure, the controlled socioeconomic comparison, site
controls, and model diagnostics for the 10-minute sample.

### `scripts/accessibility_analysis/run_all.R`

This calls the model, figure, and haptic-sensitivity scripts in order and forwards catchment and k
arguments as appropriate. The private Word document and manual ArcGIS map are
deliberately kept outside this public analysis runner.

## Stable inputs

- `data/processed/accessibility_analysis/accessibility_site_metrics_114.csv`
- `data/processed/accessibility_analysis/site_metadata_114.csv`
- `data/processed/census/ubs_census_by_walktime.csv`

The two Paper 3 site files are the boundary between spatial preprocessing and
statistical modelling. They should be regenerated only when an upstream reach,
transit, viewshed, haptic, site-boundary, or site-type input changes.

## Main outputs to review

- `outputs/accessibility_analysis/tables/table2_10min_full_regression.md`
- `outputs/accessibility_analysis/tables/table3_10min_site_controls.csv`
- `outputs/accessibility_analysis/tables/table4_controlled_catchment_sensitivity.csv`
- `outputs/accessibility_analysis/tables/table6_10min_multiple_testing.csv`
- `outputs/accessibility_analysis/tables/table7_10min_model_diagnostics.csv`
- `outputs/accessibility_analysis/tables/table8_10min_haptic_sensitivity.csv`
- `outputs/accessibility_analysis/tables/table8b_10min_haptic_model_diagnostics.csv`
- `outputs/accessibility_analysis/tables/table8c_10min_haptic_sensitivity_site_controls.csv`
- `outputs/accessibility_analysis/tables/tableS5_10min_haptic_measure_correlation.csv`
- `outputs/accessibility_analysis/tables/table5b_10min_quadrant_summary.csv`
- `outputs/accessibility_analysis/tables/tableS4_10min_quadrant_classifications.csv`
- `outputs/accessibility_analysis/figures/figure2_10min_pairwise_accessibility.png`
- `outputs/accessibility_analysis/figures/figure2b_10min_quadrant_classification.png`
- `outputs/accessibility_analysis/figures/figure3_10min_extreme_site_profiles.png`
- `outputs/accessibility_analysis/figures/figure4_10min_accessibility_composition.png`
- `outputs/accessibility_analysis/figures/figure5_10min_controlled_coefficients.png`
- `outputs/accessibility_analysis/figures/figure6_10min_haptic_sensitivity.png`

Detailed diagnostics, candidate comparisons, raw coefficients, and run
metadata are written to ignored `artifacts/accessibility_analysis/` rather than the public
output package.

Only PNG figure exports are retained. The accessibility maps are prepared in
ArcGIS by updating the original layout to the 10-minute catchment and are
inserted into the marked Word placeholder.

## Expected QA results

With the current inputs:

| Catchment | Final regression N |
|---:|---:|
| 5 minutes | 90 |
| 10 minutes | 105 |
| 20 minutes | 112 |
| 30 minutes | 114 |

The main 10-minute controlled families should be SAR lag for pedestrian and
visual, SAR error for transit, combined physical, and multidimensional access,
and OLS for haptic. All six main controlled models should have residual Moran
p-values above .05. The maximum design-matrix VIF should remain below five; it
is currently 2.83.

If these checks change after an upstream update, treat the change as a result
to investigate rather than overwriting the report silently.

## What changed from the exploratory chat workflow

- **Console state removed:** `df_control`, `park_centroids`, and overwritten
  model objects are no longer required. Every input is loaded from a saved,
  documented file.
- **Sample corrected:** the exploratory 10-minute work used N=108. Don Roberts
  Park, Lowry Lane, and Davidson's Pool have critical zero-income Census
  estimates, so the final consistent sample is N=105.
- **Spatial representation fixed:** the old chat alternated between objects
  called centroids and `park_points_for_morans.csv`. The final metadata uses
  ArcGIS `FeatureToPoint(..., "INSIDE")` representative points and calls them
  representative points, not centroids.
- **Weights corrected:** k=6 is disconnected for the complete 30-minute sample.
  The smallest common connected specification is k=7.
- **Catchment generalized:** one argument changes the main report; all four
  catchments are always evaluated under the same rules.
- **Inference strengthened:** OLS uses HC3 robust errors, SAR-lag impacts are
  exported, and Benjamini–Hochberg FDR is reported for the 30 main controlled
  socioeconomic tests.
- **Controlled spatial failures resolved:** the controlled multidimensional OLS
  and selected sensitivity models are automatically reselected instead of
  relying on a single console Moran result.
- **Proposal decision implemented:** multidimensional access is a main Paper 3
  outcome and the 10-minute score is the formal Paper 4 accessibility handoff.

## Archiving rule

The old numbered scripts and cached regression outputs are in
`archive/paper3_legacy_20260820/`. Do not copy code back into the active
workflow. If a useful legacy sensitivity is revived, rebuild it under
`scripts/accessibility_analysis/` using the current sample, spatial points, and catchment rules.
