# Paper 4 / Mapbox analysis — canonical

Paper 4 now uses the validated Paper 3 10-minute accessibility handoff and a
matching 10-minute population-density control. The canonical run order is
implemented by `run_all.R` and documented in `docs/mapbox_workflow.md`.

Final inference uses the spatially filtered RE-ESF models because the ordinary
random-intercept models retained spatial pattern in their waterfront effects.
The primary sample contains 98 waterfronts and 30,946 site-time observations.
Existing outputs from the superseded 20-minute accessibility handoff are not
part of the canonical workflow.
