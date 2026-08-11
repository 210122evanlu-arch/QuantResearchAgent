"""Safe lookup of report templates selected by the intent router."""

from pathlib import Path

from schemas.platform import WorkflowSelection

TEMPLATE_DIRECTORY = Path(__file__).resolve().parents[1] / "report_templates"


def resolve_report_template(selection: WorkflowSelection) -> Path:
    """Resolve only a router-owned filename within the template directory."""
    filename = Path(selection.report_template)
    if filename.name != selection.report_template:
        raise ValueError("report_template must be a filename, not a path")
    path = TEMPLATE_DIRECTORY / filename
    if not path.is_file():
        raise FileNotFoundError(f"Report template does not exist: {filename.name}")
    return path
