"""Fit đúng một XGBoost trên split Train để đo tài nguyên cho workstream F1."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

from src.config import (
    CANONICAL_DATASET_PATH,
    DATA_DICTIONARY_PATH,
    MODELING_DIR,
    PROJECT_ROOT,
)
from src.models.modeling_pipeline import (
    build_baseline_feature_selection,
    build_feature_schema,
    build_xgboost_pipeline,
)


RUN_ID = os.environ.get("F1_PILOT_RUN_ID", "pilot-20261009-03")
EXPERIMENT_ROOT = PROJECT_ROOT / "data" / "processed" / "modeling_experiments" / "f1_improvement"
RUN_DIR = EXPERIMENT_ROOT / RUN_ID
OUTPUT_MODEL = RUN_DIR / "xgboost_pilot.joblib"
OUTPUT_RESULT = RUN_DIR / "pilot_result.json"
PROGRESS_LOG = RUN_DIR / "pilot-progress.jsonl"
BASELINE_MANIFEST = MODELING_DIR / "ml_lc_05_manifest.json"
TRAIN_IDS_PATH = MODELING_DIR / "train_ids.parquet"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def write_checkpoint(progress_path: Path, phase: str, **details: Any) -> None:
    event = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        **details,
    }
    with progress_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _checkpoint(phase: str, **details: Any) -> None:
    write_checkpoint(PROGRESS_LOG, phase, **details)


def run_pilot() -> dict[str, Any]:
    """Select only frozen Train IDs, fit one baseline-shaped model, save isolated evidence."""
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    _checkpoint("START", run_id=RUN_ID, python_executable=os.sys.executable)
    protected_outputs = (OUTPUT_MODEL, OUTPUT_RESULT)
    if any(path.exists() for path in protected_outputs):
        _checkpoint("FAILED", reason="OUTPUT_EXISTS_REFUSING_OVERWRITE", run_dir=str(RUN_DIR))
        raise FileExistsError(f"Pilot result/model already exists; refusing overwrite: {RUN_DIR}")
    try:
        required = (CANONICAL_DATASET_PATH, DATA_DICTIONARY_PATH, BASELINE_MANIFEST, TRAIN_IDS_PATH)
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Pilot inputs are missing: {missing}")

        _checkpoint("LOADING_DATA", train_ids_path=str(TRAIN_IDS_PATH))
        baseline = json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))
        training_ids = pd.read_parquet(TRAIN_IDS_PATH, columns=["loan_id", "target"])
        if (len(training_ids) != baseline.get("train_rows")
                or training_ids["loan_id"].isna().any()
                or not training_ids["loan_id"].is_unique
                or not training_ids["target"].isin([0, 1]).all()):
            raise ValueError("Frozen Train IDs/labels fail validation against the ML-LC-05 manifest.")

        features = list(baseline["actual_features"])
        expected_parameters = {
            "n_estimators": 200,
            "max_depth": 4,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        }
        parameters = baseline["model_parameters"]
        if any(parameters.get(name) != value for name, value in expected_parameters.items()):
            raise ValueError("Current ML-LC-05 parameters differ from the documented pilot protocol.")

        selected_columns = ["loan_id", "target", *features]
        training_id_values = pa.array(training_ids["loan_id"].tolist())
        source = ds.dataset(CANONICAL_DATASET_PATH, format="parquet")
        train_table = source.to_table(
            columns=selected_columns,
            filter=ds.field("loan_id").isin(training_id_values),
        )
        train = train_table.to_pandas()
        del train_table
        if len(train) != len(training_ids) or not train["loan_id"].is_unique:
            raise ValueError("Filtered canonical rows do not equal the frozen Train partition.")
        expected_ids = set(training_ids["loan_id"].tolist())
        if set(train["loan_id"].tolist()) != expected_ids:
            raise ValueError("Filtered canonical IDs differ from frozen Train IDs.")
        expected_target = training_ids.set_index("loan_id")["target"]
        aligned_target = expected_target.reindex(train["loan_id"].tolist()).to_numpy()
        if not (train["target"].to_numpy() == aligned_target).all():
            raise ValueError("Filtered canonical target differs from frozen Train labels.")
        _checkpoint("DATA_LOADED", rows=int(len(train)), features=int(len(features)))

        _checkpoint("PREPROCESSING")
        dictionary = pd.read_csv(DATA_DICTIONARY_PATH)
        schema = build_feature_schema(train, dictionary)
        selection = build_baseline_feature_selection(train, schema, audit_frame=train)
        if list(selection.baseline_features) != features:
            raise ValueError("Pilot feature list differs from the locked ML-LC-05 actual input schema.")

        x_train = train.loc[:, features]
        y_train = train["target"].astype("int8")
        pipeline = build_xgboost_pipeline(
            train,
            schema,
            feature_columns=features,
            random_state=int(parameters["random_state"]),
            n_estimators=int(parameters["n_estimators"]),
            max_depth=int(parameters["max_depth"]),
            learning_rate=float(parameters["learning_rate"]),
            subsample=float(parameters["subsample"]),
            colsample_bytree=float(parameters["colsample_bytree"]),
        )
        preprocessor = pipeline.named_steps["preprocess"]
        model = pipeline.named_steps["model"]
        x_transformed = preprocessor.fit_transform(x_train, y_train)
        _checkpoint(
            "PREPROCESSING_COMPLETE",
            transformed_features=int(len(preprocessor.get_feature_names_out())),
        )

        _checkpoint("FIT_START", train_rows=int(len(train)))
        started = time.perf_counter()
        model.fit(x_transformed, y_train)
        fit_seconds = time.perf_counter() - started
        _checkpoint("FIT_COMPLETE", fit_seconds=float(fit_seconds))
        del x_transformed

        transformed_feature_count = len(preprocessor.get_feature_names_out())
        result: dict[str, Any] = {
            "run_id": RUN_ID,
            "status": "PILOT_FIT_PASS",
            "purpose": "resource pilot only; no validation/test scoring",
            "started_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "train_rows": int(len(train)),
            "train_target_counts": {str(key): int(value) for key, value in y_train.value_counts().sort_index().items()},
            "train_ids_sha256": _sha256(TRAIN_IDS_PATH),
            "canonical_source": str(CANONICAL_DATASET_PATH),
            "train_ids_source": str(TRAIN_IDS_PATH),
            "selected_rows_match_train_ids": True,
            "model_inputs": int(len(features)),
            "features": features,
            "transformed_features": int(transformed_feature_count),
            "model_parameters": {
                **expected_parameters,
                "objective": str(model.objective),
                "eval_metric": str(model.eval_metric),
                "tree_method": str(model.tree_method),
                "n_jobs": int(model.n_jobs),
                "scale_pos_weight": int(model.scale_pos_weight),
            },
            "fit_seconds": float(fit_seconds),
            "training_metrics": None,
            "validation_accessed": False,
            "frozen_test_accessed": False,
            "locked_artifact_modified": False,
            "artifact_path": str(OUTPUT_MODEL),
            "artifact_bytes": None,
            "artifact_sha256": None,
            "resource_monitor": "Captured by the Python Windows process-tree monitor in this run directory.",
        }

        import joblib

        temporary_model = OUTPUT_MODEL.with_suffix(OUTPUT_MODEL.suffix + ".partial")
        joblib.dump(pipeline, temporary_model, compress=0)
        temporary_model.replace(OUTPUT_MODEL)
        result["artifact_bytes"] = OUTPUT_MODEL.stat().st_size
        result["artifact_sha256"] = _sha256(OUTPUT_MODEL)
        _atomic_json(OUTPUT_RESULT, result)
        _checkpoint("ARTIFACT_SAVED", model_path=str(OUTPUT_MODEL), result_path=str(OUTPUT_RESULT))
        print(json.dumps(result, ensure_ascii=False))
        return result
    except BaseException as exc:
        _checkpoint("FAILED", reason="PILOT_EXCEPTION", exception=repr(exc))
        raise


if __name__ == "__main__":
    run_pilot()
