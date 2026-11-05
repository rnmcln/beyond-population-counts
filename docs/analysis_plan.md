# Statistical analysis plan

## Notation

Let `c[d,a,s,g,t]` be inpatient cases for diagnosis/service line `d`, age band `a`, sex `s`, geography `g`, and year `t`. Let `N[a,s,g,t]` be the corresponding observed or projected population. The baseline year is `t0 = 2024`; future horizons are `h ∈ {2030, 2035, 2040}`; the primary scenario is G2-L2-W2.

The implementation excludes published total categories whenever their components are used, preventing double counting.

## Model 0: population-only projection

For each diagnosis/service line and geography:

```text
C0[d,g,h] = C[d,g,t0] × N[g,h] / N[g,t0]
```

where `C[d,g,t0]` and `N[g,t0]` are totals across the mutually exclusive age/sex strata used by Model 1.

## Model 1: age/sex-structured constant-rate projection

Baseline stratum-specific utilization rates are:

```text
r[d,a,s,g,t0] = c[d,a,s,g,t0] / N[a,s,g,t0]
```

Projected utilization is:

```text
C1[d,g,h] = Σ(a,s) r[d,a,s,g,t0] × N[a,s,g,h]
```

Rates are carried forward unchanged. This is a standardization exercise, not a claim that clinical practice, coding, access, or incidence will remain fixed.

## Primary outcome

At 2035:

```text
Gap[d,g,2035] = C1[d,g,2035] − C0[d,g,2035]
Relative gap (%) = 100 × Gap / C0
```

The primary aggregate result sums mutually exclusive diagnosis/service lines before calculating the relative gap. `C70–C72` is consolidated once; descendants/parent categories must not be counted together.

## Shapley decomposition

Write population as total `T` times stratum shares `q`, and define `f(T,q)=T×Σ r_i q_i`. The change from baseline to future is allocated symmetrically:

```text
size = 0.5×[(f(T1,q0)−f(T0,q0)) + (f(T1,q1)−f(T0,q1))]
composition = 0.5×[(f(T0,q1)−f(T0,q0)) + (f(T1,q1)−f(T1,q0))]
```

The two contributions sum exactly to `C1 − baseline cases`. A later trend model may add rate change as another player; its Shapley implementation will be prespecified before use.

## Rolling-origin backtesting

For every origin with at least five earlier observed years and every evaluable 1-, 3-, and 5-year horizon:

1. Estimate origin-year rates.
2. Use the observed target-year population in place of the future population.
3. Predict target-year cases under Models 0 and 1.
4. Compare against observed cases using absolute error, absolute percentage error (only when observed > 0), signed error, and aggregate weighted absolute percentage error.

Model comparison will report all eligible origins, including 2020–2022, with sensitivity analyses excluding the COVID-19 disruption years.

## Missing data and suppression

- Official `-`, `.`, suppressed, or unknown cells are missing unless documentation establishes a structural zero.
- No imputation is performed in the primary analysis.
- A stratum missing any numerator or denominator required by Model 1 fails validation and is listed in the run log.
- Sparse-cell pooling may be evaluated only as a labelled sensitivity analysis.

## Planned sensitivity analyses

1. Alternative official population scenarios, including G2-L2-W1 and G2-L2-W3.
2. Adjacent baseline years and multi-year baseline-rate averages.
3. Sex-stratified versus age-only standardization.
4. Exclude 2020–2022 when evaluating temporal performance.
5. Harmonize age bands to the coarsest stable definition across all source years.
6. Germany totals calculated directly versus sum of Länder.
7. Diagnosis hierarchy handling and inclusion/exclusion of unspecified subcodes.
8. Explicit break analysis around the 2022 census population rebasing.

## Deferred model

After Models 0/1 pass validation, fit a diagnosis-specific negative-binomial model with log population offset, age, sex, calendar-time terms, and prespecified interactions. Overdispersion, nonlinearity, breakpoints, and out-of-sample calibration must be assessed. It is not implemented in the first proof of concept.

## Planned displays

1. Flow diagram of data construction and exclusions.
2. Historical utilization rates by age/sex and diagnosis.
3. Model 0 versus Model 1 projections for 2030/2035/2040.
4. 2035 relative projection gap by diagnosis.
5. Shapley contributions by diagnosis and geography.
6. Rolling-origin error comparison for Models 0/1.
