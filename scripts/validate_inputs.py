#!/usr/bin/env python3
"""Validate all normalized input files configured for the study."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd

from neurodemography.config import load_config, project_root, resolve_project_path
from neurodemography.schemas import (
    validate_diagnoses,
    validate_population_observed,
    validate_population_projected,
)


def main() -> None:
    config = load_config()
    paths = config["paths"]
    inputs = {
        "diagnoses": (paths["diagnoses"], validate_diagnoses),
        "population_observed": (
            paths["population_observed"],
            validate_population_observed,
        ),
        "population_projected": (
            paths["population_projected"],
            validate_population_projected,
        ),
    }
    report = {"validated_at_utc": datetime.now(UTC).isoformat(), "datasets": {}}
    for name, (configured_path, validator) in inputs.items():
        path = resolve_project_path(configured_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {name}: {path}. Run `make data inputs` first (see data/README.md)."
            )
        frame = validator(pd.read_csv(path))
        report["datasets"][name] = {
            "path": str(path.relative_to(project_root())),
            "rows": len(frame),
        }
    log_dir = resolve_project_path(paths["output_logs"])
    log_dir.mkdir(parents=True, exist_ok=True)
    output = log_dir / "input_validation.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
