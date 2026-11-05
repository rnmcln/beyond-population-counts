#!/usr/bin/env python3
"""Manuscript Table 1 and Table 2 (CSV) from versioned outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from neurodemography.codebook import load_diagnosis_codebook, map_service_lines

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs/tables"
ORDER = [
    "cns_malignancy",
    "meningioma",
    "benign_cns_other",
    "subarachnoid_haemorrhage",
    "intracerebral_haemorrhage",
    "other_intracranial_haemorrhage",
    "hydrocephalus",
    "intracranial_injury",
    "excluding_intracranial_injury",
    "all_prespecified",
]
OLD = ["65-69", "70-74", "75-79", "80-84", "85+"]


def historical_rates(
    diagnoses: pd.DataFrame,
    observed: pd.DataFrame,
    codebook: pd.DataFrame,
    *,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Calculate pooled age/sex-specific rates over a recent baseline window."""

    mapped = map_service_lines(diagnoses, codebook)
    mapped = mapped.loc[mapped["year"].between(start_year, end_year)]
    population = observed.loc[observed["year"].between(start_year, end_year)]
    cases = mapped.groupby(
        ["geography", "sex", "age_group", "service_line"],
        as_index=False,
        observed=True,
    )["cases"].sum()
    denominators = population.groupby(
        ["geography", "sex", "age_group"], as_index=False, observed=True
    )["population"].sum()
    rates = cases.merge(
        denominators,
        on=["geography", "sex", "age_group"],
        how="outer",
        validate="many_to_one",
        indicator=True,
    )
    if (rates["_merge"] != "both").any():
        raise ValueError("Historical rate numerator and denominator strata do not align")
    rates["rate_per_100000"] = 100_000 * rates["cases"] / rates["population"]
    rates["period"] = f"{start_year}-{end_year}"
    age_order = {
        value: index
        for index, value in enumerate(
            sorted(
                rates["age_group"].unique(),
                key=lambda label: int(str(label).split("-")[0].removesuffix("+")),
            )
        )
    }
    rates["age_order"] = rates["age_group"].map(age_order)
    return rates.drop(columns="_merge").sort_values(["service_line", "sex", "age_order"])


def main() -> None:
    codebook = load_diagnosis_codebook(ROOT / "metadata/diagnosis_codebook.csv")
    rates = historical_rates(
        pd.read_csv(ROOT / "data/processed/diagnoses.csv", dtype={"age_group": str}),
        pd.read_csv(ROOT / "data/processed/population_observed.csv", dtype={"age_group": str}),
        codebook,
        start_year=2022,
        end_year=2024,
    )
    rates.to_csv(T / "historical_age_sex_rates.csv", index=False)
    d = map_service_lines(
        pd.read_csv(ROOT / "data/processed/diagnoses.csv", dtype={"age_group": str}), codebook
    )
    d = d.loc[d["year"] == 2024]
    pop = pd.read_csv(ROOT / "data/processed/population_observed.csv", dtype={"age_group": str})
    total_pop = pop.loc[pop["year"] == 2024, "population"].sum()
    rows = []
    groups = {line: d.loc[d["service_line"] == line] for line in ORDER[:8]}
    groups["excluding_intracranial_injury"] = d.loc[d["service_line"] != "intracranial_injury"]
    groups["all_prespecified"] = d
    for line in ORDER:
        g = groups[line]
        n = g["cases"].sum()
        rows.append(
            {
                "service_line": line,
                "discharges_2024": n,
                "crude_rate_per_100000": 1e5 * n / total_pop,
                "female_pct": 100 * g.loc[g["sex"] == "female", "cases"].sum() / n,
                "age_65_plus_pct": 100 * g.loc[g["age_group"].isin(OLD), "cases"].sum() / n,
                "age_80_plus_pct": 100
                * g.loc[g["age_group"].isin(["80-84", "85+"]), "cases"].sum()
                / n,
            }
        )
    t1 = pd.DataFrame(rows)
    t1.to_csv(T / "table_1_baseline.csv", index=False)

    m = pd.read_csv(T / "models_0_1.csv")
    ex = pd.read_csv(T / "posthoc_aggregate_excluding_s06.csv")
    ex = ex.loc[(ex["scenario"] == "G2L2W2") & (ex["aggregate"] != "all_prespecified")]
    ex = ex.rename(columns={"aggregate": "service_line"})
    m = pd.concat([m, ex], ignore_index=True)
    m = m.loc[m["horizon"] == 2035].set_index("service_line")
    dec = pd.read_csv(T / "shapley_decomposition.csv")
    dec = dec.loc[dec["horizon"] == 2035].set_index("service_line")
    lines = [x for x in ORDER[:8] if x != "intracranial_injury"]
    dec.loc["excluding_intracranial_injury", "population_size_contribution"] = dec.loc[
        lines, "population_size_contribution"
    ].sum()
    dec.loc["excluding_intracranial_injury", "age_sex_composition_contribution"] = dec.loc[
        lines, "age_sex_composition_contribution"
    ].sum()
    t2 = []
    for line in ORDER:
        r = m.loc[line]
        row = {
            "service_line": line,
            "baseline_2024": r["baseline_cases"],
            "model_0_2035": r["model_0"],
            "model_1_2035": r["model_1"],
            "gap_absolute": r["gap_absolute"],
            "gap_relative_pct": r["gap_relative_pct"],
        }
        if line in dec.index:
            row["size_contribution"] = dec.loc[line, "population_size_contribution"]
            row["composition_contribution"] = dec.loc[line, "age_sex_composition_contribution"]
        t2.append(row)
    pd.DataFrame(t2).to_csv(T / "table_2_projections_2035.csv", index=False)
    print(t1.round(1).to_string())
    print(pd.DataFrame(t2).round(1).to_string())


if __name__ == "__main__":
    main()
