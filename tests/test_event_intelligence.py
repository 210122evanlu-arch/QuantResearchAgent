from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from schemas.events import (
    EventAnalysisRequest,
    EventCategory,
    EventSourceType,
    ImpactDirection,
    ResearchUpdateAction,
)
from schemas.platform import EvidenceRecord
from tools.event_intelligence import analyze_events


def _record(
    evidence_id: str,
    title: str,
    day: int,
    *,
    source_type: str = "company_announcement",
    source_name: str = "CNInfo",
    document_id: str | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        source_type=source_type,
        title=title,
        source_name=source_name,
        url=f"https://example.test/{evidence_id}",
        document_id=document_id,
        published_at=datetime(2026, 8, day, tzinfo=UTC),
        retrieved_at=datetime(2026, 8, 11, tzinfo=UTC),
        summary=title,
    )


def test_official_material_event_triggers_report_refresh_and_deduplication() -> None:
    request = EventAnalysisRequest(
        company_name="示例股份",
        security_code="600000.SH",
        report_as_of_date=date(2026, 8, 1),
        as_of_date=date(2026, 8, 10),
        evidence=[
            _record("E1", "示例股份2026年度业绩预告：利润下降", 5),
            _record("E2", "关于2026年度业绩预告利润下降的公告", 6),
        ],
    )

    result = analyze_events(request)

    assert result.action == ResearchUpdateAction.REFRESH_REPORT
    assert result.duplicate_count == 1
    assert len(result.events) == 1
    event = result.events[0]
    assert event.category == EventCategory.EARNINGS
    assert event.direction == ImpactDirection.NEGATIVE
    assert event.source_type == EventSourceType.OFFICIAL_DISCLOSURE
    assert "financial_quality" in result.affected_sections


def test_news_only_event_stays_on_watchlist_until_primary_evidence() -> None:
    request = EventAnalysisRequest(
        company_name="示例股份",
        security_code="600000.SH",
        report_as_of_date=date(2026, 8, 1),
        as_of_date=date(2026, 8, 10),
        evidence=[
            _record(
                "N1",
                "媒体称示例股份收到重大订单",
                8,
                source_type="news",
                source_name="Example Business News",
            )
        ],
    )

    result = analyze_events(request)

    assert result.action == ResearchUpdateAction.WATCHLIST
    assert result.trigger_event_ids == []
    assert result.events[0].source_type == EventSourceType.NEWS


def test_critical_regulatory_event_escalates_committee_review() -> None:
    request = EventAnalysisRequest(
        company_name="示例股份",
        security_code="600000.SH",
        report_as_of_date=date(2026, 8, 1),
        as_of_date=date(2026, 8, 10),
        evidence=[_record("R1", "公司因重大违法被立案调查", 9)],
    )

    result = analyze_events(request)

    assert result.action == ResearchUpdateAction.ESCALATE_REVIEW
    assert result.events[0].category == EventCategory.REGULATORY


def test_old_or_future_evidence_does_not_trigger_refresh() -> None:
    request = EventAnalysisRequest(
        company_name="示例股份",
        security_code="600000.SH",
        report_as_of_date=date(2026, 8, 5),
        as_of_date=date(2026, 8, 10),
        evidence=[
            _record("OLD", "年度报告", 1),
            _record("FUTURE", "重大合同公告", 11),
        ],
    )
    assert analyze_events(request).action == ResearchUpdateAction.NO_ACTION


def test_event_request_rejects_a_future_report_date() -> None:
    with pytest.raises(ValidationError, match="must not be after"):
        EventAnalysisRequest(
            company_name="示例股份",
            security_code="600000.SH",
            report_as_of_date=date(2026, 8, 11),
            as_of_date=date(2026, 8, 10),
            evidence=[_record("E1", "年度报告", 1)],
        )
