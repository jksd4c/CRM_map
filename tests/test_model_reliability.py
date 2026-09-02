from __future__ import annotations

import csv
import json
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

from crmmap_public.reliability import (  # noqa: E402
    build_model_reliability,
    chi_square_survival,
    wilson_interval,
)
from synthetic_inputs import create_synthetic_inputs  # noqa: E402


class ModelReliabilityTests(unittest.TestCase):
    def test_chi_square_survival_matches_closed_form(self) -> None:
        self.assertAlmostEqual(math.exp(-5.0), chi_square_survival(10.0, 2), places=14)

    def test_wilson_interval_contains_observed_coverage(self) -> None:
        lower, upper = wilson_interval(18, 20)
        self.assertLess(lower, 0.9)
        self.assertGreater(upper, 0.9)

    def test_reliability_outputs_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inputs = root / "inputs"
            create_synthetic_inputs(inputs)
            output_sets = []
            for name in ("first", "second"):
                output_sets.append(
                    build_model_reliability(
                        inputs / "model_reliability",
                        root / name,
                        PACKAGE_ROOT / "config" / "model_reliability.example.json",
                    )
                )

            self.assertEqual(7, len(output_sets[0]))
            for first, second in zip(*output_sets, strict=True):
                self.assertEqual(first.name, second.name)
                self.assertEqual(first.read_bytes(), second.read_bytes())

            summary = json.loads((root / "first" / "model_reliability_summary.json").read_text())
            self.assertEqual("PASS", summary["status"])
            with (root / "first" / "nested_likelihood_comparisons.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                comparisons = list(csv.DictReader(handle))
            self.assertAlmostEqual(math.exp(-5.0), float(comparisons[0]["p_value"]), places=14)


if __name__ == "__main__":
    unittest.main()
