"""Workflow registry and dispatch boundary for the generalised platform."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from graph.intent_router import route_request
from schemas.enums import TaskType
from schemas.platform import ResearchRequest

WorkflowHandler = Callable[[ResearchRequest], Mapping[str, Any]]


class WorkflowNotRegisteredError(LookupError):
    """Raised when a valid request targets a capability not installed yet."""


@dataclass
class WorkflowRegistry:
    """Keeps domain workflows replaceable without coupling nodes to one another."""

    handlers: dict[TaskType, WorkflowHandler] = field(default_factory=dict)

    def register(self, task_type: TaskType, handler: WorkflowHandler) -> None:
        self.handlers[task_type] = handler

    def dispatch(self, request: ResearchRequest | dict) -> dict[str, Any]:
        validated = (
            request
            if isinstance(request, ResearchRequest)
            else ResearchRequest.model_validate(request)
        )
        selection = route_request(validated)
        handler = self.handlers.get(validated.task_type)
        if handler is None:
            raise WorkflowNotRegisteredError(
                f"No workflow registered for task_type={validated.task_type.value}"
            )
        return {
            "request": validated,
            "research_question": validated.question,
            "workflow_selection": selection,
            "workflow_result": dict(handler(validated)),
        }
