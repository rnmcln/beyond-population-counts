#!/usr/bin/env python3
"""Run prespecified population-scenario and adjacent-baseline sensitivities."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd

from neurodemography.codebook import load_diagnosis_codebook
from neurodemography.config import load_config, resolve_project_path
from neurodemography.models import average_rate_baseline, project_models
from neurodemography.schemas import validate_diagnoses, validate_population_observed


def census_rebasing_diagnostics(
    diagnoses: pd.DataFrame,
    observed: pd.DataFrame,
) -> pd.DataFrame:
    """Summarise national totals and discontinuities around census-basis changes."""

    diagnosis_rows = validate_diagnoses(diagnoses)
    population_rows = validate_population_observed(observed)
    cases = diagnosis_rows.groupby(["year", "geography"], as_index=False, observed=True)[
        "cases"
    ].sum()
    population = population_rows.groupby(
        ["year", "geography", "census_basis"], as_index=False, observed=True
    )["population"].sum()
    result = cases.merge(
        population,
        on=["year", "geography"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    incomplete = result["_merge"] != "both"
    if incomplete.any():
        raise ValueError("Diagnosis and population years do not align for census diagnostics")
    result = result.drop(columns="_merge").sort_values(["geography", "year"])
    result["crude_rate_per_100000"] = 100_000 * result["cases"] / result["population"]
    grouped = result.groupby("geography", observed=True)
    result["population_change_pct"] = 100 * grouped["population"].pct_change()
    result["cases_change_pct"] = 100 * grouped["cases"].pct_change()
    result["crude_rate_change_pct"] = 100 * grouped["crude_rate_per_100000"].pct_change()
    previous_basis = grouped["census_basis"].shift()
    result["census_basis_transition"] = previous_basis.notna() & result["census_basis"].ne(
        previous_basis
    )
    return result.reset_index(drop=True)


def main() -> None:
    config = load_config()
    study = config["study"]
    paths = config["paths"]
    horizons = sorted({*study["secondary_horizons"], study["primary_horizon"]})
    diagnoses = pd.read_csv(resolve_project_path(paths["diagnoses"]))
    observed = pd.read_csv(resolve_project_path(paths["population_observed"]))
    projected = pd.read_csv(resolve_project_path(paths["population_projected"]))
    codebook = load_diagnosis_codebook(resolve_project_path(paths["diagnosis_codebook"]))

    scenarios = sorted(projected["scenario"].dropna().unique())
    scenario_results = []
    for scenario in scenarios:
        estimates, _ = project_models(
            diagnoses,
            observed,
            projected,
            codebook,
            baseline_year=study["baseline_year"],
            horizons=horizons,
            scenario=scenario,
        )
        scenario_results.append(estimates)

    baseline_years = [
        study["baseline_year"] - 2,
        study["baseline_year"] - 1,
        study["baseline_year"],
    ]
    baseline_results = []
    for baseline_year in baseline_years:
        estimates, _ = project_models(
            diagnoses,
            observed,
            projected,
            codebook,
            baseline_year=baseline_year,
            horizons=horizons,
            scenario=study["projection_scenario"],
        )
        baseline_results.append(estimates)

    averaging_start = study["baseline_year"] - 2
    averaged_diagnoses = average_rate_baseline(
        diagnoses,
        observed,
        start_year=averaging_start,
        end_year=study["baseline_year"],
        reference_year=study["baseline_year"],
    )
    multi_year_results, _ = project_models(
        averaged_diagnoses,
        observed,
        projected,
        codebook,
        baseline_year=study["baseline_year"],
        horizons=horizons,
        scenario=study["projection_scenario"],
    )
    multi_year_results.insert(
        3,
        "rate_window",
        f"{averaging_start}-{study['baseline_year']}",
    )
    census_diagnostics = census_rebasing_diagnostics(diagnoses, observed)

    table_dir = resolve_project_path(paths["output_tables"])
    log_dir = resolve_project_path(paths["output_logs"])
    table_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    scenario_path = table_dir / "scenario_sensitivity.csv"
    baseline_path = table_dir / "baseline_year_sensitivity.csv"
    multi_year_path = table_dir / "multi_year_rate_sensitivity.csv"
    census_path = table_dir / "census_rebasing_diagnostics.csv"
    pd.concat(scenario_results, ignore_index=True).to_csv(scenario_path, index=False)
    pd.concat(baseline_results, ignore_index=True).to_csv(baseline_path, index=False)
    multi_year_results.to_csv(multi_year_path, index=False)
    census_diagnostics.to_csv(census_path, index=False)

    manifest = {
        "run_at_utc": datetime.now(UTC).isoformat(),
        "scenarios": scenarios,
        "baseline_years": baseline_years,
        "multi_year_rate_window": [averaging_start, study["baseline_year"]],
        "horizons": horizons,
        "language_boundary": "inpatient utilization; not clinical need",
    }
    (log_dir / "sensitivity_run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(scenario_path)
    print(baseline_path)
    print(multi_year_path)
    print(census_path)


if __name__ == "__main__":
    main()
