"""Deterministic Report Generator node with source-level traceability."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.base import NodeInputError
from schemas.enums import ReviewDecision
from schemas.report import FinalReport
from schemas.state import ResearchState
from tools.report_generator import save_markdown_report


class ReportConsistencyError(ValueError):
    """Raised when an approved report conflicts with verified upstream state."""


def _source_digest(state: ResearchState, keys: tuple[str, ...]) -> str:
    state_values: Mapping[str, Any] = state
    payload = {key: state_values[key].model_dump(mode="json") for key in keys}
    payload["revision_limit_reached"] = state.get("revision_limit_reached", False)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _number(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.8g}"


@dataclass(frozen=True)
class ReportNode:
    output_path: Path | None = None
    name: str = "report"
    output_key: str = "final_report"
    output_schema: type[FinalReport] = FinalReport
    input_keys: tuple[str, ...] = (
        "research_plan",
        "research_analysis",
        "model_design",
        "data_profile",
        "experiment_result",
        "review_result",
    )

    def __call__(self, state: ResearchState) -> dict:
        missing = [key for key in self.input_keys if key not in state]
        if missing:
            raise NodeInputError(
                f"Node {self.name!r} is missing state fields: {', '.join(missing)}"
            )
        plan = state["research_plan"]
        analysis = state["research_analysis"]
        model = state["model_design"]
        data = state["data_profile"]
        experiment = state["experiment_result"]
        review = state["review_result"]
        revision_limit_reached = state.get("revision_limit_reached", False)
        if review.decision == ReviewDecision.APPROVED:
            if revision_limit_reached:
                raise ReportConsistencyError(
                    "Approved review cannot coexist with revision_limit_reached"
                )
            if (
                not data.dataset_fingerprint
                or not experiment.data_fingerprint
                or data.dataset_fingerprint != experiment.data_fingerprint
            ):
                raise ReportConsistencyError(
                    "Approved report requires matching data and experiment fingerprints"
                )
            if experiment.estimator != model.estimator:
                raise ReportConsistencyError(
                    "Approved report requires matching model and experiment estimators"
                )

        findings = []
        for result in experiment.statistical_results:
            findings.append(
                f"{result.variable}: coefficient={_number(result.coefficient)}, "
                f"t={_number(result.t_stat)}, p={_number(result.p_value)}, "
                f"significant={'yes' if result.significant else 'no'}."
            )
        robustness_summary = (
            "; ".join(
                f"{check.name}: {'passed' if check.passed else 'failed'}"
                for check in experiment.robustness_checks
            )
            or "No robustness check was reported."
        )
        risk_disclosures = [
            "This research output is not investment advice and requires human review."
        ]
        risk_disclosures.extend(experiment.warnings)
        risk_disclosures.extend(issue.description for issue in review.issues)
        if review.decision != ReviewDecision.APPROVED or revision_limit_reached:
            risk_disclosures.insert(
                0,
                "Committee approval was not obtained; this report is not an approved "
                "research conclusion.",
            )
        if any(
            paper.metadata_source != "crossref"
            for paper in state.get("literature_candidates", [])
        ):
            risk_disclosures.append(
                "The literature set contains offline or non-Crossref fixtures."
            )
        if data.dataset_fingerprint != experiment.data_fingerprint:
            risk_disclosures.append(
                "Prepared-data and experiment-data fingerprints do not match."
            )

        recommendations = list(
            dict.fromkeys(issue.recommendation for issue in review.issues)
        )
        if not recommendations:
            recommendations = [
                "Maintain out-of-sample monitoring and independent review before use."
            ]
        conclusion = (
            "The research committee approved the reported specification and results, "
            "subject to the stated limitations."
            if review.decision == ReviewDecision.APPROVED and not revision_limit_reached
            else (
                "No formal research conclusion is approved. Resolve the blocking issues "
                "before relying on these results."
            )
        )
        artifact_path = str(self.output_path.resolve()) if self.output_path else None
        report = FinalReport(
            title=f"Research Report: {plan.research_question}",
            executive_summary=(
                f"Objective: {plan.research_objective} "
                f"Committee decision: {review.decision.value}. "
                f"Experiment conclusion: {experiment.conclusion}"
            ),
            research_background=(
                f"Research gap: {analysis.research_gap} "
                f"Theoretical mechanism: {analysis.theoretical_mechanism}"
            ),
            hypotheses=[
                hypothesis.statement for hypothesis in analysis.refined_hypotheses
            ],
            methodology=(
                f"{model.model_name}; formula={model.formula}; "
                f"standard errors={model.standard_error_method}."
            ),
            data_description=(
                f"{data.universe}; {data.frequency.value}; "
                f"{data.start_date.isoformat()} to {data.end_date.isoformat()}; "
                f"prepared rows={data.sample_size}; missing rate={data.missing_rate:.8g}; "
                f"duplicate rate={data.duplicate_rate:.8g}."
            ),
            findings=findings,
            robustness_summary=robustness_summary,
            risk_disclosures=list(dict.fromkeys(risk_disclosures)),
            limitations=model.limitations,
            recommendations=recommendations,
            review_decision=review.decision,
            conclusion=conclusion,
            model_name=model.model_name,
            formula=model.formula,
            estimator=model.estimator,
            experiment_method=experiment.method,
            data_sample_size=data.sample_size,
            experiment_sample_size=experiment.sample_size,
            data_fingerprint=experiment.data_fingerprint
            or data.dataset_fingerprint
            or "unknown",
            prepared_data_fingerprint=data.dataset_fingerprint,
            experiment_data_fingerprint=experiment.data_fingerprint,
            model_metrics=experiment.model_metrics.model_copy(deep=True),
            statistical_findings=[
                result.model_copy(deep=True)
                for result in experiment.statistical_results
            ],
            portfolio_results=[
                cell.model_copy(deep=True) for cell in experiment.portfolio_results
            ],
            robustness_checks=[
                check.model_copy(deep=True) for check in experiment.robustness_checks
            ],
            references=[paper.model_copy(deep=True) for paper in analysis.key_papers],
            unresolved_issues=[issue.model_copy(deep=True) for issue in review.issues],
            source_digest=_source_digest(state, self.input_keys),
            artifact_path=artifact_path,
        )
        if self.output_path:
            save_markdown_report(report, self.output_path)
        output = {"final_report": report, "current_stage": self.name}
        if artifact_path:
            output["report_markdown_path"] = artifact_path
        return output


def create_report_node(output_path: str | Path | None = None) -> ReportNode:
    return ReportNode(Path(output_path) if output_path is not None else None)


def report_node(state: ResearchState) -> dict:
    """Production wiring must inject report output configuration."""
    raise NotImplementedError("Inject a Report node through workflow wiring")
