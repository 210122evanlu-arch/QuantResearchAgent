"""Fail when release candidates contain secrets or unapproved artifacts."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOW_SECRET_MARKER = "release-audit: allow-secret"
MAX_FIXTURE_BYTES = 1_000_000
REQUIRED_FILES = {
    ".env.example",
    ".github/workflows/ci.yml",
    "LICENSE",
    "README.md",
    "evals/baseline.json",
    "examples/data/DATA_LICENSE.md",
    "pyproject.toml",
    "requirements-dev.lock",
    "requirements.lock",
}
FORBIDDEN_EXACT = {".env", ".coverage", "coverage.xml"}
FORBIDDEN_SUFFIXES = {".parquet", ".pq", ".xlsx", ".xls", ".pdf"}
APPROVED_REPORTS = {
    "reports/example_report.md",
    "reports/showcase/byd_risk_advisory.md",
    "reports/showcase/moutai_company_research.md",
    "reports/showcase/event_intelligence_showcase.md",
    "reports/showcase/momentum_factor_research.md",
    "reports/showcase/dcf_sensitivity_showcase.md",
}
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    re.compile(
        r"\b(?:API_KEY|SECRET|TOKEN|PASSWORD)\s*=\s*"
        r"(?P<value>[^\s#'\"]+)",
    ),
)
PLACEHOLDERS = {"", "your-api-key", "changeme", "example", "placeholder"}


def release_candidates(root: Path = ROOT) -> list[Path]:
    """Return tracked and untracked, non-ignored files as release candidates."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def secret_findings(text: str) -> list[int]:
    """Return 1-based line numbers containing non-placeholder credentials."""
    findings: list[int] = []
    lines = text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        marker_window = lines[
            max(0, line_number - 3) : min(len(lines), line_number + 2)
        ]
        if any(ALLOW_SECRET_MARKER in nearby for nearby in marker_window):
            continue
        for pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            value = match.groupdict().get("value")
            if value is not None and value.lower() in PLACEHOLDERS:
                continue
            findings.append(line_number)
            break
    return findings


def audit(root: Path = ROOT) -> list[str]:
    """Return release-policy violations without mutating the repository."""
    candidates = release_candidates(root)
    candidate_names = {path.as_posix() for path in candidates}
    errors = [
        f"missing required release file: {required}"
        for required in sorted(REQUIRED_FILES - candidate_names)
    ]

    for relative in candidates:
        normalized = relative.as_posix()
        absolute = root / relative
        if normalized in FORBIDDEN_EXACT or normalized.startswith(".venv/"):
            errors.append(f"forbidden local artifact: {normalized}")
        if relative.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"unapproved binary/data artifact: {normalized}")
        if normalized.startswith("reports/") and normalized not in APPROVED_REPORTS:
            errors.append(f"generated report must stay ignored: {normalized}")
        if relative.suffix.lower() == ".csv":
            if not normalized.startswith("examples/data/"):
                errors.append(
                    f"CSV is outside the approved fixture directory: {normalized}"
                )
            elif absolute.stat().st_size > MAX_FIXTURE_BYTES:
                errors.append(
                    f"fixture exceeds {MAX_FIXTURE_BYTES} bytes: {normalized}"
                )

        try:
            text = absolute.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number in secret_findings(text):
            errors.append(f"possible secret: {normalized}:{line_number}")

    report_path = root / "reports/example_report.md"
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8").lower()
        if "not investment advice" not in report:
            errors.append("example report lacks the investment disclaimer")
        if "offline" not in report or "fixture" not in report:
            errors.append(
                "example report is not clearly identified as an offline fixture"
            )
    return errors


def main() -> int:
    errors = audit()
    if errors:
        print("Release audit failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Release audit passed: no secrets or unapproved artifacts detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
