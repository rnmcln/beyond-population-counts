#!/usr/bin/env python3
"""Render main and supplementary tables (Markdown and CSV) from versioned outputs.

Writes to outputs/manuscript_tables/: tables_main.md, tables_supplement.md and one CSV
per table. These files are inputs to manuscript assembly and are not source data.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs/tables"
OUT = ROOT / "outputs/manuscript_tables"
L = {
    "cns_malignancy": "Malignant CNS neoplasm (C70–C72)",
    "meningioma": "Meningioma (D32)",
    "benign_cns_other": "Benign brain or CNS neoplasm (D33)",
    "subarachnoid_haemorrhage": "Subarachnoid haemorrhage (I60)",
    "intracerebral_haemorrhage": "Intracerebral haemorrhage (I61)",
    "other_intracranial_haemorrhage": "Subdural and other nontraumatic haemorrhage (I62)",
    "hydrocephalus": "Hydrocephalus (G91)",
    "intracranial_injury": "Intracranial injury (S06)",
    "excluding_intracranial_injury": "All study diagnoses except S06",
    "all_prespecified": "All study diagnoses",
}
ORDER = list(L)
LINES = ORDER[:8]
EXCL = "intracranial_injury"
STATE_EN = {
    "Baden-Württemberg": "Baden-Württemberg",
    "Bayern": "Bavaria",
    "Berlin": "Berlin",
    "Brandenburg": "Brandenburg",
    "Bremen": "Bremen",
    "Hamburg": "Hamburg",
    "Hessen": "Hesse",
    "Mecklenburg-Vorpommern": "Mecklenburg-Western Pomerania",
    "Niedersachsen": "Lower Saxony",
    "Nordrhein-Westfalen": "North Rhine-Westphalia",
    "Rheinland-Pfalz": "Rhineland-Palatinate",
    "Saarland": "Saarland",
    "Sachsen": "Saxony",
    "Sachsen-Anhalt": "Saxony-Anhalt",
    "Schleswig-Holstein": "Schleswig-Holstein",
    "Thüringen": "Thuringia",
}


def n(x: float, step: int = 1) -> str:
    return f"{round(x / step) * step:,.0f}"


def s(x: float, d: int = 1) -> str:
    if pd.isna(x):
        return "–"
    v = f"{abs(x):,.{d}f}"
    return f"+{v}" if round(x, d) > 0 else (f"−{v}" if round(x, d) < 0 else v)


def md(header, rows, align) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(align) + "|"]
    return "\n".join(out + ["| " + " | ".join(r) + " |" for r in rows])


def write(name: str, frame: pd.DataFrame) -> None:
    frame.to_csv(OUT / f"{name}.csv", index=False)


def aggregate_gap(frame: pd.DataFrame, key: str) -> float:
    if key == "all_prespecified":
        sub = frame.loc[frame["service_line"].isin(LINES)]
    else:
        sub = frame.loc[frame["service_line"].isin([x for x in LINES if x != EXCL])]
    return 100 * (sub["model_1"].sum() / sub["model_0"].sum() - 1)


def population_2024() -> float:
    pop = pd.read_csv(ROOT / "data/processed/population_observed.csv")
    return float(pop.loc[pop["year"] == 2024, "population"].sum())


def flagged_changes(series: pd.DataFrame) -> str:
    large = series.groupby("icd10")["cases"].min() > 1500
    sel = series.loc[series["flag_discontinuity"] & series["icd10"].map(large)]
    out = []
    for code, rows in sel.groupby("icd10"):
        changes = "; ".join(f"{s(r.yoy_change_pct)}% in {r.year}" for r in rows.itertuples())
        out.append(f"{code} ({changes})")
    return " and ".join(out)


def start_year_note(dec: pd.DataFrame) -> str:
    agg = dec.loc[dec["service_line"] == "all_prespecified"].set_index("period")
    a = agg.loc["2011-2019", "age_sex_specific_rates_pct_of_start"]
    b = agg.loc["2012-2019", "age_sex_specific_rates_pct_of_start"]
    return f"{s(a)} points from 2011; {s(b)} points from 2012"


def main_tables() -> str:
    t1 = pd.read_csv(T / "table_1_baseline.csv").set_index("service_line").loc[ORDER]
    write("table_1", t1.reset_index())
    a = md(
        [
            "Diagnosis group",
            "Discharges",
            "Per 100,000",
            "Women, %",
            "Aged ≥65 y, %",
            "Aged ≥80 y, %",
        ],
        [
            [
                L[k],
                n(r.discharges_2024),
                f"{r.crude_rate_per_100000:.1f}",
                f"{r.female_pct:.1f}",
                f"{r.age_65_plus_pct:.1f}",
                f"{r.age_80_plus_pct:.1f}",
            ]
            for k, r in t1.iterrows()
        ],
        ["---"] + ["---:"] * 5,
    )
    t2 = pd.read_csv(T / "table_2_projections_2035.csv").set_index("service_line").loc[ORDER]
    write("table_2", t2.reset_index())
    b = md(
        [
            "Diagnosis group",
            "Observed 2024",
            "Population-based 2035",
            "Age-structured 2035",
            "Difference",
            "Difference, %",
            "Population size",
            "Age structure",
        ],
        [
            [
                L[k],
                n(r.baseline_2024),
                n(r.model_0_2035, 10),
                n(r.model_1_2035, 10),
                s(round(r.gap_absolute, -1), 0),
                s(r.gap_relative_pct),
                s(round(r.size_contribution, -1), 0),
                s(round(r.composition_contribution, -1), 0),
            ]
            for k, r in t2.iterrows()
        ],
        ["---"] + ["---:"] * 7,
    )
    ops = pd.read_csv(T / "ops_models_0_1.csv")
    write("table_3", ops)
    o35 = ops.loc[ops["horizon"] == 2035].set_index("ops")
    o40 = ops.loc[ops["horizon"] == 2040].set_index("ops")
    labels = {
        "5-013": (
            "Incision of brain and meninges, including evacuation of subdural haematoma (5-013)"
        ),
        "5-015": "Excision or destruction of intracranial lesion (5-015)",
        "5-022": "Incision of the CSF system, including external ventricular drainage (5-022)",
        "5-023": "Implantation of a CSF shunt (5-023)",
    }
    c = md(
        [
            "Procedure (OPS code)",
            "Procedures 2024",
            "Aged ≥65 y, %",
            "Population-based 2035",
            "Age-structured 2035",
            "Difference 2035, %",
            "Difference 2040, %",
        ],
        [
            [
                labels[k],
                n(r.baseline_procedures),
                f"{r.age_65_plus_pct:.1f}",
                n(r.model_0, 10),
                n(r.model_1, 10),
                s(r.gap_relative_pct),
                s(o40.loc[k, "gap_relative_pct"]),
            ]
            for k, r in o35.iterrows()
        ],
        ["---"] + ["---:"] * 6,
    )
    return (
        "**Table 1.** Hospital discharges with a study diagnosis as principal diagnosis, "
        "Germany, 2024.\n\n" + a + "\n\nRates per 100,000 population on 31 December 2024 "
        f"({population_2024():,.0f}). Percentages refer to discharges with recorded "
        "sex and age.\n\n"
        "**Table 2.** Projected discharges in 2035 (scenario G2-L2-W2; 2024 rates).\n\n"
        + b
        + "\n\nProjected counts are rounded to the nearest 10; differences and contributions "
        "were calculated before rounding. Difference: age-structured "
        "minus population-based projection; the percentage is relative to the "
        "population-based projection. Population size and age structure: contributions to "
        "the change from 2024 to the age-structured projection, which sum to that change "
        "(Supplementary Methods).\n\n"
        "**Table 3.** Projected inpatient procedures for selected cranial operations "
        "(scenario G2-L2-W2; 2024 rates).\n\n"
        + c
        + "\n\nCounts are procedures in full inpatient care (GENESIS table 23141-0102); a "
        "patient may undergo more than one procedure. Codes are analysed separately and not "
        "summed. Projected counts are rounded to the nearest 10.\n"
    )


def supplement_tables() -> str:
    parts = []
    ser = pd.read_csv(T / "icd_audit_series.csv")
    piv = ser.pivot(index="year", columns="icd10", values="cases")
    write("table_s2", piv.reset_index())
    parts.append(
        "**Table S2.** Annual discharges by principal diagnosis (official totals), Germany, "
        "2005–2024.\n\n"
        + md(
            ["Year", *piv.columns],
            [[str(y)] + [n(v) for v in r] for y, r in piv.iterrows()],
            ["---"] + ["---:"] * len(piv.columns),
        )
        + "\n\nAmong codes with more than 1,500 annual discharges, year-on-year changes of 10% "
        f"or more outside 2020–2021 occurred only for {flagged_changes(ser)}.\n"
    )
    sc = pd.read_csv(T / "scenario_sensitivity.csv")
    var = pd.read_csv(T / "extsens_all_variants.csv")
    rows, csv = [], []
    for k in ORDER:
        prim = {}
        for h in (2030, 2035, 2040):
            sub = sc.loc[(sc["scenario"] == "G2L2W2") & (sc["horizon"] == h)]
            prim[h] = (
                float(sub.loc[sub["service_line"] == k, "gap_relative_pct"].iloc[0])
                if k in set(sub["service_line"])
                else aggregate_gap(sub, k)
            )
        v = var.loc[var["horizon"] == 2035, k]
        rows.append(
            [L[k], s(prim[2030]), s(prim[2035]), s(prim[2040]), f"{s(v.min())} to {s(v.max())}"]
        )
        csv.append(
            {
                "service_line": k,
                **{f"primary_{h}": prim[h] for h in prim},
                "variants_2035_min": v.min(),
                "variants_2035_max": v.max(),
            }
        )
    write("table_s9", pd.DataFrame(csv))
    parts.append(
        "**Table S9.** Difference (%) between age-structured and population-based "
        "projections by horizon, and range across all 27 variants of the 16th coordinated "
        "population projection in 2035.\n\n"
        + md(
            ["Diagnosis group", "2030", "2035", "2040", "2035, range across 27 variants"],
            rows,
            ["---"] + ["---:"] * 4,
        )
        + "\n\nPrimary scenario G2-L2-W2 (moderate fertility, life expectancy and net "
        "migration); baseline 2024. The variants combine three assumptions each for "
        "fertility, life expectancy and net migration.\n"
    )
    base = pd.read_csv(T / "baseline_year_sensitivity.csv")
    base = base.loc[base["horizon"] == 2035]
    multi = pd.read_csv(T / "multi_year_rate_sensitivity.csv")
    multi = multi.loc[multi["horizon"] == 2035]
    py = pd.read_csv(T / "extsens_person_years.csv", index_col=0)
    ao = pd.read_csv(T / "extsens_age_only.csv", index_col=0)
    tc = pd.read_csv(T / "extsens_topcoding.csv", index_col=0)
    rows, csv = [], []
    for k in ORDER:

        def g(frame, k=k):
            return (
                float(frame.loc[frame["service_line"] == k, "gap_relative_pct"].iloc[0])
                if k in set(frame["service_line"])
                else aggregate_gap(frame, k)
            )

        vals = [
            tc.iloc[0][k],
            g(base.loc[base["baseline_year"] == 2022]),
            g(base.loc[base["baseline_year"] == 2023]),
            g(multi),
            py.iloc[1][k],
            ao.iloc[1][k],
            tc.iloc[1][k],
        ]
        rows.append([L[k], *[s(x) for x in vals]])
        csv.append(
            {
                "service_line": k,
                "primary": vals[0],
                "rates_2022": vals[1],
                "rates_2023": vals[2],
                "mean_rates_2022_2024": vals[3],
                "person_years": vals[4],
                "age_only": vals[5],
                "top_coding_90": vals[6],
            }
        )
    write("table_s10", pd.DataFrame(csv))
    parts.append(
        "**Table S10.** Difference (%) between projections in 2035 under alternative rate "
        "baselines and specifications (scenario G2-L2-W2).\n\n"
        + md(
            [
                "Diagnosis group",
                "Primary",
                "Rates 2022",
                "Rates 2023",
                "Mean rates 2022–2024",
                "Person-years",
                "Age only",
                "Ages to 90+",
            ],
            rows,
            ["---"] + ["---:"] * 7,
        )
        + "\n\nPerson-years: annual average population in 2024 and the mean of projected "
        "stocks on 31 December 2034 and 2035. Age only: rates by age group with sexes "
        "combined. Ages to 90+: separate rates for 85–89 years and 90 years or older, using "
        "state-level population tables summed to Germany.\n"
    )
    bt = pd.read_csv(T / "rolling_origin_summary.csv")
    ph = pd.read_csv(T / "posthoc_backtest_summaries.csv")
    same = ph.loc[ph["restriction"] == "same_census_basis"]
    bt = pd.concat(
        [
            bt,
            ph.loc[ph["service_line"] == "excluding_intracranial_injury"].drop(
                columns="restriction"
            ),
        ],
        ignore_index=True,
    )
    rows = []
    for k in ORDER:
        for h in (1, 3, 5):
            r = []
            for frame, aset in (
                (bt, "all_years"),
                (bt, "exclude_covid_2020_2022"),
                (same, "exclude_covid_2020_2022"),
            ):
                q = frame.loc[
                    (frame["service_line"] == k)
                    & (frame["analysis_set"] == aset)
                    & (frame["backtest_horizon_years"] == h)
                ]
                r += (
                    ["–", "–"]
                    if q.empty
                    else [f"{q['model_0_wape'].iloc[0]:.1f}", f"{q['model_1_wape'].iloc[0]:.1f}"]
                )
            rows.append([L[k] if h == 1 else "", f"{h}", *r])
    parts.append(
        "**Table S7.** Weighted absolute percentage error (%) of population-based (PB) and "
        "age-structured (AS) projections in historical backtests.\n\n"
        + md(
            [
                "Diagnosis group",
                "Years ahead",
                "All targets: PB",
                "All targets: AS",
                "Excl. 2020–2022: PB",
                "Excl. 2020–2022: AS",
                "Same census basis: PB",
                "Same census basis: AS",
            ],
            rows,
            ["---", "---:"] + ["---:"] * 6,
        )
        + "\n\nProjections started from each year from 2009 and used the population observed "
        "in the target year. Same census basis: start and target years within the same "
        "census basis (before 2011, 2011–2021, 2022 onward), excluding targets 2020–2022.\n"
    )
    per = pd.read_csv(T / "extsens_backtest_periods.csv")
    order = {"targets up to 2019": 0, "targets 2020-2022": 1, "targets 2023-2024": 2}
    per = per.sort_values(
        ["backtest_horizon_years", "period"],
        key=lambda c: c.map(order) if c.name == "period" else c,
    )
    write("table_s6", per)
    rows = [
        [
            f"{int(r.backtest_horizon_years)}",
            r.period.replace("targets ", "").replace("-", "–"),
            f"{int(r.pairs)}",
            f"{r.model_0_wape:.1f}",
            f"{r.model_1_wape:.1f}",
            s(r.model_0_mean_signed_pct),
            s(r.model_1_mean_signed_pct),
            f"{int(r.model_1_better_pairs)}",
        ]
        for r in per.itertuples()
    ]
    parts.append(
        "**Table S6.** Backtest errors for all study diagnoses by period of the target year.\n\n"
        + md(
            [
                "Years ahead",
                "Target years",
                "Pairs",
                "WAPE PB, %",
                "WAPE AS, %",
                "Mean signed error PB, %",
                "Mean signed error AS, %",
                "Pairs with lower AS error",
            ],
            rows,
            ["---:", "---"] + ["---:"] * 6,
        )
        + "\n\nSigned error: projected minus observed discharges, as a percentage of observed "
        "discharges; positive values indicate overprojection.\n"
    )
    dec = pd.read_csv(T / "posthoc_historical_decomposition.csv")
    rows, csv = [], []
    for period in ("2011-2019", "2012-2019"):
        d = dec.loc[dec["period"] == period].set_index("service_line")
        for k in [x for x in ORDER if x in d.index]:
            r = d.loc[k]
            rows.append(
                [
                    period.replace("-", "–") if k == "cns_malignancy" else "",
                    L[k],
                    n(r.cases_start),
                    n(r.cases_end),
                    s(r.change_pct_of_start),
                    s(r.population_size_pct_of_start),
                    s(r.age_sex_composition_pct_of_start),
                    s(r.age_sex_specific_rates_pct_of_start),
                ]
            )
    write("table_s8", dec)
    parts.append(
        "**Table S8.** Contributions of population size, age structure and age-specific rates "
        "to the observed change in discharges (percentage of discharges in the first year).\n\n"
        + md(
            [
                "Period",
                "Diagnosis group",
                "First year",
                "2019",
                "Change",
                "Population size",
                "Age structure",
                "Age-specific rates",
            ],
            rows,
            ["---", "---"] + ["---:"] * 6,
        )
        + "\n\nContributions sum to the observed change. Counts are sums of sex-by-age strata. "
        "The I62 rate contribution includes the 2019 coding change. The aggregate rate "
        f"contribution depends on the start year ({start_year_note(dec)}), because 2011 is "
        "the first year on the 2011 census basis.\n"
    )
    reg = pd.read_csv(T / "regional_summary_2035.csv")
    cat = pd.read_csv(T / "extsens_regional_catchment.csv")
    cat = cat.pivot_table(index="land", columns="aggregate", values="catchment-weighted")
    reg = reg.sort_values("gap_excl_s06_pct", ascending=False)
    rows = [
        [
            STATE_EN[r.land] + ("*" if r.city_state else ""),
            s(r.population_change_pct),
            f"{r.age65_share_2024:.1f} to {r.age65_share_2035:.1f}",
            n(r.baseline_cases),
            n(r.model_0, 10),
            n(r.model_1, 10),
            s(r.gap_all_pct),
            s(r.gap_excl_s06_pct),
            s(cat.loc[r.land, "excluding_intracranial_injury"]),
            s(r.size_pct),
            s(r.composition_pct),
        ]
        for r in reg.itertuples()
    ]
    write("table_s5", reg.merge(cat.reset_index(), on="land"))
    parts.append(
        "**Table S5.** Projections by federal state, 2035 (scenario G2-L2-W2; 2024 rates).\n\n"
        + md(
            [
                "Federal state",
                "Population change, %",
                "Aged ≥65 y, % (2024 to 2035)",
                "Discharges 2024",
                "Population-based 2035",
                "Age-structured 2035",
                "Difference, all, %",
                "Difference, except S06, %",
                "Difference, except S06, catchment-weighted, %",
                "Population size, %",
                "Age structure, %",
            ],
            rows,
            ["---"] + ["---:"] * 10,
        )
        + "\n\nDischarges are counted in the federal state of the treating hospital; rates use "
        "the resident population. *City-states. Catchment-weighted: denominators are the "
        "populations of all federal states weighted by the 2024 share of their residents "
        "treated in the state concerned (all diagnoses; GENESIS table 23131-0012). Population "
        "size and age structure: contributions to the change from 2024 to the age-structured "
        "projection for all study diagnoses, as a percentage of 2024 discharges.\n"
    )
    cen = pd.read_csv(T / "census_rebasing_diagnostics.csv")
    cen = cen.loc[cen["year"].isin([2010, 2011, 2021, 2022])]
    write("table_s3", cen)
    rows = [
        [
            str(int(r.year)),
            r.census_basis.replace("Zensus", "Census"),
            n(r.population),
            n(r.cases),
            f"{r.crude_rate_per_100000:.1f}",
            s(r.population_change_pct, 2),
            s(r.cases_change_pct, 2),
            s(r.crude_rate_change_pct, 2),
        ]
        for r in cen.itertuples()
    ]
    parts.append(
        "**Table S3.** Population denominators and discharges around the census revisions.\n\n"
        + md(
            [
                "Year",
                "Census basis",
                "Population",
                "Discharges",
                "Crude rate per 100,000",
                "Population change, %",
                "Discharge change, %",
                "Rate change, %",
            ],
            rows,
            ["---:", "---"] + ["---:"] * 6,
        )
        + "\n\nAll study diagnoses. Changes relative to the previous year.\n"
    )

    def number(part: str) -> int:
        return int(re.search(r"Table S(\d+)", part).group(1))

    return "\n\n".join(sorted(parts, key=number))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tables_main.md").write_text(main_tables())
    (OUT / "tables_supplement.md").write_text(supplement_tables())
    print("ok")
