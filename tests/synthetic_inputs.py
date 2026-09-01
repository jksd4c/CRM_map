from __future__ import annotations

import csv
from pathlib import Path

from crmmap_public.tables import EXPECTED_MAIN_TABLE_FILES, EXPECTED_SUPPLEMENTARY_TABLE_FILES


COHORTS = ("HRS", "CHARLS", "SHARE")


def _write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def create_synthetic_inputs(root: Path) -> None:
    figure2_rows: list[dict[str, object]] = []
    for cohort_index, cohort in enumerate(COHORTS):
        for state_index, state in enumerate(("SC", "SR", "SM")):
            for duration in range(6):
                estimate = 0.05 + 0.005 * cohort_index + 0.01 * state_index + 0.002 * duration
                figure2_rows.append(
                    {
                        "cohort": cohort,
                        "state": state,
                        "u_years": duration,
                        "probability": estimate,
                        "lower_95": estimate - 0.01,
                        "upper_95": estimate + 0.01,
                    }
                )
    _write_rows(
        root / "figure2_state_duration_probability.csv",
        ["cohort", "state", "u_years", "probability", "lower_95", "upper_95"],
        figure2_rows,
    )

    transitions = (
        ("Entry into dual-disease states", "single_to_dual", "C→C+R", "R"),
        ("Entry into dual-disease states", "single_to_dual", "R→C+R", "C"),
        ("Entry into dual-disease states", "single_to_dual", "C→C+M", "M"),
        ("Entry into dual-disease states", "single_to_dual", "M→C+M", "C"),
        ("Entry into dual-disease states", "single_to_dual", "R→R+M", "M"),
        ("Entry into dual-disease states", "single_to_dual", "M→R+M", "R"),
        ("Completion of C+R+M", "dual_to_triple", "C+R→C+R+M", "M"),
        ("Completion of C+R+M", "dual_to_triple", "C+M→C+R+M", "R"),
        ("Completion of C+R+M", "dual_to_triple", "R+M→C+R+M", "C"),
    )
    figure3_rows: list[dict[str, object]] = []
    for transition_index, (section, stage, transition, entering_disease) in enumerate(
        transitions
    ):
        for cohort_index, cohort in enumerate(COHORTS):
            rate = 0.5 + 0.1 * transition_index + 0.05 * cohort_index
            probability = 5.0 + transition_index + cohort_index
            figure3_rows.append(
                {
                    "section": section,
                    "transition_stage": stage,
                    "state_transition": transition,
                    "entering_disease": entering_disease,
                    "cohort": cohort,
                    "annual_rate_per_100py": rate,
                    "rate_lower_95": rate - 0.1,
                    "rate_upper_95": rate + 0.1,
                    "probability_5y": probability,
                    "probability_lower_95": probability - 1.0,
                    "probability_upper_95": probability + 1.0,
                }
            )
    _write_rows(
        root / "figure3_directed_transitions.csv",
        [
            "section",
            "transition_stage",
            "state_transition",
            "entering_disease",
            "cohort",
            "annual_rate_per_100py",
            "rate_lower_95",
            "rate_upper_95",
            "probability_5y",
            "probability_lower_95",
            "probability_upper_95",
        ],
        figure3_rows,
    )

    for directory, filenames in (
        ("main_tables", EXPECTED_MAIN_TABLE_FILES),
        ("supplementary_tables", EXPECTED_SUPPLEMENTARY_TABLE_FILES),
    ):
        for filename in filenames:
            _write_rows(
                root / directory / filename,
                ["item", "value"],
                [{"item": "synthetic", "value": 1}],
            )
