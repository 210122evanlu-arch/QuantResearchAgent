"""Research Manager node interface."""

from agents.base import StructuredNode
from llm.protocol import StructuredLLM
from schemas.research_plan import ResearchPlan
from schemas.state import ResearchState

_SYSTEM_PROMPT = """You are the research manager for an institutional financial research team.
Convert the user's research question into a precise, testable research plan.
Return only the requested ResearchPlan structure. Do not claim that any analysis
or experiment has already been performed."""


def create_research_manager_node(
    llm: StructuredLLM,
    available_variables: tuple[str, ...] = (),
) -> StructuredNode[ResearchPlan]:
    system_prompt = _SYSTEM_PROMPT
    if available_variables:
        variables = ", ".join(available_variables)
        system_prompt += (
            "\nFor this executable MVP, formulate hypotheses using only variables "
            f"available in the configured dataset: {variables}."
        )
    return StructuredNode(
        name="research_manager",
        output_key="research_plan",
        output_schema=ResearchPlan,
        input_keys=("research_question",),
        system_prompt=system_prompt,
        llm=llm,
    )


def research_manager_node(state: ResearchState) -> dict:
    """Production wiring must inject a configured structured LLM."""
    raise NotImplementedError("Inject a Research Manager node through workflow wiring")
