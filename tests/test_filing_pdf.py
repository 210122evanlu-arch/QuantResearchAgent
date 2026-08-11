from datetime import UTC, date, datetime
from pathlib import Path
from typing import ClassVar

import pytest

import data_sources.filing_pdf as filing_module
from agents.company_filing import analyse_company_filing
from data_sources.filing_pdf import (
    FilingPDFError,
    FilingPDFExtractor,
    select_latest_annual_report,
)
from llm.fake import FakeStructuredLLM
from schemas.company_filing import CompanyFilingAnalysis, FilingSectionTopic
from schemas.platform import EvidenceRecord


def _record(title="2024年年度报告", identifier="ANNUAL-1"):
    return EvidenceRecord(
        evidence_id=identifier,
        source_type="company_announcement",
        title=title,
        source_name="CNInfo fixture",
        url="https://example.test/report.pdf",
        document_id="123",
        published_at=datetime(2025, 3, 30, tzinfo=UTC),
        retrieved_at=datetime(2025, 4, 1, tzinfo=UTC),
        summary="Annual report fixture.",
    )


class FakeResponse:
    content = b"%PDF-1.7 fixture"
    headers: ClassVar[dict[str, str]] = {"Content-Length": str(len(content))}

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.headers = {}

    def get(self, url, **kwargs):
        return FakeResponse()


class FakePage:
    def __init__(self, text) -> None:
        self.text = text

    def extract_text(self):
        return self.text


class FakeReader:
    is_encrypted = False

    def __init__(self, _path) -> None:
        self.pages = [
            FakePage(
                "公司主要业务及经营模式。公司主营业务包括产品研发、生产和销售。" * 20
            ),
            FakePage("管理层讨论与分析。报告期内公司经营情况和管理层重点工作。" * 20),
            FakePage("分行业、分产品、分地区的营业收入构成如下。" * 20),
            FakePage("经营活动产生的现金流量和现金及现金等价物变动。" * 20),
            FakePage("公司可能面对的风险包括市场风险、供应链风险和汇率风险。" * 20),
        ]


def test_selects_full_annual_report_and_rejects_abstract() -> None:
    selected = select_latest_annual_report(
        [_record("2024年年度报告摘要", "ABSTRACT"), _record()],
        date(2025, 6, 30),
    )
    assert selected.evidence_id == "ANNUAL-1"
    with pytest.raises(FilingPDFError, match="No full annual-report"):
        select_latest_annual_report([_record("2024年年度报告摘要")], date(2025, 6, 30))


def test_extracts_page_level_filing_evidence(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(filing_module, "PdfReader", FakeReader)
    result = FilingPDFExtractor(
        cache_directory=tmp_path,
        session=FakeSession(),
        maximum_bytes=1_000_000,
        pages_per_topic=1,
    ).extract(_record())

    assert result.page_count == 5
    assert {item.topic for item in result.sections} == set(FilingSectionTopic)
    assert all(
        item.page_number == index for index, item in enumerate(result.sections, 1)
    )
    assert all(item.content_hash == result.sha256 for item in result.page_evidence)


def test_filing_llm_must_cite_extracted_page_ids(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(filing_module, "PdfReader", FakeReader)
    extraction = FilingPDFExtractor(
        cache_directory=tmp_path,
        session=FakeSession(),
        maximum_bytes=1_000_000,
        pages_per_topic=1,
    ).extract(_record())
    evidence_ids = [item.evidence_id for item in extraction.sections]
    response = {
        "executive_summary": "公司具备一体化业务结构，但仍需监控现金流与市场风险。",
        "business_model": "公司通过研发、生产和销售形成业务闭环。",
        "competitive_position": "竞争地位取决于研发转化和规模效率。",
        "management_priorities": ["提升经营效率"],
        "findings": [
            {
                "category": topic.value,
                "statement": f"关于{topic.value}的披露已定位。",
                "implication": "需要持续跟踪。",
                "evidence_ids": [evidence_id],
                "confidence": 0.8,
            }
            for topic, evidence_id in zip(FilingSectionTopic, evidence_ids, strict=True)
        ],
        "risks": ["市场风险"],
        "limitations": ["仅使用候选页面"],
    }
    result = analyse_company_filing(
        extraction, FakeStructuredLLM({CompanyFilingAnalysis: response})
    )
    assert len(result.findings) == 5

    response["findings"][0]["evidence_ids"] = ["UNKNOWN"]
    with pytest.raises(ValueError, match="unknown page evidence_ids"):
        analyse_company_filing(
            extraction, FakeStructuredLLM({CompanyFilingAnalysis: response})
        )
