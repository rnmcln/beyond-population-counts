import zipfile
from pathlib import Path

import pandas as pd
import pytest

from neurodemography.genesis import (
    _diagnosis_age_group,
    dimension_map,
    normalize_diagnoses_ffcsv,
    normalize_population_observed_ffcsv,
    normalize_population_projected_ffcsv,
    parse_value,
    read_ffcsv,
    value_columns,
)

FFCSV = """\
Statistik_Code;Statistik_Label;Zeit_Code;Zeit_Label;Zeit;1_Merkmal_Code;1_Merkmal_Label;1_Auspraegung_Code;1_Auspraegung_Label;BEV001__Bevoelkerungsstand__Anzahl;BEV001__Bevoelkerungsstand__q
12411;Bevölkerungsfortschreibung;JAHR;Jahr;2024;GES;Geschlecht;GESM;männlich;1.234,5;e
"""


def test_read_ffcsv_canonicalises_revised_german_columns(tmp_path: Path) -> None:
    source = tmp_path / "table.csv"
    source.write_text(FFCSV, encoding="utf-8")
    frame = read_ffcsv(source)
    assert frame.loc[0, "statistics_code"] == "12411"
    assert dimension_map(frame) == {
        "Geschlecht": (
            "1_variable_attribute_code",
            "1_variable_attribute_label",
        )
    }
    assert value_columns(frame) == ["BEV001__Bevoelkerungsstand__Anzahl"]
    assert parse_value(frame["BEV001__Bevoelkerungsstand__Anzahl"]).iloc[0] == 1234.5


def test_read_ffcsv_accepts_the_official_single_csv_zip_shape(tmp_path: Path) -> None:
    source = tmp_path / "table.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("12411-0006_de_flat.csv", FFCSV)
    assert len(read_ffcsv(source)) == 1


def test_read_ffcsv_rejects_ambiguous_archives(tmp_path: Path) -> None:
    source = tmp_path / "table.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("one.csv", FFCSV)
        archive.writestr("two.csv", FFCSV)
    with pytest.raises(ValueError, match="Expected one CSV"):
        read_ffcsv(source)


def test_parse_value_preserves_official_missing_signs() -> None:
    values = parse_value(pd.Series(["-", ".", "...", "/", "x", "0"]))
    assert values.isna().sum() == 5
    assert values.iloc[-1] == 0


def test_parse_value_converts_only_dash_to_zero_when_explicitly_requested() -> None:
    values = parse_value(
        pd.Series(["-", ".", "...", "/", "x", "0"]),
        dash_is_zero=True,
    )
    assert values.iloc[0] == 0
    assert values.iloc[-1] == 0
    assert values.iloc[1:5].isna().all()


def test_diagnosis_age_parser_distinguishes_under_one_from_under_ten() -> None:
    assert _diagnosis_age_group("unter 1 Jahr", topcode=85) == "0"
    assert _diagnosis_age_group("5 bis unter 10 Jahre", topcode=85) == "5-9"
    assert _diagnosis_age_group("10 bis unter 15 Jahre", topcode=85) == "10-14"
    assert _diagnosis_age_group("15 bis unter 18 Jahre", topcode=85) == "15-17"


def test_normalize_diagnoses_excludes_hierarchy_totals_and_topcodes_older_ages() -> None:
    frame = pd.DataFrame(
        {
            "statistics_code": ["23131"] * 4,
            "statistics_label": ["Diagnosen"] * 4,
            "time": ["2024"] * 4,
            "1_variable_label": ["Geschlecht"] * 4,
            "1_variable_attribute_code": ["GESM"] * 4,
            "1_variable_attribute_label": ["männlich"] * 4,
            "2_variable_label": ["Altersgruppen"] * 4,
            "2_variable_attribute_code": ["ALT8590", "ALT9095", "ALT8590", "ALT8590"],
            "2_variable_attribute_label": [
                "85 bis unter 90 Jahre",
                "90 bis unter 95 Jahre",
                "85 bis unter 90 Jahre",
                "85 bis unter 90 Jahre",
            ],
            "3_variable_label": ["Hauptdiagnose ICD-10"] * 4,
            "3_variable_attribute_code": ["I60", "I60", "A00-A09", "I61"],
            "3_variable_attribute_label": [
                "ICD10-I60 Nontraumatic SAH",
                "ICD10-I60 Nontraumatic SAH",
                "ICD10-A00-A09 Infectious intestinal diseases",
                "ICD10-I61 Intracerebral haemorrhage",
            ],
            "KRANK1__Entlassene_Patienten__Anzahl": ["10", "12", "99", "."],
            "KRANK1__Entlassene_Patienten__q": ["e", "e", "e", ""],
        }
    )
    result = normalize_diagnoses_ffcsv(frame)
    i60 = result.loc[result["icd10"] == "I60"].iloc[0]
    assert i60["age_group"] == "85+"
    assert i60["cases"] == 22
    assert set(result["icd10"]) == {"I60", "I61"}
    assert result.loc[result["icd10"] == "I61", "cases"].isna().all()
    assert result.loc[result["icd10"] == "I61", "quality_flag"].iloc[0] == "."

    parent = frame.iloc[[0]].copy()
    parent["3_variable_label"] = "ICD-10 (1-Steller) Hauptdiagnose"
    parent["3_variable_attribute_code"] = ""
    parent["3_variable_attribute_label"] = ""
    parent["KRANK1__Entlassene_Patienten__Anzahl"] = "999"
    with_parent = normalize_diagnoses_ffcsv(pd.concat([frame, parent], ignore_index=True))
    pd.testing.assert_frame_equal(result, with_parent)


def test_normalize_diagnoses_retains_explicit_structural_zero() -> None:
    frame = pd.DataFrame(
        {
            "statistics_code": ["23131"],
            "statistics_label": ["Diagnosen"],
            "time": ["2024"],
            "1_variable_label": ["Geschlecht"],
            "1_variable_attribute_code": ["GESM"],
            "1_variable_attribute_label": ["männlich"],
            "2_variable_label": ["Altersgruppen"],
            "2_variable_attribute_code": ["ALT0001"],
            "2_variable_attribute_label": ["unter 1 Jahr"],
            "3_variable_label": ["Hauptdiagnose ICD-10"],
            "3_variable_attribute_code": ["ICD10-I60"],
            "3_variable_attribute_label": ["Subarachnoidalblutung"],
            "KRANK1__Entlassene_Patienten__Anzahl": ["-"],
        }
    )
    result = normalize_diagnoses_ffcsv(frame)
    assert result.loc[0, "cases"] == 0
    assert result.loc[0, "quality_flag"] == "-"


def _population_frame(*, projected: bool) -> pd.DataFrame:
    value_column = (
        "BEV001__Bevoelkerungsstand__1000" if projected else "BEV001__Bevoelkerungsstand__Anzahl"
    )
    frame = pd.DataFrame(
        {
            "statistics_code": ["12421" if projected else "12411"] * 3,
            "statistics_label": ["Population"] * 3,
            "time": ["2035" if projected else "2024"] * 3,
            "1_variable_label": ["Geschlecht"] * 3,
            "1_variable_attribute_code": ["GESW"] * 3,
            "1_variable_attribute_label": ["weiblich"] * 3,
            "2_variable_label": ["Altersjahre"] * 3,
            "2_variable_attribute_code": ["ALT84", "ALT85", "ALT86"],
            "2_variable_attribute_label": ["84-Jährige", "85-Jährige", "86-Jährige"],
            value_column: [
                "10,0" if projected else "10000",
                "2,0" if projected else "2000",
                "3,0" if projected else "3000",
            ],
        }
    )
    if projected:
        frame["3_variable_label"] = "Varianten der Bevölkerungsvorausberechnung"
        frame["3_variable_attribute_code"] = "G2L2W2"
        frame["3_variable_attribute_label"] = "Geburtenrate, LE und WS moderat (G2L2W2)"
    return frame


def test_normalize_observed_population_harmonizes_to_85_plus() -> None:
    result = normalize_population_observed_ffcsv(_population_frame(projected=False))
    assert result.loc[result["age_group"] == "80-84", "population"].iloc[0] == 10000
    assert result.loc[result["age_group"] == "85+", "population"].iloc[0] == 5000
    assert set(result["census_basis"]) == {"Zensus 2022"}


def test_normalize_observed_population_records_census_basis_transitions() -> None:
    frames = []
    for year in (2010, 2011, 2022):
        frame = _population_frame(projected=False)
        frame["time"] = str(year)
        frames.append(frame)
    result = normalize_population_observed_ffcsv(pd.concat(frames, ignore_index=True))
    basis_by_year = result.groupby("year")["census_basis"].first().to_dict()
    assert basis_by_year == {
        2010: "pre-Zensus 2011 basis",
        2011: "Zensus 2011",
        2022: "Zensus 2022",
    }


def test_normalize_projected_population_applies_thousands_and_scenario() -> None:
    result = normalize_population_projected_ffcsv(_population_frame(projected=True))
    assert result.loc[result["age_group"] == "85+", "population"].iloc[0] == 5000
    assert set(result["scenario"]) == {"G2L2W2"}
    assert set(result["projection_vintage"]) == {"16th coordinated projection; base 2024"}


def test_normalize_current_long_form_projection_rows() -> None:
    frame = _population_frame(projected=True).drop(columns="BEV001__Bevoelkerungsstand__1000")
    frame["time"] = "2035-12-31"
    frame["value"] = ["10,0", "2,0", "3,0"]
    frame["value_unit"] = "1000"
    frame["value_variable_code"] = "BEV050"
    frame["value_variable_label"] = "Vorausberechneter Bevölkerungsstand"
    result = normalize_population_projected_ffcsv(frame)
    assert result.loc[result["age_group"] == "85+", "population"].iloc[0] == 5000
    assert set(result["year"]) == {2035}
