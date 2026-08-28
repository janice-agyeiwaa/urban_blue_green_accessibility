# Private data and reproducibility

The GitHub repository contains the analysis code, methodology, tables and
figures. Large or restricted source data are stored separately in the project
OneDrive folder:

`Urban Blue Space Project`

Copy its `data/` directory into the repository root without changing the
relative paths. The private bundle includes the canonical processed inputs for
the final Paper 3 and Paper 4 models and the source inputs needed to reconstruct
Paper 3 accessibility measures.

## Retained source GIS inputs

- `data/raw/CompositeNetwork3.gdb`
  - `OSM_NA_Network_NAD_Point3`
  - `Stops`
- `data/raw/Park_Extraction_Project.gdb`
  - `allparks_land_buffer`
  - `allparks_water_buffer`
  - `allparks_land_buff_Intersect`
- `data/raw/dtm.tif`
- `data/raw/dsm.tif`
- `data/raw/LCC2020_wateronot.tif`
- `data/interim/reach/manual_access_points.gpkg`
- the preserved OSM snapshot under `data/interim/haptic/osm/`
- the final observer points under `data/interim/viewshed/`
- the exact ArcGIS-enriched Census layers used in Papers 3 and 4

The geodatabases are trimmed reproducibility copies. Unused transit schedules,
pilot park layers, test enrichment layers and geodatabase locks are excluded.
The land and water buffers preserve how the waterfront study units were
constructed and inspected. The final viewshed calculation uses the binary
`LCC2020_wateronot.tif` raster, rather than `allparks_water_buffer`, to identify
visible water cells.

## Mapbox boundary

The approximately 10 GB raw Mapbox Movement export is not included. The private
bundle contains the processed 2023 site-hour activity data used by the final
models. Consequently, the Paper 4 analytical models can be rerun, but the raw
Mapbox grid-cell extraction cannot be repeated from the shared package.

## Transfer integrity

`SHA256_CHECKSUMS.csv` in the private bundle records the expected file size and
SHA-256 checksum for each file. Keep the OneDrive folder restricted because it
contains Mapbox-derived and ArcGIS-enriched data.
