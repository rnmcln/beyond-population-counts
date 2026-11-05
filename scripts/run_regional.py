#!/usr/bin/env python3
"""Bundesland extension: Models 0/1 by Land and reconciliation with Germany.

Requires untouched official downloads (acquired with scripts/acquire_genesis.py):
  data/raw/genesis/23131-0011/*  diagnoses by Land, sex, age group, ICD-10 (3-digit)
  data/raw/genesis/12411-0013/*  observed population by Land, sex, single age
  data/raw/genesis/12421-0004/*  projected population by Land, sex, single age, variant

Outputs:
  data/processed/regional_{diagnoses,population_observed,population_projected}.csv
  outputs/tables/regional_models_0_1.csv
  outputs/tables/regional_shapley_decomposition.csv
  outputs/tables/regional_reconciliation.csv
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from neurodemography.codebook import load_diagnosis_codebook
from neurodemography.config import load_config, resolve_project_path
from neurodemography.genesis import (
    normalize_diagnoses_ffcsv,
    normalize_population_observed_ffcsv,
    normalize_population_projected_ffcsv,
    read_ffcsv,
)
from neurodemography.models import project_models

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/genesis"
LAND_LABELS = ("Bundesländer", "Länder")


def latest(table: str) -> Path:
    files = sorted(
        path for path in (RAW / table).glob("*") if path.suffix.lower() in {".zip", ".csv"}
    )
    if not files:
        sys.exit(
            f"Missing raw download for {table}. Acquire it with scripts/acquire_genesis.py "
            "(see docs/data_retrieval.md) before running the regional extension."
        )
    return files[-1]


def split_by_land(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    for index in range(1, 10):
        label_column = f"{index}_variable_label"
        if label_column not in frame:
            break
        if frame[label_column].str.strip().isin(LAND_LABELS).all():
            code_column = f"{index}_variable_attribute_code"
            name_column = f"{index}_variable_attribute_label"
            detail = frame.loc[frame[code_column].str.strip() != ""]
            return {str(name).strip(): rows for name, rows in detail.groupby(name_column)}
    raise ValueError("No Bundesland dimension found")


def raw_files(table: str) -> list[Path]:
    latest(table)  # exits with guidance if nothing is present
    return sorted(
        path for path in (RAW / table).glob("*") if path.suffix.lower() in {".zip", ".csv"}
    )


def normalise(table: str, normaliser, **options) -> pd.DataFrame:
    frame = pd.concat([read_ffcsv(path) for path in raw_files(table)], ignore_index=True)
    parts = [
        normaliser(rows, source_table=table, geography=land, **options)
        for land, rows in split_by_land(frame).items()
    ]
    if len(parts) != 16:
        raise ValueError(f"{table}: expected 16 Länder, found {len(parts)}")
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    config = load_config()
    study = config["study"]
    paths = config["paths"]
    tables = resolve_project_path(paths["output_tables"])
    processed = ROOT / "data/processed"

    diagnoses = normalise("23131-0011", normalize_diagnoses_ffcsv)
    observed = normalise("12411-0013", normalize_population_observed_ffcsv)
    projected = normalise("12421-0004", normalize_population_projected_ffcsv)
    diagnoses.to_csv(processed / "regional_diagnoses.csv", index=False)
    observed.to_csv(processed / "regional_population_observed.csv", index=False)
    projected.to_csv(processed / "regional_population_projected.csv", index=False)

    codebook = load_diagnosis_codebook(resolve_project_path(paths["diagnosis_codebook"]))
    horizons = [study["primary_horizon"], *study["secondary_horizons"]]
    estimates, decomposition = project_models(
        diagnoses,
        observed,
        projected,
        codebook,
        baseline_year=study["baseline_year"],
        horizons=horizons,
        scenario=study["projection_scenario"],
    )
    # Non-S06 aggregate per Land.
    lines = estimates.loc[
        ~estimates["service_line"].isin(["all_prespecified", "intracranial_injury"])
    ]
    keys = ["geography", "baseline_year", "horizon", "scenario"]
    non_s06 = lines.groupby(keys, as_index=False)[["baseline_cases", "model_0", "model_1"]].sum()
    non_s06["service_line"] = "excluding_intracranial_injury"
    non_s06["gap_absolute"] = non_s06["model_1"] - non_s06["model_0"]
    non_s06["gap_relative_pct"] = 100 * non_s06["gap_absolute"] / non_s06["model_0"]
    estimates = pd.concat([estimates, non_s06], ignore_index=True)
    estimates.to_csv(tables / "regional_models_0_1.csv", index=False)
    decomposition.to_csv(tables / "regional_shapley_decomposition.csv", index=False)

    # Reconciliation: summed Länder versus direct Germany estimates.
    national = pd.read_csv(tables / "models_0_1.csv")
    summed = (
        estimates.loc[estimates["service_line"] != "excluding_intracranial_injury"]
        .groupby(["service_line", "horizon", "scenario"], as_index=False)[
            ["baseline_cases", "model_0", "model_1"]
        ]
        .sum()
    )
    rec = summed.merge(
        national[["service_line", "horizon", "scenario", "baseline_cases", "model_0", "model_1"]],
        on=["service_line", "horizon", "scenario"],
        suffixes=("_sum_laender", "_germany"),
        validate="one_to_one",
    )
    for column in ("baseline_cases", "model_0", "model_1"):
        rec[f"{column}_difference_pct"] = 100 * (
            rec[f"{column}_sum_laender"] / rec[f"{column}_germany"] - 1
        )
    rec["gap_relative_pct_sum_laender"] = 100 * (
        rec["model_1_sum_laender"] / rec["model_0_sum_laender"] - 1
    )
    rec.to_csv(tables / "regional_reconciliation.csv", index=False)

    manifest = {
        "run_at_utc": datetime.now(UTC).isoformat(),
        "raw_files": {
            t: [path.name for path in raw_files(t)]
            for t in ("23131-0011", "12411-0013", "12421-0004")
        },
        "laender": sorted(diagnoses["geography"].unique()),
        "baseline_year": study["baseline_year"],
        "scenario": study["projection_scenario"],
    }
    log = resolve_project_path(paths["output_logs"])
    (log / "regional_run.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
