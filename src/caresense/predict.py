"""Reusable inference from a trusted, saved CareSense XGBoost bundle.

Each request rebuilds patient-local causal features from the supplied history.
No synthetic fallback, probability override, target column, or future record is
accepted. Joblib artifacts must be trusted local training outputs.
"""
from __future__ import annotations

import argparse
import json
from numbers import Real
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from .calibration import SigmoidCalibrator
from .explain import TreeShapExplainer
from .features import FEATURE_VERSION, build_features, feature_dictionary
from .preprocessing import FeaturePipeline
from .risk import PROTOTYPE_THRESHOLDS, risk_output
from .schema import INPUT_COLUMNS, LABS, VITALS, TARGET
from .validation import validate_patient_history


def normalize_history(patient_history) -> pd.DataFrame:
    """Accept raw records with optional missing measurements; ICULOS is required.

    Unknown fields (including SepsisLabel) are rejected before normalization.
    Missing published measurement fields are represented by NaN, never normal
    values. Rows must describe a single patient and be in increasing hour order.
    """
    if isinstance(patient_history, dict):
        patient_history = [patient_history]
    try:
        frame = pd.DataFrame(patient_history).copy()
    except (TypeError, ValueError) as exc:
        raise ValueError("Patient history must be a table or sequence of raw observation records") from exc
    if frame.empty:
        raise ValueError("Patient history must contain at least one row")
    if frame.columns.duplicated().any():
        raise ValueError("Duplicate raw column names")
    unknown = set(frame.columns) - set(INPUT_COLUMNS)
    if unknown:
        raise ValueError(f"Unknown or forbidden raw fields: {sorted(map(str, unknown))}; {TARGET} cannot enter inference")
    if "ICULOS" not in frame:
        raise ValueError("ICULOS is required for every observation")
    # Pandas numeric conversion accepts strings and booleans, but raw JSON
    # inputs must contain actual numbers or null. Check before coercion so a
    # malformed observation is never silently converted into a measurement.
    for value in frame.to_numpy(dtype=object).flat:
        if value is None or value is pd.NA:
            continue
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise ValueError("Measurements must be numeric or null; booleans and numeric strings are not accepted")
    frame = frame.reindex(columns=INPUT_COLUMNS)
    numeric = validate_patient_history(frame)
    if (numeric.ICULOS > 10000).any():
        raise ValueError("ICULOS exceeds the supported maximum of 10000 hours")
    return numeric


def _records(frame: pd.DataFrame) -> list[dict]:
    """JSON-safe measured or engineered values; missing stays null."""
    return [{str(key): (float(value) if pd.notna(value) else None) for key, value in row.items()}
            for row in frame.to_dict("records")]


def _quality_flags(raw: pd.DataFrame, features: pd.DataFrame) -> list[str]:
    flags = []
    if len(raw) < 2:
        flags.append("first_available_observation")
    if raw.ICULOS.iloc[-1] - raw.ICULOS.iloc[0] < 6:
        flags.append("less_than_six_hours_of_observed_history")
    if np.any(np.diff(raw.ICULOS) > 1):
        flags.append("gaps_in_hourly_history")
    if features.loc[:, LABS].isna().all(axis=None):
        flags.append("all_laboratory_values_missing")
    if features.iloc[-1][VITALS + LABS].isna().all():
        flags.append("no_current_valid_clinical_measurements")
    for name in ("Lactate", "WBC"):
        if pd.isna(features.iloc[-1][name]):
            flags.append(f"current_{name}_missing")
        if pd.isna(features.iloc[-1][f"{name}_last"]):
            flags.append(f"no_recent_{name}_measurement")
    for name in INPUT_COLUMNS:
        indicator = f"{name}_out_of_range"
        if indicator in features and features[indicator].any():
            flags.append(f"out_of_range_{name}_treated_as_missing")
    return flags


class CareSensePredictor:
    def __init__(self, project_dir: str | Path | None = None, *, bundle_path: str | Path | None = None):
        if project_dir is not None and bundle_path is not None:
            raise ValueError("Specify project_dir or bundle_path, not both")
        location = Path(bundle_path if bundle_path is not None else project_dir if project_dir is not None else Path(__file__).resolve().parents[2])
        self.bundle_path = location if location.suffix in {".pkl", ".joblib"} else location / "models" / "caresense_xgboost.pkl"
        if not self.bundle_path.is_file():
            raise FileNotFoundError(f"Trained CareSense bundle is missing: {self.bundle_path}. No prediction was produced.")
        bundle = joblib.load(self.bundle_path)
        if not isinstance(bundle, dict) or not {"model", "calibrator", "feature_pipeline", "feature_names", "metadata", "thresholds"}.issubset(bundle):
            raise ValueError("Incomplete CareSense model bundle")
        self.model, self.calibrator, self.pipeline = bundle["model"], bundle["calibrator"], bundle["feature_pipeline"]
        self.feature_names, self.metadata = list(bundle["feature_names"]), bundle["metadata"]
        if not isinstance(self.model, XGBClassifier) or not isinstance(self.calibrator, SigmoidCalibrator) or not isinstance(self.pipeline, FeaturePipeline):
            raise ValueError("Bundle must contain XGBClassifier, SigmoidCalibrator and FeaturePipeline")
        expected = list(feature_dictionary())
        if self.feature_names != expected or list(self.pipeline.get_feature_names_out()) != expected:
            raise ValueError("Saved feature schema/order does not match the current inference implementation")
        if getattr(self.pipeline, "feature_version_", None) != FEATURE_VERSION or self.metadata.get("feature_version") != FEATURE_VERSION:
            raise ValueError("Saved feature version does not match the current inference implementation")
        if not self.metadata.get("model_version") or self.metadata.get("estimator") != "xgboost":
            raise ValueError("Bundle metadata must identify a versioned XGBoost model")
        booster = self.model.get_booster()
        if booster.num_features() != len(expected) or (booster.feature_names is not None and booster.feature_names != expected):
            raise ValueError("Estimator feature schema does not match the saved pipeline")
        if not np.array_equal(self.model.classes_, [0, 1]):
            raise ValueError("Expected binary labels 0 and 1")
        calibration_model = getattr(self.calibrator, "model_", None)
        coefficient = np.asarray(getattr(calibration_model, "coef_", []), dtype=float)
        intercept = np.asarray(getattr(calibration_model, "intercept_", []), dtype=float)
        if coefficient.shape != (1, 1) or not np.isfinite(coefficient).all() or coefficient[0, 0] <= 0 or intercept.shape != (1,) or not np.isfinite(intercept).all():
            raise ValueError("A fitted, finite, strictly increasing sigmoid calibrator is required")
        self._explainer = None

    def _prepare(self, history) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
        raw = normalize_history(history)
        engineered = build_features(raw)
        if engineered.loc[:, VITALS + LABS].isna().all(axis=None):
            raise ValueError("Prediction withheld: the entire history has no valid vital or laboratory measurement")
        matrix = self.pipeline.transform_features(engineered)
        return raw, engineered, matrix

    def _probabilities(self, matrix: np.ndarray) -> np.ndarray:
        raw = np.asarray(self.model.predict_proba(matrix), dtype=float)
        if raw.shape != (len(matrix), 2) or not np.isfinite(raw).all() or np.any((raw < 0) | (raw > 1)):
            raise ValueError("Estimator returned invalid probabilities")
        probabilities = np.asarray(self.calibrator.predict(raw[:, 1]), dtype=float)
        if probabilities.shape != (len(matrix),) or not np.isfinite(probabilities).all() or np.any((probabilities < 0) | (probabilities > 1)):
            raise ValueError("Calibrator returned invalid probabilities")
        return probabilities

    def predict(self, patient_history, top_n: int = 10) -> dict:
        raw, features, matrix = self._prepare(patient_history)
        probability = self._probabilities(matrix[-1:])[0]
        if self._explainer is None:
            self._explainer = TreeShapExplainer(self.model, self.feature_names)
        explanation = self._explainer.explain(features.iloc[-1:], top_n=top_n)
        return {**risk_output(probability), "top_features": explanation["top_features"], "explanation": explanation,
                "current_values": _records(raw.iloc[-1:])[0], "icu_hour": int(raw.ICULOS.iloc[-1]),
                "model_version": self.metadata["model_version"], "feature_version": FEATURE_VERSION,
                "data_quality_flags": _quality_flags(raw, features), "thresholds": dict(PROTOTYPE_THRESHOLDS),
                "clinically_validated": False, "prediction_framing": self.metadata.get("target_framing"),
                "notice": "Research prototype: model-estimated risk supports clinical judgment and does not diagnose sepsis. Prototype risk tiers are not clinically validated."}

    def features(self, patient_history) -> dict:
        raw, features, _ = self._prepare(patient_history)
        return {"feature_version": FEATURE_VERSION, "feature_names": list(self.feature_names),
                "rows": _records(features), "current_values": _records(raw.iloc[-1:])[0],
                "data_quality_flags": _quality_flags(raw, features)}

    def trajectory(self, patient_history) -> dict:
        raw, features, matrix = self._prepare(patient_history)
        # build_features is causal: row t contains only data through t. A batch
        # prediction therefore equals repeated prefix predictions. Early empty
        # clinical prefixes are withheld just as a standalone request would be.
        available = np.isfinite(features.loc[:, VITALS + LABS].to_numpy()).any(axis=1)
        eligible = np.maximum.accumulate(available)
        probabilities = self._probabilities(matrix[eligible])
        iterator = iter(probabilities)
        measured = _records(raw)
        rows = []
        for index, hour in enumerate(raw.ICULOS):
            common = {"icu_hour": int(hour), "current_values": measured[index]}
            if eligible[index]:
                rows.append({**common, **risk_output(next(iterator))})
            else:
                rows.append({**common, "risk_probability": None, "risk_tier": None,
                             "risk_status": "Prediction withheld: no valid clinical history", "status": "withheld"})
        return {"model_version": self.metadata["model_version"], "feature_version": FEATURE_VERSION,
                "rows": rows, "clinically_validated": False}


def predict(patient_history, project_dir: str | Path | None = None, *, bundle_path: str | Path | None = None, top_n: int = 10) -> dict:
    return CareSensePredictor(project_dir, bundle_path=bundle_path).predict(patient_history, top_n=top_n)


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict from a trusted CareSense model and raw history JSON")
    parser.add_argument("history", type=Path, help="JSON array of raw hourly observation records")
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()
    history = json.loads(args.history.read_text(encoding="utf-8"))
    print(json.dumps(predict(history, args.project_dir, top_n=args.top_n), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
