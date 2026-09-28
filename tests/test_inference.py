"""Inference mechanics only; synthetic fixtures are never performance evidence.

The tiny estimator lives in pytest's temporary directory and is not a release
artifact. No official data, training command, or held-out evaluation is used.
"""
from copy import deepcopy
import json

import joblib
import numpy as np
import pandas as pd
import pytest
from xgboost import XGBClassifier

from caresense.calibration import SigmoidCalibrator
from caresense.features import FEATURE_VERSION, build_features, feature_dictionary
from caresense.predict import CareSensePredictor, normalize_history, predict
from caresense.preprocessing import FeaturePipeline
from caresense.risk import risk_output, risk_tier
from caresense.schema import INPUT_COLUMNS
from caresense.simulation import PRESET_NAMES, SimulationStore, preset_histories


@pytest.fixture(scope="module")
def bundle_path(tmp_path_factory):
    """Save the same contract as train.py with explicitly synthetic mechanics data."""
    rows = []
    labels = []
    for i in range(48):
        high = i % 2
        rows.append(build_features(normalize_history({
            "ICULOS": 1, "HR": 70 + 55 * high + i % 7,
            "MAP": 85 - 25 * high, "Temp": 36.8 + 2 * high,
            "Resp": 16 + 12 * high, "Lactate": 1 + 3 * high,
        })))
        labels.append(high)
    features = pd.concat(rows, ignore_index=True)
    pipeline = FeaturePipeline().fit(features)
    model = XGBClassifier(n_estimators=8, max_depth=2, learning_rate=.2,
                          min_child_weight=1, n_jobs=1, random_state=19,
                          objective="binary:logistic", tree_method="hist")
    model.fit(features, np.asarray(labels))
    # A separate toy calibration fixture verifies serialization and transforms;
    # these values have no clinical or model-performance interpretation.
    calibrator = SigmoidCalibrator().fit([.1, .2, .3, .7, .8, .9], [0, 0, 0, 1, 1, 1])
    bundle = {
        "model": model, "calibrator": calibrator,
        "feature_pipeline": pipeline, "feature_names": list(feature_dictionary()),
        "metadata": {"model_version": "synthetic-test-fixture-only",
                     "feature_version": FEATURE_VERSION, "estimator": "xgboost",
                     "target_framing": "Synthetic mechanics fixture; no clinical claim"},
        "thresholds": {"research_max_f1": {"threshold": .5}},
    }
    path = tmp_path_factory.mktemp("mechanics-model") / "fixture.joblib"
    joblib.dump(bundle, path)
    return path


@pytest.fixture(scope="module")
def predictor(bundle_path):
    return CareSensePredictor(bundle_path=bundle_path)


def test_saved_training_contract_loads_and_probabilities_are_calibrated(predictor):
    history = preset_histories()["demo-3"]["history"]
    untouched = deepcopy(history)
    features = build_features(normalize_history(history))
    raw_p = predictor.model.predict_proba(predictor.pipeline.transform_features(features.iloc[-1:]))[:, 1]
    expected = float(predictor.calibrator.predict(raw_p)[0])
    result = predictor.predict(history, top_n=4)
    assert result["risk_probability"] == pytest.approx(expected)
    assert result["risk_tier"] == risk_tier(expected)
    assert result["icu_hour"] == 12
    assert result["model_version"] == "synthetic-test-fixture-only"
    assert result["feature_version"] == FEATURE_VERSION
    assert result["clinically_validated"] is False
    assert history == untouched
    json.dumps(result, allow_nan=False)


def test_real_shap_recovers_margin_and_reports_units(predictor):
    result = predictor.predict({"ICULOS": 1, "HR": 130, "Lactate": 4}, top_n=5)
    explanation = result["explanation"]
    assert explanation["method"] == "TreeExplainer"
    assert explanation["units"] == "uncalibrated log odds"
    assert explanation["feature_count"] == len(feature_dictionary())
    assert explanation["base_value"] + explanation["sum_all_contributions"] == pytest.approx(
        explanation["model_margin"], abs=1e-3)
    assert explanation["additivity_absolute_error"] <= 1e-3
    assert len(result["top_features"]) == 5
    assert [item["magnitude"] for item in result["top_features"]] == sorted(
        [item["magnitude"] for item in result["top_features"]], reverse=True)
    for item in result["top_features"]:
        assert item["feature"] in feature_dictionary()
        assert item["magnitude"] == abs(item["shap_value"])
        assert item["units"] == "uncalibrated log odds"
        expected = ("increases risk" if item["shap_value"] > 0 else
                    "decreases risk" if item["shap_value"] < 0 else "no contribution")
        assert item["direction"] == expected


@pytest.mark.parametrize("top_n", [0, -1, 10000, 1.5, True, "3"])
def test_invalid_explanation_count_is_rejected(predictor, top_n):
    with pytest.raises(ValueError, match="top_n"):
        predictor.predict({"ICULOS": 1, "HR": 85}, top_n=top_n)


def test_batch_trajectory_equals_each_causal_prefix(predictor):
    history = [
        {"ICULOS": 1},
        {"ICULOS": 2, "HR": 75},
        {"ICULOS": 4, "HR": 95, "Lactate": 2},
        {"ICULOS": 7, "HR": 130, "Lactate": 4},
        {"ICULOS": 15},
    ]
    trajectory = predictor.trajectory(history)
    assert trajectory["rows"][0]["status"] == "withheld"
    assert trajectory["rows"][0]["risk_probability"] is None
    for end in range(2, len(history) + 1):
        standalone = predictor.predict(history[:end], top_n=1)
        batched = trajectory["rows"][end - 1]
        assert batched["risk_probability"] == pytest.approx(standalone["risk_probability"])
        assert batched["risk_tier"] == standalone["risk_tier"]
        assert batched["current_values"] == standalone["current_values"]
    # Appending an extreme future record cannot revise an earlier probability.
    extended = predictor.trajectory(history + [{"ICULOS": 16, "HR": 200}])
    assert extended["rows"][:-1] == trajectory["rows"]
    json.dumps(trajectory, allow_nan=False)


def test_missing_and_invalid_measurements_are_visible_and_not_zero_filled(predictor):
    history = [{"ICULOS": 1, "HR": 80}, {"ICULOS": 4, "HR": 999}]
    response = predictor.features(history)
    current = response["rows"][-1]
    assert current["HR"] is None
    assert current["HR_last"] == 80
    assert current["HR_out_of_range"] == 1
    assert current["Lactate"] is None
    assert current["Lactate_missing"] == 1
    assert current["Lactate_count_6h"] == 0
    assert response["current_values"]["HR"] == 999
    assert {"gaps_in_hourly_history", "out_of_range_HR_treated_as_missing",
            "no_current_valid_clinical_measurements", "current_Lactate_missing",
            "no_recent_Lactate_measurement", "all_laboratory_values_missing"}.issubset(
                response["data_quality_flags"])
    assert response["feature_names"] == list(feature_dictionary())
    json.dumps(response, allow_nan=False)


@pytest.mark.parametrize("history", [
    [{"ICULOS": 1}], [{"ICULOS": 1, "HR": 999}],
    [{"ICULOS": 1, "Age": 70, "Gender": 1}],
])
def test_history_without_valid_clinical_measurement_withholds_prediction(predictor, history):
    for method in [predictor.predict, predictor.features, predictor.trajectory]:
        with pytest.raises(ValueError, match="no valid vital or laboratory"):
            method(history)


@pytest.mark.parametrize("history, message", [
    ([], "at least one row"),
    ([{"HR": 80}], "ICULOS is required"),
    ([{"ICULOS": 1, "SepsisLabel": 1}], "forbidden"),
    ([{"ICULOS": 1, "risk_probability": .9}], "forbidden"),
    ([{"ICULOS": 1}, {"ICULOS": 1}], "strictly increasing"),
    ([{"ICULOS": 2}, {"ICULOS": 1}], "strictly increasing"),
    ([{"ICULOS": 0}], "positive"),
    ([{"ICULOS": 1.5}], "integer"),
    ([{"ICULOS": None}], "finite"),
    ([{"ICULOS": 10001}], "maximum"),
    ([{"ICULOS": 1, "HR": float("inf")}], "Infinite"),
    ([{"ICULOS": 1, "HR": "unmeasured"}], "numeric or null"),
    ([{"ICULOS": 1, "Gender": 2}], "Gender"),
    ([{"ICULOS": True, "HR": 80}], "booleans"),
    ([{"ICULOS": "1", "HR": 80}], "numeric strings"),
    ([{"ICULOS": 1, "HR": True}], "booleans"),
    ([{"ICULOS": 1, "HR": "80"}], "numeric strings"),
    ([{"ICULOS": 1, "HR": [80]}], "numeric or null"),
    ([{"ICULOS": 1, "HR": {"value": 80}}], "numeric or null"),
])
def test_raw_history_validation_rejects_unsafe_input(history, message):
    with pytest.raises(ValueError, match=message):
        normalize_history(history)


def test_normalization_expands_sparse_history_and_rejects_duplicate_columns():
    normalized = normalize_history({"ICULOS": 1, "HR": 85})
    assert list(normalized.columns) == INPUT_COLUMNS
    assert normalized.loc[0, "HR"] == 85
    assert pd.isna(normalized.loc[0, "Lactate"])
    with pytest.raises(ValueError, match="Duplicate"):
        normalize_history(pd.DataFrame([[1, 80, 90]], columns=["ICULOS", "HR", "HR"]))


@pytest.mark.parametrize("mutation, message", [
    ("missing_model", "Incomplete"),
    ("feature_order", "schema/order"),
    ("feature_version", "feature version"),
    ("estimator_type", "XGBoost"),
    ("calibration_decreasing", "strictly increasing"),
    ("calibration_nonfinite", "strictly increasing"),
])
def test_incompatible_bundles_fail_closed(bundle_path, tmp_path, mutation, message):
    bundle = joblib.load(bundle_path)
    if mutation == "missing_model":
        del bundle["model"]
    elif mutation == "feature_order":
        bundle["feature_names"] = list(reversed(bundle["feature_names"]))
    elif mutation == "feature_version":
        bundle["metadata"]["feature_version"] = "obsolete"
    elif mutation == "estimator_type":
        bundle["metadata"]["estimator"] = "random_forest"
    elif mutation == "calibration_decreasing":
        bundle["calibrator"].model_.coef_[0, 0] = -1
    elif mutation == "calibration_nonfinite":
        bundle["calibrator"].model_.intercept_[0] = np.nan
    path = tmp_path / "invalid.pkl"
    joblib.dump(bundle, path)
    with pytest.raises(ValueError, match=message):
        CareSensePredictor(bundle_path=path)


def test_missing_artifact_never_produces_a_fallback_prediction(tmp_path):
    with pytest.raises(FileNotFoundError, match="No prediction was produced"):
        predict({"ICULOS": 1, "HR": 80}, project_dir=tmp_path)
    with pytest.raises(ValueError, match="not both"):
        CareSensePredictor(tmp_path, bundle_path=tmp_path / "model.pkl")


@pytest.mark.parametrize("probability, expected", [
    (0, "Lower"), (np.nextafter(.3, 0), "Lower"), (.3, "Watch"),
    (np.nextafter(.5, 0), "Watch"), (.5, "Elevated"), (.75, "Elevated"),
    (np.nextafter(.75, 1), "Critical"), (1, "Critical"),
])
def test_risk_boundary_semantics(probability, expected):
    assert risk_tier(probability) == expected
    output = risk_output(probability)
    assert output["risk_probability"] == probability
    assert output["risk_tier"] == expected


@pytest.mark.parametrize("probability", [None, True, np.bool_(True), -.01, 1.01, np.nan, np.inf, "bad", "0.5", np.array([.5])])
def test_invalid_risk_probabilities_are_rejected(probability):
    with pytest.raises(ValueError, match="finite number"):
        risk_output(probability)


def test_simulation_store_has_five_editable_presets_and_copy_isolation():
    store = SimulationStore()
    assert [p["id"] for p in store.list_patients()] == list(PRESET_NAMES)
    assert all(p["synthetic"] and p["is_preset"] for p in store.list_patients())
    snapshot = store.get("demo-1")
    snapshot["history"][0]["HR"] = -999
    assert store.get("demo-1")["history"][0]["HR"] != -999
    store.update_history("demo-1", [{"ICULOS": 1, "HR": 90}])
    store.append("demo-1", {"ICULOS": 2, "HR": 95})
    assert len(store.get("demo-1")["history"]) == 2
    with pytest.raises(ValueError, match="protected"):
        store.delete("demo-1")
    store.reset()
    assert len(store.list_patients()) == 5
    assert len(store.get("demo-1")["history"]) == 12


def test_custom_simulation_crud_rejects_invalid_updates_atomically():
    store = SimulationStore()
    added = store.add("  Mechanics patient  ", [{"ICULOS": 1, "HR": 80}])
    patient_id = added["id"]
    assert added["name"] == "Mechanics patient"
    assert added["synthetic"] is True and added["is_preset"] is False
    before = store.get(patient_id)
    with pytest.raises(ValueError, match="strictly increasing"):
        store.append(patient_id, {"ICULOS": 1, "HR": 90})
    assert store.get(patient_id) == before
    with pytest.raises(ValueError, match="forbidden"):
        store.update_history(patient_id, [{"ICULOS": 1, "SepsisLabel": 1}])
    assert store.get(patient_id) == before
    store.delete(patient_id)
    with pytest.raises(KeyError, match="Unknown patient"):
        store.get(patient_id)
    with pytest.raises(ValueError, match="display name"):
        store.add(" ", [{"ICULOS": 1, "HR": 80}])


def test_simulation_uses_saved_predictor_for_each_preset(predictor):
    store = SimulationStore()
    for patient in store.list_patients():
        result = store.predict(patient["id"], predictor, top_n=2)
        expected = predictor.predict(store.get(patient["id"])["history"], top_n=2)
        assert result["patient_id"] == patient["id"]
        assert result["synthetic"] is True
        assert result["risk_probability"] == expected["risk_probability"]
        assert result["top_features"] == expected["top_features"]
        json.dumps(result, allow_nan=False)


def test_numpy_numeric_and_nullable_dataframe_inputs_remain_supported():
    data = pd.DataFrame({"ICULOS": pd.Series([1, 2], dtype="Int64"),
                         "HR": pd.Series([80., pd.NA], dtype="Float64")})
    result = normalize_history(data)
    assert result["ICULOS"].tolist() == [1., 2.]
    assert result.loc[0, "HR"] == 80
    assert pd.isna(result.loc[1, "HR"])
    with pytest.raises(ValueError, match="booleans"):
        normalize_history({"ICULOS": np.int64(1), "HR": np.bool_(True)})
    assert normalize_history({"ICULOS": np.int64(1), "HR": np.float32(80)}).loc[0, "HR"] == 80
