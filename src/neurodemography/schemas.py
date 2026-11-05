"""Validation for normalized study inputs."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def _require_columns(frame: pd.DataFrame, required: Iterable[str], name: str) -> None:
    missing = set(required).difference(frame.columns)
    if missing:
        raise ValueError(f"{name} is missing required columns: {sorted(missing)}")


def _require_unique(frame: pd.DataFrame, key: list[str], name: str) -> None:
    duplicated = frame.duplicated(key, keep=False)
    if duplicated.any():
        example = frame.loc[duplicated, key].head().to_dict(orient="records")
        raise ValueError(f"{name} has duplicate keys; examples: {example}")


def _validate_common(frame: pd.DataFrame, value: str, name: str) -> None:
    if frame.empty:
        raise ValueError(f"{name} is empty")
    if frame[value].isna().any():
        raise ValueError(f"{name}.{value} contains missing/suppressed values")
    if (frame[value] < 0).any():
        raise ValueError(f"{name}.{value} contains negative values")
    invalid_sex = set(frame["sex"].dropna().unique()).difference({"male", "female"})
    if invalid_sex:
        raise ValueError(f"{name}.sex contains non-component categories: {sorted(invalid_sex)}")


def validate_diagnoses(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate normalized diagnosis rows and return a typed copy."""

    required = ["year", "geography", "sex", "age_group", "icd10", "cases"]
    _require_columns(frame, required, "diagnoses")
    typed = frame.copy()
    typed["year"] = pd.to_numeric(typed["year"], errors="raise").astype(int)
    typed["cases"] = pd.to_numeric(typed["cases"], errors="raise")
    _validate_common(typed, "cases", "diagnoses")
    _require_unique(typed, ["year", "geography", "sex", "age_group", "icd10"], "diagnoses")
    return typed


def validate_population_observed(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate normalized observed population rows."""

    required = ["year", "geography", "sex", "age_group", "population"]
    _require_columns(frame, required, "population_observed")
    typed = frame.copy()
    typed["year"] = pd.to_numeric(typed["year"], errors="raise").astype(int)
    typed["population"] = pd.to_numeric(typed["population"], errors="raise")
    _validate_common(typed, "population", "population_observed")
    if (typed["population"] == 0).any():
        raise ValueError("population_observed.population contains zero denominators")
    _require_unique(typed, ["year", "geography", "sex", "age_group"], "population_observed")
    return typed


def validate_population_projected(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate normalized projected population rows."""

    required = ["year", "geography", "sex", "age_group", "scenario", "population"]
    _require_columns(frame, required, "population_projected")
    typed = frame.copy()
    typed["year"] = pd.to_numeric(typed["year"], errors="raise").astype(int)
    typed["population"] = pd.to_numeric(typed["population"], errors="raise")
    _validate_common(typed, "population", "population_projected")
    _require_unique(
        typed,
        ["year", "geography", "sex", "age_group", "scenario"],
        "population_projected",
    )
    return typed
