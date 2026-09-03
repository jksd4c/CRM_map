from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.dont_write_bytecode = True
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crmmap_public.privacy import audit_share_package  # noqa: E402
from crmmap_public.weibull import build_weibull_outputs  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Weibull transition functions and state-outcome probabilities from aggregate parameters."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quadrature-order", type=int, default=96)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    input_dir = arguments.input_dir.resolve()
    output_dir = arguments.output_dir.resolve()
    input_issues = audit_share_package(input_dir)
    if input_issues:
        raise RuntimeError(f"Input audit failed: {input_issues}")
    build_weibull_outputs(
        input_dir,
        output_dir,
        quadrature_order=arguments.quadrature_order,
    )
    output_issues = audit_share_package(output_dir)
    if output_issues:
        raise RuntimeError(f"Output audit failed: {output_issues}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
