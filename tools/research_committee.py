"""Deterministic model-risk and research-quality policy checks."""

from dataclasses import dataclass, field

from schemas.data_profile import DataProfile
from schemas.enums import (
    ExpectedDirection,
    IssueSeverity,
    ProblemType,
    ReviewIssueOrigin,
)
from schemas.experiment import ExperimentResult
from schemas.model_design import ModelDesign
from schemas.review import ReviewIssue


@dataclass(frozen=True)
class ReviewPolicyConfig:
    """Risk-based committee thresholds; these are project policy, not regulation."""

    maximum_missing_rate: float = 0.05
    minimum_observations_per_parameter: float = 10.0
    require_survivorship_bias_check: bool = True
    require_robustness_checks: bool = True
    failed_robustness_requires_revision: bool = True

    def __post_init__(self) -> None:
        if not 0 <= self.maximum_missing_rate <= 1:
            raise ValueError("maximum_missing_rate must be between 0 and 1")
        if self.minimum_observations_per_parameter <= 0:
            raise ValueError("minimum_observations_per_parameter must be positive")


@dataclass(frozen=True)
class PolicyAssessment:
    strengths: list[str] = field(default_factory=list)
    issues: list[ReviewIssue] = field(default_factory=list)


def _issue(
    *,
    rule_id: str,
    category: str,
    problem_type: ProblemType,
    severity: IssueSeverity,
    description: str,
    recommendation: str,
    evidence: list[str],
    blocking: bool = True,
) -> ReviewIssue:
    return ReviewIssue(
        rule_id=rule_id,
        category=category,
        problem_type=problem_type,
        severity=severity,
        description=description,
        recommendation=recommendation,
        evidence=evidence,
        origin=ReviewIssueOrigin.POLICY,
        blocking=blocking,
    )


def evaluate_research_policy(
    model: ModelDesign,
    data: DataProfile,
    experiment: ExperimentResult,
    config: ReviewPolicyConfig,
) -> PolicyAssessment:
    """Evaluate only facts present in structured research artifacts."""
    strengths: list[str] = []
    issues: list[ReviewIssue] = []

    if data.look_ahead_bias_checked:
        strengths.append("Target-date alignment check was completed.")
    else:
        issues.append(
            _issue(
                rule_id="DATA_LOOKAHEAD_001",
                category="look_ahead_bias",
                problem_type=ProblemType.DATA_ISSUE,
                severity=IssueSeverity.CRITICAL,
                description="Look-ahead date alignment was not verified.",
                recommendation="Rebuild the dataset with auditable feature and target dates.",
                evidence=["data_profile.look_ahead_bias_checked=false"],
            )
        )

    if data.duplicate_rate > 0:
        issues.append(
            _issue(
                rule_id="DATA_DUPLICATE_001",
                category="duplicate_keys",
                problem_type=ProblemType.DATA_ISSUE,
                severity=IssueSeverity.HIGH,
                description="Duplicate entity/date observations remain in the sample.",
                recommendation="Resolve duplicate keys and regenerate the data profile.",
                evidence=[f"data_profile.duplicate_rate={data.duplicate_rate:.6f}"],
            )
        )
    else:
        strengths.append("No duplicate entity/date keys were reported.")

    if data.missing_rate > config.maximum_missing_rate:
        issues.append(
            _issue(
                rule_id="DATA_MISSING_001",
                category="missing_data",
                problem_type=ProblemType.DATA_ISSUE,
                severity=IssueSeverity.HIGH,
                description="Model-variable missingness exceeds committee policy.",
                recommendation="Explain, impute, or narrow the sample and rerun preparation.",
                evidence=[
                    f"data_profile.missing_rate={data.missing_rate:.6f}",
                    f"policy.maximum_missing_rate={config.maximum_missing_rate:.6f}",
                ],
            )
        )
    else:
        strengths.append("Model-variable missingness is within committee policy.")

    if config.require_survivorship_bias_check and not data.survivorship_bias_checked:
        issues.append(
            _issue(
                rule_id="DATA_SURVIVORSHIP_001",
                category="survivorship_bias",
                problem_type=ProblemType.DATA_ISSUE,
                severity=IssueSeverity.HIGH,
                description="The sample has no documented survivorship-bias review.",
                recommendation="Document delisting and historical-universe treatment.",
                evidence=["data_profile.survivorship_bias_checked=false"],
            )
        )

    if (
        not data.dataset_fingerprint
        or not experiment.data_fingerprint
        or data.dataset_fingerprint != experiment.data_fingerprint
    ):
        issues.append(
            _issue(
                rule_id="EXP_DATA_VERSION_001",
                category="data_version_mismatch",
                problem_type=ProblemType.EXPERIMENT_ISSUE,
                severity=IssueSeverity.CRITICAL,
                description="Experiment data version is missing or differs from DataProfile.",
                recommendation="Rerun the experiment from the profiled data version.",
                evidence=[
                    f"data_profile.dataset_fingerprint={data.dataset_fingerprint}",
                    f"experiment_result.data_fingerprint={experiment.data_fingerprint}",
                ],
            )
        )
    else:
        strengths.append("Experiment and DataProfile use the same data fingerprint.")

    parameter_count = (
        1 + len(model.independent_variables) + len(model.control_variables)
    )
    observations_per_parameter = experiment.sample_size / parameter_count
    if observations_per_parameter < config.minimum_observations_per_parameter:
        issues.append(
            _issue(
                rule_id="EXP_CAPACITY_001",
                category="sample_capacity",
                problem_type=ProblemType.EXPERIMENT_ISSUE,
                severity=IssueSeverity.HIGH,
                description="The estimation sample is small relative to parameter count.",
                recommendation="Increase the sample or simplify the specification.",
                evidence=[
                    f"experiment_result.sample_size={experiment.sample_size}",
                    f"model_parameter_count={parameter_count}",
                    f"observations_per_parameter={observations_per_parameter:.3f}",
                ],
            )
        )
    else:
        strengths.append("Sample size meets the observations-per-parameter policy.")

    if config.require_robustness_checks and not experiment.robustness_checks:
        issues.append(
            _issue(
                rule_id="EXP_ROBUSTNESS_001",
                category="missing_robustness",
                problem_type=ProblemType.EXPERIMENT_ISSUE,
                severity=IssueSeverity.HIGH,
                description="No robustness check was reported.",
                recommendation="Run at least one pre-specified sensitivity analysis.",
                evidence=["experiment_result.robustness_checks=[]"],
            )
        )
    elif experiment.robustness_checks:
        failed = [
            check.name for check in experiment.robustness_checks if not check.passed
        ]
        if failed:
            issues.append(
                _issue(
                    rule_id="EXP_ROBUSTNESS_002",
                    category="failed_robustness",
                    problem_type=ProblemType.EXPERIMENT_ISSUE,
                    severity=(
                        IssueSeverity.HIGH
                        if config.failed_robustness_requires_revision
                        else IssueSeverity.MEDIUM
                    ),
                    description="At least one robustness check failed.",
                    recommendation="Explain instability or revise and rerun the experiment.",
                    evidence=[f"failed_checks={', '.join(failed)}"],
                    blocking=config.failed_robustness_requires_revision,
                )
            )
        else:
            strengths.append("All reported robustness checks passed.")

    limitation_text = " ".join(model.limitations).casefold()
    if not model.limitations:
        issues.append(
            _issue(
                rule_id="MODEL_LIMITATIONS_001",
                category="undisclosed_limitations",
                problem_type=ProblemType.MODEL_ISSUE,
                severity=IssueSeverity.HIGH,
                description="ModelDesign contains no limitations disclosure.",
                recommendation="Document material assumptions and model limitations.",
                evidence=["model_design.limitations=[]"],
            )
        )
    if "endogen" in limitation_text and not model.endogeneity_strategy:
        issues.append(
            _issue(
                rule_id="MODEL_ENDOGENEITY_001",
                category="endogeneity",
                problem_type=ProblemType.MODEL_ISSUE,
                severity=IssueSeverity.HIGH,
                description="Endogeneity is disclosed but no mitigation strategy is specified.",
                recommendation="Add a defensible identification or sensitivity strategy.",
                evidence=["model_design.endogeneity_strategy=[]"],
            )
        )

    results_by_name = {
        result.variable.casefold(): result for result in experiment.statistical_results
    }
    for variable in model.independent_variables:
        result = results_by_name.get(variable.name.casefold())
        if result is None or not result.significant:
            continue
        expected = variable.expected_sign
        sign_conflict = (
            expected == ExpectedDirection.POSITIVE and result.coefficient < 0
        ) or (expected == ExpectedDirection.NEGATIVE and result.coefficient > 0)
        if sign_conflict:
            issues.append(
                _issue(
                    rule_id="MODEL_SIGN_001",
                    category="economic_sign_conflict",
                    problem_type=ProblemType.MODEL_ISSUE,
                    severity=IssueSeverity.MEDIUM,
                    description=(
                        f"{variable.name} is significant but has the opposite "
                        "sign from ModelDesign."
                    ),
                    recommendation="Interpret as contradictory evidence; do not relabel the sign.",
                    evidence=[
                        f"expected_sign={expected.value}",
                        f"coefficient={result.coefficient:.8g}",
                        f"p_value={result.p_value}",
                    ],
                    blocking=False,
                )
            )

    return PolicyAssessment(strengths=strengths, issues=issues)
