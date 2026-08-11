"""Shared state passed through every node in the research graph."""

from typing import Any, TypedDict

from schemas.advisory import CompanyRiskProfile
from schemas.company_data import CompanyPublicDataPackage
from schemas.company_filing import CompanyFilingAnalysis, FilingExtractionResult
from schemas.company_research import (
    CompanyResearchReport,
    CompanyResearchReviewResult,
)
from schemas.data_profile import DataProfile
from schemas.debate import (
    ChallengerCase,
    DebateGateResult,
    DebateResult,
    DebateRound,
    ModeratorAssessment,
    ProponentCase,
)
from schemas.experiment import ExperimentResult
from schemas.industry_research import (
    IndustryResearchReport,
    IndustryResearchReviewResult,
)
from schemas.literature import RetrievedPaper
from schemas.model_design import ModelDesign
from schemas.platform import AnalysisBundle, ResearchRequest, WorkflowSelection
from schemas.report import FinalReport
from schemas.research_analysis import ResearchAnalysis
from schemas.research_plan import ResearchPlan
from schemas.review import ReviewResult


class ResearchState(TypedDict, total=False):
    request: ResearchRequest
    workflow_selection: WorkflowSelection
    analysis_context: dict[str, Any]
    analysis_bundle: AnalysisBundle
    risk_profile: CompanyRiskProfile
    company_research_report: CompanyResearchReport
    company_research_review: CompanyResearchReviewResult
    industry_research_report: IndustryResearchReport
    industry_research_review: IndustryResearchReviewResult
    company_data: CompanyPublicDataPackage
    peer_company_data: list[CompanyPublicDataPackage]
    company_filing_extraction: FilingExtractionResult
    company_filing_analysis: CompanyFilingAnalysis
    debate_gate_result: DebateGateResult
    proponent_case: ProponentCase
    challenger_case: ChallengerCase
    moderator_assessment: ModeratorAssessment
    debate_rounds: list[DebateRound]
    debate_round: int
    max_debate_rounds: int
    debate_limit_reached: bool
    debate_result: DebateResult
    research_question: str
    research_plan: ResearchPlan
    literature_candidates: list[RetrievedPaper]
    research_analysis: ResearchAnalysis
    model_design: ModelDesign
    data_profile: DataProfile
    experiment_result: ExperimentResult
    review_result: ReviewResult
    final_report: FinalReport
    report_markdown_path: str
    active_data_revision_index: int
    active_data_path: str
    data_revision_count: int

    current_stage: str
    revision_count: int
    max_revisions: int
    revision_limit_reached: bool
    errors: list[str]
