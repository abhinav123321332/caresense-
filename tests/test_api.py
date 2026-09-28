"""API contract tests; the injected engine below tests HTTP mechanics only.

The deterministic probabilities in this file are never used by the application
or presented as trained model predictions. Real-bundle verification is separate.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from caresense.api import MAX_HISTORY_ROWS, _verify_completed_artifacts, create_app
from caresense.predict import _records, normalize_history
from caresense.risk import risk_output


PROJECT = Path(__file__).resolve().parents[1]


class MechanicsEngine:
    def __init__(self):
        self.calls = []

    def predict(self, history, top_n=10):
        self.calls.append(("predict", deepcopy(history), top_n))
        raw = normalize_history(history)
        current = _records(raw)[-1]
        if current["HR"] is None:
            raise ValueError("Prediction withheld: no test input HR")
        probability = current["HR"] / 200
        return {**risk_output(probability), "current_values": current,
                "model_version": "mechanics-test-only", "feature_version": "test",
                "top_features": [{"feature": "HR", "value": current["HR"], "shap_value": 0}],
                "explanation": {"test_only": True}, "clinically_validated": False}

    def features(self, history):
        self.calls.append(("features", deepcopy(history)))
        return {"rows": _records(normalize_history(history)), "feature_names": ["HR"]}

    def trajectory(self, history):
        self.calls.append(("trajectory", deepcopy(history)))
        return {"rows": [{"icu_hour": row["ICULOS"], **risk_output(row["HR"] / 200)} for row in history]}


@pytest.fixture
def client():
    return TestClient(create_app(PROJECT, predictor=MechanicsEngine()))


def read_history(client, patient_id="demo-1"):
    response = client.get("/vitals", params={"patient_id": patient_id})
    assert response.status_code == 200
    return response.json()


def create_user(client, history=None):
    response = client.post("/patients", json={"name": "My simulation", "history": history or [{"ICULOS": 1, "HR": 100}]})
    assert response.status_code == 201
    return response.json()


def test_five_presets_and_isolated_process_state(client):
    patients = client.get("/patients").json()["patients"]
    assert len(patients) == 5
    assert all(patient["is_preset"] and patient["synthetic"] for patient in patients)
    assert {p["id"] for p in patients} == {f"demo-{i}" for i in range(1, 6)}
    assert len(client.get("/vitals").json()["patients"]) == 5
    create_user(client)
    separate = TestClient(create_app(PROJECT, predictor=MechanicsEngine()))
    assert len(separate.get("/patients").json()["patients"]) == 5


def test_user_crud_and_protected_presets(client):
    for index in range(1, 6):
        assert client.delete(f"/patients/demo-{index}").status_code == 403
    user = create_user(client)
    assert user["synthetic"] and not user["is_preset"]
    assert client.delete(f"/patients/{user['id']}").json() == {"deleted": user["id"]}
    assert client.get("/vitals", params={"patient_id": user["id"]}).status_code == 404
    assert client.delete(f"/patients/{user['id']}").status_code == 404


def test_reset_restores_original_histories_and_removes_users(client):
    original = read_history(client)
    user = create_user(client)
    assert client.post("/vitals", json={"patient_id": "demo-1", "history": [{"ICULOS": 1, "HR": 140}]}).status_code == 200
    response = client.post("/reset")
    assert len(response.json()["patients"]) == 5
    assert read_history(client) == original
    assert client.get("/vitals", params={"patient_id": user["id"]}).status_code == 404


def test_prediction_explanation_features_trajectory_share_snapshot(client):
    user = create_user(client)
    patient_id = user["id"]
    paths = [("post", f"/patients/{patient_id}/predict"), ("get", f"/patients/{patient_id}/explain"),
             ("get", f"/patients/{patient_id}/features"), ("get", f"/patients/{patient_id}/trajectory"),
             ("get", f"/alert-status/{patient_id}")]
    results = [getattr(client, method)(path).json() for method, path in paths]
    assert all(result["history_sha256"] == user["history_sha256"] for result in results)
    assert all(result["patient_id"] == patient_id and result["synthetic"] for result in results)
    assert results[0]["risk_probability"] == results[1]["risk_probability"] == results[3]["rows"][-1]["risk_probability"]
    assert results[0]["top_features"] == results[1]["top_features"]
    assert {call[0] for call in client.app.state.predictor.calls} == {"predict", "features", "trajectory"}


def test_updates_recompute_prediction_and_shap_from_new_history(client):
    user = create_user(client)
    patient_id = user["id"]
    old = client.post(f"/patients/{patient_id}/predict").json()
    update = client.post("/vitals", json={"patient_id": patient_id, "observation": {"ICULOS": 2, "HR": 170}})
    assert update.status_code == 200
    new = client.get(f"/patients/{patient_id}/explain").json()
    assert old["history_sha256"] != new["history_sha256"] == update.json()["history_sha256"]
    assert old["risk_probability"] == .5 and new["risk_probability"] == .85
    assert new["current_values"]["HR"] == new["top_features"][0]["value"] == 170
    assert new["history_rows"] == 2


@pytest.mark.parametrize("hr,critical", [(59, False), (60, False), (100, False), (150, False), (151, True)])
def test_critical_reference_and_hardware_truth(client, hr, critical):
    user = create_user(client, [{"ICULOS": 1, "HR": hr}])
    result = client.get(f"/alert-status/{user['id']}").json()
    assert result["visual_alert"] is result["physical_alert_requested"] is critical
    assert result["hardware_delivery_confirmed"] is False
    assert result["hardware_status"] == "not_connected"
    if critical:
        assert result["clinical_reference"] == json.loads((PROJECT / "artifacts/clinical_reference.json").read_text(encoding="utf-8"))
        assert result["clinical_reference"]["patient_specific"] is False
        assert result["clinical_reference"]["automatic_treatment_orders"] is False
    else:
        assert result["clinical_reference"] is None


def test_critical_reference_missing_is_explicit(client):
    client.app.state.clinical_reference = None
    user = create_user(client, [{"ICULOS": 1, "HR": 170}])
    assert client.get(f"/alert-status/{user['id']}").status_code == 503


@pytest.mark.parametrize("history", [
    [], [{"HR": 80}], [{"ICULOS": 0, "HR": 80}], [{"ICULOS": 1.5, "HR": 80}],
    [{"ICULOS": 10001, "HR": 80}], [{"ICULOS": True, "HR": 80}],
    [{"ICULOS": 1, "HR": True}], [{"ICULOS": 1, "HR": "80"}],
    [{"ICULOS": "1", "HR": 80}], [{"ICULOS": 1, "HR": [80]}],
    [{"ICULOS": 1, "HR": {"value": 80}}], [{"ICULOS": 1, "HR": 80, "SepsisLabel": 1}],
    [{"ICULOS": 1, "HR": 10 ** 500}],
    [{"ICULOS": 1, "HR": 80, "unknown": 1}], [{"ICULOS": 1, "Gender": 2}],
    [{"ICULOS": 1, "HR": 80}, {"ICULOS": 1, "HR": 90}],
    [{"ICULOS": 2, "HR": 80}, {"ICULOS": 1, "HR": 90}],
])
def test_bad_history_rejected_before_mutation(client, history):
    original = read_history(client)
    response = client.post("/vitals", json={"patient_id": "demo-1", "history": history})
    assert response.status_code == 422
    assert read_history(client) == original
    response = client.post("/patients", json={"name": "Invalid", "history": history})
    assert response.status_code == 422
    assert len(client.get("/patients").json()["patients"]) == 5


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_tokens_rejected_safely(client, token):
    original = read_history(client)
    content = '{"patient_id":"demo-1","history":[{"ICULOS":1,"HR":' + token + '}]}'
    response = client.post("/vitals", content=content, headers={"content-type": "application/json"})
    assert response.status_code == 422
    assert "finite numbers or null" in response.json()["detail"]
    assert read_history(client) == original


def test_missing_values_remain_null_and_are_never_imputed_by_api(client):
    user = create_user(client, [{"ICULOS": 1, "HR": 80, "Lactate": None}])
    assert user["history"][0]["Lactate"] is None
    assert user["history"][0]["WBC"] is None
    assert user["history"][0]["HR"] == 80


@pytest.mark.parametrize("payload", [
    {"patient_id": "demo-1"},
    {"patient_id": "demo-1", "history": [{"ICULOS": 1}], "observation": {"ICULOS": 2}},
    {"patient_id": "demo-1", "history": [{"ICULOS": 1}], "unexpected": True},
    {"patient_id": 1, "observation": {"ICULOS": 13}},
])
def test_strict_vitals_envelope(client, payload):
    original = read_history(client)
    assert client.post("/vitals", json=payload).status_code == 422
    assert read_history(client) == original


@pytest.mark.parametrize("name", ["", " ", "x" * 121, True, 17])
def test_invalid_name_rejected_without_creating_patient(client, name):
    assert client.post("/patients", json={"name": name, "history": [{"ICULOS": 1}]}).status_code == 422
    assert len(client.get("/patients").json()["patients"]) == 5


def test_history_size_limit_including_append_is_atomic(client):
    history = [{"ICULOS": hour, "HR": 80} for hour in range(1, MAX_HISTORY_ROWS + 1)]
    user = create_user(client, history)
    original = read_history(client, user["id"])
    response = client.post("/vitals", json={"patient_id": user["id"], "observation": {"ICULOS": 10001, "HR": 80}})
    assert response.status_code == 422
    assert read_history(client, user["id"]) == original
    assert client.post("/patients", json={"name": "Too large", "history": history + [history[-1]]}).status_code == 422


@pytest.mark.parametrize("method,path", [
    ("get", "/patients/unknown/features"), ("get", "/patients/unknown/explain"),
    ("get", "/patients/unknown/trajectory"), ("post", "/patients/unknown/predict"),
    ("get", "/alert-status/unknown"), ("delete", "/patients/unknown"),
])
def test_unknown_patient_is_404(client, method, path):
    assert getattr(client, method)(path).status_code == 404


def test_unavailable_model_never_returns_fallback_predictions(tmp_path):
    client = TestClient(create_app(tmp_path))
    health = client.get("/health").json()
    assert health["status"] == "degraded" and health["model_available"] is False
    assert client.get("/patients").status_code == 200
    for method, path in [("post", "/patients/demo-1/predict"), ("get", "/patients/demo-1/explain"),
                         ("get", "/patients/demo-1/features"), ("get", "/patients/demo-1/trajectory"),
                         ("get", "/alert-status/demo-1")]:
        response = getattr(client, method)(path)
        assert response.status_code == 503
        assert "no prediction produced" in response.json()["detail"]["message"]


def test_prediction_withheld_and_internal_failure_have_explicit_status(client, monkeypatch):
    user = create_user(client, [{"ICULOS": 1}])
    assert client.post(f"/patients/{user['id']}/predict").status_code == 422
    def fail(*args, **kwargs):
        raise RuntimeError("broken test engine")
    monkeypatch.setattr(client.app.state.predictor, "predict", fail)
    response = client.post("/patients/demo-1/predict")
    assert response.status_code == 503
    assert "no prediction produced" in response.json()["detail"]


@pytest.mark.parametrize("top_n", [0, 177, "bad", 1.5])
def test_invalid_top_n_rejected(client, top_n):
    assert client.post("/patients/demo-1/predict", params={"top_n": top_n}).status_code == 422
    assert client.get("/patients/demo-1/explain", params={"top_n": top_n}).status_code == 422


def test_top_n_passed_to_same_engine_and_unexpected_body_rejected(client):
    assert client.post("/patients/demo-1/predict", params={"top_n": 3}).status_code == 200
    assert client.app.state.predictor.calls[-1][2] == 3
    assert client.post("/patients/demo-1/predict", json={"risk_probability": .9}).status_code == 422
    assert client.post("/reset", json={"delete_presets": True}).status_code == 422


@pytest.fixture
def completed_project(tmp_path):
    def save(relative, content):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content), encoding="utf-8")
    save("experiment_config.json", {"test": "mechanics"})
    relative_files = ["models/caresense_xgboost.pkl", "models/caresense_xgboost.json",
                      "artifacts/preprocessing_pipeline.pkl", "artifacts/feature_names.json",
                      "artifacts/feature_dictionary.json", "artifacts/model_metadata.json",
                      "artifacts/threshold_config.json", "artifacts/run_config.json"]
    for relative in relative_files:
        save(relative, {"test_only": relative})
    hashes = {relative: hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest() for relative in relative_files}
    config_hash = hashlib.sha256((tmp_path / "experiment_config.json").read_bytes()).hexdigest()
    frozen = {"status": "decisions_frozen", "config_sha256": config_hash, "frozen_artifact_sha256": hashes}
    save("artifacts/frozen_decisions.json", frozen)
    save("reports/training_status.json", {**frozen, "status": "completed"})
    save("reports/leakage_audit.json", {"status": "passed", "failures": [],
                                       "checks": {"saved_preprocessing_training_row_count_verified": True,
                                                  "frozen_configuration_hash": config_hash}})
    save("reports/model_metrics.json", {"completed_utc": "test", "models": {"xgboost": {}}})
    return tmp_path


def test_verify_complete_frozen_manifest_then_load(completed_project, monkeypatch):
    _verify_completed_artifacts(completed_project)
    calls = []
    def load(root):
        calls.append(root)
        return MechanicsEngine()
    monkeypatch.setattr("caresense.api.CareSensePredictor", load)
    app = create_app(completed_project)
    assert calls == [completed_project]
    assert TestClient(app).get("/health").json()["model_available"] is True


@pytest.mark.parametrize("relative,content", [
    ("experiment_config.json", {"altered": True}),
    ("models/caresense_xgboost.pkl", {"altered": True}),
    ("artifacts/feature_names.json", {"altered": True}),
    ("reports/training_status.json", {"status": "training"}),
    ("reports/leakage_audit.json", {"status": "passed_pretraining", "failures": []}),
    ("reports/leakage_audit.json", {"status": "passed", "failures": ["test failure"]}),
    ("reports/leakage_audit.json", {"status": "passed", "failures": [], "checks": {}}),
    ("reports/model_metrics.json", {"models": {"xgboost": {}}}),
    ("artifacts/frozen_decisions.json", {"status": "decisions_frozen", "frozen_artifact_sha256": {}}),
])
def test_bad_experiment_blocks_deserialization(completed_project, monkeypatch, relative, content):
    (completed_project / relative).write_text(json.dumps(content), encoding="utf-8")
    def forbidden(*args, **kwargs):
        pytest.fail("Unverified artifact was deserialized")
    monkeypatch.setattr("caresense.api.CareSensePredictor", forbidden)
    client = TestClient(create_app(completed_project))
    assert client.get("/health").json()["model_available"] is False
    assert client.post("/patients/demo-1/predict").status_code == 503


def test_frozen_manifest_cannot_reference_outside_project(completed_project):
    frozen_path = completed_project / "artifacts/frozen_decisions.json"
    frozen = json.loads(frozen_path.read_text())
    frozen["frozen_artifact_sha256"]["../outside"] = "00"
    frozen_path.write_text(json.dumps(frozen))
    training = {**frozen, "status": "completed"}
    (completed_project / "reports/training_status.json").write_text(json.dumps(training))
    with pytest.raises(ValueError, match="Missing or invalid frozen artifact"):
        _verify_completed_artifacts(completed_project)
