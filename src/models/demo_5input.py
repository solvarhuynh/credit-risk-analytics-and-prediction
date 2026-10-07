"""Mô hình dự đoán demo riêng dùng năm đầu vào hiển thị trên ứng dụng Dash."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from src.config import (
    CANONICAL_DATASET_PATH,
    DATA_DICTIONARY_PATH,
    DATASET_MANIFEST_PATH,
    ML_LC_08_MANIFEST_PATH,
    ML_LC_08_PREDICTIONS_PATH,
    ML_LC_12_MANIFEST_PATH,
    MODELING_DIR,
    XGBOOST_5INPUT_DEMO_MANIFEST_PATH,
    XGBOOST_5INPUT_DEMO_PATH,
    XGBOOST_5INPUT_DEMO_TEST_LOCK_PATH,
    XGBOOST_5INPUT_DEMO_TEST_PREDICTIONS_PATH,
)
from src.models.cost_optimization import calculate_expected_loss
from src.models.preprocess_pipeline import NormalizePandasMissing, build_xgboost_preprocessor
from src.models.scoring import (
    ML_LC_10_LOCKED_THRESHOLD,
    assign_pd_risk_tier,
    probability_to_project_credit_score,
    probability_to_risk_score,
    validate_probability_of_default,
)


DEMO_FEATURES = ("loan_amnt", "annual_inc", "dti", "term_months", "fico_avg")
DISPLAY_FEATURES = {
    "loan_amnt": "Số tiền vay",
    "annual_inc": "Thu nhập năm",
    "dti": "DTI",
    "term_months": "Kỳ hạn vay",
    "fico_avg": "Điểm FICO",
}
DEFAULT_LGD = 0.45
LGD_OPTIONS = (0.30, 0.45, 0.60)
MODEL_PARAMETERS = {
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "tree_method": "hist",
    "n_jobs": 4,
}


class SanitizeDemoInputs(BaseEstimator, TransformerMixin):
    """Biến income không dương và DTI âm của nguồn thành missing trước imputation."""

    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> "SanitizeDemoInputs":
        _validate_feature_frame(X)
        self.feature_names_in_ = np.asarray(DEMO_FEATURES, dtype=object)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        _validate_feature_frame(X)
        result = X.loc[:, list(DEMO_FEATURES)].copy()
        result["annual_inc"] = pd.to_numeric(result["annual_inc"], errors="coerce")
        result["dti"] = pd.to_numeric(result["dti"], errors="coerce")
        result.loc[result["annual_inc"] <= 0, "annual_inc"] = np.nan
        result.loc[result["dti"] < 0, "dti"] = np.nan
        return result


# Stable pickle path is required when training via python -m (where __name__ is __main__).
SanitizeDemoInputs.__module__ = "src.models.demo_5input"


def _validate_feature_frame(frame: pd.DataFrame) -> None:
    """Bảo đảm model luôn nhận đúng năm field theo thứ tự đã khóa."""
    if not isinstance(frame, pd.DataFrame) or tuple(frame.columns) != DEMO_FEATURES:
        raise ValueError(f"Input model phải đúng schema: {list(DEMO_FEATURES)}.")


def _sha256(path: Path) -> str:
    """Tính SHA-256 theo luồng để kiểm artifact lớn mà không nạp cả file vào RAM."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    """Đọc JSON object hoặc dừng với lỗi rõ ràng."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Manifest không phải object JSON: {path.name}.")
    return value


def _read_partition_ids(path: Path, expected_split: str) -> pd.DataFrame:
    """Đọc ID/target của một split và kiểm tra grain/label."""
    frame = pd.read_parquet(path, columns=["loan_id", "target", "split"])
    if (frame.isna().any().any() or not frame["loan_id"].is_unique
            or not frame["target"].isin([0, 1]).all()
            or not frame["split"].eq(expected_split).all()):
        raise ValueError(f"Partition {expected_split} không đạt ID/target/split contract.")
    return frame.reset_index(drop=True)


def _read_canonical_rows(
    canonical_path: Path,
    partition: pd.DataFrame,
) -> pd.DataFrame:
    """Đọc feature rows đúng theo ID list, không đọc toàn canonical vào DataFrame."""
    parquet = pq.ParquetFile(canonical_path)
    columns = ["loan_id", "target", *DEMO_FEATURES, "fico_range_low", "fico_range_high"]
    absent = sorted(set(columns) - set(parquet.schema_arrow.names))
    if absent:
        raise ValueError(f"Canonical dataset thiếu cột demo model: {absent}.")
    wanted = set(partition["loan_id"].tolist())
    pieces: list[pd.DataFrame] = []
    found: set[Any] = set()
    for group_index in range(parquet.num_row_groups):
        group = parquet.read_row_group(group_index, columns=columns).to_pandas()
        selected = group.loc[group["loan_id"].isin(wanted)].copy()
        if len(selected):
            found.update(selected["loan_id"].tolist())
            pieces.append(selected)
    if found != wanted:
        raise ValueError(f"Canonical dataset thiếu {len(wanted - found)} ID của partition.")
    frame = pd.concat(pieces, ignore_index=True)
    if len(frame) != len(partition) or frame["loan_id"].isna().any() or not frame["loan_id"].is_unique:
        raise ValueError("Canonical partition không còn một dòng trên mỗi loan_id.")
    aligned = frame.set_index("loan_id").loc[partition["loan_id"].tolist()].reset_index()
    if not aligned["target"].astype(int).equals(partition["target"].astype(int)):
        raise ValueError("Target canonical không khớp frozen split IDs.")
    fico_expected = (aligned["fico_range_low"] + aligned["fico_range_high"]) / 2
    if not np.allclose(aligned["fico_avg"].to_numpy(dtype=float), fico_expected.to_numpy(dtype=float), rtol=0, atol=0):
        raise ValueError("fico_avg không khớp trung bình fico_range_low/high trong canonical.")
    return aligned


def _primary_artifact_hashes() -> dict[str, str]:
    """Hash các artifact chính để chứng minh training demo không sửa chúng."""
    paths = (
        MODELING_DIR / "xgboost_candidate.joblib",
        MODELING_DIR / "xgboost_full_refit.joblib",
        MODELING_DIR / "ml_lc_08_manifest.json",
        MODELING_DIR / "ml_lc_08_frozen_test_predictions.parquet",
        MODELING_DIR / "ml_lc_12_manifest.json",
    )
    return {path.name: _sha256(path) for path in paths}


def _metrics(y_true: pd.Series, probabilities: np.ndarray, threshold: float) -> dict[str, Any]:
    """Tính ranking, probability và class metrics ở threshold đã khóa."""
    probabilities = validate_probability_of_default(probabilities)
    if len(y_true) != len(probabilities) or y_true.isna().any() or not y_true.isin([0, 1]).all():
        raise ValueError("Target/PD lệch kích thước hoặc target không binary.")
    classes = (probabilities >= threshold).astype(np.int8)
    matrix = confusion_matrix(y_true, classes, labels=[0, 1])
    return {
        "rows": int(len(y_true)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "pr_auc": float(average_precision_score(y_true, probabilities)),
        "log_loss": float(log_loss(y_true, probabilities, labels=[0, 1])),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "precision": float(precision_score(y_true, classes, zero_division=0)),
        "recall": float(recall_score(y_true, classes, zero_division=0)),
        "f1": float(f1_score(y_true, classes, zero_division=0)),
        "accuracy": float(accuracy_score(y_true, classes)),
        "confusion_matrix": matrix.astype(int).tolist(),
        "threshold": float(threshold),
    }


def build_demo_pipeline(
    training_features: pd.DataFrame,
    *,
    model_parameters: Mapping[str, Any] = MODEL_PARAMETERS,
) -> Pipeline:
    """Dựng preprocessing + XGBoost pipeline; mọi imputer chỉ fit ở train."""
    _validate_feature_frame(training_features)
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise RuntimeError("Thiếu xgboost; cài requirements.txt rồi thử lại.") from exc
    return Pipeline([
        ("sanitize", SanitizeDemoInputs()),
        ("normalize_missing", NormalizePandasMissing()),
        ("preprocess", build_xgboost_preprocessor(training_features, DEMO_FEATURES)),
        ("model", XGBClassifier(**dict(model_parameters))),
    ])


def _atomic_write(path: Path, writer: Any) -> None:
    """Ghi tệp tạm cạnh đích rồi thay thế nguyên tử."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.stem}-", suffix=path.suffix,
                                     delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        writer(temporary_path)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _save_joblib(path: Path, model: Any) -> None:
    """Lưu model demo hoàn chỉnh theo kiểu atomic."""
    _atomic_write(path, lambda temporary: joblib.dump(model, temporary))


def _save_parquet(path: Path, frame: pd.DataFrame) -> None:
    """Lưu prediction audit Parquet nguyên tử."""
    _atomic_write(path, lambda temporary: frame.to_parquet(temporary, index=False))


def _save_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Lưu manifest UTF-8 nguyên tử."""
    _atomic_write(path, lambda temporary: temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
    ))


def train_demo_model(
    *,
    canonical_path: Path = CANONICAL_DATASET_PATH,
    dataset_manifest_path: Path = DATASET_MANIFEST_PATH,
    split_dir: Path = MODELING_DIR,
    refit_manifest_path: Path = ML_LC_12_MANIFEST_PATH,
    primary_test_manifest_path: Path = ML_LC_08_MANIFEST_PATH,
    dictionary_path: Path = DATA_DICTIONARY_PATH,
    model_path: Path = XGBOOST_5INPUT_DEMO_PATH,
    manifest_path: Path = XGBOOST_5INPUT_DEMO_MANIFEST_PATH,
    test_predictions_path: Path = XGBOOST_5INPUT_DEMO_TEST_PREDICTIONS_PATH,
    test_lock_path: Path = XGBOOST_5INPUT_DEMO_TEST_LOCK_PATH,
) -> dict[str, Any]:
    """Fit trên train, kiểm validation và chỉ đánh giá model demo một lần trên test."""
    canonical_path, split_dir = Path(canonical_path), Path(split_dir)
    model_path, manifest_path = Path(model_path), Path(manifest_path)
    test_predictions_path, test_lock_path = Path(test_predictions_path), Path(test_lock_path)
    protected_outputs = (model_path, manifest_path, test_predictions_path, test_lock_path)
    if any(path.exists() for path in protected_outputs):
        raise FileExistsError("5-input demo model/test artifacts đã tồn tại; không train hoặc mở test lần nữa.")

    dataset_manifest = _read_json(Path(dataset_manifest_path))
    split_manifest = _read_json(split_dir / "split_manifest.json")
    refit_manifest = _read_json(Path(refit_manifest_path))
    primary_test_manifest = _read_json(Path(primary_test_manifest_path))
    dictionary = pd.read_csv(dictionary_path).set_index("column_name")
    if (not set(DEMO_FEATURES).issubset(dictionary.index)
            or not dictionary.loc[list(DEMO_FEATURES), "policy_class"].isin(
                ["APPLICATION_TIME", "CREDIT_SNAPSHOT"]
            ).all()
            or not dictionary.loc[list(DEMO_FEATURES), "model_eligible_default"].astype(str)
            .str.lower().eq("true").all()):
        raise ValueError("Năm field của demo model không đều được policy cho phép.")
    if (dataset_manifest.get("run_status") != "PASS"
            or dataset_manifest.get("quality_status") != "PASS"
            or dataset_manifest.get("leakage_gate") != "PASS"
            or split_manifest.get("stage_status") != "PASS"
            or split_manifest.get("coverage_status") != "PASS"
            or refit_manifest.get("status") != "PASS"
            or primary_test_manifest.get("status") != "PASS"):
        raise ValueError("Canonical handoff, frozen split, ML-LC-08 hoặc ML-LC-12 chưa PASS.")
    if (split_manifest.get("dataset_id") != dataset_manifest.get("dataset_id")
            or split_manifest.get("source_rows") != dataset_manifest.get("labeled_rows")
            or refit_manifest.get("canonical_dataset_sha256") != _sha256(canonical_path)):
        raise ValueError("Dataset/split/model manifest không trỏ cùng canonical population.")
    if (primary_test_manifest.get("evaluation_type") != "one_shot_frozen_test"
            or primary_test_manifest.get("test_rows") != split_manifest.get("test_rows")):
        raise ValueError("ML-LC-08 frozen test manifest không khớp partition đang khóa.")
    if refit_manifest.get("carried_forward_threshold") != ML_LC_10_LOCKED_THRESHOLD:
        raise ValueError("Threshold nguồn không khớp policy hiện tại.")

    source_hashes_before = _primary_artifact_hashes()
    canonical_hash = _sha256(canonical_path)
    split_hashes = {
        name: _sha256(split_dir / f"{name}_ids.parquet")
        for name in ("train", "validation")
    }
    train_ids = _read_partition_ids(split_dir / "train_ids.parquet", "train")
    validation_ids = _read_partition_ids(split_dir / "validation_ids.parquet", "validation")
    if set(train_ids.loan_id).intersection(set(validation_ids.loan_id)):
        raise ValueError("Train và validation bị overlap.")
    train = _read_canonical_rows(canonical_path, train_ids)
    validation = _read_canonical_rows(canonical_path, validation_ids)
    train_x = train.loc[:, list(DEMO_FEATURES)].copy()
    validation_x = validation.loc[:, list(DEMO_FEATURES)].copy()
    train_y = train["target"].astype(np.int8)
    validation_y = validation["target"].astype(np.int8)

    expected_parameters = refit_manifest.get("locked_hyperparameters")
    if expected_parameters != MODEL_PARAMETERS:
        raise ValueError("Hyperparameters nguồn không khớp cấu hình đã khóa của full-refit.")
    pipeline = build_demo_pipeline(train_x)
    source_invalid_counts = {
        "annual_inc_nonpositive_to_missing": int((train_x["annual_inc"] <= 0).sum()),
        "dti_negative_to_missing": int((train_x["dti"] < 0).sum()),
    }
    pipeline.fit(train_x, train_y)
    validation_pd = validate_probability_of_default(pipeline.predict_proba(validation_x)[:, 1])
    validation_metrics = _metrics(validation_y, validation_pd, ML_LC_10_LOCKED_THRESHOLD)

    # Đặt one-shot lock trước khi mở test IDs/label; mọi lỗi sau đây giữ lock.
    test_lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(test_lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise FileExistsError("Frozen test của demo đã được mở; không đánh giá lại.") from exc
    with os.fdopen(lock_fd, "w", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "opened_at_utc": datetime.now(timezone.utc).isoformat(),
            "model": "xgboost_5input_demo",
            "canonical_dataset_sha256": canonical_hash,
        }, ensure_ascii=False))

    test_ids = _read_partition_ids(split_dir / "test_ids.parquet", "test")
    split_hashes["test"] = _sha256(split_dir / "test_ids.parquet")
    if set(test_ids.loan_id).intersection(set(train_ids.loan_id) | set(validation_ids.loan_id)):
        raise ValueError("Frozen test bị overlap với train/validation.")
    test = _read_canonical_rows(canonical_path, test_ids)
    test_x = test.loc[:, list(DEMO_FEATURES)].copy()
    test_y = test["target"].astype(np.int8)
    test_pd = validate_probability_of_default(pipeline.predict_proba(test_x)[:, 1])
    test_class = (test_pd >= ML_LC_10_LOCKED_THRESHOLD).astype(np.int8)
    test_metrics = _metrics(test_y, test_pd, ML_LC_10_LOCKED_THRESHOLD)
    if len(test_pd) != split_manifest["test_rows"]:
        raise ValueError("Frozen test probabilities không đủ số dòng đã khóa.")

    input_bounds: dict[str, dict[str, float]] = {}
    sanitized_train = SanitizeDemoInputs().fit_transform(train_x)
    for feature in DEMO_FEATURES:
        values = pd.to_numeric(sanitized_train[feature], errors="coerce").dropna()
        if values.empty or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"Không thể xác định giới hạn nhập từ train cho {feature}.")
        input_bounds[feature] = {"min": float(values.min()), "max": float(values.max())}
    if set(train_x["term_months"].dropna().unique()) != {36, 60}:
        raise ValueError("Train partition không chứa đúng hai kỳ hạn 36/60 tháng.")

    source_hashes_after = _primary_artifact_hashes()
    if source_hashes_after != source_hashes_before:
        raise RuntimeError("Model/metrics chính bị thay đổi trong lúc dựng demo model.")

    model_path.parent.mkdir(parents=True, exist_ok=True)
    _save_joblib(model_path, pipeline)
    test_predictions = pd.DataFrame({
        "loan_id": test_ids["loan_id"].to_numpy(),
        "target": test_y.to_numpy(dtype=np.int8),
        "predicted_pd": test_pd,
        "predicted_class": test_class,
    })
    _save_parquet(test_predictions_path, test_predictions)
    manifest = {
        "stage": "demo-5input-model",
        "status": "PASS",
        "model_role": "secondary_ui_demo_only",
        "primary_model": "xgboost_full_refit_ml-lc-12",
        "primary_model_sha256_before_after": source_hashes_before["xgboost_full_refit.joblib"],
        "dataset_id": split_manifest["dataset_id"],
        "canonical_dataset_path": str(canonical_path.resolve()),
        "canonical_dataset_sha256": canonical_hash,
        "target_policy": {
            "target_0": "Fully Paid",
            "target_1": ["Charged Off", "Default"],
            "source": "canonical target from TV2 approved labeled population",
        },
        "features": list(DEMO_FEATURES),
        "feature_count": len(DEMO_FEATURES),
        "fico_input_mapping": {
            "visible_field": "Điểm FICO",
            "model_field": "fico_avg",
            "mapping": "user-entered score maps directly to canonical fico_avg",
            "canonical_definition": "(fico_range_low + fico_range_high) / 2",
            "verified_exactly_on_partitions": ["train", "validation", "frozen_test"],
        },
        "input_bounds_from_training_partition": input_bounds,
        "missing_policy": {
            "pipeline": "SanitizeDemoInputs -> NormalizePandasMissing -> median SimpleImputer -> XGBoost",
            "imputer_fit_partition": "train only",
            "annual_inc_nonpositive_to_missing_train_rows": source_invalid_counts[
                "annual_inc_nonpositive_to_missing"
            ],
            "dti_negative_to_missing_train_rows": source_invalid_counts["dti_negative_to_missing"],
            "term_months_allowed": [36, 60],
        },
        "model_artifact": str(model_path.resolve()),
        "model_sha256": _sha256(model_path),
        "model_parameters": MODEL_PARAMETERS,
        "threshold": ML_LC_10_LOCKED_THRESHOLD,
        "threshold_source": "ML-LC-07 validation, carried forward without retuning for demo model",
        "train_rows": len(train),
        "validation_rows": len(validation),
        "frozen_test_rows": len(test),
        "train_metrics_at_locked_threshold": _metrics(train_y, pipeline.predict_proba(train_x)[:, 1],
                                                       ML_LC_10_LOCKED_THRESHOLD),
        "validation_metrics": validation_metrics,
        "demo_model_frozen_test_metrics": test_metrics,
        "frozen_test_used_for_training": False,
        "frozen_test_used_for_preprocessing_fit": False,
        "frozen_test_used_for_model_or_threshold_selection": False,
        "frozen_test_used_for_evaluation": True,
        "frozen_test_evaluation_rows": len(test),
        "frozen_test_evaluation_scope": "this separate, predeclared five-input demo model only",
        "primary_ml_lc_08_metrics_changed": False,
        "primary_artifact_sha256_before": source_hashes_before,
        "primary_artifact_sha256_after": source_hashes_after,
        "split_artifact_sha256": split_hashes,
        "ml_lc_08_manifest_sha256": _sha256(Path(primary_test_manifest_path)),
        "test_prediction_artifact": str(test_predictions_path.resolve()),
        "test_prediction_sha256": _sha256(test_predictions_path),
        "frozen_test_evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_evaluation_is_one_shot": True,
        "next_step": "Serve this secondary demo artifact from the five-input Dash application.",
    }
    _save_json(manifest_path, manifest)
    return manifest


@lru_cache(maxsize=2)
def load_demo_model(signature: tuple[int, int, int, int] | None = None) -> tuple[Any, dict[str, Any]]:
    """Nạp model demo một lần và kiểm manifest/hash/schema trước khi infer."""
    del signature  # cache key comes from load_demo_model_cached below
    if not XGBOOST_5INPUT_DEMO_PATH.is_file() or not XGBOOST_5INPUT_DEMO_MANIFEST_PATH.is_file():
        raise FileNotFoundError("Chưa có 5-input demo model. Chạy lệnh huấn luyện một lần trước.")
    manifest = _read_json(XGBOOST_5INPUT_DEMO_MANIFEST_PATH)
    if (manifest.get("stage") != "demo-5input-model" or manifest.get("status") != "PASS"
            or manifest.get("features") != list(DEMO_FEATURES)
            or manifest.get("threshold") != ML_LC_10_LOCKED_THRESHOLD
            or manifest.get("model_sha256") != _sha256(XGBOOST_5INPUT_DEMO_PATH)):
        raise ValueError("5-input demo model artifact/manifest không khớp.")
    pipeline = joblib.load(XGBOOST_5INPUT_DEMO_PATH)
    if (not isinstance(pipeline, Pipeline) or not {"sanitize", "normalize_missing", "preprocess", "model"}
            .issubset(pipeline.named_steps)
            or tuple(pipeline.named_steps["normalize_missing"].feature_names_in_) != DEMO_FEATURES):
        raise ValueError("Pipeline demo không còn đúng năm input hoặc thiếu preprocessing.")
    return pipeline, manifest


def _model_file_signature() -> tuple[int, int, int, int]:
    """Tạo cache key từ timestamp/kích thước artifact và manifest."""
    return tuple(
        item
        for path in (XGBOOST_5INPUT_DEMO_PATH, XGBOOST_5INPUT_DEMO_MANIFEST_PATH)
        for item in (path.stat().st_size, path.stat().st_mtime_ns)
    )


def get_demo_model() -> tuple[Any, dict[str, Any]]:
    """Trả model đã cache theo đúng phiên bản các file local."""
    return load_demo_model(_model_file_signature())


def validate_demo_inputs(values: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, float | int]:
    """Kiểm tra năm ô giao diện và ánh xạ FICO trực tiếp sang `fico_avg`."""
    visible = ("loan_amnt", "annual_inc", "dti", "term_months", "fico_score")
    if set(values) != set(visible):
        raise ValueError("Cần nhập đủ năm thông tin khoản vay.")
    bounds = manifest["input_bounds_from_training_partition"]
    checked: dict[str, float | int] = {}
    for field in visible:
        raw = values[field]
        if isinstance(raw, bool) or raw is None or isinstance(raw, str):
            raise ValueError(f"{DISPLAY_FEATURES.get('fico_avg' if field == 'fico_score' else field, field)} cần là số hợp lệ.")
        try:
            number = float(raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{DISPLAY_FEATURES.get('fico_avg' if field == 'fico_score' else field, field)} cần là số hợp lệ.") from exc
        if not math.isfinite(number):
            raise ValueError(f"{DISPLAY_FEATURES.get('fico_avg' if field == 'fico_score' else field, field)} cần là số hữu hạn.")
        model_field = "fico_avg" if field == "fico_score" else field
        if field == "term_months":
            if number not in (36.0, 60.0):
                raise ValueError("Kỳ hạn chỉ hỗ trợ 36 hoặc 60 tháng.")
            checked[model_field] = int(number)
            continue
        limits = bounds[model_field]
        if not limits["min"] <= number <= limits["max"]:
            label = DISPLAY_FEATURES[model_field]
            raise ValueError(f"{label} phải từ {limits['min']:g} đến {limits['max']:g}.")
        if field == "annual_inc" and number <= 0:
            raise ValueError("Thu nhập năm phải lớn hơn 0.")
        checked[model_field] = number
    return checked


def predict_demo(values: Mapping[str, Any]) -> dict[str, Any]:
    """Chạy model 5-input thật, tính policy output và local SHAP của bản ghi."""
    pipeline, manifest = get_demo_model()
    return predict_demo_using_model(pipeline, values, manifest)


def predict_demo_using_model(
    pipeline: Pipeline,
    values: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Chạy fitted pipeline được truyền vào; dùng cho app và kiểm thử tích hợp."""
    checked = validate_demo_inputs(values, manifest)
    model_input = pd.DataFrame([{feature: checked[feature] for feature in DEMO_FEATURES}],
                               columns=list(DEMO_FEATURES))
    probability = validate_probability_of_default(pipeline.predict_proba(model_input)[:, 1])
    pd_value = float(probability[0])
    prediction_class = int(pd_value >= ML_LC_10_LOCKED_THRESHOLD)
    amount = float(checked["loan_amnt"])
    loss_values = {
        f"expected_loss_lgd_{int(lgd * 100)}": float(calculate_expected_loss([pd_value], lgd, [amount])[0])
        for lgd in LGD_OPTIONS
    }
    model = pipeline.named_steps["model"]
    transformed = pipeline[:-1].transform(model_input)
    import shap

    explainer = shap.TreeExplainer(model, model_output="raw")
    raw_values = explainer.shap_values(transformed, check_additivity=False)
    if isinstance(raw_values, list):
        if len(raw_values) != 1:
            raise ValueError("SHAP trả về số output không mong đợi.")
        raw_values = raw_values[0]
    contributions = np.asarray(raw_values, dtype=float)
    margin = float(np.asarray(model.predict(transformed, output_margin=True), dtype=float)[0])
    base_value = float(np.asarray(explainer.expected_value, dtype=float).reshape(-1)[0])
    if (contributions.shape != (1, len(DEMO_FEATURES)) or not np.isfinite(contributions).all()
            or abs(base_value + float(contributions.sum()) - margin) > 1e-3):
        raise ValueError("Local SHAP không đạt shape/finite/additivity check.")
    shap_rows = [
        {
            "feature": field,
            "label": DISPLAY_FEATURES[field],
            "value": float(model_input.iloc[0][field]),
            "shap_value": float(contributions[0, index]),
        }
        for index, field in enumerate(DEMO_FEATURES)
    ]
    shap_rows.sort(key=lambda row: abs(row["shap_value"]), reverse=True)
    return {
        "predicted_pd": pd_value,
        "predicted_class": prediction_class,
        "threshold": ML_LC_10_LOCKED_THRESHOLD,
        "risk_score": float(probability_to_risk_score([pd_value])[0]),
        "project_credit_score": int(probability_to_project_credit_score([pd_value])[0]),
        "risk_tier": str(assign_pd_risk_tier([pd_value], decision_threshold=ML_LC_10_LOCKED_THRESHOLD)[0]),
        "ead_proxy": amount,
        "expected_loss": loss_values["expected_loss_lgd_45"],
        **loss_values,
        "inputs": checked,
        "shap": shap_rows,
        "shap_output_space": "raw margin/log-odds",
    }


def main() -> int:
    """CLI one-shot huấn luyện/đánh giá artifact demo tách biệt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", action="store_true", help="Fit trên train và đánh giá một lần trên frozen test.")
    args = parser.parse_args()
    if not args.train:
        parser.error("Cần chỉ định --train để tạo artifact 5-input demo lần đầu.")
    result = train_demo_model()
    print(json.dumps({
        "status": result["status"],
        "model_artifact": result["model_artifact"],
        "features": result["features"],
        "validation_metrics": result["validation_metrics"],
        "demo_model_frozen_test_metrics": result["demo_model_frozen_test_metrics"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
