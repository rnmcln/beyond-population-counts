#!/usr/bin/env python3
"""ICD-10 and table-definition audit of the untouched 23131-0002 extract.

Outputs (outputs/tables/):
  icd_audit_reconciliation.csv   stratum sums versus official GENESIS totals
  icd_audit_series.csv           annual counts, year-on-year change and discontinuity flags
  icd_audit_age_topcode.csv      distribution of 85+ discharges across 85-89, 90-94, 95+
  icd_audit_share_all_cause.csv  study codes as a share of all-cause discharges
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw/genesis/23131-0002"
OUT = ROOT / "outputs/tables"
LOG = ROOT / "outputs/logs"
DISCONTINUITY_PCT = 10.0
DISRUPTION_YEARS = {2020, 2021}


def load_raw(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        (name,) = archive.namelist()
        text = archive.read(name).decode("utf-8-sig")
    frame = pd.read_csv(io.StringIO(text), sep=";", dtype=str, keep_default_na=False)
    frame = frame.rename(
        columns={
            "time": "year",
            "2_variable_attribute_code": "sex_code",
            "3_variable_attribute_code": "age_code",
            "4_variable_code": "icd_level",
            "4_variable_attribute_code": "icd_code",
        }
    )
    frame["year"] = frame["year"].astype(int)
    numeric = pd.to_numeric(frame["value"].str.replace(",", "."), errors="coerce")
    structural_zero = np.where(frame["value"] == "-", 0.0, np.nan)
    frame["quality_sign"] = np.where(numeric.isna(), frame["value"], "")
    frame["cases"] = numeric.where(numeric.notna(), structural_zero)
    return frame[["year", "sex_code", "age_code", "icd_level", "icd_code", "cases", "quality_sign"]]


def main() -> None:
    files = sorted(RAW_DIR.glob("*_uncompressed.zip"))
    if not files:
        raise SystemExit("Missing uncompressed 23131-0002 download; run `make data` first.")
    raw_path = files[-1]
    raw = load_raw(raw_path)
    study = raw.loc[raw["icd_code"].str.startswith("ICD10-")].copy()
    study["icd10"] = study["icd_code"].str.removeprefix("ICD10-")

    # 1. Reconciliation of mutually exclusive strata against official totals.
    detail = study.loc[(study["sex_code"] != "") & (study["age_code"] != "")]
    total = study.loc[(study["sex_code"] == "") & (study["age_code"] == "")]
    strata_sum = detail.groupby(["year", "icd10"], as_index=False)["cases"].sum()
    rec = strata_sum.merge(
        total[["year", "icd10", "cases"]].rename(columns={"cases": "official_total"}),
        on=["year", "icd10"],
        how="outer",
        validate="one_to_one",
    )
    rec["difference"] = rec["cases"] - rec["official_total"]
    rec = rec.rename(columns={"cases": "sum_of_sex_age_strata"})
    # Unknown sex/age can make strata sums fall short of totals; record, do not impute.
    rec["difference_pct"] = 100 * rec["difference"] / rec["official_total"]

    # 2. Annual series and discontinuities.
    series = total[["year", "icd10", "cases"]].sort_values(["icd10", "year"]).copy()
    series["yoy_change_pct"] = 100 * series.groupby("icd10")["cases"].pct_change()
    series["flag_discontinuity"] = (series["yoy_change_pct"].abs() >= DISCONTINUITY_PCT) & ~series[
        "year"
    ].isin(DISRUPTION_YEARS)
    series["flag_disruption_year"] = series["year"].isin(DISRUPTION_YEARS)
    allcause = raw.loc[
        (raw["icd_level"] == "ICD10A")
        & (raw["icd_code"] == "")
        & (raw["sex_code"] == "")
        & (raw["age_code"] == "")
    ]
    allcause = allcause[["year", "cases"]].rename(columns={"cases": "all_cause_discharges"})
    if allcause.empty:
        allcause = (
            raw.loc[
                (raw["icd_code"] == "") & (raw["sex_code"] == "") & (raw["age_code"] == ""),
                ["year", "cases"],
            ]
            .drop_duplicates("year")
            .rename(columns={"cases": "all_cause_discharges"})
        )

    # 3. Composition of the 85+ top-coded group.
    old = detail.loc[detail["age_code"].isin(["ALT085B90", "ALT090B95", "ALT095UM"])]
    topcode = old.pivot_table(
        index=["year", "icd10"], columns="age_code", values="cases", aggfunc="sum"
    ).reset_index()
    topcode.columns.name = None
    topcode["cases_85_plus"] = topcode[["ALT085B90", "ALT090B95", "ALT095UM"]].sum(axis=1)
    all_age = detail.groupby(["year", "icd10"], as_index=False)["cases"].sum()
    topcode = topcode.merge(
        all_age.rename(columns={"cases": "cases_all_ages"}), on=["year", "icd10"]
    )
    topcode["share_85_plus_pct"] = 100 * topcode["cases_85_plus"] / topcode["cases_all_ages"]
    topcode["share_90_plus_within_85_plus_pct"] = (
        100 * (topcode["ALT090B95"] + topcode["ALT095UM"]) / topcode["cases_85_plus"]
    )
    topcode = topcode.rename(
        columns={
            "ALT085B90": "cases_85_89",
            "ALT090B95": "cases_90_94",
            "ALT095UM": "cases_95_plus",
        }
    )

    # 4. Share of all-cause discharges.
    share = (
        series.groupby("year", as_index=False)["cases"]
        .sum()
        .rename(columns={"cases": "study_code_discharges"})
    )
    share = share.merge(allcause, on="year", how="left")
    share["share_pct"] = 100 * share["study_code_discharges"] / share["all_cause_discharges"]

    flags = (
        study.loc[study["quality_sign"] != ""]
        .groupby(["icd10", "quality_sign"], as_index=False)
        .size()
        .rename(columns={"size": "cells"})
    )

    OUT.mkdir(parents=True, exist_ok=True)
    rec.to_csv(OUT / "icd_audit_reconciliation.csv", index=False)
    series.to_csv(OUT / "icd_audit_series.csv", index=False)
    topcode.to_csv(OUT / "icd_audit_age_topcode.csv", index=False)
    share.to_csv(OUT / "icd_audit_share_all_cause.csv", index=False)
    flags.to_csv(OUT / "icd_audit_quality_signs.csv", index=False)
    manifest = {
        "run_at_utc": datetime.now(UTC).isoformat(),
        "raw_file": raw_path.name,
        "discontinuity_threshold_pct": DISCONTINUITY_PCT,
        "excluded_from_flagging": sorted(DISRUPTION_YEARS),
        "max_abs_reconciliation_difference": float(rec["difference"].abs().max()),
        "flagged_discontinuities": series.loc[
            series["flag_discontinuity"], ["icd10", "year", "yoy_change_pct"]
        ]
        .round(2)
        .to_dict(orient="records"),
    }
    LOG.mkdir(parents=True, exist_ok=True)
    (LOG / "icd_audit_run.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
