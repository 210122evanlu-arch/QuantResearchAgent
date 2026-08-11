from pathlib import Path

from examples.event_intelligence_demo import run_event_intelligence_demo
from schemas.events import ResearchUpdateAction


def test_event_demo_generates_refresh_decision(tmp_path: Path) -> None:
    result, report = run_event_intelligence_demo(tmp_path / "events.md")
    assert result.action == ResearchUpdateAction.REFRESH_REPORT
    assert result.duplicate_count == 1
    assert report.is_file()
    content = report.read_text(encoding="utf-8")
    assert "建议重跑的报告部分" in content
    assert "新闻报道在缺少原始披露时仅进入观察清单" in content
