# Paper 4 Mapbox Methodology

## Analytical purpose

Paper 4 examines whether multidimensional accessibility is associated with
observed use of Metro Vancouver waterfronts. In accordance with the proposal,
multidimensional accessibility is the primary explanatory variable. Physical,
visual, and haptic accessibility are evaluated in separate models to determine
whether component-specific associations differ from the aggregate result.

## Paper 3 accessibility handoff

Paper 4 uses the validated 10-minute Paper 3 scores for all 114 waterfronts:

- physical accessibility: equal-weight average of scaled pedestrian-entry
  density and 10-minute transit availability;
- visual accessibility: visible-water ratio;
- haptic accessibility: shoreline-length-to-perimeter ratio; and
- multidimensional accessibility: equal-weight average of scaled physical,
  visual, and haptic accessibility.

The Paper 4 dataset builder checks every handoff score against the canonical
Paper 3 analysis table before joining it to Mapbox activity. The exploratory
DTM-OSM haptic proxy does not replace the proposal-specified haptic component.

## Mapbox activity outcome

The 2023 Mapbox Movement file contains an activity index for grid-cell
centroids matched to each waterfront extraction area. Cell values are averaged
to one waterfront-level activity value for each month, day type, and hour.
Hours from 06:00 through 20:59 are retained and classified as:

- morning: 06:00-11:59;
- afternoon: 12:00-16:59; and
- evening: 17:00-20:59.

Day type is weekday or weekend. Meteorological seasons are winter
(December-February), spring (March-May), summer (June-August), and fall
(September-November).

The raw activity index is positive and strongly right-skewed (skewness 3.38).
The natural logarithm of activity is therefore the primary model outcome. Its
unconditional skewness is -0.06, and the mixed-model residual skewness is about
-0.75 instead of about 2.00 under the raw outcome. Raw-scale models are retained
as a sensitivity analysis.

## Samples and population-density control

Mapbox activity is available for 103 waterfronts and 32,472 site-time
observations. The primary neighbourhood control is 2021 population density in
the same 10-minute network-based walking catchment used for accessibility.
Population density is total enriched population divided by catchment area in
square kilometres.

Five of the 103 Mapbox waterfronts have `HasData = 0` in the 10-minute Enrich
output. These values are treated as missing rather than as true zero
populations. The primary complete-case sample therefore contains 98 waterfronts
and 30,946 observations. The high-coverage sensitivity contains 76 waterfronts
and 27,013 observations. The previous 20-minute population-density control is
retained only as a sensitivity analysis; it contains all 103 waterfronts and
32,472 observations.

## Mixed-effects and spatial models

Each accessibility measure is evaluated in a separate random-intercept model:

```text
log(activity_ij) = beta_0 + beta_1 accessibility_j
                 + temporal controls_ij + site controls_j
                 + waterfront effect_j + error_ij
```

The temporal controls are day type, time of day, and season. Site controls are
four-category waterfront type, log-transformed land-buffer area, and
log-transformed population density. Weekday, morning, winter, and riverfront
are the reference categories. Accessibility, log site area, and log population
density are standardized at the waterfront level. A random intercept accounts
for repeated observations within each waterfront.

The random-intercept models retained spatial pattern in their waterfront
effects. Final inference therefore uses random-effects eigenvector spatial
filtering (RE-ESF), with spatial structure defined at the waterfront level.
Residual spatial autocorrelation is tested using row-standardized
seven-nearest-neighbour weights, matching the Paper 3 spatial-neighbour rule.
All final RE-ESF residual Moran tests are nonsignificant.

Benjamini-Hochberg false-discovery-rate adjustment is applied across the four
accessibility coefficients within each specification. Because the outcome is
logged, `100 * (exp(beta) - 1)` is reported as the estimated percentage change
in activity associated with a one-standard-deviation increase in accessibility.

## Sensitivity analyses

The final sensitivity analyses repeat the spatially filtered models using:

1. waterfronts with at least 90% temporal coverage;
2. the previous 20-minute population-density control;
3. exclusion of waterfront type; and
4. the untransformed activity index.

The raw-outcome sensitivity is interpreted cautiously because its residual
distribution is substantially more skewed, it produces conclusions that are
not stable under the better-fitting logged outcome, and its spatially filtered
physical model retains negative residual spatial autocorrelation
(Moran's I = -0.087, p = .022).

## Principal results

In the primary 98-waterfront RE-ESF models:

- physical accessibility is positively associated with activity
  (beta = 0.495, 95% CI 0.285 to 0.705, p < .001, q < .001), equivalent to an
  estimated 64.0% increase for a one-standard-deviation increase;
- haptic accessibility is negatively associated with activity
  (beta = -0.248, 95% CI -0.447 to -0.050, p = .014, q = .029), equivalent to
  an estimated 22.0% decrease;
- visual accessibility is not statistically significant
  (beta = -0.173, p = .106, q = .141); and
- multidimensional accessibility is not statistically significant
  (beta = -0.025, p = .821, q = .821).

The positive physical and negative haptic associations remain in the logged
high-coverage, 20-minute-density, and no-site-type sensitivities. The
multidimensional coefficient remains nonsignificant in every logged
specification. These results indicate that distinct accessibility components
have opposing relationships with activity that are not represented by a single
aggregate association.
