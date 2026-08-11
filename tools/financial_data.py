"""Local financial dataset loading, validation, and objective profiling."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

from schemas.data_profile import DataProfile
from schemas.enums import DataFrequency
from schemas.model_design import ModelDesign


class FinancialDataError(ValueError):
    """Base error for unusable financial datasets."""


class MissingModelVariablesError(FinancialDataError):
    """Raised when the dataset cannot supply every designed model variable."""


class LookAheadBiasError(FinancialDataError):
    """Raised when target dates do not occur after feature observation dates."""


class DataProfileProvider(Protocol):
    """Adapter contract for local files and future licensed data sources."""

    def build_profile(self, model: ModelDesign) -> DataProfile:
        """Return an objectively computed profile for the supplied model."""


@dataclass(frozen=True)
class LocalDataConfig:
    path: Path
    date_column: str
    target_date_column: str
    frequency: DataFrequency
    universe: str
    entity_column: str | None = None
    outlier_handling: str = "none"
    survivorship_policy: str | None = None


@dataclass(frozen=True)
class LocalDataProfileProvider:
    """CSV/Parquet implementation of the data-profile adapter contract."""

    config: LocalDataConfig

    def build_profile(self, model: ModelDesign) -> DataProfile:
        return build_data_profile(self.config, model)


def load_financial_data(path: str | Path) -> pd.DataFrame:
    """Load a local CSV or Parquet dataset without modifying it."""
    source = Path(path)
    if not source.is_file():
        raise FinancialDataError(f"Financial data file does not exist: {source}")
    suffix = source.suffix.casefold()
    if suffix == ".csv":
        frame = pd.read_csv(source)
    elif suffix in {".parquet", ".pq"}:
        try:
            frame = pd.read_parquet(source)
        except ImportError as exc:
            raise FinancialDataError(
                "Parquet support requires pyarrow; install project requirements"
            ) from exc
    else:
        raise FinancialDataError("Only CSV and Parquet data files are supported")
    if frame.empty:
        raise FinancialDataError("Financial dataset is empty")
    return frame


def _required_model_variables(model: ModelDesign) -> list[str]:
    return [
        model.dependent_variable.name,
        *(variable.name for variable in model.independent_variables),
        *(variable.name for variable in model.control_variables),
    ]


def compute_dataset_fingerprint(path: str | Path) -> str:
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def build_data_profile(config: LocalDataConfig, model: ModelDesign) -> DataProfile:
    """Compute a DataProfile and fail closed on missing fields or date leakage."""
    frame = load_financial_data(config.path)
    required = _required_model_variables(model)
    required_columns = {
        *required,
        config.date_column,
        config.target_date_column,
    }
    if config.entity_column:
        required_columns.add(config.entity_column)
    missing_columns = sorted(required_columns.difference(frame.columns))
    if missing_columns:
        raise MissingModelVariablesError(
            "Dataset is missing required columns: " + ", ".join(missing_columns)
        )

    observation_dates = pd.to_datetime(frame[config.date_column], errors="coerce")
    target_dates = pd.to_datetime(frame[config.target_date_column], errors="coerce")
    if observation_dates.isna().any() or target_dates.isna().any():
        raise FinancialDataError("Date columns contain missing or invalid values")
    invalid_targets = target_dates <= observation_dates
    if invalid_targets.any():
        raise LookAheadBiasError(
            "Target dates must be strictly later than feature observation dates"
        )

    key_columns = [config.date_column]
    if config.entity_column:
        key_columns.insert(0, config.entity_column)
    if frame[key_columns].isna().any().any():
        raise FinancialDataError("Entity/date key columns contain missing values")
    duplicate_rate = float(frame.duplicated(subset=key_columns).mean())
    missing_by_column = {
        str(column): float(frame[column].isna().mean()) for column in frame.columns
    }
    missing_rate = float(frame[required].isna().to_numpy().mean())
    survivorship_policy = (
        config.survivorship_policy.strip() if config.survivorship_policy else None
    )
    survivorship_checked = bool(survivorship_policy)
    bias_details = [
        f"Verified {config.target_date_column} > {config.date_column} for every row."
    ]
    if survivorship_checked:
        bias_details.append(survivorship_policy or "")
    else:
        bias_details.append("Survivorship-bias policy was not supplied.")

    return DataProfile(
        data_sources=[str(config.path.resolve())],
        start_date=observation_dates.min().date(),
        end_date=observation_dates.max().date(),
        frequency=config.frequency,
        universe=config.universe,
        sample_size=len(frame),
        variables=list(frame.columns),
        missing_rate=missing_rate,
        duplicate_rate=duplicate_rate,
        outlier_handling=config.outlier_handling,
        look_ahead_bias_checked=True,
        survivorship_bias_checked=survivorship_checked,
        column_missing_rates=missing_by_column,
        duplicate_key_columns=key_columns,
        dataset_fingerprint=compute_dataset_fingerprint(config.path),
        bias_check_details=bias_details,
    )
