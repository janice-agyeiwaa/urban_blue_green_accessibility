# Paper 4 Methods and Results Update Guide

This guide is designed to update the existing Paper 4 section without changing
its proposal-based structure or terminology.

## Methods changes

### Section 5.2.3: analytical sample

Replace the paragraph beginning `Of the 114 urban waterfronts...` with:

> Of the 114 urban waterfronts, 103 had usable Mapbox activity data, producing
> 32,472 site-time observations before model-specific exclusions. The primary
> models used 2021 population density in the 10-minute network-based walking
> catchment as a neighbourhood control. Five Mapbox waterfronts had no usable
> 10-minute population estimate and were treated as missing rather than as
> having zero population. The primary complete-case sample therefore contained
> 98 waterfronts and 30,946 site-time observations. A temporal-coverage
> sensitivity analysis retained waterfronts with at least 90% coverage,
> resulting in 76 waterfronts and 27,013 observations.

### Section 5.2.4: population density

Replace the 20-minute population-density paragraph with:

> Population density was calculated for the 10-minute network-based walking
> catchment surrounding each waterfront, matching the main accessibility
> specification used in Study 3. The 2021 total population obtained using
> ArcGIS Enrich was divided by the corresponding catchment area and expressed
> as people per square kilometre. Records for which ArcGIS Enrich returned
> `HasData = 0` were treated as missing. Population density was natural-log
> transformed before modelling. The previous 20-minute population-density
> measure was retained only as a sensitivity analysis.

### Section 5.2.5: outcome and spatial analysis

After the paragraph describing standardization, insert:

> The Mapbox activity index was strongly right-skewed and was natural-log
> transformed for the primary analysis. Consequently, coefficients for
> continuous site-level predictors are reported as the estimated percentage
> change in activity associated with a one-standard-deviation increase. Models
> using the untransformed activity index were retained as a sensitivity
> analysis.

Replace the spatial-autocorrelation placeholder with:

> Spatial dependence was evaluated at the waterfront level. The ordinary
> random-intercept models retained statistically significant spatial pattern in
> their waterfront effects. Final inference therefore used random-effects
> eigenvector spatial filtering, which represented spatially structured and
> spatially independent waterfront effects while retaining the repeated
> site-time observations. Residual spatial autocorrelation was assessed using
> Moran's I and row-standardized seven-nearest-neighbour weights. The selected
> spatially filtered models had no statistically significant residual spatial
> autocorrelation.

Replace the sensitivity-analysis paragraph with:

> Four sensitivity analyses were conducted. First, the models were repeated
> among waterfronts with at least 90% temporal coverage. Second, the previous
> 20-minute population-density control was substituted for the 10-minute
> control. Third, the models were repeated without waterfront type. Fourth, the
> untransformed Mapbox activity index was used as the outcome. The same spatial
> filtering and residual spatial diagnostics were applied to the sensitivity
> specifications.

## Results text

### Sample and temporal activity

> Mapbox activity was available for 103 waterfronts and 32,472 site-time
> observations. After excluding five waterfronts without usable 10-minute
> population estimates, the primary models included 98 waterfronts and 30,946
> observations. The high-coverage sensitivity included 76 waterfronts and
> 27,013 observations. Descriptively, waterfront activity was higher on
> weekends than weekdays, highest during the afternoon, and highest during
> summer and lowest during winter. These comparisons are descriptive and do
> not account for the other model covariates.

### Primary accessibility models

> The ordinary random-intercept models retained residual spatial pattern at the
> waterfront level; therefore, the spatially filtered models were used for
> final inference. A one-standard-deviation increase in physical accessibility
> was associated with an estimated 64.0% increase in Mapbox activity
> (beta = 0.495, 95% CI 0.285 to 0.705, p < .001, q < .001). In contrast, a
> one-standard-deviation increase in haptic accessibility was associated with
> an estimated 22.0% decrease in activity (beta = -0.248, 95% CI -0.447 to
> -0.050, p = .014, q = .029). Visual accessibility was not statistically
> significant (beta = -0.173, p = .106, q = .141). The primary
> multidimensional accessibility coefficient was also not statistically
> significant (beta = -0.025, p = .821, q = .821).

> The results therefore did not provide evidence that the aggregate
> multidimensional accessibility score was associated with waterfront use.
> However, the dimension-specific models identified opposing component
> relationships: greater physical accessibility was associated with more
> activity, whereas greater shoreline exposure, measured as haptic
> accessibility, was associated with less activity after adjustment. These
> associations are cross-sectional and should not be interpreted as causal.

### Spatial diagnostics and sensitivity analyses

> Residual Moran's I was not statistically significant in any primary
> spatially filtered model: physical (p = .628), visual (p = .889), haptic
> (p = .410), and multidimensional accessibility (p = .681). The spatial
> filtering therefore addressed the waterfront-level residual spatial pattern.

> The positive physical-accessibility association and negative
> haptic-accessibility association were retained in the high-coverage,
> 20-minute population-density, and no-site-type sensitivity analyses. Visual
> accessibility was negative in the high-coverage model before multiple-testing
> adjustment but did not remain significant after adjustment. Multidimensional
> accessibility was not significant in any logged-outcome specification. The
> raw-outcome models produced materially different results, retained substantial
> residual skewness, and the physical model retained residual spatial
> autocorrelation; they were therefore not preferred over the logged-outcome
> models.

## Tables and figures to insert

- Sample table: `outputs/mapbox/tables/table1_mapbox_sample.csv`
- Descriptive table: `outputs/mapbox/tables/table2_mapbox_site_descriptives.csv`
- Temporal table: `outputs/mapbox/tables/table3_mapbox_temporal_activity.csv`
- Main accessibility results: `outputs/mapbox/tables/table4_mapbox_spatially_filtered_effects.csv`
- Full controlled results: `outputs/mapbox/tables/table5_mapbox_main_reesf_coefficients.csv`
- Spatial diagnostics: `outputs/mapbox/tables/tableB1_mapbox_spatial_diagnostics.csv`
- Sensitivity results: `outputs/mapbox/tables/table6_mapbox_spatial_sensitivity_effects.csv`
- Main coefficient figure: `outputs/mapbox/figures/figure1_mapbox_main_accessibility_effects.png`
- Sensitivity figure: `outputs/mapbox/figures/figure2_mapbox_sensitivity_effects.png`
- Temporal figure: `outputs/mapbox/figures/figure3_mapbox_temporal_activity.png`

Use the next sequential table and figure numbers in the working Word document.
The repository filenames are analytical identifiers and do not need to match
the manuscript numbering.

Suggested captions:

> Standardized accessibility associations with logged Mapbox waterfront
> activity in the primary spatially filtered mixed-effects models. Points show
> estimated percentage changes and horizontal lines show 95% confidence
> intervals. Models include day type, time of day, season, waterfront type,
> log-transformed site area, and log-transformed 10-minute population density.

> Accessibility associations across the primary and sensitivity
> specifications. All displayed models use the logged activity outcome and
> spatial filtering. Points show estimated percentage changes associated with
> a one-standard-deviation increase, and horizontal lines show 95% confidence
> intervals.

> Observed Mapbox waterfront activity by day type, time of day, and season.
> Points are site-balanced means and vertical lines are 95% confidence
> intervals. These are descriptive comparisons and do not adjust for the other
> model covariates.
