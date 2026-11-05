# Analysis data dictionary

These are strict, tidy contracts for normalized files. Raw GENESIS exports remain unchanged under `data/raw/` and may require table-specific parsing before they satisfy these contracts.

## `diagnoses.csv`

One row per mutually exclusive year × geography × sex × diagnosis age band × ICD-10 three-character code.

| Column | Type | Definition |
|---|---|---|
| `year` | integer | Calendar year of discharge/statistic |
| `geography` | string | `Germany` or official Bundesland name |
| `sex` | category | `male` or `female`; never `total` alongside components |
| `age_group` | string | Stable canonical band, e.g. `65-69`; primary oldest band is `85+` |
| `icd10` | string | Three-character principal diagnosis code, e.g. `I60` |
| `cases` | number | Discharged patients/cases; missing if suppressed, never silently zero |
| `quality_flag` | string | Empty or a documented source sign. For diagnoses, `-` is retained while its officially defined “nothing present” value is represented numerically as zero. |
| `source_table` | string | `23131-0002` or `23131-0011` |

Unique key: `year, geography, sex, age_group, icd10`.

## `population_observed.csv`

One row per year × geography × sex × analysis age band.

| Column | Type | Definition |
|---|---|---|
| `year` | integer | Calendar year represented by the population reference date |
| `geography` | string | Same coding as diagnoses |
| `sex` | category | `male` or `female` |
| `age_group` | string | Exact analysis age band; primary oldest band is `85+` |
| `population` | number | Persons after applying any source unit multiplier |
| `source_table` | string | Official GENESIS table code |
| `census_basis` | string | `pre-Zensus 2011 basis` through 2010, `Zensus 2011` for 2011–2021, or `Zensus 2022` from 2022 |

Unique key: `year, geography, sex, age_group`.

## `population_projected.csv`

One row per horizon × geography × sex × analysis age band × official scenario.

| Column | Type | Definition |
|---|---|---|
| `year` | integer | Projection year (31 December reference) |
| `geography` | string | Same coding as diagnoses |
| `sex` | category | `male` or `female` |
| `age_group` | string | Exact analysis age band; primary oldest band is `85+` |
| `scenario` | string | Canonical scenario, primary `G2L2W2` |
| `population` | number | Persons, not thousands |
| `source_table` | string | `12421-0002` or `12421-0004` |
| `projection_vintage` | string | `16th coordinated projection; base 2024` |

Unique key: `year, geography, sex, age_group, scenario`.

## General conventions

- UTF-8 CSV with comma delimiter and dot decimal separator.
- Counts are numeric and nonnegative.
- Category totals are excluded when mutually exclusive components are present.
- ICD codes are stored without `ICD10-` prefixes or decimal subcodes at this proof-of-concept level.
- `quality_flag` preserves source suppression/quality signs, including diagnosis-table `-` structural-zero cells.
- Every processed dataset must be derivable from a checksummed raw file.
