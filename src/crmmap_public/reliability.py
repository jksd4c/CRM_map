from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping

from .io import write_csv_rows, write_json


REQUIRED_INPUT_COLUMNS = {
    "nested_models.csv": (
        "analysis_id",
        "comparison",
        "restricted_model",
        "restricted_parameters",
        "restricted_log_likelihood",
        "full_model",
        "full_parameters",
        "full_log_likelihood",
    ),
    "model_diagnostics.csv": (
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
    ),
    "multistart_runs.csv": (
        "analysis_id",
        "start_id",
        "negative_log_likelihood",
        "success",
        "maximum_parameter_difference_from_reference",
    ),
    "simulation_estimates.csv": (
        "scenario",
        "method",
        "metric",
        "truth",
        "estimate",
    ),
    "coverage_intervals.csv": (
        "scenario",
        "replicate",
        "family",
        "estimand",
        "truth",
        "lower_95",
        "upper_95",
    ),
    "validation_checks.csv": (
        "check_group",
        "check_name",
        "value",
        "tolerance",
    ),
}

SIMULATION_METRICS = {
    "direction_log_contrast",
    "log_rate",
    "order_probability_5y",
    "state_probability_5y",
}


def _read_rows(path: Path, required: Iterable[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        missing = [column for column in required if column not in columns]
        if missing:
            raise ValueError(f"Missing columns in {path.name}: {missing}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"No rows in {path.name}")
    return rows


def _number(row: Mapping[str, str], column: str, source: str) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid numeric value in {source}:{column}") from error
    if not math.isfinite(value):
        raise ValueError(f"Non-finite numeric value in {source}:{column}")
    return value


def _integer(row: Mapping[str, str], column: str, source: str) -> int:
    value = _number(row, column, source)
    integer = int(value)
    if value != integer:
        raise ValueError(f"Expected integer in {source}:{column}")
    return integer


def _boolean(row: Mapping[str, str], column: str, source: str) -> bool:
    value = row[column].strip().lower()
    if value in {"1", "true", "yes"}:
        return True
    if value in {"0", "false", "no"}:
        return False
    raise ValueError(f"Invalid boolean value in {source}:{column}")


def _regularized_gamma_q(shape: float, value: float) -> float:
    if shape <= 0.0 or value < 0.0:
        raise ValueError("Gamma arguments must be positive")
    if value == 0.0:
        return 1.0

    tolerance = 3e-14
    minimum = 1e-300
    maximum_iterations = 1000
    log_factor = -value + shape * math.log(value) - math.lgamma(shape)

    if value < shape + 1.0:
        term = 1.0 / shape
        total = term
        denominator = shape
        for _ in range(maximum_iterations):
            denominator += 1.0
            term *= value / denominator
            total += term
            if abs(term) <= abs(total) * tolerance:
                break
        else:
            raise ArithmeticError("Gamma series did not converge")
        result = 1.0 - total * math.exp(log_factor)
    else:
        denominator = value + 1.0 - shape
        reciprocal = 1.0 / max(abs(denominator), minimum)
        if denominator < 0.0:
            reciprocal = -reciprocal
        factor = 1.0 / minimum
        product = reciprocal
        for iteration in range(1, maximum_iterations + 1):
            coefficient = -iteration * (iteration - shape)
            denominator += 2.0
            reciprocal = coefficient * reciprocal + denominator
            if abs(reciprocal) < minimum:
                reciprocal = minimum
            factor = denominator + coefficient / factor
            if abs(factor) < minimum:
                factor = minimum
            reciprocal = 1.0 / reciprocal
            delta = reciprocal * factor
            product *= delta
            if abs(delta - 1.0) <= tolerance:
                break
        else:
            raise ArithmeticError("Gamma continued fraction did not converge")
        result = math.exp(log_factor) * product
    return min(max(result, 0.0), 1.0)


def chi_square_survival(statistic: float, degrees_of_freedom: int) -> float:
    if statistic < 0.0:
        raise ValueError("Chi-square statistic cannot be negative")
    if degrees_of_freedom <= 0:
        raise ValueError("Degrees of freedom must be positive")
    return _regularized_gamma_q(degrees_of_freedom / 2.0, statistic / 2.0)


def wilson_interval(covered: int, total: int, z_value: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0 or covered < 0 or covered > total:
        raise ValueError("Invalid coverage counts")
    proportion = covered / total
    denominator = 1.0 + z_value**2 / total
    center = (proportion + z_value**2 / (2.0 * total)) / denominator
    half_width = (
        z_value
        * math.sqrt(proportion * (1.0 - proportion) / total + z_value**2 / (4.0 * total**2))
        / denominator
    )
    return center - half_width, center + half_width


def _nested_comparisons(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        restricted_parameters = _integer(row, "restricted_parameters", "nested_models.csv")
        full_parameters = _integer(row, "full_parameters", "nested_models.csv")
        restricted_log_likelihood = _number(row, "restricted_log_likelihood", "nested_models.csv")
        full_log_likelihood = _number(row, "full_log_likelihood", "nested_models.csv")
        degrees_of_freedom = full_parameters - restricted_parameters
        statistic = 2.0 * (full_log_likelihood - restricted_log_likelihood)
        if degrees_of_freedom <= 0 or statistic < -1e-10:
            raise ValueError("Nested-model comparison is not ordered")
        statistic = max(statistic, 0.0)
        output.append(
            {
                "analysis_id": row["analysis_id"],
                "comparison": row["comparison"],
                "restricted_model": row["restricted_model"],
                "restricted_parameters": restricted_parameters,
                "restricted_log_likelihood": restricted_log_likelihood,
                "full_model": row["full_model"],
                "full_parameters": full_parameters,
                "full_log_likelihood": full_log_likelihood,
                "likelihood_ratio_statistic": statistic,
                "degrees_of_freedom": degrees_of_freedom,
                "p_value": chi_square_survival(statistic, degrees_of_freedom),
            }
        )
    return output


def _diagnostics(rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    output: list[dict[str, object]] = []
    indexed: dict[str, dict[str, object]] = {}
    for row in rows:
        analysis_id = row["analysis_id"]
        if analysis_id in indexed:
            raise ValueError(f"Duplicate model diagnostic: {analysis_id}")
        parameter_count = _integer(row, "parameter_count", "model_diagnostics.csv")
        observation_count = _integer(row, "observation_count", "model_diagnostics.csv")
        log_likelihood = _number(row, "log_likelihood", "model_diagnostics.csv")
        if parameter_count <= 0 or observation_count <= 0:
            raise ValueError("Parameter and observation counts must be positive")
        record = {
            "analysis_id": analysis_id,
            "model": row["model"],
            "parameter_count": parameter_count,
            "observation_count": observation_count,
            "log_likelihood": log_likelihood,
            "aic": 2.0 * parameter_count - 2.0 * log_likelihood,
            "bic": math.log(observation_count) * parameter_count - 2.0 * log_likelihood,
            "reference_negative_log_likelihood": _number(
                row, "reference_negative_log_likelihood", "model_diagnostics.csv"
            ),
            "maximum_absolute_gradient": _number(
                row, "maximum_absolute_gradient", "model_diagnostics.csv"
            ),
            "curvature_rank": _integer(row, "curvature_rank", "model_diagnostics.csv"),
            "curvature_dimension": _integer(
                row, "curvature_dimension", "model_diagnostics.csv"
            ),
            "condition_number": _number(row, "condition_number", "model_diagnostics.csv"),
            "hard_boundary_parameters": _integer(
                row, "hard_boundary_parameters", "model_diagnostics.csv"
            ),
        }
        output.append(record)
        indexed[analysis_id] = record
    return output, indexed


def _multistart_summary(
    rows: list[dict[str, str]],
    diagnostics: Mapping[str, Mapping[str, object]],
    configuration: Mapping[str, object],
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["analysis_id"]].append(row)
    if set(grouped) != set(diagnostics):
        raise ValueError("Multistart and diagnostic analysis identifiers do not match")

    tolerance = float(configuration["objective_equivalence_absolute_nll"])
    output: list[dict[str, object]] = []
    for analysis_id, group in sorted(grouped.items()):
        parsed = []
        for row in group:
            objective = _number(row, "negative_log_likelihood", "multistart_runs.csv")
            parsed.append(
                {
                    "objective": objective,
                    "success": _boolean(row, "success", "multistart_runs.csv"),
                    "parameter_difference": _number(
                        row,
                        "maximum_parameter_difference_from_reference",
                        "multistart_runs.csv",
                    ),
                }
            )
        best = min(item["objective"] for item in parsed)
        equivalent = [item for item in parsed if item["objective"] - best <= tolerance]
        diagnostic = diagnostics[analysis_id]
        nll_difference = abs(best - float(diagnostic["reference_negative_log_likelihood"]))
        best_parameter_difference = min(
            item["parameter_difference"]
            for item in parsed
            if abs(item["objective"] - best) <= 1e-12
        )
        passed = (
            len(parsed) >= int(configuration["finite_starts_required"])
            and sum(item["success"] for item in parsed)
            >= int(configuration["successful_starts_minimum"])
            and len(equivalent) >= int(configuration["equivalent_starts_minimum"])
            and nll_difference <= float(configuration["maximum_reference_nll_difference"])
            and best_parameter_difference
            <= float(configuration["maximum_reference_parameter_difference"])
            and float(diagnostic["maximum_absolute_gradient"])
            <= float(configuration["maximum_absolute_gradient"])
            and int(diagnostic["curvature_rank"]) == int(diagnostic["curvature_dimension"])
            and float(diagnostic["condition_number"])
            <= float(configuration["maximum_condition_number"])
            and int(diagnostic["hard_boundary_parameters"])
            <= int(configuration["maximum_hard_boundary_parameters"])
        )
        output.append(
            {
                "analysis_id": analysis_id,
                "finite_starts": len(parsed),
                "successful_starts": sum(item["success"] for item in parsed),
                "equivalent_optima": len(equivalent),
                "absolute_nll_difference_from_reference": nll_difference,
                "maximum_parameter_difference_from_reference": best_parameter_difference,
                "maximum_absolute_gradient": diagnostic["maximum_absolute_gradient"],
                "curvature_rank": diagnostic["curvature_rank"],
                "curvature_dimension": diagnostic["curvature_dimension"],
                "condition_number": diagnostic["condition_number"],
                "hard_boundary_parameters": diagnostic["hard_boundary_parameters"],
                "status": "PASS" if passed else "FLAGGED",
            }
        )
    return output


def _simulation_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        metric = row["metric"]
        if metric not in SIMULATION_METRICS:
            raise ValueError(f"Unsupported simulation metric: {metric}")
        truth = _number(row, "truth", "simulation_estimates.csv")
        estimate = _number(row, "estimate", "simulation_estimates.csv")
        if metric == "log_rate":
            if truth <= 0.0 or estimate <= 0.0:
                raise ValueError("Log-rate values must be positive")
            error = abs(math.log(estimate) - math.log(truth))
        else:
            error = abs(estimate - truth)
        grouped[(row["scenario"], row["method"], metric)].append(error)

    output: list[dict[str, object]] = []
    for (scenario, method, metric), errors in sorted(grouped.items()):
        ordered = sorted(errors)
        middle = len(ordered) // 2
        median = (
            ordered[middle]
            if len(ordered) % 2
            else (ordered[middle - 1] + ordered[middle]) / 2.0
        )
        output.append(
            {
                "scenario": scenario,
                "method": method,
                "metric": metric,
                "estimates": len(errors),
                "mean_absolute_error": sum(errors) / len(errors),
                "median_absolute_error": median,
                "maximum_absolute_error": max(errors),
            }
        )
    return output


def _coverage_summary(
    rows: list[dict[str, str]], configuration: Mapping[str, object]
) -> tuple[list[dict[str, object]], bool]:
    groups: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for row in rows:
        truth = _number(row, "truth", "coverage_intervals.csv")
        lower = _number(row, "lower_95", "coverage_intervals.csv")
        upper = _number(row, "upper_95", "coverage_intervals.csv")
        if lower > upper:
            raise ValueError("Coverage interval endpoints are reversed")
        covered = lower <= truth <= upper
        scenario = row["scenario"]
        family = row["family"]
        for key in (("ALL", "ALL"), (scenario, "ALL"), ("ALL", family), (scenario, family)):
            groups[key].append(covered)

    output: list[dict[str, object]] = []
    for (scenario, family), values in sorted(groups.items()):
        covered = sum(values)
        lower, upper = wilson_interval(covered, len(values))
        output.append(
            {
                "scenario": scenario,
                "family": family,
                "covered": covered,
                "total": len(values),
                "coverage": covered / len(values),
                "wilson_95_lower": lower,
                "wilson_95_upper": upper,
            }
        )

    overall = next(row for row in output if row["scenario"] == row["family"] == "ALL")
    family_rows = [row for row in output if row["scenario"] == "ALL" and row["family"] != "ALL"]
    interval = [float(value) for value in configuration["overall_acceptance_interval"]]
    passed = (
        interval[0] <= float(overall["coverage"]) <= interval[1]
        and all(
            float(row["coverage"]) >= float(configuration["minimum_family_coverage"])
            for row in family_rows
        )
    )
    return output, passed


def _validation_checks(rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], bool]:
    output: list[dict[str, object]] = []
    for row in rows:
        value = _number(row, "value", "validation_checks.csv")
        tolerance = _number(row, "tolerance", "validation_checks.csv")
        if tolerance < 0.0:
            raise ValueError("Validation tolerance cannot be negative")
        passed = abs(value) <= tolerance
        output.append(
            {
                "check_group": row["check_group"],
                "check_name": row["check_name"],
                "value": value,
                "tolerance": tolerance,
                "status": "PASS" if passed else "FAIL",
            }
        )
    return output, all(row["status"] == "PASS" for row in output)


def build_model_reliability(
    input_dir: Path, output_dir: Path, configuration_path: Path
) -> list[Path]:
    configuration = json.loads(configuration_path.read_text(encoding="utf-8"))
    rows = {
        filename: _read_rows(input_dir / filename, columns)
        for filename, columns in REQUIRED_INPUT_COLUMNS.items()
    }

    comparisons = _nested_comparisons(rows["nested_models.csv"])
    diagnostics, indexed_diagnostics = _diagnostics(rows["model_diagnostics.csv"])
    multistart = _multistart_summary(
        rows["multistart_runs.csv"],
        indexed_diagnostics,
        configuration["multistart"],
    )
    simulation = _simulation_summary(rows["simulation_estimates.csv"])
    coverage, coverage_passed = _coverage_summary(
        rows["coverage_intervals.csv"], configuration["coverage"]
    )
    checks, checks_passed = _validation_checks(rows["validation_checks.csv"])

    output_dir.mkdir(parents=True, exist_ok=True)
    specifications = (
        (
            "nested_likelihood_comparisons.csv",
            comparisons,
            list(comparisons[0]),
        ),
        ("model_diagnostics.csv", diagnostics, list(diagnostics[0])),
        ("multistart_stability.csv", multistart, list(multistart[0])),
        ("simulation_recovery.csv", simulation, list(simulation[0])),
        ("coverage_summary.csv", coverage, list(coverage[0])),
        ("validation_checks.csv", checks, list(checks[0])),
    )
    outputs: list[Path] = []
    for filename, records, fieldnames in specifications:
        path = output_dir / filename
        write_csv_rows(path, records, fieldnames)
        outputs.append(path)

    summary_path = output_dir / "model_reliability_summary.json"
    status = (
        "PASS"
        if all(row["status"] == "PASS" for row in multistart)
        and coverage_passed
        and checks_passed
        else "FLAGGED"
    )
    write_json(
        summary_path,
        {
            "status": status,
            "coverage_status": "PASS" if coverage_passed else "FLAGGED",
            "multistart_status": (
                "PASS" if all(row["status"] == "PASS" for row in multistart) else "FLAGGED"
            ),
            "validation_check_status": "PASS" if checks_passed else "FAIL",
            "notes": [
                "Coverage describes interval calibration in the supplied synthetic records.",
                "The outputs do not estimate type-I error, type-II error, or statistical power.",
            ],
        },
    )
    outputs.append(summary_path)
    return outputs
