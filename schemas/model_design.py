"""Structured financial model specification."""

from pydantic import BaseModel, Field, model_validator

from schemas.common import VariableDefinition
from schemas.enums import Estimator, VariableRole


class ModelDesign(BaseModel):
    model_name: str
    formula: str
    estimator: Estimator
    dependent_variable: VariableDefinition
    independent_variables: list[VariableDefinition] = Field(min_length=1)
    control_variables: list[VariableDefinition]
    fixed_effects: list[str]
    standard_error_method: str
    assumptions: list[str]
    endogeneity_strategy: list[str]
    limitations: list[str]

    @model_validator(mode="after")
    def validate_variable_roles_and_names(self) -> "ModelDesign":
        if self.dependent_variable.role != VariableRole.DEPENDENT:
            raise ValueError("dependent_variable must have role='dependent'")
        if any(
            variable.role != VariableRole.INDEPENDENT
            for variable in self.independent_variables
        ):
            raise ValueError("independent_variables must have role='independent'")
        if any(
            variable.role != VariableRole.CONTROL for variable in self.control_variables
        ):
            raise ValueError("control_variables must have role='control'")

        names = [
            self.dependent_variable.name,
            *(variable.name for variable in self.independent_variables),
            *(variable.name for variable in self.control_variables),
        ]
        normalised = [name.strip().casefold() for name in names]
        if len(normalised) != len(set(normalised)):
            raise ValueError("model variable names must be unique")
        return self
