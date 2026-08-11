"""Contracts for market-regime strategy, scenarios, and committee review."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from schemas.enums import IssueSeverity, ReviewDecision


class MarketRegime(StrEnum):
    RISK_ON = "risk_on"
    BALANCED = "balanced"
    DEFENSIVE = "defensive"
    TRANSITION = "transition"


class StrategyStance(StrEnum):
    OVERWEIGHT = "overweight"
    NEUTRAL = "neutral"
    UNDERWEIGHT = "underweight"


class ConvictionLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MarketStrategyRevisionTarget(StrEnum):
    ANALYSIS = "market_analysis"
    SYNTHESIS = "market_synthesis"


class MarketSignalSnapshot(BaseModel):
    growth_momentum: float = Field(ge=-1, le=1)
    liquidity_support: float = Field(ge=-1, le=1)
    valuation_attractiveness: float = Field(ge=-1, le=1)
    earnings_momentum: float = Field(ge=-1, le=1)
    risk_appetite: float = Field(ge=-1, le=1)
    provenance: str = Field(min_length=1)


class MarketRegimeAssessment(BaseModel):
    score: float = Field(ge=-1, le=1)
    regime: MarketRegime
    signal_contributions: dict[str, float] = Field(min_length=5)
    rationale: str = Field(min_length=1)


class StrategyView(BaseModel):
    segment: str = Field(min_length=1)
    stance: StrategyStance
    rationale: str = Field(min_length=1)
    catalysts: list[str] = Field(min_length=1)
    risks: list[str] = Field(min_length=1)


class MarketScenario(BaseModel):
    name: str = Field(min_length=1)
    probability: float = Field(ge=0, le=1)
    triggers: list[str] = Field(min_length=1)
    market_implications: list[str] = Field(min_length=1)
    preferred_exposures: list[str] = Field(min_length=1)


class MarketStrategyReport(BaseModel):
    title: str = Field(min_length=1)
    market_name: str = Field(min_length=1)
    as_of_date: date
    horizon: str = Field(min_length=1)
    regime: MarketRegime
    conviction: ConvictionLevel
    partner_view: str = Field(min_length=1)
    key_signals: dict[str, str] = Field(min_length=1)
    macro_environment: str = Field(min_length=1)
    liquidity_and_policy: str = Field(min_length=1)
    valuation_and_earnings: str = Field(min_length=1)
    style_views: list[StrategyView] = Field(min_length=1)
    sector_views: list[StrategyView] = Field(min_length=1)
    scenarios: list[MarketScenario] = Field(min_length=3)
    portfolio_implications: list[str] = Field(min_length=1)
    monitoring_indicators: list[str] = Field(min_length=1)
    risks: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    conclusion: str = Field(min_length=1)

    @model_validator(mode="after")
    def scenario_probabilities_sum_to_one(self) -> "MarketStrategyReport":
        total = sum(item.probability for item in self.scenarios)
        if abs(total - 1.0) > 1e-6:
            raise ValueError("market scenario probabilities must sum to one")
        return self


class MarketStrategyReviewIssue(BaseModel):
    severity: IssueSeverity
    description: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    target: MarketStrategyRevisionTarget
    blocking: bool = True


class MarketStrategyReviewResult(BaseModel):
    decision: ReviewDecision
    strengths: list[str] = Field(default_factory=list)
    issues: list[MarketStrategyReviewIssue] = Field(default_factory=list)
    revision_target: MarketStrategyRevisionTarget | None = None
    overall_assessment: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_review_route(self) -> "MarketStrategyReviewResult":
        blocking = [issue for issue in self.issues if issue.blocking]
        if self.decision == ReviewDecision.APPROVED:
            if blocking or self.revision_target is not None:
                raise ValueError("approved market strategy cannot require revision")
        else:
            if not blocking or self.revision_target is None:
                raise ValueError(
                    "need_revision market strategy requires a blocking issue and target"
                )
            if self.revision_target not in {issue.target for issue in blocking}:
                raise ValueError("revision_target must match a blocking issue target")
        return self
