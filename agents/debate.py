"""Evidence-constrained proponent, challenger, and moderator nodes."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agents.base import NodeInputError
from llm.protocol import StructuredLLM
from schemas.debate import ChallengerCase, ModeratorAssessment, ProponentCase
from schemas.platform import AnalysisBundle
from schemas.state import ResearchState

_PROPONENT_PROMPT = """You are the proponent in an institutional research debate.
Build the strongest defensible case for the current analysis. Use only supplied
evidence IDs. Acknowledge material limitations; do not invent data or citations.
Each argument must use position='support'."""

_CHALLENGER_PROMPT = """You are the independent challenger in an institutional
research debate. Test alternative explanations, data limitations, model risk,
economic logic, and implementation risk. Use only supplied evidence IDs and cite
the proponent argument IDs you challenge. Each argument must use
position='challenge'. Do not invent facts or tests."""

_MODERATOR_PROMPT = """You are the neutral moderator of an institutional research
debate. Decide whether another round has a concrete chance to resolve a material
issue. Continue only when this round added new information and unresolved issues
remain. Otherwise conclude. Distinguish consensus from disputed findings and do
not change verified calculations."""


class DebateEvidenceError(ValueError):
    """Raised when a debater cites evidence outside the verified bundle."""


def _payload(state: ResearchState, keys: tuple[str, ...]) -> str:
    state_values: Mapping[str, Any] = state
    missing = [key for key in keys if key not in state_values]
    if missing:
        raise NodeInputError(
            "Debate node is missing state fields: " + ", ".join(missing)
        )
    values = {}
    for key in keys:
        value = state_values[key]
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        elif isinstance(value, list):
            value = [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in value
            ]
        values[key] = value
    return json.dumps(values, ensure_ascii=False, indent=2, default=str)


def _known_evidence(state: ResearchState) -> set[str]:
    state_values: Mapping[str, Any] = state
    bundle = state_values["analysis_bundle"]
    if not isinstance(bundle, AnalysisBundle):
        bundle = AnalysisBundle.model_validate(bundle)
    return {item.evidence_id for item in bundle.evidence}


def _validate_evidence(state: ResearchState, case: ProponentCase | ChallengerCase):
    known = _known_evidence(state)
    cited = {
        evidence_id
        for argument in case.arguments
        for evidence_id in argument.evidence_ids
    }
    unknown = cited - known
    if unknown:
        raise DebateEvidenceError(
            "Debate arguments cite unknown evidence IDs: " + ", ".join(sorted(unknown))
        )
    return case


@dataclass(frozen=True)
class ProponentNode:
    llm: StructuredLLM
    name: str = "debate_proponent"

    def __call__(self, state: ResearchState) -> dict:
        prompt = _payload(state, ("request", "analysis_bundle", "debate_rounds"))
        result = self.llm.generate(
            schema=ProponentCase,
            system_prompt=_PROPONENT_PROMPT,
            user_prompt=prompt,
            node_name=self.name,
        )
        return {
            "proponent_case": _validate_evidence(state, result),
            "current_stage": self.name,
        }


@dataclass(frozen=True)
class ChallengerNode:
    llm: StructuredLLM
    name: str = "debate_challenger"

    def __call__(self, state: ResearchState) -> dict:
        prompt = _payload(
            state,
            ("request", "analysis_bundle", "debate_rounds", "proponent_case"),
        )
        result = self.llm.generate(
            schema=ChallengerCase,
            system_prompt=_CHALLENGER_PROMPT,
            user_prompt=prompt,
            node_name=self.name,
        )
        proponent_ids = {
            argument.argument_id for argument in state["proponent_case"].arguments
        }
        challenged_ids = {
            argument_id
            for argument in result.arguments
            for argument_id in argument.challenges_argument_ids
        }
        unknown = challenged_ids - proponent_ids
        if unknown:
            raise ValueError(
                "Challenger references unknown proponent argument IDs: "
                + ", ".join(sorted(unknown))
            )
        return {
            "challenger_case": _validate_evidence(state, result),
            "current_stage": self.name,
        }


@dataclass(frozen=True)
class ModeratorNode:
    llm: StructuredLLM
    name: str = "debate_moderator"

    def __call__(self, state: ResearchState) -> dict:
        prompt = _payload(
            state,
            (
                "request",
                "analysis_bundle",
                "debate_rounds",
                "proponent_case",
                "challenger_case",
            ),
        )
        result = self.llm.generate(
            schema=ModeratorAssessment,
            system_prompt=_MODERATOR_PROMPT,
            user_prompt=prompt,
            node_name=self.name,
        )
        return {"moderator_assessment": result, "current_stage": self.name}


def create_debate_nodes(llm: StructuredLLM):
    """Create the three role nodes sharing one configured provider."""
    return ProponentNode(llm), ChallengerNode(llm), ModeratorNode(llm)
