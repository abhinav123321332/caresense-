# CareSense ML Backend — VERIFIED AND FROZEN

This is the inference/API distribution of the verified PhysioNet experiment. It contains no dashboard, raw patient dataset, preparation/training runner, or frontend assets. Never retrain or replace its frozen artifacts to change dashboard behavior.

## Install and run

Use Python 3.12. From the extracted ZIP directory:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
$env:CARESENSE_PROJECT_DIR = (Get-Location).Path
.venv\Scripts\python.exe -m uvicorn caresense.api:create_app --factory --host 127.0.0.1 --port 8000
```

On macOS/Linux use `.venv/bin/python` and `export CARESENSE_PROJECT_DIR="$PWD"`. The archive was verified on Windows/Python3.12; other platforms have not been executed in this release verification. Use one worker: synthetic simulation data is process-local and resets on restart. Read `/health` and `/docs`. There is no dashboard route at `/`; start the separate Dashboard package on port8080.

## Verify

```powershell
.venv\Scripts\python.exe verify_checksums.py
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .qa-test
.venv\Scripts\python.exe -m caresense.verify_inference --project-dir .
.venv\Scripts\python.exe -m caresense.verify_api --project-dir .
```

These runtime tests include explicitly synthetic mechanics fixtures, which do not replace or retrain the released model. The full original experiment tests are retained and rerun in the source workspace; this runtime-only ZIP includes API, inference, temporal-feature and history-conflict tests.

## Freeze boundary

All13 frozen artifact hashes match the original decisions manifest. Model weights, preprocessing, metadata,176-feature ordering, calibration and the verified inference source remain unchanged. The API retains the optional `expected_history_sha256` concurrency guard; stale edits return409 atomically. The packaged API excludes only the dashboard import/mount from the working integration version. The original working dashboard is preserved separately. Request/response model probabilities are not modified by this wrapper.

## Evidence and limitations

40,336 source patient records;1,552,210 hours. Internal test:5,985 patients,232,838 eligible hours,2,235 positive hours. XGBoost AUROC0.8364, average precision0.0881. At research threshold0.06359397084821286: precision12.45%,recall22.82%,specificity98.44%,F1 0.1611. The separate preserved boundary0.30 detects only5/2,235 positive test hours;0.50 and >0.75 produce no test alerts. Lower is not a clinical safety finding.

The research threshold does not replace the preserved tiers. No external/prospective clinical validation, production authentication or physical hardware delivery is established. Static clinician references are historical and not personalized treatment orders. See `reports/CARESENSE_MODEL_REPORT.md`. Final extracted-package execution evidence and ZIP checksums are delivered beside the ZIPs in RELEASE_VERIFICATION_REPORT.md; historical figures in the model report retain their original dates.
"# caresense-" 
