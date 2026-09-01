from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


TEXT_EXTENSIONS = {
    ".csv",
    ".json",
    ".md",
    ".py",
    ".svg",
    ".txt",
    ".yml",
    ".yaml",
}

PROHIBITED_EXTENSIONS = {
    ".7z",
    ".db",
    ".dta",
    ".env",
    ".feather",
    ".key",
    ".parquet",
    ".pem",
    ".pickle",
    ".pkl",
    ".pyc",
    ".rar",
    ".sas7bdat",
    ".sav",
    ".sqlite",
    ".xpt",
    ".zip",
}

PROHIBITED_HEADERS = {
    "address",
    "birth_date",
    "date_of_birth",
    "email",
    "hhid",
    "mergeid",
    "name",
    "national_id",
    "participant_id",
    "person_id",
    "person_key_restricted",
    "phone",
    "social_security_number",
}

PATH_PATTERNS = {
    "windows_absolute_path": re.compile(r"(?i)(?<![A-Za-z])[A-Za-z]:[\\/]"),
    "windows_user_profile": re.compile(r"(?i)Users[\\/][^\\/\s]+"),
    "unix_home_path": re.compile(r"(?i)(?:/home/|/Users/)[^/\s]+"),
    "unc_path": re.compile(r"\\\\[^\\\s]+\\[^\\\s]+"),
}

CORE_CODE_PATTERN = re.compile(
    r"(?i)\b(?:best_parameters_log_scale|observed_information|compatible_order|"
    r"likelihood_engine|optimizer_checkpoint)\b"
)

SIGNED_NUMERIC_SUMMARY_PATTERN = re.compile(
    r"^[+-](?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
    r"(?:\s+\([+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
    r"\s+to\s+[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?\))?$"
)


@dataclass(frozen=True)
class AuditIssue:
    category: str
    path: str
    detail: str


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_spreadsheet_formula(value: str) -> bool:
    stripped = value.lstrip()
    if not stripped:
        return False
    if stripped[0] in {"=", "@"}:
        return True
    if stripped[0] not in {"+", "-"} or stripped == "-":
        return False
    return SIGNED_NUMERIC_SUMMARY_PATTERN.fullmatch(stripped) is None


def audit_share_package(root: Path) -> list[AuditIssue]:
    root = root.resolve()
    issues: list[AuditIssue] = []

    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = _relative(root, path)
        suffix = path.suffix.lower()

        if path.is_symlink():
            issues.append(AuditIssue("symbolic_link", relative, "external target risk"))
            continue

        if suffix in PROHIBITED_EXTENSIONS:
            issues.append(AuditIssue("prohibited_file_type", relative, suffix))
            continue

        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, [])
                rows = list(reader)
            matches = sorted(
                value.strip().lower()
                for value in header
                if value.strip().lower() in PROHIBITED_HEADERS
            )
            if matches:
                issues.append(
                    AuditIssue("participant_identifier_header", relative, ",".join(matches))
                )
            for row_index, row in enumerate(rows, start=2):
                for column_index, value in enumerate(row, start=1):
                    if _is_spreadsheet_formula(value):
                        issues.append(
                            AuditIssue(
                                "spreadsheet_formula_cell",
                                relative,
                                f"row={row_index},column={column_index}",
                            )
                        )

        if suffix not in TEXT_EXTENSIONS:
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        is_rule_definition = relative == "src/crmmap_public/privacy.py"
        if not is_rule_definition:
            for category, pattern in PATH_PATTERNS.items():
                if pattern.search(text):
                    issues.append(AuditIssue(category, relative, "pattern detected"))

            if suffix in {".py"} and CORE_CODE_PATTERN.search(text):
                issues.append(
                    AuditIssue("restricted_model_code_marker", relative, "pattern detected")
                )

    return issues
