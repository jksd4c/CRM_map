from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.dont_write_bytecode = True
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crmmap_public.figures import build_figure2, build_figure3  # noqa: E402
from crmmap_public.io import relative_manifest, write_json  # noqa: E402
from crmmap_public.privacy import audit_share_package  # noqa: E402
from crmmap_public.tables import build_table_outputs  # noqa: E402
from crmmap_public.verify import validate_reference_inputs  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build disclosure-checked CRMmap tables and Figures 2-3."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("public_reference"))
    parser.add_argument("--output-dir", type=Path, default=Path("build"))
    return parser.parse_args()


def resolve_from_package(path: Path) -> Path:
    return path if path.is_absolute() else PACKAGE_ROOT / path


def main() -> int:
    args = parse_args()
    input_dir = resolve_from_package(args.input_dir).resolve()
    output_dir = resolve_from_package(args.output_dir).resolve()

    preflight_issues = audit_share_package(PACKAGE_ROOT)
    if preflight_issues:
        raise RuntimeError(f"Share-package audit failed: {preflight_issues}")

    validation = validate_reference_inputs(PACKAGE_ROOT, input_dir)
    outputs = build_table_outputs(input_dir, output_dir)
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

    manifest_path = output_dir / "release_manifest.json"
    write_json(
        manifest_path,
        {
            "status": "PASS",
            "input_validation": validation,
            "outputs": relative_manifest(output_dir, outputs),
        },
    )
    postflight_issues = audit_share_package(PACKAGE_ROOT)
    if postflight_issues:
        raise RuntimeError(f"Post-build share-package audit failed: {postflight_issues}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
