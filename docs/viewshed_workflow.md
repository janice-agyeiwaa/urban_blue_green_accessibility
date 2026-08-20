# Viewshed Workflow Notes

## Purpose

The viewshed workflow measures visual access to water for each waterfront park/site. The workflow creates observer points, runs a viewshed analysis from those observer points, and calculates the visible water area for each park.

The final visual access metric is:

* `visible_water_area_m2`

This value represents the total water area visible from the park’s observer locations. A water cell is counted if it is visible from at least one observer point. Visibility is not averaged across observers.

---

## Input Data

### Park land buffer

* Source geodatabase: `data/raw/Park_Extraction_Project.gdb`
* Layer: `allparks_land_buffer`
* Number of records: 114
* CRS: EPSG:26910
* Key fields:

  * `park_num`
  * `PARK_NAME`
  * `MUNI`
  * `geometry`

### Composite network

* Source geodatabase: `data/raw/CompositeNetwork3.gdb`
* Layer: `OSM_NA_Network_NAD_Point3`
* CRS: EPSG:26910
* Number of records: 247,869
* Used to generate path-based observer point candidates.

### Final reach access points

* Source file: `data/processed/reach/reach_access_points.gpkg`
* Used only as a final fallback if path-based observer generation cannot produce enough observer points for a park.

### DSM

* Source raster: `data/raw/dsm.tif`
* Used as the elevation surface for the viewshed analysis.

### Water raster

* Source raster: `data/raw/LCC2020_wateronot.tif`
* Values:

  * `0` = not water
  * `1` = water

The water raster is used to identify which visible cells are water.

---

## Observer Point Method

Observer points are generated using a hierarchical path-based method.

The workflow prioritizes paths inside the park land buffer. Nearby paths are only used when inside-park paths do not produce enough observer points. Final reach access points are only used as a fallback when path-based methods are still insufficient.

For each park:

1. Identify composite-network paths that intersect the park land buffer.
2. Generate candidate observer points along inside-park paths.
3. Try 100 m spacing first.
4. If fewer than 3 prepared observer points are produced, try 50 m spacing.
5. If still fewer than 3 prepared observer points are produced, try 25 m spacing.
6. Candidate observer points are filtered to remove points that fall on water using `LCC2020_wateronot.tif`.
7. Duplicate or stacked observer points are removed using rounded coordinates.
8. Points that are too close together are thinned using a 50 m minimum separation rule.
9. If inside-park paths still produce fewer than 3 observer points, nearby paths within 30 m of the park land buffer are used as a supplement.
10. Inside-park observer points are preserved first. Nearby-path points are only added if needed and only if they are far enough from already-kept inside-path points.
11. If the park still has fewer than 3 observer points, final reach access points are added as a fallback.
12. If a park has more than the maximum allowed observer points, the points are capped using a farthest-point spatial selection method so the final observers remain spread out.

---

## Observer Point Settings

* Preferred spacing order: 100 m, then 50 m, then 25 m
* Minimum observer points per park: 3
* Maximum observer points per park: 15
* Nearby path search distance: 30 m
* Minimum observer separation distance: 50 m
* Coordinate duplicate rounding: 2 decimal places

The script first tries to generate observer candidates every 100 m. If there are fewer than 3 prepared observer points, it tries 50 m, then 25 m.

Prepared observer points are candidate points that have passed:

* water filtering
* duplicate removal
* minimum-distance thinning

For large parks, the script does not simply keep the first 15 points. It generates all candidate points first, then caps the final observer set using a farthest-point approach. This helps keep observer points spatially spread across the park.

---

## Observer Point Script

* `scripts/accessibility_analysis/upstream/viewshed/02_create_observer_points_spacing_access_fallback.py`

---

## Observer Point Output

### Interim output

* `data/interim/viewshed/observer_points_spacing_access_fallback.gpkg`

This file is an intermediate input for the viewshed script. It is not treated as a final processed result.

---

## Viewshed Method

Viewshed analysis is run park by park using the final observer points.

For each park:

1. Select the observer points for the park.
2. Create a 1 km analysis buffer around the observer points.
3. Clip the DSM to the analysis buffer.
4. Fill DSM NoData cells with `-1`.
5. Clip the water raster to the analysis buffer.
6. Run Geodesic Viewshed using the DSM and observer points.
7. Identify visible water cells using the viewshed raster and water raster.
8. Calculate visible water area in square metres.
9. Save the result by park.
10. Save progress to the output CSV after each park so the script can resume if interrupted.

---

## Viewshed Settings

* Observer height: 1.6 m
* Analysis buffer: 1,000 m
* Viewshed tool: `Viewshed2`
* Analysis type: `FREQUENCY`
* Analysis method: `ALL_SIGHTLINES`
* Analysis target device: `GPU_THEN_CPU`

The 1 km analysis buffer is used to keep the viewshed analysis consistent and manageable across all parks.

---

## Visible Water Calculation

Visible water is calculated using:

```text
viewshed cells > 0 AND water raster = 1
```

Because the viewshed raster is created using `FREQUENCY`, a cell can have a value showing how many observers can see it. However, the final calculation only checks whether the cell is visible from at least one observer:

```text
viewshed value > 0
```

Therefore, a visible water cell is counted once, even if it is visible from multiple observer points.

The final park-level metric is:

```text
visible_water_area_m2 = visible water cell count × raster cell area
```

This is a total visible water area per park, not an average visible water area per observer.

---

## Viewshed Script

* `scripts/accessibility_analysis/upstream/viewshed/03_run_viewshed_all_parks.py`

---

## Viewshed Outputs

### Processed output

* `data/processed/viewshed/allparks_viewshed_visible_water_area_spacing_access_fallback.csv`

This is the final viewshed result table.

### Interim review rasters

* `data/interim/viewshed/viewshed_visible_water_rasters_spacing_access_fallback.gdb`

This geodatabase stores visible water rasters for review, using names such as:

```text
visible_water_park_<park_num>
```

---

## Resume / Progress Saving

The viewshed script saves progress to the same CSV after each park. If the script is interrupted or manually stopped, the next run reads the existing CSV, skips parks with completed `visible_water_area_m2` values, and continues from the remaining parks.

This avoids restarting the full viewshed process from the beginning.
