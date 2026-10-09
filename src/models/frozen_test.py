"""Đánh giá một lần trên frozen test với model và threshold đã khóa."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from src.config import CANONICAL_DATASET_PATH, DATA_DICTIONARY_PATH, DATASET_MANIFEST_PATH, MODELING_DIR, REPORTS_DIR
from src.models.evaluation import evaluate_binary_classifier
from src.models.modeling_pipeline import GateError

STAGE = "ml-lc-08"
LOCKED_CANDIDATE = "xgboost_candidate"
LOCKED_THRESHOLD = 0.22009515762329102
EXPECTED_TEST_ROWS = 269070
METRIC_NAMES = ("roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateError(f"Thiếu artifact: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise GateError(f"Không đọc được JSON: {path}") from exc


def _validate_locks(output_dir: Path, reports_dir: Path, hash_file: Any, expected_rows: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Chặn stage trước khi đọc một dòng frozen test nào."""
    m06_path = output_dir / "ml_lc_06_manifest.json"
    m07_path = output_dir / "ml_lc_07_manifest.json"
    model_path = output_dir / "xgboost_candidate.joblib"
    m05_path = output_dir / "ml_lc_05_manifest.json"
    m06, m07, m05 = (_read_json(path) for path in (m06_path, m07_path, m05_path))
    s06 = _read_json(reports_dir / "tv1_stages/state/ml-lc-06.json")
    s07 = _read_json(reports_dir / "tv1_stages/state/ml-lc-07.json")
    if any(state.get("stage") != stage or state.get("status") != "PASS"
           for state, stage in ((s06, "ml-lc-06"), (s07, "ml-lc-07"))):
        raise GateError("ML-LC-06/07 state chưa PASS.")
    if (m06.get("stage") != "ml-lc-06" or m06.get("status") != "PASS"
            or m06.get("selected_candidate") != LOCKED_CANDIDATE
            or m06.get("threshold_selected") is not False
            or m06.get("frozen_test_used_for_selection") is not False
            or m06.get("frozen_test_used_for_evaluation") is not False
            or m06.get("selected_model_artifact_path") != str(model_path)):
        raise GateError("ML-LC-06 candidate lock không hợp lệ.")
    if (m07.get("stage") != "ml-lc-07" or m07.get("status") != "PASS"
            or m07.get("locked_candidate") != LOCKED_CANDIDATE
            or m07.get("selected_threshold") != LOCKED_THRESHOLD
            or s07.get("selected_candidate") != LOCKED_CANDIDATE
            or s07.get("selected_threshold") != LOCKED_THRESHOLD
            or m07.get("selection_partition") != "validation"
            or m07.get("selection_rule") != "maximize_f1"
            or m07.get("threshold_selected") is not True
            or m07.get("candidate_changed") is not False
            or m07.get("model_retrained") is not False
            or m07.get("frozen_test_used_for_threshold_selection") is not False
            or m07.get("frozen_test_used_for_evaluation") is not False
            or m07.get("source_model_artifact") != str(model_path)):
        raise GateError("ML-LC-07 threshold lock không hợp lệ.")
    if (m05.get("stage") != "ml-lc-05" or m05.get("status") != "PASS"
            or not isinstance(m05.get("actual_features"), list)
            or len(m05["actual_features"]) != m05.get("actual_feature_count")
            or len(set(m05["actual_features"])) != len(m05["actual_features"])):
        raise GateError("ML-LC-05 feature artifact không hợp lệ.")
    if (m06.get("validation_rows") != m07.get("validation_rows")
            or m06.get("frozen_test_rows") != expected_rows):
        raise GateError("ML-LC-06/07 population không khớp.")
    if (hash_file(model_path) != m06.get("source_artifact_sha256", {}).get(model_path.name)
            or hash_file(model_path) != m07.get("source_model_sha256_after")
            or hash_file(m06_path) != m07.get("ml_lc_06_manifest_sha256_after")
            or hash_file(m05_path) != m06.get("source_artifact_sha256", {}).get(m05_path.name)):
        raise GateError("Model hoặc lock manifest đã thay đổi kể từ ML-LC-06/07.")
    return m06, m07, m05


def _validate_ids(output_dir: Path, split: dict[str, Any], expected_rows: int) -> pd.DataFrame:
    """Kiểm tra membership, target và tính tách biệt của ba partition."""
    frames: dict[str, pd.DataFrame] = {}
    for name in ("train", "validation", "test"):
        frame = pd.read_parquet(output_dir / f"{name}_ids.parquet")
        if (frame.columns.tolist() != ["loan_id", "target", "split"]
                or len(frame) != split.get(f"{name}_rows")
                or frame["loan_id"].isna().any() or not frame["loan_id"].is_unique
                or frame["target"].isna().any() or not frame["target"].isin([0, 1]).all()
                or not frame["split"].eq(name).all()
                or {str(k): int(v) for k, v in frame["target"].value_counts().items()}
                != split.get(f"{name}_target_counts")):
            raise GateError(f"{name}_ids không khớp frozen split contract.")
        frames[name] = frame
    if len(frames["test"]) != expected_rows or split.get("test_rows") != expected_rows:
        raise GateError("Frozen test row count không khớp khóa.")
    sets = {name: set(frame["loan_id"]) for name, frame in frames.items()}
    if any(sets[a] & sets[b] for a, b in (("train", "test"), ("validation", "test"), ("train", "validation"))):
        raise GateError("Frozen split có loan_id overlap.")
    if (split.get("stage_status") != "PASS" or split.get("frozen") is not True
            or sum(len(frame) for frame in frames.values()) != split.get("source_rows")
            or len(sets["train"] | sets["validation"] | sets["test"]) != split.get("union_rows")):
        raise GateError("Frozen split manifest/coverage không hợp lệ.")
    return frames["test"]


def _metrics(target: pd.Series, probabilities: np.ndarray, threshold: float) -> dict[str, Any]:
    """Đánh giá duy nhất tại ngưỡng đã khóa; không tìm ngưỡng mới."""
    result = evaluate_binary_classifier(target, probabilities, threshold=threshold)
    matrix = result.confusion.astype(int)
    return {
        "roc_auc": result.roc_auc, "pr_auc": result.pr_auc,
        "log_loss": float(log_loss(target, probabilities, labels=[0, 1])),
        "brier_score": float(brier_score_loss(target, probabilities)),
        "precision": result.precision, "recall": result.recall,
        "f1": result.f1, "accuracy": result.accuracy,
        "confusion_matrix": matrix.tolist(),
        "tn": int(matrix[0, 0]), "fp": int(matrix[0, 1]),
        "fn": int(matrix[1, 0]), "tp": int(matrix[1, 1]),
    }


def _report(payload: dict[str, Any]) -> str:
    test = payload["test_metrics"]
    validation = payload["validation_reference_metrics"]
    deltas = payload["generalization_delta"]
    rows = [f"| {name} | {validation[name]:.6f} | {test[name]:.6f} | {deltas[name]:+.6f} |"
            for name in METRIC_NAMES]
    return "\n".join([
        "# ML-LC-08 — Frozen Test Evaluation", "",
        "## 1. Mục tiêu", "", "Frozen Test là bài thi cuối trên dữ liệu chưa dùng để huấn luyện hay chọn cấu hình.", "",
        "## 2. Cấu hình khóa trước test", "",
        f"Model: `{LOCKED_CANDIDATE}` (ML-LC-06 validation). Threshold: `{LOCKED_THRESHOLD}` (ML-LC-07 validation).", "",
        "## 3. Frozen test", "", f"{payload['test_rows']:,} dòng; không overlap train/validation; nhãn khớp canonical.", "",
        "## 4. Kết quả cuối", "",
        f"ROC-AUC {test['roc_auc']:.6f}; PR-AUC {test['pr_auc']:.6f}; Log Loss {test['log_loss']:.6f}; Brier {test['brier_score']:.6f}.",
        f"Precision {test['precision']:.6f}; Recall {test['recall']:.6f}; F1 {test['f1']:.6f}; Accuracy {test['accuracy']:.6f}.",
        f"Confusion [[TN, FP], [FN, TP]]: `{test['confusion_matrix']}`.", "",
        "## 5. Validation so với test (test trừ validation)", "",
        "| Metric | Validation | Test | Delta |", "|---|---:|---:|---:|", *rows, "",
        "## 6. Diễn giải", "",
        ("Một số chỉ số giảm trên dữ liệu chưa từng dùng; đây là generalization gap cần báo cáo, không quay lại tối ưu bằng test."
         if any(deltas[name] < -0.01 for name in ("roc_auc", "pr_auc", "f1"))
         else "Hiệu năng trên dữ liệu chưa từng dùng tương đối gần validation; không dùng test để tối ưu lại."), "",
        "## 7. Tính toàn vẹn", "",
        "Không retrain, đổi feature/candidate/threshold, fit preprocessing hoặc dùng test cho chọn mô hình/ngưỡng."
        " Test thật chỉ đánh giá một lần; unit test dùng fixture synthetic không mở test thật.", "",
        "## 8. Tiếp theo", "", "ML-LC-09 Explainability; không sửa cấu hình theo kết quả test.", "",
    ])


def run_ml_lc_08(
    *, canonical_path: Path = CANONICAL_DATASET_PATH,
    dictionary_path: Path = DATA_DICTIONARY_PATH,
    manifest_path: Path = DATASET_MANIFEST_PATH,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
    expected_test_rows: int = EXPECTED_TEST_ROWS,
) -> dict[str, Any]:
    """Thực hiện đúng một lần; mọi rerun hoặc output dở dang đều fail closed."""
    from src.models.tv1_runner import _atomic_write_dataframe, _atomic_write_text, _sha256

    output_dir, reports_dir = Path(output_dir), Path(reports_dir)
    m06, m07, m05 = _validate_locks(output_dir, reports_dir, _sha256, expected_test_rows)
    prediction_path = output_dir / "ml_lc_08_frozen_test_predictions.parquet"
    result_path = output_dir / "ml_lc_08_manifest.json"
    report_path = reports_dir / "tv1_stages/ml-lc-08.md"
    state_path = reports_dir / "tv1_stages/state/ml-lc-08.json"
    reservation_path = output_dir / "ml_lc_08_one_shot.lock"
    outputs = (prediction_path, result_path, report_path, state_path, reservation_path)
    if any(path.exists() for path in outputs):
        raise GateError("ML-LC-08 đã được đánh giá hoặc có output/lock dở dang; không mở frozen test lần nữa.")
    protected = [output_dir / "xgboost_candidate.joblib", output_dir / "ml_lc_06_manifest.json",
                 output_dir / "ml_lc_07_manifest.json"]
    hashes_before = {path.name: _sha256(path) for path in protected}
    split_path = output_dir / "split_manifest.json"
    split = _read_json(split_path)
    if (split.get("stage") != "ml-lc-02" or split.get("dataset_id") != m05.get("dataset_id")
            or split.get("test_rows") != expected_test_rows
            or m06.get("frozen_test_rows") != expected_test_rows):
        raise GateError("Split manifest không khớp locked modeling population.")
    tv2 = _read_json(Path(manifest_path))
    if (tv2.get("dataset_id") != split.get("dataset_id") or tv2.get("run_status") != "PASS"
            or tv2.get("quality_status") != "PASS" or tv2.get("leakage_gate") != "PASS"
            or tv2.get("labeled_rows") != split.get("source_rows")):
        raise GateError("TV2 canonical handoff không còn PASS/khớp split.")
    features = m05["actual_features"]
    dictionary = pd.read_csv(dictionary_path).set_index("column_name")
    if (not set(features).issubset(dictionary.index)
            or not dictionary.loc[features, "policy_class"].isin(["APPLICATION_TIME", "CREDIT_SNAPSHOT"]).all()
            or not dictionary.loc[features, "model_eligible_default"].astype(str).str.lower().eq("true").all()):
        raise GateError("Locked features không còn được dictionary cho phép.")
    test_ids = _validate_ids(output_dir, split, expected_test_rows)
    columns = ["loan_id", "target", *features]
    dataset = pd.read_parquet(canonical_path, columns=columns)
    if (len(dataset) != tv2["labeled_rows"] or dataset["loan_id"].isna().any()
            or not dataset["loan_id"].is_unique):
        raise GateError("Canonical dataset không đúng row count hoặc loan_id.")
    if not set(test_ids["loan_id"]).issubset(set(dataset["loan_id"])):
        raise GateError("Frozen test IDs không thuộc canonical dataset.")
    ordered = dataset.set_index("loan_id").loc[test_ids["loan_id"].tolist()]
    if not ordered["target"].reset_index(drop=True).eq(test_ids["target"].reset_index(drop=True)).all():
        raise GateError("Canonical target mismatch với frozen test target.")
    model = joblib.load(protected[0])
    if not hasattr(model, "predict_proba") or not hasattr(model, "named_steps"):
        raise GateError("Locked model không phải fitted probability pipeline.")
    if hasattr(model, "feature_names_in_") and list(model.feature_names_in_) != features:
        raise GateError("Serialized pipeline feature schema khác locked feature list.")
    try:
        reservation_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(reservation_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise GateError("ML-LC-08 đã được đặt one-shot lock.") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(datetime.now(timezone.utc).isoformat())
    probabilities = np.asarray(model.predict_proba(ordered.loc[:, features])[:, 1], dtype=float)
    if (probabilities.shape != (expected_test_rows,) or not np.isfinite(probabilities).all()
            or not ((0 <= probabilities) & (probabilities <= 1)).all()):
        raise GateError("Frozen test probabilities không hợp lệ.")
    predictions = pd.DataFrame({"loan_id": test_ids["loan_id"].to_numpy(),
                                "target": test_ids["target"].astype(int).to_numpy(),
                                "predicted_pd": probabilities,
                                "predicted_class": (probabilities >= LOCKED_THRESHOLD).astype(int)})
    metrics = _metrics(test_ids["target"], probabilities, LOCKED_THRESHOLD)
    if sum(map(sum, metrics["confusion_matrix"])) != expected_test_rows:
        raise GateError("Confusion matrix không khớp test rows.")
    validation = {**{name: m06["metrics"][LOCKED_CANDIDATE][name] for name in ("roc_auc", "pr_auc")},
                  **{name: m07["selected_metrics"][name] for name in ("precision", "recall", "f1", "accuracy")},
                  "confusion_matrix": m07["selected_metrics"]["confusion_matrix"]}
    if any(_sha256(path) != hashes_before[path.name] for path in protected):
        raise GateError("Protected model/lock artifact bị thay đổi trong lúc đánh giá.")
    payload = {
        "stage": STAGE, "status": "PASS", "evaluation_type": "one_shot_frozen_test",
        "selected_candidate": LOCKED_CANDIDATE, "selected_threshold": LOCKED_THRESHOLD,
        "threshold_source": "ml-lc-07 validation", "model_selection_source": "ml-lc-06 validation",
        "test_rows": expected_test_rows, "model_artifact_path": str(protected[0]),
        "test_prediction_path": str(prediction_path), "test_metrics": metrics,
        "validation_reference_metrics": validation,
        "generalization_delta": {name: metrics[name] - validation[name] for name in METRIC_NAMES},
        "model_retrained": False, "candidate_changed": False, "threshold_changed": False,
        "frozen_test_used_for_model_selection": False,
        "frozen_test_used_for_threshold_selection": False,
        "frozen_test_used_for_final_evaluation": True,
        "frozen_test_evaluation_rows": expected_test_rows, "test_evaluated": True,
        "next_stage": "ml-lc-09", "protected_sha256_before": hashes_before,
        "protected_sha256_after": {path.name: _sha256(path) for path in protected},
        "input_sha256": {path.name: _sha256(path) for path in
                         (split_path, output_dir / "test_ids.parquet", Path(canonical_path), Path(manifest_path))},
    }
    _atomic_write_dataframe(prediction_path, predictions, format="parquet")
    payload["test_prediction_sha256"] = _sha256(prediction_path)
    _atomic_write_text(result_path, json.dumps(payload, ensure_ascii=False, indent=2))
    _atomic_write_text(report_path, _report(payload))
    _atomic_write_text(state_path, json.dumps({
        "stage": STAGE, "status": "PASS", "title": "One-shot Frozen Test Evaluation",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(result_path), "report_path": str(report_path),
    }, ensure_ascii=False, indent=2))
    if any(_sha256(path) != hashes_before[path.name] for path in protected):
        raise GateError("Protected artifacts changed after persistence.")
    return payload
