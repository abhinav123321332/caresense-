"""Local, process-local simulation API using the saved CareSense inference engine.

Run one worker: ``uvicorn caresense.api:create_app --factory --host 127.0.0.1``.
This prototype has no authentication, durable storage or connected alert hardware.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import logging
import math
import os
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .predict import CareSensePredictor, _records, normalize_history
from .simulation import SimulationStore


MAX_HISTORY_ROWS = 10000
LOGGER = logging.getLogger(__name__)
DEFAULT_PROJECT = Path(__file__).resolve().parents[2]


class PatientInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=120)
    history: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=MAX_HISTORY_ROWS,
    )


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class VitalsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    patient_id: str = Field(min_length=1, max_length=128)
    expected_history_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    history: list[dict[str, Any]] | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_HISTORY_ROWS,
    )
    observation: dict[str, Any] | None = None

    @model_validator(mode="after")
    def exactly_one_payload(self):
        if (self.history is None) == (self.observation is None):
            raise ValueError(
                "Provide exactly one of history (replace) or observation (append)"
            )
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _read_json(path: Path) -> dict:
    content = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(content, dict):
        raise ValueError(f"Expected a JSON object in {path.name}")

    return content


def _verify_completed_artifacts(root: Path) -> None:
    """Verify the completed experiment before deserializing trusted local joblib.

    Hashes establish consistency with this local experiment, not authenticity of
    files from an untrusted source. Only use your trusted training outputs.
    """

    training = _read_json(root / "reports/training_status.json")
    leakage = _read_json(root / "reports/leakage_audit.json")
    metrics = _read_json(root / "reports/model_metrics.json")
    frozen = _read_json(root / "artifacts/frozen_decisions.json")

    if training.get("status") != "completed":
        raise ValueError("Training and evaluation have not completed")

    if leakage.get("status") != "passed" or leakage.get("failures") != []:
        raise ValueError("The post-training leakage audit has not passed")

    if not metrics.get("completed_utc") or "xgboost" not in metrics.get("models", {}):
        raise ValueError("Completed XGBoost evaluation is missing")

    if frozen.get("status") != "decisions_frozen":
        raise ValueError("The experiment decisions were not frozen")

    config_hash = _sha256(root / "experiment_config.json")

    if (
        config_hash != frozen.get("config_sha256")
        or training.get("config_sha256") != config_hash
    ):
        raise ValueError("Experiment configuration differs from the frozen run")

    checks = leakage.get("checks", {})

    if (
        checks.get("saved_preprocessing_training_row_count_verified") is not True
        or checks.get("frozen_configuration_hash") != config_hash
    ):
        raise ValueError(
            "Post-training leakage audit evidence does not match the frozen run"
        )

    hashes = frozen.get("frozen_artifact_sha256", {})

    required = {
        "models/caresense_xgboost.pkl",
        "models/caresense_xgboost.json",
        "artifacts/preprocessing_pipeline.pkl",
        "artifacts/feature_names.json",
        "artifacts/feature_dictionary.json",
        "artifacts/model_metadata.json",
        "artifacts/threshold_config.json",
        "artifacts/run_config.json",
    }

    if not isinstance(hashes, dict) or not required.issubset(hashes):
        raise ValueError("The frozen artifact manifest is incomplete")

    if training.get("frozen_artifact_sha256") != hashes:
        raise ValueError(
            "Completed training and frozen artifact manifests disagree"
        )

    for relative, expected in hashes.items():
        artifact = (root / relative).resolve()

        if not artifact.is_relative_to(root) or not artifact.is_file():
            raise ValueError(f"Missing or invalid frozen artifact: {relative}")

        if not isinstance(expected, str) or _sha256(artifact) != expected:
            raise ValueError(f"Frozen artifact hash mismatch: {relative}")


def _validated_records(history: list[dict]) -> list[dict]:
    if not 1 <= len(history) <= MAX_HISTORY_ROWS:
        raise ValueError(
            f"History must contain 1 to {MAX_HISTORY_ROWS} observations"
        )

    # JSON non-finite tokens are not legitimate missing values. The reusable
    # dataframe interface accepts NaN as missing; the HTTP interface uses null.
    for row in history:
        for value in row.values():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                try:
                    finite = math.isfinite(value)
                except OverflowError:
                    finite = False

                if not finite:
                    raise ValueError(
                        "JSON measurements must be finite numbers or null; "
                        "NaN and Infinity are forbidden"
                    )

    try:
        return _records(normalize_history(history))
    except OverflowError as exc:
        raise ValueError(
            "A numeric measurement exceeds supported precision"
        ) from exc


def _snapshot_metadata(patient: dict) -> dict:
    canonical = json.dumps(
        patient["history"],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return {
        "patient_id": patient["id"],
        "synthetic": True,
        "history_sha256": hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest(),
        "history_rows": len(patient["history"]),
    }


def create_app(
    project_dir: str | Path | None = None,
    *,
    predictor=None,
    store: SimulationStore | None = None,
) -> FastAPI:
    """Build an isolated simulation app; predictor injection is for mechanics tests.

    Default startup validates the completed local experiment and loads its saved
    XGBoost bundle once. Failed readiness leaves simulation CRUD available but
    returns explicit 503 responses for every inference-dependent endpoint.
    """

    root = Path(
        project_dir or os.environ.get("CARESENSE_PROJECT_DIR", DEFAULT_PROJECT)
    ).resolve()

    app = FastAPI(
        title="CareSense research prototype",
        version="0.1.0",
        description=(
            "Synthetic ICU simulation with model-estimated risk. "
            "Not a diagnostic device. "
            "Use one local worker; simulation data resets on restart. "
            "Prototype thresholds are not clinically validated."
        ),
    )

    # ---------------------------------------------------------
    # CORS CONFIGURATION
    # ---------------------------------------------------------
    # Allows the hosted Google AI Studio dashboard to communicate
    # with this FastAPI backend over HTTPS.
    #
    # Localhost origins are included so local dashboard testing
    # continues to work.
    # ---------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://ais-dev-nacgilhoy3ivsqjzrjtnpm-521005117426.asia-east1.run.app",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.store = store if store is not None else SimulationStore()
    app.state.predictor = predictor
    app.state.model_error = None
    app.state.predictor_source = (
        "injected_for_testing"
        if predictor is not None
        else "verified_saved_bundle"
    )
    app.state.state_lock = RLock()
    app.state.engine_lock = RLock()

    if predictor is None:
        try:
            _verify_completed_artifacts(root)
            app.state.predictor = CareSensePredictor(root)
        except Exception as exc:
            app.state.model_error = str(exc)
            LOGGER.warning("CareSense model unavailable: %s", exc)

    try:
        reference = _read_json(
            root / "artifacts/clinical_reference.json"
        )

        if (
            reference.get("patient_specific") is not False
            or reference.get("automatic_treatment_orders") is not False
            or reference.get("historical_reference") is not True
        ):
            raise ValueError(
                "Clinical reference must be static, historical and non-patient-specific"
            )

        app.state.clinical_reference = reference

    except (OSError, ValueError) as exc:
        app.state.clinical_reference = None
        LOGGER.warning(
            "CareSense static clinical reference unavailable: %s",
            exc,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, exc: RequestValidationError):
        # Do not echo invalid NaN/Infinity into a JSON response or reflect all
        # potentially large patient histories when a request is malformed.

        details = [
            {
                "loc": list(error["loc"]),
                "msg": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]

        return JSONResponse(
            status_code=422,
            content={"detail": details},
        )

    def patient_snapshot(patient_id: str) -> dict:
        try:
            with app.state.state_lock:
                return app.state.store.get(patient_id)

        except KeyError:
            raise HTTPException(
                404,
                "Unknown simulation patient",
            ) from None

    def engine():
        if app.state.predictor is None:
            raise HTTPException(
                503,
                {
                    "message": "Validated model unavailable; no prediction produced",
                    "reason": app.state.model_error,
                },
            )

        return app.state.predictor

    def infer(
        patient: dict,
        operation: str,
        top_n: int = 10,
    ) -> dict:
        predictor_engine = engine()

        try:
            with app.state.engine_lock:
                if operation == "predict":
                    result = predictor_engine.predict(
                        patient["history"],
                        top_n=top_n,
                    )
                else:
                    result = getattr(
                        predictor_engine,
                        operation,
                    )(patient["history"])

        except ValueError as exc:
            raise HTTPException(
                422,
                str(exc),
            ) from exc

        except Exception as exc:
            LOGGER.exception("CareSense inference failed")

            raise HTTPException(
                503,
                "Model inference failed; no prediction produced",
            ) from exc

        return {
            **result,
            **_snapshot_metadata(patient),
        }

    @app.get("/health")
    def health():
        metadata = getattr(
            app.state.predictor,
            "metadata",
            {},
        )

        return {
            "status": (
                "ready"
                if app.state.predictor is not None
                else "degraded"
            ),
            "model_available": app.state.predictor is not None,
            "model_version": metadata.get("model_version"),
            "feature_version": metadata.get("feature_version"),
            "model_error": app.state.model_error,
            "predictor_source": app.state.predictor_source,
            "clinical_reference_available": (
                app.state.clinical_reference is not None
            ),
            "storage": "process-local; resets on restart; use one worker",
            "clinically_validated": False,
            "hardware_connected": False,
        }

    @app.get("/patients")
    def patients():
        with app.state.state_lock:
            return {
                "patients": app.state.store.list_patients()
            }

    @app.post("/patients", status_code=201)
    def add_patient(body: PatientInput):
        try:
            history = _validated_records(body.history)

            with app.state.state_lock:
                patient = app.state.store.add(
                    body.name,
                    history,
                )

            return {
                **patient,
                **_snapshot_metadata(patient),
            }

        except ValueError as exc:
            raise HTTPException(
                422,
                str(exc),
            ) from exc

    @app.delete("/patients/{patient_id}")
    def delete_patient(patient_id: str):
        with app.state.state_lock:
            patient = patient_snapshot(patient_id)

            if patient["is_preset"]:
                raise HTTPException(
                    403,
                    "The five preset simulation patients are protected from deletion",
                )

            app.state.store.delete(patient_id)

        return {
            "deleted": patient_id
        }

    @app.post("/reset")
    def reset(body: EmptyInput | None = None):
        with app.state.state_lock:
            return {
                "patients": app.state.store.reset(),
                "notice": "Simulation reset to the five original presets",
            }

    @app.get("/vitals")
    def vitals(
        patient_id: str | None = Query(
            default=None,
            min_length=1,
            max_length=128,
        )
    ):
        if patient_id is not None:
            patient = patient_snapshot(patient_id)

            return {
                **_snapshot_metadata(patient),
                "history": patient["history"],
                "current_values": patient["history"][-1],
            }

        with app.state.state_lock:
            snapshots = [
                app.state.store.get(patient["id"])
                for patient in app.state.store.list_patients()
            ]

        return {
            "patients": [
                {
                    **_snapshot_metadata(patient),
                    "current_values": patient["history"][-1],
                }
                for patient in snapshots
            ]
        }

    @app.post("/vitals")
    def change_vitals(body: VitalsInput):
        try:
            with app.state.state_lock:
                patient = patient_snapshot(
                    body.patient_id
                )

                current_hash = _snapshot_metadata(
                    patient
                )["history_sha256"]

                if (
                    body.expected_history_sha256 is not None
                    and body.expected_history_sha256 != current_hash
                ):
                    raise HTTPException(
                        409,
                        {
                            "message": (
                                "History changed since the editor was opened. "
                                "Reload it before saving."
                            ),
                            "current_history_sha256": current_hash,
                        },
                    )

                proposed = (
                    body.history
                    if body.history is not None
                    else patient["history"] + [body.observation]
                )

                history = _validated_records(proposed)

                changed = app.state.store.update_history(
                    body.patient_id,
                    history,
                )

            return {
                **_snapshot_metadata(changed),
                "history": changed["history"],
                "current_values": changed["history"][-1],
            }

        except ValueError as exc:
            raise HTTPException(
                422,
                str(exc),
            ) from exc

    @app.get("/patients/{patient_id}/features")
    def features(patient_id: str):
        return infer(
            patient_snapshot(patient_id),
            "features",
        )

    @app.post("/patients/{patient_id}/predict")
    def prediction(
        patient_id: str,
        body: EmptyInput | None = None,
        top_n: int = Query(
            default=10,
            ge=1,
            le=176,
        ),
    ):
        return infer(
            patient_snapshot(patient_id),
            "predict",
            top_n,
        )

    @app.get("/patients/{patient_id}/explain")
    def explanation(
        patient_id: str,
        top_n: int = Query(
            default=10,
            ge=1,
            le=176,
        ),
    ):
        # Recompute probability and SHAP together from a single immutable
        # snapshot. A later history update is detectable using history_sha256.

        return infer(
            patient_snapshot(patient_id),
            "predict",
            top_n,
        )

    @app.get("/patients/{patient_id}/trajectory")
    def trajectory(patient_id: str):
        return infer(
            patient_snapshot(patient_id),
            "trajectory",
        )

    @app.get("/alert-status/{patient_id}")
    def alert_status(patient_id: str):
        result = infer(
            patient_snapshot(patient_id),
            "predict",
        )

        critical = result["risk_probability"] > 0.75

        if critical and app.state.clinical_reference is None:
            raise HTTPException(
                503,
                "The required static Critical-tier reference is unavailable",
            )

        return {
            **result,
            "visual_alert": critical,
            "physical_alert_requested": critical,
            "hardware_delivery_confirmed": False,
            "hardware_status": "not_connected",
            "clinical_reference": (
                deepcopy(app.state.clinical_reference)
                if critical
                else None
            ),
            "alert_notice": (
                "Prototype model risk state only; no hardware signal was sent "
                "and no treatment was ordered."
            ),
        }

    return app