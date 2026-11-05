# ICD-10 and table-definition audit

**Date:** 5 November 2026
**Source:** GENESIS-Online table 23131-0002, uncompressed flat-file extract (SHA-256 `99a14b3c…05bdc`), 2005–2024
**Script:** `scripts/run_icd_audit.py`

## Unit of observation

The value variable is GES025, *Entlassene Patienten*: patients discharged after full inpatient treatment, including in-hospital deaths and same-day (*Stunden-*) cases. The unit is the hospital episode, not the person; readmissions are counted separately. The diagnosis is the principal diagnosis (*Hauptdiagnose*) at three-digit ICD-10-GM level. Secondary diagnoses are not represented. Geography is Germany as a whole.

## Hierarchy and overlap

All ten study codes are three-digit categories at the same hierarchical level (variable ICD10C). No parent chapter or two-digit block is combined with a component. C70, C71 and C72 are summed into one service line; all other service lines correspond to one code. The ten codes are mutually exclusive, so the aggregate contains no double counting.

## Reconciliation with official totals

For every year and code, the sum of the 40 sex-by-age strata was compared with the official total. Differences ranged from −90 to 0 discharges (maximum 90 for S06; at most 6 for every other code). The shortfall represents discharges with unknown sex or age, which cannot be allocated to strata. Its maximum is 0.03% of annual S06 discharges, so it was not imputed.

## Quality signs

The uncompressed extract contained 509 cells marked `-` (“nothing present”). These were coded as structural zeros: 286 for C70, 91 for C72, 57 for D32, 45 for D33, 16 for I60, 7 for G91, 5 for C71 and 2 for I62. No suppression or uncertainty signs were present. (The normalised analysis file holds 353 such cells after the 85–89, 90–94 and 95+ groups were combined into 85+.)

## Discontinuities

Year-on-year changes of at least 10% outside 2020–2021 were flagged.

- C70 and C72 are small series (300–1,250 discharges per year) with repeated fluctuations of 10–23%; these are consistent with random variation at low counts. Both are pooled with C71 in the analysis.
- I62 rose by 10.1% in 2008, during a period of steady growth (2005–2013). It fell by 19.2% between 2018 and 2019 (11,619 to 9,383). The decline was similar in every age group from 50 years upward (−11% to −22%) and did not reverse. The age pattern argues against a demographic explanation and points to a change in diagnostic coding or classification practice. Its source was not identified. The discontinuity predates the 2022–2024 baseline period and affects only backtests whose origin precedes 2019.
- No other study code had a non-pandemic year-on-year change of at least 10%.

## Pandemic period

Discharges fell in 2020 for every study code except C70. The total for the study diagnoses fell by 13.5%, driven mainly by S06 (−16.0%) and G91 (−16.9%). By 2024, S06 discharges had recovered to 91.8% of the 2019 level and G91 discharges to 89.0%.

## Census rebasing

Observed population denominators change basis in 2011 (Zensus 2011) and 2022 (Zensus 2022). The 2011 rebasing reduced the recorded population by 1.74%, which raised the crude utilisation rate by 3.43%. Backtests were therefore repeated within single census bases (post hoc; `docs/amendments.md`).

## Age top-coding

The observed population denominator ends at 85+, whereas the diagnosis table distinguishes 85–89, 90–94 and 95+. In 2024 the 85+ group accounted for 20.3% of S06 discharges, 25.6% of I62 discharges and 19.8% of I61 discharges. Within 85+, the share aged 90 or older was 38.4% for S06 and about 28% for I60–I62. The primary model therefore assumes a constant internal age structure within the 85+ group. A sensitivity analysis with separate rates for 85–89 years and 90 years or older, using Land-level population tables summed to Germany, is implemented in `scripts/run_extended_sensitivity.py`.
