import pandas as pd
import pytest

from neurodemography.models import (
    average_rate_baseline,
    backtest_models,
    project_models,
    summarize_backtests,
)


def _codebook() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "service_line": ["haemorrhage"],
            "code_start": ["I60"],
            "code_end": ["I60"],
        }
    )


def _baseline_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    strata = [(sex, age) for sex in ("male", "female") for age in ("20-24", "85+")]
    diagnoses = pd.DataFrame(
        [
            {
                "year": 2024,
                "geography": "Germany",
                "sex": sex,
                "age_group": age,
                "icd10": "I60",
                "cases": 5 if age == "20-24" else 10,
            }
            for sex, age in strata
        ]
    )
    observed = pd.DataFrame(
        [
            {
                "year": 2024,
                "geography": "Germany",
                "sex": sex,
                "age_group": age,
                "population": 500,
            }
            for sex, age in strata
        ]
    )
    projected = pd.DataFrame(
        [
            {
                "year": 2035,
                "geography": "Germany",
                "sex": sex,
                "age_group": age,
                "scenario": "G2L2W2",
                "population": 400 if age == "20-24" else 600,
            }
            for sex, age in strata
        ]
    )
    return diagnoses, observed, projected


def test_model_1_captures_composition_change_and_shapley_reconstructs() -> None:
    diagnoses, observed, projected = _baseline_inputs()
    estimates, decomposition = project_models(
        diagnoses,
        observed,
        projected,
        _codebook(),
        baseline_year=2024,
        horizons=[2035],
        scenario="G2L2W2",
    )
    row = estimates.loc[estimates["service_line"] == "haemorrhage"].iloc[0]
    assert row["baseline_cases"] == pytest.approx(30)
    assert row["model_0"] == pytest.approx(30)
    assert row["model_1"] == pytest.approx(32)
    assert row["gap_relative_pct"] == pytest.approx(100 * 2 / 30)
    shapley = decomposition.loc[decomposition["service_line"] == "haemorrhage"].iloc[0]
    assert shapley["population_size_contribution"] == pytest.approx(0)
    assert shapley["age_sex_composition_contribution"] == pytest.approx(2)
    assert shapley["reconstruction_error"] == pytest.approx(0)


def test_rolling_origin_model_1_is_exact_for_constant_rates() -> None:
    diagnosis_rows = []
    population_rows = []
    for year in range(2010, 2017):
        for sex in ("male", "female"):
            for age, population, rate in (
                ("20-24", 500 - 10 * (year - 2010), 0.01),
                ("85+", 500 + 10 * (year - 2010), 0.02),
            ):
                population_rows.append(
                    {
                        "year": year,
                        "geography": "Germany",
                        "sex": sex,
                        "age_group": age,
                        "population": population,
                    }
                )
                diagnosis_rows.append(
                    {
                        "year": year,
                        "geography": "Germany",
                        "sex": sex,
                        "age_group": age,
                        "icd10": "I60",
                        "cases": population * rate,
                    }
                )
    result = backtest_models(
        pd.DataFrame(diagnosis_rows),
        pd.DataFrame(population_rows),
        _codebook(),
        horizons=[1],
        minimum_training_years=5,
    )
    assert len(result) == 4
    assert (result["model_1_absolute_error"] < 1e-10).all()


def test_average_rate_baseline_averages_rates_not_counts() -> None:
    diagnoses = pd.DataFrame(
        [
            {
                "year": 2023,
                "geography": "Germany",
                "sex": "female",
                "age_group": "85+",
                "icd10": "I60",
                "cases": 10,
            },
            {
                "year": 2024,
                "geography": "Germany",
                "sex": "female",
                "age_group": "85+",
                "icd10": "I60",
                "cases": 40,
            },
        ]
    )
    population = pd.DataFrame(
        [
            {
                "year": 2023,
                "geography": "Germany",
                "sex": "female",
                "age_group": "85+",
                "population": 100,
            },
            {
                "year": 2024,
                "geography": "Germany",
                "sex": "female",
                "age_group": "85+",
                "population": 200,
            },
        ]
    )
    result = average_rate_baseline(
        diagnoses,
        population,
        start_year=2023,
        end_year=2024,
        reference_year=2024,
    )
    assert result.loc[0, "cases"] == pytest.approx(30)
    assert result.loc[0, "source_table"] == "mean_rates_2023_2024"


def test_backtest_summary_reports_wape_and_covid_sensitivity() -> None:
    results = pd.DataFrame(
        {
            "geography": ["Germany"] * 3,
            "service_line": ["haemorrhage"] * 3,
            "horizon": [2019, 2020, 2023],
            "backtest_horizon_years": [1, 1, 1],
            "observed_cases": [100, 200, 100],
            "model_0_error": [10, 100, -10],
            "model_0_absolute_error": [10, 100, 10],
            "model_0_ape_pct": [10, 50, 10],
            "model_1_error": [0, 40, 0],
            "model_1_absolute_error": [0, 40, 0],
            "model_1_ape_pct": [0, 20, 0],
        }
    )
    summary = summarize_backtests(results)
    overall = summary.loc[summary["analysis_set"] == "all_years"].iloc[0]
    sensitivity = summary.loc[summary["analysis_set"] == "exclude_covid_2020_2022"].iloc[0]
    assert overall["model_0_wape"] == pytest.approx(30)
    assert overall["model_1_wape"] == pytest.approx(10)
    assert sensitivity["evaluations"] == 2
    assert sensitivity["model_1_wape"] == pytest.approx(0)
