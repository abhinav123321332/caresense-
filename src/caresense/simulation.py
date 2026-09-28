"""Exactly five synthetic demonstration histories and an in-memory patient store.

Scenario names describe inputs, not predicted risk. Every probability and SHAP
explanation is obtained from CareSensePredictor; nothing is hardcoded here.
"""
from __future__ import annotations

from copy import deepcopy
from threading import RLock
from uuid import uuid4

from .predict import CareSensePredictor, normalize_history, _records
from .schema import INPUT_COLUMNS


PRESET_NAMES = {
    "demo-1": "Stable measurements",
    "demo-2": "Rising pulse and temperature",
    "demo-3": "Falling pressure and rising lactate",
    "demo-4": "Improving measurements",
    "demo-5": "Intermittent laboratory measurements",
}


def preset_histories() -> dict[str, dict]:
    result = {}
    for number, (patient_id, name) in enumerate(PRESET_NAMES.items(), start=1):
        history = []
        for hour in range(1, 13):
            progress = (hour - 1) / 11
            row = {column: None for column in INPUT_COLUMNS}
            row.update({"ICULOS": hour, "Age": 40 + 6 * number, "Gender": number % 2,
                        "Unit1": 1, "Unit2": 0, "HospAdmTime": -8,
                        "HR": 76 + hour % 3, "O2Sat": 97, "Temp": 36.8,
                        "SBP": 118, "MAP": 82, "DBP": 64, "Resp": 17, "EtCO2": 35})
            if number == 2:
                row.update(HR=82 + 42 * progress, Temp=37 + 2.1 * progress,
                           Resp=18 + 9 * progress, MAP=84 - 11 * progress)
            elif number == 3:
                row.update(HR=85 + 45 * progress, SBP=120 - 35 * progress,
                           MAP=85 - 29 * progress, DBP=67 - 20 * progress,
                           O2Sat=97 - 4 * progress, Resp=18 + 13 * progress)
            elif number == 4:
                row.update(HR=121 - 39 * progress, Temp=38.7 - 1.6 * progress,
                           MAP=61 + 20 * progress, SBP=91 + 29 * progress,
                           DBP=47 + 18 * progress, Resp=29 - 11 * progress)
            elif number == 5:
                row.update(HR=90 + (hour % 4) * 5, Resp=21 + hour % 3,
                           O2Sat=None if hour % 4 == 0 else 95, Temp=None if hour % 3 else 37.6)
            if hour in {1, 6, 12}:
                lactate = (1.2 if number == 1 else 1.5 + progress if number == 2 else
                           1.4 + 3.8 * progress if number == 3 else 3.3 - 2 * progress if number == 4 else 2 + .3 * progress)
                wbc = (7.5 if number == 1 else 9 + 7 * progress if number == 2 else
                       10 + 9 * progress if number == 3 else 17 - 7 * progress if number == 4 else 11)
                row.update(Lactate=lactate, WBC=wbc, Creatinine=.9, Platelets=220, Hgb=12.5)
            history.append(row)
        result[patient_id] = {"id": patient_id, "name": name, "is_preset": True,
                              "synthetic": True, "history": history}
    return result


class SimulationStore:
    """Process-local demo data. Reset/restart restores the five presets.

    This is a prototype store, not a persistent clinical record system. A lock
    protects each read/mutation. Returned copies cannot mutate protected state.
    """
    def __init__(self):
        self._lock = RLock()
        self._patients = preset_histories()

    def list_patients(self) -> list[dict]:
        with self._lock:
            return [{key: deepcopy(value) for key, value in patient.items() if key != "history"}
                    for patient in self._patients.values()]

    def get(self, patient_id: str) -> dict:
        with self._lock:
            if patient_id not in self._patients:
                raise KeyError(f"Unknown patient: {patient_id}")
            return deepcopy(self._patients[patient_id])

    def add(self, name: str, history) -> dict:
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            raise ValueError("Patient display name must contain 1 to 120 characters")
        normalized = _records(normalize_history(history))
        patient_id = "user-" + uuid4().hex
        patient = {"id": patient_id, "name": name.strip(), "is_preset": False,
                   "synthetic": True, "history": normalized}
        with self._lock:
            self._patients[patient_id] = patient
        return deepcopy(patient)

    def update_history(self, patient_id: str, history) -> dict:
        normalized = _records(normalize_history(history))
        with self._lock:
            if patient_id not in self._patients:
                raise KeyError(f"Unknown patient: {patient_id}")
            self._patients[patient_id]["history"] = normalized
            return deepcopy(self._patients[patient_id])

    def append(self, patient_id: str, observation: dict) -> dict:
        with self._lock:
            patient = self.get(patient_id)
            return self.update_history(patient_id, patient["history"] + [observation])

    def delete(self, patient_id: str) -> None:
        with self._lock:
            patient = self.get(patient_id)
            if patient["is_preset"]:
                raise ValueError("The five default simulation patients are protected from deletion")
            del self._patients[patient_id]

    def reset(self) -> list[dict]:
        with self._lock:
            self._patients = preset_histories()
            return self.list_patients()

    def predict(self, patient_id: str, predictor: CareSensePredictor, top_n: int = 10) -> dict:
        patient = self.get(patient_id)
        return {"patient_id": patient_id, "synthetic": True,
                **predictor.predict(patient["history"], top_n=top_n)}
