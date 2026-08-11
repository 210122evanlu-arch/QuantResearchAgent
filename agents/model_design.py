"""Source-aware Model Design node."""

import json
import re
from dataclasses import dataclass

from agents.base import NodeInputError
from llm.protocol import StructuredLLM
from schemas.model_design import ModelDesign
from schemas.state import ResearchState

_SYSTEM_PROMPT = """You are a quantitative financial research model designer.
Translate the supplied research analysis into a transparent empirical model.
Use the exact dependent and independent variable names from the refined
hypotheses. Define variable roles, estimator, fixed effects, standard errors,
assumptions, endogeneity strategy, and limitations without claiming results.
The formula must explicitly contain every dependent, independent, and control
variable."""


class ModelDesignValidationError(ValueError):
    """Raised when a model cannot be mapped to its hypotheses or formula."""


def _formula_mentions(formula: str, variable: str) -> bool:
    return (
        re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(variable)}(?![A-Za-z0-9_])",
            formula,
            flags=re.IGNORECASE,
        )
        is not None
    )


@dataclass(frozen=True)
class ModelDesignNode:
    llm: StructuredLLM
    available_variables: tuple[str, ...] = ()
    name: str = "model_design"
    output_key: str = "model_design"
    output_schema: type[ModelDesign] = ModelDesign
    input_keys: tuple[str, ...] = ("research_analysis",)

    def __call__(self, state: ResearchState) -> dict:
        if "research_analysis" not in state:
            raise NodeInputError(
                "Node 'model_design' is missing state fields: research_analysis"
            )
        payload = {
            "research_analysis": state["research_analysis"].model_dump(mode="json"),
            "available_variables": list(self.available_variables),
        }
        if "model_design" in state and "review_result" in state:
            payload["previous_model_design"] = state["model_design"].model_dump(
                mode="json"
            )
            payload["review_feedback"] = state["review_result"].model_dump(mode="json")

        system_prompt = _SYSTEM_PROMPT + (
            "\nUse only the currently implemented estimators: ols or fama_macbeth."
        )
        if self.available_variables:
            variable_catalog = ", ".join(self.available_variables)
            system_prompt += (
                "\nUse exact dataset column names and select model variables only "
                f"from this catalog: {variable_catalog}."
            )
        design = self.llm.generate(
            schema=ModelDesign,
            system_prompt=system_prompt,
            user_prompt=(
                "Design or revise the empirical model using these artifacts.\n\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
            ),
            node_name=self.name,
        )
        analysis = state["research_analysis"]

        model_dependent = design.dependent_variable.name.casefold()
        model_independent = {
            variable.name.casefold() for variable in design.independent_variables
        }
        for hypothesis in analysis.refined_hypotheses:
            if hypothesis.dependent_variable.casefold() != model_dependent:
                raise ModelDesignValidationError(
                    f"Model omits hypothesis dependent variable: "
                    f"{hypothesis.dependent_variable}"
                )
            if hypothesis.independent_variable.casefold() not in model_independent:
                raise ModelDesignValidationError(
                    f"Model omits hypothesis independent variable: "
                    f"{hypothesis.independent_variable}"
                )

        variables = [
            design.dependent_variable,
            *design.independent_variables,
            *design.control_variables,
        ]
        missing_from_formula = [
            variable.name
            for variable in variables
            if not _formula_mentions(design.formula, variable.name)
        ]
        if missing_from_formula:
            raise ModelDesignValidationError(
                "Formula omits model variables: " + ", ".join(missing_from_formula)
            )
        return {"model_design": design, "current_stage": self.name}


def create_model_design_node(
    llm: StructuredLLM,
    available_variables: tuple[str, ...] = (),
) -> ModelDesignNode:
    return ModelDesignNode(llm=llm, available_variables=available_variables)


def model_design_node(state: ResearchState) -> dict:
    """Production wiring must inject a configured structured LLM."""
    raise NotImplementedError("Inject a Model Design node through workflow wiring")
