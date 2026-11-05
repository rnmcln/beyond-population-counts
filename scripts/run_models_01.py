#!/usr/bin/env python3
"""Run prespecified Models 0/1 and write tables plus the primary figure."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from neurodemography.codebook import load_diagnosis_codebook  # noqa: E402
from neurodemography.config import load_config, resolve_project_path  # noqa: E402
from neurodemography.models import project_models  # noqa: E402
from neurodemography.plotting import (  # noqa: E402
    primary_projection_gap_figure,
    save_publication_figure,
)


def main() -> None:
    config = load_config()
    study = config["study"]
    paths = config["paths"]
    horizons = [*study["secondary_horizons"], study["primary_horizon"]]
    horizons = sorted(set(horizons))
    diagnoses = pd.read_csv(resolve_project_path(paths["diagnoses"]))
    observed = pd.read_csv(resolve_project_path(paths["population_observed"]))
    projected = pd.read_csv(resolve_project_path(paths["population_projected"]))
    codebook = load_diagnosis_codebook(resolve_project_path(paths["diagnosis_codebook"]))

    estimates, decomposition = project_models(
        diagnoses,
        observed,
        projected,
        codebook,
        baseline_year=study["baseline_year"],
        horizons=horizons,
        scenario=study["projection_scenario"],
    )
    table_dir = resolve_project_path(paths["output_tables"])
    figure_dir = resolve_project_path(paths["output_figures"])
    log_dir = resolve_project_path(paths["output_logs"])
    for directory in (table_dir, figure_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)
    estimates.to_csv(table_dir / "models_0_1.csv", index=False)
    decomposition.to_csv(table_dir / "shapley_decomposition.csv", index=False)

    primary = estimates.loc[estimates["horizon"] == study["primary_horizon"]].copy()
    labels = codebook.set_index("service_line")["label"].to_dict()
    labels["all_prespecified"] = "All prespecified diagnoses"
    figure = primary_projection_gap_figure(primary, labels)
    figure_paths = save_publication_figure(
        figure,
        figure_dir / f"primary_{study['primary_horizon']}_projection_gap",
    )
    plt.close(figure)

    manifest = {
        "run_at_utc": datetime.now(UTC).isoformat(),
        "baseline_year": study["baseline_year"],
        "horizons": horizons,
        "scenario": study["projection_scenario"],
        "language_boundary": "inpatient utilization; not clinical need",
        "rows": len(estimates),
    }
    (log_dir / "models_0_1_run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(table_dir / "models_0_1.csv")
    print(table_dir / "shapley_decomposition.csv")
    for path in figure_paths:
        print(path)


if __name__ == "__main__":
    main()
