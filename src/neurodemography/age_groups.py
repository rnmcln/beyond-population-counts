"""Age harmonization for diagnosis and population tables."""

from __future__ import annotations

import pandas as pd


def diagnosis_age_group(age: int, *, topcode: int = 85) -> str:
    """Map a nonnegative single age to the stable diagnosis bands.

    The default top-code is 85 because the national observed-population table
    currently groups older ages as 85 years and over. A finer top-code must not
    be used unless all numerator and denominator sources support it.
    """

    if age < 0:
        raise ValueError("Age must be nonnegative")
    if age >= topcode:
        return f"{topcode}+"
    if age == 0:
        return "0"
    if age <= 4:
        return "1-4"
    if age <= 14:
        lower = 5 if age <= 9 else 10
        return f"{lower}-{lower + 4}"
    if age <= 17:
        return "15-17"
    if age <= 19:
        return "18-19"
    lower = (age // 5) * 5
    return f"{lower}-{lower + 4}"


def aggregate_single_age_population(
    frame: pd.DataFrame,
    *,
    topcode: int = 85,
    projected: bool = False,
) -> pd.DataFrame:
    """Aggregate normalized single-age population rows to analysis bands."""

    required = {"year", "geography", "sex", "age", "population"}
    if projected:
        required.add("scenario")
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Single-age population is missing columns: {sorted(missing)}")
    result = frame.copy()
    result["age"] = pd.to_numeric(result["age"], errors="raise").astype(int)
    result["population"] = pd.to_numeric(result["population"], errors="raise")
    if (result["population"] < 0).any():
        raise ValueError("Population contains negative values")
    result["age_group"] = result["age"].map(
        lambda value: diagnosis_age_group(value, topcode=topcode)
    )
    group = ["year", "geography", "sex", "age_group"]
    if projected:
        group.append("scenario")
    return result.groupby(group, as_index=False, observed=True)["population"].sum()
