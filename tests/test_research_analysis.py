import pytest

from agents.research_analysis import (
    UnverifiedCitationError,
    create_research_analysis_node,
)
from literature.protocol import StaticLiteratureRetriever
from llm.fake import FakeStructuredLLM
from schemas.literature import RetrievedPaper
from schemas.research_analysis import ResearchAnalysis
from schemas.research_plan import ResearchPlan


def _plan() -> ResearchPlan:
    return ResearchPlan.model_validate(
        {
            "research_question": "Does investor sentiment predict returns?",
            "research_objective": "Test return predictability.",
            "research_type": "panel",
            "hypotheses": [
                {
                    "hypothesis_id": "H1",
                    "statement": "Sentiment predicts returns",
                    "dependent_variable": "future_return",
                    "independent_variable": "sentiment",
                    "expected_direction": "negative",
                    "rationale": "Behavioral mechanism",
                }
            ],
            "methodology": "Panel regression",
            "required_data": ["returns", "sentiment"],
            "evaluation_metrics": ["coefficient"],
        }
    )


def _candidate(*, abstract: str | None = "Verified abstract") -> RetrievedPaper:
    return RetrievedPaper(
        title="Investor Sentiment and the Cross-Section of Stock Returns",
        authors=["Verified Author"],
        year=2006,
        journal="The Journal of Finance",
        issn="0022-1082",
        doi="10.1111/verified",
        url="https://doi.org/10.1111/verified",
        abstract=abstract,
    )


def _analysis(paper: dict) -> dict:
    hypothesis = _plan().hypotheses[0].model_dump(mode="json")
    return {
        "related_theories": ["Behavioral finance"],
        "existing_models": ["Sentiment model"],
        "key_papers": [paper],
        "theoretical_mechanism": "Limits to arbitrage.",
        "research_gap": "Out-of-sample evidence is needed.",
        "refined_hypotheses": [hypothesis],
    }


def test_node_accepts_only_retrieved_paper_and_restores_metadata() -> None:
    candidate = _candidate()
    llm = FakeStructuredLLM(
        {
            ResearchAnalysis: _analysis(
                {
                    "title": candidate.title,
                    "authors": ["Wrong Generated Author"],
                    "year": 1900,
                    "source": "Wrong source",
                    "key_finding": "Finding grounded in supplied abstract",
                    "relevance": "Directly relevant",
                    "doi_or_url": "doi:10.1111/verified",
                }
            )
        }
    )
    retriever = StaticLiteratureRetriever([candidate])

    result = create_research_analysis_node(llm, retriever)({"research_plan": _plan()})

    paper = result["research_analysis"].key_papers[0]
    assert paper.authors == ["Verified Author"]
    assert paper.year == 2006
    assert paper.source == "The Journal of Finance"
    assert paper.doi_or_url == "https://doi.org/10.1111/verified"
    assert result["literature_candidates"] == [candidate]
    assert candidate.title in llm.calls[0].user_prompt


def test_node_rejects_hallucinated_citation() -> None:
    llm = FakeStructuredLLM(
        {
            ResearchAnalysis: _analysis(
                {
                    "title": "Invented Paper",
                    "authors": ["Nobody"],
                    "year": 2025,
                    "source": "Invented Journal",
                    "key_finding": "Invented result",
                    "relevance": "Claimed relevance",
                    "doi_or_url": "https://example.invalid/invented",
                }
            )
        }
    )

    node = create_research_analysis_node(llm, StaticLiteratureRetriever([_candidate()]))
    with pytest.raises(UnverifiedCitationError, match="Invented Paper"):
        node({"research_plan": _plan()})


def test_node_marks_finding_pending_when_abstract_is_missing() -> None:
    candidate = _candidate(abstract=None)
    llm = FakeStructuredLLM(
        {
            ResearchAnalysis: _analysis(
                {
                    "title": candidate.title,
                    "authors": candidate.authors,
                    "year": candidate.year,
                    "source": candidate.journal,
                    "key_finding": "This must not survive without an abstract",
                    "relevance": "Potentially relevant",
                    "doi_or_url": candidate.url,
                }
            )
        }
    )

    result = create_research_analysis_node(llm, StaticLiteratureRetriever([candidate]))(
        {"research_plan": _plan()}
    )

    assert result["research_analysis"].key_papers[0].key_finding == (
        "Abstract unavailable; full-text review required."
    )


def test_node_stops_when_retrieval_returns_no_candidates() -> None:
    node = create_research_analysis_node(
        FakeStructuredLLM({}), StaticLiteratureRetriever([])
    )

    with pytest.raises(UnverifiedCitationError, match="No verified literature"):
        node({"research_plan": _plan()})


def test_node_rejects_changed_hypothesis_identity() -> None:
    candidate = _candidate()
    payload = _analysis(
        {
            "title": candidate.title,
            "authors": candidate.authors,
            "year": candidate.year,
            "source": candidate.journal,
            "key_finding": "Grounded finding",
            "relevance": "Relevant",
            "doi_or_url": candidate.url,
        }
    )
    payload["refined_hypotheses"][0]["hypothesis_id"] = "H_NEW"
    node = create_research_analysis_node(
        FakeStructuredLLM({ResearchAnalysis: payload}),
        StaticLiteratureRetriever([candidate]),
    )

    with pytest.raises(UnverifiedCitationError, match="preserve every"):
        node({"research_plan": _plan()})
