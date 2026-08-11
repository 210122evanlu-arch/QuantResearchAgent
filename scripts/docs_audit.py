"""Audit local documentation links, quality commands, and version declarations."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MYPY_TARGETS = (
    "agents api data_sources evals graph literature llm schemas tools examples "
    "production.py config.py logging_config.py main.py scripts/docs_audit.py"
)
QUALITY_COMMAND = rf".\.venv\Scripts\python.exe -m mypy {MYPY_TARGETS}"
MARKDOWN_LINK = re.compile(
    r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)"
)
HTML_LINK = re.compile(r"(?:href|src)=[\"'](?P<target>[^\"']+)[\"']")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "data:")


def document_paths(root: Path = ROOT) -> list[Path]:
    """Return tracked and untracked, non-ignored Markdown release candidates."""
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.md",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def _local_target(target: str) -> str | None:
    cleaned = target.strip("<>").strip()
    if not cleaned or cleaned.startswith("#"):
        return None
    if cleaned.casefold().startswith(EXTERNAL_PREFIXES):
        return None
    return unquote(cleaned.split("#", 1)[0].split("?", 1)[0])


def audit_links(root: Path, paths: list[Path]) -> list[str]:
    """Return broken or unsafe local link findings for the supplied documents."""
    errors: list[str] = []
    resolved_root = root.resolve()
    for relative in paths:
        source = root / relative
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read UTF-8 document {relative.as_posix()}: {exc}")
            continue
        targets = [
            *(match.group("target") for match in MARKDOWN_LINK.finditer(text)),
            *(match.group("target") for match in HTML_LINK.finditer(text)),
        ]
        for raw_target in targets:
            target = _local_target(raw_target)
            if target is None:
                continue
            destination = (
                (resolved_root / target.lstrip("/"))
                if target.startswith("/")
                else (source.parent / target)
            ).resolve()
            try:
                destination.relative_to(resolved_root)
            except ValueError:
                errors.append(
                    f"local link escapes repository: {relative.as_posix()} -> {target}"
                )
                continue
            if not destination.exists():
                errors.append(f"broken local link: {relative.as_posix()} -> {target}")
    return errors


def audit_consistency(root: Path = ROOT) -> list[str]:
    """Return documentation consistency violations."""
    errors = audit_links(root, document_paths(root))
    required = {
        "README.md": (
            QUALITY_COMMAND,
            "docs/capability_status.md",
            "当前公开 Release\uff1a[v0.1.0]",
            "API 契约版本为 `0.3.0`",
        ),
        "CONTRIBUTING.md": (
            QUALITY_COMMAND,
            "python.exe -m evals.release_benchmark",
            "python.exe scripts\\docs_audit.py",
        ),
        "docs/release_status.md": (
            "Public release: v0.1.0",
            "Main branch: Unreleased",
            "API contract: 0.3.0",
        ),
        "CHANGELOG.md": ("## [Unreleased]", "## [0.1.0]"),
        ".github/workflows/ci.yml": (
            f"run: mypy {MYPY_TARGETS}",
            "run: python scripts/docs_audit.py",
        ),
        "docs/capability_status.md": (
            "End-to-end offline showcase",
            "Route contract and template",
        ),
    }
    for relative, markers in required.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing consistency document: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(f"missing documentation marker in {relative}: {marker}")

    app_path = root / "api" / "app.py"
    if app_path.is_file():
        app_text = app_path.read_text(encoding="utf-8")
        match = re.search(r'version="(?P<version>[^"]+)"', app_text)
        status_text = (root / "docs" / "release_status.md").read_text(encoding="utf-8")
        if (
            match is None
            or f"API contract: {match.group('version')}" not in status_text
        ):
            errors.append(
                "API contract version differs between code and release status"
            )
    if "\uff08后续\uff09" in (root / "ROADMAP.md").read_text(encoding="utf-8"):
        errors.append("ROADMAP uses ambiguous status '后续'; move work to Backlog")
    return errors


def main() -> int:
    errors = audit_consistency()
    if errors:
        print("Documentation audit failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Documentation audit passed: links, commands, versions, and statuses agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
