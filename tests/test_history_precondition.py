from fastapi.testclient import TestClient
import pytest

from caresense.api import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path))


def test_stale_editor_cannot_overwrite_newer_history(client):
    initial = client.get("/vitals?patient_id=demo-1").json()
    rows = initial["history"]
    rows[-1]["HR"] = 100
    accepted = client.post("/vitals", json={"patient_id": "demo-1", "history": rows,
                                            "expected_history_sha256": initial["history_sha256"]})
    assert accepted.status_code == 200
    current_hash = accepted.json()["history_sha256"]
    assert current_hash != initial["history_sha256"]
    rows[-1]["HR"] = 140
    stale = client.post("/vitals", json={"patient_id": "demo-1", "history": rows,
                                         "expected_history_sha256": initial["history_sha256"]})
    assert stale.status_code == 409
    assert stale.json()["detail"]["current_history_sha256"] == current_hash
    current = client.get("/vitals?patient_id=demo-1").json()
    assert current["current_values"]["HR"] == 100
    assert current["history_sha256"] == current_hash


def test_append_uses_same_atomic_history_precondition(client):
    initial = client.get("/vitals?patient_id=demo-1").json()
    payload = {"patient_id": "demo-1", "observation": {"ICULOS": 13, "HR": 90},
               "expected_history_sha256": initial["history_sha256"]}
    assert client.post("/vitals", json=payload).status_code == 200
    payload["observation"]["ICULOS"] = 14
    assert client.post("/vitals", json=payload).status_code == 409
    assert client.get("/vitals?patient_id=demo-1").json()["history_rows"] == 13


@pytest.mark.parametrize("value", ["bad", "z" * 64, 123, True])
def test_invalid_history_hash_is_rejected_before_mutation(client, value):
    response = client.post("/vitals", json={"patient_id": "demo-1", "observation": {"ICULOS": 13, "HR": 90},
                                           "expected_history_sha256": value})
    assert response.status_code == 422
    assert client.get("/vitals?patient_id=demo-1").json()["history_rows"] == 12
