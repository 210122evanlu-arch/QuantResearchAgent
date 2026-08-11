"""Offline two-round research debate using the real LangGraph subgraph."""

from datetime import date, datetime

from graph.debate import create_debate_workflow
from llm.fake import FakeStructuredLLM
from schemas.debate import ChallengerCase, ModeratorAssessment, ProponentCase
from schemas.enums import AnalysisMethod, EvidenceStatus, TaskType
from schemas.platform import (
    AnalysisArtifact,
    AnalysisBundle,
    EvidenceRecord,
    ResearchFinding,
    ResearchRequest,
)


def _fake_responses() -> dict:
    support = {
        "thesis": "The verified analysis supports the working conclusion.",
        "arguments": [
            {
                "argument_id": "P1",
                "position": "support",
                "claim": "The reported relationship is supported by the fixture.",
                "reasoning": "The analysis artifact and source record agree.",
                "evidence_ids": ["E1"],
                "challenges_argument_ids": [],
                "confidence": 0.75,
            }
        ],
        "acknowledged_limitations": ["The fixture is not investment evidence."],
    }
    challenge = {
        "counter_thesis": "The conclusion remains sensitive to external validity.",
        "arguments": [
            {
                "argument_id": "C1",
                "position": "challenge",
                "claim": "The fixture cannot establish market-wide validity.",
                "reasoning": "Its declared scope is deliberately narrow.",
                "evidence_ids": ["E2"],
                "challenges_argument_ids": ["P1"],
                "confidence": 0.9,
            }
        ],
        "requested_checks": ["Document the external-validity limitation."],
    }
    return {
        ProponentCase: [support, support],
        ChallengerCase: [challenge, challenge],
        ModeratorAssessment: [
            {
                "decision": "continue",
                "new_information_added": True,
                "resolved_issues": [],
                "unresolved_issues": ["External validity remains unresolved."],
                "consensus_findings": ["The fixture calculation is internally valid."],
                "disputed_findings": ["The result generalises to a live market."],
                "rationale": "One focused response round may clarify the scope.",
                "synthesis": "Continue for one response on external validity.",
            },
            {
                "decision": "conclude",
                "new_information_added": False,
                "resolved_issues": ["The result is explicitly limited to the fixture."],
                "unresolved_issues": ["Live-market validity requires real data."],
                "consensus_findings": ["The fixture calculation is internally valid."],
                "disputed_findings": ["Live-market generalisation is unverified."],
                "rationale": "Further debate cannot replace missing real data.",
                "synthesis": (
                    "The internal fixture is valid, but no live-market conclusion is "
                    "approved without additional evidence."
                ),
            },
        ],
    }


def _initial_state(max_debate_rounds: int = 3) -> dict:
    request = ResearchRequest(
        task_type=TaskType.QUANT_RESEARCH,
        question="Does the fixture support the working conclusion?",
        as_of_date=date(2026, 8, 7),
    )
    evidence = [
        EvidenceRecord(
            evidence_id="E1",
            source_type="analysis_artifact",
            title="Fixture result",
            source_name="Offline demo",
            retrieved_at=datetime(2026, 8, 7),
            summary="The deterministic fixture produced the reported result.",
        ),
        EvidenceRecord(
            evidence_id="E2",
            source_type="scope_note",
            title="Fixture limitation",
            source_name="Offline demo",
            retrieved_at=datetime(2026, 8, 7),
            summary="The fixture is synthetic and has no external validity.",
        ),
    ]
    artifact = AnalysisArtifact(
        method=AnalysisMethod.REGRESSION,
        title="Offline regression fixture",
        summary="A synthetic result used only to verify debate routing.",
        findings=[
            ResearchFinding(
                finding_id="F1",
                statement="The fixture supports its internal working conclusion.",
                implication="The debate graph may challenge its interpretation.",
                evidence_ids=["E1"],
                status=EvidenceStatus.VERIFIED,
                confidence=0.8,
            )
        ],
    )
    return {
        "request": request,
        "analysis_bundle": AnalysisBundle(artifacts=[artifact], evidence=evidence),
        "debate_rounds": [],
        "debate_round": 0,
        "max_debate_rounds": max_debate_rounds,
        "debate_limit_reached": False,
    }


def run_debate_fake_demo(max_debate_rounds: int = 3):
    llm = FakeStructuredLLM(_fake_responses())
    workflow = create_debate_workflow(llm)
    return workflow.invoke(_initial_state(max_debate_rounds)), llm


if __name__ == "__main__":
    result, fake_llm = run_debate_fake_demo()
    print("Debate Fake LLM workflow: passed")
    print("Calls:", " -> ".join(call.node_name for call in fake_llm.calls))
    print("Rounds:", len(result["debate_result"].rounds))
    print("Stopped by limit:", result["debate_result"].stopped_by_limit)
    print("Conclusion:", result["debate_result"].moderator_conclusion)
