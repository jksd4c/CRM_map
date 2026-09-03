from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from .io import read_csv_rows, sha256_file
from .tables import EXPECTED_MAIN_TABLE_FILES, EXPECTED_SUPPLEMENTARY_TABLE_FILES


def _required_files(schema_path: Path) -> dict[str, list[str]]:
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    return payload["required_files"]


def _numeric(row: dict[str, str], column: str, filename: str) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid numeric value in {filename}:{column}") from error
    if not math.isfinite(value):
        raise ValueError(f"Non-finite numeric value in {filename}:{column}")
    return value


def _validate_figure2(rows: list[dict[str, str]]) -> None:
    filename = "figure2_state_duration_probability.csv"
    expected_keys = {
        (cohort, state, float(duration))
        for cohort in ("HRS", "CHARLS", "SHARE")
        for state in ("SC", "SR", "SM")
        for duration in range(6)
    }
    actual_keys = [
        (row["cohort"], row["state"], _numeric(row, "u_years", filename)) for row in rows
    ]
    if len(actual_keys) != len(set(actual_keys)) or set(actual_keys) != expected_keys:
        raise ValueError(f"Unexpected or duplicate rows in {filename}")
    for row in rows:
        estimate = _numeric(row, "probability", filename)
        lower = _numeric(row, "lower_95", filename)
        upper = _numeric(row, "upper_95", filename)
        if not 0.0 <= lower <= estimate <= upper <= 1.0:
            raise ValueError(f"Invalid probability interval in {filename}")


def _validate_figure3(rows: list[dict[str, str]]) -> None:
    filename = "figure3_directed_transitions.csv"
    keys = [(row["section"], row["state_transition"], row["cohort"]) for row in rows]
    transitions = {(row["section"], row["state_transition"]) for row in rows}
    expected_keys = {
        (section, transition, cohort)
        for section, transition in transitions
        for cohort in ("HRS", "CHARLS", "SHARE")
    }
    if len(transitions) != 9 or len(keys) != len(set(keys)) or set(keys) != expected_keys:
        raise ValueError(f"Unexpected or duplicate rows in {filename}")
    interval_columns = (
        ("annual_rate_per_100py", "rate_lower_95", "rate_upper_95", None),
        ("probability_5y", "probability_lower_95", "probability_upper_95", 100.0),
    )
    for row in rows:
        for estimate_column, lower_column, upper_column, maximum in interval_columns:
            estimate = _numeric(row, estimate_column, filename)
            lower = _numeric(row, lower_column, filename)
            upper = _numeric(row, upper_column, filename)
            if not 0.0 <= lower <= estimate <= upper:
                raise ValueError(f"Invalid interval in {filename}:{estimate_column}")
            if maximum is not None and upper > maximum:
                raise ValueError(f"Out-of-range probability in {filename}:{estimate_column}")


def validate_reference_inputs(package_root: Path, input_dir: Path) -> dict[str, object]:
    schema_path = package_root / "schemas" / "aggregate_output.schema.json"
    required = _required_files(schema_path)
    checks: list[dict[str, object]] = []

    validated_rows: dict[str, list[dict[str, str]]] = {}
    for filename, columns in required.items():
        path = input_dir / filename
        rows = read_csv_rows(path)
        validated_rows[filename] = rows
        actual_columns = list(rows[0]) if rows else []
        missing = [column for column in columns if column not in actual_columns]
        checks.append(
            {
                "file": filename,
                "rows": len(rows),
                "missing_columns": missing,
                "sha256": sha256_file(path),
            }
        )

    reliability_schema = package_root / "schemas" / "model_reliability_input.schema.json"
    reliability_required = _required_files(reliability_schema)
    for filename, columns in reliability_required.items():
        path = input_dir / "model_reliability" / filename
        rows = read_csv_rows(path)
        actual_columns = list(rows[0]) if rows else []
        missing = [column for column in columns if column not in actual_columns]
        checks.append(
            {
                "file": f"model_reliability/{filename}",
                "rows": len(rows),
                "missing_columns": missing,
                "sha256": sha256_file(path),
            }
        )

    weibull_schema = package_root / "schemas" / "weibull_aggregate_input.schema.json"
    weibull_required = _required_files(weibull_schema)
    for filename, columns in weibull_required.items():
        path = input_dir / "weibull" / filename
        rows = read_csv_rows(path)
        actual_columns = list(rows[0]) if rows else []
        missing = [column for column in columns if column not in actual_columns]
        checks.append(
            {
                "file": f"weibull/{filename}",
                "rows": len(rows),
                "missing_columns": missing,
                "sha256": sha256_file(path),
            }
        )

    table_groups = (
        ("main_tables", EXPECTED_MAIN_TABLE_FILES),
        ("supplementary_tables", EXPECTED_SUPPLEMENTARY_TABLE_FILES),
    )
    for directory, filenames in table_groups:
        for filename in filenames:
            path = input_dir / directory / filename
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            checks.append(
                {
                    "file": f"{directory}/{filename}",
                    "rows": len(rows),
                    "missing_columns": [],
                    "sha256": sha256_file(path),
                }
            )

    failures = [check for check in checks if check["missing_columns"] or check["rows"] == 0]
    if failures:
        raise ValueError(f"Aggregate input validation failed: {failures}")

    _validate_figure2(validated_rows["figure2_state_duration_probability.csv"])
    _validate_figure3(validated_rows["figure3_directed_transitions.csv"])

    return {"status": "PASS", "files": checks}
