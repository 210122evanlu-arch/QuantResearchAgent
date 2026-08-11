"""Interfaces and offline doubles for literature retrieval."""

from typing import Protocol

from schemas.literature import RetrievedPaper
from schemas.research_plan import ResearchPlan


class LiteratureRetriever(Protocol):
    def search(self, plan: ResearchPlan) -> list[RetrievedPaper]:
        """Return verified metadata candidates for one research plan."""


class StaticLiteratureRetriever:
    """Deterministic retriever used by offline workflow tests."""

    def __init__(self, papers: list[RetrievedPaper]) -> None:
        self._papers = list(papers)
        self.calls: list[str] = []

    def search(self, plan: ResearchPlan) -> list[RetrievedPaper]:
        self.calls.append(plan.research_question)
        return list(self._papers)
