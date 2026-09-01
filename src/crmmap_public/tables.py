from __future__ import annotations

import csv
from pathlib import Path

EXPECTED_MAIN_TABLE_FILES = (
    "table1_baseline_characteristics.csv",
    "table2_state_duration_competing_exits.csv",
)

EXPECTED_SUPPLEMENTARY_TABLE_FILES = (
    "table_s1_definitions_states.csv",
    "table_s2_cohort.csv",
    "table_s3_state_probabilities.csv",
    "table_s4_duration_second_disease.csv",
    "table_s5_directed_transitions.csv",
    "table_s6_prognosis.csv",
    "table_s7_function.csv",
    "table_s8_associations.csv",
    "table_s9_model_validation.csv",
    "table_s10_sensitivities.csv",
)


def build_table_outputs(input_dir: Path, output_dir: Path) -> list[Path]:
    target_dir = output_dir / "tables"
    outputs: list[Path] = []

    table_groups = (
        (input_dir / "main_tables", EXPECTED_MAIN_TABLE_FILES),
        (input_dir / "supplementary_tables", EXPECTED_SUPPLEMENTARY_TABLE_FILES),
    )
    for source_dir, filenames in table_groups:
        for filename in filenames:
            source = source_dir / filename
            with source.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            if not rows or not any(any(cell != "" for cell in row) for row in rows):
                raise ValueError(f"Empty table source: {filename}")
            target = target_dir / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerows(rows)
            outputs.append(target)

    return outputs
