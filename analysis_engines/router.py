"""Method router for financial, market, quantitative, and advisory engines."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from schemas.enums import AnalysisMethod
from schemas.platform import AnalysisArtifact

AnalysisEngine = Callable[[Mapping[str, Any]], AnalysisArtifact]


class AnalysisEngineUnavailable(LookupError):
    """Raised instead of silently substituting an inappropriate method."""


@dataclass
class AnalysisEngineRegistry:
    engines: dict[AnalysisMethod, AnalysisEngine] = field(default_factory=dict)

    def register(self, method: AnalysisMethod, engine: AnalysisEngine) -> None:
        self.engines[method] = engine

    def execute(
        self, method: AnalysisMethod, context: Mapping[str, Any]
    ) -> AnalysisArtifact:
        engine = self.engines.get(method)
        if engine is None:
            raise AnalysisEngineUnavailable(
                f"Analysis engine is not registered: {method.value}"
            )
        artifact = engine(context)
        if artifact.method != method:
            raise ValueError(
                f"Engine returned method={artifact.method.value}; expected={method.value}"
            )
        return artifact
