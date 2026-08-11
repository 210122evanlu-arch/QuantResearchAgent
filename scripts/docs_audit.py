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
RELEASE_HEADING = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\]", re.MULTILINE)


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


def latest_release_version(changelog: str) -> str | None:
    """Return the newest semantic release heading below Unreleased."""
    match = RELEASE_HEADING.search(changelog)
    return match.group("version") if match else None


def audit_consistency(root: Path = ROOT) -> list[str]:
    """Return documentation consistency violations."""
    errors = audit_links(root, document_paths(root))
    required = {
        "README.md": (
            QUALITY_COMMAND,
            "docs/capability_status.md",
        ),
        "CONTRIBUTING.md": (
            QUALITY_COMMAND,
            "python.exe -m evals.release_benchmark",
            "python.exe scripts\\docs_audit.py",
        ),
        "docs/release_status.md": ("API contract:",),
        "CHANGELOG.md": ("## [Unreleased]", "## [0.1.0]"),
        ".github/workflows/ci.yml": (
            f"run: mypy {MYPY_TARGETS}",
            "run: python scripts/docs_audit.py",
        ),
        "docs/capability_status.md": ("End-to-end offline showcase",),
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

    changelog_text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    release_version = latest_release_version(changelog_text)
    if release_version is None:
        errors.append("CHANGELOG has no semantic release heading")
    else:
        release_markers = {
            "README.md": f"[v{release_version}]",
            "docs/release_status.md": f"Public release: v{release_version}",
            f"docs/releases/v{release_version}.md": f"v{release_version}",
        }
        for relative, marker in release_markers.items():
            path = root / relative
            if not path.is_file():
                errors.append(f"missing release document: {relative}")
            elif marker not in path.read_text(encoding="utf-8"):
                errors.append(
                    f"release version differs in {relative}: expected {marker}"
                )

    app_path = root / "api" / "app.py"
    if app_path.is_file():
        app_text = app_path.read_text(encoding="utf-8")
        match = re.search(r'version="(?P<version>[^"]+)"', app_text)
        status_text = (root / "docs" / "release_status.md").read_text(encoding="utf-8")
        readme_text = (root / "README.md").read_text(encoding="utf-8")
        if match is None:
            errors.append("API contract version is missing from code")
        elif (
            f"API contract: {match.group('version')}" not in status_text
            or f"API 契约版本为 `{match.group('version')}`" not in readme_text
        ):
            errors.append(
                "API contract version differs between code, README, and release status"
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
