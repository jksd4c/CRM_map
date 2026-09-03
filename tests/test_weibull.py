from __future__ import annotations

import csv
import math
import sys
import tempfile
import unittest
from pathlib import Path


sys.dont_write_bytecode = True
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crmmap_public.weibull import (  # noqa: E402
    WeibullExit,
    build_weibull_outputs,
    conditional_outcome_probabilities,
    weibull_cumulative_hazard,
    weibull_hazard,
    weibull_survival,
)
from synthetic_inputs import create_synthetic_inputs  # noqa: E402


class WeibullFunctionTests(unittest.TestCase):
    def test_exponential_special_case(self) -> None:
        rate = 0.2
        duration = 3.0
        self.assertAlmostEqual(rate, weibull_hazard(duration, rate, 1.0))
        self.assertAlmostEqual(rate * duration, weibull_cumulative_hazard(duration, rate, 1.0))
        self.assertAlmostEqual(math.exp(-rate * duration), weibull_survival(duration, rate, 1.0))

    def test_competing_exponential_probabilities_match_closed_form(self) -> None:
        exits = (
            WeibullExit("A", "SC", "SCR", "progression", 0.1, 1.0, 10.0),
            WeibullExit("A", "SC", "SX", "death", 0.05, 1.0, 10.0),
        )
        result = conditional_outcome_probabilities(
            exits,
            duration_years=2.0,
            horizon_years=4.0,
        )
        total_exit = 1.0 - math.exp(-0.15 * 4.0)
        self.assertAlmostEqual(total_exit * 2.0 / 3.0, result["progression_probability"], places=12)
        self.assertAlmostEqual(total_exit / 3.0, result["death_probability"], places=12)
        self.assertAlmostEqual(math.exp(-0.15 * 4.0), result["stable_probability"], places=12)
        self.assertAlmostEqual(
            1.0,
            result["progression_probability"]
            + result["death_probability"]
            + result["stable_probability"],
            places=14,
        )

    def test_duration_dependence_changes_conditional_probability(self) -> None:
        exits = (
            WeibullExit("A", "SC", "SCR", "progression", 0.1, 0.7, 10.0),
            WeibullExit("A", "SC", "SX", "death", 0.05, 1.4, 10.0),
        )
        early = conditional_outcome_probabilities(
            exits,
            duration_years=0.0,
            horizon_years=2.0,
        )
        late = conditional_outcome_probabilities(
            exits,
            duration_years=5.0,
            horizon_years=2.0,
        )
        self.assertNotAlmostEqual(
            early["progression_probability"],
            late["progression_probability"],
            places=6,
        )


class WeibullBuildTests(unittest.TestCase):
    def test_synthetic_build_has_closed_probabilities_and_support_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "inputs"
            output_dir = root / "outputs"
            create_synthetic_inputs(input_dir)
            outputs = build_weibull_outputs(input_dir / "weibull", output_dir)
            self.assertEqual(2, len(outputs))
            with (output_dir / "weibull_state_outcomes.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(189, len(rows))
            for row in rows:
                total = sum(
                    float(row[column])
                    for column in (
                        "progression_probability",
                        "death_probability",
                        "stable_probability",
                    )
                )
                self.assertAlmostEqual(1.0, total, places=12)
                self.assertIn(row["beyond_support"], {"True", "False"})


if __name__ == "__main__":
    unittest.main()
