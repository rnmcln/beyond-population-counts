#!/usr/bin/env python3
"""Normalise the national GENESIS downloads into the processed analysis inputs.

Locates the most recent download for each role under data/raw/genesis/ and writes
data/processed/diagnoses.csv, population_observed.csv and population_projected.csv.
"""

from __future__ import annotations

from pathlib import Path

from neurodemography.genesis import (
    normalize_diagnoses_ffcsv,
    normalize_population_observed_ffcsv,
    normalize_population_projected_ffcsv,
    read_ffcsv,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/genesis"
OUT = ROOT / "data/processed"

ROLES = {
    "diagnoses": ("23131-0002", "*_2005-2024_uncompressed.zip", normalize_diagnoses_ffcsv),
    "population_observed": ("12411-0006", "*_2005-2024*.zip", normalize_population_observed_ffcsv),
    "population_projected": (
        "12421-0002",
        "*_2030-2040*.zip",
        normalize_population_projected_ffcsv,
    ),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for kind, (table, pattern, normaliser) in ROLES.items():
        files = sorted((RAW / table).glob(pattern))
        if not files:
            raise SystemExit(f"Missing {table} download matching {pattern}; run `make data`.")
        frame = normaliser(read_ffcsv(files[-1]), source_table=table)
        output = OUT / f"{kind}.csv"
        frame.to_csv(output, index=False)
        print(f"{files[-1].name} -> {output.relative_to(ROOT)} ({len(frame):,} rows)")


if __name__ == "__main__":
    main()
