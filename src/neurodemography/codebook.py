"""ICD-10 code normalization and service-line mapping."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ICD3_PATTERN = re.compile(r"(?<![A-Z0-9])([A-Z][0-9]{2})(?![0-9])", flags=re.IGNORECASE)
ICD_RANGE_PATTERN = re.compile(
    r"(?<![A-Z0-9])[A-Z][0-9]{2}\s*[-–—]\s*[A-Z][0-9]{2}(?![0-9])",
    flags=re.IGNORECASE,
)


def normalize_icd3(value: object) -> str | None:
    """Extract a three-character ICD-10 code from common GENESIS labels."""

    if pd.isna(value):
        return None
    text = str(value).upper()
    if ICD_RANGE_PATTERN.search(text):
        return None
    match = ICD3_PATTERN.search(text)
    return match.group(1) if match else None


def _icd_ordinal(code: str) -> int:
    return (ord(code[0]) - ord("A")) * 100 + int(code[1:])


def load_diagnosis_codebook(path: str | Path) -> pd.DataFrame:
    """Load and validate the diagnosis range codebook."""

    codebook = pd.read_csv(path)
    required = {"service_line", "label", "code_start", "code_end", "include_primary"}
    missing = required.difference(codebook.columns)
    if missing:
        raise ValueError(f"Diagnosis codebook is missing columns: {sorted(missing)}")
    for column in ("code_start", "code_end"):
        codebook[column] = codebook[column].map(normalize_icd3)
        if codebook[column].isna().any():
            raise ValueError(f"Diagnosis codebook has invalid {column} values")
    include = codebook["include_primary"].astype(str).str.lower().isin({"true", "1", "yes"})
    return codebook.loc[include].reset_index(drop=True)


def map_service_lines(diagnoses: pd.DataFrame, codebook: pd.DataFrame) -> pd.DataFrame:
    """Map ICD-10 rows to one and only one prespecified service line."""

    mapped = diagnoses.copy()
    mapped["icd10"] = mapped["icd10"].map(normalize_icd3)
    if mapped["icd10"].isna().any():
        examples = diagnoses.loc[mapped["icd10"].isna(), "icd10"].head().tolist()
        raise ValueError(f"Unparseable ICD-10 values: {examples}")

    def service_line_for(code: str) -> str | None:
        value = _icd_ordinal(code)
        matches = codebook.loc[
            codebook.apply(
                lambda row: (
                    _icd_ordinal(row["code_start"]) <= value <= _icd_ordinal(row["code_end"])
                ),
                axis=1,
            ),
            "service_line",
        ].tolist()
        if len(matches) > 1:
            raise ValueError(f"ICD-10 code {code} maps to multiple service lines: {matches}")
        return matches[0] if matches else None

    mapped["service_line"] = mapped["icd10"].map(service_line_for)
    return mapped.loc[mapped["service_line"].notna()].copy()
