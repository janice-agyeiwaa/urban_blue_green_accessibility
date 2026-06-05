# Reach Workflow Notes

## Purpose

The reach workflow identifies candidate physical access points for each waterfront park/site. Access points are created where the composite pedestrian/network layer intersects the boundary of each park land buffer.

## Input Data

### Park land buffer

- Source geodatabase: `data/raw/Park_Extraction_Project.gdb`
- Layer: `allparks_land_buffer`
- Number of records: 114
- CRS: EPSG:26910
- Key fields:
  - `park_num`
  - `PARK_NAME`
  - `geometry`

### Composite network

- Source geodatabase: `data/raw/CompositeNetwork3.gdb`
- Layer: `OSM_NA_Network_NAD_Point3`
- Number of records: 247,869
- CRS: EPSG:26910

## Method

1. Read the 114 park land buffers.
2. Read the composite network layer.
3. Confirm that both layers use the same CRS: EPSG:26910.
4. Convert each land buffer polygon to its boundary line.
5. Intersect the land-buffer boundary with the composite network.
6. Save the resulting intersection points as raw candidate access points.
7. Count the number of raw candidate access points per park.

## Script

- `scripts/reach/01_create_candidate_access_points.py`

## Output Files

- `data/interim/reach/candidate_access_points_raw.gpkg`
- `data/interim/reach/access_point_counts_raw.csv`

## Script Output Summary

- Total parks processed: 114
- Parks with generated candidate access points: 108
- Parks without generated candidate access points: 6
- Total raw candidate access points: 1,759


## Manual Additions

Six parks did not receive candidate access points from the composite network and land-buffer boundary intersection method. These parks were reviewed manually in ArcGIS Pro, and access points were added in a separate manual point layer.

Manual access points were assigned the required fields:

- `park_num`
- `PARK_NAME`
- `method`

For manually added points:
method = manual_review

## Comparison with Avery Access Points

The cleaned access points were compared with Avery’s access point layer after exploding Avery’s MultiPoint geometries into individual points.

Final comparison summary:

- Cleaned access points: 1,772
- Avery access points after explode: 1,776
- Overall difference: -4

Some differences were identified during review:

- Parks 2, 61, and 82: Avery’s layer had duplicate records pointing to the same location, so these were treated as duplicate points.
- Park 13: One manual access point was added after review.
- Park 72: Eight manual access points were added after review.

These differences were reviewed manually and are related to duplicate point records or manual corrections for missing or undetected access locations.
## Bus Stop Data Source

Bus stops were taken from the `Stops` layer in `CompositeNetwork3.gdb` to maintain consistency with the composite network dataset.

A quick comparison was also made with the TransLink GTFS stops downloaded in May 2026:

- TransLink GTFS stops: 8,944
- Composite network `Stops` layer: 8,828
- Difference: 116 stops

The composite `Stops` layer was used for the reach workflow because it belongs to the same prepared network dataset used for the walktime analysis.

## Walktime and Bus Stop Count Settings

Walktime polygons are created from the composite network using the cleaned access points as routing origins.

The script uses a walking speed of 80 metres per minute, equivalent to 4.8 km/h.. This gives the following distance thresholds:

- 5 minutes: 400 m
- 10 minutes: 800 m
- 20 minutes: 1,600 m
- 30 minutes: 2,400 m

The maximum routing distance is therefore 2,400 m, based on the 30-minute threshold.

Reachable network edges are buffered by 15 m to create approximate walktime polygons. Bus stops are then counted where they intersect each walktime polygon.

Coordinate rounding is used only to reduce precision-related duplicates:

- `NODE_ROUND = 3`: rounds network node coordinates to 3 decimal places when building the graph.
- `XY_ROUND = 2`: rounds access-point coordinates to 2 decimal places when removing stacked routing origins.

A snap warning threshold of 50 m is used to flag access points that are far from the nearest composite network edge. This does not remove the point; it only marks it for review.

