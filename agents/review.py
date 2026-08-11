"""Research Committee node combining policy checks with reviewer challenge."""

import json
import re
from dataclasses import dataclass, field

from agents.base import NodeInputError
from llm.protocol import StructuredLLM
from schemas.data_profile import DataProfile
from schemas.enums import (
    IssueSeverity,
    ProblemType,
    ReviewDecision,
    ReviewIssueOrigin,
    RevisionTarget,
)
from schemas.experiment import ExperimentResult
from schemas.model_design import ModelDesign
from schemas.review import ReviewIssue, ReviewResult
from schemas.state import ResearchState
from tools.research_committee import ReviewPolicyConfig, evaluate_research_policy

_SYSTEM_PROMPT = """You are an independent institutional research reviewer.
Challenge economic logic, model specification, data interpretation, statistical
validity, robustness, and overfitting using only the supplied structured
artifacts and policy assessment. Every suggested issue must cite exact artifact
fields in evidence, using `root.field` or `root.field = value`. Do not invent
tests or facts. You may request a revision,
but the committee code makes the final decision and cannot be overridden to
Approved when deterministic policy issues remain."""

_TARGET_BY_PROBLEM = {
    ProblemType.MODEL_ISSUE: RevisionTarget.MODEL_DESIGN,
    ProblemType.DATA_ISSUE: RevisionTarget.DATA_PREPARATION,
    ProblemType.EXPERIMENT_ISSUE: RevisionTarget.EXPERIMENT,
}
_SEVERITY_RANK = {
    IssueSeverity.LOW: 1,
    IssueSeverity.MEDIUM: 2,
    IssueSeverity.HIGH: 3,
    IssueSeverity.CRITICAL: 4,
}
_UPSTREAM_PRIORITY = {
    ProblemType.MODEL_ISSUE: 3,
    ProblemType.DATA_ISSUE: 2,
    ProblemType.EXPERIMENT_ISSUE: 1,
}
_ALLOWED_EVIDENCE_ROOTS = (
    "model_design.",
    "data_profile.",
    "experiment_result.",
)
_EVIDENCE_FIELDS = {
    "model_design": set(ModelDesign.model_fields),
    "data_profile": set(DataProfile.model_fields),
    "experiment_result": set(ExperimentResult.model_fields),
}
_EXPERIMENT_SHORTHANDS = (
    "model_metrics.",
    "statistical_results",
    "robustness_checks",
    "warnings",
    "parameters.",
)


class ReviewEvidenceError(ValueError):
    """Raised when a reviewer issue has no traceable state evidence."""


def _normalise_reviewer_issue(issue: ReviewIssue) -> ReviewIssue:
    if not issue.evidence:
        raise ReviewEvidenceError(
            f"Reviewer issue {issue.category!r} has no artifact evidence"
        )
    evidence = []
    for item in issue.evidence:
        normalised = item.strip().casefold()
        if normalised.startswith(_EXPERIMENT_SHORTHANDS):
            evidence.append(f"experiment_result.{item.strip()}")
        else:
            evidence.append(item)
    invalid = [
        item
        for item in evidence
        if not item.strip().casefold().startswith(_ALLOWED_EVIDENCE_ROOTS)
    ]
    if invalid:
        raise ReviewEvidenceError(
            "Reviewer evidence must reference model_design, data_profile, or "
            "experiment_result fields: " + ", ".join(invalid)
        )
    unknown_fields = []
    for item in evidence:
        path = re.split(r"\s*(?:=|:)\s*", item.strip().casefold(), maxsplit=1)[0]
        root, remainder = path.split(".", 1)
        field_name = remainder.split(".", 1)[0].split("[", 1)[0]
        if field_name not in _EVIDENCE_FIELDS[root]:
            unknown_fields.append(item)
    if unknown_fields:
        raise ReviewEvidenceError(
            "Reviewer evidence references unknown artifact fields: "
            + ", ".join(unknown_fields)
        )
    return issue.model_copy(
        update={
            "origin": ReviewIssueOrigin.REVIEWER,
            "blocking": issue.severity in {IssueSeverity.HIGH, IssueSeverity.CRITICAL},
            "evidence": evidence,
        }
    )


def _deduplicate_issues(issues: list[ReviewIssue]) -> list[ReviewIssue]:
    output: list[ReviewIssue] = []
    seen: set[tuple[str, ProblemType, str]] = set()
    for issue in issues:
        key = (
            issue.category.casefold(),
            issue.problem_type,
            issue.description.casefold(),
        )
        if key not in seen:
            output.append(issue)
            seen.add(key)
    return output


def _select_revision_target(blocking: list[ReviewIssue]) -> RevisionTarget:
    priority_issue = max(
        blocking,
        key=lambda issue: (
            _SEVERITY_RANK[issue.severity],
            _UPSTREAM_PRIORITY[issue.problem_type],
        ),
    )
    return _TARGET_BY_PROBLEM[priority_issue.problem_type]


@dataclass(frozen=True)
class ResearchCommitteeNode:
    llm: StructuredLLM
    policy_config: ReviewPolicyConfig = field(default_factory=ReviewPolicyConfig)
    name: str = "review"
    output_key: str = "review_result"
    output_schema: type[ReviewResult] = ReviewResult
    input_keys: tuple[str, ...] = (
        "model_design",
        "data_profile",
        "experiment_result",
    )

    def __call__(self, state: ResearchState) -> dict:
        missing = [key for key in self.input_keys if key not in state]
        if missing:
            raise NodeInputError(
                f"Node {self.name!r} is missing state fields: {', '.join(missing)}"
            )
        model = state["model_design"]
        data = state["data_profile"]
        experiment = state["experiment_result"]
        policy = evaluate_research_policy(model, data, experiment, self.policy_config)
        prompt_payload = {
            "model_design": model.model_dump(mode="json"),
            "data_profile": data.model_dump(mode="json"),
            "experiment_result": experiment.model_dump(mode="json"),
            "deterministic_policy": {
                "strengths": policy.strengths,
                "issues": [issue.model_dump(mode="json") for issue in policy.issues],
            },
        }
        advisory = self.llm.generate(
            schema=ReviewResult,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=(
                "Provide an evidence-grounded independent committee advisory.\n\n"
                + json.dumps(prompt_payload, ensure_ascii=False, indent=2)
            ),
            node_name=self.name,
        )

        reviewer_issues = [
            _normalise_reviewer_issue(issue) for issue in advisory.issues
        ]
        issues = _deduplicate_issues([*policy.issues, *reviewer_issues])
        blocking = [issue for issue in issues if issue.blocking]
        decision = ReviewDecision.NEED_REVISION if blocking else ReviewDecision.APPROVED
        revision_target = _select_revision_target(blocking) if blocking else None
        strengths = list(dict.fromkeys([*policy.strengths, *advisory.strengths]))
        status = (
            "Committee revision required."
            if blocking
            else "Committee policy checks passed."
        )
        result = ReviewResult(
            strengths=strengths,
            issues=issues,
            decision=decision,
            revision_target=revision_target,
            overall_assessment=f"{status} {advisory.overall_assessment}".strip(),
        )
        return {"review_result": result, "current_stage": self.name}


def create_review_node(
    llm: StructuredLLM,
    policy_config: ReviewPolicyConfig | None = None,
) -> ResearchCommitteeNode:
    return ResearchCommitteeNode(
        llm=llm,
        policy_config=policy_config or ReviewPolicyConfig(),
    )


def review_node(state: ResearchState) -> dict:
    """Production wiring must inject a structured LLM and committee policy."""
    raise NotImplementedError(
        "Inject a Research Committee node through workflow wiring"
    )
