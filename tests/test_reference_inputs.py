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

from crmmap_public.verify import validate_reference_inputs  # noqa: E402
from synthetic_inputs import create_synthetic_inputs  # noqa: E402


class ReferenceInputTests(unittest.TestCase):
    def test_reference_inputs_match_public_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_dir = Path(temporary_directory) / "inputs"
            create_synthetic_inputs(input_dir)
            report = validate_reference_inputs(PACKAGE_ROOT, input_dir)
        self.assertEqual("PASS", report["status"])
        self.assertEqual(20, len(report["files"]))


if __name__ == "__main__":
    unittest.main()
