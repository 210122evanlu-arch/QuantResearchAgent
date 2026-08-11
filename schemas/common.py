"""Reusable schema components shared by multiple research stages."""

from pydantic import BaseModel

from schemas.enums import ExpectedDirection, VariableRole


class ResearchHypothesis(BaseModel):
    hypothesis_id: str
    statement: str
    dependent_variable: str
    independent_variable: str
    expected_direction: ExpectedDirection
    rationale: str


class PaperReference(BaseModel):
    title: str
    authors: list[str]
    year: int
    source: str
    key_finding: str
    relevance: str
    doi_or_url: str | None = None


class VariableDefinition(BaseModel):
    name: str
    role: VariableRole
    definition: str
    calculation: str | None = None
    expected_sign: ExpectedDirection = ExpectedDirection.UNCERTAIN
