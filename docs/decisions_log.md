# Decision Log

## 2026-05-10 — Reach base layer
Decision: Use `allparks_land_buffer` as the base layer for reach access analysis, not the full park polygon layer.

Reason: Project documentation defines reach access points as access to the waterfront land buffer, not access to the entire park. The land buffer has 114 records and matches the later project working dataset.

## 2026-05-10 — Network source
Decision: Use OSM walking network downloaded with OSMnx instead of relying on the original Composite Network.

Reason: This supports a reproducible Python-based workflow using open data. The original workflow used Yiyang’s Composite Network, but the current rebuild aims to generate candidate access points from accessible/reproducible spatial inputs.

## 2026-05-10 — Access point generation method
Decision: Generate raw candidate access points by intersecting OSM walking network lines with the land-buffer boundary.

Reason: This follows the documented logic that access points are where walkable paths/streets meet the edge of the land buffer.

## 2026-05-10 — Fallback tolerance
Decision: Use exact intersections first. If a park has no exact intersections, try nearby OSM lines within 3 m, then 5 m.

Reason: Some OSM paths may be slightly misaligned with the land-buffer boundary. The fallback helps recover likely access candidates without using a large tolerance that may create false points.