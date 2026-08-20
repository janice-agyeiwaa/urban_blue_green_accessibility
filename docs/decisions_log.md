# Decision Log

## Reach Access Workflow

* Used the composite network instead of downloading new OSM data.
* Generated candidate access points from intersections between the composite network and land-buffer boundaries.
* Started with exact intersections only.
* Parks without generated access points were identified for manual review.
* Six parks did not receive candidate access points from the automated intersection method.
* Manual access points were added for the missing parks in ArcGIS Pro.
* Manual access points were assigned:

  * `park_num`
  * `PARK_NAME`
  * `method = manual_review`
* Duplicate or stacked access points were removed using rounded coordinates.
* Connectivity checks were used to classify candidate access points as keep, review, or remove.
* Manual access points were kept because they were added specifically to correct missing automated access locations.
* Final kept access points were saved as the reach access input for later reach and viewshed workflows.

---

## Bus Stop / Reach Workflow

* Bus stops were taken from the `Stops` layer in `CompositeNetwork3.gdb`.
* This source was used to keep the bus stop dataset consistent with the composite network used for routing.
* A comparison was made with TransLink GTFS stops downloaded in May 2026:

  * TransLink GTFS stops: 8,944
  * Composite network `Stops` layer: 8,828
  * Difference: 116 stops
* The composite `Stops` layer was selected for the final workflow.
* Walktime thresholds were calculated using a walking speed of 80 m/min:

  * 5 minutes = 400 m
  * 10 minutes = 800 m
  * 20 minutes = 1,600 m
  * 30 minutes = 2,400 m
* Reachable network edges were buffered by 15 m to create approximate walktime polygons.
* Bus stops were counted where they intersected each walktime polygon.
* The final reach independent variables per park are:

  * `access_point_count`
  * `bus_stops_05min`
  * `bus_stops_10min`
  * `bus_stops_20min`
  * `bus_stops_30min`

---

## Viewshed Workflow

* The original fixed-observer approach was revised because parks differ greatly in size and path length.
* A fixed number of observer points for every park was considered less fair for larger parks.
* The updated method generates observer points from park path networks using spacing-based sampling.
* The observer point method uses a hierarchy:

  1. Use paths inside the park land buffer first.
  2. If inside paths are insufficient, add nearby paths within 30 m.
  3. If still insufficient, use final reach access points as fallback.
* Nearby paths are treated only as supplements.
* Inside-park observer points are preserved first and are not replaced by nearby-road points.
* Final reach access points are not always included as observer candidates; they are only used as fallback.
* Candidate observer points are filtered against the water raster so observer points are not placed on water cells.
* Candidate observer points are generated using spacing options in this order:

  * 100 m
  * 50 m
  * 25 m
* The minimum observer count per park is 3.
* The maximum observer count per park is 15.
* If more than 15 observer points are available, the final set is selected using a farthest-point approach to keep points spatially spread.
* This avoids simply taking the first 15 points and helps reduce clustering.
* The final observer points are saved as an interim file because they are inputs to the viewshed run, not final outputs.

---

## Park 86 Validation Case

* Park 86, Sandy Cove Park, was used as a validation case for the updated observer method.
* The earlier observer placement produced a visible water area of 0 m².
* Review showed that the useful beach connector/path was outside or only near the land buffer, while observers were not well placed for actual beach visibility.
* The updated nearby-path supplement method captured the local path network within 30 m.
* With the revised observer placement, Park 86 produced visible water area greater than 0.
* This confirmed that observer placement strongly affects viewshed results and that the hierarchical observer method is more appropriate.

---

## Viewshed Calculation

* Viewshed is run park by park using `Viewshed2`.
* The DSM is used as the elevation surface.
* The water raster is used to isolate visible water cells.
* Observer height is set to 1.6 m.
* The analysis buffer is set to 1,000 m around observer points.
* The viewshed raster is generated using `FREQUENCY`.
* The final metric does not average visibility across observers.
* A water cell is counted if it is visible from at least one observer point.
* The final metric is total visible water area per park:

  * `visible_water_area_m2`
* The viewshed script saves progress after each park so interrupted runs can resume without restarting from the beginning.



# Decision Log: Haptic Workflow

## Shoreline Exposure Metric

* Avery’s haptic-related value was compared for several parks.
* The comparison showed that Avery’s method uses:

```text
shoreline_to_perimeter_ratio = shoreline_length_m / park_perimeter_m
```

* The shoreline length comes from the polyline layer:

```text
allparks_land_buff_Intersect
```

* The park perimeter comes from:

```text
allparks_land_buffer
```

* This method was retained so that the updated workflow remains comparable with Avery’s previous results.

## Interpretation of Avery’s Metric

* Avery’s metric is interpreted as a shoreline exposure or shoreline contact metric.
* It tells us how much of the park boundary is shoreline-facing.
* It does not directly confirm whether the shoreline is physically touchable or accessible.
* Because of this limitation, an additional terrain-based haptic proxy was added.

## Terrain-Based Haptic Proxy

* Full manual shoreline classification was not used because it would take too much time.
* Instead, a fully automated terrain-based proxy was selected.
* The terrain-based proxy uses DTM-derived slope near the shoreline to estimate whether shoreline segments are physically approachable.
* This better matches the haptic access idea than using park entrances, because haptic access is about whether someone can approach the shoreline once inside the park.

## Slope Threshold Decision

* Shoreline segments are split into 20 m pieces.
* A 10 m land-side buffer is created for each segment by intersecting the segment buffer with the park land buffer.
* Mean slope is calculated inside each land-side buffer.
* A shoreline segment is classified as gentle if:

```text
mean_slope_degrees <= 10°
```

* The 10° threshold was chosen as a practical project threshold for likely approachable shoreline.
* The working interpretation is:

```text
0–5°     very flat / easy shoreline approach
5–10°    gentle / likely approachable
10–20°   moderate slope / possible but less comfortable
20°+     steep / less likely to be haptically accessible
```

* This classification is used as a proxy, not a field-verified accessibility assessment.

## Final Haptic Variables

The haptic workflow keeps two final variables:

```text
shoreline_to_perimeter_ratio
```

This is Avery’s shoreline exposure metric.

```text
gentle_shoreline_ratio
```

This is the terrain-based haptic access proxy.

## Limitations

* The terrain-based proxy does not detect fences, cliffs, railings, private barriers, dense vegetation, seawalls, or safety restrictions unless these are reflected in the slope surface.
* The metric should therefore be described as potential haptic access or terrain-based shoreline approachability, not confirmed touchable shoreline.
* Parks with unexpected values should be flagged for targeted review rather than full manual classification.
