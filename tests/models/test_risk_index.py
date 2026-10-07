"""Kiểm tra percentile theo validation của các model demo."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.models import risk_index


def test_percentile_risk_index_boundaries_and_monotonicity() -> None:
    """PD thấp/cao nằm đúng đầu thang và Risk Index tăng theo PD."""
    reference = np.array([0.10, 0.20, 0.30, 0.40])
    values = [
        risk_index.percentile_risk_index(probability, reference)
        for probability in (0.05, 0.10, 0.20, 0.25, 0.40, 0.50)
    ]
    assert values == [0.0, 25.0, 50.0, 50.0, 100.0, 100.0]
    assert all(left <= right for left, right in zip(values, values[1:]))
    assert risk_index.display_risk_index(63.4) == 63


def test_risk_index_uses_model_specific_validation_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cùng một PD có thể có percentile khác theo phân bố validation của model."""
    monkeypatch.setattr(
        risk_index,
        "get_reference_distribution",
        lambda: {
            "xgboost": np.array([0.10, 0.20, 0.30, 0.40]),
            "logistic": np.array([0.10, 0.15, 0.20, 0.25, 0.30]),
        },
    )
    assert risk_index.risk_index_for_model("xgboost", 0.25) == 50.0
    assert risk_index.risk_index_for_model("logistic", 0.25) == 80.0
    with pytest.raises(ValueError, match="Model không hợp lệ"):
        risk_index.risk_index_for_model("unknown", 0.25)


def test_six_input_personal_score_is_monotonic_and_model_specific(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PD như nhau cho percentile khác nhau khi hai model có reference riêng."""
    monkeypatch.setattr(
        risk_index, "get_six_input_reference_distributions",
        lambda: {
            "xgboost": np.array([0.10, 0.20, 0.30, 0.40]),
            "logistic": np.array([0.05, 0.10, 0.15, 0.20]),
        },
    )
    for model in ("xgboost", "logistic"):
        values = [
            risk_index.personal_risk_percentile_for_model(model, pd)
            for pd in (0.01, 0.10, 0.25, 0.50)
        ]
        assert all(0 <= value <= 100 for value in values)
        assert values == sorted(values)
    assert risk_index.personal_risk_percentile_for_model("xgboost", 0.25) == 50.0
    assert risk_index.personal_risk_percentile_for_model("logistic", 0.25) == 100.0
    with pytest.raises(ValueError, match="Model không hợp lệ"):
        risk_index.personal_risk_percentile_for_model("unknown", 0.25)


def test_six_input_reference_reads_validation_predictions_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    """Reference cần khớp validation IDs, hash và frozen-test policy của manifest."""
    ids_path = tmp_path / "validation_ids.parquet"
    pd.DataFrame({"loan_id": [11, 22, 33]}).to_parquet(ids_path, index=False)
    sources = {}
    for name, probabilities in (
        ("xgboost", [0.10, 0.20, 0.30]),
        ("logistic", [0.05, 0.10, 0.15]),
    ):
        model_path = tmp_path / f"{name}.joblib"
        manifest_path = tmp_path / f"{name}.json"
        predictions_path = tmp_path / f"{name}_validation.parquet"
        model_path.write_bytes(name.encode("ascii"))
        pd.DataFrame({
            "loan_id": [11, 22, 33], "predicted_pd": probabilities,
        }).to_parquet(predictions_path, index=False)
        manifest_path.write_text(json.dumps({
            "status": "PASS",
            "stage": f"{name}-6input-demo-validation-candidate",
            "features": list(risk_index.DEMO_6_FEATURES),
            "frozen_test_accessed": False,
            "split_artifact_sha256": {"validation": risk_index._sha256(ids_path)},
            "validation_rows": 3,
            "model_sha256": risk_index._sha256(model_path),
            "validation_prediction_sha256": risk_index._sha256(predictions_path),
        }), encoding="utf-8")
        sources[name] = model_path, manifest_path, predictions_path

    monkeypatch.setattr(risk_index, "MODELING_DIR", tmp_path)
    monkeypatch.setattr(risk_index, "SIX_INPUT_REFERENCE_FILES", sources)
    risk_index._load_six_input_references_cached.cache_clear()
    try:
        first = risk_index.get_six_input_reference_distributions()
        second = risk_index.get_six_input_reference_distributions()
        assert first is second
        assert list(first["xgboost"]) == [0.10, 0.20, 0.30]
        assert list(first["logistic"]) == [0.05, 0.10, 0.15]

        manifest_path = sources["logistic"][1]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["frozen_test_accessed"] = True
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(ValueError, match="Reference validation"):
            risk_index.get_six_input_reference_distributions()
    finally:
        risk_index._load_six_input_references_cached.cache_clear()
