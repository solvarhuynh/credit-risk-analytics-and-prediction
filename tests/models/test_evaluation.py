"""Tests cho src.models.evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.evaluation import (
    BinaryEvaluationResult,
    align_validation_predictions,
    build_validation_threshold_table,
    compare_evaluation_results,
    evaluate_binary_classifier,
    evaluate_validation_predictions,
    select_validation_threshold,
    select_validation_candidate,
    _select_threshold_row,
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


def test_candidate_validation_alignment_fails_closed() -> None:
    frozen = pd.DataFrame({"loan_id": ["a", "b", "c", "d"], "target": [0, 1, 0, 1]})
    original = pd.DataFrame({
        "loan_id": ["b", "a", "d", "c"], "target": [1, 0, 1, 0],
        "predicted_pd": [0.8, 0.1, 0.7, 0.2],
    })
    candidates = {name: original.copy() for name in
                  ("logistic_baseline", "logistic_weighted", "xgboost_candidate")}
    aligned = align_validation_predictions(candidates, frozen, expected_rows=4)
    assert all(frame["loan_id"].tolist() == frozen["loan_id"].tolist()
               for frame in aligned.values())

    wrong_id = original.copy()
    wrong_id.loc[0, "loan_id"] = "other"
    with pytest.raises(ValueError, match="loan_id"):
        align_validation_predictions({**candidates, "xgboost_candidate": wrong_id}, frozen, expected_rows=4)
    wrong_target = original.copy()
    wrong_target.loc[0, "target"] = 0
    with pytest.raises(ValueError, match="target"):
        align_validation_predictions({**candidates, "xgboost_candidate": wrong_target}, frozen, expected_rows=4)
    wrong_probability = original.copy()
    wrong_probability.loc[0, "predicted_pd"] = np.inf
    with pytest.raises(ValueError, match="predicted_pd"):
        align_validation_predictions({**candidates, "xgboost_candidate": wrong_probability}, frozen, expected_rows=4)
    wrong_probability.loc[0, "predicted_pd"] = 1.01
    with pytest.raises(ValueError, match="predicted_pd"):
        align_validation_predictions({**candidates, "xgboost_candidate": wrong_probability}, frozen, expected_rows=4)


def test_candidate_metrics_recomputed_from_probabilities() -> None:
    from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

    labels = np.array([0, 0, 1, 1])
    probabilities = np.array([0.1, 0.6, 0.4, 0.9])
    result = evaluate_validation_predictions(pd.DataFrame({
        "target": labels, "predicted_pd": probabilities,
    }))
    assert result["roc_auc"] == pytest.approx(roc_auc_score(labels, probabilities))
    assert result["pr_auc"] == pytest.approx(average_precision_score(labels, probabilities))
    assert result["log_loss"] == pytest.approx(log_loss(labels, probabilities))
    assert result["brier_score"] == pytest.approx(brier_score_loss(labels, probabilities))
    assert result["confusion_matrix"] == [[1, 1], [1, 1]]
    assert result["precision"] == result["recall"] == result["f1"] == result["accuracy"] == 0.5
    assert result["threshold"] == 0.5


def test_candidate_selection_rule_uses_ranking_and_practical_ties() -> None:
    rows = {
        "logistic_baseline": {"roc_auc": 0.7148, "pr_auc": 0.3853, "log_loss": 0.5, "brier_score": 0.16},
        "logistic_weighted": {"roc_auc": 0.7150, "pr_auc": 0.3840, "log_loss": 0.6, "brier_score": 0.19},
        "xgboost_candidate": {"roc_auc": 0.7245, "pr_auc": 0.3992, "log_loss": 0.48, "brier_score": 0.15},
    }
    assert select_validation_candidate(rows) == "xgboost_candidate"
    rows["xgboost_candidate"] = {"roc_auc": 0.70, "pr_auc": 0.35, "log_loss": 0.7, "brier_score": 0.25}
    assert select_validation_candidate(rows) == "logistic_baseline"
    rows["logistic_weighted"]["log_loss"] = 0.49
    assert select_validation_candidate(rows) == "logistic_weighted"
    rows["logistic_weighted"]["pr_auc"] = 0.40
    assert select_validation_candidate(rows) == "logistic_weighted"
    with pytest.raises(ValueError, match="đúng ba candidate"):
        select_validation_candidate({"logistic_baseline": rows["logistic_baseline"]})


def test_threshold_selector_finds_maximum_f1_from_exact_scores() -> None:
    result = select_validation_threshold([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8])
    assert result["selected_threshold"] == pytest.approx(0.35)
    assert result["selected_metrics"]["f1"] == pytest.approx(0.8)
    assert result["selected_metrics"]["f1"] == pytest.approx(result["max_f1"])
    assert result["reference_metrics"]["f1"] == pytest.approx(2 / 3)
    table = result["threshold_table"]
    assert int(table["selected"].sum()) == 1
    assert {0.1, 0.2, 0.3, 0.4, 0.5, 0.6}.issubset(set(table["threshold"]))


def test_threshold_tie_prefers_higher_recall() -> None:
    result = select_validation_threshold(
        [1, 1, 0, 0, 0], [0.9, 0.8, 0.8, 0.8, 0.1],
    )
    assert result["selected_threshold"] == pytest.approx(0.8)
    assert result["selected_metrics"]["recall"] == 1.0


def test_threshold_ties_apply_precision_then_higher_threshold() -> None:
    precision_tie = pd.DataFrame([
        {"threshold": 0.7, "f1": 0.8, "recall": 0.6, "precision": 0.95},
        {"threshold": 0.6, "f1": 0.8 - 5e-13, "recall": 0.6, "precision": 0.96},
    ])
    assert _select_threshold_row(precision_tie, tie_tolerance=1e-12)["threshold"] == 0.6
    threshold_tie = pd.DataFrame([
        {"threshold": 0.4, "f1": 0.75, "recall": 0.75, "precision": 0.75},
        {"threshold": 0.6, "f1": 0.75, "recall": 0.75, "precision": 0.75},
    ])
    assert _select_threshold_row(threshold_tie, tie_tolerance=1e-12)["threshold"] == 0.6


def test_threshold_selector_rejects_invalid_inputs_and_tolerance() -> None:
    with pytest.raises(ValueError, match="xác suất"):
        select_validation_threshold([0, 1], [0.2, 1.01])
    with pytest.raises(ValueError, match="y_true"):
        select_validation_threshold([0, 2], [0.2, 0.8])
    with pytest.raises(ValueError, match="tie_tolerance"):
        select_validation_threshold([0, 1], [0.2, 0.8], tie_tolerance=-1)

