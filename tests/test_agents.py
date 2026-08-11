import pytest

from agents import (
    data_preparation_node,
    experiment_node,
    model_design_node,
    report_node,
    research_analysis_node,
    research_manager_node,
    review_node,
)


@pytest.mark.parametrize(
    "node",
    [
        research_manager_node,
        research_analysis_node,
        model_design_node,
        data_preparation_node,
        experiment_node,
        review_node,
        report_node,
    ],
)
def test_unimplemented_production_nodes_fail_explicitly(node) -> None:
    with pytest.raises(NotImplementedError):
        node({"research_question": "投资者情绪与未来收益"})
