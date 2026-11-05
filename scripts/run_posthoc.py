#!/usr/bin/env python3
"""Post hoc analyses recorded in docs/amendments.md (5 November 2026).

1. Aggregate projection gap excluding intracranial injury (S06).
2. Backtest summaries restricted to origin/target pairs on the same census basis.
3. Directly age/sex-standardised utilisation rates, 2005-2024 (2024 standard).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from neurodemography.codebook import load_diagnosis_codebook, map_service_lines
from neurodemography.config import load_config, resolve_project_path
from neurodemography.models import summarize_backtests


def census_basis(year: int) -> str:
    if year <= 2010:
        return "pre-2011"
    if year <= 2021:
        return "zensus-2011"
    return "zensus-2022"


def main() -> None:
    config = load_config()
    paths = config["paths"]
    tables = resolve_project_path(paths["output_tables"])
    study = config["study"]

    # 1. Aggregate without S06.
    models = pd.read_csv(tables / "models_0_1.csv")
    lines = models.loc[models["service_line"] != "all_prespecified"]
    sets = {
        "all_prespecified": lines,
        "excluding_intracranial_injury": lines.loc[lines["service_line"] != "intracranial_injury"],
    }
    rows = []
    for label, frame in sets.items():
        agg = frame.groupby(["horizon", "scenario"], as_index=False)[
            ["baseline_cases", "model_0", "model_1"]
        ].sum()
        agg.insert(0, "aggregate", label)
        rows.append(agg)
    for scen_file in ["scenario_sensitivity.csv"]:
        scen = pd.read_csv(tables / scen_file)
        scen = scen.loc[
            (scen["service_line"] != "all_prespecified")
            & (scen["service_line"] != "intracranial_injury")
            & (scen["scenario"] != study["projection_scenario"])
        ]
        agg = scen.groupby(["horizon", "scenario"], as_index=False)[
            ["baseline_cases", "model_0", "model_1"]
        ].sum()
        agg.insert(0, "aggregate", "excluding_intracranial_injury")
        rows.append(agg)
    aggregates = pd.concat(rows, ignore_index=True)
    aggregates["gap_absolute"] = aggregates["model_1"] - aggregates["model_0"]
    aggregates["gap_relative_pct"] = 100 * aggregates["gap_absolute"] / aggregates["model_0"]
    aggregates.to_csv(tables / "posthoc_aggregate_excluding_s06.csv", index=False)

    # 2. Same-census-basis backtests.
    backtest = pd.read_csv(tables / "rolling_origin_backtest.csv")
    same = backtest.loc[
        backtest["baseline_year"].map(census_basis) == backtest["horizon"].map(census_basis)
    ]
    summary = summarize_backtests(same)
    summary.insert(1, "restriction", "same_census_basis")
    # Also the non-S06 aggregate in the backtest.
    non_s06 = backtest.loc[
        ~backtest["service_line"].isin(["all_prespecified", "intracranial_injury"])
    ]
    cols = ["observed_cases", "model_0", "model_1"]
    agg = non_s06.groupby(
        ["geography", "baseline_year", "backtest_horizon_years", "horizon"], as_index=False
    )[cols].sum()
    agg["service_line"] = "excluding_intracranial_injury"
    for model in ("model_0", "model_1"):
        agg[f"{model}_error"] = agg[model] - agg["observed_cases"]
        agg[f"{model}_absolute_error"] = agg[f"{model}_error"].abs()
        agg[f"{model}_ape_pct"] = 100 * agg[f"{model}_absolute_error"] / agg["observed_cases"]
    summary_non_s06 = summarize_backtests(agg)
    summary_non_s06.insert(1, "restriction", "none")
    pd.concat([summary, summary_non_s06], ignore_index=True).to_csv(
        tables / "posthoc_backtest_summaries.csv", index=False
    )

    # 3. Direct standardisation to the 2024 population.
    codebook = load_diagnosis_codebook(resolve_project_path(paths["diagnosis_codebook"]))
    diagnoses = map_service_lines(pd.read_csv(resolve_project_path(paths["diagnoses"])), codebook)
    observed = pd.read_csv(resolve_project_path(paths["population_observed"]))
    keys = ["year", "sex", "age_group"]
    cases = diagnoses.groupby([*keys, "service_line"], as_index=False)["cases"].sum()
    total = cases.groupby(keys, as_index=False)["cases"].sum()
    total["service_line"] = "all_prespecified"
    cases = pd.concat([cases, total], ignore_index=True)
    merged = cases.merge(observed[[*keys, "population"]], on=keys, validate="many_to_one")
    merged["rate"] = merged["cases"] / merged["population"]
    standard = observed.loc[
        observed["year"] == study["baseline_year"], ["sex", "age_group", "population"]
    ]
    standard = standard.rename(columns={"population": "standard_population"})
    merged = merged.merge(standard, on=["sex", "age_group"], validate="many_to_one")
    merged["expected"] = merged["rate"] * merged["standard_population"]
    std = merged.groupby(["year", "service_line"], as_index=False).agg(
        cases=("cases", "sum"),
        population=("population", "sum"),
        expected=("expected", "sum"),
        standard_population=("standard_population", "sum"),
    )
    std["crude_rate_per_100000"] = 1e5 * std["cases"] / std["population"]
    std["standardised_rate_per_100000"] = 1e5 * std["expected"] / std["standard_population"]
    std = std.sort_values(["service_line", "year"])
    # Average annual percentage change of standardised rate (log-linear), 2005-2019.
    trend_rows = []
    for line, frame in std.groupby("service_line"):
        for start, end in [(2005, 2019), (2011, 2019), (2005, 2024)]:
            window = frame.loc[frame["year"].between(start, end)]
            slope = np.polyfit(window["year"], np.log(window["standardised_rate_per_100000"]), 1)[0]
            trend_rows.append(
                {
                    "service_line": line,
                    "window": f"{start}-{end}",
                    "annual_pct_change": 100 * (np.exp(slope) - 1),
                    "rate_first": float(window["standardised_rate_per_100000"].iloc[0]),
                    "rate_last": float(window["standardised_rate_per_100000"].iloc[-1]),
                }
            )
    std.to_csv(tables / "posthoc_standardised_rates.csv", index=False)
    pd.DataFrame(trend_rows).to_csv(tables / "posthoc_standardised_rate_trends.csv", index=False)

    # 4. Three-factor Shapley decomposition of observed change, 2011-2019.
    decomp_rows = []
    for start, end in [(2011, 2019), (2012, 2019)]:
        for line, frame in merged.groupby("service_line"):
            a = frame.loc[frame["year"] == start].set_index(["sex", "age_group"])
            b = frame.loc[frame["year"] == end].set_index(["sex", "age_group"])
            b = b.reindex(a.index)
            n = {0: a["population"].sum(), 1: b["population"].sum()}
            sh = {0: a["population"] / n[0], 1: b["population"] / n[1]}
            rt = {0: a["rate"], 1: b["rate"]}

            def f(i: int, j: int, k: int, n=n, sh=sh, rt=rt) -> float:
                return float(n[i] * (sh[j] * rt[k]).sum())

            def shapley(factor: int) -> float:
                total = 0.0
                others = [x for x in range(3) if x != factor]
                weights = {0: 1 / 3, 1: 1 / 6, 2: 1 / 3}
                from itertools import product

                for state in product([0, 1], repeat=2):
                    level = [0, 0, 0]
                    for idx, val in zip(others, state, strict=True):
                        level[idx] = val
                    lo, hi = list(level), list(level)
                    lo[factor], hi[factor] = 0, 1
                    total += weights[sum(state)] * (f(*hi) - f(*lo))
                return total

            observed_start, observed_end = f(0, 0, 0), f(1, 1, 1)
            size, comp, rate = shapley(0), shapley(1), shapley(2)
            decomp_rows.append(
                {
                    "service_line": line,
                    "period": f"{start}-{end}",
                    "cases_start": observed_start,
                    "cases_end": observed_end,
                    "change": observed_end - observed_start,
                    "population_size": size,
                    "age_sex_composition": comp,
                    "age_sex_specific_rates": rate,
                    "reconstruction_error": observed_end - observed_start - size - comp - rate,
                }
            )
    decomp = pd.DataFrame(decomp_rows)
    for col in ["change", "population_size", "age_sex_composition", "age_sex_specific_rates"]:
        decomp[f"{col}_pct_of_start"] = 100 * decomp[col] / decomp["cases_start"]
    decomp.to_csv(tables / "posthoc_historical_decomposition.csv", index=False)

    manifest = {
        "run_at_utc": datetime.now(UTC).isoformat(),
        "analyses": [
            "aggregate excluding S06",
            "same-census-basis backtests",
            "direct standardisation to 2024 Germany population",
            "three-factor Shapley decomposition of observed change 2011-2019",
        ],
        "status": "post hoc; see docs/amendments.md",
    }
    log = resolve_project_path(paths["output_logs"])
    (log / "posthoc_run.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
