#!/usr/bin/env python3
"""Validate and import a tidy CSV into the processed-data contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from neurodemography.schemas import (
    validate_diagnoses,
    validate_population_observed,
    validate_population_projected,
)

VALIDATORS = {
    "diagnoses": validate_diagnoses,
    "population_observed": validate_population_observed,
    "population_projected": validate_population_projected,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=sorted(VALIDATORS))
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--delimiter", default=",")
    args = parser.parse_args()

    frame = pd.read_csv(args.input, sep=args.delimiter)
    validated = VALIDATORS[args.kind](frame)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"{args.kind}.csv"
    validated.to_csv(output, index=False)
    print(f"Validated {len(validated):,} rows -> {output}")


if __name__ == "__main__":
    main()
