from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from neurodemography.plotting import (
    backtest_performance_figure,
    primary_projection_gap_figure,
    projection_trajectory_figure,
    save_publication_figure,
)


def _estimates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "service_line": ["hydrocephalus", "all_prespecified"],
            "gap_relative_pct": [4.5, 7.2],
        }
    )


def test_primary_figure_has_no_title_or_redundant_legend() -> None:
    figure = primary_projection_gap_figure(
        _estimates(),
        {
            "hydrocephalus": "Hydrocephalus",
            "all_prespecified": "All prespecified diagnoses",
        },
    )
    axis = figure.axes[0]
    assert axis.get_title() == ""
    assert axis.get_legend() is None
    assert [label.get_text() for label in axis.get_yticklabels()] == [
        "Hydrocephalus",
        "All prespecified diagnoses",
    ]
    plt.close(figure)


def test_primary_figure_rejects_duplicate_service_lines() -> None:
    duplicated = pd.concat([_estimates(), _estimates().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate service lines"):
        primary_projection_gap_figure(duplicated, {})


def test_publication_figure_exports_vector_and_high_resolution_files(tmp_path: Path) -> None:
    figure = primary_projection_gap_figure(_estimates(), {})
    outputs = save_publication_figure(figure, tmp_path / "figure")
    assert {path.suffix for path in outputs} == {".pdf", ".svg", ".png"}
    assert all(path.stat().st_size > 0 for path in outputs)
    plt.close(figure)


def test_projection_trajectory_has_direct_labels_and_no_legend() -> None:
    estimates = pd.DataFrame(
        {
            "service_line": ["all_prespecified", "all_prespecified"],
            "baseline_year": [2024, 2024],
            "horizon": [2030, 2035],
            "baseline_cases": [100, 100],
            "model_0": [98, 96],
            "model_1": [102, 106],
        }
    )
    figure = projection_trajectory_figure(estimates)
    axis = figure.axes[0]
    assert axis.get_legend() is None
    assert {text.get_text() for text in axis.texts} == {
        "Age/sex structured",
        "Population only",
    }
    plt.close(figure)


def test_backtest_figure_requires_both_analysis_sets() -> None:
    summary = pd.DataFrame(
        {
            "analysis_set": ["all_years"],
            "service_line": ["all_prespecified"],
            "backtest_horizon_years": [1],
            "model_0_wape": [2.0],
            "model_1_wape": [1.8],
        }
    )
    with pytest.raises(ValueError, match="COVID-excluded"):
        backtest_performance_figure(summary)
