"""Verify saved official model inference without refitting or selecting settings."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import numpy as np
from xgboost import XGBClassifier

from .predict import CareSensePredictor
from .simulation import preset_histories


def verify(project_dir: Path) -> dict:
    started = perf_counter()
    frozen = json.loads((project_dir / "artifacts/frozen_decisions.json").read_text())
    hashes = frozen["frozen_artifact_sha256"]
    for relative, expected in hashes.items():
        actual = hashlib.sha256((project_dir / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Frozen artifact changed: {relative}")
    engine = CareSensePredictor(project_dir)
    reloaded = CareSensePredictor(project_dir)
    native = XGBClassifier()
    native.load_model(project_dir / "models/caresense_xgboost.json")
    predictions = {}
    max_prefix_difference = 0.0
    max_native_difference = 0.0
    max_additivity_error = 0.0
    for patient_id, patient in preset_histories().items():
        history = patient["history"]
        result = engine.predict(history)
        assert result == reloaded.predict(history), "Reloaded bundle output differs"
        trajectory = engine.trajectory(history)["rows"]
        for length, row in enumerate(trajectory, start=1):
            prefix = engine.predict(history[:length])
            difference = abs(prefix["risk_probability"] - row["risk_probability"])
            max_prefix_difference = max(max_prefix_difference, difference)
            assert difference < 1e-7, "Batch trajectory differs from causal prefix inference"
        _, _, matrix = engine._prepare(history)
        native_probability = engine.calibrator.predict(native.predict_proba(matrix)[:, 1])
        bundle_probability = engine._probabilities(matrix)
        difference = float(np.max(np.abs(native_probability - bundle_probability)))
        max_native_difference = max(max_native_difference, difference)
        assert difference < 1e-7, "Native JSON estimator differs from bundle estimator"
        explanation = result["explanation"]
        max_additivity_error = max(max_additivity_error, explanation["additivity_absolute_error"])
        predictions[patient_id] = {"name": patient["name"], "synthetic": True, **result}
    # Entirely absent clinical data is withheld, while absent labs are allowed.
    try:
        engine.predict([{"ICULOS": 1, "Age": 60}])
    except ValueError as exc:
        assert "withheld" in str(exc)
    else:
        raise AssertionError("Empty clinical history produced a prediction")
    no_labs = engine.predict([{"ICULOS": 1, "HR": 90}])
    assert "all_laboratory_values_missing" in no_labs["data_quality_flags"]
    result = {
        "status": "passed", "verified_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": perf_counter() - started,
        "model_version": engine.metadata["model_version"],
        "frozen_artifact_hashes_verified": len(hashes),
        "synthetic_patients": len(predictions), "causal_prefix_predictions": 60,
        "reload_exact_match": True, "native_json_max_probability_difference": max_native_difference,
        "trajectory_max_prefix_probability_difference": max_prefix_difference,
        "maximum_local_shap_additivity_error": max_additivity_error,
        "empty_clinical_history_withheld": True, "all_missing_labs_supported": True,
        "notice": "These are runtime correctness checks, not clinical performance estimates.",
    }
    reports = project_dir / "reports"
    (reports / "demo_predictions.json").write_text(json.dumps(predictions, indent=2, allow_nan=False), encoding="utf-8")
    (reports / "inference_checks.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parents[2])
    print(json.dumps(verify(parser.parse_args().project_dir), indent=2))


if __name__ == "__main__":
    main()
