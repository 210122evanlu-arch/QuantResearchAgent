"""Research Analysis node with source-constrained literature synthesis."""

import json
import re
from dataclasses import dataclass

from literature.protocol import LiteratureRetriever
from llm.protocol import StructuredLLM
from schemas.common import PaperReference
from schemas.literature import RetrievedPaper
from schemas.research_analysis import ResearchAnalysis
from schemas.state import ResearchState

_SYSTEM_PROMPT = """You are a literature and financial-theory research analyst.
Synthesize only verified literature supplied in literature_candidates, explain
the economic mechanism, identify a research gap, and refine the hypotheses.
Every key_papers entry must match a supplied candidate by title or DOI/URL.
Never invent a paper, author, DOI, URL, or empirical finding. If an abstract is
unavailable, explicitly state that full-text review is required."""
_SYSTEM_PROMPT += """
The refined_hypotheses list must contain exactly the same hypothesis_id values
as ResearchPlan.hypotheses, with no additions, deletions, or renamed IDs."""


class UnverifiedCitationError(ValueError):
    """Raised when generated analysis cites a paper outside the retrieved set."""


def _normalise_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _normalise_locator(value: str | None) -> str | None:
    if not value:
        return None
    normalised = value.strip().casefold().rstrip("/")
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalised.startswith(prefix):
            return normalised.removeprefix(prefix)
    return normalised


def _verified_reference(
    generated: PaperReference,
    candidates: list[RetrievedPaper],
) -> PaperReference:
    generated_locator = _normalise_locator(generated.doi_or_url)
    generated_title = _normalise_title(generated.title)

    matched = next(
        (
            candidate
            for candidate in candidates
            if generated_title == _normalise_title(candidate.title)
            or (
                generated_locator is not None
                and generated_locator
                in {
                    _normalise_locator(candidate.doi),
                    _normalise_locator(candidate.url),
                }
            )
        ),
        None,
    )
    if matched is None:
        raise UnverifiedCitationError(
            f"Research Analysis cited an unverified paper: {generated.title!r}"
        )

    key_finding = generated.key_finding
    if matched.abstract is None:
        key_finding = "Abstract unavailable; full-text review required."

    return generated.model_copy(
        update={
            "title": matched.title,
            "authors": matched.authors,
            "year": matched.year,
            "source": matched.journal,
            "doi_or_url": matched.url,
            "key_finding": key_finding,
        }
    )


@dataclass(frozen=True)
class ResearchAnalysisNode:
    """Retrieve metadata, then constrain synthesis to those candidates."""

    llm: StructuredLLM
    literature_retriever: LiteratureRetriever
    name: str = "research_analysis"
    output_key: str = "research_analysis"
    output_schema: type[ResearchAnalysis] = ResearchAnalysis
    input_keys: tuple[str, ...] = ("research_plan",)

    def __call__(self, state: ResearchState) -> dict:
        if "research_plan" not in state:
            from agents.base import NodeInputError

            raise NodeInputError(
                "Node 'research_analysis' is missing state fields: research_plan"
            )

        plan = state["research_plan"]
        candidates = self.literature_retriever.search(plan)
        if not candidates:
            raise UnverifiedCitationError(
                "No verified literature candidates were retrieved; synthesis stopped"
            )

        inputs = {
            "research_plan": plan.model_dump(mode="json"),
            "literature_candidates": [
                paper.model_dump(mode="json") for paper in candidates
            ],
        }
        user_prompt = (
            "Produce ResearchAnalysis using only these verified artifacts. "
            "Preserve exactly these hypothesis IDs: "
            f"{sorted(hypothesis.hypothesis_id for hypothesis in plan.hypotheses)}."
            "\n\n" + json.dumps(inputs, ensure_ascii=False, indent=2)
        )
        analysis = self.llm.generate(
            schema=ResearchAnalysis,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            node_name=self.name,
        )
        planned_ids = {hypothesis.hypothesis_id for hypothesis in plan.hypotheses}
        refined_ids = {
            hypothesis.hypothesis_id for hypothesis in analysis.refined_hypotheses
        }
        if refined_ids != planned_ids:
            try:
                analysis = self.llm.generate(
                    schema=ResearchAnalysis,
                    system_prompt=_SYSTEM_PROMPT,
                    user_prompt=(
                        user_prompt
                        + "\n\nYour previous response changed the hypothesis identity. "
                        f"Return exactly these IDs: {sorted(planned_ids)}."
                    ),
                    node_name=self.name,
                )
            except Exception as exc:
                raise UnverifiedCitationError(
                    "refined_hypotheses must preserve every ResearchPlan hypothesis_id"
                ) from exc
            refined_ids = {
                hypothesis.hypothesis_id for hypothesis in analysis.refined_hypotheses
            }
            if refined_ids != planned_ids:
                raise UnverifiedCitationError(
                    "refined_hypotheses must preserve every ResearchPlan hypothesis_id"
                )
        verified_papers = [
            _verified_reference(paper, candidates) for paper in analysis.key_papers
        ]
        verified_analysis = analysis.model_copy(update={"key_papers": verified_papers})
        return {
            "literature_candidates": candidates,
            "research_analysis": verified_analysis,
            "current_stage": self.name,
        }


def create_research_analysis_node(
    llm: StructuredLLM,
    literature_retriever: LiteratureRetriever,
) -> ResearchAnalysisNode:
    return ResearchAnalysisNode(llm=llm, literature_retriever=literature_retriever)


def research_analysis_node(state: ResearchState) -> dict:
    """Production wiring must inject an LLM and a literature retriever."""
    raise NotImplementedError("Inject ResearchAnalysisNode through workflow wiring")
