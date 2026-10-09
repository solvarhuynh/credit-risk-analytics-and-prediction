"""Logistic Regression năm input: benchmark riêng cho ứng dụng Dash."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import (
    CANONICAL_DATASET_PATH,
    LOGISTIC_5INPUT_DEMO_MANIFEST_PATH,
    LOGISTIC_5INPUT_DEMO_PATH,
    LOGISTIC_5INPUT_DEMO_TEST_LOCK_PATH,
    LOGISTIC_5INPUT_DEMO_TEST_PREDICTIONS_PATH,
    MODELING_DIR,
    XGBOOST_5INPUT_DEMO_MANIFEST_PATH,
    XGBOOST_5INPUT_DEMO_PATH,
    XGBOOST_5INPUT_DEMO_TEST_PREDICTIONS_PATH,
)
from src.models.cost_optimization import calculate_expected_loss
from src.models.demo_5input import (
    DEMO_FEATURES,
    DISPLAY_FEATURES,
    LGD_OPTIONS,
    SanitizeDemoInputs,
    _metrics,
    _primary_artifact_hashes,
    _read_canonical_rows,
    _read_json,
    _read_partition_ids,
    _save_joblib,
    _save_json,
    _save_parquet,
    _sha256,
    validate_demo_inputs,
)
from src.models.preprocess_pipeline import NormalizePandasMissing
from src.models.scoring import (
    ML_LC_10_LOCKED_THRESHOLD,
    assign_pd_risk_tier,
    probability_to_project_credit_score,
    probability_to_risk_score,
    validate_probability_of_default,
)


MODEL_PARAMETERS = {"max_iter": 1000, "solver": "lbfgs", "C": 1.0, "random_state": 42}
DEMO_THRESHOLD = ML_LC_10_LOCKED_THRESHOLD


def build_logistic_pipeline() -> Pipeline:
    """Dựng pipeline chỉ fit imputer/scaler bằng train partition."""
    return Pipeline([
        ("sanitize", SanitizeDemoInputs()),
        ("normalize_missing", NormalizePandasMissing()),
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(**MODEL_PARAMETERS)),
    ])


def train_logistic_demo() -> dict[str, Any]:
    """Fit benchmark trên train, đánh giá validation và mở frozen test đúng một lần."""
    outputs = (
        LOGISTIC_5INPUT_DEMO_PATH,
        LOGISTIC_5INPUT_DEMO_MANIFEST_PATH,
        LOGISTIC_5INPUT_DEMO_TEST_PREDICTIONS_PATH,
        LOGISTIC_5INPUT_DEMO_TEST_LOCK_PATH,
    )
    if any(path.exists() for path in outputs):
        raise FileExistsError("Artifact/one-shot lock Logistic 5-input đã tồn tại; không đánh giá lại.")

    xgb_manifest = _read_json(XGBOOST_5INPUT_DEMO_MANIFEST_PATH)
    split_manifest = _read_json(MODELING_DIR / "split_manifest.json")
    if (xgb_manifest.get("status") != "PASS"
            or xgb_manifest.get("features") != list(DEMO_FEATURES)
            or xgb_manifest.get("threshold") != DEMO_THRESHOLD
            or xgb_manifest.get("model_sha256") != _sha256(XGBOOST_5INPUT_DEMO_PATH)
            or xgb_manifest.get("canonical_dataset_sha256") != _sha256(CANONICAL_DATASET_PATH)
            or xgb_manifest.get("dataset_id") != split_manifest.get("dataset_id")
            or split_manifest.get("stage_status") != "PASS"
            or split_manifest.get("coverage_status") != "PASS"):
        raise ValueError("Nguồn canonical/split/XGBoost demo không đạt contract năm input.")
    source_hashes = _primary_artifact_hashes()
    xgb_hashes = {
        path.name: _sha256(path)
        for path in (XGBOOST_5INPUT_DEMO_PATH, XGBOOST_5INPUT_DEMO_MANIFEST_PATH,
                     XGBOOST_5INPUT_DEMO_TEST_PREDICTIONS_PATH)
    }
    split_hashes = {
        name: _sha256(MODELING_DIR / f"{name}_ids.parquet")
        for name in ("train", "validation", "test")
    }
    if any(split_hashes[name] != xgb_manifest["split_artifact_sha256"][name]
           for name in split_hashes):
        raise ValueError("Train/validation IDs khác lần dựng XGBoost demo.")

    train_ids = _read_partition_ids(MODELING_DIR / "train_ids.parquet", "train")
    validation_ids = _read_partition_ids(MODELING_DIR / "validation_ids.parquet", "validation")
    if set(train_ids.loan_id).intersection(validation_ids.loan_id):
        raise ValueError("Train và validation overlap.")
    train = _read_canonical_rows(CANONICAL_DATASET_PATH, train_ids)
    validation = _read_canonical_rows(CANONICAL_DATASET_PATH, validation_ids)
    if len(train) != split_manifest["train_rows"] or len(validation) != split_manifest["validation_rows"]:
        raise ValueError("Số dòng train/validation khác split manifest.")
    train_x, train_y = train.loc[:, list(DEMO_FEATURES)], train["target"].astype(np.int8)
    validation_x, validation_y = validation.loc[:, list(DEMO_FEATURES)], validation["target"].astype(np.int8)
    pipeline = build_logistic_pipeline()
    pipeline.fit(train_x, train_y)
    validation_pd = validate_probability_of_default(pipeline.predict_proba(validation_x)[:, 1])
    validation_metrics = _metrics(validation_y, validation_pd, DEMO_THRESHOLD)
    if not np.isfinite(pipeline.named_steps["model"].coef_).all():
        raise ValueError("Hệ số Logistic không hữu hạn.")

    LOGISTIC_5INPUT_DEMO_TEST_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(LOGISTIC_5INPUT_DEMO_TEST_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(lock_fd, "w", encoding="utf-8") as stream:
        json.dump({"opened_at_utc": datetime.now(timezone.utc).isoformat(),
                   "model": "logistic_5input_demo",
                   "canonical_sha256": xgb_manifest["canonical_dataset_sha256"]}, stream)

    test_ids = _read_partition_ids(MODELING_DIR / "test_ids.parquet", "test")
    if set(test_ids.loan_id).intersection(set(train_ids.loan_id) | set(validation_ids.loan_id)):
        raise ValueError("Frozen test split khác lần dựng XGBoost demo hoặc overlap.")
    test = _read_canonical_rows(CANONICAL_DATASET_PATH, test_ids)
    test_pd = validate_probability_of_default(pipeline.predict_proba(test.loc[:, list(DEMO_FEATURES)])[:, 1])
    test_metrics = _metrics(test["target"].astype(np.int8), test_pd, DEMO_THRESHOLD)
    if (len(train) != split_manifest["train_rows"]
            or len(validation) != split_manifest["validation_rows"]
            or len(test) != split_manifest["test_rows"]):
        raise ValueError("Số dòng split khác manifest.")
    if _primary_artifact_hashes() != source_hashes or any(
        _sha256(path) != xgb_hashes[path.name]
        for path in (XGBOOST_5INPUT_DEMO_PATH, XGBOOST_5INPUT_DEMO_MANIFEST_PATH,
                     XGBOOST_5INPUT_DEMO_TEST_PREDICTIONS_PATH)
    ):
        raise RuntimeError("Artifact model/metrics hiện có thay đổi trong lúc dựng benchmark.")

    _save_joblib(LOGISTIC_5INPUT_DEMO_PATH, pipeline)
    predictions = pd.DataFrame({
        "loan_id": test_ids.loan_id.to_numpy(),
        "target": test["target"].to_numpy(dtype=np.int8),
        "predicted_pd": test_pd,
        "predicted_class": (test_pd >= DEMO_THRESHOLD).astype(np.int8),
    })
    _save_parquet(LOGISTIC_5INPUT_DEMO_TEST_PREDICTIONS_PATH, predictions)
    manifest = {
        "stage": "logistic-5input-demo", "status": "PASS",
        "model_role": "secondary_ui_benchmark_only",
        "features": list(DEMO_FEATURES), "feature_count": len(DEMO_FEATURES),
        "dataset_id": split_manifest["dataset_id"],
        "canonical_dataset_sha256": xgb_manifest["canonical_dataset_sha256"],
        "split_artifact_sha256": split_hashes,
        "input_bounds_from_training_partition": xgb_manifest["input_bounds_from_training_partition"],
        "fico_input_mapping": xgb_manifest["fico_input_mapping"],
        "target_policy": xgb_manifest["target_policy"],
        "preprocessing_fit_partition": "train only",
        "preprocessing": "sanitize -> normalize missing -> median impute -> standard scale",
        "model_parameters": MODEL_PARAMETERS,
        "threshold": DEMO_THRESHOLD,
        "threshold_source": "carried forward from ML-LC-07 for fixed demo comparison; not retuned for Logistic",
        "train_rows": len(train), "validation_rows": len(validation), "frozen_test_rows": len(test),
        "validation_metrics": validation_metrics,
        "demo_model_frozen_test_metrics": test_metrics,
        "frozen_test_evaluation_is_one_shot": True,
        "frozen_test_used_for_training_or_selection": False,
        "frozen_test_evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "explanation_method": "signed coefficient * standardized input; exact log-odds decomposition",
        "model_artifact": str(LOGISTIC_5INPUT_DEMO_PATH.resolve()),
        "model_sha256": _sha256(LOGISTIC_5INPUT_DEMO_PATH),
        "test_prediction_artifact": str(LOGISTIC_5INPUT_DEMO_TEST_PREDICTIONS_PATH.resolve()),
        "test_prediction_sha256": _sha256(LOGISTIC_5INPUT_DEMO_TEST_PREDICTIONS_PATH),
        "primary_artifact_sha256_before_after": source_hashes,
        "xgboost_demo_artifact_sha256_before_after": xgb_hashes,
    }
    _save_json(LOGISTIC_5INPUT_DEMO_MANIFEST_PATH, manifest)
    return manifest


@lru_cache(maxsize=2)
def load_logistic_demo(signature: tuple[int, int, int, int]) -> tuple[Pipeline, dict[str, Any]]:
    """Nạp artifact Logistic đã khóa và xác minh schema/hash."""
    del signature
    if not LOGISTIC_5INPUT_DEMO_PATH.is_file() or not LOGISTIC_5INPUT_DEMO_MANIFEST_PATH.is_file():
        raise FileNotFoundError("Chưa có Logistic 5-input benchmark model.")
    manifest = _read_json(LOGISTIC_5INPUT_DEMO_MANIFEST_PATH)
    if (manifest.get("status") != "PASS"
            or manifest.get("features") != list(DEMO_FEATURES)
            or manifest.get("threshold") != DEMO_THRESHOLD
            or manifest.get("model_sha256") != _sha256(LOGISTIC_5INPUT_DEMO_PATH)):
        raise ValueError("Artifact/manifest Logistic 5-input không khớp.")
    pipeline = joblib.load(LOGISTIC_5INPUT_DEMO_PATH)
    if (not isinstance(pipeline, Pipeline)
            or tuple(pipeline.named_steps["normalize_missing"].feature_names_in_) != DEMO_FEATURES
            or pipeline.named_steps["model"].coef_.shape != (1, len(DEMO_FEATURES))):
        raise ValueError("Logistic pipeline không còn đúng schema năm input.")
    return pipeline, manifest


def get_logistic_demo() -> tuple[Pipeline, dict[str, Any]]:
    """Cache theo phiên bản artifact và manifest hiện tại."""
    signature = tuple(value for path in (LOGISTIC_5INPUT_DEMO_PATH, LOGISTIC_5INPUT_DEMO_MANIFEST_PATH)
                      for value in (path.stat().st_size, path.stat().st_mtime_ns))
    return load_logistic_demo(signature)


def predict_logistic_demo(values: Mapping[str, Any]) -> dict[str, Any]:
    """Dự đoán bằng benchmark đã lưu với đúng năm input biểu mẫu."""
    pipeline, manifest = get_logistic_demo()
    return predict_logistic_using_model(pipeline, values, manifest)


def predict_logistic_using_model(
    pipeline: Pipeline, values: Mapping[str, Any], manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Tính PD, score/tier/EL và đóng góp tuyến tính của chính hồ sơ này."""
    checked = validate_demo_inputs(values, manifest)
    frame = pd.DataFrame([{field: checked[field] for field in DEMO_FEATURES}], columns=list(DEMO_FEATURES))
    probability = validate_probability_of_default(pipeline.predict_proba(frame)[:, 1])
    pd_value = float(probability[0])
    transformed = np.asarray(pipeline[:-1].transform(frame), dtype=float)
    model = pipeline.named_steps["model"]
    contributions = transformed[0] * model.coef_[0]
    margin = float(model.decision_function(transformed)[0])
    if (transformed.shape != (1, len(DEMO_FEATURES)) or not np.isfinite(contributions).all()
            or not np.isclose(float(model.intercept_[0] + contributions.sum()), margin, atol=1e-8)):
        raise ValueError("Local Logistic explanation không đạt additivity check.")
    amount = float(checked["loan_amnt"])
    losses = {
        f"expected_loss_lgd_{int(lgd * 100)}": float(calculate_expected_loss([pd_value], lgd, [amount])[0])
        for lgd in LGD_OPTIONS
    }
    rows = [
        {"feature": field, "label": DISPLAY_FEATURES[field],
         "value": float(frame.iloc[0][field]), "shap_value": float(contributions[index])}
        for index, field in enumerate(DEMO_FEATURES)
    ]
    rows.sort(key=lambda row: abs(row["shap_value"]), reverse=True)
    return {
        "predicted_pd": pd_value,
        "predicted_class": int(pd_value >= DEMO_THRESHOLD),
        "threshold": DEMO_THRESHOLD,
        "risk_score": float(probability_to_risk_score([pd_value])[0]),
        "project_credit_score": int(probability_to_project_credit_score([pd_value])[0]),
        "risk_tier": str(assign_pd_risk_tier([pd_value], decision_threshold=DEMO_THRESHOLD)[0]),
        "ead_proxy": amount,
        "expected_loss": losses["expected_loss_lgd_45"],
        **losses,
        "inputs": checked,
        "shap": rows,
        "explanation_method": "linear_log_odds_contribution",
    }


def main() -> int:
    """CLI dựng benchmark đúng một lần."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()
    if not args.train:
        parser.error("Cần --train để tạo benchmark lần đầu.")
    manifest = train_logistic_demo()
    print(json.dumps({"status": manifest["status"], "validation_metrics": manifest["validation_metrics"],
                      "demo_model_frozen_test_metrics": manifest["demo_model_frozen_test_metrics"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
