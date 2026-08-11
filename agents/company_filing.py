"""Evidence-constrained LLM interpretation of extracted annual-report pages."""

import json

from llm.protocol import StructuredLLM
from schemas.company_filing import CompanyFilingAnalysis, FilingExtractionResult

SYSTEM_PROMPT = """You are a sell-side company research analyst. Analyse only the supplied annual-report page extracts. Return concise Chinese research judgments, not generic descriptions. Every finding must cite one or more supplied page evidence IDs. Distinguish disclosed facts from analyst interpretation, do not invent financial values, market shares, customers, strategies, or risks. Cover business model, competitive position, management priorities, segment or operating signals, cash-flow observations, and risk factors. Put missing context in limitations."""


def analyse_company_filing(
    extraction: FilingExtractionResult,
    llm: StructuredLLM,
) -> CompanyFilingAnalysis:
    payload = {
        "filing": {
            "title": extraction.title,
            "sha256": extraction.sha256,
            "page_count": extraction.page_count,
        },
        "page_extracts": [
            {
                "evidence_id": item.evidence_id,
                "topic": item.topic.value,
                "page_number": item.page_number,
                "matched_keywords": item.matched_keywords,
                "text": item.text,
            }
            for item in extraction.sections
        ],
    }
    result = llm.generate(
        schema=CompanyFilingAnalysis,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=json.dumps(payload, ensure_ascii=False, indent=2),
        node_name="company_filing_analysis",
    )
    known = {item.evidence_id for item in extraction.sections}
    referenced = {
        evidence_id
        for finding in result.findings
        for evidence_id in finding.evidence_ids
    }
    if missing := referenced - known:
        raise ValueError(
            "filing analysis references unknown page evidence_ids: "
            + ", ".join(sorted(missing))
        )
    return result
