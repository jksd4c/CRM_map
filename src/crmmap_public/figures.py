from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from .io import read_csv_rows


COHORTS = ("HRS", "CHARLS", "SHARE")
STATE_ORDER = ("SC", "SR", "SM")
STATE_LABELS = {"SC": "C only", "SR": "R only", "SM": "M only"}
STATE_COLORS = {"SC": "#DD7C4F", "SR": "#629C35", "SM": "#6C61AF"}


def _remove_svg_metadata(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    cleaned, replacements = re.subn(
        r"\n <metadata>\n.*?\n </metadata>\n",
        "\n",
        source,
        count=1,
        flags=re.DOTALL,
    )
    if replacements:
        cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines()) + "\n"
        path.write_text(cleaned, encoding="utf-8", newline="\n")


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "font.size": 7.5,
            "axes.labelsize": 8.0,
            "axes.titlesize": 8.5,
            "xtick.labelsize": 7.0,
            "ytick.labelsize": 7.0,
            "axes.edgecolor": "#4C5357",
            "axes.linewidth": 0.7,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "svg.hashsalt": "crmmap-public-v1",
        }
    )


def _save_figure(fig: plt.Figure, output_stem: Path) -> list[Path]:
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    outputs = [
        output_stem.with_suffix(".pdf"),
        output_stem.with_suffix(".svg"),
        output_stem.with_suffix(".png"),
    ]
    fig.savefig(
        outputs[0],
        bbox_inches="tight",
        metadata={"Creator": "", "Producer": "", "CreationDate": None},
    )
    fig.savefig(outputs[1], bbox_inches="tight", metadata={"Creator": "", "Date": None})
    _remove_svg_metadata(outputs[1])
    fig.savefig(
        outputs[2],
        bbox_inches="tight",
        dpi=600,
        facecolor="white",
        metadata={"Software": ""},
    )
    plt.close(fig)
    return outputs


def build_figure2(source: Path, output_dir: Path) -> list[Path]:
    rows = read_csv_rows(source)
    _configure_style()

    width_in = 170.0 / 25.4
    fig, axes = plt.subplots(1, 3, figsize=(width_in, width_in * 0.31), sharex=True, sharey=True)

    for panel_index, (axis, cohort) in enumerate(zip(axes, COHORTS, strict=True)):
        axis.set_xlim(-0.08, 5.08)
        axis.set_ylim(0.0, 21.0)
        axis.set_xticks(np.arange(0, 6, 1))
        axis.set_yticks(np.arange(0, 21, 5))
        axis.grid(axis="y", color="#E7EAEB", linewidth=0.5)
        axis.set_axisbelow(True)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_title(cohort, fontweight="bold", pad=4)
        axis.text(
            -0.12,
            1.04,
            chr(ord("A") + panel_index),
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=8.8,
            fontweight="bold",
        )

        for state in STATE_ORDER:
            selected = sorted(
                (
                    row
                    for row in rows
                    if row["cohort"] == cohort and row["state"] == state
                ),
                key=lambda row: float(row["u_years"]),
            )
            x = np.asarray([float(row["u_years"]) for row in selected])
            y = np.asarray([100.0 * float(row["probability"]) for row in selected])
            lower = np.asarray([100.0 * float(row["lower_95"]) for row in selected])
            upper = np.asarray([100.0 * float(row["upper_95"]) for row in selected])
            color = STATE_COLORS[state]

            axis.fill_between(x, lower, upper, color=color, alpha=0.08, linewidth=0)
            axis.errorbar(
                x,
                y,
                yerr=np.vstack((y - lower, upper - y)),
                fmt="none",
                ecolor=color,
                elinewidth=0.65,
                capsize=1.6,
                alpha=0.65,
            )
            axis.plot(x, y, color=color, linewidth=1.35, label=STATE_LABELS[state])

        axis.set_xlabel("State duration (years)", fontweight="bold")

    axes[0].set_ylabel("3-year progression probability (%)", fontweight="bold")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.55, 1.08),
        ncol=3,
        frameon=False,
        handlelength=2.2,
        handletextpad=0.35,
    )
    fig.suptitle(
        "Second-disease progression by first-disease state duration",
        x=0.5,
        y=1.14,
        fontsize=9.2,
        fontweight="bold",
    )
    fig.subplots_adjust(left=0.09, right=0.995, bottom=0.22, top=0.80, wspace=0.16)
    return _save_figure(fig, output_dir / "Figure2_state_duration_progression")


def build_figure3(source: Path, output_dir: Path) -> list[Path]:
    rows = read_csv_rows(source)
    _configure_style()

    transition_order: list[tuple[str, str]] = []
    for row in rows:
        key = (row["section"], row["state_transition"])
        if key not in transition_order:
            transition_order.append(key)

    row_lookup = {
        (row["section"], row["state_transition"], row["cohort"]): row for row in rows
    }

    display_rows: list[tuple[str, str, str, dict[str, str]]] = []
    previous_section = None
    for section, transition in transition_order:
        if section != previous_section:
            display_rows.append(("section", section, "", {}))
            previous_section = section
        for cohort in COHORTS:
            display_rows.append(
                ("estimate", transition, cohort, row_lookup[(section, transition, cohort)])
            )

    width_in = 170.0 / 25.4
    height_in = max(6.6, 0.22 * len(display_rows))
    fig = plt.figure(figsize=(width_in, height_in))
    grid = fig.add_gridspec(
        1,
        5,
        width_ratios=(1.65, 0.55, 1.35, 1.85, 1.15),
        wspace=0.0,
    )
    axes = [fig.add_subplot(grid[0, index]) for index in range(5)]
    label_axis, cohort_axis, rate_axis, forest_axis, probability_axis = axes

    n_rows = len(display_rows)
    for axis in axes:
        axis.set_ylim(n_rows - 0.5, -0.5)
        axis.set_yticks([])
        axis.tick_params(left=False)

    label_axis.set_xlim(0, 1)
    cohort_axis.set_xlim(0, 1)
    rate_axis.set_xlim(0, 1)
    probability_axis.set_xlim(0, 1)
    forest_axis.set_xlim(0, 45)
    forest_axis.set_xticks(np.arange(0, 46, 10))
    forest_axis.grid(axis="x", color="#D5D8DA", linewidth=0.55)
    forest_axis.set_axisbelow(True)
    forest_axis.set_xlabel("Five-year probability of entering the next CRM disease state (%)")

    for axis in (label_axis, cohort_axis, rate_axis, probability_axis):
        axis.set_axis_off()
    forest_axis.spines[["top", "right", "left"]].set_visible(False)

    marker_by_cohort = {"HRS": "o", "CHARLS": "s", "SHARE": "D"}
    for y, (row_type, label, cohort, row) in enumerate(display_rows):
        if row_type == "section":
            for axis in axes:
                axis.axhspan(y - 0.48, y + 0.48, color="#E1E1E1", zorder=-3)
            label_axis.text(0.02, y, label, va="center", ha="left", fontweight="bold")
            continue

        if y % 2 == 0:
            for axis in axes:
                axis.axhspan(y - 0.48, y + 0.48, color="#F5F5F5", zorder=-4)

        if cohort == COHORTS[0]:
            label_axis.text(0.03, y + 1.0, label, va="center", ha="left", fontweight="bold")
        cohort_axis.text(0.5, y, cohort, va="center", ha="center")

        annual_rate = float(row["annual_rate_per_100py"])
        rate_lower = float(row["rate_lower_95"])
        rate_upper = float(row["rate_upper_95"])
        rate_axis.text(
            0.5,
            y,
            f"{annual_rate:.2f} ({rate_lower:.2f}-{rate_upper:.2f})",
            va="center",
            ha="center",
        )

        estimate = float(row["probability_5y"])
        lower = float(row["probability_lower_95"])
        upper = float(row["probability_upper_95"])
        forest_axis.errorbar(
            estimate,
            y,
            xerr=[[estimate - lower], [upper - estimate]],
            fmt=marker_by_cohort[cohort],
            color="black",
            ecolor="#737373",
            elinewidth=0.75,
            capsize=0,
            markersize=3.2,
            markerfacecolor="black",
        )
        probability_axis.text(
            0.5,
            y,
            f"{estimate:.1f} ({lower:.1f}-{upper:.1f})",
            va="center",
            ha="center",
        )

    label_axis.set_title("Complete state transition", loc="left", fontweight="bold", pad=7)
    cohort_axis.set_title("Cohort", fontweight="bold", pad=7)
    rate_axis.set_title(
        "Annual transition rate per\n100 person-years (95% CI)",
        fontweight="bold",
        pad=4,
    )
    forest_axis.set_title("Five-year probability\nforest plot", fontweight="bold", pad=4)
    probability_axis.set_title("Five-year probability, %\n(95% CI)", fontweight="bold", pad=4)
    fig.subplots_adjust(left=0.02, right=0.995, top=0.96, bottom=0.08)
    return _save_figure(fig, output_dir / "Figure3_directed_disease_accumulation")
