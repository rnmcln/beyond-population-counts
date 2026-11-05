import pandas as pd

from neurodemography.codebook import map_service_lines, normalize_icd3


def test_normalize_icd3_handles_genesis_labels() -> None:
    assert normalize_icd3("ICD10-I60 Nontraumatic SAH") == "I60"
    assert normalize_icd3("s06.5") == "S06"
    assert normalize_icd3("ICD10-A00-A09 Infectious intestinal diseases") is None
    assert normalize_icd3("ICD10-C00–D48 Neoplasms") is None


def test_range_mapping_consolidates_c70_to_c72() -> None:
    codebook = pd.DataFrame(
        {
            "service_line": ["cns"],
            "code_start": ["C70"],
            "code_end": ["C72"],
        }
    )
    diagnoses = pd.DataFrame({"icd10": ["C70", "C71", "C72", "C73"]})
    mapped = map_service_lines(diagnoses, codebook)
    assert mapped["icd10"].tolist() == ["C70", "C71", "C72"]
    assert set(mapped["service_line"]) == {"cns"}
