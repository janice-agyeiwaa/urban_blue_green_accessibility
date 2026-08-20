# Haptic Workflow Notes

## Purpose

The haptic workflow measures physical shoreline contact and potential physical access to water for each waterfront park/site.

The workflow includes two haptic-related metrics:

1. Avery-style shoreline exposure metric
2. Terrain-based haptic access proxy

The Avery-style metric measures how much of the park boundary is shoreline-facing. The terrain-based proxy estimates how much shoreline is likely to be physically approachable based on nearby land-side slope.

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

### Shoreline / water-contact polyline

* Source geodatabase: `data/raw/Park_Extraction_Project.gdb`
* Layer: `allparks_land_buff_Intersect`
* Geometry type: polyline
* Used as the shoreline/contact line between the park land buffer and water edge.

This layer appears to represent the line where the park land buffer intersects or contacts the water/shoreline. Comparisons with Avery’s values suggest that this is the shoreline layer used in Avery’s haptic calculation.

### DTM

* Source raster: `data/raw/dtm.tif`
* Used to derive slope for the terrain-based haptic access proxy.

---

## Metric 1: Avery-Style Shoreline / Perimeter Ratio

The first haptic metric follows Avery’s shoreline-to-perimeter method.

The metric is:

```text
shoreline_to_perimeter_ratio = shoreline_length_m / park_perimeter_m
```

Where:

* `shoreline_length_m` is the total length of `allparks_land_buff_Intersect` for each park.
* `park_perimeter_m` is the total perimeter of the park land buffer polygon.

This metric measures the proportion of the park boundary that is shoreline-facing or in contact with water.

A higher value means a larger share of the park boundary is shoreline-facing.

This metric is best interpreted as a shoreline exposure or shoreline contact measure. It does not directly confirm whether the shoreline is physically touchable, safe, flat, fenced, steep, or accessible.

---

## Script 1

* `scripts/accessibility_analysis/upstream/haptic/01_calculate_avery_shoreline_perimeter_ratio.py`

## Script 1 Output

* `data/processed/haptic/avery_shoreline_perimeter_ratio.csv`

Output fields:

* `park_num`
* `PARK_NAME`
* `MUNI`
* `park_perimeter_m`
* `shoreline_length_m`
* `shoreline_to_perimeter_ratio`
* `shoreline_to_perimeter_percent`

---

## Metric 2: Terrain-Based Haptic Access Proxy

The second haptic metric is an automated proxy for physical shoreline approachability.

The metric is:

```text
gentle_shoreline_ratio = gentle_shoreline_length_m / shoreline_length_m
```

Where:

* `shoreline_length_m` is the total shoreline/contact length for the park.
* `gentle_shoreline_length_m` is the length of shoreline segments where the nearby land-side terrain is classified as gentle.
* A shoreline segment is classified as gentle if the mean DTM-derived slope in its land-side buffer is less than or equal to the chosen slope threshold.

This metric estimates the proportion of shoreline that is likely to be physically approachable from the park side.

It is a proxy, not a field-verified measure. It does not directly identify fences, vegetation, private barriers, seawalls, cliffs, or other non-terrain barriers.

---

## Terrain-Based Haptic Method

For each park:

1. Read the shoreline/contact polyline from `allparks_land_buff_Intersect`.
2. Split the shoreline into 20 m segments.
3. Create a 10 m buffer around each shoreline segment.
4. Intersect the segment buffer with the park land buffer to approximate the land-side area beside the shoreline.
5. Derive slope from the DTM.
6. Calculate mean slope within each shoreline segment’s land-side buffer.
7. Classify each shoreline segment as gentle or steep/unknown using the slope threshold.
8. Sum gentle shoreline length by park.
9. Calculate `gentle_shoreline_ratio`.

---

## Slope Interpretation

The terrain-based proxy uses slope as an indicator of physical approachability.

The working interpretation is:

```text
0–5°     very flat / easy shoreline approach
5–10°    gentle / likely approachable
10–20°   moderate slope / possible but less comfortable
20°+     steep / less likely to be haptically accessible
```

For this workflow, the current gentle-slope threshold is:

```text
mean_slope_degrees <= 10°
```

This threshold is used as a practical project rule. Published slope classifications vary, but Canadian soil/terrain slope classes commonly distinguish gentle, moderate, and steeper slopes using increasing slope-gradient ranges. For example, the Canadian Soil Information Service identifies gentle slopes as 4–9% gradient, moderate slopes as 10–15%, and steep slopes as 16–30%; Ontario’s slope guidance similarly separates gently, moderately, and strongly sloping terrain into increasing percent-grade classes.

---

## Script 2

* `scripts/accessibility_analysis/upstream/haptic/02_calculate_terrain_based_haptic_proxy.py`

## Script 2 Outputs

### Interim outputs

* `data/interim/haptic/haptic_shoreline_segments.gpkg`
* `data/interim/haptic/haptic_shoreline_landside_buffers.gpkg`

### Processed output

* `data/processed/haptic/terrain_based_haptic_proxy.csv`

Output fields:

* `park_num`
* `PARK_NAME`
* `MUNI`
* `shoreline_length_m`
* `gentle_shoreline_length_m`
* `steep_or_unknown_shoreline_length_m`
* `mean_shoreline_slope_degrees`
* `segment_count`
* `gentle_shoreline_ratio`
* `gentle_shoreline_percent`
* `slope_threshold_degrees`
* `segment_length_m_used`
* `landside_buffer_m_used`

---

## Interpretation

The haptic workflow produces two complementary variables:

```text
shoreline_to_perimeter_ratio
```

This measures how much of the park boundary is shoreline-facing.

```text
gentle_shoreline_ratio
```

This estimates how much of the shoreline is likely to be physically approachable based on nearby land-side slope.

Together, these describe both shoreline exposure and potential physical access to the shoreline.
