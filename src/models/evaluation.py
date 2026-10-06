"""Tiện ích đánh giá binary default model từ nhãn và xác suất có sẵn.

Module không gọi model, không train model và không tự tối ưu threshold trên test.
Threshold để báo cáo final phải được chốt từ validation trước khi frozen test được
đánh giá đúng một lần.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


ROC_AUC_CLOSE_GAP = 0.002
PR_AUC_CLOSE_GAP = 0.005
CANDIDATE_SIMPLICITY_ORDER = (
    "logistic_baseline", "logistic_weighted", "xgboost_candidate",
)
CANDIDATE_COMPLEXITY = {
    "logistic_baseline": 0, "logistic_weighted": 0, "xgboost_candidate": 1,
}


@dataclass(frozen=True)
class CurveData:
    """Dữ liệu curve để caller tự vẽ hoặc xuất theo nhu cầu."""

    x: np.ndarray
    y: np.ndarray
    thresholds: np.ndarray


@dataclass(frozen=True)
class BinaryEvaluationResult:
    """Kết quả đánh giá binary classifier tại một threshold đã cho."""

    roc_auc: float
    pr_auc: float
    precision: float
    recall: float
    f1: float
    accuracy: float
    threshold: float
    confusion: np.ndarray
    roc_curve: CurveData
    precision_recall_curve: CurveData

    def metrics_dict(self) -> dict[str, float]:
        """Trả metrics có thể dùng cho bảng so sánh, không gồm model name."""
        return {
            "roc_auc": self.roc_auc,
            "pr_auc": self.pr_auc,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "accuracy": self.accuracy,
            "threshold": self.threshold,
        }


def evaluate_binary_classifier(
    y_true: Sequence[int] | np.ndarray | pd.Series,
    y_proba: Sequence[float] | np.ndarray | pd.Series,
    *,
    threshold: float,
) -> BinaryEvaluationResult:
    """Đánh giá binary default predictions tại threshold do caller cung cấp.

    ``y_pred`` được tạo theo ``y_proba >= threshold``. AUC, precision, recall và
    F1 là metrics chính; accuracy chỉ là thông tin bổ sung. Hàm phù hợp để đánh
    giá validation hoặc frozen test sau khi threshold đã được quyết định, không
    dùng để chọn threshold trên test set.

    Raises:
        ValueError: Nếu label/probability/threshold không hợp lệ, hoặc y_true
            không chứa đủ hai lớp để ROC AUC và curves có ý nghĩa.
    """
    labels, probabilities, validated_threshold = _validate_evaluation_inputs(
        y_true,
        y_proba,
        threshold=threshold,
    )
    predicted_labels = (probabilities >= validated_threshold).astype(int)
    fpr, tpr, roc_thresholds = roc_curve(labels, probabilities)
    precision_values, recall_values, pr_thresholds = precision_recall_curve(
        labels,
        probabilities,
    )

    return BinaryEvaluationResult(
        roc_auc=float(roc_auc_score(labels, probabilities)),
        pr_auc=float(average_precision_score(labels, probabilities)),
        precision=float(precision_score(labels, predicted_labels, zero_division=0)),
        recall=float(recall_score(labels, predicted_labels, zero_division=0)),
        f1=float(f1_score(labels, predicted_labels, zero_division=0)),
        accuracy=float(accuracy_score(labels, predicted_labels)),
        threshold=validated_threshold,
        confusion=confusion_matrix(labels, predicted_labels, labels=[0, 1]),
        roc_curve=CurveData(x=fpr, y=tpr, thresholds=roc_thresholds),
        precision_recall_curve=CurveData(
            x=recall_values,
            y=precision_values,
            thresholds=pr_thresholds,
        ),
    )


def build_validation_threshold_table(
    y_true: Sequence[int] | np.ndarray | pd.Series,
    y_proba: Sequence[float] | np.ndarray | pd.Series,
    *,
    thresholds: Sequence[float],
) -> pd.DataFrame:
    """Tạo bảng threshold trên validation data; không chọn threshold cuối.

    Chỉ gọi hàm này với validation partition. Không dùng output để tối ưu
    threshold trên frozen test set.
    """
    labels, probabilities, _ = _validate_evaluation_inputs(
        y_true,
        y_proba,
        threshold=0.5,
    )
    if len(thresholds) == 0:
        raise ValueError("thresholds phải có ít nhất một giá trị validation.")

    rows: list[dict[str, float | int]] = []
    for threshold in thresholds:
        validated_threshold = _validate_threshold(threshold)
        predictions = (probabilities >= validated_threshold).astype(int)
        matrix = confusion_matrix(labels, predictions, labels=[0, 1])
        rows.append(
            {
                "threshold": validated_threshold,
                "precision": float(precision_score(labels, predictions, zero_division=0)),
                "recall": float(recall_score(labels, predictions, zero_division=0)),
                "f1": float(f1_score(labels, predictions, zero_division=0)),
                "false_positive": int(matrix[0, 1]),
                "false_negative": int(matrix[1, 0]),
            }
        )

    return pd.DataFrame(rows)


def compare_evaluation_results(
    results: Mapping[str, BinaryEvaluationResult],
) -> pd.DataFrame:
    """Đưa các kết quả đã tính vào DataFrame để so sánh model minh bạch."""
    rows = [
        {"model": model_name, **result.metrics_dict()}
        for model_name, result in results.items()
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "model",
            "roc_auc",
            "pr_auc",
            "precision",
            "recall",
            "f1",
            "accuracy",
            "threshold",
        ],
    )


def align_validation_predictions(
    predictions: Mapping[str, pd.DataFrame],
    validation_ids: pd.DataFrame,
    *,
    expected_rows: int,
) -> dict[str, pd.DataFrame]:
    """Kiểm tra và sắp ba prediction artifacts theo đúng frozen validation IDs."""

    if not predictions:
        raise ValueError("Không có validation prediction artifact để so sánh.")
    if not {"loan_id", "target"}.issubset(validation_ids.columns):
        raise ValueError("Frozen validation IDs thiếu loan_id/target.")
    if (len(validation_ids) != expected_rows or validation_ids["loan_id"].isna().any()
            or not validation_ids["loan_id"].is_unique
            or validation_ids["target"].isna().any()
            or not validation_ids["target"].isin([0, 1]).all()):
        raise ValueError("Frozen validation IDs/target không hợp lệ.")
    reference = validation_ids.set_index("loan_id")["target"]
    reference_ids = set(reference.index)
    aligned: dict[str, pd.DataFrame] = {}
    for name, frame in predictions.items():
        if frame.columns.tolist() != ["loan_id", "target", "predicted_pd"]:
            raise ValueError(f"{name}: prediction schema không hợp lệ.")
        if (len(frame) != expected_rows or frame["loan_id"].isna().any()
                or not frame["loan_id"].is_unique
                or frame["target"].isna().any()
                or not frame["target"].isin([0, 1]).all()):
            raise ValueError(f"{name}: validation IDs/target không hợp lệ.")
        if set(frame["loan_id"]) != reference_ids:
            raise ValueError(f"{name}: loan_id không khớp frozen validation population.")
        ordered = frame.set_index("loan_id").loc[reference.index]
        if not ordered["target"].eq(reference).all():
            raise ValueError(f"{name}: target theo loan_id không khớp frozen validation.")
        try:
            probabilities = ordered["predicted_pd"].to_numpy(dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name}: predicted_pd phải là số.") from exc
        if not np.isfinite(probabilities).all() or not np.all((0 <= probabilities) & (probabilities <= 1)):
            raise ValueError(f"{name}: predicted_pd phải hữu hạn trong [0,1].")
        aligned[name] = ordered.reset_index()
    return aligned


def evaluate_validation_predictions(frame: pd.DataFrame) -> dict[str, float | list[list[int]]]:
    """Tính lại ranking, chất lượng PD và chẩn đoán tại ngưỡng tham chiếu 0.5."""

    labels = frame["target"].to_numpy(dtype=int)
    probabilities = frame["predicted_pd"].to_numpy(dtype=float)
    result = evaluate_binary_classifier(labels, probabilities, threshold=0.5)
    return {
        **result.metrics_dict(),
        "log_loss": float(log_loss(labels, probabilities, labels=[0, 1])),
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "confusion_matrix": result.confusion.astype(int).tolist(),
    }


def select_validation_candidate(metrics: Mapping[str, Mapping[str, float]]) -> str:
    """Khóa candidate bằng ROC-AUC, PR-AUC và thứ tự đơn giản đã công bố."""

    if set(metrics) != set(CANDIDATE_SIMPLICITY_ORDER):
        raise ValueError("Phải có đúng ba candidate ML-LC-03/04/05.")
    if any(not np.isfinite([row["roc_auc"], row["pr_auc"]]).all() for row in metrics.values()):
        raise ValueError("ROC-AUC/PR-AUC phải hữu hạn.")
    best_roc = max(row["roc_auc"] for row in metrics.values())
    close_roc = [name for name in CANDIDATE_SIMPLICITY_ORDER
                 if best_roc - metrics[name]["roc_auc"] <= ROC_AUC_CLOSE_GAP]
    best_pr = max(metrics[name]["pr_auc"] for name in close_roc)
    close_pr = [name for name in close_roc
                if best_pr - metrics[name]["pr_auc"] <= PR_AUC_CLOSE_GAP]
    return min(close_pr, key=lambda name: (
        CANDIDATE_COMPLEXITY[name], metrics[name]["log_loss"],
        metrics[name]["brier_score"], CANDIDATE_SIMPLICITY_ORDER.index(name),
    ))


def select_validation_threshold(
    y_true: Sequence[int] | np.ndarray | pd.Series,
    y_proba: Sequence[float] | np.ndarray | pd.Series,
    *,
    tie_tolerance: float = 1e-12,
    diagnostic_thresholds: Sequence[float] = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60),
) -> dict[str, Any]:
    """Tìm operating threshold F1 tối đa chính xác trên prediction scores validation."""

    labels, probabilities, _ = _validate_evaluation_inputs(y_true, y_proba, threshold=0.5)
    if not np.isfinite(tie_tolerance) or tie_tolerance < 0:
        raise ValueError("tie_tolerance phải hữu hạn và không âm.")
    precision_curve, recall_curve, candidate_thresholds = precision_recall_curve(
        labels, probabilities,
    )
    candidate_f1 = np.divide(
        2 * precision_curve[:-1] * recall_curve[:-1],
        precision_curve[:-1] + recall_curve[:-1],
        out=np.zeros_like(precision_curve[:-1]),
        where=(precision_curve[:-1] + recall_curve[:-1]) > 0,
    )
    exact_candidates = pd.DataFrame({
        "threshold": candidate_thresholds,
        "precision": precision_curve[:-1],
        "recall": recall_curve[:-1],
        "f1": candidate_f1,
    })
    chosen = _select_threshold_row(exact_candidates, tie_tolerance=tie_tolerance)
    selected_threshold = float(chosen["threshold"])
    if not np.isfinite(selected_threshold) or not 0 <= selected_threshold <= 1:
        raise ValueError("selected threshold không hữu hạn hoặc ngoài [0,1].")

    supplied = np.asarray(diagnostic_thresholds, dtype=float)
    if supplied.ndim != 1 or not np.isfinite(supplied).all() or np.any((supplied < 0) | (supplied > 1)):
        raise ValueError("diagnostic thresholds phải là vector hữu hạn trong [0,1].")
    thresholds = np.unique(np.concatenate((candidate_thresholds, supplied, [selected_threshold])))
    sorted_indices = np.argsort(probabilities, kind="mergesort")
    sorted_probabilities = probabilities[sorted_indices]
    sorted_positive = labels[sorted_indices].astype(np.int64)
    prefix_positive = np.concatenate(([0], np.cumsum(sorted_positive)))
    start = np.searchsorted(sorted_probabilities, thresholds, side="left")
    predicted_positive = len(labels) - start
    true_positive = int(labels.sum()) - prefix_positive[start]
    false_positive = predicted_positive - true_positive
    false_negative = int(labels.sum()) - true_positive
    true_negative = len(labels) - int(labels.sum()) - false_positive
    precision = np.divide(true_positive, predicted_positive,
                          out=np.zeros(len(thresholds), dtype=float), where=predicted_positive > 0)
    recall = true_positive / int(labels.sum())
    f1 = np.divide(2 * precision * recall, precision + recall,
                   out=np.zeros(len(thresholds), dtype=float), where=(precision + recall) > 0)
    accuracy = (true_positive + true_negative) / len(labels)
    table = pd.DataFrame({
        "threshold": thresholds,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "tn": true_negative,
        "fp": false_positive,
        "fn": false_negative,
        "tp": true_positive,
        "predicted_positive_count": predicted_positive,
        "predicted_negative_count": len(labels) - predicted_positive,
        "predicted_positive_rate": predicted_positive / len(labels),
        "specificity": np.divide(true_negative, len(labels) - int(labels.sum()),
                                  out=np.zeros(len(thresholds), dtype=float),
                                  where=(len(labels) - int(labels.sum())) > 0),
        "selected": np.isclose(thresholds, selected_threshold, rtol=0, atol=0),
    })
    if int(table["selected"].sum()) != 1:
        raise ValueError("Threshold table phải có đúng một selected row.")
    selected_row = table.loc[table["selected"]].iloc[0]
    if abs(float(selected_row["f1"]) - float(exact_candidates["f1"].max())) > tie_tolerance:
        raise ValueError("selected F1 không đạt maximum theo tie tolerance.")
    selected_metrics = {
        key: (float(selected_row[key]) if key in {"precision", "recall", "f1", "accuracy"}
              else int(selected_row[key]))
        for key in ("precision", "recall", "f1", "accuracy", "tn", "fp", "fn", "tp")
    }
    selected_metrics["confusion_matrix"] = [
        [selected_metrics["tn"], selected_metrics["fp"]],
        [selected_metrics["fn"], selected_metrics["tp"]],
    ]
    reference = evaluate_binary_classifier(labels, probabilities, threshold=0.5)
    reference_metrics = {
        "precision": reference.precision, "recall": reference.recall,
        "f1": reference.f1, "accuracy": reference.accuracy,
        "confusion_matrix": reference.confusion.astype(int).tolist(),
        "tn": int(reference.confusion[0, 0]), "fp": int(reference.confusion[0, 1]),
        "fn": int(reference.confusion[1, 0]), "tp": int(reference.confusion[1, 1]),
    }
    return {
        "selected_threshold": selected_threshold,
        "selected_metrics": selected_metrics,
        "reference_metrics": reference_metrics,
        "max_f1": float(exact_candidates["f1"].max()),
        "tie_tolerance": float(tie_tolerance),
        "threshold_table": table,
    }


def _select_threshold_row(candidates: pd.DataFrame, *, tie_tolerance: float) -> pd.Series:
    """Áp dụng thứ tự F1, recall, precision, threshold cao nhất."""

    if candidates.empty or not {"f1", "recall", "precision", "threshold"}.issubset(candidates.columns):
        raise ValueError("Không có threshold candidates hợp lệ.")
    max_f1 = float(candidates["f1"].max())
    tied = candidates.loc[(max_f1 - candidates["f1"]) <= tie_tolerance]
    tied = tied.loc[tied["recall"] == tied["recall"].max()]
    tied = tied.loc[tied["precision"] == tied["precision"].max()]
    return tied.sort_values("threshold", ascending=False, kind="mergesort").iloc[0]


def _validate_evaluation_inputs(
    y_true: Sequence[int] | np.ndarray | pd.Series,
    y_proba: Sequence[float] | np.ndarray | pd.Series,
    *,
    threshold: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Chuẩn hóa và kiểm tra input trước khi gọi sklearn metrics."""
    labels = np.asarray(y_true)
    probabilities = np.asarray(y_proba)
    if labels.ndim != 1 or probabilities.ndim != 1:
        raise ValueError("y_true và y_proba phải là vector một chiều.")
    if len(labels) == 0:
        raise ValueError("y_true và y_proba không được rỗng.")
    if len(labels) != len(probabilities):
        raise ValueError("y_true và y_proba phải có cùng số phần tử.")

    if pd.isna(labels).any():
        raise ValueError("y_true không được chứa giá trị null.")
    if not set(labels).issubset({0, 1}) or len(set(labels)) != 2:
        raise ValueError("y_true phải chứa cả hai lớp 0 và 1.")

    try:
        probabilities = probabilities.astype(float)
    except (TypeError, ValueError) as exc:
        raise ValueError("y_proba phải là xác suất dạng số trong [0, 1].") from exc
    if not np.isfinite(probabilities).all() or not np.all(
        (probabilities >= 0) & (probabilities <= 1)
    ):
        raise ValueError("y_proba phải là xác suất hữu hạn trong [0, 1].")

    return labels.astype(int), probabilities, _validate_threshold(threshold)


def _validate_threshold(threshold: float) -> float:
    """Kiểm tra threshold xác suất đóng trong [0, 1]."""
    if isinstance(threshold, bool) or not isinstance(threshold, Real):
        raise ValueError("threshold phải là một số trong [0, 1].")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold phải nằm trong [0, 1].")
    return float(threshold)
