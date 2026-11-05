"""Population-only and age/sex-structured projection models."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from neurodemography.codebook import map_service_lines
from neurodemography.schemas import (
    validate_diagnoses,
    validate_population_observed,
    validate_population_projected,
)

STRATA = ["geography", "sex", "age_group"]


def average_rate_baseline(
    diagnoses: pd.DataFrame,
    population_observed: pd.DataFrame,
    *,
    start_year: int,
    end_year: int,
    reference_year: int,
) -> pd.DataFrame:
    """Construct reference-year pseudo-cases from mean stratum-specific rates.

    Rates are calculated separately for every geography, sex, age group and ICD-10
    code in each requested year, then averaged with equal weight across years. The
    mean rates are applied to the reference-year population so the returned rows can
    enter the otherwise unchanged projection pipeline.
    """

    diagnosis_rows = validate_diagnoses(diagnoses)
    population_rows = validate_population_observed(population_observed)
    years = set(range(int(start_year), int(end_year) + 1))
    if reference_year not in years:
        raise ValueError("reference_year must fall within the averaging window")
    for name, frame in (
        ("diagnoses", diagnosis_rows),
        ("population_observed", population_rows),
    ):
        missing = years.difference(frame["year"].unique())
        if missing:
            raise ValueError(f"{name} is missing averaging years: {sorted(missing)}")

    window = diagnosis_rows.loc[diagnosis_rows["year"].isin(years)].merge(
        population_rows.loc[population_rows["year"].isin(years), ["year", *STRATA, "population"]],
        on=["year", *STRATA],
        how="outer",
        validate="many_to_one",
        indicator=True,
    )
    incomplete = window["_merge"] != "both"
    if incomplete.any():
        example = window.loc[incomplete, ["year", *STRATA, "icd10", "_merge"]].head()
        raise ValueError(f"Diagnosis/population averaging strata do not align:\n{example}")
    window["rate"] = window["cases"] / window["population"]
    mean_rates = window.groupby([*STRATA, "icd10"], as_index=False, observed=True)["rate"].mean()

    reference = population_rows.loc[
        population_rows["year"] == reference_year, [*STRATA, "population"]
    ]
    baseline = mean_rates.merge(
        reference,
        on=STRATA,
        how="outer",
        validate="many_to_one",
        indicator=True,
    )
    incomplete = baseline["_merge"] != "both"
    if incomplete.any():
        example = baseline.loc[incomplete, [*STRATA, "icd10", "_merge"]].head()
        raise ValueError(f"Mean-rate/reference strata do not align:\n{example}")
    baseline["cases"] = baseline["rate"] * baseline["population"]
    baseline["year"] = int(reference_year)
    baseline["quality_flag"] = ""
    baseline["source_table"] = f"mean_rates_{start_year}_{end_year}"
    columns = [
        "year",
        "geography",
        "sex",
        "age_group",
        "icd10",
        "cases",
        "quality_flag",
        "source_table",
    ]
    return baseline[columns].sort_values(columns[:5]).reset_index(drop=True)


def _baseline_rates(
    diagnoses: pd.DataFrame,
    population: pd.DataFrame,
    codebook: pd.DataFrame,
    baseline_year: int,
) -> pd.DataFrame:
    diagnosis_rows = map_service_lines(validate_diagnoses(diagnoses), codebook)
    population_rows = validate_population_observed(population)
    diagnosis_rows = diagnosis_rows.loc[diagnosis_rows["year"] == baseline_year]
    population_rows = population_rows.loc[population_rows["year"] == baseline_year]
    if diagnosis_rows.empty or population_rows.empty:
        raise ValueError(
            f"No diagnosis/population data available for baseline year {baseline_year}"
        )

    cases = diagnosis_rows.groupby([*STRATA, "service_line"], as_index=False, observed=True)[
        "cases"
    ].sum()
    denominators = population_rows[[*STRATA, "population"]]
    merged = cases.merge(
        denominators,
        on=STRATA,
        how="outer",
        validate="many_to_one",
        indicator=True,
    )
    incomplete = merged["_merge"] != "both"
    if incomplete.any():
        example = merged.loc[incomplete, [*STRATA, "service_line", "_merge"]].head()
        raise ValueError(f"Baseline diagnosis/population strata do not align:\n{example}")
    merged = merged.drop(columns="_merge")
    merged["rate"] = merged["cases"] / merged["population"]
    return merged


def _future_strata(
    projected: pd.DataFrame,
    scenario: str,
    horizons: Iterable[int],
) -> pd.DataFrame:
    future = validate_population_projected(projected)
    years = sorted(set(int(year) for year in horizons))
    future = future.loc[(future["scenario"] == scenario) & (future["year"].isin(years))].copy()
    missing = set(years).difference(future["year"].unique())
    if missing:
        raise ValueError(f"Projection scenario {scenario} is missing horizons: {sorted(missing)}")
    return future


def project_models(
    diagnoses: pd.DataFrame,
    population_observed: pd.DataFrame,
    population_projected: pd.DataFrame,
    codebook: pd.DataFrame,
    *,
    baseline_year: int,
    horizons: Iterable[int],
    scenario: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run Models 0/1 and the two-factor Shapley decomposition."""

    rates = _baseline_rates(diagnoses, population_observed, codebook, baseline_year)
    future = _future_strata(population_projected, scenario, horizons)

    expanded = rates.merge(
        future[[*STRATA, "year", "scenario", "population"]],
        on=STRATA,
        how="outer",
        validate="many_to_many",
        suffixes=("_baseline", "_future"),
        indicator=True,
    )
    incomplete = expanded["_merge"] != "both"
    if incomplete.any():
        example = expanded.loc[incomplete, [*STRATA, "service_line", "year", "_merge"]].head()
        raise ValueError(f"Baseline and future population strata do not align:\n{example}")
    expanded = expanded.drop(columns="_merge")
    expanded["model_1_component"] = expanded["rate"] * expanded["population_future"]

    group = ["geography", "service_line", "year", "scenario"]
    estimates = expanded.groupby(group, as_index=False, observed=True).agg(
        baseline_cases=("cases", "sum"),
        baseline_population=("population_baseline", "sum"),
        future_population=("population_future", "sum"),
        model_1=("model_1_component", "sum"),
    )
    estimates["model_0"] = (
        estimates["baseline_cases"]
        * estimates["future_population"]
        / estimates["baseline_population"]
    )
    estimates = _append_aggregate_estimates(estimates)
    estimates["gap_absolute"] = estimates["model_1"] - estimates["model_0"]
    estimates["gap_relative_pct"] = 100 * estimates["gap_absolute"] / estimates["model_0"]
    estimates.insert(2, "baseline_year", baseline_year)
    estimates = estimates.rename(columns={"year": "horizon"})

    decomposition = _append_aggregate_decomposition(_shapley_decomposition(expanded, baseline_year))
    sort_columns = ["geography", "service_line", "horizon", "scenario"]
    return estimates.sort_values(sort_columns).reset_index(drop=True), decomposition


def _append_aggregate_estimates(estimates: pd.DataFrame) -> pd.DataFrame:
    """Add the prespecified aggregate across non-overlapping service lines."""

    group = ["geography", "year", "scenario"]
    aggregate = estimates.groupby(group, as_index=False, observed=True).agg(
        baseline_cases=("baseline_cases", "sum"),
        baseline_population=("baseline_population", "first"),
        future_population=("future_population", "first"),
        model_1=("model_1", "sum"),
        model_0=("model_0", "sum"),
    )
    aggregate.insert(1, "service_line", "all_prespecified")
    return pd.concat([estimates, aggregate], ignore_index=True)


def _shapley_decomposition(expanded: pd.DataFrame, baseline_year: int) -> pd.DataFrame:
    records: list[dict[str, float | int | str]] = []
    group = ["geography", "service_line", "year", "scenario"]
    for keys, rows in expanded.groupby(group, observed=True):
        geography, service_line, horizon, scenario = keys
        total_0 = rows["population_baseline"].sum()
        total_1 = rows["population_future"].sum()
        share_0 = rows["population_baseline"] / total_0
        share_1 = rows["population_future"] / total_1
        rates = rows["rate"].to_numpy()
        mean_rate_0 = float(np.dot(rates, share_0.to_numpy()))
        mean_rate_1 = float(np.dot(rates, share_1.to_numpy()))
        f00 = total_0 * mean_rate_0
        f10 = total_1 * mean_rate_0
        f01 = total_0 * mean_rate_1
        f11 = total_1 * mean_rate_1
        size = 0.5 * ((f10 - f00) + (f11 - f01))
        composition = 0.5 * ((f01 - f00) + (f11 - f10))
        records.append(
            {
                "geography": geography,
                "service_line": service_line,
                "baseline_year": baseline_year,
                "horizon": int(horizon),
                "scenario": scenario,
                "baseline_cases": f00,
                "projected_model_1": f11,
                "population_size_contribution": size,
                "age_sex_composition_contribution": composition,
                "reconstruction_error": (f11 - f00) - size - composition,
            }
        )
    return pd.DataFrame.from_records(records)


def _append_aggregate_decomposition(decomposition: pd.DataFrame) -> pd.DataFrame:
    group = ["geography", "baseline_year", "horizon", "scenario"]
    aggregate = decomposition.groupby(group, as_index=False, observed=True).agg(
        baseline_cases=("baseline_cases", "sum"),
        projected_model_1=("projected_model_1", "sum"),
        population_size_contribution=("population_size_contribution", "sum"),
        age_sex_composition_contribution=("age_sex_composition_contribution", "sum"),
        reconstruction_error=("reconstruction_error", "sum"),
    )
    aggregate.insert(1, "service_line", "all_prespecified")
    return pd.concat([decomposition, aggregate], ignore_index=True)


def backtest_models(
    diagnoses: pd.DataFrame,
    population_observed: pd.DataFrame,
    codebook: pd.DataFrame,
    *,
    horizons: Iterable[int] = (1, 3, 5),
    minimum_training_years: int = 5,
) -> pd.DataFrame:
    """Rolling-origin evaluation using observed target-year populations."""

    diagnosis_rows = validate_diagnoses(diagnoses)
    population_rows = validate_population_observed(population_observed)
    years = sorted(set(diagnosis_rows["year"]).intersection(population_rows["year"]))
    if len(years) <= minimum_training_years:
        raise ValueError("Insufficient shared years for rolling-origin backtesting")

    actual_mapped = map_service_lines(diagnosis_rows, codebook)
    actual = actual_mapped.groupby(
        ["year", "geography", "service_line"], as_index=False, observed=True
    )["cases"].sum()
    actual_aggregate = actual.groupby(["year", "geography"], as_index=False, observed=True)[
        "cases"
    ].sum()
    actual_aggregate["service_line"] = "all_prespecified"
    actual = pd.concat([actual, actual_aggregate], ignore_index=True)
    records: list[pd.DataFrame] = []
    first_origin_index = minimum_training_years - 1
    for origin in years[first_origin_index:]:
        for step in horizons:
            target = origin + int(step)
            if target not in years:
                continue
            projected = population_rows.loc[population_rows["year"] == target].copy()
            projected["scenario"] = "observed_target_population"
            estimates, _ = project_models(
                diagnosis_rows,
                population_rows,
                projected,
                codebook,
                baseline_year=origin,
                horizons=[target],
                scenario="observed_target_population",
            )
            evaluated = estimates.merge(
                actual.loc[actual["year"] == target, ["geography", "service_line", "cases"]],
                on=["geography", "service_line"],
                how="left",
                validate="one_to_one",
            ).rename(columns={"cases": "observed_cases"})
            evaluated.insert(3, "backtest_horizon_years", int(step))
            for model in ("model_0", "model_1"):
                evaluated[f"{model}_error"] = evaluated[model] - evaluated["observed_cases"]
                evaluated[f"{model}_absolute_error"] = evaluated[f"{model}_error"].abs()
                evaluated[f"{model}_ape_pct"] = np.where(
                    evaluated["observed_cases"] > 0,
                    100 * evaluated[f"{model}_absolute_error"] / evaluated["observed_cases"],
                    np.nan,
                )
            records.append(evaluated)
    if not records:
        raise ValueError("No evaluable rolling-origin pairs for requested horizons")
    return pd.concat(records, ignore_index=True)


def summarize_backtests(
    results: pd.DataFrame,
    *,
    disruption_years: Iterable[int] = (2020, 2021, 2022),
) -> pd.DataFrame:
    """Summarize backtests overall and after excluding disruption target years."""

    required = {
        "geography",
        "service_line",
        "horizon",
        "backtest_horizon_years",
        "observed_cases",
        "model_0_error",
        "model_0_absolute_error",
        "model_0_ape_pct",
        "model_1_error",
        "model_1_absolute_error",
        "model_1_ape_pct",
    }
    missing = required.difference(results.columns)
    if missing:
        raise ValueError(f"Backtest results are missing columns: {sorted(missing)}")
    if results.empty:
        raise ValueError("Backtest results are empty")

    excluded = {int(year) for year in disruption_years}
    analysis_sets = [("all_years", results)]
    sensitivity = results.loc[~results["horizon"].isin(excluded)].copy()
    if not sensitivity.empty:
        analysis_sets.append(("exclude_covid_2020_2022", sensitivity))

    summaries: list[pd.DataFrame] = []
    group = ["geography", "service_line", "backtest_horizon_years"]
    for label, frame in analysis_sets:
        summary = frame.groupby(group, as_index=False, observed=True).agg(
            model_0_mean_error=("model_0_error", "mean"),
            model_1_mean_error=("model_1_error", "mean"),
            model_0_mae=("model_0_absolute_error", "mean"),
            model_1_mae=("model_1_absolute_error", "mean"),
            model_0_mape=("model_0_ape_pct", "mean"),
            model_1_mape=("model_1_ape_pct", "mean"),
            model_0_absolute_error_total=("model_0_absolute_error", "sum"),
            model_1_absolute_error_total=("model_1_absolute_error", "sum"),
            observed_cases_total=("observed_cases", "sum"),
            evaluations=("observed_cases", "count"),
        )
        summary["model_0_wape"] = np.where(
            summary["observed_cases_total"] > 0,
            100 * summary.pop("model_0_absolute_error_total") / summary["observed_cases_total"],
            np.nan,
        )
        summary["model_1_wape"] = np.where(
            summary["observed_cases_total"] > 0,
            100 * summary.pop("model_1_absolute_error_total") / summary["observed_cases_total"],
            np.nan,
        )
        summary = summary.drop(columns="observed_cases_total")
        summary.insert(0, "analysis_set", label)
        summaries.append(summary)
    return pd.concat(summaries, ignore_index=True)
