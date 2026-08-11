from copy import deepcopy

import pytest
from pydantic import ValidationError

from agents.debate import DebateEvidenceError, ProponentNode
from examples.debate_workflow_demo import (
    _fake_responses,
    _initial_state,
    run_debate_fake_demo,
)
from graph.debate import create_debate_workflow
from llm.fake import FakeStructuredLLM
from schemas.debate import ModeratorAssessment, ProponentCase
from schemas.enums import ModeratorDecision


def test_moderator_runs_two_rounds_then_concludes() -> None:
    result, llm = run_debate_fake_demo()

    assert [call.node_name for call in llm.calls] == [
        "debate_proponent",
        "debate_challenger",
        "debate_moderator",
        "debate_proponent",
        "debate_challenger",
        "debate_moderator",
    ]
    assert result["debate_round"] == 2
    assert result["debate_result"].stopped_by_limit is False
    assert len(result["debate_result"].rounds) == 2
    assert result["current_stage"] == "debate_synthesis"


def test_code_hard_limit_overrides_moderator_continue() -> None:
    result, llm = run_debate_fake_demo(max_debate_rounds=1)

    assert len(llm.calls) == 3
    assert result["debate_round"] == 1
    assert result["moderator_assessment"].decision == ModeratorDecision.CONTINUE
    assert result["debate_result"].stopped_by_limit is True


def test_continuation_requires_new_information_and_an_open_issue() -> None:
    with pytest.raises(ValidationError, match="must add new information"):
        ModeratorAssessment(
            decision=ModeratorDecision.CONTINUE,
            new_information_added=False,
            rationale="Continue",
            synthesis="Continue",
            unresolved_issues=["Open"],
        )


def test_debater_cannot_invent_evidence_ids() -> None:
    responses = _fake_responses()
    invalid = deepcopy(responses[ProponentCase][0])
    invalid["arguments"][0]["evidence_ids"] = ["INVENTED"]
    node = ProponentNode(FakeStructuredLLM({ProponentCase: invalid}))

    with pytest.raises(DebateEvidenceError, match="INVENTED"):
        node(_initial_state())


def test_debate_schema_rejects_empty_evidence() -> None:
    invalid = deepcopy(_fake_responses()[ProponentCase][0])
    invalid["arguments"][0]["evidence_ids"] = []
    with pytest.raises(ValidationError):
        ProponentCase.model_validate(invalid)


def test_invalid_maximum_is_rejected_before_looping() -> None:
    llm = FakeStructuredLLM(_fake_responses())
    workflow = create_debate_workflow(llm)
    with pytest.raises(ValueError, match="between 1 and 5"):
        workflow.invoke(_initial_state(max_debate_rounds=0))
    assert llm.calls == []
