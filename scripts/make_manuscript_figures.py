#!/usr/bin/env python3
"""Manuscript and supplementary figures, built from versioned output tables.

Design rules: no titles or legend boxes inside figures (direct labelling only);
greyscale with one muted blue accent reserved for the age/sex-structured projection
and the age/sex-structure component; thin lines; no gridlines; three type sizes
(6, 7 and 8 pt); exact journal widths (88 or 180 mm). Exports PDF, SVG and 600-dpi PNG
to outputs/figures/manuscript/ with fixed metadata so that reruns are byte-stable.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs/tables"
OUT = ROOT / "outputs/figures/manuscript"

INK = "#2E3440"
GREY = "#7B8394"
LIGHT = "#C9CED6"
ACCENT = "#5E81AC"
MM = 1 / 25.4
DOUBLE = 180 * MM
SINGLE = 88 * MM
SMALL, BASE, LARGE = 6, 7, 8

LABELS = {
    "cns_malignancy": "Malignant CNS neoplasm (C70–C72)",
    "meningioma": "Meningioma (D32)",
    "benign_cns_other": "Benign brain or CNS neoplasm (D33)",
    "subarachnoid_haemorrhage": "Subarachnoid haemorrhage (I60)",
    "intracerebral_haemorrhage": "Intracerebral haemorrhage (I61)",
    "other_intracranial_haemorrhage": "Subdural and other nontraumatic haemorrhage (I62)",
    "hydrocephalus": "Hydrocephalus (G91)",
    "intracranial_injury": "Intracranial injury (S06)",
    "all_prespecified": "All study diagnoses",
    "excluding_intracranial_injury": "All study diagnoses except S06",
}
ORDER = [
    "cns_malignancy",
    "meningioma",
    "benign_cns_other",
    "subarachnoid_haemorrhage",
    "intracerebral_haemorrhage",
    "other_intracranial_haemorrhage",
    "hydrocephalus",
    "intracranial_injury",
]
AGE_ORDER = (
    ["0", "1-4", "5-9", "10-14", "15-17", "18-19"]
    + [f"{a}-{a + 4}" for a in range(20, 85, 5)]
    + ["85+"]
)
AGE_MID = {
    "0": 0.5,
    "1-4": 3.0,
    "5-9": 7.5,
    "10-14": 12.5,
    "15-17": 16.5,
    "18-19": 19.0,
    **{f"{a}-{a + 4}": a + 2.5 for a in range(20, 85, 5)},
    "85+": 89.0,
}
SCENARIO = "G2L2W2"


def fmt(x: float, _pos: int | None = None) -> str:
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    return f"{x:g}"


def style() -> None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    family = next((f for f in ("Arial", "Liberation Sans") if f in available), None)
    if family is None:
        raise SystemExit("Arial or Liberation Sans (metric-compatible TrueType) is required")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [family],
            "font.size": BASE,
            "axes.labelsize": BASE,
            "axes.titlesize": BASE,
            "xtick.labelsize": SMALL,
            "ytick.labelsize": SMALL,
            "axes.linewidth": 0.5,
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "xtick.major.width": 0.5,
            "ytick.major.width": 0.5,
            "xtick.major.size": 2.5,
            "ytick.major.size": 2.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "lines.linewidth": 0.8,
            "svg.fonttype": "none",
            "svg.hashsalt": "beyond-population-counts",
            "pdf.fonttype": 42,
            "figure.constrained_layout.use": True,
        }
    )


def panel(ax, letter: str) -> None:
    ax.annotate(
        letter,
        xy=(0, 1),
        xycoords="axes fraction",
        xytext=(-24, 6),
        textcoords="offset points",
        fontsize=LARGE,
        va="bottom",
        ha="left",
    )


def save(fig, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.pdf", metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(OUT / f"{stem}.svg", metadata={"Date": None})
    fig.savefig(OUT / f"{stem}.png", dpi=600)
    plt.close(fig)
    print(stem)


def dotrows(ax, labels: list[str]) -> None:
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)


# Figure 1 ---------------------------------------------------------------------------
def figure_1() -> None:
    rates = pd.read_csv(TABLES / "historical_age_sex_rates.csv", dtype={"age_group": str})
    fig, axes = plt.subplots(4, 2, figsize=(DOUBLE, 190 * MM), sharex=True)
    for i, (ax, line) in enumerate(zip(axes.flat, ORDER, strict=True)):
        data = rates.loc[rates["service_line"] == line]
        for sex, colour, dash, name in (
            ("female", INK, (), "Women"),
            ("male", GREY, (3, 1.5), "Men"),
        ):
            d = data.loc[data["sex"] == sex].set_index("age_group").reindex(AGE_ORDER)
            x = [AGE_MID[a] for a in AGE_ORDER]
            ax.plot(x, d["rate_per_100000"], color=colour, dashes=dash)
            if i == 0:
                ax.text(
                    91,
                    d["rate_per_100000"].iloc[-1],
                    name,
                    color=colour,
                    va="center",
                    fontsize=SMALL,
                )
        ax.set_title(LABELS[line], loc="left", pad=2, fontsize=BASE)
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(FuncFormatter(fmt))
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 20, 40, 60, 80])
        ax.spines["bottom"].set_bounds(0, 90)
    for ax in axes[-1]:
        ax.set_xlabel("Age (years)")
    fig.supylabel("Annual discharges per 100,000 population (2022–2024)", fontsize=BASE)
    save(fig, "figure_1_age_sex_rates")


# Figure 2 ---------------------------------------------------------------------------
def figure_2() -> None:
    models = pd.read_csv(TABLES / "models_0_1.csv")
    agg = pd.read_csv(TABLES / "posthoc_aggregate_excluding_s06.csv")
    agg = agg.loc[agg["scenario"] == SCENARIO]
    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE, 64 * MM))
    sets = [
        models.loc[models["service_line"] == "all_prespecified"],
        agg.loc[agg["aggregate"] == "excluding_intracranial_injury"],
    ]
    for ax, letter, frame in zip(axes, "AB", sets, strict=True):
        frame = frame.sort_values("horizon")
        base = frame["baseline_cases"].iloc[0]
        years = [2024, *frame["horizon"].tolist()]
        m0 = [base, *frame["model_0"].tolist()]
        m1 = [base, *frame["model_1"].tolist()]
        ax.plot(years, m0, color=GREY, dashes=(3, 1.5), zorder=1)
        ax.plot(years[1:], m0[1:], "o", ms=3, mfc="white", mec=GREY, mew=0.7, zorder=2)
        ax.plot(years, m1, color=ACCENT, zorder=1)
        ax.plot(years[1:], m1[1:], "o", ms=3, color=ACCENT, mew=0, zorder=2)
        ax.plot(2024, base, "o", ms=3.4, color=INK, mew=0, zorder=3)
        ax.annotate(
            "Observed",
            xy=(2024, base),
            xytext=(0, -9),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=SMALL,
        )
        ax.text(2040.8, m1[-1], "Age-structured", color=ACCENT, va="center", fontsize=SMALL)
        ax.text(2040.8, m0[-1], "Population-based", color=GREY, va="center", fontsize=SMALL)
        gap, pct = m1[2] - m0[2], 100 * (m1[2] / m0[2] - 1)
        ax.plot([2035, 2035], [m0[2], m1[2]], color=LIGHT, lw=0.6, zorder=0)
        ax.text(
            2034.5,
            (m0[2] + m1[2]) / 2,
            f"+{round(gap, -2):,.0f}\n(+{pct:.1f}%)",
            ha="right",
            va="center",
            fontsize=SMALL,
        )
        ax.set_xticks(years)
        ax.set_xlim(2020.5, 2047.5)
        ax.spines["bottom"].set_bounds(2024, 2040)
        ax.yaxis.set_major_formatter(FuncFormatter(fmt))
        ax.set_ylabel("Hospital discharges" if letter == "A" else "")
        panel(ax, letter)
    save(fig, "figure_2_projections")


# Figure 3 ---------------------------------------------------------------------------
def gap_table() -> pd.DataFrame:
    models = pd.read_csv(TABLES / "models_0_1.csv")
    agg = pd.read_csv(TABLES / "posthoc_aggregate_excluding_s06.csv")
    agg = agg.loc[
        (agg["scenario"] == SCENARIO) & (agg["aggregate"] == "excluding_intracranial_injury")
    ]
    data = pd.concat([models, agg.rename(columns={"aggregate": "service_line"})])
    return data.pivot_table(index="service_line", columns="horizon", values="gap_relative_pct")


def line_order() -> list[str]:
    return list(gap_table().loc[ORDER].sort_values(2035).index)


def figure_3() -> None:
    wide = gap_table()
    rows = ["all_prespecified", "excluding_intracranial_injury", None, *line_order()]
    fig, ax = plt.subplots(figsize=(DOUBLE, 72 * MM))
    for y, name in enumerate(rows):
        if name is None:
            continue
        r = wide.loc[name]
        ax.plot([min(r[2030], r[2040]), max(r[2030], r[2040])], [y, y], color=LIGHT, zorder=1)
        ax.plot(r[2030], y, "o", ms=2.8, mfc="white", mec=INK, mew=0.6, zorder=2)
        ax.plot(r[2040], y, "D", ms=2.6, mfc="white", mec=INK, mew=0.6, zorder=2)
        ax.plot(r[2035], y, "o", ms=3.4, color=ACCENT, mew=0, zorder=3)
    top = len(rows) - 1
    r = wide.loc[rows[-1]]
    for year, colour in ((2030, INK), (2035, ACCENT), (2040, INK)):
        ax.text(
            r[year], top + 0.6, str(year), ha="center", va="bottom", fontsize=SMALL, color=colour
        )
    ax.axvline(0, color=LIGHT, lw=0.5, zorder=0)
    labels = [LABELS[n] if n else "" for n in rows]
    dotrows(ax, labels)
    ax.set_ylim(-0.6, top + 1.5)
    ax.set_xlabel("Difference between age-structured and population-based projections (%)")
    save(fig, "figure_3_projection_gap")


# Figure 4 ---------------------------------------------------------------------------
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


def figure_4() -> None:
    s = pd.read_csv(TABLES / "regional_summary_2035.csv").sort_values("gap_excl_s06_pct")
    s = s.reset_index(drop=True)
    gaps = gap_table()
    fig, (a, b) = plt.subplots(1, 2, figsize=(DOUBLE, 84 * MM), sharey=True)
    labels = [
        STATE_EN[n] + ("*" if c else "") for n, c in zip(s["land"], s["city_state"], strict=True)
    ]
    for i, r in s.iterrows():
        a.plot([r.gap_all_pct, r.gap_excl_s06_pct], [i, i], color=LIGHT, zorder=1)
        a.plot(r.gap_all_pct, i, "o", ms=3, mfc="white", mec=INK, mew=0.6, zorder=2)
        a.plot(r.gap_excl_s06_pct, i, "o", ms=3.2, color=INK, mew=0, zorder=3)
    a.axvline(gaps.loc["all_prespecified", 2035], color=LIGHT, lw=0.5, dashes=(2, 2), zorder=0)
    a.axvline(
        gaps.loc["excluding_intracranial_injury", 2035], color=GREY, lw=0.5, dashes=(2, 2), zorder=0
    )
    top = len(s) - 1
    t = s.iloc[-1]
    a.annotate(
        "All study diagnoses",
        xy=(t.gap_all_pct, top),
        xytext=(t.gap_all_pct, top + 1.4),
        ha="center",
        fontsize=SMALL,
        arrowprops={"arrowstyle": "-", "color": LIGHT, "lw": 0.4},
    )
    a.annotate(
        "Except S06",
        xy=(t.gap_excl_s06_pct, top),
        xytext=(t.gap_excl_s06_pct, top + 1.4),
        ha="center",
        fontsize=SMALL,
        arrowprops={"arrowstyle": "-", "color": LIGHT, "lw": 0.4},
    )
    dotrows(a, labels)
    a.set_ylim(-0.6, top + 3.0)
    a.set_xlim(0, 13)
    a.set_xlabel("Difference between projections, 2035 (%)")
    panel(a, "A")
    for i, r in s.iterrows():
        vals = [r.size_pct, r.composition_pct, r.model_1_change_pct]
        b.plot([min(vals), max(vals)], [i, i], color=LIGHT, zorder=1)
        b.plot(r.size_pct, i, "s", ms=2.8, mfc="white", mec=INK, mew=0.6, zorder=3)
        b.plot(r.composition_pct, i, "s", ms=2.8, color=ACCENT, mew=0, zorder=3)
        b.plot(r.model_1_change_pct, i, "|", ms=6, color=INK, mew=1.0, zorder=4)
    t = s.iloc[-1]
    for val, text, colour, level in (
        (t.size_pct, "Population size", INK, 1.4),
        (t.composition_pct, "Age structure", ACCENT, 2.3),
        (t.model_1_change_pct, "Net change", INK, 1.4),
    ):
        b.annotate(
            text,
            xy=(val, top),
            xytext=(val, top + level),
            ha="center",
            fontsize=SMALL,
            color=colour,
            arrowprops={"arrowstyle": "-", "color": LIGHT, "lw": 0.4},
        )
    b.axvline(0, color=LIGHT, lw=0.5, zorder=0)
    b.tick_params(axis="y", length=0)
    b.spines["left"].set_visible(False)
    b.set_xticks([-8, -4, 0, 4, 8])
    b.set_xlabel("Change in discharges, 2024 to 2035 (% of 2024)")
    panel(b, "B")
    save(fig, "figure_4_regional")


# Figure 5 ---------------------------------------------------------------------------
def figure_5() -> None:
    s = pd.read_csv(TABLES / "rolling_origin_summary.csv")
    ph = pd.read_csv(TABLES / "posthoc_backtest_summaries.csv")
    nons06 = ph.loc[ph["service_line"] == "excluding_intracranial_injury"].drop(
        columns="restriction"
    )
    s = pd.concat([s, nons06], ignore_index=True)
    fig, (a, b) = plt.subplots(
        1, 2, figsize=(DOUBLE, 78 * MM), gridspec_kw={"width_ratios": [1, 1.25]}
    )
    rows = []
    for aset, tag in (
        ("all_years", "all target years"),
        ("exclude_covid_2020_2022", "excluding 2020–2022"),
    ):
        for h in (1, 3, 5):
            q = s.loc[
                (s["service_line"] == "all_prespecified")
                & (s["analysis_set"] == aset)
                & (s["backtest_horizon_years"] == h)
            ].iloc[0]
            unit = "year" if h == 1 else "years"
            rows.append((f"{h} {unit}, {tag}", q.model_0_wape, q.model_1_wape, int(q.evaluations)))
    rows = rows[::-1]
    for y, (_, m0, m1, n) in enumerate(rows):
        a.plot([m0, m1], [y, y], color=LIGHT, zorder=1)
        a.plot(m0, y + 0.12, "o", ms=3, mfc="white", mec=GREY, mew=0.7, zorder=2)
        a.plot(m1, y - 0.12, "o", ms=3, color=ACCENT, mew=0, zorder=3)
        a.text(12.4, y, f"{n}", va="center", ha="right", fontsize=SMALL, color=GREY)
    a.text(12.4, len(rows) - 0.3, "Pairs", ha="right", fontsize=SMALL, color=GREY)
    dotrows(a, [r[0] for r in rows])
    a.set_xlim(0, 12.6)
    a.set_xticks([0, 2, 4, 6, 8, 10])
    a.spines["bottom"].set_bounds(0, 10)
    a.set_ylim(-0.6, len(rows) + 0.4)
    a.set_xlabel("Weighted absolute percentage error (%)")
    panel(a, "A")
    f = s.loc[
        (s["analysis_set"] == "exclude_covid_2020_2022") & (s["backtest_horizon_years"] == 5)
    ].set_index("service_line")
    order = ["all_prespecified", "excluding_intracranial_injury", *line_order()]
    order = order[::-1]
    for y, line in enumerate(order):
        r = f.loc[line]
        b.plot([r.model_0_wape, r.model_1_wape], [y, y], color=LIGHT, zorder=1)
        b.plot(r.model_0_wape, y, "o", ms=3, mfc="white", mec=GREY, mew=0.7, zorder=2)
        b.plot(r.model_1_wape, y, "o", ms=3, color=ACCENT, mew=0, zorder=3)
    r = f.loc[order[-1]]
    lo, hi = sorted(
        [(r.model_0_wape, "Population-based", GREY), (r.model_1_wape, "Age-structured", ACCENT)]
    )
    b.text(lo[0] - 0.3, len(order) - 0.4, lo[1], ha="right", fontsize=SMALL, color=lo[2])
    b.text(hi[0] + 0.3, len(order) - 0.4, hi[1], ha="left", fontsize=SMALL, color=hi[2])
    dotrows(b, [LABELS[x] for x in order])
    b.set_ylim(-0.6, len(order) + 0.2)
    b.set_xlim(0, 15)
    b.set_xlabel("Weighted absolute percentage error, 5 years (%)")
    panel(b, "B")
    save(fig, "figure_5_backtest")


# Supplementary figures ---------------------------------------------------------------
def figure_s1() -> None:
    std = pd.read_csv(TABLES / "posthoc_standardised_rates.csv")
    fig, axes = plt.subplots(3, 3, figsize=(DOUBLE, 140 * MM), sharex=True)
    for ax, line in zip(axes.flat, ["all_prespecified", *ORDER], strict=True):
        d = std.loc[std["service_line"] == line]
        ax.axvspan(2019.5, 2022.5, color="#ECEFF4", lw=0, zorder=0)
        for x in (2010.5, 2021.5):
            ax.axvline(x, color=GREY, lw=0.4, dashes=(1, 1.5), zorder=1)
        ax.plot(d["year"], d["standardised_rate_per_100000"], color=INK, zorder=3)
        ax.plot(d["year"], d["crude_rate_per_100000"], color=GREY, dashes=(3, 1.5), zorder=2)
        ax.set_title(LABELS[line], loc="left", pad=2, fontsize=SMALL)
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(FuncFormatter(fmt))
        ax.locator_params(axis="y", integer=True, nbins=4)
        ax.set_xticks([2005, 2010, 2015, 2020, 2024])
        if line == "all_prespecified":
            r13 = d.loc[d["year"] == 2013].iloc[0]
            r08 = d.loc[d["year"] == 2008].iloc[0]
            ax.annotate(
                "Standardised",
                xy=(2013, r13["standardised_rate_per_100000"]),
                xytext=(2013, 250),
                ha="center",
                fontsize=SMALL,
                arrowprops={"arrowstyle": "-", "color": LIGHT, "lw": 0.4},
            )
            ax.annotate(
                "Crude",
                xy=(2008, r08["crude_rate_per_100000"]),
                xytext=(2008, 150),
                ha="center",
                fontsize=SMALL,
                color=GREY,
                arrowprops={"arrowstyle": "-", "color": LIGHT, "lw": 0.4},
            )
    fig.supylabel("Discharges per 100,000 population", fontsize=BASE)
    save(fig, "figure_s2_standardised_rates")


def figure_s2() -> None:
    d = pd.read_csv(TABLES / "posthoc_historical_decomposition.csv")
    d = d.loc[d["period"] == "2011-2019"].set_index("service_line")
    rows = ["all_prespecified", None, *line_order()]
    fig, ax = plt.subplots(figsize=(DOUBLE, 80 * MM))
    comps = [
        ("population_size_pct_of_start", "Population size", "s", INK, "white"),
        ("age_sex_composition_pct_of_start", "Age structure", "s", ACCENT, ACCENT),
        ("age_sex_specific_rates_pct_of_start", "Age-specific rates", "^", INK, "white"),
    ]
    for y, name in enumerate(rows):
        if name is None:
            continue
        r = d.loc[name]
        vals = [r[c[0]] for c in comps] + [r["change_pct_of_start"]]
        ax.plot([min(vals), max(vals)], [y, y], color=LIGHT, zorder=1)
        for col, _, marker, colour, face in comps:
            ax.plot(r[col], y, marker, ms=3, mec=colour, mfc=face, mew=0.6, zorder=3)
        ax.plot(r["change_pct_of_start"], y, "|", ms=6, color=INK, mew=1.0, zorder=4)
    top = len(rows) - 1
    r = d.loc[rows[-1]]
    placements = [(-5.0, 1.3), (1.0, 2.3), (9.0, 1.3), (14.0, 2.3)]
    items = [(r[c[0]], c[1], c[3]) for c in comps] + [
        (r["change_pct_of_start"], "Observed change", INK)
    ]
    items = sorted(items, key=lambda item: item[0])
    for (val, text, colour), (tx, level) in zip(items, placements, strict=True):
        ax.annotate(
            text,
            xy=(val, top),
            xytext=(tx, top + level),
            ha="center",
            fontsize=SMALL,
            color=colour,
            arrowprops={"arrowstyle": "-", "color": LIGHT, "lw": 0.4},
        )
    ax.axvline(0, color=LIGHT, lw=0.5, zorder=0)
    dotrows(ax, [LABELS[n] if n else "" for n in rows])
    ax.set_ylim(-0.6, top + 3.1)
    ax.set_xlabel("Contribution to change in discharges, 2011 to 2019 (% of 2011)")
    save(fig, "figure_s1_historical_decomposition")


def figure_s3() -> None:
    var = pd.read_csv(TABLES / "extsens_all_variants.csv")
    var = var.loc[var["horizon"] == 2035]
    base = pd.read_csv(TABLES / "baseline_year_sensitivity.csv")
    base = base.loc[base["horizon"] == 2035]
    multi = pd.read_csv(TABLES / "multi_year_rate_sensitivity.csv")
    multi = multi.loc[multi["horizon"] == 2035].set_index("service_line")
    py = pd.read_csv(TABLES / "extsens_person_years.csv", index_col=0)
    ao = pd.read_csv(TABLES / "extsens_age_only.csv", index_col=0)
    tc = pd.read_csv(TABLES / "extsens_topcoding.csv", index_col=0)
    ex = pd.read_csv(TABLES / "posthoc_aggregate_excluding_s06.csv")

    def base_gap(year: int, key: str) -> float:
        if key == "all_prespecified":
            return float(
                base.loc[
                    (base["baseline_year"] == year) & (base["service_line"] == key),
                    "gap_relative_pct",
                ].iloc[0]
            )
        sub = base.loc[
            (base["baseline_year"] == year)
            & ~base["service_line"].isin(["all_prespecified", "intracranial_injury"])
        ]
        return 100 * (sub["model_1"].sum() / sub["model_0"].sum() - 1)

    def multi_gap(key: str) -> float:
        if key == "all_prespecified":
            return float(multi.loc[key, "gap_relative_pct"])
        sub = multi.drop(index=["all_prespecified", "intracranial_injury"])
        return 100 * (sub["model_1"].sum() / sub["model_0"].sum() - 1)

    keys = ["all_prespecified", "excluding_intracranial_injury"]
    rows = [
        ("Baseline rates 2022", [base_gap(2022, k) for k in keys]),
        ("Baseline rates 2023", [base_gap(2023, k) for k in keys]),
        ("Mean rates 2022–2024", [multi_gap(k) for k in keys]),
        ("Person-year denominators", [py.iloc[1][k] for k in keys]),
        ("Rates by age only (sexes combined)", [ao.iloc[1][k] for k in keys]),
        ("Age groups to 90+", [tc.iloc[1][k] for k in keys]),
    ]
    primary = [
        float(
            ex.loc[
                (ex["aggregate"] == k) & (ex["horizon"] == 2035) & (ex["scenario"] == SCENARIO),
                "gap_relative_pct",
            ].iloc[0]
        )
        for k in keys
    ]
    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE, 62 * MM), sharey=True)
    labels = ["All 27 population projection variants", *[r[0] for r in rows]][::-1]
    for j, (ax, key) in enumerate(zip(axes, keys, strict=True)):
        y_var = len(labels) - 1
        vals = var[key]
        ax.plot(
            [vals.min(), vals.max()],
            [y_var, y_var],
            color=LIGHT,
            lw=2.2,
            solid_capstyle="butt",
            zorder=1,
        )
        ax.plot(vals, [y_var] * len(vals), "|", ms=4, color=GREY, mew=0.5, zorder=2)
        for y, (_, v) in enumerate(rows[::-1]):
            ax.plot(v[j], y, "o", ms=3, mfc="white", mec=INK, mew=0.6, zorder=2)
        ax.axvline(primary[j], color=ACCENT, lw=0.6, zorder=0)
        ax.text(
            primary[j], len(labels) - 0.35, "Primary", color=ACCENT, ha="center", fontsize=SMALL
        )
        ax.set_xlim(2, 12)
        ax.set_xlabel("Difference between projections, 2035 (%)")
        panel(ax, "AB"[j])
    dotrows(axes[0], labels)
    axes[1].tick_params(axis="y", length=0)
    axes[1].spines["left"].set_visible(False)
    axes[0].set_ylim(-0.6, len(labels) + 0.2)
    save(fig, "figure_s3_sensitivity")


if __name__ == "__main__":
    style()
    for fn in (figure_1, figure_2, figure_3, figure_4, figure_5, figure_s1, figure_s2, figure_s3):
        fn()
