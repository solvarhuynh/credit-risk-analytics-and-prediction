# Render deployment — Dash individual prediction

This guide deploys the existing six-input Dash app as a Render **Python Web Service** from this GitHub repository. It does not train models or change inference logic. Keep the checked-in `src/` runtime mirror synchronized with the canonical root `src/`; `tests/apps/test_render_bundle.py` enforces byte-for-byte parity.

## Render service settings

- **Repository:** the current `credit-risk-analytics-and-prediction` GitHub repository.
- **Root Directory:** `apps/individual_prediction_dash`
- **Runtime:** Python
- **Python Version environment variable:** `3.12.10`
- **Build Command:** `pip install -r requirements-deploy.txt`
- **Start Command:** `gunicorn app:server --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
- **Environment variables:** set `PYTHON_VERSION=3.12.10` in Render. Render supplies `PORT`; do not define it manually. There are no application secrets or `.env` files required.

One Gunicorn worker is intentional on the 512 MB Free instance to avoid multiplying model/import memory. SHAP runs on demand only when a user requests a prediction; the app does not train during startup.

## Runtime bundle

The app root contains a small `src/` package mirror because Render commands rooted here cannot import sibling repository files. Model pickle class paths remain `src.models.demo_6input` and `src.models.demo_5input`, matching the saved artifacts. The mirror is byte-tested against the canonical root source.

Required files under `data/processed/modeling/`:

- `xgboost_6input_demo.joblib` and `xgboost_6input_demo_manifest.json`
- `logistic_6input_demo.joblib` and `logistic_6input_demo_manifest.json`
- `xgboost_6input_demo_validation_predictions.parquet`
- `logistic_6input_demo_validation_predictions.parquet`
- `validation_ids.parquet`

These provide selectable models, model provenance, the eight labeled Validation presets, the reference scatter/threshold calculations, Validation metrics, and risk-index distributions. Risk tiers and Expected Loss are computed by the existing code; no separate artifact is needed. Local SHAP is computed for the current input by the selected model, so global SHAP CSV/Parquet artifacts are not required. The HCMUTE logo and stylesheet remain in `assets/`.

The current seven data artifacts total **12,044,787 bytes (11.49 MiB)**; the largest is the Logistic Validation predictions Parquet at **4,914,567 bytes**. GitHub's 100 MB per-file limit is not approached. They are required runtime files, not training data. Do not replace them with the primary 103-input model or Frozen Test predictions.

## What the service reads

At runtime it reads only the bundled model/manifest files, Validation prediction files, and `validation_ids.parquet`. Paths are rooted from `Path(__file__)` in the bundled `src/config.py`, not from a developer drive or the shell's current directory. There are no raw datasets, full canonical dataset, Train rows, or Frozen Test prediction files in this bundle. Startup imports inference code only; it does not call a training/experiment CLI.

## Local checks before connecting GitHub

From the repository root, with its existing `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/apps/test_render_bundle.py tests/apps/test_individual_prediction_dash.py tests/models/test_demo_6input.py tests/models/test_risk_index.py -v
.\.venv\Scripts\python.exe -m compileall -q apps/individual_prediction_dash/src apps/individual_prediction_dash/app.py apps/individual_prediction_dash/logic.py
```

Then test imports from the service root (not the repository root):

```powershell
Push-Location apps/individual_prediction_dash
..\..\.venv\Scripts\python.exe -c "import app; print(app.server.test_client().get('/').status_code)"
Pop-Location
```

Expected local HTTP status is `200`. This checks the app-root import path, not an actual Linux Render deployment. Compare the same fixed six-input prediction via the local canonical source and app-root bundle before deploying; automated tests also verify source/artifact byte parity.

The direct local script entry point is also retained. From the repository root:

```powershell
Push-Location apps/individual_prediction_dash
..\..\.venv\Scripts\python.exe app.py
Pop-Location
```

Stop it with `Ctrl+C`; optionally set `DASH_PORT` to a verified free local port. This direct launch path was smoke-tested and returned HTTP 200.

## 512 MB memory caveat

The seven runtime data artifacts total 12,044,787 bytes on disk. In a local Windows smoke process, importing the app and running one XGBoost prediction with its per-record SHAP explanation measured a peak Working Set of **484,134,912 bytes (~462 MiB)**; post-call Working Set was 366,514,176 bytes. Windows PrivateUsage was about 1.36 GiB and is commit, not resident RAM. This local peak is already close to Render Free's 512 MB limit, before accounting for Linux-specific memory behavior or service overhead. It is a warning signal, not a Linux measurement: Free-tier operation is **not verified and appears high-risk**. Do not remove features or change inference to force it under the limit; if deployment is later approved, observe Render memory during first startup and prediction and stop if it approaches the limit.

Do not store raw loan data, Frozen Test artifacts, `.venv`, caches, `.env`, tokens, or experimental training outputs in this app bundle. The runtime model and exact Validation references listed above must remain tracked with the app unless an approved artifact-hosting mechanism is later selected.
