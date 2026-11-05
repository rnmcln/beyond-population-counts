#!/usr/bin/env python3
"""Extended sensitivity analyses requested at internal review (post hoc).

1. All 27 variants of the 16th coordinated population projection.
2. Finer top-coding (85-89 and 90+) using Land-level population tables summed to Germany.
3. Person-year denominators (annual average population; mean of adjacent projected stocks).
4. Age-only rates (sexes combined).
5. Catchment-weighted regional denominators from treatment-by-residence flows (23131-0012).
6. Backtest errors split by target period and with signed errors.

Outputs: outputs/tables/extsens_*.csv and outputs/logs/extsens_run.json
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from neurodemography.codebook import load_diagnosis_codebook, map_service_lines
from neurodemography.genesis import read_ffcsv

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/genesis"
RAWS = ROOT / "data/raw/genesis_sensitivity"
OUT = ROOT / "outputs/tables"
BASE, HORIZON = 2024, 2035
EXCL = {"intracranial_injury"}
GROUPS20 = (
    ["0", "1-4", "5-9", "10-14", "15-17", "18-19"]
    + [f"{a}-{a + 4}" for a in range(20, 85, 5)]
    + ["85+"]
)


def age_band(age: int, top: int) -> str:
    if age >= top:
        return f"{top}+"
    if age == 0:
        return "0"
    for lo, hi in ((1, 4), (5, 9), (10, 14), (15, 17), (18, 19)):
        if lo <= age <= hi:
            return f"{lo}-{hi}"
    lo = (age // 5) * 5
    return f"{lo}-{lo + 4}"


def single_age(label: str) -> int:
    text = str(label)
    if text.startswith("unter 1"):
        return 0
    match = re.match(r"(\d+)", text)
    return int(match.group(1)) if match else None


def sex_of(label: str) -> str | None:
    return {"männlich": "male", "weiblich": "female"}.get(str(label).strip())


def numeric(series: pd.Series, multiplier: float = 1.0) -> pd.Series:
    return pd.to_numeric(series.str.replace(",", "."), errors="coerce") * multiplier


def projected_single_ages() -> pd.DataFrame:
    frames = []
    for path in sorted((RAWS / "12421-0002").glob("*.zip")):
        raw = read_ffcsv(path)
        frames.append(
            pd.DataFrame(
                {
                    "year": raw["time"].str[:4].astype(int),
                    "variant": raw["2_variable_attribute_label"].str.extract(r"\(([^)]+)\)")[0],
                    "kind": raw["2_variable_attribute_code"],
                    "sex": raw["3_variable_attribute_label"].map(sex_of),
                    "age": raw["4_variable_attribute_label"].map(single_age),
                    "population": numeric(raw["value"], 1000.0),
                }
            )
        )
    out = pd.concat(frames, ignore_index=True).dropna(subset=["sex", "age"])
    out["age"] = out["age"].astype(int)
    return out.loc[out["kind"].str.startswith("BEV-VARIANTE")]


def diagnoses_fine(top: int) -> pd.DataFrame:
    path = sorted(RAW.joinpath("23131-0002").glob("*_uncompressed.zip"))[-1]
    raw = read_ffcsv(path)
    raw = raw.loc[raw["4_variable_code"] == "ICD10C"]
    frame = pd.DataFrame(
        {
            "year": raw["time"].astype(int),
            "sex": raw["2_variable_attribute_label"].map(sex_of),
            "label": raw["3_variable_attribute_label"],
            "icd10": raw["4_variable_attribute_code"].str.removeprefix("ICD10-"),
            "cases": numeric(raw["value"]).fillna(0.0),
        }
    ).dropna(subset=["sex"])
    frame = frame.loc[(frame["year"] == BASE) & (frame["label"] != "Insgesamt")]

    def band(label: str) -> str:
        if label.startswith("unter 1"):
            return "0"
        lo = int(re.match(r"(\d+)", label).group(1))
        return age_band(lo, top)

    frame["age_group"] = frame["label"].map(band)
    return frame.groupby(["sex", "age_group", "icd10"], as_index=False)["cases"].sum()


def gap_by_line(cases: pd.DataFrame, pop0: pd.Series, pop1: pd.Series, codebook) -> pd.Series:
    """Relative gap (%) for each service line and the two aggregates."""
    mapped = map_service_lines(cases.assign(year=BASE, geography="Germany"), codebook)
    keys = ["sex", "age_group"]
    by_line = mapped.groupby(["service_line", *keys])["cases"].sum()
    results = {}
    for line, frame in by_line.groupby(level=0):
        c = frame.droplevel(0).reindex(pop0.index).fillna(0.0)
        results[line] = (c, c / pop0)
    out = {}
    sets = {
        "all_prespecified": list(results),
        "excluding_intracranial_injury": [k for k in results if k not in EXCL],
    }
    for name, lines in [(k, [k]) for k in results] + list(sets.items()):
        m0 = sum(results[k][0].sum() for k in lines) * pop1.sum() / pop0.sum()
        m1 = sum(float((results[k][1] * pop1).sum()) for k in lines)
        out[name] = 100 * (m1 / m0 - 1)
    return pd.Series(out)


def main() -> None:
    codebook = load_diagnosis_codebook(ROOT / "metadata/diagnosis_codebook.csv")
    diag = pd.read_csv(ROOT / "data/processed/diagnoses.csv", dtype={"age_group": str})
    obs = pd.read_csv(ROOT / "data/processed/population_observed.csv", dtype={"age_group": str})
    keys = ["sex", "age_group"]
    cases24 = diag.loc[diag["year"] == BASE, [*keys, "icd10", "cases"]]
    pop24 = obs.loc[obs["year"] == BASE].set_index(keys)["population"]
    proj = projected_single_ages()
    proj["age_group"] = proj["age"].map(lambda a: age_band(a, 85))

    def projected(variant: str, year: int, top: int = 85) -> pd.Series:
        p = proj.loc[(proj["variant"] == variant) & (proj["year"] == year)].copy()
        p["age_group"] = p["age"].map(lambda a: age_band(int(a), top))
        return p.groupby(keys)["population"].sum()

    # 1. All variants.
    rows = []
    for variant in sorted(proj["variant"].unique()):
        for year in (2030, 2035, 2040):
            gaps = gap_by_line(
                cases24, pop24, projected(variant, year).reindex(pop24.index), codebook
            )
            rows.append({"variant": variant, "horizon": year, **gaps.to_dict()})
    variants = pd.DataFrame(rows)
    variants.to_csv(OUT / "extsens_all_variants.csv", index=False)

    # 2. Finer top-coding: 85-89 and 90+ (Land-level 2024 population summed to Germany).
    land = read_ffcsv(sorted((RAW / "12411-0013").glob("*.zip"))[-1])
    land = land.loc[land["time"].str.startswith(str(BASE))]
    lp = pd.DataFrame(
        {
            "sex": land["2_variable_attribute_label"].map(sex_of),
            "age": land["3_variable_attribute_label"].map(single_age),
            "population": numeric(land["value"]),
            "land": land["1_variable_attribute_code"],
        }
    ).dropna(subset=["sex", "age"])
    lp = lp.loc[lp["land"].str.strip() != ""]
    lp["age_group"] = lp["age"].map(lambda a: age_band(int(a), 90))
    pop24_90 = lp.groupby(keys)["population"].sum()
    check = abs(pop24_90.sum() - pop24.sum())
    fine = diagnoses_fine(90)
    top = {}
    for label, cases, p0, top_age in (
        ("85+ (primary)", cases24, pop24, 85),
        ("90+ (85-89 and 90+ separated)", fine, pop24_90, 90),
    ):
        p1 = projected("G2L2W2", HORIZON, top_age).reindex(p0.index)
        top[label] = gap_by_line(cases, p0, p1, codebook)
    topcode = pd.DataFrame(top).T
    topcode.to_csv(OUT / "extsens_topcoding.csv")

    # 3. Person-year denominators.
    avg = read_ffcsv(sorted((RAWS / "12411-0041").glob("*.zip"))[-1])
    avg = avg.loc[(avg["2_variable_attribute_label"] == "Insgesamt")]
    av = pd.DataFrame(
        {
            "sex": avg["3_variable_attribute_label"].map(sex_of),
            "age": avg["4_variable_attribute_label"].map(single_age),
            "population": numeric(avg["value"]),
        }
    ).dropna(subset=["sex", "age"])
    av["age_group"] = av["age"].map(lambda a: age_band(int(a), 85))
    pop24_avg = av.groupby(keys)["population"].sum().reindex(pop24.index)
    p_mid = ((projected("G2L2W2", 2034) + projected("G2L2W2", 2035)) / 2).reindex(pop24.index)
    personyears = pd.DataFrame(
        {
            "31 December stocks (primary)": gap_by_line(
                cases24, pop24, projected("G2L2W2", HORIZON).reindex(pop24.index), codebook
            ),
            "Person-years (annual average; mean of adjacent projected stocks)": gap_by_line(
                cases24, pop24_avg, p_mid, codebook
            ),
        }
    ).T
    personyears.to_csv(OUT / "extsens_person_years.csv")

    # 4. Age-only rates.
    c_age = (
        cases24.assign(sex="all")
        .groupby(["sex", "age_group", "icd10"], as_index=False)["cases"]
        .sum()
    )
    p0_age = pop24.groupby(level="age_group").sum()
    p0_age.index = pd.MultiIndex.from_product([["all"], p0_age.index], names=keys)
    p1_age = projected("G2L2W2", HORIZON).groupby(level="age_group").sum()
    p1_age.index = pd.MultiIndex.from_product([["all"], p1_age.index], names=keys)
    ageonly = pd.DataFrame(
        {
            "Age and sex (primary)": topcode.loc["85+ (primary)"],
            "Age only": gap_by_line(c_age, p0_age, p1_age.reindex(p0_age.index), codebook),
        }
    ).T
    ageonly.to_csv(OUT / "extsens_age_only.csv")

    # 5. Catchment-weighted regional denominators.
    flows = read_ffcsv(sorted((RAW / "23131-0012").glob("*.zip"))[-1])
    flows = flows.loc[flows["2_variable_attribute_label"] == "Insgesamt"]
    fl = pd.DataFrame(
        {
            "treat": flows["1_variable_attribute_label"],
            "res": flows["3_variable_attribute_label"],
            "n": numeric(flows["value"]),
        }
    )
    laender = sorted(fl["treat"].unique())
    fl = fl.loc[fl["res"].isin(laender)]
    mat = fl.pivot_table(index="treat", columns="res", values="n", aggfunc="sum").fillna(0)
    share = mat / mat.sum(axis=0)  # share of residents of j treated in i
    berlin_from_bb = float(
        mat.loc["Berlin", "Brandenburg"]
        / flows.loc[
            (flows["1_variable_attribute_label"] == "Berlin")
            & (flows["3_variable_attribute_label"].isin(laender + ["Ausland", "unbekannt"])),
            "value",
        ]
        .pipe(numeric)
        .sum()
    )
    # Table 23131-0011 does not state whether Laender refer to residence or treatment.
    # Its 2024 all-diagnosis totals are compared with the row sums of the
    # treatment-by-residence table (16 Laender of residence plus abroad and unknown).
    reg = read_ffcsv(sorted((RAW / "23131-0011").glob("*.zip"))[-1])
    reg = reg.loc[
        (reg["time"].astype(str) == "2024")
        & (reg["2_variable_attribute_label"] == "Insgesamt")
        & (reg["3_variable_attribute_label"] == "Insgesamt")
        & (reg["4_variable_attribute_label"] == "Insgesamt")
    ]
    reg_totals = numeric(reg["value"]).groupby(reg["1_variable_attribute_label"].values).sum()
    by_treatment = flows.loc[
        ~flows["3_variable_attribute_label"].isin(["Insgesamt", "Deutschland"])
    ]
    flow_totals = (
        numeric(by_treatment["value"])
        .groupby(by_treatment["1_variable_attribute_label"].values)
        .sum()
    )
    treatment_check = float((reg_totals - flow_totals.reindex(reg_totals.index)).abs().max())
    rd = map_service_lines(
        pd.read_csv(ROOT / "data/processed/regional_diagnoses.csv", dtype={"age_group": str}),
        codebook,
    )
    rpo = pd.read_csv(
        ROOT / "data/processed/regional_population_observed.csv", dtype={"age_group": str}
    )
    rpp = pd.read_csv(
        ROOT / "data/processed/regional_population_projected.csv", dtype={"age_group": str}
    )
    p0 = rpo.loc[rpo["year"] == BASE].pivot_table(
        index=keys, columns="geography", values="population"
    )
    p1 = rpp.loc[(rpp["year"] == HORIZON) & (rpp["scenario"] == "G2L2W2")].pivot_table(
        index=keys, columns="geography", values="population"
    )
    share = share.reindex(index=p0.columns, columns=p0.columns)
    c0 = p0 @ share.T  # catchment population for each treating Land
    c1 = p1 @ share.T
    reg = []
    for aggregate, exclude in (
        ("all_prespecified", set()),
        ("excluding_intracranial_injury", EXCL),
    ):
        sel = rd.loc[(rd["year"] == BASE) & ~rd["service_line"].isin(exclude)]
        cases = sel.pivot_table(index=keys, columns="geography", values="cases", aggfunc="sum")
        for label, d0, d1 in (("resident", p0, p1), ("catchment-weighted", c0, c1)):
            for landname in p0.columns:
                c = cases[landname].reindex(d0.index).fillna(0)
                m0 = c.sum() * d1[landname].sum() / d0[landname].sum()
                m1 = float((c / d0[landname] * d1[landname]).sum())
                reg.append(
                    {
                        "aggregate": aggregate,
                        "denominator": label,
                        "land": landname,
                        "gap_relative_pct": 100 * (m1 / m0 - 1),
                    }
                )
    regional = (
        pd.DataFrame(reg)
        .pivot_table(index=["aggregate", "land"], columns="denominator", values="gap_relative_pct")
        .reset_index()
    )
    regional.to_csv(OUT / "extsens_regional_catchment.csv", index=False)

    # 6. Backtest by target period.
    bt = pd.read_csv(OUT / "rolling_origin_backtest.csv")
    bt = bt.loc[bt["service_line"] == "all_prespecified"].copy()
    bt["period"] = np.where(
        bt["horizon"] <= 2019,
        "targets up to 2019",
        np.where(bt["horizon"] >= 2023, "targets 2023-2024", "targets 2020-2022"),
    )
    summ = (
        bt.groupby(["backtest_horizon_years", "period"])
        .apply(
            lambda g: pd.Series(
                {
                    "pairs": len(g),
                    "model_0_wape": 100
                    * g["model_0_absolute_error"].sum()
                    / g["observed_cases"].sum(),
                    "model_1_wape": 100
                    * g["model_1_absolute_error"].sum()
                    / g["observed_cases"].sum(),
                    "model_0_mean_signed_pct": 100
                    * (g["model_0_error"] / g["observed_cases"]).mean(),
                    "model_1_mean_signed_pct": 100
                    * (g["model_1_error"] / g["observed_cases"]).mean(),
                    "model_1_better_pairs": int(
                        (g["model_1_absolute_error"] < g["model_0_absolute_error"]).sum()
                    ),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    summ.to_csv(OUT / "extsens_backtest_periods.csv", index=False)

    log = {
        "run_at_utc": datetime.now(UTC).isoformat(),
        "land_sum_vs_national_population_2024_abs_difference": float(check),
        "berlin_discharges_share_brandenburg_residents_2024": berlin_from_bb,
        "regional_table_vs_treatment_flows_2024_max_abs_difference": treatment_check,
        "status": "post hoc sensitivity analyses",
    }
    (ROOT / "outputs/logs/extsens_run.json").write_text(json.dumps(log, indent=2))
    pd.set_option("display.width", 250)
    v = variants.loc[variants["horizon"] == HORIZON]
    print(v[["variant", "all_prespecified", "excluding_intracranial_injury"]].round(2).to_string())
    print(topcode.round(2).T.to_string())
    print(personyears.round(2).T.to_string())
    print(ageonly.round(2).T.to_string())
    print(regional.round(2).to_string())
    print(summ.round(2).to_string())
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
