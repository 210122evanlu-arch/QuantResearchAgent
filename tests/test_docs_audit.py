from pathlib import Path

from scripts.docs_audit import ROOT, audit_consistency, audit_links


def test_repository_documentation_is_consistent() -> None:
    assert audit_consistency(ROOT) == []


def test_link_audit_reports_missing_and_escaping_targets(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "index.md"
    source.write_text(
        "[valid](existing.md) [missing](missing.md) "
        "[escape](../../outside.md) [external](https://example.test)",
        encoding="utf-8",
    )
    (docs / "existing.md").write_text("ok", encoding="utf-8")

    errors = audit_links(tmp_path, [Path("docs/index.md")])

    assert "broken local link: docs/index.md -> missing.md" in errors
    assert "local link escapes repository: docs/index.md -> ../../outside.md" in errors
    assert len(errors) == 2


def test_link_audit_reports_non_utf8_document(tmp_path: Path) -> None:
    path = tmp_path / "broken.md"
    path.write_bytes(b"\xff\xfe")

    errors = audit_links(tmp_path, [Path("broken.md")])

    assert errors and errors[0].startswith("cannot read UTF-8 document broken.md")
