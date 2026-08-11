"""General analysis node; the existing Experiment node is its quant specialist."""

from dataclasses import dataclass

from agents.base import NodeInputError
from analysis_engines.router import AnalysisEngineRegistry
from schemas.platform import AnalysisBundle, EvidenceRecord, WorkflowSelection


@dataclass(frozen=True)
class AnalysisExecutionNode:
    registry: AnalysisEngineRegistry
    name: str = "analysis_execution"

    def __call__(self, state: dict) -> dict:
        missing = [
            key
            for key in ("workflow_selection", "analysis_context")
            if key not in state
        ]
        if missing:
            raise NodeInputError(
                f"Node {self.name!r} is missing state fields: {', '.join(missing)}"
            )
        selection = state["workflow_selection"]
        if not isinstance(selection, WorkflowSelection):
            selection = WorkflowSelection.model_validate(selection)
        context = state["analysis_context"]
        artifacts = [
            self.registry.execute(method, context)
            for method in selection.analysis_methods
        ]
        evidence = [
            item
            if isinstance(item, EvidenceRecord)
            else EvidenceRecord.model_validate(item)
            for item in context.get("evidence", [])
        ]
        return {
            "analysis_bundle": AnalysisBundle(
                artifacts=artifacts,
                evidence=evidence,
                warnings=list(context.get("warnings", [])),
            ),
            "current_stage": self.name,
        }
