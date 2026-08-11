from pathlib import Path

import pytest

import production
from schemas.enums import DataFrequency
from tools.financial_data import LocalDataConfig


def _data_config() -> LocalDataConfig:
    return LocalDataConfig(
        path=Path("unused.csv"),
        date_column="date",
        target_date_column="target_date",
        entity_column="stock_id",
        frequency=DataFrequency.MONTHLY,
        universe="Test universe",
    )


def test_run_research_validates_control_inputs() -> None:
    with pytest.raises(ValueError, match="research_question"):
        production.run_research("  ", _data_config())
    with pytest.raises(ValueError, match="max_revisions"):
        production.run_research("Question", _data_config(), max_revisions=-1)


def test_run_research_initializes_graph_state(monkeypatch) -> None:
    captured = {}

    class FakeWorkflow:
        def invoke(self, state):
            captured.update(state)
            return state

    monkeypatch.setattr(
        production,
        "build_production_workflow",
        lambda data_config, **options: FakeWorkflow(),
    )

    result = production.run_research(
        "  Does IVOL predict returns?  ",
        _data_config(),
        max_revisions=2,
    )

    assert result["research_question"] == "Does IVOL predict returns?"
    assert captured["revision_count"] == 0
    assert captured["max_revisions"] == 2
