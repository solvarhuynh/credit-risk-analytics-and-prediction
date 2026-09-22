"""Focused tests for the gated TV1 modeling workflow helpers."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import src.models.modeling_pipeline as modeling_pipeline_module
from src.models.modeling_pipeline import (
    CandidateCVResult,
    CandidateDefinition,
    DatasetFingerprint,
    FeatureSchema,
    FoldMetric,
    GateError,
    RunConfig,
    build_candidate_pipeline,
    build_feature_schema,
    choose_threshold_from_oof,
    create_scored_dataset,
    run_candidate_cv,
    sha256_file,
    select_candidate,
    validate_production_artifacts,
)


@pytest.fixture
def modeling_frame() -> pd.DataFrame:
    """Small labeled frame with both numeric/categorical features and an EAD proxy."""
    size = 40
    target = np.asarray(([0, 1] * (size // 2)), dtype=int)
    return pd.DataFrame(
        {
            "SK_ID_CURR": np.arange(100000, 100000 + size),
            "TARGET": target,
            "AMT_CREDIT": np.linspace(10_000.0, 100_000.0, size),
            "NUMERIC_SIGNAL": target + np.linspace(0.0, 0.2, size),
            "CATEGORY": np.where(target == 1, "HIGH", "LOW"),
        }
    )


@pytest.fixture
def modeling_dictionary(modeling_frame: pd.DataFrame) -> pd.DataFrame:
    """Dictionary roles sufficient to define a safe feature boundary."""
    roles = ["identifier", "target"] + ["feature"] * (len(modeling_frame.columns) - 2)
    return pd.DataFrame({"column_name": modeling_frame.columns, "role": roles})


def test_feature_schema_excludes_outputs_and_assigns_dtypes(
    modeling_frame: pd.DataFrame,
    modeling_dictionary: pd.DataFrame,
) -> None:
    """TARGET/ID/output columns remain excluded even when absent from the snapshot."""
    schema = build_feature_schema(modeling_frame, modeling_dictionary)

    assert schema.numeric_features == ("AMT_CREDIT", "NUMERIC_SIGNAL")
    assert schema.categorical_features == ("CATEGORY",)
    assert "TARGET" in schema.excluded_features
    assert "SK_ID_CURR" in schema.excluded_features
    assert "PREDICTED_PD" in schema.excluded_features


def test_logistic_cv_is_oof_and_scored_output_is_contract_shaped(
    modeling_frame: pd.DataFrame,
    modeling_dictionary: pd.DataFrame,
) -> None:
    """Candidate preprocessing stays in CV and production scores have required fields."""
    schema = build_feature_schema(modeling_frame, modeling_dictionary)
    definition = CandidateDefinition("logistic_baseline", "logistic", {"class_weight": None})
    config = RunConfig(cv_splits=2, n_jobs=1)
    X = modeling_frame.loc[:, schema.all_features]
    y = modeling_frame["TARGET"]
    result = run_candidate_cv(definition, X, y, schema, config=config)

    assert len(result.fold_metrics) == 2
    assert np.isfinite(result.oof_probabilities).all()
    assert np.all((result.oof_probabilities >= 0) & (result.oof_probabilities <= 1))

    threshold, table = choose_threshold_from_oof(y, result.oof_probabilities, config=config)
    pipeline = build_candidate_pipeline(
        definition,
        schema,
        available_columns=X.columns,
        config=config,
    )
    pipeline.fit(X, y)
    scored = create_scored_dataset(
        modeling_frame,
        schema,
        pipeline,
        threshold=threshold,
        config=config,
        model_version="test-version",
    )

    assert not table.empty
    assert set(scored.columns) == {
        "SK_ID_CURR",
        "TARGET",
        "PREDICTED_PD",
        "DECISION_THRESHOLD",
        "RECOMMENDATION",
        "MODEL_VERSION",
        "CREDIT_SCORE",
        "RISK_TIER",
        "EXPECTED_LOSS",
    }
    assert scored["PREDICTED_PD"].between(0, 1).all()
    assert (scored["EXPECTED_LOSS"] >= 0).all()
    assert set(scored["RECOMMENDATION"]).issubset({"APPROVE", "REJECT"})


def test_selection_requests_human_decision_for_cross_family_metric_tie() -> None:
    """Near-identical cross-family evidence is not silently resolved by the workflow."""
    metric = FoldMetric(1, 0.70, 0.20, 0.20, 0.20, 0.20)
    logistic = CandidateCVResult(
        CandidateDefinition("logistic", "logistic", {}),
        [metric],
        np.asarray([0.1, 0.9]),
    )
    xgboost = CandidateCVResult(
        CandidateDefinition("xgboost", "xgboost", {}),
        [FoldMetric(1, 0.7001, 0.2001, 0.2, 0.2, 0.2)],
        np.asarray([0.1, 0.9]),
    )

    decision = select_candidate([logistic, xgboost])

    assert decision.needs_human_decision
    assert decision.selected_name == "xgboost"


def test_production_validation_rejects_non_deterministic_inference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    modeling_frame: pd.DataFrame,
) -> None:
    """Gate Q must fail rather than merely report a non-deterministic artifact."""

    class NonDeterministicPipeline:
        def __init__(self) -> None:
            self.calls = 0

        def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
            self.calls += 1
            probability = np.full(len(frame), 0.10 + (self.calls * 0.01))
            return np.column_stack((1.0 - probability, probability))

    schema = FeatureSchema(
        numeric_features=("AMT_CREDIT",),
        categorical_features=(),
        excluded_features=("TARGET", "SK_ID_CURR"),
        review_only_features=(),
    )
    artifact_path = tmp_path / "models" / "full_inference_pipeline.joblib"
    scored_path = tmp_path / "data" / "processed" / "scored_dataset.parquet"
    artifact_path.parent.mkdir(parents=True)
    scored_path.parent.mkdir(parents=True)
    artifact_path.touch()
    scored_path.touch()
    record_path = tmp_path / "reports" / "frozen_test_evaluation_record.json"
    record_path.parent.mkdir(parents=True)
    scored = pd.DataFrame(
        {
            "SK_ID_CURR": modeling_frame["SK_ID_CURR"],
            "TARGET": modeling_frame["TARGET"],
            "PREDICTED_PD": np.full(len(modeling_frame), 0.10),
            "DECISION_THRESHOLD": np.full(len(modeling_frame), 0.16),
            "RECOMMENDATION": "APPROVE",
            "MODEL_VERSION": "test-version",
            "CREDIT_SCORE": np.full(len(modeling_frame), 700.0),
            "RISK_TIER": "LOW_RISK",
            "EXPECTED_LOSS": np.full(len(modeling_frame), 100.0),
        }
    )
    monkeypatch.setattr(
        modeling_pipeline_module,
        "load_canonical_input",
        lambda root: (
            modeling_frame,
            pd.DataFrame(),
            {},
            DatasetFingerprint("dataset-hash", "dataset-hash", len(modeling_frame), 5, {}, None, None),
        ),
    )
    monkeypatch.setattr(modeling_pipeline_module.joblib, "load", lambda path: NonDeterministicPipeline())
    monkeypatch.setattr(modeling_pipeline_module.pd, "read_parquet", lambda path: scored)
    record_path.write_text(
        json.dumps(
            {
                "dataset_sha256": "dataset-hash",
                "threshold": 0.16,
                "production_artifacts": {
                    "model_artifact_sha256": sha256_file(artifact_path),
                    "scored_dataset_sha256": sha256_file(scored_path),
                    "model_version": "test-version",
                    "scored_row_count": len(scored),
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(GateError, match="deterministic"):
        validate_production_artifacts(tmp_path, schema=schema)


def test_production_validation_rejects_stale_scored_probabilities(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    modeling_frame: pd.DataFrame,
) -> None:
    """Gate Q rejects a scored dataset that does not come from the loaded artifact."""

    class DeterministicPipeline:
        def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
            probability = np.full(len(frame), 0.10)
            return np.column_stack((1.0 - probability, probability))

    schema = FeatureSchema(
        numeric_features=("AMT_CREDIT",),
        categorical_features=(),
        excluded_features=("TARGET", "SK_ID_CURR"),
        review_only_features=(),
    )
    artifact_path = tmp_path / "models" / "full_inference_pipeline.joblib"
    scored_path = tmp_path / "data" / "processed" / "scored_dataset.parquet"
    record_path = tmp_path / "reports" / "frozen_test_evaluation_record.json"
    artifact_path.parent.mkdir(parents=True)
    scored_path.parent.mkdir(parents=True)
    record_path.parent.mkdir(parents=True)
    artifact_path.touch()
    scored_path.touch()
    scored = pd.DataFrame(
        {
            "SK_ID_CURR": modeling_frame["SK_ID_CURR"],
            "TARGET": modeling_frame["TARGET"],
            "PREDICTED_PD": np.full(len(modeling_frame), 0.20),
            "DECISION_THRESHOLD": np.full(len(modeling_frame), 0.16),
            "RECOMMENDATION": "REJECT",
            "MODEL_VERSION": "test-version",
            "CREDIT_SCORE": np.full(len(modeling_frame), 700.0),
            "RISK_TIER": "LOW_RISK",
            "EXPECTED_LOSS": np.full(len(modeling_frame), 100.0),
        }
    )
    record_path.write_text(
        json.dumps(
            {
                "dataset_sha256": "dataset-hash",
                "threshold": 0.16,
                "production_artifacts": {
                    "model_artifact_sha256": sha256_file(artifact_path),
                    "scored_dataset_sha256": sha256_file(scored_path),
                    "model_version": "test-version",
                    "scored_row_count": len(scored),
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        modeling_pipeline_module,
        "load_canonical_input",
        lambda root: (
            modeling_frame,
            pd.DataFrame(),
            {},
            DatasetFingerprint("dataset-hash", "dataset-hash", len(modeling_frame), 5, {}, None, None),
        ),
    )
    monkeypatch.setattr(modeling_pipeline_module.joblib, "load", lambda path: DeterministicPipeline())
    monkeypatch.setattr(modeling_pipeline_module.pd, "read_parquet", lambda path: scored)

    with pytest.raises(GateError, match="PD không khớp"):
        validate_production_artifacts(tmp_path, schema=schema)
