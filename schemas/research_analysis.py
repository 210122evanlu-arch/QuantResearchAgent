"""Literature and financial-theory analysis output."""

from pydantic import BaseModel, Field

from schemas.common import PaperReference, ResearchHypothesis


class ResearchAnalysis(BaseModel):
    related_theories: list[str]
    existing_models: list[str]
    key_papers: list[PaperReference] = Field(min_length=1)
    theoretical_mechanism: str
    research_gap: str
    refined_hypotheses: list[ResearchHypothesis]
