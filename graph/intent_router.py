"""Deterministic routing from platform intake to specialised workflows."""

from dataclasses import dataclass

from schemas.enums import AnalysisMethod, TaskType
from schemas.platform import ResearchRequest, WorkflowSelection


@dataclass(frozen=True)
class RouteProfile:
    workflow_name: str
    methods: tuple[AnalysisMethod, ...]
    report_template: str


ROUTE_PROFILES: dict[TaskType, RouteProfile] = {
    TaskType.COMPANY_RESEARCH: RouteProfile(
        workflow_name="company_research",
        methods=(
            AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS,
            AnalysisMethod.STRATEGIC_DIAGNOSIS,
            AnalysisMethod.RELATIVE_VALUATION,
            AnalysisMethod.PEER_BENCHMARKING,
        ),
        report_template="company_research.md",
    ),
    TaskType.INDUSTRY_RESEARCH: RouteProfile(
        workflow_name="industry_research",
        methods=(
            AnalysisMethod.INDUSTRY_ANALYSIS,
            AnalysisMethod.PEER_BENCHMARKING,
            AnalysisMethod.SCENARIO_ANALYSIS,
        ),
        report_template="industry_research.md",
    ),
    TaskType.QUANT_RESEARCH: RouteProfile(
        workflow_name="quant_research",
        methods=(
            AnalysisMethod.REGRESSION,
            AnalysisMethod.PORTFOLIO_BACKTEST,
        ),
        report_template="quant_research.md",
    ),
    TaskType.MARKET_STRATEGY: RouteProfile(
        workflow_name="market_strategy",
        methods=(
            AnalysisMethod.MARKET_REGIME_ANALYSIS,
            AnalysisMethod.SCENARIO_ANALYSIS,
        ),
        report_template="market_strategy.md",
    ),
    TaskType.EVENT_STUDY: RouteProfile(
        workflow_name="event_study",
        methods=(AnalysisMethod.EVENT_STUDY,),
        report_template="event_study.md",
    ),
    TaskType.CORPORATE_ADVISORY: RouteProfile(
        workflow_name="corporate_advisory",
        methods=(
            AnalysisMethod.FINANCIAL_STATEMENT_ANALYSIS,
            AnalysisMethod.PEER_BENCHMARKING,
            AnalysisMethod.STRATEGIC_DIAGNOSIS,
            AnalysisMethod.SCENARIO_ANALYSIS,
            AnalysisMethod.FINANCIAL_ANOMALY_SCREENING,
        ),
        report_template="corporate_advisory.md",
    ),
}


def route_request(request: ResearchRequest) -> WorkflowSelection:
    """Return an auditable default route; downstream planning may narrow methods."""
    profile = ROUTE_PROFILES[request.task_type]
    methods = list(profile.methods)
    if request.task_type == TaskType.COMPANY_RESEARCH and "dcf" in {
        topic.casefold() for topic in request.topics
    }:
        methods.insert(
            methods.index(AnalysisMethod.PEER_BENCHMARKING),
            AnalysisMethod.DCF_VALUATION,
        )
    return WorkflowSelection(
        task_type=request.task_type,
        workflow_name=profile.workflow_name,
        analysis_methods=methods,
        report_template=profile.report_template,
        rationale=(
            f"Selected the {profile.workflow_name} capability profile for "
            f"task_type={request.task_type.value}."
        ),
    )


def intent_router_node(state: dict) -> dict:
    """LangGraph-compatible platform entry node."""
    request = state.get("request")
    if request is None:
        raise ValueError("platform state is missing request")
    if not isinstance(request, ResearchRequest):
        request = ResearchRequest.model_validate(request)
    return {
        "request": request,
        "research_question": request.question,
        "workflow_selection": route_request(request),
        "current_stage": "intent_router",
    }
