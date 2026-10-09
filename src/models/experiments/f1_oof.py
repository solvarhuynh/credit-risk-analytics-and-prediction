"""Tạo dự đoán OOF 5-fold chỉ trên split Train cho thử nghiệm F1."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

from src.config import CANONICAL_DATASET_PATH, DATA_DICTIONARY_PATH, MODELING_DIR, PROJECT_ROOT
from src.models.experiments.f1_pilot import fit_transform_in_batches, write_checkpoint
from src.models.modeling_pipeline import build_feature_schema, build_xgboost_pipeline


RUN_ID = os.environ.get("F1_OOF_RUN_ID", "f1-oof-20261009-01")
RUN_DIR = PROJECT_ROOT / "data" / "processed" / "modeling_experiments" / "f1_improvement" / RUN_ID
BASELINE_MANIFEST = MODELING_DIR / "ml_lc_05_manifest.json"
TRAIN_IDS_PATH = MODELING_DIR / "train_ids.parquet"
RESULT_PATH = RUN_DIR / "oof_result.json"
PREDICTIONS_PATH = RUN_DIR / "oof_predictions.parquet"
LOCKED_THRESHOLD = 0.22009515762329102


def _checkpoint(phase: str, **details: Any) -> None:
    write_checkpoint(RUN_DIR / "oof-progress.jsonl", phase, **details)


def _metrics(target: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict[str, Any]:
    predicted = probabilities >= threshold
    matrix = confusion_matrix(target, predicted, labels=[0, 1])
    return {
        "threshold": float(threshold),
        "precision": float(precision_score(target, predicted, zero_division=0)),
        "recall": float(recall_score(target, predicted, zero_division=0)),
        "f1": float(f1_score(target, predicted, zero_division=0)),
        "accuracy": float(accuracy_score(target, predicted)),
        "confusion_matrix_tn_fp_fn_tp": matrix.ravel().astype(int).tolist(),
        "predicted_positive_rate": float(predicted.mean()),
    }


def choose_oof_threshold(target: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    """Maximize pooled OOF F1 with protocol tie-breaks; not an unbiased estimate."""
    precision, recall, thresholds = precision_recall_curve(target, probabilities)
    if len(thresholds) == 0:
        raise ValueError("Cannot select a threshold from constant OOF predictions")
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-15)
    best = max(
        range(len(thresholds)),
        key=lambda index: (f1[index], recall[index], precision[index], thresholds[index]),
    )
    return {
        "threshold": float(thresholds[best]),
        "precision": float(precision[best]),
        "recall": float(recall[best]),
        "f1": float(f1[best]),
        "selection_note": "Threshold selected on pooled Train OOF labels; reported F1 is exploratory and selection-biased, not independent evaluation.",
    }


def run_oof() -> dict[str, Any]:
    protected_outputs = (RESULT_PATH, PREDICTIONS_PATH, RUN_DIR / "oof-progress.jsonl")
    if any(path.exists() for path in protected_outputs):
        raise FileExistsError(f"Refusing to overwrite OOF artifacts: {RUN_DIR}")
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    _checkpoint("START", run_id=RUN_ID, python_executable=os.sys.executable)
    try:
        baseline = json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))
        training_ids = pd.read_parquet(TRAIN_IDS_PATH, columns=["loan_id", "target"])
        if (len(training_ids) != baseline["train_rows"] or training_ids["loan_id"].isna().any()
                or not training_ids["loan_id"].is_unique or not training_ids["target"].isin([0, 1]).all()):
            raise ValueError("Frozen Train IDs/labels fail validation against ML-LC-05 manifest")

        features = list(baseline["actual_features"])
        selected_columns = ["loan_id", "target", *features]
        id_values = pa.array(training_ids["loan_id"].tolist())
        source = ds.dataset(CANONICAL_DATASET_PATH, format="parquet")
        table = source.to_table(
            columns=selected_columns,
            filter=ds.field("loan_id").isin(id_values),
        )
        train = table.to_pandas()
        if len(train) != len(training_ids) or not train["loan_id"].is_unique:
            raise ValueError("Canonical filtered rows do not equal frozen Train partition")
        expected_ids = set(training_ids["loan_id"].tolist())
        if set(train["loan_id"].tolist()) != expected_ids:
            raise ValueError("Canonical filtered loan IDs differ from frozen Train IDs")
        expected_target = training_ids.set_index("loan_id")["target"]
        aligned_target = expected_target.reindex(train["loan_id"].tolist()).to_numpy()
        if not np.array_equal(train["target"].to_numpy(), aligned_target):
            raise ValueError("Canonical Train labels differ from frozen Train IDs")
        del table, source, id_values, expected_ids, expected_target, aligned_target, training_ids

        target = train.pop("target").to_numpy(dtype=np.int8)
        loan_ids = train.pop("loan_id").to_numpy(copy=True)
        X = train
        dictionary = pd.read_csv(DATA_DICTIONARY_PATH)
        schema = build_feature_schema(X, dictionary)
        if list(baseline["actual_features"]) != features:
            raise ValueError("Feature manifest mismatch")
        if list(X.columns) != features:
            raise ValueError("Train feature order differs from locked ML-LC-05 feature order")
        _checkpoint("DATA_LOADED", rows=int(len(X)), features=len(features), folds=5)

        parameters = baseline["model_parameters"]
        expected_parameters = {
            "n_estimators": 200, "max_depth": 4, "learning_rate": 0.05,
            "subsample": 0.8, "colsample_bytree": 0.8, "random_state": 42,
        }
        if any(parameters.get(key) != value for key, value in expected_parameters.items()):
            raise ValueError("XGBoost parameters differ from the locked incumbent candidate")

        oof = np.full(len(target), np.nan, dtype=np.float32)
        splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        fold_indices = list(splitter.split(np.zeros(len(target), dtype=np.int8), target))
        for fold_number, (train_index, valid_index) in enumerate(fold_indices, start=1):
            fold_dir = RUN_DIR / f"_preprocess_matrix_work_fold_{fold_number}"
            _checkpoint(f"FOLD_{fold_number}_START", train_rows=len(train_index), valid_rows=len(valid_index))
            x_train_raw = X.iloc[train_index]
            y_train = target[train_index]
            pipeline = build_xgboost_pipeline(
                X,
                schema,
                feature_columns=features,
                **expected_parameters,
            )
            normalizer = pipeline.named_steps["normalize_missing"]
            preprocessor = pipeline.named_steps["preprocess"]
            model = pipeline.named_steps["model"]
            x_train = normalizer.fit_transform(x_train_raw)
            del x_train_raw
            transformed = fit_transform_in_batches(
                preprocessor, x_train, pd.Series(y_train), scratch_dir=fold_dir,
            )
            del x_train
            _checkpoint(f"FOLD_{fold_number}_PREPROCESSING_COMPLETE", transformed_features=transformed.shape[1])

            _checkpoint(f"FOLD_{fold_number}_FIT_START")
            started = time.perf_counter()
            model.fit(transformed, y_train)
            fit_seconds = time.perf_counter() - started
            del transformed
            shutil.rmtree(fold_dir, ignore_errors=True)
            _checkpoint(f"FOLD_{fold_number}_FIT_COMPLETE", fit_seconds=fit_seconds)

            predictions = np.empty(len(valid_index), dtype=np.float32)
            for start in range(0, len(valid_index), 50_000):
                index_batch = valid_index[start:start + 50_000]
                normalized = normalizer.transform(X.iloc[index_batch])
                batch_transformed = preprocessor.transform(normalized)
                predictions[start:start + len(index_batch)] = model.predict_proba(batch_transformed)[:, 1]
                del normalized, batch_transformed
            oof[valid_index] = predictions
            _checkpoint(
                f"FOLD_{fold_number}_COMPLETE", fit_seconds=fit_seconds,
                valid_rows=len(valid_index), prediction_min=float(predictions.min()),
                prediction_max=float(predictions.max()),
            )
            del pipeline, normalizer, preprocessor, model, predictions, y_train, train_index, valid_index
            import gc

            gc.collect()

        if np.isnan(oof).any():
            raise ValueError("OOF predictions are incomplete")
        selected = choose_oof_threshold(target, oof)
        ap = float(average_precision_score(target, oof))
        auc = float(roc_auc_score(target, oof))
        loss = float(log_loss(target, oof, labels=[0, 1]))
        brier = float(brier_score_loss(target, oof))
        selected_threshold = selected["threshold"]
        fold_metrics = []
        for fold_number, (_, valid_index) in enumerate(fold_indices, start=1):
            fold_metrics.append({
                "fold": fold_number,
                **_metrics(target[valid_index], oof[valid_index], selected_threshold),
            })
        result = {
            "run_id": RUN_ID,
            "status": "TRAIN_ONLY_OOF_PASS",
            "folds": 5,
            "seed": 42,
            "train_rows": int(len(target)),
            "positive_prevalence": float(target.mean()),
            "model_parameters": {**expected_parameters, "objective": "binary:logistic", "eval_metric": "logloss", "tree_method": "hist", "n_jobs": 4},
            "metrics": {"roc_auc": auc, "average_precision": ap, "log_loss": loss, "brier": brier},
            "threshold_at_0_5": _metrics(target, oof, 0.5),
            "threshold_at_locked_validation_value": _metrics(target, oof, LOCKED_THRESHOLD),
            "selected_train_oof_threshold": {**selected, "metrics_recomputed": _metrics(target, oof, selected_threshold)},
            "fold_metrics_at_selected_threshold": fold_metrics,
            "predictions_path": str(PREDICTIONS_PATH),
            "validation_accessed": False,
            "frozen_test_accessed": False,
            "selection_warning": "Selected threshold F1 is optimistic because the same pooled OOF labels choose the threshold; independent threshold evaluation was not performed.",
        }
        pd.DataFrame({"loan_id": loan_ids, "target": target, "oof_probability": oof}).to_parquet(
            PREDICTIONS_PATH, index=False,
        )
        RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        _checkpoint("OOF_METRICS_COMPLETE", selected_threshold=selected_threshold, selected_f1=selected["f1"])
        _checkpoint("ARTIFACT_SAVED", predictions_path=str(PREDICTIONS_PATH), result_path=str(RESULT_PATH))
        print(json.dumps(result, ensure_ascii=False))
        return result
    except BaseException as exc:
        _checkpoint("FAILED", reason="OOF_EXCEPTION", exception=repr(exc))
        raise


if __name__ == "__main__":
    run_oof()
