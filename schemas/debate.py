"""Structured contracts for evidence-grounded research debate."""

from pydantic import BaseModel, Field, model_validator

from schemas.enums import (
    DebateGateDecision,
    DebatePosition,
    DebateTrigger,
    ModeratorDecision,
)


class DebateGateResult(BaseModel):
    decision: DebateGateDecision
    triggers: list[DebateTrigger] = Field(default_factory=list)
    max_rounds: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def entered_debates_require_a_trigger(self) -> "DebateGateResult":
        if self.decision == DebateGateDecision.ENTER_DEBATE and not self.triggers:
            raise ValueError("enter_debate decisions require at least one trigger")
        return self


class DebateArgument(BaseModel):
    argument_id: str = Field(min_length=1)
    position: DebatePosition
    claim: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    challenges_argument_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ProponentCase(BaseModel):
    thesis: str = Field(min_length=1)
    arguments: list[DebateArgument] = Field(min_length=1)
    acknowledged_limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def arguments_are_supporting(self) -> "ProponentCase":
        if any(item.position != DebatePosition.SUPPORT for item in self.arguments):
            raise ValueError("proponent arguments must have position='support'")
        return self


class ChallengerCase(BaseModel):
    counter_thesis: str = Field(min_length=1)
    arguments: list[DebateArgument] = Field(min_length=1)
    requested_checks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def arguments_are_challenges(self) -> "ChallengerCase":
        if any(item.position != DebatePosition.CHALLENGE for item in self.arguments):
            raise ValueError("challenger arguments must have position='challenge'")
        return self


class ModeratorAssessment(BaseModel):
    decision: ModeratorDecision
    new_information_added: bool
    resolved_issues: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    consensus_findings: list[str] = Field(default_factory=list)
    disputed_findings: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
    synthesis: str = Field(min_length=1)

    @model_validator(mode="after")
    def continuation_requires_progress(self) -> "ModeratorAssessment":
        if self.decision == ModeratorDecision.CONTINUE:
            if not self.new_information_added:
                raise ValueError("continued debate must add new information")
            if not self.unresolved_issues:
                raise ValueError("continued debate must identify unresolved issues")
        return self


class DebateRound(BaseModel):
    round_number: int = Field(ge=1)
    proponent: ProponentCase
    challenger: ChallengerCase
    moderator: ModeratorAssessment


class DebateResult(BaseModel):
    rounds: list[DebateRound] = Field(min_length=1)
    consensus_findings: list[str] = Field(default_factory=list)
    disputed_findings: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    moderator_conclusion: str = Field(min_length=1)
    stopped_by_limit: bool
