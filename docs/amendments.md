# Prospective protocol amendments

## 5 November 2026: interpretation of the primary estimand

This amendment was made before official study data were acquired or any empirical result was observed.

The original protocol stated a null hypothesis that the aggregate 2035 projection gap was zero. This has been replaced by a prespecified directional expectation without a sampling-based hypothesis test. The analysis uses complete official hospital counts and conditional official population scenarios. A conventional null-hypothesis test would therefore attach sampling uncertainty to a contrast whose principal uncertainty arises from scenario assumptions, measurement, coding stability and rate constancy.

The primary output remains unchanged: the relative difference between the age/sex-structured projection and the population-only projection in 2035 under G2L2W2. The analysis will report the absolute and relative gap, alternative official scenarios, adjacent baseline years and rolling-origin prediction errors.

## 5 November 2026: backtest summary

The backtest summary now reports signed error, mean absolute error, mean absolute percentage error and weighted absolute percentage error by service line and forecast horizon. It produces an all-years analysis and a sensitivity analysis excluding target years 2020–2022. This operationalises analyses already specified in the statistical analysis plan.

## 5 November 2026: figure output standard

The primary projection-gap figure is exported as PDF, SVG and 600-dpi PNG. It uses directly labelled point estimates, contains no title inside the graphic and distinguishes the aggregate estimate with one muted accent colour. This changes presentation only, not the analysis.

## 5 November 2026: explicit structural-zero diagnosis cells

The diagnosis table is retrieved with GENESIS compression disabled. The compressed export omitted cells represented by `-` in the complete table. GENESIS defines this sign as “nothing present”, so these cells are represented numerically as zero while the original sign is retained in `quality_flag`. Other missing, uncertain or suppressed signs remain missing. This amendment prevents incomplete service-line denominator coverage and was made during source-format validation before interpretation of model outputs.

## 5 November 2026: post hoc analyses after the national results

These analyses were defined after the national primary results had been obtained and are reported as post hoc. They do not change the primary estimand.

1. **Aggregate excluding intracranial injury (S06).** S06 accounted for 72.7% of 2024 baseline discharges, so the prespecified aggregate largely reflects head injury admissions, many of which do not involve neurosurgical treatment. A second aggregate of the remaining seven service lines is reported alongside the primary aggregate.
2. **Same-census-basis backtests.** Origin/target pairs spanning the 2011 or 2022 census rebasing compare rates computed on different denominator bases. Backtest summaries were repeated using only pairs within one basis (pre-2011, 2011–2021, 2022 onward).
3. **Direct age/sex standardisation (2024 standard population), 2005–2024.** This describes whether age/sex-specific rates were historically stable, which is the central assumption of Model 1.
4. **Three-factor Shapley decomposition of observed change, 2011–2019.** Observed change in discharges is partitioned into population size, age/sex composition and age/sex-specific rates over the longest pre-pandemic interval on a single census basis.

Script: `scripts/run_posthoc.py`. Outputs: `outputs/tables/posthoc_*.csv`.

## 5 November 2026: ICD and table-definition audit

Script `scripts/run_icd_audit.py` reconciles stratum sums with official totals, flags year-on-year changes of at least 10% outside 2020–2021, and describes the composition of the 85+ age group. Results are summarised in `docs/icd_audit.md`.

## 5 November 2026: Bundesland extension implementation

`scripts/run_regional.py` implements the prespecified Bundesland extension with Land-specific 2024 rates; it was run on 5 November 2026 after authenticated retrieval of 23131-0011, 12411-0013 and 12421-0004. Two features of the source tables were established before interpretation: (1) table 23131-0011 assigns discharges to the Land of the treating hospital, as shown by comparison with the treatment-by-residence table 23131-0012, so regional rates are treatment-location rates; (2) the regional projection table uses variant variable BEVPR2 and exceeds the direct-retrieval limit, so it was retrieved one horizon year at a time for variants G2-L2-W1 to W3. The Land-level sum of 2024 discharges equals the national total; summed Land-level Model 1 projections differ from the national projection by −0.09% in 2035 for all study diagnoses (at most 0.5% for any service line in 2035 and 0.6% in 2040).

## 5 November 2026: additional analyses after internal review (post hoc)

The following analyses were added after internal review of the draft results. None changes the primary estimand.

1. **Procedure corroboration.** OPS codes 5-013, 5-015, 5-022 and 5-023 from table 23141-0102 (2019–2024), projected with the same two models and analysed separately (`scripts/run_ops.py`).
2. **All 27 variants of the 16th coordinated population projection** in place of the three migration variants (`scripts/run_extended_sensitivity.py`).
3. **Finer top-coding.** Separate rates for 85–89 years and 90 years or older, using Land-level population tables (to 90+) summed to Germany.
4. **Person-year denominators** (annual average population; mean of adjacent projected stocks).
5. **Rates by age only** (sexes combined), corresponding to planned sensitivity analysis 3.
6. **Catchment-weighted regional denominators** derived from the 2024 treatment-by-residence table 23131-0012.
7. **Backtest summaries by period of the target year**, with signed errors and the number of start years in which each approach was more accurate.

The planned sensitivity analysis by four-digit ICD-10 subcode was not possible because the published tables contain three-digit codes only. The analysis plan specified at least five years of data before the first backtest start year; the analysis started in 2009, the fifth year of data. The trend-adjusted count model and the geographic accessibility extension remain deferred.

## 5 November 2026: corrections after verification of release 1.0.0

- Rates by age only (item 5 above) implement planned sensitivity analysis 3 and are not a post hoc addition; the manuscript was corrected accordingly.
- The comparison of table 23131-0011 with the treatment-by-residence table 23131-0012, previously done outside the pipeline, is now computed in `scripts/run_extended_sensitivity.py` and written to `outputs/logs/extsens_run.json`. No result changed.
- `metadata/ops_codebook.csv` and `metadata/source_register.csv` were updated to the tables and procedure codes actually used; neither file is read by the analysis code.
