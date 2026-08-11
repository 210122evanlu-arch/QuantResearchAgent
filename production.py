"""Production assembly for the seven-node research workflow."""

from __future__ import annotations

import os
from pathlib import Path

from agents.data_preparation import create_data_preparation_node
from agents.experiment import create_experiment_node
from agents.model_design import create_model_design_node
from agents.report import create_report_node
from agents.research_analysis import create_research_analysis_node
from agents.research_manager import create_research_manager_node
from agents.review import create_review_node
from graph.workflow import WorkflowNodes, build_workflow
from literature.crossref import CrossrefClient, CrossrefLiteratureRetriever
from literature.protocol import LiteratureRetriever
from llm import get_default_llm
from llm.protocol import StructuredLLM
from schemas.state import ResearchState
from tools.financial_data import LocalDataConfig, load_financial_data
from tools.research_committee import ReviewPolicyConfig
from tools.statistics import ExperimentConfig


def build_production_workflow(
    data_config: LocalDataConfig,
    *,
    revision_data_configs: tuple[LocalDataConfig, ...] = (),
    report_path: str | Path | None = None,
    experiment_artifact_directory: str | Path | None = None,
    llm: StructuredLLM | None = None,
    literature_retriever: LiteratureRetriever | None = None,
    experiment_config: ExperimentConfig | None = None,
    review_policy: ReviewPolicyConfig | None = None,
    crossref_mailto: str | None = None,
):
    """Build the real graph with one configured LLM shared by all LLM nodes."""
    resolved_llm = llm or get_default_llm()
    all_configs = (data_config, *revision_data_configs)
    variable_sets = [
        {str(column) for column in load_financial_data(config.path).columns}
        for config in all_configs
    ]
    available_variables = tuple(sorted(set.intersection(*variable_sets)))
    retriever = literature_retriever or CrossrefLiteratureRetriever(
        CrossrefClient(mailto=crossref_mailto or os.getenv("CROSSREF_MAILTO"))
    )
    nodes = WorkflowNodes(
        research_manager=create_research_manager_node(
            resolved_llm,
            available_variables=available_variables,
        ),
        research_analysis=create_research_analysis_node(resolved_llm, retriever),
        model_design=create_model_design_node(
            resolved_llm,
            available_variables=available_variables,
        ),
        data_preparation=create_data_preparation_node(
            data_config, revision_configs=revision_data_configs
        ),
        experiment=create_experiment_node(
            data_config,
            experiment_config=experiment_config,
            artifact_directory=experiment_artifact_directory,
            revision_data_configs=revision_data_configs,
        ),
        review=create_review_node(resolved_llm, review_policy),
        report=create_report_node(report_path),
    )
    return build_workflow(nodes)


def run_research(
    research_question: str,
    data_config: LocalDataConfig,
    *,
    max_revisions: int = 3,
    **workflow_options,
) -> ResearchState:
    """Build and execute a paid production workflow."""
    if not research_question.strip():
        raise ValueError("research_question cannot be empty")
    if max_revisions < 0:
        raise ValueError("max_revisions must be non-negative")
    workflow = build_production_workflow(data_config, **workflow_options)
    return workflow.invoke(
        {
            "research_question": research_question.strip(),
            "revision_count": 0,
            "max_revisions": max_revisions,
            "errors": [],
        }
    )
