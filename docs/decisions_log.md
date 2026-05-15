# Decision Log

## 2026-05-10 — Reach base layer

Decision: Use `allparks_land_buffer` as the base layer for reach access analysis, not the full park polygon layer.

Reason: Project documentation defines reach access points as access to the waterfront land buffer, not access to the entire park. The land buffer has 114 records and matches the later project working dataset.

---

## 2026-05-10 — Network source

Decision: Use OSM walking network downloaded with OSMnx instead of relying on the original Composite Network.

Reason: This supports a reproducible Python-based workflow using open data. The original workflow used Yiyang’s Composite Network, but the current rebuild aims to generate candidate access points from accessible/reproducible spatial inputs.

---

## 2026-05-10 — Access point generation method

Decision: Generate raw candidate access points by intersecting OSM walking network lines with the land-buffer boundary.

Reason: This follows the documented logic that access points are where walkable paths/streets meet the edge of the land buffer.

---

## 2026-05-10 — Park-by-park OSM download

Decision: Process each park separately when downloading OSM walking networks.

Reason: Downloading one large OSM network for all 114 disconnected buffers created incomplete access point results. Processing parks individually gives each park its own local OSM network query and improves coverage.

---

## 2026-05-10 — Fallback tolerance

Decision: Use exact intersections first. If a park has no exact intersections, try nearby OSM lines within 3 m, then 5 m.

Reason: Some OSM paths may be slightly misaligned with the land-buffer boundary. The fallback helps recover likely access candidates without using a large tolerance that may create false points.

---

## 2026-05-10 — Exact duplicate removal

Decision: Remove only exact stacked duplicate candidate access points before comparison.

Reason: The raw OSM intersection process produced multiple records at the same coordinates when several OSM line segments met the land-buffer boundary at one location. Exact duplicates were removed by park and rounded x/y coordinates. Near-duplicates were retained for later QA because close points may represent distinct access routes.

---

## 2026-05-10 — Pilot subset for reach workflow

Decision: Continue the next reach-analysis steps using the best-matching 10 pilot parks instead of all 114 parks.

Reason: The OSM-generated access points require additional QA for the full dataset. For this reproducibility test, the pilot parks are selected where generated access points closely match the reference access layer in both count and location. This allows the workflow to demonstrate the method clearly before scaling to all parks.

---

## 2026-05-10 — TransLink GTFS bus stop source

Decision: Use TransLink GTFS static `stops.txt` as the bus stop source for the Python pilot.

Reason: TransLink GTFS is an open and reproducible source for Metro Vancouver bus stop locations. It allows the bus stop layer to be recreated from source data rather than relying only on an existing processed layer.

---

## 2026-05-10 — Walking speed for Python reach pilot

Decision: Use a walking speed of 4.8 km/h, equivalent to 80 m/min, to convert walk-time thresholds into network distances.

Reason: The original ArcGIS Network Analyst walking-speed setting is not documented. The Python workflow therefore uses a clear average adult walking-speed assumption for reproducibility.

---

## 2026-05-10 — Network-distance bus stop count test

Decision: First test bus stop counts using direct network distance from pilot access points to nearby TransLink bus stops.

Reason: This provided a simple open-source test of reachability using OSMnx and Dijkstra shortest-path distance. However, this method did not produce visible walk-time polygons, so it was kept as a diagnostic step rather than the main comparison method.

---

## 2026-05-10 — Open-source service area method

Decision: Use an open-source Python method for pilot walk-time areas instead of ArcGIS Network Analyst.

Reason: The pilot is intended to test a reproducible workflow using open data and Python tools. OSMnx and NetworkX are used for network reachability, and reachable edges are buffered/dissolved to approximate walk-time polygons.

---

## 2026-05-10 — Python walk-time polygon approximation

Decision: Approximate walk-time polygons by buffering reachable OSM walking-network edges and dissolving by park and time threshold.

Reason: Avery used ArcGIS Network Analyst service-area polygons, which are not directly recreated by the current open-source Python workflow. The buffered-edge method provides a visible and reproducible approximation for pilot testing and bus-stop counting.

---

## 2026-05-10 — Edge buffer for Python walk-time polygons

Decision: Use a 15 m buffer around reachable OSM walking-network edges for the pilot walk-time polygons.

Reason: Initial testing with wider buffers overcounted bus stops. A 15 m buffer produced more conservative walk-time polygons while still capturing bus stops close to walkable paths. This is used as a pilot approximation and can be adjusted after further QA.



---

## 2026-05-10 — Separate viewshed workflow documentation

Decision: Create a separate `viewshed_workflow.md` file while keeping all major project decisions in the shared `decision_log.md`.

Reason: Reach and viewshed have different methods, inputs, and assumptions. Separate workflow documents keep the methods organized, while a shared decision log keeps project decisions easy to track chronologically.

---

## 2026-05-10 — Viewshed pilot subset

Decision: Start the viewshed workflow using the same 10 pilot parks selected from the reach workflow.

Reason: Using the same pilot parks keeps the analysis manageable and allows the visual access workflow to be tested before scaling to all 114 parks.

---

## 2026-05-10 — Viewshed observer area

Decision: Use `allparks_land_buffer` as the observer area for viewshed analysis, not the full park polygon or combined land-water buffer.

Reason: Observer points should represent people viewing water from the accessible waterfront land area. The combined buffer includes water, and the full park polygon may include areas far from the waterfront.

---

## 2026-05-10 — Path-based viewshed observer points

Decision: Generate viewshed observer points along walkable OSM paths/corridors inside the land buffer instead of using purely random points.

Reason: Random observer points may fall in unrealistic or inaccessible locations. Path-based observer points better represent where people are likely to walk, stand, and experience views of water.

---

## 2026-05-10 — Three observer points per pilot park

Decision: Use three final observer points per pilot park for the initial viewshed pilot.

Reason: Avery’s previous method used three random observer points per park. Keeping three observers per park allows a comparable observer count while improving point placement through path-based selection.

---

## 2026-05-10 — Cluster-based observer selection

Decision: Generate candidate observer points along all clipped OSM paths inside each land buffer, cluster the candidates into three spatial groups, and select one observer point from each cluster.

Reason: Clustering helps distribute observer points across the accessible waterfront area without assuming disconnected paths form one continuous corridor. It also reduces the risk of all observer points being concentrated in one small part of the park.

---

## 2026-05-10 — Viewshed fallback observer points

Decision: If a pilot park has no usable OSM paths inside the land buffer, create fallback observer points inside the land buffer and flag them clearly.

Reason: Some parks may have incomplete OSM path data. Fallback points allow the workflow to continue while documenting where observer placement was not path-based.

---

## 2026-05-10 — Viewshed observer height

Decision: Use an observer height of 1.6 m for the viewshed analysis.

Reason: Avery used 1.6 m as the observer height in the original viewshed workflow. Using the same value keeps the pilot workflow closer to the reference method.

---

## 2026-05-10 — Viewshed elevation surface

Decision: Use the locally exported DSM raster `data/raw/dsm.tif` for the viewshed pilot.

Reason: The raster was exported from Avery’s `finaldsmv3float` DSM, has approximately 1 m cell size, 32-bit float pixel type, and uses NAD 1983 CSRS UTM Zone 10N. This keeps the workflow close to the original ArcGIS viewshed setup while storing the DSM locally in the project folder.

---

## 2026-05-10 — Viewshed visible-water target

Decision: Use `LCC2020_wateronot.tif` as the visible-water target.

Reason: The raster classifies cells as water or not water, where `0 = not water` and `1 = water`. This allows visible water to be calculated beyond the immediate shoreline buffer and produced a Marina Park test result close to Avery’s reference visual-access value.

---

## 2026-05-10 — Viewshed analysis distance

Decision: Use a 1000 m analysis buffer around each observer point for the pilot viewshed workflow.

Reason: Visible water can extend outward across open water if no distance limit is applied. A 1000 m distance captures nearby visible water while preventing the metric from expanding indefinitely across distant water bodies. The Marina Park test produced 206,545.28 m², close to Avery’s reference value of 204,565 m².

---

## 2026-05-10 — Viewshed visible-water calculation

Decision: Calculate visible water using the rule `viewshed > 0 AND LCC2020_wateronot == 1`.

Reason: The viewshed raster identifies cells visible from the observer points, while the LCC2020 raster identifies water cells. Combining them gives the area of water visible from at least one observer point.

---

## 2026-05-10 — Viewshed output interpretation

Decision: Treat the visible-water result as the combined visible water area from the three observer points, not the average per observer.

Reason: The Geodesic Viewshed output is a frequency raster. Cells with values greater than 0 are visible from at least one observer point, so the final metric counts the unique visible water area seen by any of the three observers.


---

## 2026-05-10 — Visual magnitude / weighted viewshed method

Decision: Do not implement a weighted visual magnitude method in the current pilot workflow.

Reason: Visual magnitude was identified as a possible advanced direction, but the appropriate model or weighting approach still needs to be confirmed by the supervisor/project team. The current pilot therefore focuses on a clearer and comparable visual-access metric: visible water area using Geodesic Viewshed and the LCC2020 water/not-water raster.