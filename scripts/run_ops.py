#!/usr/bin/env python3
"""Procedure-based corroboration: Models 0/1 for selected cranial OPS codes.

Source: GENESIS table 23141-0102 (operations and procedures in full inpatient care,
Germany, by sex and age group; 4-digit OPS level). The unit is the procedure, so a
patient with several procedures contributes several counts. Codes are analysed
separately and are not summed.

Output: outputs/tables/ops_models_0_1.csv
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from neurodemography.config import load_config, resolve_project_path
from neurodemography.genesis import _diagnosis_age_group, _sex, read_ffcsv

ROOT = Path(__file__).resolve().parents[1]
OLD = ["65-69", "70-74", "75-79", "80-84", "85+"]
LABELS = {
    "5-013": "Incision of brain and meninges (incl. evacuation of subdural haematoma)",
    "5-015": "Excision or destruction of intracranial lesion",
    "5-022": "Incision of the CSF system (incl. external ventricular drainage)",
    "5-023": "Implantation of a CSF shunt",
}


def load_procedures() -> pd.DataFrame:
    files = sorted((ROOT / "data/raw/genesis/23141-0102").glob("*.zip"))
    if not files:
        raise SystemExit("Missing 23141-0102 download; see docs/data_retrieval.md")
    raw = read_ffcsv(files[-1])
    rows = pd.DataFrame(
        {
            "year": raw["time"].astype(int),
            "sex": raw["2_variable_attribute_label"].map(_sex),
            "age_group": raw["3_variable_attribute_label"].map(
                lambda v: _diagnosis_age_group(v, topcode=85)
            ),
            "ops": raw["4_variable_attribute_code"].str.removeprefix("OPS-"),
            "value": raw["value"],
        }
    )
    rows = rows.dropna(subset=["sex", "age_group"])
    rows = rows.loc[rows["ops"].isin(LABELS)]
    numeric = pd.to_numeric(rows["value"], errors="coerce")
    rows["procedures"] = numeric.where(numeric.notna(), np.where(rows["value"] == "-", 0, np.nan))
    if rows["procedures"].isna().any():
        raise ValueError("Unexpected suppressed procedure cells")
    return rows.groupby(["year", "sex", "age_group", "ops"], as_index=False)["procedures"].sum()


def main() -> None:
    config = load_config()
    study = config["study"]
    paths = config["paths"]
    base = study["baseline_year"]
    procedures = load_procedures()
    observed = pd.read_csv(
        resolve_project_path(paths["population_observed"]), dtype={"age_group": str}
    )
    projected = pd.read_csv(
        resolve_project_path(paths["population_projected"]), dtype={"age_group": str}
    )
    keys = ["sex", "age_group"]
    pop0 = observed.loc[observed["year"] == base].set_index(keys)["population"]
    records = []
    for code, frame in procedures.groupby("ops"):
        cases = frame.loc[frame["year"] == base].set_index(keys)["procedures"].reindex(pop0.index)
        if cases.isna().any():
            raise ValueError(f"Strata missing for {code}")
        rate = cases / pop0
        for horizon in [2030, 2035, 2040]:
            fut = (
                projected.loc[
                    (projected["year"] == horizon)
                    & (projected["scenario"] == study["projection_scenario"])
                ]
                .set_index(keys)["population"]
                .reindex(pop0.index)
            )
            m0 = cases.sum() * fut.sum() / pop0.sum()
            m1 = float((rate * fut).sum())
            records.append(
                {
                    "ops": code,
                    "label": LABELS.get(code, code),
                    "baseline_year": base,
                    "horizon": horizon,
                    "scenario": study["projection_scenario"],
                    "baseline_procedures": cases.sum(),
                    "age_65_plus_pct": 100
                    * cases.loc[cases.index.get_level_values(1).isin(OLD)].sum()
                    / cases.sum(),
                    "age_80_plus_pct": 100
                    * cases.loc[cases.index.get_level_values(1).isin(["80-84", "85+"])].sum()
                    / cases.sum(),
                    "procedures_2019": frame.loc[frame["year"] == 2019, "procedures"].sum(),
                    "model_0": m0,
                    "model_1": m1,
                    "gap_absolute": m1 - m0,
                    "gap_relative_pct": 100 * (m1 / m0 - 1),
                }
            )
    out = pd.DataFrame(records)
    table_dir = resolve_project_path(paths["output_tables"])
    out.to_csv(table_dir / "ops_models_0_1.csv", index=False)
    log = resolve_project_path(paths["output_logs"])
    (log / "ops_run.json").write_text(
        json.dumps(
            {
                "run_at_utc": datetime.now(UTC).isoformat(),
                "source": "23141-0102",
                "codes": sorted(LABELS),
                "unit": "procedures; codes analysed separately and not summed",
            },
            indent=2,
        )
    )
    print(out.loc[out["horizon"] == 2035].round(1).to_string())


if __name__ == "__main__":
    main()
