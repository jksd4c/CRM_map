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

from crmmap_public.privacy import audit_share_package  # noqa: E402


class PrivacyAuditTests(unittest.TestCase):
    def test_share_package_has_no_privacy_or_path_issues(self) -> None:
        issues = audit_share_package(PACKAGE_ROOT)
        self.assertEqual([], issues, msg="\n".join(str(issue) for issue in issues))

    def test_spreadsheet_formula_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "table.csv").write_text("value\n=SUM(A1:A1)\n", encoding="utf-8")
            issues = audit_share_package(root)
        self.assertEqual(["spreadsheet_formula_cell"], [issue.category for issue in issues])


if __name__ == "__main__":
    unittest.main()
