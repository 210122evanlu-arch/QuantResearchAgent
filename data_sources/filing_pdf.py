"""Download, verify, and extract page-level evidence from filing PDFs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, ClassVar, Protocol, cast

import requests
from pypdf import PdfReader

from schemas.company_filing import (
    FilingExtractionResult,
    FilingPageSection,
    FilingSectionTopic,
)
from schemas.platform import EvidenceRecord


class FilingPDFError(RuntimeError):
    """Raised when a filing cannot be safely downloaded or extracted."""


class DownloadResponse(Protocol):
    content: bytes
    headers: Any

    def raise_for_status(self) -> None: ...


class DownloadSession(Protocol):
    headers: Any

    def get(self, url: str, **kwargs: Any) -> DownloadResponse: ...


def select_latest_annual_report(
    records: list[EvidenceRecord], as_of_date: date
) -> EvidenceRecord:
    candidates = [
        item
        for item in records
        if "年度报告" in item.title
        and "摘要" not in item.title
        and "英文" not in item.title
        and item.url
        and item.published_at is not None
        and item.published_at.date() <= as_of_date
    ]
    if not candidates:
        raise FilingPDFError("No full annual-report PDF was found before as_of_date")
    return max(candidates, key=lambda item: cast(datetime, item.published_at))


def _normalise_text(value: str) -> str:
    value = value.replace("\x00", " ").replace("\u3000", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", value)).strip()


def _excerpt(text: str, keywords: tuple[str, ...], limit: int = 4500) -> str:
    positions = [text.find(keyword) for keyword in keywords if keyword in text]
    start = max(0, min(positions) - 600) if positions else 0
    return text[start : start + limit].strip()


@dataclass(frozen=True)
class FilingPDFExtractor:
    cache_directory: Path = Path("data/company_filings")
    timeout_seconds: float = 45.0
    maximum_bytes: int = 80 * 1024 * 1024
    pages_per_topic: int = 2
    session: DownloadSession | None = None

    topic_keywords: ClassVar[dict[FilingSectionTopic, tuple[str, ...]]] = {
        FilingSectionTopic.BUSINESS_MODEL: (
            "报告期内公司从事的主要业务",
            "主要业务及经营模式",
            "主营业务",
            "经营模式",
        ),
        FilingSectionTopic.MANAGEMENT_DISCUSSION: (
            "管理层讨论与分析",
            "经营情况讨论与分析",
            "经营情况的讨论与分析",
            "报告期内公司经营情况",
        ),
        FilingSectionTopic.SEGMENT_INFORMATION: (
            "分行业",
            "分产品",
            "分地区",
            "营业收入构成",
        ),
        FilingSectionTopic.CASH_FLOW: (
            "现金流量",
            "经营活动产生的现金流量",
            "现金及现金等价物",
        ),
        FilingSectionTopic.RISK_FACTORS: (
            "可能面对的风险",
            "公司面临的风险",
            "仍面临多重挑战",
            "面对诸多挑战",
            "国际贸易环境充满不确定性",
        ),
        FilingSectionTopic.AUDIT_OPINION: (
            "审计意见",
            "无保留意见",
            "保留意见",
            "否定意见",
            "无法表示意见",
        ),
    }

    def __post_init__(self) -> None:
        if self.maximum_bytes < 1_000_000:
            raise ValueError("maximum_bytes must be at least 1 MB")
        if not 1 <= self.pages_per_topic <= 4:
            raise ValueError("pages_per_topic must be between 1 and 4")

    def _download(self, record: EvidenceRecord) -> tuple[Path, str]:
        if not record.url:
            raise FilingPDFError("Annual-report evidence is missing a URL")
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        output = self.cache_directory / f"{record.evidence_id}.pdf"
        if output.exists():
            content = output.read_bytes()
        else:
            active = self.session or cast(DownloadSession, requests.Session())
            active.headers.update(
                {
                    "User-Agent": "QuantResearchAgent/0.1 filing research",
                    "Referer": "https://www.cninfo.com.cn/",
                }
            )
            try:
                response = active.get(record.url, timeout=self.timeout_seconds)
                response.raise_for_status()
                content = response.content
            except requests.RequestException as exc:
                raise FilingPDFError("Annual-report PDF download failed") from exc
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > self.maximum_bytes:
                raise FilingPDFError("Annual-report PDF exceeds maximum_bytes")
            if len(content) > self.maximum_bytes:
                raise FilingPDFError("Annual-report PDF exceeds maximum_bytes")
            if not content.startswith(b"%PDF-"):
                raise FilingPDFError("Downloaded filing is not a PDF")
            output.write_bytes(content)
        if not content.startswith(b"%PDF-"):
            raise FilingPDFError("Cached filing is not a PDF")
        return output.resolve(), hashlib.sha256(content).hexdigest()

    def extract(self, record: EvidenceRecord) -> FilingExtractionResult:
        path, digest = self._download(record)
        text_cache = path.with_suffix(".pages.json")
        page_texts: list[str]
        if text_cache.exists():
            try:
                cached = json.loads(text_cache.read_text(encoding="utf-8"))
                if cached.get("sha256") != digest:
                    raise ValueError("cached page text belongs to another PDF")
                page_texts = [str(value) for value in cached["page_texts"]]
            except (OSError, ValueError, TypeError, KeyError) as exc:
                raise FilingPDFError(
                    "Annual-report page-text cache is invalid"
                ) from exc
        else:
            try:
                reader = PdfReader(path)
                if reader.is_encrypted and reader.decrypt("") == 0:
                    raise FilingPDFError("Annual-report PDF is encrypted")
                page_texts = [
                    _normalise_text(page.extract_text() or "") for page in reader.pages
                ]
                text_cache.write_text(
                    json.dumps(
                        {"sha256": digest, "page_texts": page_texts},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except FilingPDFError:
                raise
            except Exception as exc:
                raise FilingPDFError("Annual-report PDF extraction failed") from exc
        total_characters = sum(len(text) for text in page_texts)
        if total_characters < 1000:
            raise FilingPDFError(
                "Annual-report PDF contains too little extractable text"
            )

        sections: list[FilingPageSection] = []
        evidence: list[EvidenceRecord] = []
        retrieved = datetime.now(UTC)
        for topic, keywords in self.topic_keywords.items():
            scored = []
            for page_index, text in enumerate(page_texts):
                matched = tuple(keyword for keyword in keywords if keyword in text)
                if not matched:
                    continue
                score = float(sum(text.count(keyword) for keyword in matched))
                if topic == FilingSectionTopic.BUSINESS_MODEL and (
                    "本集团主要从事" in text or "报告期内公司从事的主要业务" in text
                ):
                    score += 10
                if topic == FilingSectionTopic.MANAGEMENT_DISCUSSION and (
                    "第三节 管理层讨论与分析" in text
                ):
                    score += 8
                if topic == FilingSectionTopic.CASH_FLOW and (
                    "经营活动产生的现金流量净额同比" in text
                ):
                    score += 8
                if page_index < 15 and "目录" in text:
                    score -= 3
                # Opening notices and the table of contents often repeat section
                # headings without containing substantive disclosure.  Keep them
                # searchable, but rank them below the actual discussion pages.
                if page_index < 10 and ("重要提示" in text or "备查文件目录" in text):
                    score -= 12
                score += min(len(text) / 5000, 1)
                scored.append((score, page_index, text, matched))
            for _, page_index, text, matched in sorted(scored, reverse=True)[
                : self.pages_per_topic
            ]:
                page_number = page_index + 1
                evidence_id = f"{record.evidence_id}-P{page_number:03d}-{topic.value}"
                snippet = _excerpt(text, matched)
                if len(snippet) < 40:
                    continue
                sections.append(
                    FilingPageSection(
                        evidence_id=evidence_id,
                        topic=topic,
                        page_number=page_number,
                        matched_keywords=list(matched),
                        text=snippet,
                    )
                )
                evidence.append(
                    EvidenceRecord(
                        evidence_id=evidence_id,
                        source_type="annual_report_page",
                        title=f"{record.title} - page {page_number} - {topic.value}",
                        source_name=record.source_name,
                        url=record.url,
                        document_id=record.document_id,
                        published_at=record.published_at,
                        retrieved_at=retrieved,
                        page_number=page_number,
                        summary=(
                            "Page selected by deterministic keyword matching for "
                            + topic.value
                            + "."
                        ),
                        content_hash=digest,
                    )
                )
        found_topics = {item.topic for item in sections}
        missing_topics = [
            topic.value for topic in self.topic_keywords if topic not in found_topics
        ]
        if not sections:
            raise FilingPDFError("No target annual-report sections were located")
        return FilingExtractionResult(
            source_evidence_id=record.evidence_id,
            title=record.title,
            source_url=cast(str, record.url),
            local_path=str(path),
            sha256=digest,
            page_count=len(page_texts),
            extracted_characters=total_characters,
            sections=sections,
            page_evidence=evidence,
            warnings=(
                ["Target sections not located: " + ", ".join(missing_topics)]
                if missing_topics
                else []
            ),
        )
