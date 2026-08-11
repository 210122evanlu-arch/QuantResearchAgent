"""Deterministic company-analysis engines backed by public-data packages."""

from collections.abc import Mapping
from statistics import median
from typing import Any

from analysis_engines.router import AnalysisEngineRegistry
from schemas.company_data import CompanyPublicDataPackage
from schemas.company_filing import CompanyFilingAnalysis, FilingExtractionResult
from schemas.enums import AnalysisMethod, EvidenceStatus
from schemas.platform import AnalysisArtifact, ResearchFinding
from schemas.valuation import DCFInput, DCFSensitivityConfig
from tools.valuation import run_dcf


def _package(value: Any) -> CompanyPublicDataPackage:
    if isinstance(value, CompanyPublicDataPackage):
        return value
    return CompanyPublicDataPackage.model_validate(value)


def _context(context: Mapping[str, Any]):
    target = _package(context["company_data"])
    peers = [_package(item) for item in context.get("peer_company_data", [])]
    return target, peers


def _metrics(package: CompanyPublicDataPackage) -> dict[str, float]:
    return {
        item.name: item.value
        for item in [*package.market_metrics, *package.financial_metrics]
    }


def _evidence_by_type(package: CompanyPublicDataPackage, prefix: str) -> list[str]:
    return [
        item.evidence_id
        for item in package.evidence
        if item.source_type.startswith(prefix)
    ]


def financial_statement_engine(context: Mapping[str, Any]) -> AnalysisArtifact:
    target, _ = _context(context)
    metrics = _metrics(target)
    evidence_ids = _evidence_by_type(target, "financial_")
    selected = {
        key: value
        for key, value in metrics.items()
        if any(
            token in key.casefold()
            for token in ("roe", "margin", "yoy", "liability", "cfo", "revenue")
        )
    }
    status = (
        EvidenceStatus.VERIFIED
        if evidence_ids and selected
        else EvidenceStatus.INSUFFICIENT
    )
    summary = (
        "Latest published BaoStock financial indicators were selected using publication dates."
        if status == EvidenceStatus.VERIFIED
        else "No sufficiently complete published financial indicators were available."
    )
    return AnalysisArtifact(
        method=AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS,
        title="Financial statement quality",
        summary=summary,
        findings=[
            ResearchFinding(
                finding_id="COMPANY-FIN-1",
                statement=summary,
                implication="Profitability, growth, leverage, and cash conversion require joint interpretation.",
                evidence_ids=evidence_ids,
                status=status,
                confidence=0.85 if status == EvidenceStatus.VERIFIED else 0.2,
            )
        ],
        metrics=selected,
        limitations=[
            "BaoStock indicators do not replace line-item verification against the filing PDF."
        ],
    )


def strategic_diagnosis_engine(context: Mapping[str, Any]) -> AnalysisArtifact:
    target, _ = _context(context)
    filing_analysis_value = context.get("company_filing_analysis")
    filing_extraction_value = context.get("company_filing_extraction")
    if filing_analysis_value is not None and filing_extraction_value is not None:
        analysis = (
            filing_analysis_value
            if isinstance(filing_analysis_value, CompanyFilingAnalysis)
            else CompanyFilingAnalysis.model_validate(filing_analysis_value)
        )
        extraction = (
            filing_extraction_value
            if isinstance(filing_extraction_value, FilingExtractionResult)
            else FilingExtractionResult.model_validate(filing_extraction_value)
        )
        return AnalysisArtifact(
            method=AnalysisMethod.STRATEGIC_DIAGNOSIS,
            title="Business and competitive diagnosis",
            summary=analysis.executive_summary,
            findings=[
                ResearchFinding(
                    finding_id=f"COMPANY-FILING-{index}",
                    statement=finding.statement,
                    implication=finding.implication,
                    evidence_ids=finding.evidence_ids,
                    status=EvidenceStatus.INFERRED,
                    confidence=finding.confidence,
                )
                for index, finding in enumerate(analysis.findings, start=1)
            ],
            metrics={
                "annual_report_pages": extraction.page_count,
                "extracted_characters": extraction.extracted_characters,
                "located_sections": len(extraction.sections),
            },
            assumptions=["LLM interpretation is restricted to extracted filing pages."],
            limitations=[*analysis.limitations, *extraction.warnings],
        )
    announcements = _evidence_by_type(target, "company_announcement")
    if announcements:
        summary = (
            f"{len(announcements)} official disclosure titles were collected for "
            "business-event screening; full-text interpretation remains pending."
        )
        status = EvidenceStatus.INSUFFICIENT
        confidence = 0.4
    else:
        summary = (
            "No official disclosure evidence was available for business diagnosis."
        )
        status = EvidenceStatus.INSUFFICIENT
        confidence = 0.1
    return AnalysisArtifact(
        method=AnalysisMethod.STRATEGIC_DIAGNOSIS,
        title="Business and competitive diagnosis",
        summary=summary,
        findings=[
            ResearchFinding(
                finding_id="COMPANY-STRATEGY-1",
                statement=summary,
                implication="Business conclusions must wait for filing full-text extraction and source triangulation.",
                evidence_ids=announcements,
                status=status,
                confidence=confidence,
            )
        ],
        metrics={"official_disclosure_count": len(announcements)},
        limitations=["Announcement-title screening is not full-document analysis."],
    )


def relative_valuation_engine(context: Mapping[str, Any]) -> AnalysisArtifact:
    target, peers = _context(context)
    target_metrics = _metrics(target)
    comparable: dict[str, Any] = {}
    for multiple in ("pe_ttm", "pb_mrq", "ps_ttm"):
        peer_values = [
            value
            for peer in peers
            if (value := _metrics(peer).get(multiple)) is not None and value > 0
        ]
        if multiple in target_metrics and peer_values:
            comparable[multiple] = {
                "target": target_metrics[multiple],
                "peer_median": median(peer_values),
                "premium_discount": target_metrics[multiple] / median(peer_values) - 1,
            }
    evidence_ids = [
        *_evidence_by_type(target, "market_data"),
        *(
            evidence_id
            for peer in peers
            for evidence_id in _evidence_by_type(peer, "market_data")
        ),
    ]
    status = EvidenceStatus.VERIFIED if comparable else EvidenceStatus.INSUFFICIENT
    summary = (
        "Target valuation multiples were compared with the median of the supplied peers."
        if comparable
        else "Relative valuation could not be completed because comparable peer multiples were unavailable."
    )
    return AnalysisArtifact(
        method=AnalysisMethod.RELATIVE_VALUATION,
        title="Relative valuation",
        summary=summary,
        findings=[
            ResearchFinding(
                finding_id="COMPANY-VAL-1",
                statement=summary,
                implication="Premiums or discounts are descriptive and require earnings-quality and growth adjustment.",
                evidence_ids=evidence_ids if comparable else [],
                status=status,
                confidence=0.8 if comparable else 0.2,
            )
        ],
        metrics=comparable,
        assumptions=[
            "Peer accounting definitions and observation dates are comparable."
        ],
        limitations=["Relative valuation is not a standalone target-price model."],
    )


def dcf_valuation_engine(context: Mapping[str, Any]) -> AnalysisArtifact:
    value = context.get("dcf_input")
    if value is None:
        return AnalysisArtifact(
            method=AnalysisMethod.DCF_VALUATION,
            title="Discounted cash-flow valuation",
            summary="DCF was requested but no forecast assumptions were supplied.",
            findings=[
                ResearchFinding(
                    finding_id="COMPANY-DCF-1",
                    statement="DCF inputs are incomplete.",
                    implication="A valuation conclusion cannot be produced without explicit cash-flow assumptions.",
                    status=EvidenceStatus.INSUFFICIENT,
                    confidence=0.0,
                )
            ],
            limitations=[
                "No implicit forecasts are generated by the valuation engine."
            ],
        )
    inputs = value if isinstance(value, DCFInput) else DCFInput.model_validate(value)
    sensitivity_value = context.get("dcf_sensitivity")
    sensitivity = (
        sensitivity_value
        if isinstance(sensitivity_value, DCFSensitivityConfig)
        else DCFSensitivityConfig.model_validate(sensitivity_value or {})
    )
    result = run_dcf(inputs, sensitivity)
    evidence_ids = list(context.get("dcf_evidence_ids", []))
    return AnalysisArtifact(
        method=AnalysisMethod.DCF_VALUATION,
        title="Discounted cash-flow valuation",
        summary=(
            f"Base-case DCF value per share is {result.value_per_share:.2f} "
            f"{result.currency}; terminal value contributes "
            f"{result.terminal_value_share:.1%} of enterprise value."
        ),
        findings=[
            ResearchFinding(
                finding_id="COMPANY-DCF-1",
                statement="DCF output is derived from the supplied forecast scenario.",
                implication="The sensitivity range, not only the base case, should inform valuation review.",
                evidence_ids=evidence_ids,
                status=EvidenceStatus.INFERRED,
                confidence=0.7,
            )
        ],
        metrics={
            "enterprise_value": result.enterprise_value,
            "equity_value": result.equity_value,
            "value_per_share": result.value_per_share,
            "terminal_value_share": result.terminal_value_share,
            "sensitivity_low": min(item.value_per_share for item in result.sensitivity),
            "sensitivity_high": max(
                item.value_per_share for item in result.sensitivity
            ),
            "sensitivity_cells": len(result.sensitivity),
        },
        assumptions=[
            f"Discount rate={inputs.discount_rate:.2%}",
            f"Terminal growth={inputs.terminal_growth_rate:.2%}",
        ],
        limitations=[
            "DCF is assumption-driven and is not a target-price recommendation.",
            *result.warnings,
        ],
    )


def peer_benchmarking_engine(context: Mapping[str, Any]) -> AnalysisArtifact:
    target, peers = _context(context)
    target_metrics = _metrics(target)
    common = (
        sorted(
            set(target_metrics).intersection(*(set(_metrics(peer)) for peer in peers))
        )
        if peers
        else []
    )
    market_common = [
        name
        for name in common
        if name
        in {"one_year_return", "annualized_volatility", "pe_ttm", "pb_mrq", "ps_ttm"}
    ]
    evidence_ids = [
        *_evidence_by_type(target, "market_data"),
        *(
            evidence_id
            for peer in peers
            for evidence_id in _evidence_by_type(peer, "market_data")
        ),
    ]
    status = (
        EvidenceStatus.VERIFIED
        if peers and market_common
        else EvidenceStatus.INSUFFICIENT
    )
    summary = (
        f"{target.company_name} was benchmarked against {len(peers)} peers on "
        f"{len(market_common)} aligned market indicators."
        if status == EvidenceStatus.VERIFIED
        else "No sufficiently aligned peer dataset was supplied."
    )
    return AnalysisArtifact(
        method=AnalysisMethod.PEER_BENCHMARKING,
        title="Peer benchmark",
        summary=summary,
        findings=[
            ResearchFinding(
                finding_id="COMPANY-PEER-1",
                statement=summary,
                implication="Peer rankings should be refreshed on synchronized reporting dates.",
                evidence_ids=evidence_ids if status == EvidenceStatus.VERIFIED else [],
                status=status,
                confidence=0.8 if status == EvidenceStatus.VERIFIED else 0.2,
            )
        ],
        metrics={"peer_count": len(peers), "aligned_metric_count": len(market_common)},
        limitations=[
            "Industry and business-model comparability require analyst review."
        ],
    )


def create_company_analysis_registry() -> AnalysisEngineRegistry:
    registry = AnalysisEngineRegistry()
    registry.register(
        AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS,
        financial_statement_engine,
    )
    registry.register(AnalysisMethod.STRATEGIC_DIAGNOSIS, strategic_diagnosis_engine)
    registry.register(AnalysisMethod.RELATIVE_VALUATION, relative_valuation_engine)
    registry.register(AnalysisMethod.DCF_VALUATION, dcf_valuation_engine)
    registry.register(AnalysisMethod.PEER_BENCHMARKING, peer_benchmarking_engine)
    return registry


def build_company_analysis_context(
    target: CompanyPublicDataPackage,
    peers: list[CompanyPublicDataPackage] | None = None,
    *,
    filing_extraction: FilingExtractionResult | None = None,
    filing_analysis: CompanyFilingAnalysis | None = None,
    dcf_input: DCFInput | None = None,
    dcf_sensitivity: DCFSensitivityConfig | None = None,
    dcf_evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    peer_packages = peers or []
    evidence = []
    seen = set()
    for package in [target, *peer_packages]:
        for record in package.evidence:
            if record.evidence_id not in seen:
                evidence.append(record)
                seen.add(record.evidence_id)
    if filing_extraction is not None:
        for record in filing_extraction.page_evidence:
            if record.evidence_id not in seen:
                evidence.append(record)
                seen.add(record.evidence_id)
    return {
        "company_data": target,
        "peer_company_data": peer_packages,
        "evidence": evidence,
        "company_filing_extraction": filing_extraction,
        "company_filing_analysis": filing_analysis,
        "dcf_input": dcf_input,
        "dcf_sensitivity": dcf_sensitivity,
        "dcf_evidence_ids": dcf_evidence_ids or [],
        "warnings": [
            warning
            for package in [target, *peer_packages]
            for warning in package.warnings
        ],
    }
