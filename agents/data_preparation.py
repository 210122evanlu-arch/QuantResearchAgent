"""Deterministic Data Preparation node backed by local data tools."""

from dataclasses import dataclass

from agents.base import NodeInputError
from schemas.data_profile import DataProfile
from schemas.enums import RevisionTarget
from schemas.state import ResearchState
from tools.financial_data import (
    DataProfileProvider,
    LocalDataConfig,
    LocalDataProfileProvider,
)


@dataclass(frozen=True)
class DataPreparationNode:
    provider: DataProfileProvider
    revision_providers: tuple[DataProfileProvider, ...] = ()
    name: str = "data_preparation"
    output_key: str = "data_profile"
    output_schema: type[DataProfile] = DataProfile
    input_keys: tuple[str, ...] = ("research_plan", "model_design")

    def __call__(self, state: ResearchState) -> dict:
        missing = [key for key in self.input_keys if key not in state]
        if missing:
            raise NodeInputError(
                f"Node {self.name!r} is missing state fields: {', '.join(missing)}"
            )
        current_index = state.get("active_data_revision_index", 0)
        review = state.get("review_result")
        is_data_revision = (
            review is not None
            and review.revision_target == RevisionTarget.DATA_PREPARATION
        )
        requested_index = current_index + 1 if is_data_revision else current_index
        providers = (self.provider, *self.revision_providers)
        selected_index = min(requested_index, len(providers) - 1)
        profile = providers[selected_index].build_profile(state["model_design"])
        return {
            "data_profile": profile,
            "active_data_revision_index": selected_index,
            "active_data_path": profile.data_sources[0],
            "data_revision_count": state.get("data_revision_count", 0)
            + int(is_data_revision),
            "current_stage": self.name,
        }


def create_data_preparation_node(
    config: LocalDataConfig,
    revision_configs: tuple[LocalDataConfig, ...] = (),
) -> DataPreparationNode:
    return DataPreparationNode(
        provider=LocalDataProfileProvider(config),
        revision_providers=tuple(
            LocalDataProfileProvider(revision) for revision in revision_configs
        ),
    )


def data_preparation_node(state: ResearchState) -> dict:
    """Production wiring must inject an explicit local data configuration."""
    raise NotImplementedError("Inject a Data Preparation node through workflow wiring")
