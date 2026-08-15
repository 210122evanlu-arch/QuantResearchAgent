"""Enumerations used by structured research outputs and graph routing."""

from enum import StrEnum


class ResearchType(StrEnum):
    CROSS_SECTIONAL = "cross_sectional"
    TIME_SERIES = "time_series"
    PANEL = "panel"
    EVENT_STUDY = "event_study"
    PORTFOLIO_SORT = "portfolio_sort"
    BACKTEST = "backtest"


class ExpectedDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NONLINEAR = "nonlinear"
    UNCERTAIN = "uncertain"


class VariableRole(StrEnum):
    DEPENDENT = "dependent"
    INDEPENDENT = "independent"
    CONTROL = "control"


class Estimator(StrEnum):
    OLS = "ols"
    FAMA_MACBETH = "fama_macbeth"
    PORTFOLIO_SORT = "portfolio_sort"
    BACKTEST = "backtest"


class DataFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    NEED_REVISION = "need_revision"


class ProblemType(StrEnum):
    MODEL_ISSUE = "model_issue"
    DATA_ISSUE = "data_issue"
    EXPERIMENT_ISSUE = "experiment_issue"


class RevisionTarget(StrEnum):
    MODEL_DESIGN = "model_design"
    DATA_PREPARATION = "data_preparation"
    EXPERIMENT = "experiment"


class IssueSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewIssueOrigin(StrEnum):
    POLICY = "policy"
    REVIEWER = "reviewer"


class TaskType(StrEnum):
    """Top-level institutional research and advisory service lines."""

    COMPANY_RESEARCH = "company_research"
    INDUSTRY_RESEARCH = "industry_research"
    QUANT_RESEARCH = "quant_research"
    MARKET_STRATEGY = "market_strategy"
    EVENT_STUDY = "event_study"
    CORPORATE_ADVISORY = "corporate_advisory"


class AnalysisMethod(StrEnum):
    """Reusable analysis capabilities selected after intake."""

    FINANCIAL_STATEMENT_ANALYSIS = "financial_statement_analysis"
    RELATIVE_VALUATION = "relative_valuation"
    DCF_VALUATION = "dcf_valuation"
    PEER_BENCHMARKING = "peer_benchmarking"
    INDUSTRY_ANALYSIS = "industry_analysis"
    MARKET_REGIME_ANALYSIS = "market_regime_analysis"
    EVENT_STUDY = "event_study"
    REGRESSION = "regression"
    PORTFOLIO_BACKTEST = "portfolio_backtest"
    SCENARIO_ANALYSIS = "scenario_analysis"
    STRATEGIC_DIAGNOSIS = "strategic_diagnosis"
    FINANCIAL_ANOMALY_SCREENING = "financial_anomaly_screening"


class ReportAudience(StrEnum):
    RESEARCH_TEAM = "research_team"
    INVESTMENT_COMMITTEE = "investment_committee"
    MANAGEMENT = "management"
    RISK_TEAM = "risk_team"
    CLIENT = "client"


class ReportDepth(StrEnum):
    BRIEF = "brief"
    STANDARD = "standard"
    DEEP_DIVE = "deep_dive"


class EvidenceStatus(StrEnum):
    VERIFIED = "verified"
    INFERRED = "inferred"
    INSUFFICIENT = "insufficient_evidence"


class DebatePosition(StrEnum):
    SUPPORT = "support"
    CHALLENGE = "challenge"


class ModeratorDecision(StrEnum):
    CONTINUE = "continue"
    CONCLUDE = "conclude"


class DebateGateDecision(StrEnum):
    ENTER_DEBATE = "enter_debate"
    SKIP_DEBATE = "skip_debate"


class DebateTrigger(StrEnum):
    USER_REQUESTED = "user_requested"
    MATERIAL_ADVISORY = "material_advisory"
    LOW_CONFIDENCE = "low_confidence"
    UNVERIFIED_FINDING = "unverified_finding"
    EVIDENCE_CONFLICT = "evidence_conflict"
    ANALYSIS_WARNING = "analysis_warning"


class FinancialRiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class FinancialRiskCategory(StrEnum):
    EARNINGS_QUALITY = "earnings_quality"
    WORKING_CAPITAL = "working_capital"
    MARGIN = "margin"
    LIQUIDITY = "liquidity"
    GOVERNANCE = "governance"
    REGULATORY = "regulatory"


class QualityReviewCategory(StrEnum):
    EVIDENCE = "evidence"
    DATA = "data"
    MODEL = "model"
    REPORT = "report"
    AI_GOVERNANCE = "ai_governance"


class QualityReviewTarget(StrEnum):
    EVIDENCE_COLLECTION = "evidence_collection"
    FINANCIAL_RISK_ANALYSIS = "financial_risk_analysis"
    DRAFT_REPORT = "draft_report"


class QualityReviewDecision(StrEnum):
    PASSED = "passed"
    REMEDIATION_REQUIRED = "remediation_required"
    BLOCKED = "blocked"


class SignOffStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
