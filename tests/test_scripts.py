"""Tests for helper functions in the analysis scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_age_band_matches_study_groups():
    ext = load("run_extended_sensitivity")
    assert ext.age_band(0, 85) == "0"
    assert ext.age_band(3, 85) == "1-4"
    assert ext.age_band(17, 85) == "15-17"
    assert ext.age_band(19, 85) == "18-19"
    assert ext.age_band(84, 85) == "80-84"
    assert ext.age_band(87, 85) == "85+"
    assert ext.age_band(87, 90) == "85-89"
    assert ext.age_band(95, 90) == "90+"


def test_single_age_parses_genesis_labels():
    ext = load("run_extended_sensitivity")
    assert ext.single_age("unter 1 Jahr") == 0
    assert ext.single_age("66-Jährige") == 66
    assert ext.single_age("90 Jahre und mehr") == 90
    assert ext.single_age("Insgesamt") is None


def test_flagged_changes_groups_by_code():
    tables = load("make_manuscript_tables_md")
    series = pd.DataFrame(
        {
            "icd10": ["I62", "I62", "C70"],
            "year": [2008, 2019, 2009],
            "cases": [8000, 9000, 400],
            "yoy_change_pct": [10.13, -19.24, -15.3],
            "flag_discontinuity": [True, True, True],
        }
    )
    assert tables.flagged_changes(series) == "I62 (+10.1% in 2008; −19.2% in 2019)"


def test_regional_split_requires_land_dimension():
    regional = load("run_regional")
    frame = pd.DataFrame(
        {
            "1_variable_label": ["Bundesländer", "Bundesländer", "Bundesländer"],
            "1_variable_attribute_code": ["01", "02", ""],
            "1_variable_attribute_label": ["Schleswig-Holstein", "Hamburg", "Insgesamt"],
        }
    )
    parts = regional.split_by_land(frame)
    assert sorted(parts) == ["Hamburg", "Schleswig-Holstein"]
