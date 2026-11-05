# Study protocol

## Title

**Beyond Population Counts: Age-Structured Projections and Utilization-Weighted Geographic Access to Neurosurgical Care in Germany, 2005–2040**

## Rationale

Hospital planning often treats total population size, historical activity, and catchment size as interchangeable proxies for future service requirements. They can diverge substantially when utilization is age-dependent and population structure changes. Neurosurgically relevant inpatient care is an informative case because many disease domains have strongly age-patterned utilization.

This study projects observed inpatient utilization. It does **not** estimate clinical need, appropriateness, unmet need, or capacity requirements. Those require additional assumptions and data.

## Primary objective and expectation

Estimate the 2035 **population-only projection gap**: the relative difference between age/sex-structured projected utilization (Model 1) and utilization projected only by total population change (Model 0), for the prespecified diagnosis set under the 16th coordinated population projection, variant G2-L2-W2.

The prespecified directional expectation is that Model 1 projects greater aggregate utilization than Model 0 because ageing increases the population weights of high-utilization strata. This expectation will not be tested with a sampling-based null-hypothesis test. The inputs are complete official counts and conditional population scenarios, so the primary analysis reports the magnitude and direction of the scenario contrast.

The primary estimand is descriptive and scenario-conditional; no sampling-based confidence interval will be attached to the official population scenario itself.

## Secondary objectives

1. Repeat projections for 2030 and 2040.
2. Estimate diagnosis/service-line-specific gaps.
3. Evaluate Models 0/1 using rolling-origin backtesting on observed historical data.
4. Decompose projected change into total-population-size and age/sex-composition components with a symmetric Shapley allocation.
5. Repeat at Bundesland level where numerator and denominator tables can be aligned.
6. In a later phase, fit a trend-adjusted negative-binomial model after validating the simpler models and assessing coding discontinuities.
7. Optionally extend to utilization-weighted geographic accessibility using Zensus 2022 population grids and Bundes-Klinik-Atlas hospital sites.

## Data sources

### Diagnoses

- GENESIS `23131-0002`: hospital patients, Germany, year, sex, age group, principal diagnosis ICD-10 (1–3 digit hierarchy).
- GENESIS `23131-0011`: corresponding Bundesland, year, sex, age group, principal diagnosis table, required for the regional extension.

The outcome is discharged patients/cases as defined by the table, not unique persons and not disease incidence.

### Procedures (deferred validation phase)

Preserved source tables: `23141-0102`, `23141-0103`, `23141-0110`, `23141-0111`.

Candidate OPS families: `5-014`, `5-015`, `5-022`, `5-023`, `5-024`, `5-025`, `5-026`, `5-027`, `5-028`, `5-035`, `5-831`, `5-836`, `5-837`, `5-838`, `5-839`, `5-83b`.

OPS analyses are not allowed to become the primary proof of concept until table semantics, double counting, version changes, and aggregation rules have been reviewed.

### Population denominators

- Observed Germany by sex and single year of age: GENESIS `12411-0006` (with all nationalities/family statuses selected) or an equivalently documented official export.
- Observed Bundesländer by sex and single year of age: GENESIS `12411-0013`.
- Projected Germany by sex and single year of age: GENESIS `12421-0002`.
- Projected Bundesländer by sex and single year of age: GENESIS `12421-0004`.
- Projection: 16th coordinated population projection, base 31 December 2024, years 2025–2070; primary variant G2-L2-W2.

Single ages must be aggregated to mutually compatible diagnosis/denominator bands. GENESIS `12411-0006` currently top-codes the oldest national observed-population category at 85 years and over, whereas the diagnosis table is finer at older ages. The primary national analysis therefore combines all diagnosis and projection cells aged 85 years and over unless a documented finer official baseline denominator is obtained. The regional analysis must use the same 85+ grouping for comparability. Population counts published in thousands must be multiplied by 1,000 before rates are calculated.

## Prespecified diagnosis proof-of-concept set

- `C70–C72`: malignant neoplasms of meninges, brain, and other parts of central nervous system
- `D32`: benign neoplasm of meninges
- `D33`: benign neoplasm of brain and other parts of central nervous system
- `G91`: hydrocephalus
- `I60`: nontraumatic subarachnoid haemorrhage
- `I61`: nontraumatic intracerebral haemorrhage
- `I62`: other nontraumatic intracranial haemorrhage
- `S06`: intracranial injury

Selection is a service-planning proof of concept, not a definition of the complete neurosurgical workload. Diagnosis does not prove that a neurosurgical procedure or consultation occurred.

## Scope decisions

- Diagnosis-based pipeline first.
- Models 0 and 1 first.
- Germany primary; Bundesland secondary.
- Negative-binomial secular-trend model later.
- Geospatial access later and explicitly labelled utilization-weighted accessibility.
- Scenario variants are sensitivity analyses, not confidence bounds.

## Governance and reproducibility

Every source file must retain provenance, retrieval date, official table code, selection, hash, and licence/attribution. Analysis changes after outcome inspection must be labelled amendments. Suppression, structural breaks, ICD/OPS revisions, the 2022 census rebasing, and the COVID-19 period require explicit sensitivity analyses.
