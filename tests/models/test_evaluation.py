"""Tests cho src.models.evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.evaluation import (
    BinaryEvaluationResult,
    build_validation_threshold_table,
    compare_evaluation_results,
    evaluate_binary_classifier,
)


def test_perfect_prediction_metrics() -> None:
    """Mô hình dự báo hoàn hảo cho metrics đạt 1.0."""
    y_true = [0, 0, 1, 1]
    y_proba = [0.1, 0.2, 0.8, 0.9]
    result = evaluate_binary_classifier(y_true, y_proba, threshold=0.5)

    assert result.roc_auc == 1.0
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.f1 == 1.0
    assert result.accuracy == 1.0
    assert result.threshold == 0.5

    # Confusion matrix: TN=2, FP=0, FN=0, TP=2
    np.testing.assert_array_equal(result.confusion, np.array([[2, 0], [0, 2]]))


def test_confusion_matrix_consistency() -> None:
    """Tổng các ô trong confusion matrix phải bằng tổng số mẫu."""
    y_true = [0, 0, 0, 1, 1]
    y_proba = [0.1, 0.6, 0.3, 0.4, 0.8]
    result = evaluate_binary_classifier(y_true, y_proba, threshold=0.5)

    assert result.confusion.sum() == len(y_true)
    assert result.confusion.shape == (2, 2)


def test_curves_have_valid_shapes() -> None:
    """ROC curve và PR curve trả về các mảng có shape hợp lệ."""
    y_true = [0, 0, 1, 1, 0, 1]
    y_proba = [0.1, 0.3, 0.7, 0.8, 0.2, 0.6]
    result = evaluate_binary_classifier(y_true, y_proba, threshold=0.5)

    assert len(result.roc_curve.x) == len(result.roc_curve.y)
    assert len(result.roc_curve.x) == len(result.roc_curve.thresholds)
    assert len(result.precision_recall_curve.x) == len(result.precision_recall_curve.y)


def test_invalid_probability_range_rejected() -> None:
    """Xác suất ngoài [0, 1] hoặc chứa inf/nan phải raise ValueError."""
    y_true = [0, 1]
    with pytest.raises(ValueError, match="xác suất"):
        evaluate_binary_classifier(y_true, [-0.1, 0.5], threshold=0.5)

    with pytest.raises(ValueError, match="xác suất"):
        evaluate_binary_classifier(y_true, [0.5, 1.2], threshold=0.5)

    with pytest.raises(ValueError, match="xác suất"):
        evaluate_binary_classifier(y_true, [np.nan, 0.5], threshold=0.5)


def test_invalid_threshold_rejected() -> None:
    """Threshold ngoài [0, 1] phải raise ValueError."""
    y_true = [0, 1]
    y_proba = [0.2, 0.8]
    with pytest.raises(ValueError, match="threshold phải nằm trong"):
        evaluate_binary_classifier(y_true, y_proba, threshold=-0.01)

    with pytest.raises(ValueError, match="threshold phải nằm trong"):
        evaluate_binary_classifier(y_true, y_proba, threshold=1.01)


def test_invalid_y_true_rejected() -> None:
    """y_true chỉ có 1 lớp hoặc chứa null phải raise ValueError."""
    with pytest.raises(ValueError, match="y_true phải chứa cả hai lớp 0 và 1"):
        evaluate_binary_classifier([0, 0, 0], [0.1, 0.2, 0.3], threshold=0.5)

    with pytest.raises(ValueError, match="không được chứa giá trị null"):
        evaluate_binary_classifier([0, np.nan], [0.1, 0.8], threshold=0.5)

    with pytest.raises(ValueError, match="y_true phải chứa cả hai lớp 0 và 1"):
        evaluate_binary_classifier([0, 2], [0.1, 0.8], threshold=0.5)


def test_length_mismatch_rejected() -> None:
    """Số lượng nhãn và xác suất không bằng nhau phải raise ValueError."""
    with pytest.raises(ValueError, match="cùng số phần tử"):
        evaluate_binary_classifier([0, 1], [0.1, 0.5, 0.9], threshold=0.5)


def test_threshold_table_generation() -> None:
    """Bảng validation threshold tạo đúng các cột mà không tự chọn optimum."""
    y_true = [0, 0, 1, 1, 0, 1]
    y_proba = [0.1, 0.3, 0.7, 0.8, 0.2, 0.6]
    thresholds = [0.3, 0.5, 0.7]

    table = build_validation_threshold_table(y_true, y_proba, thresholds=thresholds)

    assert isinstance(table, pd.DataFrame)
    assert len(table) == len(thresholds)
    expected_cols = {
        "threshold",
        "precision",
        "recall",
        "f1",
        "false_positive",
        "false_negative",
    }
    assert expected_cols.issubset(set(table.columns))
    # Bảng là báo cáo khách quan, không tự ý thêm cột decision hay select threshold
    assert "is_optimal" not in table.columns
    assert "selected" not in table.columns


def test_threshold_table_empty_thresholds_rejected() -> None:
    """Truyền thresholds rỗng phải raise ValueError."""
    with pytest.raises(ValueError, match="thresholds phải có ít nhất một giá trị"):
        build_validation_threshold_table([0, 1], [0.2, 0.8], thresholds=[])


def test_compare_evaluation_results() -> None:
    """So sánh nhiều model cho ra DataFrame có đầy đủ thông tin."""
    y_true = [0, 0, 1, 1]
    res_a = evaluate_binary_classifier(y_true, [0.1, 0.2, 0.8, 0.9], threshold=0.5)
    res_b = evaluate_binary_classifier(y_true, [0.2, 0.4, 0.6, 0.7], threshold=0.5)

    comparison = compare_evaluation_results(
        {
            "logistic_regression": res_a,
            "xgboost": res_b,
        }
    )

    assert isinstance(comparison, pd.DataFrame)
    assert len(comparison) == 2
    assert list(comparison["model"]) == ["logistic_regression", "xgboost"]
    assert "roc_auc" in comparison.columns
    assert "precision" in comparison.columns
    assert "f1" in comparison.columns

