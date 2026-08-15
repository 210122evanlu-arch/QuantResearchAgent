"""Structured output contracts shared by the research workflow."""

from schemas.data_profile import DataProfile
from schemas.debate import (
    ChallengerCase,
    DebateArgument,
    DebateGateResult,
    DebateResult,
    DebateRound,
    ModeratorAssessment,
    ProponentCase,
)
from schemas.event_study import (
    EventStudyDesign,
    EventStudyReport,
    EventStudyResult,
    EventStudyReviewResult,
)
from schemas.events import EventAnalysisRequest, EventIntelligenceResult, ResearchEvent
from schemas.experiment import ExperimentResult
from schemas.financial_risk import (
    AuditTrail,
    FinancialRiskInput,
    FinancialRiskScorecard,
    FinancialRiskSignal,
    HumanSignOff,
)
from schemas.industry_research import (
    IndustryResearchReport,
    IndustryResearchReviewResult,
    IndustryScenario,
)
from schemas.literature import RetrievedPaper
from schemas.market_strategy import (
    MarketRegimeAssessment,
    MarketSignalSnapshot,
    MarketStrategyReport,
    MarketStrategyReviewResult,
)
from schemas.model_design import ModelDesign
from schemas.platform import (
    AnalysisArtifact,
    AnalysisBundle,
    EvidenceRecord,
    ResearchFinding,
    ResearchRequest,
    WorkflowSelection,
)
from schemas.quality_review import QualityReviewResult
from schemas.report import FinalReport
from schemas.research_analysis import ResearchAnalysis
from schemas.research_plan import ResearchPlan
from schemas.review import ReviewResult
from schemas.state import ResearchState
from schemas.valuation import DCFInput, DCFResult

__all__ = [
    "AnalysisArtifact",
    "AnalysisBundle",
    "AuditTrail",
    "ChallengerCase",
    "DCFInput",
    "DCFResult",
    "DataProfile",
    "DebateArgument",
    "DebateGateResult",
    "DebateResult",
    "DebateRound",
    "EventAnalysisRequest",
    "EventIntelligenceResult",
    "EventStudyDesign",
    "EventStudyReport",
    "EventStudyResult",
    "EventStudyReviewResult",
    "EvidenceRecord",
    "ExperimentResult",
    "FinalReport",
    "FinancialRiskInput",
    "FinancialRiskScorecard",
    "FinancialRiskSignal",
    "HumanSignOff",
    "IndustryResearchReport",
    "IndustryResearchReviewResult",
    "IndustryScenario",
    "MarketRegimeAssessment",
    "MarketSignalSnapshot",
    "MarketStrategyReport",
    "MarketStrategyReviewResult",
    "ModelDesign",
    "ModeratorAssessment",
    "ProponentCase",
    "QualityReviewResult",
    "ResearchAnalysis",
    "ResearchEvent",
    "ResearchFinding",
    "ResearchPlan",
    "ResearchRequest",
    "ResearchState",
    "RetrievedPaper",
    "ReviewResult",
    "WorkflowSelection",
]
