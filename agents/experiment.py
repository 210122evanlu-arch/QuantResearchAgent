"""Experiment node with enumerated estimator routing and data-version checks."""

from dataclasses import dataclass, field
from pathlib import Path

from agents.base import NodeInputError
from schemas.experiment import ExperimentResult
from schemas.state import ResearchState
from tools.experiment_artifacts import save_experiment_artifact
from tools.financial_data import (
    LocalDataConfig,
    compute_dataset_fingerprint,
    load_financial_data,
)
from tools.statistics import ExperimentConfig, ExperimentEngineError, run_experiment


class ExperimentDataMismatchError(ExperimentEngineError):
    """Raised when prepared metadata no longer matches the experiment file."""


@dataclass(frozen=True)
class ExperimentNode:
    data_config: LocalDataConfig
    revision_data_configs: tuple[LocalDataConfig, ...] = ()
    experiment_config: ExperimentConfig = field(default_factory=ExperimentConfig)
    artifact_directory: Path | None = None
    name: str = "experiment"
    output_key: str = "experiment_result"
    output_schema: type[ExperimentResult] = ExperimentResult
    input_keys: tuple[str, ...] = ("model_design", "data_profile")

    def __call__(self, state: ResearchState) -> dict:
        missing = [key for key in self.input_keys if key not in state]
        if missing:
            raise NodeInputError(
                f"Node {self.name!r} is missing state fields: {', '.join(missing)}"
            )
        profile = state["data_profile"]
        configs = (self.data_config, *self.revision_data_configs)
        config_index = state.get("active_data_revision_index", 0)
        if config_index >= len(configs):
            raise ExperimentDataMismatchError(
                "Experiment has no data configuration for the active revision"
            )
        active_config = configs[config_index]
        if not profile.look_ahead_bias_checked:
            raise ExperimentEngineError(
                "Experiment blocked: look-ahead date alignment was not checked"
            )
        if profile.duplicate_rate > 0:
            raise ExperimentEngineError(
                "Experiment blocked: duplicate entity/date keys remain"
            )
        if not profile.dataset_fingerprint:
            raise ExperimentDataMismatchError(
                "Experiment blocked: DataProfile has no dataset fingerprint"
            )
        actual_fingerprint = compute_dataset_fingerprint(active_config.path)
        if actual_fingerprint != profile.dataset_fingerprint:
            raise ExperimentDataMismatchError(
                "Experiment data changed after Data Preparation; rebuild DataProfile"
            )

        frame = load_financial_data(active_config.path)
        result = run_experiment(
            frame,
            state["model_design"],
            self.experiment_config,
            date_column=active_config.date_column,
            data_fingerprint=actual_fingerprint,
        )
        if self.artifact_directory is not None:
            result = save_experiment_artifact(
                result=result,
                model=state["model_design"],
                output_directory=self.artifact_directory,
            )
        return {"experiment_result": result, "current_stage": self.name}


def create_experiment_node(
    data_config: LocalDataConfig,
    experiment_config: ExperimentConfig | None = None,
    artifact_directory: str | Path | None = None,
    revision_data_configs: tuple[LocalDataConfig, ...] = (),
) -> ExperimentNode:
    return ExperimentNode(
        data_config=data_config,
        revision_data_configs=revision_data_configs,
        experiment_config=experiment_config or ExperimentConfig(),
        artifact_directory=(
            Path(artifact_directory) if artifact_directory is not None else None
        ),
    )


def experiment_node(state: ResearchState) -> dict:
    """Production wiring must inject data and experiment configuration."""
    raise NotImplementedError("Inject an Experiment node through workflow wiring")
