#!/usr/bin/env python3
"""Normalize a raw GENESIS flat-file download to an analysis input."""

from __future__ import annotations

import argparse
from pathlib import Path

from neurodemography.genesis import (
    normalize_diagnoses_ffcsv,
    normalize_population_observed_ffcsv,
    normalize_population_projected_ffcsv,
    read_ffcsv,
)

NORMALIZERS = {
    "diagnoses": normalize_diagnoses_ffcsv,
    "population_observed": normalize_population_observed_ffcsv,
    "population_projected": normalize_population_projected_ffcsv,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=sorted(NORMALIZERS))
    parser.add_argument("input", type=Path, help="Official ffcsv file or single-CSV ZIP")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--source-table")
    parser.add_argument("--value-column")
    parser.add_argument("--unit-multiplier", type=float)
    parser.add_argument("--topcode", type=int, default=85)
    args = parser.parse_args()

    options: dict[str, object] = {"topcode": args.topcode}
    if args.source_table:
        options["source_table"] = args.source_table
    if args.value_column:
        options["value_column"] = args.value_column
    if args.unit_multiplier is not None:
        options["unit_multiplier"] = args.unit_multiplier
    normalized = NORMALIZERS[args.kind](read_ffcsv(args.input), **options)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"{args.kind}.csv"
    normalized.to_csv(output, index=False)
    print(f"Normalized {len(normalized):,} rows -> {output}")


if __name__ == "__main__":
    main()
