# Reach Access Workflow

## Goal

Rebuild the physical/reach access workflow from spatial inputs using Python and open-source spatial data.

The purpose is to test whether the reach accessibility workflow can be reproduced from spatial inputs, rather than only reading existing processed values.

---

## Base Layer

- Layer: `allparks_land_buffer`
- Records: 114
- CRS: NAD 1983 UTM Zone 10N / EPSG:26910
- Reason for use: Project documentation defines reach access points as access to the waterfront land buffer, not access to the full park polygon.

The full park polygon layer is not used as the main reach analysis unit.

---

## Script 01: Candidate Access Point Generation

**Script:**  
`scripts/reach/01_create_candidate_access_points.py`

### Inputs

- `data/raw/Park_Extraction_Project.gdb/allparks_land_buffer`
- OpenStreetMap walking network downloaded with OSMnx

### Method

1. Read the 114 edited land-buffer polygons.
2. Process each park separately.
3. Convert each land buffer to WGS84 for OSMnx.
4. Download the OSM walking network around each park buffer.
5. Convert OSM lines back to EPSG:26910.
6. Convert each land buffer polygon to a boundary line.
7. Intersect OSM walking lines with the land-buffer boundary.
8. Extract point geometries from the intersection results.
9. If no exact intersections are found, try fallback candidates using nearby OSM lines within 3 m, then 5 m.
10. Save raw candidate access points.

### Outputs

- `data/interim/reach/candidate_access_points_raw.gpkg`
- `data/interim/reach/candidate_access_points_failed_parks.csv`

### Notes

- Exact intersections are preferred.
- The 3 m / 5 m fallback is used only when a park has no exact intersection.
- Parks with no exact or fallback candidates are flagged in the failed-park log.
- OSM may not contain all local trails, plazas, informal paths, or park access routes.

---

## Script 02: Candidate Access Point Cleaning

**Script:**  
`scripts/reach/02_clean_candidate_access_points.py`

### Purpose

Remove only exact stacked duplicate candidate access points.

### Method

1. Read the raw candidate access points.
2. Round x/y coordinates to 2 decimal places.
3. Within each park, remove records with the same rounded coordinate.
4. Keep near-but-not-identical points for later QA.

### Outputs

- `data/interim/reach/candidate_access_points_cleaned.gpkg`
- `data/interim/reach/candidate_access_points_removed_exact_duplicates.csv`
- `data/interim/reach/candidate_access_point_counts_cleaned.csv`

### Summary

- Raw candidate points: 3018
- Exact stacked duplicates removed: 1511
- Cleaned candidate points: 1507

### Notes

Near-duplicates were not removed automatically because close points may represent distinct access routes.

---

## Script 03: Compare Access Points to Reference Layer

**Script:**  
`scripts/reach/03_compare_access_points_to_reference.py`

### Inputs

- `data/interim/reach/candidate_access_points_cleaned.gpkg`
- `data/raw/Park_Extraction_Project.gdb/allparks_access_points`

### Method

1. Read cleaned Python-generated access points.
2. Read Avery’s/reference access point layer.
3. Explode Avery’s `MultiPoint` geometries into individual point geometries.
4. Compare generated and reference access points by park.
5. Calculate:
   - generated point count;
   - reference point count;
   - count difference;
   - mean nearest distance;
   - median nearest distance;
   - max nearest distance.
6. Select best-matching parks for the pilot subset.

### Outputs

- `data/interim/reach/access_point_comparison_by_park.csv`
- `data/interim/reach/best_matching_parks_for_pilot.csv`

### Notes

The reference access point layer had 1185 table records, but 1776 individual point geometries after exploding `MultiPoint` features.

---

## Script 04: Select Pilot Parks

**Script:**  
`scripts/reach/04_select_pilot_parks.py`

### Purpose

Select the best-matching 10 pilot parks for the next reach-analysis steps.

### Method

1. Read `best_matching_parks_for_pilot.csv`.
2. Select the top 10 parks.
3. Export the selected pilot park list.
4. Export generated access points for only those 10 parks.

### Outputs

- `data/processed/reach/pilot_10_parks.csv`
- `data/processed/reach/pilot_10_access_points.gpkg`

### Notes

The pilot subset is used because the full 114-park generated access point layer still requires additional QA.

---

## Script 05: Prepare Bus Stops

**Script:**  
`scripts/reach/05_prepare_bus_stops.py`

### Input

- `data/raw/google_transit/stops.txt`

This is the TransLink GTFS static `stops.txt` file.

### Method

1. Read TransLink GTFS `stops.txt`.
2. Use `stop_lon` and `stop_lat` to create point geometries.
3. Assign CRS EPSG:4326.
4. Project bus stops to EPSG:26910.
5. Export bus stop point layer.

### Output

- `data/interim/reach/translink_bus_stops.gpkg`

---

## Walking-Distance Assumption

The original documentation does not specify the exact walking speed or impedance used in ArcGIS Network Analyst.

For the Python pilot workflow, walk-time thresholds were approximated using:

- 4.8 km/h = 80 m/min

Thresholds:

- 5 min = 400 m
- 10 min = 800 m
- 20 min = 1600 m
- 30 min = 2400 m

This assumption is used only for the Python-based pilot workflow.

---

## Script 06: Bus Stop Counts Using Network Distance

**Script:**  
`scripts/reach/06_count_bus_stops_for_pilot.py`

### Purpose

Initial open-source test for bus stop reach using direct network distance from access points to bus stops.

### Method

1. Read pilot access points.
2. Read TransLink bus stops.
3. For each pilot park, download the OSM walking network around the access points.
4. Snap access points to nearest OSM nodes.
5. Snap nearby bus stops to nearest OSM nodes.
6. Use Dijkstra shortest-path distance from the park’s access points.
7. Count bus stops within 5, 10, 20, and 30 minute network distances.

### Outputs

- `data/processed/reach/pilot_10_bus_stop_counts.csv`
- `data/processed/reach/pilot_10_bus_stop_reach_details.csv`

### Notes

This method does not create walk-time polygons. It counts bus stops based on network distance from access points to bus stop nodes.

This was useful as a test, but it was harder to visually compare with Avery’s ArcGIS service-area polygons.

---

## Script 07: Walk-Time Polygons and Bus Stop Counts

**Script:**  
`scripts/reach/07_create_walktime_polygons_for_pilot.py`

### Purpose

Create visible open-source walk-time polygons and count bus stops inside them.

This became the main pilot method for comparison with Avery’s bus stop counts.

### Method

1. Read pilot access points.
2. Read TransLink bus stops.
3. For each pilot park, download the OSM walking network.
4. Snap access points to the OSM network.
5. Use Dijkstra shortest-path distance to identify reachable OSM nodes.
6. Select reachable OSM edges within 5, 10, 20, and 30 minute thresholds.
7. Buffer reachable edges by 15 m.
8. Dissolve buffered edges by park and walk-time threshold.
9. Count TransLink bus stops inside each walk-time polygon.

### Outputs

- `data/processed/reach/pilot_10_walktime_polygons.gpkg`
- `data/processed/reach/pilot_10_bus_stop_counts_from_walktime_polygons.csv`

### Notes

Avery used ArcGIS Network Analyst service-area polygons. This Python method is an open-source approximation using reachable OSM edges and buffered polygons.

The method is not expected to exactly match ArcGIS Network Analyst outputs.

---

## Script 08: Compare Bus Stop Counts

**Script:**  
`scripts/reach/08_compare_bus_stop_counts.py`

### Inputs

- `data/processed/reach/pilot_10_bus_stop_counts_from_walktime_polygons.csv`
- `data/raw/Park_Extraction_Project.gdb/allparks_land_buffer_reachvariables`

### Method

1. Read Python-derived pilot bus stop counts.
2. Read Avery’s/reference reach variables.
3. Join by `park_num`.
4. Compare bus stop counts at 5, 10, 20, and 30 minutes.
5. Calculate difference:

`diff = Python result - Avery/reference result`

### Output

- `data/processed/reach/pilot_10_bus_stop_count_comparison.csv`

### Final Table Columns

- `park_num`
- `PARK_NAME`
- `bus_stops_05min`
- `avery_05min`
- `diff_05min`
- `bus_stops_10min`
- `avery_10min`
- `diff_10min`
- `bus_stops_20min`
- `avery_20min`
- `diff_20min`
- `bus_stops_30min`
- `avery_30min`
- `diff_30min`

---

## Marina Park Sensitivity Note

Marina Park was used as a quick sensitivity check for the edge-buffer size.

Avery’s Marina Park counts:

- 20 min = 8
- 30 min = 16

Python pilot with 15 m edge buffer:

- 20 min = 13
- 30 min = 15

The 30-minute result was close, but the 20-minute result remained higher.

Possible reasons include:

- OSM network differs from Yiyang’s Composite Network;
- TransLink GTFS stops differ from Avery’s bus stop dataset;
- ArcGIS Network Analyst service-area polygons differ from the Python buffered-edge approximation;
- Avery’s exact ArcGIS impedance/walking-speed settings are unknown.

---

## Current Limitations

- This is a pilot workflow, not a final full 114-park analysis.
- The OSM-generated access point layer still requires QA before scaling.
- Some parks have no OSM-based candidate access points.
- Avery’s Composite Network and ArcGIS settings are not fully documented.
- Python walk-time polygons are approximate and may not match ArcGIS Network Analyst polygons exactly.
- Bus stop counts may differ because the bus stop source is current TransLink GTFS, not necessarily the exact dataset Avery used.
- The pilot workflow demonstrates reproducibility, but the full 114-park workflow would need additional QA of generated access points, walk-time polygons, and bus stop counts before being treated as final.
---

## Next Steps

- Review the 10 pilot parks visually in ArcGIS.
- Compare generated access points with Avery’s reference access points.
- Compare generated walk-time polygons with Avery’s walk-time polygons where available.
- Review parks with large bus stop count differences.
- Decide whether to refine the open-source approach before scaling to all 114 parks.