#!/usr/bin/env python3
"""Run rolling-origin backtests for Models 0/1."""

from __future__ import annotations

import pandas as pd

from neurodemography.codebook import load_diagnosis_codebook
from neurodemography.config import load_config, resolve_project_path
from neurodemography.models import backtest_models, summarize_backtests


def main() -> None:
    config = load_config()
    paths = config["paths"]
    settings = config["backtest"]
    results = backtest_models(
        pd.read_csv(resolve_project_path(paths["diagnoses"])),
        pd.read_csv(resolve_project_path(paths["population_observed"])),
        load_diagnosis_codebook(resolve_project_path(paths["diagnosis_codebook"])),
        horizons=settings["horizons"],
        minimum_training_years=settings["minimum_training_years"],
    )
    table_dir = resolve_project_path(paths["output_tables"])
    table_dir.mkdir(parents=True, exist_ok=True)
    detail_path = table_dir / "rolling_origin_backtest.csv"
    results.to_csv(detail_path, index=False)
    summary = summarize_backtests(results)
    summary_path = table_dir / "rolling_origin_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(detail_path)
    print(summary_path)


if __name__ == "__main__":
    main()
