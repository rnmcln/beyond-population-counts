# Population ageing and inpatient care for neurosurgically relevant conditions in Germany to 2040: age-structured versus population-based projections

Analysis code and documentation for the study of the same title.

**Author:** Aaron Lawson McLean (ORCID [0000-0001-5528-6905](https://orcid.org/0000-0001-5528-6905))

Department of Neurosurgery, Jena University Hospital, Friedrich Schiller University Jena, Jena, Germany; Comprehensive Cancer Centre Central Germany, Jena Campus, Jena, Germany

**Correspondence:** Aaron Lawson McLean, Computational Neuro-Oncology and Health Intelligence Lab, Department of Neurosurgery, Jena University Hospital, Am Klinikum 1, 07747 Jena, Germany. aaron.lawsonmclean@med.uni-jena.de

## Summary

Projections of neurosurgical caseload often scale current activity by population size. In Germany the population is ageing while its total size changes little, so projections based on population size and projections based on age-specific utilisation can diverge. The study compared the two approaches for eight diagnosis groups commonly managed by cranial neurosurgical services (ICD-10-GM C70–C72, D32, D33, G91, I60, I61, I62 and S06) and four cranial procedure codes (OPS 5-013, 5-015, 5-022 and 5-023), nationally and for the 16 federal states, and tested both approaches against observed utilisation from 2010 to 2024.

Discharges in 2024 were projected to 2030, 2035 and 2040 under the 16th coordinated population projection of the Federal Statistical Office, either in proportion to total population (population-based) or by applying 2024 age- and sex-specific rates to the projected population (age-structured). Projected change was decomposed into the contributions of population size and age structure, and past change (2011–2019) into population size, age structure and age-specific rates.

Of 358,758 discharges with a study diagnosis in 2024, 49.5% concerned patients aged 65 years or older. By 2035, the population-based projection fell by 1.9% and the age-structured projection rose by 2.9%, a difference of 4.9% (8.6% excluding intracranial injury). The difference was largest for hydrocephalus (14.7%), subdural and other nontraumatic intracranial haemorrhage (14.3%) and intracerebral haemorrhage (11.4%), and was 11.1% for incision of brain and meninges, which includes evacuation of subdural haematoma. It was positive in every federal state and under all 27 population projection variants. In historical tests, the age-structured approach was more accurate for pre-pandemic target years but less accurate for diagnosis groups whose age-specific rates declined.

All numbers above are produced by the code in this repository.

## Repository structure

```
config/analysis.toml           baseline year, horizons, scenario and paths
src/neurodemography/           tested analysis library (parsing, age groups, models)
scripts/                       acquisition, preparation, analysis, tables and figures
tests/                         unit tests with synthetic data
metadata/                      diagnosis and procedure codebooks, source register, data dictionary
metadata/retrieval_manifests/  parameters, dates and SHA-256 checksums of every download used
data/README.md                 how to obtain the source data
data/SHA256SUMS                checksums of the source files used for the published analysis
docs/                          protocol, analysis plan, amendments and data audit
Makefile                       complete pipeline
```

No source data are included. The data are published by the Federal Statistical Office of Germany; `data/README.md` lists every table, how to obtain it and how the scripts use it.

## Reproducing the analysis

1. Install Python 3.12 and [uv](https://docs.astral.sh/uv/), then run `make setup` to create the locked environment.
2. Register for a free GENESIS-Online account and create a personal API token (see `data/README.md`). Copy `.env.example` to `.env` and enter the token.
3. Download the source tables with `make data`, and compare them with the published checksums: `sha256sum -c data/SHA256SUMS`. File names contain the retrieval date; the checksums apply to the files used for the published analysis.
4. Run `make all`. This lints and tests the code, normalises the downloads into `data/processed/`, runs all analyses and writes tables to `outputs/tables/`, manuscript tables to `outputs/manuscript_tables/` and figures to `outputs/figures/manuscript/`.

A full run of `make all` takes about four minutes on a single core.

### Pipeline

| Make target | Script | Content |
|---|---|---|
| `data` | `acquire_genesis.py` | downloads all source tables with the parameters in `metadata/retrieval_manifests/` |
| `inputs` | `prepare_inputs.py` | national diagnoses, observed and projected population in a common format (20 age groups, 85+) |
| `validate` | `validate_inputs.py` | schema and key checks |
| `models` | `run_models_01.py` | population-based and age-structured projections; decomposition |
| `backtest` | `run_backtest.py` | rolling-origin evaluation at 1, 3 and 5 years |
| `sensitivities` | `run_sensitivities.py` | migration variants, baseline years, mean rates 2022–2024, census rebasing |
| `posthoc` | `run_posthoc.py` | aggregate excluding S06, census-basis backtests, standardised rates, decomposition 2011–2019 |
| `audit` | `run_icd_audit.py` | reconciliation with official totals, discontinuities, composition of the 85+ group |
| `procedures` | `run_ops.py` | projections for OPS 5-013, 5-015, 5-022 and 5-023 |
| `regional` | `run_regional.py`, `make_regional_outputs.py` | federal-state projections and summary |
| `extended` | `run_extended_sensitivity.py` | all 27 population variants, finer top-coding, person-year denominators, age-only rates, catchment-weighted regional denominators, backtests by period |
| `tables`, `figures` | `make_tables.py`, `make_manuscript_tables_md.py`, `make_manuscript_figures.py` | manuscript tables and figures |

### Reproducibility notes

- The environment is pinned in `uv.lock`. The analysis is deterministic and uses no random numbers.
- Regenerated tables are identical to those used for the paper when the files listed in `data/SHA256SUMS` are used; a few tables differ in the last floating-point digit between platforms.
- Figures are exported as PDF, SVG and 600-dpi PNG with fixed metadata. They use Arial or the metric-compatible Liberation Sans; the script stops if neither is installed.
- GENESIS tables can be revised by the publisher. A new download may then differ from the checksummed files and produce slightly different results.
- Departures from the protocol are listed in `docs/amendments.md`.

## Licence

Code: MIT licence (`LICENSE`). The source data remain subject to the terms of the Federal Statistical Office of Germany (see `data/README.md`).

## Citation

Please cite the study and this repository; `CITATION.cff` contains the repository metadata.
