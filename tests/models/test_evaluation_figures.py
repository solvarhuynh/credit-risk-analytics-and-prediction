from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import evaluation_figures as figures


def _inputs() -> figures.EvaluationInputs:
    n = 10_000
    y = np.tile([0, 1], n // 2)
    p = np.linspace(0.01, 0.99, n)
    frame = pd.DataFrame({"loan_id": np.arange(n), "target": y, "predicted_pd": p})
    return figures.EvaluationInputs(
        predictions={"xgboost_candidate": frame},
        validation_ids=frame[["loan_id", "target"]],
        manifests={},
        locked_threshold=0.5,
        threshold_manifest={"selected_metrics": {"confusion_matrix": [[0, 50], [1, 49]]}},
        positive_prevalence=0.5,
    )


def test_validate_probability_metrics_matches_saved_metrics() -> None:
    frame = pd.DataFrame({"target": [0, 0, 1, 1], "predicted_pd": [0.1, 0.4, 0.6, 0.9]})
    metrics = {"roc_auc": 1.0, "pr_auc": 1.0}
    figures._validate_probability_metrics("candidate", frame, {"validation_metrics": metrics},
                                          ("validation_metrics",))


def test_validate_probability_metrics_fails_on_manifest_mismatch() -> None:
    frame = pd.DataFrame({"target": [0, 0, 1, 1], "predicted_pd": [0.1, 0.4, 0.6, 0.9]})
    with pytest.raises(ValueError, match="không khớp manifest"):
        figures._validate_probability_metrics(
            "candidate", frame, {"metrics": {"roc_auc": 0.5, "pr_auc": 0.5}}, ("metrics",)
        )


def test_confusion_plot_uses_locked_threshold_and_has_stable_labels(tmp_path, monkeypatch) -> None:
    inputs = _inputs()
    monkeypatch.setattr(figures, "FIGURE_DIR", tmp_path)
    path = figures.create_confusion_figure(inputs)
    assert path.is_file() and path.stat().st_size > 0
    assert path.name == figures.OUTPUT_FILES["confusion"]


def test_calibration_quantile_bins_are_populated_and_bounded(tmp_path, monkeypatch) -> None:
    inputs = _inputs()
    monkeypatch.setattr(figures, "FIGURE_DIR", tmp_path)
    path, bins, metrics = figures.create_calibration_figure(inputs)
    assert path.is_file()
    assert len(bins) == 10
    assert bins["sample_count"].sum() == 10_000
    assert bins["sample_count"].min() >= 500
    assert bins["mean_predicted_pd"].between(0, 1).all()
    assert bins["observed_default_rate"].between(0, 1).all()
    assert set(metrics) == {"brier_score", "log_loss"}


def test_input_loader_checks_prediction_cohort_and_manifest(monkeypatch) -> None:
    ids = pd.DataFrame({"loan_id": [1, 2], "target": [0, 1]})
    prediction = pd.DataFrame({"loan_id": [1, 3], "target": [0, 1], "predicted_pd": [0.1, 0.9]})
    monkeypatch.setattr(figures, "EXPECTED_ROWS", 2)
    monkeypatch.setattr(figures, "MODEL_SOURCES", {
        "xgboost_candidate": {
            "label": "XGBoost Candidate", "prediction_file": "pred.parquet",
            "manifest_file": "model.json", "metric_path": ("validation_metrics",), "color": "#000000",
        },
    })
    monkeypatch.setattr(pd, "read_parquet", lambda path, columns: ids if str(path).endswith("validation_ids.parquet") else prediction)
    monkeypatch.setattr(figures, "_read_json", lambda path: {
        "status": "PASS", "validation_rows": 2, "validation_metrics": {"roc_auc": 1.0, "pr_auc": 1.0}
    } if str(path).endswith("model.json") else {
        "status": "PASS", "selection_partition": "validation", "locked_candidate": "xgboost_candidate",
        "selected_threshold": 0.5, "selected_metrics": {"confusion_matrix": [[1, 0], [0, 1]]},
    })
    monkeypatch.setattr(figures.Path, "is_file", lambda _self: True)
    with pytest.raises(ValueError, match="loan_id không khớp"):
        figures.load_validation_inputs()
