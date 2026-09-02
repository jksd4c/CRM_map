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

    reliability_dir = root / "model_reliability"
    _write_rows(
        reliability_dir / "nested_models.csv",
        [
            "analysis_id",
            "comparison",
            "restricted_model",
            "restricted_parameters",
            "restricted_log_likelihood",
            "full_model",
            "full_parameters",
            "full_log_likelihood",
        ],
        [
            {
                "analysis_id": cohort,
                "comparison": "reduced versus full",
                "restricted_model": "reduced",
                "restricted_parameters": 4,
                "restricted_log_likelihood": -105.0 - cohort_index,
                "full_model": "full",
                "full_parameters": 6,
                "full_log_likelihood": -100.0 - cohort_index,
            }
            for cohort_index, cohort in enumerate(COHORTS)
        ],
    )
    _write_rows(
        reliability_dir / "model_diagnostics.csv",
        [
            "analysis_id",
            "model",
            "parameter_count",
            "observation_count",
            "log_likelihood",
            "reference_negative_log_likelihood",
            "maximum_absolute_gradient",
            "curvature_rank",
            "curvature_dimension",
            "condition_number",
            "hard_boundary_parameters",
        ],
        [
            {
                "analysis_id": cohort,
                "model": "full",
                "parameter_count": 6,
                "observation_count": 1000 + 100 * cohort_index,
                "log_likelihood": -100.0 - cohort_index,
                "reference_negative_log_likelihood": 100.0 + cohort_index,
                "maximum_absolute_gradient": 0.001,
                "curvature_rank": 6,
                "curvature_dimension": 6,
                "condition_number": 250.0,
                "hard_boundary_parameters": 0,
            }
            for cohort_index, cohort in enumerate(COHORTS)
        ],
    )
    multistart_rows = []
    for cohort_index, cohort in enumerate(COHORTS):
        for start in range(10):
            multistart_rows.append(
                {
                    "analysis_id": cohort,
                    "start_id": start + 1,
                    "negative_log_likelihood": 100.0 + cohort_index + start * 0.0001,
                    "success": True,
                    "maximum_parameter_difference_from_reference": 0.001 + start * 0.00001,
                }
            )
    _write_rows(
        reliability_dir / "multistart_runs.csv",
        [
            "analysis_id",
            "start_id",
            "negative_log_likelihood",
            "success",
            "maximum_parameter_difference_from_reference",
        ],
        multistart_rows,
    )

    simulation_rows = []
    for scenario_index, scenario in enumerate(("balanced", "sparse")):
        for method_index, method in enumerate(("interval_integrated", "midpoint")):
            scale = 0.02 + 0.03 * method_index + 0.01 * scenario_index
            for metric, truth in (
                ("log_rate", 0.1),
                ("state_probability_5y", 0.3),
                ("order_probability_5y", 0.1),
                ("direction_log_contrast", 0.2),
            ):
                for replicate in range(3):
                    estimate = truth + scale * (replicate - 1)
                    if metric == "log_rate" and estimate <= 0.0:
                        estimate = truth / 2.0
                    simulation_rows.append(
                        {
                            "scenario": scenario,
                            "method": method,
                            "metric": metric,
                            "truth": truth,
                            "estimate": estimate,
                        }
                    )
    _write_rows(
        reliability_dir / "simulation_estimates.csv",
        ["scenario", "method", "metric", "truth", "estimate"],
        simulation_rows,
    )

    coverage_rows = []
    for scenario in ("balanced", "sparse"):
        for family in ("parameters", "derived_estimands"):
            for replicate in range(5):
                failure = replicate == 4 and (
                    (scenario == "balanced" and family == "parameters")
                    or (scenario == "sparse" and family == "derived_estimands")
                )
                coverage_rows.append(
                    {
                        "scenario": scenario,
                        "replicate": replicate + 1,
                        "family": family,
                        "estimand": f"{family}_{replicate + 1}",
                        "truth": 0.5,
                        "lower_95": 0.6 if failure else 0.4,
                        "upper_95": 0.8 if failure else 0.6,
                    }
                )
    _write_rows(
        reliability_dir / "coverage_intervals.csv",
        ["scenario", "replicate", "family", "estimand", "truth", "lower_95", "upper_95"],
        coverage_rows,
    )
    _write_rows(
        reliability_dir / "validation_checks.csv",
        ["check_group", "check_name", "value", "tolerance"],
        [
            {
                "check_group": "probability",
                "check_name": "probability_sum_error",
                "value": 1e-12,
                "tolerance": 1e-10,
            },
            {
                "check_group": "aggregation",
                "check_name": "history_to_state_error",
                "value": 0.0,
                "tolerance": 1e-10,
            },
            {
                "check_group": "implementation",
                "check_name": "negative_log_likelihood_difference",
                "value": 1e-7,
                "tolerance": 1e-6,
            },
        ],
    )
