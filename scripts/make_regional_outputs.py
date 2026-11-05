#!/usr/bin/env python3
"""Regional summary table for the federal-state analysis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs/tables"
OLD = ["65-69", "70-74", "75-79", "80-84", "85+"]
CITY_STATES = {"Berlin", "Hamburg", "Bremen"}


def summary() -> pd.DataFrame:
    m = pd.read_csv(T / "regional_models_0_1.csv")
    m = m.loc[m["horizon"] == 2035]
    d = pd.read_csv(T / "regional_shapley_decomposition.csv")
    d = d.loc[d["horizon"] == 2035]
    lines = d.loc[~d["service_line"].isin(["all_prespecified", "intracranial_injury"])]
    d_ex = lines.groupby("geography", as_index=False)[
        ["baseline_cases", "population_size_contribution", "age_sex_composition_contribution"]
    ].sum()
    po = pd.read_csv(
        ROOT / "data/processed/regional_population_observed.csv", dtype={"age_group": str}
    )
    pp = pd.read_csv(
        ROOT / "data/processed/regional_population_projected.csv", dtype={"age_group": str}
    )

    def share(frame: pd.DataFrame) -> pd.Series:
        old = frame.loc[frame["age_group"].isin(OLD)].groupby("geography")["population"].sum()
        return 100 * old / frame.groupby("geography")["population"].sum()

    s24 = share(po.loc[po["year"] == 2024])
    s35 = share(pp.loc[(pp["year"] == 2035) & (pp["scenario"] == "G2L2W2")])
    rows = []
    for land, g in m.groupby("geography"):
        a = g.set_index("service_line")
        allp, ex = a.loc["all_prespecified"], a.loc["excluding_intracranial_injury"]
        dd = d.loc[(d["geography"] == land) & (d["service_line"] == "all_prespecified")].iloc[0]
        de = d_ex.loc[d_ex["geography"] == land].iloc[0]
        rows.append(
            {
                "land": land,
                "city_state": land in CITY_STATES,
                "population_change_pct": 100
                * (allp["future_population"] / allp["baseline_population"] - 1),
                "age65_share_2024": s24[land],
                "age65_share_2035": s35[land],
                "baseline_cases": allp["baseline_cases"],
                "model_0": allp["model_0"],
                "model_1": allp["model_1"],
                "model_1_change_pct": 100 * (allp["model_1"] / allp["baseline_cases"] - 1),
                "gap_all_pct": allp["gap_relative_pct"],
                "gap_excl_s06_pct": ex["gap_relative_pct"],
                "size_pct": 100 * dd["population_size_contribution"] / dd["baseline_cases"],
                "composition_pct": 100
                * dd["age_sex_composition_contribution"]
                / dd["baseline_cases"],
                "size_excl_s06_pct": 100
                * de["population_size_contribution"]
                / de["baseline_cases"],
                "composition_excl_s06_pct": 100
                * de["age_sex_composition_contribution"]
                / de["baseline_cases"],
            }
        )
    out = pd.DataFrame(rows).sort_values("gap_excl_s06_pct")
    out.to_csv(T / "regional_summary_2035.csv", index=False)
    return out


if __name__ == "__main__":
    s = summary()
    print(s.round(1).to_string())
