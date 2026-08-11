"""Deterministic event classification, deduplication, and refresh decisions."""

import hashlib
import re
from datetime import timedelta
from difflib import SequenceMatcher

from schemas.enums import IssueSeverity
from schemas.events import (
    EventAnalysisRequest,
    EventCategory,
    EventIntelligenceResult,
    EventSourceType,
    ImpactDirection,
    ResearchEvent,
    ResearchUpdateAction,
)
from schemas.platform import EvidenceRecord

_CATEGORY_KEYWORDS = {
    EventCategory.EARNINGS: ("业绩", "年报", "季报", "盈利", "earnings", "profit"),
    EventCategory.OPERATIONS: ("产销", "销量", "订单", "投产", "召回", "sales"),
    EventCategory.CAPITAL_ALLOCATION: (
        "分红",
        "回购",
        "增持",
        "减持",
        "融资",
        "dividend",
    ),
    EventCategory.GOVERNANCE: ("董事", "高管", "关联交易", "审计", "governance"),
    EventCategory.REGULATORY: ("处罚", "监管", "立案", "制裁", "问询", "sanction"),
    EventCategory.TRANSACTION: ("收购", "出售", "重组", "合并", "并购", "acquisition"),
    EventCategory.LITIGATION: ("诉讼", "仲裁", "判决", "litigation"),
}
_CRITICAL = ("立案调查", "重大违法", "破产", "退市", "刑事", "重大诉讼")
_HIGH = ("业绩预告", "年度报告", "重大合同", "担保", "召回", "处罚", "制裁", "重组")
_POSITIVE = ("增长", "中标", "增持", "回购", "上调", "扭亏", "获批")
_NEGATIVE = ("下降", "亏损", "减持", "处罚", "诉讼", "召回", "下调", "终止")
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _normalized_title(title: str, company_name: str) -> str:
    value = title.lower().replace(company_name.lower(), "")
    value = re.sub(r"关于|公告|更正|补充|[\W_]+", "", value)
    return value


def _category(text: str) -> EventCategory:
    lowered = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return EventCategory.OTHER


def _source_type(record: EvidenceRecord) -> EventSourceType:
    value = f"{record.source_type} {record.source_name}".lower()
    if any(item in value for item in ("cninfo", "公告", "announcement", "filing")):
        return EventSourceType.OFFICIAL_DISCLOSURE
    if any(item in value for item in ("exchange", "监管", "regulator")):
        return EventSourceType.REGULATORY_SOURCE
    return EventSourceType.NEWS


def _materiality(text: str, category: EventCategory) -> IssueSeverity:
    if any(keyword in text for keyword in _CRITICAL):
        return IssueSeverity.CRITICAL
    if any(keyword in text for keyword in _HIGH):
        return IssueSeverity.HIGH
    if category != EventCategory.OTHER:
        return IssueSeverity.MEDIUM
    return IssueSeverity.LOW


def _direction(text: str) -> ImpactDirection:
    positive = any(keyword in text for keyword in _POSITIVE)
    negative = any(keyword in text for keyword in _NEGATIVE)
    if positive and negative:
        return ImpactDirection.MIXED
    if positive:
        return ImpactDirection.POSITIVE
    if negative:
        return ImpactDirection.NEGATIVE
    return ImpactDirection.UNCERTAIN


def _affected_sections(category: EventCategory) -> list[str]:
    mapping = {
        EventCategory.EARNINGS: ["executive_summary", "financial_quality", "valuation"],
        EventCategory.OPERATIONS: [
            "executive_summary",
            "competitive_position",
            "risks",
        ],
        EventCategory.CAPITAL_ALLOCATION: [
            "financial_quality",
            "valuation",
            "catalysts",
        ],
        EventCategory.GOVERNANCE: ["risks", "limitations"],
        EventCategory.REGULATORY: ["executive_summary", "risks", "limitations"],
        EventCategory.TRANSACTION: ["business_model", "valuation", "risks"],
        EventCategory.LITIGATION: ["risks", "limitations"],
        EventCategory.OTHER: ["monitoring_indicators"],
    }
    return mapping[category]


def _is_duplicate(
    record: EvidenceRecord,
    normalized: str,
    accepted: list[tuple[EvidenceRecord, str]],
) -> bool:
    for prior, prior_normalized in accepted:
        if record.document_id and record.document_id == prior.document_id:
            return True
        if record.url and record.url == prior.url:
            return True
        if not record.published_at or not prior.published_at:
            continue
        nearby = abs(record.published_at - prior.published_at) <= timedelta(days=3)
        similar = SequenceMatcher(None, normalized, prior_normalized).ratio() >= 0.82
        if nearby and similar:
            return True
    return False


def analyze_events(request: EventAnalysisRequest) -> EventIntelligenceResult:
    eligible = [
        item
        for item in request.evidence
        if item.published_at and item.published_at.date() <= request.as_of_date
    ]
    eligible.sort(
        key=lambda item: (
            _source_type(item) == EventSourceType.NEWS,
            item.published_at,
        )
    )
    accepted: list[tuple[EvidenceRecord, str]] = []
    duplicates = 0
    events: list[ResearchEvent] = []
    for record in eligible:
        published_at = record.published_at
        if published_at is None:
            continue
        normalized = _normalized_title(record.title, request.company_name)
        if _is_duplicate(record, normalized, accepted):
            duplicates += 1
            continue
        accepted.append((record, normalized))
        category = _category(f"{record.title} {record.summary}")
        materiality = _materiality(record.title, category)
        source_type = _source_type(record)
        fingerprint = hashlib.sha256(
            f"{request.security_code}|{normalized}|{published_at.date()}".encode()
        ).hexdigest()[:16]
        events.append(
            ResearchEvent(
                event_id=f"EVT-{fingerprint.upper()}",
                fingerprint=fingerprint,
                company_name=request.company_name,
                security_code=request.security_code,
                title=record.title,
                published_at=published_at,
                source_type=source_type,
                category=category,
                direction=_direction(f"{record.title} {record.summary}"),
                materiality=materiality,
                evidence_ids=[record.evidence_id],
                affected_sections=_affected_sections(category),
                rationale=(
                    "Official or regulatory evidence can trigger a research refresh."
                    if source_type != EventSourceType.NEWS
                    else "News is retained as a lead until primary evidence is available."
                ),
            )
        )

    new_events = [
        event
        for event in events
        if event.published_at.date() > request.report_as_of_date
    ]
    verified = [
        event for event in new_events if event.source_type != EventSourceType.NEWS
    ]
    highest = max(
        (_SEVERITY_RANK[event.materiality.value] for event in verified), default=-1
    )
    if highest >= _SEVERITY_RANK[IssueSeverity.CRITICAL.value]:
        action = ResearchUpdateAction.ESCALATE_REVIEW
    elif highest >= _SEVERITY_RANK[IssueSeverity.HIGH.value]:
        action = ResearchUpdateAction.REFRESH_REPORT
    elif new_events:
        action = ResearchUpdateAction.WATCHLIST
    else:
        action = ResearchUpdateAction.NO_ACTION
    triggers = [
        event
        for event in verified
        if _SEVERITY_RANK[event.materiality.value]
        >= _SEVERITY_RANK[IssueSeverity.HIGH.value]
    ]
    sections = list(
        dict.fromkeys(
            section for event in triggers for section in event.affected_sections
        )
    )
    return EventIntelligenceResult(
        company_name=request.company_name,
        security_code=request.security_code,
        as_of_date=request.as_of_date,
        report_as_of_date=request.report_as_of_date,
        events=events,
        duplicate_count=duplicates,
        action=action,
        trigger_event_ids=[event.event_id for event in triggers],
        affected_sections=sections,
        rationale=(
            f"识别 {len(new_events)} 项报告截止日后的新事件，其中 {len(verified)} 项"
            f"获得原始证据支持；进入判断前移除 {duplicates} 项重复信息。"
        ),
    )
