import pandas as pd

from neurodemography.age_groups import aggregate_single_age_population, diagnosis_age_group


def test_diagnosis_age_groups_include_irregular_young_bands_and_topcode() -> None:
    expected = {
        0: "0",
        1: "1-4",
        4: "1-4",
        5: "5-9",
        15: "15-17",
        18: "18-19",
        20: "20-24",
        84: "80-84",
        85: "85+",
        100: "85+",
    }
    assert {age: diagnosis_age_group(age) for age in expected} == expected


def test_aggregate_single_age_population_preserves_total() -> None:
    frame = pd.DataFrame(
        {
            "year": [2024] * 4,
            "geography": ["Germany"] * 4,
            "sex": ["female"] * 4,
            "age": [0, 1, 85, 86],
            "population": [10, 20, 30, 40],
        }
    )
    result = aggregate_single_age_population(frame)
    assert result["population"].sum() == 100
    assert result.set_index("age_group").loc["85+", "population"] == 70
