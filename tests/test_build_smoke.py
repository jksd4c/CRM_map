from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.dont_write_bytecode = True
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crmmap_public.figures import build_figure2, build_figure3  # noqa: E402
from crmmap_public.tables import build_table_outputs  # noqa: E402
from synthetic_inputs import create_synthetic_inputs  # noqa: E402


class BuildSmokeTests(unittest.TestCase):
    def test_public_outputs_are_created_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            input_dir = temporary_root / "inputs"
            create_synthetic_inputs(input_dir)
            build_outputs: list[list[Path]] = []
            for build_name in ("first", "second"):
                output_dir = temporary_root / build_name
                outputs = build_table_outputs(input_dir, output_dir)
                self.assertEqual(12, len(outputs))
                outputs.extend(
                    build_figure2(
                        input_dir / "figure2_state_duration_probability.csv",
                        output_dir / "figures",
                    )
                )
                outputs.extend(
                    build_figure3(
                        input_dir / "figure3_directed_transitions.csv",
                        output_dir / "figures",
                    )
                )
                build_outputs.append(outputs)

            first_outputs, second_outputs = build_outputs
            self.assertEqual(18, len(first_outputs))
            for path in first_outputs + second_outputs:
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 0)
            for first, second in zip(first_outputs, second_outputs, strict=True):
                self.assertEqual(first.name, second.name)
                self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
