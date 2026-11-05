"""Publication figures for the primary projection analysis."""

from __future__ import annotations

import math
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

NEUTRAL = "#5E646B"
ACCENT = "#2F6B73"


def _publication_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 8,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "axes.linewidth": 0.5,
            "xtick.major.width": 0.5,
            "ytick.major.width": 0.5,
        }
    )


def primary_projection_gap_figure(
    estimates: pd.DataFrame,
    labels: dict[str, str],
) -> Figure:
    """Plot Model 1 versus Model 0 gaps as directly labelled point estimates."""

    required = {"service_line", "gap_relative_pct"}
    missing = required.difference(estimates.columns)
    if missing:
        raise ValueError(f"Figure data are missing columns: {sorted(missing)}")
    if estimates.empty:
        raise ValueError("Figure data are empty")
    if estimates["service_line"].duplicated().any():
        raise ValueError("Figure data contain duplicate service lines")

    data = estimates[["service_line", "gap_relative_pct"]].copy()
    data["gap_relative_pct"] = pd.to_numeric(data["gap_relative_pct"], errors="raise")
    if data["gap_relative_pct"].isna().any():
        raise ValueError("Figure data contain missing projection gaps")
    mapped_labels = data["service_line"].map(labels)
    data["display_label"] = mapped_labels.where(mapped_labels.notna(), data["service_line"])
    data = data.sort_values("gap_relative_pct", ascending=True).reset_index(drop=True)

    _publication_style()
    height = max(2.7, 0.32 * len(data) + 0.7)
    figure, axis = plt.subplots(figsize=(6.3, height))
    positions = range(len(data))
    colours = [
        ACCENT if service_line == "all_prespecified" else NEUTRAL
        for service_line in data["service_line"]
    ]
    axis.scatter(
        data["gap_relative_pct"],
        positions,
        s=22,
        c=colours,
        edgecolors="white",
        linewidths=0.4,
        zorder=3,
    )
    axis.axvline(0, color="#A7AAAE", linewidth=0.6, zorder=1)
    axis.set_yticks(list(positions), labels=data["display_label"])
    axis.set_xlabel(
        "Relative difference between age/sex-structured and population-only projections (%)"
    )
    axis.set_ylabel("")
    axis.tick_params(axis="x", length=3, color="#6F7377")
    axis.tick_params(axis="y", length=0, pad=5)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.spines["bottom"].set_color("#6F7377")
    axis.margins(y=0.12)
    figure.tight_layout(pad=0.6)
    return figure


def historical_age_sex_figure(
    rates: pd.DataFrame,
    labels: dict[str, str],
) -> Figure:
    """Plot pooled recent age-specific utilisation rates by sex and service line."""

    required = {"service_line", "sex", "age_group", "rate_per_100000"}
    missing = required.difference(rates.columns)
    if missing:
        raise ValueError(f"Historical-rate figure data are missing: {sorted(missing)}")
    if rates.empty:
        raise ValueError("Historical-rate figure data are empty")
    service_lines = sorted(rates["service_line"].unique())
    if not service_lines:
        raise ValueError("Historical-rate figure has no service lines")

    _publication_style()
    columns = 2
    rows = math.ceil(len(service_lines) / columns)
    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(7.2, 1.9 * rows),
        sharex=True,
        squeeze=False,
    )
    styles = {
        "female": (ACCENT, "-", "Female"),
        "male": (NEUTRAL, "--", "Male"),
    }
    age_groups = list(dict.fromkeys(rates["age_group"].astype(str)))
    positions = {age: index for index, age in enumerate(age_groups)}
    for axis, service_line in zip(axes.flat, service_lines, strict=False):
        panel = rates.loc[rates["service_line"] == service_line]
        for sex in ("female", "male"):
            rows_for_sex = panel.loc[panel["sex"] == sex].copy()
            rows_for_sex["position"] = rows_for_sex["age_group"].map(positions)
            rows_for_sex = rows_for_sex.sort_values("position")
            colour, line_style, display = styles[sex]
            axis.plot(
                rows_for_sex["position"],
                rows_for_sex["rate_per_100000"],
                color=colour,
                linestyle=line_style,
                linewidth=1.0,
                label=display,
            )
        axis.text(
            0,
            1.03,
            textwrap.fill(labels.get(service_line, service_line), width=42),
            transform=axis.transAxes,
            ha="left",
            va="bottom",
            fontsize=7.5,
        )
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#E3E4E5", linewidth=0.4)
        axis.set_axisbelow(True)
    for axis in axes.flat[len(service_lines) :]:
        axis.set_visible(False)
    tick_positions = list(range(0, len(age_groups), 3))
    if len(age_groups) - 1 not in tick_positions:
        tick_positions.append(len(age_groups) - 1)
    for axis in axes[-1, :]:
        axis.set_xticks(tick_positions, [age_groups[index] for index in tick_positions])
        axis.tick_params(axis="x", labelrotation=45)
    figure.supylabel("Hospital discharges per 100,000 population", x=0.01, fontsize=8)
    figure.supxlabel("Age group (years)", y=0.01, fontsize=8)
    handles, legend_labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(
        handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.005),
        frameon=False,
        ncol=2,
    )
    figure.tight_layout(rect=(0.025, 0.035, 1, 0.965), h_pad=1.3, w_pad=1.0)
    return figure


def projection_trajectory_figure(estimates: pd.DataFrame) -> Figure:
    """Plot absolute aggregate cases under population-only and structured models."""

    required = {"service_line", "baseline_year", "horizon", "baseline_cases", "model_0", "model_1"}
    missing = required.difference(estimates.columns)
    if missing:
        raise ValueError(f"Projection figure data are missing: {sorted(missing)}")
    data = estimates.loc[estimates["service_line"] == "all_prespecified"].copy()
    if data.empty or data["horizon"].duplicated().any():
        raise ValueError("Projection figure requires one aggregate row per horizon")
    data = data.sort_values("horizon")
    baseline_year = int(data["baseline_year"].iloc[0])
    baseline_cases = float(data["baseline_cases"].iloc[0])
    years = [baseline_year, *data["horizon"].astype(int).tolist()]
    model_0 = [baseline_cases, *data["model_0"].astype(float).tolist()]
    model_1 = [baseline_cases, *data["model_1"].astype(float).tolist()]

    _publication_style()
    figure, axis = plt.subplots(figsize=(6.3, 3.4))
    axis.plot(years, model_0, color=NEUTRAL, linestyle="--", marker="o", linewidth=1.0)
    axis.plot(years, model_1, color=ACCENT, linestyle="-", marker="o", linewidth=1.2)
    axis.text(years[-1] + 0.25, model_1[-1], "Age/sex structured", color=ACCENT, va="center")
    axis.text(years[-1] + 0.25, model_0[-1], "Population only", color=NEUTRAL, va="center")
    axis.set_xlabel("Year")
    axis.set_ylabel("Projected hospital discharges")
    axis.set_xticks(years)
    axis.ticklabel_format(axis="y", style="plain", useOffset=False)
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#E3E4E5", linewidth=0.4)
    axis.margins(x=0.08, y=0.12)
    figure.tight_layout(pad=0.7)
    return figure


def backtest_performance_figure(summary: pd.DataFrame) -> Figure:
    """Plot aggregate WAPE for both models by horizon and analysis set."""

    required = {
        "analysis_set",
        "service_line",
        "backtest_horizon_years",
        "model_0_wape",
        "model_1_wape",
    }
    missing = required.difference(summary.columns)
    if missing:
        raise ValueError(f"Backtest figure data are missing: {sorted(missing)}")
    data = summary.loc[summary["service_line"] == "all_prespecified"].copy()
    analysis_sets = [
        value
        for value in ("all_years", "exclude_covid_2020_2022")
        if value in set(data["analysis_set"])
    ]
    if len(analysis_sets) != 2:
        raise ValueError("Backtest figure requires all-years and COVID-excluded summaries")

    _publication_style()
    figure, axes = plt.subplots(1, 2, figsize=(6.3, 2.8), sharex=True, sharey=True)
    panel_labels = {
        "all_years": "A  All target years",
        "exclude_covid_2020_2022": "B  Excluding 2020–2022 targets",
    }
    for axis, analysis_set in zip(axes, analysis_sets, strict=True):
        panel = data.loc[data["analysis_set"] == analysis_set].sort_values("backtest_horizon_years")
        positions = range(len(panel))
        for position, (_, row) in zip(positions, panel.iterrows(), strict=True):
            axis.plot(
                [row["model_0_wape"], row["model_1_wape"]],
                [position, position],
                color="#B8BBBE",
                linewidth=0.8,
                zorder=1,
            )
        axis.scatter(
            panel["model_0_wape"],
            list(positions),
            color=NEUTRAL,
            marker="o",
            s=24,
            label="Population only",
            zorder=2,
        )
        axis.scatter(
            panel["model_1_wape"],
            list(positions),
            color=ACCENT,
            marker="s",
            s=22,
            label="Age/sex structured",
            zorder=3,
        )
        axis.text(
            0,
            1.04,
            panel_labels[analysis_set],
            transform=axis.transAxes,
            ha="left",
            va="bottom",
        )
        axis.set_yticks(
            list(positions),
            [f"{year} year" for year in panel["backtest_horizon_years"]],
        )
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.grid(axis="x", color="#E3E4E5", linewidth=0.4)
        axis.tick_params(axis="y", length=0)
    figure.supxlabel("Weighted absolute percentage error (%)", y=0.02, fontsize=8)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        frameon=False,
        ncol=2,
    )
    figure.tight_layout(rect=(0, 0.06, 1, 0.92), w_pad=1.5)
    return figure


def save_publication_figure(figure: Figure, output_stem: Path) -> list[Path]:
    """Save a figure as editable vector files and a high-resolution preview."""

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    outputs = [output_stem.with_suffix(suffix) for suffix in (".pdf", ".svg", ".png")]
    for path in outputs:
        options = {"bbox_inches": "tight", "facecolor": "white"}
        if path.suffix == ".png":
            options["dpi"] = 600
        figure.savefig(path, **options)
    return outputs
