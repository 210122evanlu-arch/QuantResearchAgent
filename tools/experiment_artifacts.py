"""Reproducible JSON artifact persistence for deterministic experiments."""

import hashlib
import json
from pathlib import Path

from schemas.experiment import ExperimentResult
from schemas.model_design import ModelDesign


def save_experiment_artifact(
    *,
    result: ExperimentResult,
    model: ModelDesign,
    output_directory: str | Path,
) -> ExperimentResult:
    """Save model, data version, parameters, and results under a stable run ID."""
    if result.estimator is None:
        raise ValueError("Experiment artifact requires a concrete estimator")
    model_payload = model.model_dump(mode="json")
    identity = json.dumps(
        {
            "model": model_payload,
            "data_fingerprint": result.data_fingerprint,
            "parameters": result.parameters,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    run_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.estimator.value}_{run_id}.json"
    result_with_path = result.model_copy(update={"artifact_path": str(path.resolve())})
    payload = {
        "run_id": run_id,
        "model_design": model_payload,
        "experiment_result": result_with_path.model_dump(mode="json"),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return result_with_path
