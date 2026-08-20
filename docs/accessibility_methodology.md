# Paper 3 methodology

## Study design and unit of analysis

Paper 3 is a cross-sectional ecological analysis of 114 publicly accessible
blue-green waterfront sites in Metro Vancouver. The site is the spatial unit
for each accessibility outcome. Neighbourhood socioeconomic characteristics
are summarized within walking catchments around each site.

The 10-minute catchment is the main specification because it represents a
defensible neighbourhood walking scale while retaining substantially more
valid Census observations than five minutes. Five-, 20-, and 30-minute
catchments are sensitivity analyses. The 10-minute choice is conceptual and
was requested before final reporting; it was not selected by searching for the
smallest p-values.

## Accessibility outcomes

### Pedestrian access

```text
access points per kilometre of land-buffer boundary
```

The raw density is min-max scaled from zero to one within each catchment. It
measures the density of identified ways to enter a site, not entrance quality,
universal accessibility, or travel distance from every residence.

### Transit access

```text
number of bus stops inside the selected walk-time catchment
```

The count is min-max scaled within each catchment. It measures nearby transit
supply, not service frequency, reliability, fare affordability, or a complete
door-to-site transit journey.

### Combined physical access

```text
physical = (scaled pedestrian + scaled transit) / 2
```

This gives the two components equal nominal weight. Because their empirical
variances differ, it does not guarantee equal influence on variation in the
combined score. Pedestrian and transit models are therefore reported alongside
the combined outcome.

### Visual access

The implemented visual metric is:

```text
visible water area / total water area in the common 1 km analysis area
```

Values slightly above one from raster alignment are capped at one. Observer
points are generated hierarchically from paths using 100 m, 50 m, and 25 m
spacing, with 3–15 well-separated observers per site and access-point fallback
when necessary. A water cell is counted once if at least one observer can see
it. This measures potential visible-water extent, not perceived scenic quality.

### Haptic access

The main Avery-style measure is:

```text
shoreline-contact length / land-buffer perimeter
```

It is best described as shoreline exposure or potential shoreline contact. It
does not confirm that water is safely touchable or that fences, vegetation,
seawalls, or other barriers are absent. The DTM/OSM shoreline-approachability
measure remains a potential sensitivity outcome, not a replacement used in the
main regression.

### Multidimensional access

Physical, visual, and haptic scores are separately min-max scaled within each
catchment and averaged with equal weight:

```text
multidimensional = (scaled physical + scaled visual + scaled haptic) / 3
```

The approved proposal requires this aggregate model. It is retained as the
Paper 3 synthesis outcome and is the accessibility input passed to Paper 4.
Pedestrian, transit, combined physical, visual, and haptic outcomes remain in
the Paper 3 results to explain which dimensions contribute to the aggregate.

## Socioeconomic predictors

The five Census predictors are:

- principal accommodation expenditure;
- percentage of residents below the low-income threshold;
- percentage with a bachelor's degree or higher;
- percentage identifying as a visible minority; and
- percentage identifying as Indigenous.

All continuous outcome and predictor variables are standardized within each
catchment-specific analytical sample before regression. Coefficients therefore
represent standard-deviation changes, subject to the spatial-model caveats
below.

## Census data-quality rule

A record is eligible when:

1. `HasData == 1`;
2. all five predictors are present; and
3. it has no critical Census-quality flag.

Critical flags identify zero median-household-income values and related
impossible/extreme combinations that indicate failed or unreliable enrichment,
not real neighbourhood characteristics. This identical rule produces N=90,
105, 112, and 114 at 5, 10, 20, and 30 minutes.

## Site controls

Controlled models add:

- site type: beach, coastal waterfront without beach, lakefront, or riverfront;
  beach is the reference category; and
- natural log of land-buffer area, standardized within the analytical sample.

The two one-record proposal categories are collapsed before modelling:
`beach + coastal promenade` becomes beach, and `coastal promenade` becomes
coastal waterfront without beach.

Land-buffer area excludes adjacent water. This controls for differences in the
terrestrial site footprint. Because area and geometry are involved in several
accessibility constructions, baseline and controlled models answer different
questions: the baseline is the total observed association, whereas the
controlled model compares sites of similar type and land-buffer area.

## Spatial representation and weights

Each site is represented by a point created from `allparks_land_buffer` using
ArcGIS `FeatureToPoint` with the `INSIDE` option. These points are used only for
spatial-neighbour calculations. They are not catchment origins, access points,
or geometric centroids.

Spatial weights use row-standardized k-nearest neighbours. The workflow begins
with the requested minimum k=6, finds the smallest k that connects every
catchment sample, and applies one common value to all models. The current data
require k=7 because the 30-minute 114-site graph has two components at k=6.

## Regression and spatial-model procedure

For every catchment and outcome:

1. fit standardized OLS with the five socioeconomic predictors;
2. test OLS residuals using two-sided Moran's I;
3. retain OLS when residual Moran p is at least .05;
4. otherwise fit SAR lag and SAR error candidates;
5. among candidates that remove residual autocorrelation, select the one with
   the lowest AIC; and
6. add site type and log area using the selected baseline family for the
   initial direct comparison; and
7. if the controlled residual Moran p is below .05, reselect from controlled
   OLS/SAR candidates and report the spatially adequate controlled model.

Controlled-family reselection currently affects the multidimensional model at
5 and 10 minutes and the 30-minute transit sensitivity.

At 10 minutes, the main selected families are:

| Outcome | Baseline family | Controlled family |
|---|---|---|
| Pedestrian | SAR lag | SAR lag |
| Transit | SAR error | SAR error |
| Combined physical | SAR error | SAR error |
| Visual | SAR lag | SAR lag |
| Haptic | OLS | OLS |
| Multidimensional | OLS | SAR error |

The SAR lag/error AIC differences are below two for the main spatial outcomes.
Consequently, the chosen family follows a reproducible rule but should not be
interpreted as proof of a particular spatial-generating mechanism.

## Statistical inference

- OLS uses HC3 heteroskedasticity-robust standard errors.
- SAR coefficients use model-based standard errors.
- SAR-lag models also export direct, indirect, and total impacts because raw
  structural coefficients are not total marginal effects.
- The main controlled table contains 30 socioeconomic tests. Raw p-values are
  shown for comparability with the requested table, and Benjamini–Hochberg
  q-values are exported as a multiple-testing check.
- VIF is calculated from the controlled design matrix. The current maximum is
  2.83, below the conventional concern threshold of five.

All results are associations. The cross-sectional design, catchment
aggregation, and non-random siting of waterfronts do not support causal claims.

## Pairwise dimension analysis

Physical, visual, and haptic scores are compared across all 114 sites using:

- Pearson correlation;
- Spearman rank correlation;
- exact sample size;
- vertical and horizontal median reference lines; and
- standardized dimension differences to identify extreme/divergent sites.

These scatterplots are appropriate because the dimensions are distinct but
comparable site scores. Bland–Altman plots are not used as a main result because
they are intended for methods measuring the same quantity. Ternary and radar
plots may be retained only as exploratory supplements.

## Departures from the approved proposal

The final Methods must describe the implementation rather than repeat the
proposal verbatim. Major refinements are:

- 114 sites rather than the proposal's 95/96;
- walking catchments rather than only adjacent/intersecting Dissemination Areas;
- separate pedestrian and transit components rather than one feature total
  divided by site area;
- path-based 3–15 observer points and visible-water union rather than five
  random viewpoints and their average;
- an explicit, reproducible OLS/SAR selection procedure; and
- five component outcomes are reported alongside the proposal's aggregate
  multidimensional outcome, which is also passed to Paper 4.

These refinements should be justified as improvements in construct clarity,
data coverage, observer placement, and reproducibility—not presented as if
they were specified unchanged in the original proposal.
