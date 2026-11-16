#!/usr/bin/env python3
"""Quantities added to the manuscript in the revision of 16 November 2026.

All values are derived from processed inputs and existing pipeline outputs; no new
data are used. The script writes one long-format table so that every number added
to the manuscript text can be traced to code.

1. Population change 2024-2035 for ages 70-79 combined (scenario G2-L2-W2).
2. Discharges in 2024 relative to 2019 for each diagnosis group (official totals).
3. Change from 2024 to the age-structured projection in 2035 and 2040, by diagnosis
   group and OPS code.
4. Share of the 2035 absolute difference between projections by diagnosis group.
5. Poisson standard deviation of the 2035 difference between projections, treating
   each 2024 sex-by-age stratum count as Poisson; populations are treated as fixed.
   For stratum s with count C_s, baseline population N_s and projected population
   N_s(t), the difference is sum_s C_s * (N_s(t)/N_s - N(t)/N), so its variance is
   sum_s C_s * (N_s(t)/N_s - N(t)/N)^2.
6. Five-year backtest WAPE for start and target years within one census basis,
   excluding target years 2020-2022 (all study diagnoses).
7. Population-size contribution to the change from 2024 to the age-structured
   projection in 2035, as a percentage of 2024 discharges, and the change in total
   population (Table 2 footnote).
8. Share of 2024 discharges from Berlin hospitals among Brandenburg residents
   (taken from the extended sensitivity log).

Output: outputs/tables/revision_quantities.csv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_ops import load_procedures  # noqa: E402

from neurodemography.codebook import load_diagnosis_codebook, map_service_lines  # noqa: E402
from neurodemography.config import load_config, resolve_project_path  # noqa: E402

KEYS = ["sex", "age_group"]


def main() -> None:
    config = load_config()
    study = config["study"]
    paths = config["paths"]
    base = int(study["baseline_year"])
    scen = study["projection_scenario"]
    tables = resolve_project_path(paths["output_tables"])
    out: list[dict] = []

    def add(quantity: str, item: str, value: float, unit: str) -> None:
        out.append({"quantity": quantity, "item": item, "value": float(value), "unit": unit})

    obs = pd.read_csv(resolve_project_path(paths["population_observed"]), dtype={"age_group": str})
    proj = pd.read_csv(
        resolve_project_path(paths["population_projected"]), dtype={"age_group": str}
    )
    obs = obs.loc[obs["geography"] == "Germany"]
    proj = proj.loc[(proj["geography"] == "Germany") & (proj["scenario"] == scen)]
    pop0 = obs.loc[obs["year"] == base].groupby(KEYS)["population"].sum()

    # 1. Population aged 70-79.
    def ages(frame: pd.DataFrame, groups: list[str]) -> float:
        return float(frame.loc[frame["age_group"].isin(groups), "population"].sum())

    for label, groups in (
        ("70-74", ["70-74"]),
        ("75-79", ["75-79"]),
        ("70-79", ["70-74", "75-79"]),
    ):
        p24 = ages(obs.loc[obs["year"] == base], groups)
        p35 = ages(proj.loc[proj["year"] == 2035], groups)
        add("population_change_2024_2035_pct", label, 100 * (p35 / p24 - 1), "%")

    # 2. Discharges 2024 relative to 2019 (official totals by ICD-10 code).
    series = pd.read_csv(tables / "icd_audit_series.csv")
    codebook = load_diagnosis_codebook(resolve_project_path(paths["diagnosis_codebook"]))
    mapped = map_service_lines(
        series.assign(geography="Germany", sex="all", age_group="all"), codebook
    )
    by_line = mapped.groupby(["service_line", "year"])["cases"].sum().unstack()
    for line in by_line.index:
        add(
            "discharges_2024_vs_2019_pct",
            line,
            100 * (by_line.loc[line, 2024] / by_line.loc[line, 2019] - 1),
            "%",
        )

    # 3. and 4. Change from 2024 to the age-structured projection; absolute shares.
    models = pd.read_csv(tables / "models_0_1.csv")
    models = models.loc[(models["geography"] == "Germany") & (models["scenario"] == scen)]
    for _, r in models.iterrows():
        add(
            f"age_structured_change_2024_{int(r['horizon'])}_pct",
            r["service_line"],
            100 * (r["model_1"] / r["baseline_cases"] - 1),
            "%",
        )
    m35 = models.loc[models["horizon"] == 2035].set_index("service_line")
    total_gap = m35.loc["all_prespecified", "gap_absolute"]
    for line, r in m35.iterrows():
        add("share_of_2035_absolute_difference_pct", line, 100 * r["gap_absolute"] / total_gap, "%")
    ops = pd.read_csv(tables / "ops_models_0_1.csv")
    for _, r in ops.iterrows():
        add(
            f"age_structured_change_2024_{int(r['horizon'])}_pct",
            f"OPS {r['ops']}",
            100 * (r["model_1"] / r["baseline_procedures"] - 1),
            "%",
        )

    # 5. Poisson standard deviation of the 2035 difference.
    fut = proj.loc[proj["year"] == 2035].groupby(KEYS)["population"].sum().reindex(pop0.index)
    weight = fut / pop0 - fut.sum() / pop0.sum()
    diag = pd.read_csv(resolve_project_path(paths["diagnoses"]), dtype={"age_group": str})
    diag = map_service_lines(
        diag.loc[(diag["year"] == base) & (diag["geography"] == "Germany")], codebook
    )
    strata = diag.groupby(["service_line", *KEYS])["cases"].sum()
    groups = {line: strata.loc[line] for line in strata.index.get_level_values(0).unique()}
    groups["all_prespecified"] = strata.groupby(level=KEYS).sum()
    groups["excluding_intracranial_injury"] = (
        strata.drop("intracranial_injury", level=0).groupby(level=KEYS).sum()
    )
    for line, cases in groups.items():
        cases = cases.reindex(pop0.index)
        diff = float((cases * weight).sum())
        sd = float(((cases * weight**2).sum()) ** 0.5)
        if line in m35.index:
            check = abs(diff - m35.loc[line, "gap_absolute"])
            if check > 1e-6 * max(1.0, abs(diff)):
                raise ValueError(
                    f"Reconstructed difference for {line} does not match models_0_1.csv"
                )
        model0 = float(cases.sum() * fut.sum() / pop0.sum())
        add("poisson_sd_2035_difference", line, sd, "discharges")
        add(
            "poisson_sd_2035_difference_pct_of_population_based",
            line,
            100 * sd / model0,
            "percentage points",
        )
        add("difference_2035", line, diff, "discharges")
    procs = load_procedures()
    procs = procs.loc[procs["year"] == base]
    for code, frame in procs.groupby("ops"):
        cases = frame.set_index(KEYS)["procedures"].reindex(pop0.index)
        model0 = float(cases.sum() * fut.sum() / pop0.sum())
        sd = float(((cases * weight**2).sum()) ** 0.5)
        add(
            "poisson_sd_2035_difference_pct_of_population_based",
            f"OPS {code}",
            100 * sd / model0,
            "percentage points",
        )

    # 6. Same-census-basis backtest.
    bt = pd.read_csv(tables / "posthoc_backtest_summaries.csv")
    sel = bt.loc[
        (bt["analysis_set"] == "exclude_covid_2020_2022")
        & (bt["restriction"] == "same_census_basis")
        & (bt["service_line"] == "all_prespecified")
    ]
    for _, r in sel.iterrows():
        h = int(r["backtest_horizon_years"])
        add(
            "wape_same_census_basis_excl_2020_2022_population_based",
            f"{h} years",
            r["model_0_wape"],
            "%",
        )
        add(
            "wape_same_census_basis_excl_2020_2022_age_structured",
            f"{h} years",
            r["model_1_wape"],
            "%",
        )
        add("pairs_same_census_basis_excl_2020_2022", f"{h} years", r["evaluations"], "pairs")

    # 7. Population-size contribution by diagnosis group, 2035.
    shap = pd.read_csv(tables / "shapley_decomposition.csv")
    shap = shap.loc[
        (shap["geography"] == "Germany") & (shap["horizon"] == 2035) & (shap["scenario"] == scen)
    ]
    for _, r in shap.iterrows():
        add(
            "population_size_contribution_2035_pct_of_2024",
            r["service_line"],
            100 * r["population_size_contribution"] / r["baseline_cases"],
            "%",
        )
    add("total_population_change_2024_2035_pct", "Germany", 100 * (fut.sum() / pop0.sum() - 1), "%")

    # 8. Berlin hospitals and Brandenburg residents.
    log = json.loads((ROOT / "outputs/logs/extsens_run.json").read_text())
    add(
        "berlin_hospital_discharges_brandenburg_residents_2024_pct",
        "all diagnoses",
        100 * log["berlin_discharges_share_brandenburg_residents_2024"],
        "%",
    )

    table = pd.DataFrame(out)
    table.to_csv(tables / "revision_quantities.csv", index=False)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 300)
    print(table.round(3).to_string())


if __name__ == "__main__":
    main()
