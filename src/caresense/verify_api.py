"""Exercise a real localhost HTTP server with the saved official model.

No model is refitted and no output probability is substituted. Temporary
simulation edits disappear when the verification server exits.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from time import perf_counter, sleep
from datetime import datetime, timezone

import httpx

from .predict import CareSensePredictor


def verify(project_dir: Path) -> dict:
    project_dir = project_dir.resolve()
    reports = project_dir / "reports"
    engine = CareSensePredictor(project_dir)
    started = perf_counter()
    checks = []
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = {**os.environ, "CARESENSE_PROJECT_DIR": str(project_dir)}
    command = [sys.executable, "-m", "uvicorn", "caresense.api:create_app", "--factory",
               "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"]
    with (reports / "api_smoke_server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, env=environment, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=30, trust_env=False) as client:
                deadline = perf_counter() + 40
                while True:
                    try:
                        response = client.get("/health")
                        response.raise_for_status()
                        break
                    except httpx.TransportError:
                        if process.poll() is not None or perf_counter() >= deadline:
                            raise RuntimeError("Verification server failed to become reachable; see api_smoke_server.log")
                        sleep(0.1)

                def request(method, path, expected=200, **kwargs):
                    response = client.request(method, path, **kwargs)
                    assert response.status_code == expected, f"{method} {path}: {response.status_code} {response.text[:500]}"
                    checks.append({"method": method, "path": path, "status_code": response.status_code})
                    return response.json()

                health = request("GET", "/health")
                assert health["model_available"] and health["predictor_source"] == "verified_saved_bundle"
                assert health["clinical_reference_available"]
                openapi = request("GET", "/openapi.json")
                assert "/patients/{patient_id}/predict" in openapi["paths"]
                patients = request("GET", "/patients")["patients"]
                assert len(patients) == 5 and all(p["is_preset"] and p["synthetic"] for p in patients)
                assert len(request("GET", "/vitals")["patients"]) == 5
                actual_predictions = []
                for patient in patients:
                    patient_id = patient["id"]
                    vitals = request("GET", "/vitals", params={"patient_id": patient_id})
                    result = request("POST", f"/patients/{patient_id}/predict")
                    direct = engine.predict(vitals["history"])
                    assert result["risk_probability"] == direct["risk_probability"]
                    assert result["top_features"] == direct["top_features"]
                    actual_predictions.append({"patient_id": patient_id, "risk_probability": result["risk_probability"],
                                               "risk_tier": result["risk_tier"]})
                original = request("GET", "/vitals", params={"patient_id": "demo-1"})
                features = request("GET", "/patients/demo-1/features")
                explanation = request("GET", "/patients/demo-1/explain")
                trajectory = request("GET", "/patients/demo-1/trajectory")
                alert = request("GET", "/alert-status/demo-1")
                assert len(features["feature_names"]) == 176
                assert all(item["history_sha256"] == original["history_sha256"]
                           for item in (features, explanation, trajectory, alert))
                assert trajectory["rows"][-1]["risk_probability"] == explanation["risk_probability"]
                assert alert["hardware_delivery_confirmed"] is False
                request("DELETE", "/patients/demo-1", 403)
                request("POST", "/vitals", 422, json={"patient_id": "demo-1", "observation": {"ICULOS": 13, "HR": "90"}})
                unchanged = request("GET", "/vitals", params={"patient_id": "demo-1"})
                assert unchanged["history_sha256"] == original["history_sha256"]
                history = original["history"]
                history[-1]["HR"] = 139
                history[-1]["MAP"] = 60
                changed = request("POST", "/vitals", json={"patient_id": "demo-1", "history": history})
                changed_prediction = request("POST", "/patients/demo-1/predict")
                assert changed["history_sha256"] != original["history_sha256"]
                assert changed_prediction["history_sha256"] == changed["history_sha256"]
                assert changed_prediction["risk_probability"] == engine.predict(history)["risk_probability"]
                appended = request("POST", "/vitals", json={"patient_id": "demo-1", "observation": {"ICULOS": 13, "HR": 110}})
                assert appended["history_rows"] == 13
                created = request("POST", "/patients", 201, json={"name": "HTTP verification", "history": [{"ICULOS": 1, "HR": 90}]})
                request("POST", f"/patients/{created['id']}/predict")
                request("DELETE", f"/patients/{created['id']}")
                request("POST", f"/patients/{created['id']}/predict", 404)
                empty = request("POST", "/patients", 201, json={"name": "Missing clinical values", "history": [{"ICULOS": 1, "Age": 60}]})
                request("POST", f"/patients/{empty['id']}/predict", 422)
                reset = request("POST", "/reset")
                assert len(reset["patients"]) == 5
                restored = request("GET", "/vitals", params={"patient_id": "demo-1"})
                assert restored["history_sha256"] == original["history_sha256"]
                assert len(request("GET", "/patients")["patients"]) == 5
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    evidence = {"status": "passed", "verified_utc": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": perf_counter() - started, "transport": "real localhost HTTP / uvicorn",
                "model_version": engine.metadata["model_version"], "request_count": len(checks), "requests": checks,
                "five_actual_demo_predictions": actual_predictions,
                "direct_saved_model_probability_and_shap_parity": True,
                "history_edit_recomputes_prediction": True, "invalid_update_preserves_state": True,
                "protected_presets_and_user_crud": True, "reset_restores_exact_histories": True,
                "empty_clinical_history_withheld": True, "hardware_tested": False,
                "critical_branch_note": "If absent from real demo outputs, Critical handling is tested separately using an explicitly injected test double; no official model risk is overridden."}
    (reports / "api_checks.json").write_text(json.dumps(evidence, indent=2, allow_nan=False), encoding="utf-8")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parents[2])
    evidence = verify(parser.parse_args().project_dir)
    print(json.dumps({key: value for key, value in evidence.items() if key != "requests"}, indent=2))


if __name__ == "__main__":
    main()
