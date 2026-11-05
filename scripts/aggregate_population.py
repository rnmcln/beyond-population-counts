#!/usr/bin/env python3
"""Aggregate a normalized single-age population CSV to study age bands."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from neurodemography.age_groups import aggregate_single_age_population


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--topcode", type=int, default=85)
    parser.add_argument("--projected", action="store_true")
    args = parser.parse_args()
    source = pd.read_csv(args.input)
    result = aggregate_single_age_population(source, topcode=args.topcode, projected=args.projected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(f"Aggregated {len(source):,} rows to {len(result):,} rows -> {args.output}")


if __name__ == "__main__":
    main()
