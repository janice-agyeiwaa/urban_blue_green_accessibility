# Viewshed Workflow

## Goal

Rebuild the visual accessibility workflow for the blue-green spaces project.

The visual accessibility question is:

How visible is water from realistic public viewing locations within the waterfront land buffer?

This workflow will begin with the same 10 pilot parks used in the reach workflow, then later scale up if the method works well.

---

## Current Viewshed Direction

Avery’s previous workflow used random observer points inside the land buffer and ran Geodesic Viewshed in ArcGIS Pro using DSM data.

For this rebuild, the initial focus is improving observer-point placement.

Instead of placing observer points randomly, the pilot workflow will generate observer points along walkable paths/corridors inside each land buffer.

---

## Base Layers

### Observer area

- Layer: `allparks_land_buffer`
- Reason: Observer points should represent people viewing water from the accessible waterfront land area, not from the full park polygon or from the water.

### Candidate viewing corridors

- Source: OSM walkable network downloaded with OSMnx
- Method: Clip OSM walkable paths to each pilot land buffer.

### Visible target

- Water buffer, shoreline, or water polygon layer
- Final target layer still needs to be confirmed before viewshed calculation.

### Elevation surface

- DSM raster
- Final DSM source/preparation still needs to be confirmed.

---

## Initial Pilot Parks

The viewshed workflow will use the same 10 pilot parks selected from the reach workflow.

Input:

- `data/processed/reach/pilot_10_parks.csv`

Reason:

Using the same pilot parks keeps the workflow manageable and allows observer-point generation, DSM processing, and visible-water calculations to be tested before scaling to all 114 parks.

---

## Step 1: Summarize Pilot Land Buffers and Walkable Paths

**Script:**  
`scripts/viewshed/01_summarize_pilot_land_buffers.py`

### Purpose

Before generating observer points, summarize each pilot land buffer to understand:

- land-buffer area;
- land-buffer perimeter;
- OSM walkable path length inside the buffer;
- whether each park has enough walkable path data for observer placement.

### Method

1. Read `allparks_land_buffer`.
2. Filter to the 10 pilot parks.
3. Download OSM walking network around each pilot land buffer.
4. Clip OSM walkable paths to the land buffer.
5. Calculate total OSM path length inside each land buffer.
6. Estimate how many observer points fixed spacing would produce.

### Output

- `data/interim/viewshed/pilot_10_land_buffer_path_summary.csv`

### Notes

This pre-check showed that pilot parks vary greatly in land-buffer size and OSM path length. Therefore, a fixed spacing rule alone may over-sample large parks and under-sample small parks.

---

## Step 2: Path-Based Observer Point Generation

**Planned script:**  
`scripts/viewshed/02_generate_path_observer_points.py`

### Purpose

Generate realistic observer points along walkable paths inside each pilot land buffer.

The goal is to keep the number of observers comparable across parks while placing them in locations where people are more likely to stand or walk.

### Planned method

For each pilot park:

1. Download OSM walkable network around the land buffer.
2. Clip OSM walkable paths to the land buffer.
3. Generate candidate observer points along all clipped path segments.
4. Calculate each candidate point’s distance to the water/shoreline.
5. Cluster candidate points into 3 spatial groups.
6. Select one observer point from each cluster.
7. Where possible, selected points should represent different parts of the buffer and different distances from water.
8. If no OSM paths exist inside the buffer, create fallback observer points inside the land buffer and flag them.

### Planned outputs

- `data/interim/viewshed/pilot_10_clipped_osm_paths.gpkg`
- `data/interim/viewshed/pilot_10_candidate_observer_points.gpkg`
- `data/processed/viewshed/pilot_10_observer_points.gpkg`
- `data/interim/viewshed/pilot_10_observer_point_log.csv`

### Output layers for visual QA

The workflow will save intermediate spatial layers so the method can be checked visually:

1. **Clipped OSM paths**
   - Shows the walkable paths/corridors inside each land buffer.

2. **Candidate observer points**
   - Shows all possible path-based observer locations before selection.

3. **Clustered candidate points**
   - Shows which spatial cluster each candidate belongs to.

4. **Final observer points**
   - Shows the 3 selected observer points per park.

5. **Fallback observer points**
   - Clearly flagged where path-based observer generation was not possible.

---

## Why Use Clustering?

Simple random points may fall in unrealistic or inaccessible locations.

Fixed spacing along paths can over-sample large parks and under-sample small parks.

A simple 25%, 50%, and 75% method works well for one continuous path, but may not work well when a park has multiple disconnected paths.

Clustering is used because it can select observer points that are spatially spread across all available walkable paths without pretending disconnected paths are one continuous route.

---

## Current Observer Strategy

The pilot observer strategy is:

- Use 3 observer points per park.
- Place observers on walkable paths/corridors inside the land buffer.
- Use clustering to spread observer points across the accessible waterfront area.
- Record fallback cases clearly.
- Use the same observer count per park to keep sites comparable.

---

## Next Steps

1. Generate clipped OSM paths for the 10 pilot parks.
2. Generate candidate observer points along the clipped paths.
3. Cluster candidate points into 3 groups per park.
4. Select final observer points.
5. Visually QA observer points before running viewshed.
6. Confirm DSM and visible-water target layer.


## Observer point generation result

The path-based observer point workflow successfully generated 3 observer points for each of the 10 pilot parks, giving 30 observer points total.

All final observer points were selected from OSM walkable paths clipped to the land buffer. No fallback polygon-based observer points were needed for the pilot parks.

Outputs:
- `data/interim/viewshed/pilot_10_raw_osm_walk_paths.gpkg`
- `data/interim/viewshed/pilot_10_clipped_osm_paths.gpkg`
- `data/interim/viewshed/pilot_10_candidate_observer_points.gpkg`
- `data/interim/viewshed/pilot_10_candidate_observer_points_clustered.gpkg`
- `data/processed/viewshed/pilot_10_observer_points.gpkg`
- `data/interim/viewshed/pilot_10_observer_point_log.csv`


## DSM and Visible-Water Target

The DSM input for the viewshed workflow is:

- `data/raw/dsm.tif`

The DSM has approximately 1 m cell size, 32-bit float pixel type, and uses NAD 1983 CSRS UTM Zone 10N.

The visible-water target is:

- `data/raw/LCC2020_wateronot.tif`

This raster is a binary water/not-water layer where:

- `0` = not water
- `1` = water

Visible water is calculated using:

`viewshed > 0 AND LCC2020_wateronot == 1`

This means the final visible-water area includes water cells visible from at least one observer point.

## Prepared Viewshed Inputs

The DSM was exported locally as `data/raw/dsm.tif`.

The final path-based observer points were projected to match the DSM coordinate system.

Prepared output:
- `data/processed/viewshed/viewshed_inputs.gdb/pilot_10_observer_points_projected`

The LCC2020 water/not-water raster is used directly during the viewshed calculation. It is not projected as a full raster during preprocessing because projecting the full raster to 1 m resolution is computationally expensive.

## Single-Park Viewshed Test Result

A single-park Geodesic Viewshed test was completed for Marina Park (`park_num = 134`).

Settings:
- Observer height: 1.6 m
- Analysis buffer: 1000 m around each observer point
- Water target: `LCC2020_wateronot`
- Visible-water rule: `viewshed > 0 AND LCC2020_wateronot == 1`

Result:
- Visible water cells: 206,621
- Cell area: 0.9996 m²
- Visible water area: 206,545.28 m²
- Avery reference value: 204,565 m²

This result is close to Avery’s reference value, suggesting that the LCC2020 water/not-water raster and 1000 m analysis buffer provide a reasonable approximation of the original visual-access metric.

## Pilot 10 Viewshed Analysis

**Script:**  
`scripts/viewshed/05_run_geodesic_viewshed_pilot_10.py`

### Purpose

Run the LCC-based Geodesic Viewshed workflow for all 10 pilot parks.

### Settings

- Observer height: 1.6 m
- Analysis buffer: 1000 m around each observer point
- Viewshed method: ArcGIS Geodesic Viewshed / Viewshed2
- Analysis type: Frequency
- Water target: `LCC2020_wateronot`

### Method

For each pilot park:

1. Select the park’s 3 projected observer points.
2. Create a 1000 m analysis buffer around each observer point and dissolve the buffers.
3. Clip the DSM to the local analysis area.
4. Run Geodesic Viewshed.
5. Calculate visible water using:

   `viewshed > 0 AND LCC2020_wateronot == 1`

6. Save the final visible-water raster.
7. Calculate visible water area in square metres.
8. Delete temporary intermediate outputs.

### Outputs

- `data/processed/viewshed/viewshed_outputs.gdb/visible_water_park_<park_num>`
- `data/processed/viewshed/pilot_10_visible_water_summary.csv`


## Next Steps

1. Review the pilot 10 visible-water summary table.
2. Visually QA the final visible-water rasters.
3. Compare pilot results with Avery’s reference visual-access values where available.
4. Decide whether the method should be scaled to all 114 parks.

## Comparison with Avery’s Reference Values

The pilot 10 visible-water outputs were compared with Avery’s final visual-access values from the project Excel file.

Output:
- `data/processed/viewshed/pilot_10_visible_water_comparison.csv`

Comparison fields:
- `park_num`
- `PARK_NAME`
- `visible_water_area_m2`
- `avery_visual_access_m2`
- `diff_m2`
- `percent_diff`

The Marina Park result closely matched Avery’s reference value, but other pilot parks showed larger differences. This is expected because the rebuilt workflow uses path-based clustered observer points, while Avery’s original workflow used random observer points inside the land buffer.

## QA Notes and Interpretation

Visual QA showed that observer placement is highly influential in the viewshed results. Some locations are sensitive to small differences in observer placement, land-buffer geometry, OSM path alignment, and land-cover classification.

One QA issue was that an observer point appeared to fall in an area that visually looked like water on the basemap. However, the same area was classified as land/non-water in the LCC raster and was also included in the land buffer, with an OSM path present nearby. This suggests the issue is due to disagreement between the basemap, land-buffer geometry, OSM paths, and land-cover classification rather than a simple scripting error.

This should be flagged for manual QA before scaling the method to all 114 parks.

## Next Steps

1. Review the pilot 10 visible-water summary and comparison tables with the supervisor.
2. Visually QA parks with the largest differences from Avery’s reference values.
3. Confirm whether path-based observer placement should replace or supplement random observer placement.
4. Confirm whether a weighted/visual magnitude method should be developed after receiving expert feedback.
5. If approved, scale the workflow from the 10 pilot parks to all 114 parks.