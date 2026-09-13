"""Tiện ích đánh giá binary default model từ nhãn và xác suất có sẵn.

Module không gọi model, không train model và không tự tối ưu threshold trên test.
Threshold để báo cáo final phải được chốt từ validation trước khi frozen test được
đánh giá đúng một lần.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


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
            "precision",
            "recall",
            "f1",
            "accuracy",
            "threshold",
        ],
    )


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
