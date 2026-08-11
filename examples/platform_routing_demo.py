"""Offline demonstration of all platform service-line routes."""

from datetime import date

from graph.platform import WorkflowRegistry
from schemas.enums import TaskType
from schemas.platform import ResearchRequest
from tools.report_templates import resolve_report_template


def _fixture_request(task_type: TaskType) -> ResearchRequest:
    values = {
        "task_type": task_type,
        "question": f"Offline routing check for {task_type.value}",
        "as_of_date": date(2026, 8, 7),
    }
    if task_type in {TaskType.COMPANY_RESEARCH, TaskType.CORPORATE_ADVISORY}:
        values["securities"] = ["600000.SH"]
    if task_type == TaskType.INDUSTRY_RESEARCH:
        values["industries"] = ["renewable_energy"]
    return ResearchRequest.model_validate(values)


def run_platform_routing_demo() -> list[dict]:
    registry = WorkflowRegistry()
    for task_type in TaskType:
        registry.register(
            task_type,
            lambda request: {"status": "fixture", "task": request.task_type.value},
        )

    results = []
    for task_type in TaskType:
        result = registry.dispatch(_fixture_request(task_type))
        template = resolve_report_template(result["workflow_selection"])
        results.append({**result, "template_path": str(template)})
    return results


if __name__ == "__main__":
    for routed in run_platform_routing_demo():
        selection = routed["workflow_selection"]
        print(
            f"{selection.task_type.value} -> {selection.workflow_name} -> "
            f"{selection.report_template}"
        )
