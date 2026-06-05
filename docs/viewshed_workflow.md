# Viewshed Workflow Notes

## Purpose

The viewshed workflow measures visual access to water for each waterfront park/site. The workflow creates observer points, runs a viewshed analysis from those observer points, and calculates the visible water area for each park.

The final visual access metric is:

- `visible_water_area_m2`

## Input Data

### Park land buffer

- Source geodatabase: `data/raw/Park_Extraction_Project.gdb`
- Layer: `allparks_land_buffer`
- Number of records: 114
- CRS: EPSG:26910
- Key fields:
  - `park_num`
  - `PARK_NAME`
  - `MUNI`
  - `geometry`

### Composite network

- Source geodatabase: `data/raw/CompositeNetwork3.gdb`
- Layer: `OSM_NA_Network_NAD_Point3`
- Used to generate path-based observer point candidates.

### DSM

- Source raster: `data/raw/dsm.tif`
- Used as the elevation surface for the viewshed analysis.

### Water raster

- Source raster: `data/raw/LCC2020_wateronot.tif`
- Values:
  - `0` = not water
  - `1` = water

The water raster is used to identify which visible cells are water.

## Observer Point Method

Observer points are generated from composite-network paths inside each park land buffer.

The observer point workflow follows these steps:

1. Read the 114 park land buffers.
2. Read the composite network layer.
3. For each park, identify composite-network paths that intersect the land buffer.
4. If no paths intersect the land buffer, search for nearby paths within 15 m of the land buffer.
5. Generate candidate observer points along the selected paths.
6. Filter out candidate observer points that fall on water using `LCC2020_wateronot.tif`.
7. Select 3 observer points per park using KMeans clustering.
8. Save the final observer points and observer log.

## Observer Point Settings

- Target observer points per park: 3
- Candidate point spacing options: 25 m, 10 m, 5 m
- Nearby path search distance: 15 m
- KMeans random state: 42

The script first tries to generate observer candidates every 25 m. If there are fewer than 3 non-water candidates, it tries 10 m, then 5 m. The fixed random state makes the KMeans selection reproducible.

## Observer Point Script

- `scripts/viewshed/01_create_observer_points.py`

## Observer Point Outputs

### Interim outputs

- `data/interim/viewshed/all114_raw_composite_network_paths.gpkg`
- `data/interim/viewshed/all114_clipped_or_nearby_composite_network_paths.gpkg`
- `data/interim/viewshed/all114_candidate_observer_points_composite.gpkg`
- `data/interim/viewshed/all114_candidate_observer_points_clustered_composite.gpkg`
- `data/interim/viewshed/all114_observer_point_log_composite.csv`

### Processed output

- `data/processed/viewshed/all114_observer_points_composite.gpkg`

## Viewshed Method

Viewshed analysis is run park by park using the final observer points.

For each park:

1. Select the 3 observer points for the park.
2. Create a 1 km analysis buffer around the observer points.
3. Clip the DSM to the analysis buffer.
4. Clip the water raster to the analysis buffer.
5. Run Geodesic Viewshed using the DSM and observer points.
6. Identify visible water cells using the viewshed raster and water raster.
7. Calculate visible water area in square metres.
8. Save the visible water result by park.

## Viewshed Settings

- Observer height: 1.6 m
- Analysis buffer: 1,000 m
- Viewshed tool: `Viewshed2`
- Analysis type: `FREQUENCY`
- Analysis method: `ALL_SIGHTLINES`

The 1 km analysis buffer is used to keep the viewshed analysis consistent and manageable across all parks.

## Visible Water Calculation

Visible water is calculated using:

```text
viewshed cells > 0 AND water raster = 1