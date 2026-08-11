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
from schemas.events import EventAnalysisRequest, EventIntelligenceResult, ResearchEvent
from schemas.experiment import ExperimentResult
from schemas.literature import RetrievedPaper
from schemas.model_design import ModelDesign
from schemas.platform import (
    AnalysisArtifact,
    AnalysisBundle,
    EvidenceRecord,
    ResearchFinding,
    ResearchRequest,
    WorkflowSelection,
)
from schemas.report import FinalReport
from schemas.research_analysis import ResearchAnalysis
from schemas.research_plan import ResearchPlan
from schemas.review import ReviewResult
from schemas.state import ResearchState

__all__ = [
    "AnalysisArtifact",
    "AnalysisBundle",
    "ChallengerCase",
    "DataProfile",
    "DebateArgument",
    "DebateGateResult",
    "DebateResult",
    "DebateRound",
    "EventAnalysisRequest",
    "EventIntelligenceResult",
    "EvidenceRecord",
    "ExperimentResult",
    "FinalReport",
    "ModelDesign",
    "ModeratorAssessment",
    "ProponentCase",
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
