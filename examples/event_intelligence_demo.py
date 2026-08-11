"""Offline disclosure-plus-news event intelligence showcase."""

from datetime import UTC, date, datetime
from pathlib import Path

from schemas.events import EventAnalysisRequest
from schemas.platform import EvidenceRecord
from tools.event_intelligence import analyze_events
from tools.event_report import render_event_intelligence, save_event_intelligence


def _record(
    evidence_id: str,
    title: str,
    published_at: datetime,
    *,
    source_type: str,
    source_name: str,
    url: str,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        source_type=source_type,
        title=title,
        source_name=source_name,
        url=url,
        published_at=published_at,
        retrieved_at=datetime(2026, 8, 11, tzinfo=UTC),
        summary=title,
    )


def run_event_intelligence_demo(report_path: str | Path | None = None):
    request = EventAnalysisRequest(
        company_name="示例制造股份有限公司",
        security_code="000000.SZ",
        report_as_of_date=date(2026, 8, 1),
        as_of_date=date(2026, 8, 10),
        evidence=[
            _record(
                "BYD-EVT-1",
                "示例制造股份有限公司2026年半年度业绩预告：净利润下降",
                datetime(2026, 8, 5, tzinfo=UTC),
                source_type="company_announcement",
                source_name="CNInfo",
                url="https://example.test/company/earnings-guidance",
            ),
            _record(
                "BYD-EVT-2",
                "关于2026年半年度业绩预告净利润下降的公告",
                datetime(2026, 8, 6, tzinfo=UTC),
                source_type="news",
                source_name="Licensed Business News",
                url="https://example.test/news/company-guidance",
            ),
            _record(
                "BYD-EVT-3",
                "示例制造关于回购股份的公告",
                datetime(2026, 8, 7, tzinfo=UTC),
                source_type="company_announcement",
                source_name="CNInfo",
                url="https://example.test/company/buyback",
            ),
            _record(
                "BYD-EVT-4",
                "媒体称示例制造海外产品可能面临召回",
                datetime(2026, 8, 9, tzinfo=UTC),
                source_type="news",
                source_name="Licensed Business News",
                url="https://example.test/news/company-recall",
            ),
        ],
    )
    result = analyze_events(request)
    content = render_event_intelligence(result)
    target = (
        Path(report_path)
        if report_path
        else (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "event_intelligence"
            / "event_update_demo.md"
        )
    )
    return result, save_event_intelligence(content, target)


if __name__ == "__main__":
    result, path = run_event_intelligence_demo()
    print("Action:", result.action.value)
    print("Events:", len(result.events))
    print("Duplicates removed:", result.duplicate_count)
    print("Report:", path)
