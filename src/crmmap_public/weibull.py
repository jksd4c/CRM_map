from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np

from .io import write_csv_rows


PARAMETER_COLUMNS = (
    "analysis_id",
    "origin_state",
    "destination_state",
    "outcome",
    "rate_per_year",
    "shape",
    "support_max_years",
)

ESTIMAND_COLUMNS = (
    "analysis_id",
    "origin_state",
    "duration_years",
    "horizon_years",
)

OUTCOME_TYPES = {"progression", "death"}


@dataclass(frozen=True)
class WeibullExit:
    analysis_id: str
    origin_state: str
    destination_state: str
    outcome: str
    rate_per_year: float
    shape: float
    support_max_years: float

    def __post_init__(self) -> None:
        if not self.analysis_id or not self.origin_state or not self.destination_state:
            raise ValueError("Weibull exit identifiers cannot be empty")
        if self.outcome not in OUTCOME_TYPES:
            raise ValueError(f"Unsupported outcome type: {self.outcome}")
        if not math.isfinite(self.rate_per_year) or self.rate_per_year <= 0.0:
            raise ValueError("Weibull rates must be finite and positive")
        if not math.isfinite(self.shape) or self.shape <= 0.0:
            raise ValueError("Weibull shapes must be finite and positive")
        if not math.isfinite(self.support_max_years) or self.support_max_years <= 0.0:
            raise ValueError("Support limits must be finite and positive")


def weibull_cumulative_hazard(
    duration_years: float | np.ndarray,
    rate_per_year: float,
    shape: float,
) -> float | np.ndarray:
    duration = np.asarray(duration_years, dtype=float)
    if np.any(~np.isfinite(duration)) or np.any(duration < 0.0):
        raise ValueError("Durations must be finite and nonnegative")
    if not math.isfinite(rate_per_year) or rate_per_year <= 0.0:
        raise ValueError("The Weibull rate must be finite and positive")
    if not math.isfinite(shape) or shape <= 0.0:
        raise ValueError("The Weibull shape must be finite and positive")
    result = np.power(rate_per_year * duration, shape)
    return float(result) if result.ndim == 0 else result


def weibull_hazard(
    duration_years: float | np.ndarray,
    rate_per_year: float,
    shape: float,
) -> float | np.ndarray:
    duration = np.asarray(duration_years, dtype=float)
    if np.any(~np.isfinite(duration)) or np.any(duration < 0.0):
        raise ValueError("Durations must be finite and nonnegative")
    if not math.isfinite(rate_per_year) or rate_per_year <= 0.0:
        raise ValueError("The Weibull rate must be finite and positive")
    if not math.isfinite(shape) or shape <= 0.0:
        raise ValueError("The Weibull shape must be finite and positive")
    with np.errstate(divide="ignore", invalid="ignore"):
        result = shape * rate_per_year**shape * np.power(duration, shape - 1.0)
    if shape > 1.0:
        result = np.where(duration == 0.0, 0.0, result)
    elif shape == 1.0:
        result = np.where(duration == 0.0, rate_per_year, result)
    return float(result) if result.ndim == 0 else result


def weibull_survival(
    duration_years: float | np.ndarray,
    rate_per_year: float,
    shape: float,
) -> float | np.ndarray:
    cumulative = weibull_cumulative_hazard(duration_years, rate_per_year, shape)
    result = np.exp(-np.asarray(cumulative, dtype=float))
    return float(result) if result.ndim == 0 else result


def conditional_outcome_probabilities(
    exits: Iterable[WeibullExit],
    *,
    duration_years: float,
    horizon_years: float,
    quadrature_order: int = 96,
) -> dict[str, float]:
    exit_list = tuple(exits)
    if not exit_list:
        raise ValueError("At least one exit transition is required")
    if not math.isfinite(duration_years) or duration_years < 0.0:
        raise ValueError("Duration must be finite and nonnegative")
    if not math.isfinite(horizon_years) or horizon_years <= 0.0:
        raise ValueError("Prediction horizon must be finite and positive")
    if quadrature_order < 8:
        raise ValueError("Quadrature order must be at least 8")

    analysis_keys = {(item.analysis_id, item.origin_state) for item in exit_list}
    if len(analysis_keys) != 1:
        raise ValueError("All exits must belong to one analysis and origin state")

    nodes, weights = np.polynomial.legendre.leggauss(quadrature_order)
    evaluation_time = duration_years + (nodes + 1.0) * horizon_years / 2.0
    integration_weight = weights * horizon_years / 2.0

    cumulative_at_origin = np.zeros_like(evaluation_time)
    hazards: dict[str, np.ndarray] = {
        "progression": np.zeros_like(evaluation_time),
        "death": np.zeros_like(evaluation_time),
    }
    total_cumulative_increment = 0.0
    for item in exit_list:
        cumulative_at_origin += np.asarray(
            weibull_cumulative_hazard(
                evaluation_time,
                item.rate_per_year,
                item.shape,
            )
        ) - float(
            weibull_cumulative_hazard(
                duration_years,
                item.rate_per_year,
                item.shape,
            )
        )
        hazards[item.outcome] += np.asarray(
            weibull_hazard(
                evaluation_time,
                item.rate_per_year,
                item.shape,
            )
        )
        total_cumulative_increment += float(
            weibull_cumulative_hazard(
                duration_years + horizon_years,
                item.rate_per_year,
                item.shape,
            )
        ) - float(
            weibull_cumulative_hazard(
                duration_years,
                item.rate_per_year,
                item.shape,
            )
        )

    conditional_survival = np.exp(-cumulative_at_origin)
    raw_progression = float(
        np.sum(conditional_survival * hazards["progression"] * integration_weight)
    )
    raw_death = float(np.sum(conditional_survival * hazards["death"] * integration_weight))
    stable = math.exp(-total_cumulative_increment)
    exact_exit_probability = 1.0 - stable
    raw_exit_probability = raw_progression + raw_death
    if raw_exit_probability <= 0.0:
        raise ArithmeticError("Numerical integration returned no exit probability")
    scale = exact_exit_probability / raw_exit_probability
    progression = raw_progression * scale
    death = raw_death * scale

    return {
        "progression_probability": progression,
        "death_probability": death,
        "stable_probability": stable,
        "raw_partition_error": abs(raw_exit_probability + stable - 1.0),
    }


def _read_rows(path: Path, required_columns: Iterable[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        missing = [column for column in required_columns if column not in columns]
        if missing:
            raise ValueError(f"Missing columns in {path.name}: {missing}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"No rows in {path.name}")
    return rows


def _finite_number(row: Mapping[str, str], column: str, source: str) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid numeric value in {source}:{column}") from error
    if not math.isfinite(value):
        raise ValueError(f"Non-finite numeric value in {source}:{column}")
    return value


def _load_parameters(path: Path) -> dict[tuple[str, str], tuple[WeibullExit, ...]]:
    grouped: dict[tuple[str, str], list[WeibullExit]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    for row in _read_rows(path, PARAMETER_COLUMNS):
        key = (row["analysis_id"].strip(), row["origin_state"].strip())
        duplicate_key = (*key, row["destination_state"].strip())
        if duplicate_key in seen:
            raise ValueError(f"Duplicate Weibull exit: {duplicate_key}")
        seen.add(duplicate_key)
        grouped[key].append(
            WeibullExit(
                analysis_id=key[0],
                origin_state=key[1],
                destination_state=row["destination_state"].strip(),
                outcome=row["outcome"].strip().lower(),
                rate_per_year=_finite_number(row, "rate_per_year", path.name),
                shape=_finite_number(row, "shape", path.name),
                support_max_years=_finite_number(row, "support_max_years", path.name),
            )
        )
    for key, values in grouped.items():
        support_values = {item.support_max_years for item in values}
        if len(support_values) != 1:
            raise ValueError(f"Inconsistent support limit for {key}")
        if not any(item.outcome == "death" for item in values):
            raise ValueError(f"Missing death exit for {key}")
    return {key: tuple(values) for key, values in grouped.items()}


def build_weibull_outputs(
    input_dir: Path,
    output_dir: Path,
    *,
    quadrature_order: int = 96,
) -> list[Path]:
    parameters = _load_parameters(input_dir / "weibull_parameters.csv")
    estimands = _read_rows(input_dir / "weibull_estimands.csv", ESTIMAND_COLUMNS)

    outcome_rows: list[dict[str, object]] = []
    transition_rows: list[dict[str, object]] = []
    seen_estimands: set[tuple[str, str, float, float]] = set()
    seen_transition_points: set[tuple[str, str, str, float]] = set()

    for row in estimands:
        analysis_id = row["analysis_id"].strip()
        origin_state = row["origin_state"].strip()
        duration = _finite_number(row, "duration_years", "weibull_estimands.csv")
        horizon = _finite_number(row, "horizon_years", "weibull_estimands.csv")
        key = (analysis_id, origin_state)
        if key not in parameters:
            raise ValueError(f"No Weibull parameters for {key}")
        estimand_key = (*key, duration, horizon)
        if estimand_key in seen_estimands:
            raise ValueError(f"Duplicate Weibull estimand: {estimand_key}")
        seen_estimands.add(estimand_key)

        probabilities = conditional_outcome_probabilities(
            parameters[key],
            duration_years=duration,
            horizon_years=horizon,
            quadrature_order=quadrature_order,
        )
        support_max = parameters[key][0].support_max_years
        outcome_rows.append(
            {
                "analysis_id": analysis_id,
                "origin_state": origin_state,
                "duration_years": duration,
                "horizon_years": horizon,
                **probabilities,
                "support_max_years": support_max,
                "beyond_support": duration + horizon > support_max,
                "quadrature_order": quadrature_order,
            }
        )

        for evaluation_duration in (duration, duration + horizon):
            for item in parameters[key]:
                transition_key = (
                    analysis_id,
                    origin_state,
                    item.destination_state,
                    evaluation_duration,
                )
                if transition_key in seen_transition_points:
                    continue
                seen_transition_points.add(transition_key)
                hazard = weibull_hazard(
                    evaluation_duration,
                    item.rate_per_year,
                    item.shape,
                )
                finite_hazard = math.isfinite(float(hazard))
                transition_rows.append(
                    {
                        "analysis_id": analysis_id,
                        "origin_state": origin_state,
                        "destination_state": item.destination_state,
                        "outcome": item.outcome,
                        "duration_years": evaluation_duration,
                        "rate_per_year": item.rate_per_year,
                        "shape": item.shape,
                        "hazard": hazard if finite_hazard else "",
                        "hazard_boundary": "" if finite_hazard else "infinite_at_zero",
                        "cumulative_hazard": weibull_cumulative_hazard(
                            evaluation_duration,
                            item.rate_per_year,
                            item.shape,
                        ),
                        "isolated_survival": weibull_survival(
                            evaluation_duration,
                            item.rate_per_year,
                            item.shape,
                        ),
                    }
                )

    output_dir.mkdir(parents=True, exist_ok=True)
    outcome_path = output_dir / "weibull_state_outcomes.csv"
    transition_path = output_dir / "weibull_transition_functions.csv"
    write_csv_rows(outcome_path, outcome_rows, list(outcome_rows[0]))
    write_csv_rows(transition_path, transition_rows, list(transition_rows[0]))
    return [outcome_path, transition_path]
