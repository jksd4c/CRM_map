from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.dont_write_bytecode = True
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crmmap_public.privacy import audit_share_package  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the shareable CRMmap package.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional relative or absolute JSON report path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    issues = audit_share_package(PACKAGE_ROOT)
    payload = {
        "status": "PASS" if not issues else "FAIL",
        "issues": [issue.__dict__ for issue in issues],
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        output = args.output if args.output.is_absolute() else PACKAGE_ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
