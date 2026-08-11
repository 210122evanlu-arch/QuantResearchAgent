"""Structured output produced by the research manager node."""

from pydantic import BaseModel, Field, model_validator

from schemas.common import ResearchHypothesis
from schemas.enums import ResearchType


class ResearchPlan(BaseModel):
    research_question: str
    research_objective: str
    research_type: ResearchType
    hypotheses: list[ResearchHypothesis] = Field(min_length=1)
    methodology: str
    required_data: list[str] = Field(min_length=1)
    evaluation_metrics: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def hypothesis_ids_are_unique(self) -> "ResearchPlan":
        ids = [hypothesis.hypothesis_id for hypothesis in self.hypotheses]
        if len(ids) != len(set(ids)):
            raise ValueError("hypothesis_id values must be unique")
        return self
