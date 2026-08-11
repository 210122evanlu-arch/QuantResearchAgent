"""Objective profile of the dataset prepared for an experiment."""

from datetime import date

from pydantic import BaseModel, Field, model_validator

from schemas.enums import DataFrequency


class DataProfile(BaseModel):
    data_sources: list[str]
    start_date: date
    end_date: date
    frequency: DataFrequency
    universe: str
    sample_size: int = Field(ge=0)
    variables: list[str]
    missing_rate: float = Field(ge=0, le=1)
    duplicate_rate: float = Field(ge=0, le=1)
    outlier_handling: str
    look_ahead_bias_checked: bool
    survivorship_bias_checked: bool
    column_missing_rates: dict[str, float] = Field(default_factory=dict)
    duplicate_key_columns: list[str] = Field(default_factory=list)
    dataset_fingerprint: str | None = None
    bias_check_details: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sample_period(self) -> "DataProfile":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be earlier than start_date")
        invalid_columns = [
            name
            for name, rate in self.column_missing_rates.items()
            if not 0 <= rate <= 1
        ]
        if invalid_columns:
            raise ValueError(
                "column missing rates must be between 0 and 1: "
                + ", ".join(invalid_columns)
            )
        return self
