import json

import joblib
import numpy as np
import pandas as pd

from src.models.tv1_runner import run_ml_lc_02, run_ml_lc_03, run_ml_lc_04


def _write_model_input(tmp_path):
    canonical = pd.DataFrame({
        "loan_id": [f"loan-{index}" for index in range(20)],
        "target": [0] * 15 + [1] * 5,
        "dti": [float(index) for index in range(20)],
    })
    canonical_path = tmp_path / "cleaned_dataset.parquet"
    canonical.to_parquet(canonical_path, index=False)
    dictionary = pd.DataFrame({
        "column_name": canonical.columns,
        "policy_class": ["IDENTIFIER", "TARGET_SOURCE", "CREDIT_SNAPSHOT"],
        "model_eligible_default": [False, False, True],
    })
    dictionary_path = tmp_path / "data_dictionary.csv"
    dictionary.to_csv(dictionary_path, index=False)
    manifest_path = tmp_path / "cleaned_dataset_manifest.json"
    manifest_path.write_text(json.dumps({
        "dataset_id": "lending_club_2007_2018",
        "run_status": "PASS",
        "quality_status": "PASS",
        "leakage_gate": "PASS",
        "labeled_rows": len(canonical),
    }), encoding="utf-8")
    return canonical_path, dictionary_path, manifest_path


def test_ml_lc_02_runner_writes_and_reuses_frozen_split(tmp_path) -> None:
    canonical_path, dictionary_path, manifest_path = _write_model_input(tmp_path)
    output_dir = tmp_path / "modeling"
    reports_dir = tmp_path / "reports"

    first = run_ml_lc_02(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )
    second = run_ml_lc_02(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )

    assert first["reused_existing_artifacts"] is False
    assert second["reused_existing_artifacts"] is True
    assert first["preprocessing_fitted"] is False
    assert first["model_trained"] is False
    assert (reports_dir / "tv1_stages" / "ml-lc-02.md").is_file()
    marker = json.loads((reports_dir / "tv1_stages" / "state" / "ml-lc-02.json").read_text())
    assert marker["status"] == "PASS"


def test_ml_lc_03_runner_trains_validation_only_baseline(tmp_path) -> None:
    rows = 100
    canonical = pd.DataFrame({
        "loan_id": [f"loan-{index}" for index in range(rows)],
        "target": [0] * 75 + [1] * 25,
        "dti": [float(index % 30) for index in range(rows)],
        "purpose": ["car", "medical", "home", "card"] * 25,
        "issue_d": pd.to_datetime(["2018-01-01"] * rows),
    })
    canonical_path = tmp_path / "cleaned_dataset.parquet"
    canonical.to_parquet(canonical_path, index=False)
    dictionary = pd.DataFrame({
        "column_name": canonical.columns,
        "policy_class": ["IDENTIFIER", "TARGET_SOURCE", "CREDIT_SNAPSHOT", "APPLICATION_TIME", "APPLICATION_TIME"],
        "model_eligible_default": [False, False, True, True, True],
    })
    dictionary_path = tmp_path / "data_dictionary.csv"
    dictionary.to_csv(dictionary_path, index=False)
    manifest_path = tmp_path / "cleaned_dataset_manifest.json"
    manifest_path.write_text(json.dumps({
        "dataset_id": "lending_club_2007_2018",
        "run_status": "PASS",
        "quality_status": "PASS",
        "leakage_gate": "PASS",
        "labeled_rows": rows,
    }), encoding="utf-8")
    output_dir = tmp_path / "modeling"
    reports_dir = tmp_path / "reports"

    run_ml_lc_02(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )
    result = run_ml_lc_03(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )

    assert result["status"] == "PASS"
    assert result["class_weight"] is None
    assert result["frozen_test_used_for_training"] is False
    assert result["frozen_test_used_for_evaluation"] is False
    assert result["threshold_selected"] is False
    assert result["imbalance_treatment"] == "none"
    assert result["train_rows"] == 60
    assert result["validation_rows"] == 20
    assert result["frozen_test_rows"] == 20
    assert result["excluded_safe_features"] == ["issue_d"]
    assert result["validation_metrics"]["roc_auc"] >= 0
    assert result["transformed_feature_count"] >= result["actual_baseline_feature_count"]
    assert joblib.load(output_dir / "logistic_baseline.joblib").named_steps["model"].class_weight is None
    predictions = pd.read_parquet(output_dir / "ml_lc_03_validation_predictions.parquet")
    assert len(predictions) == result["validation_rows"]
    assert predictions["loan_id"].is_unique
    assert predictions["predicted_pd"].between(0, 1).all()
    assert not (output_dir / "test_predictions.parquet").exists()
    assert not list(output_dir.glob("*.partial*"))

    rerun = run_ml_lc_03(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )
    rerun_predictions = pd.read_parquet(output_dir / "ml_lc_03_validation_predictions.parquet")
    np.testing.assert_allclose(
        predictions["predicted_pd"].to_numpy(),
        rerun_predictions["predicted_pd"].to_numpy(),
        rtol=1e-10,
        atol=1e-12,
    )
    assert rerun["validation_metrics"] == result["validation_metrics"]


def test_ml_lc_04_runner_compares_weighted_model_without_mutating_baseline(tmp_path) -> None:
    rows = 100
    canonical = pd.DataFrame({
        "loan_id": [f"loan-{index}" for index in range(rows)],
        "target": [0] * 75 + [1] * 25,
        "dti": [float(index % 30) for index in range(rows)],
        "purpose": ["car", "medical", "home", "card"] * 25,
        "issue_d": pd.to_datetime(["2018-01-01"] * rows),
    })
    canonical_path = tmp_path / "cleaned_dataset.parquet"
    canonical.to_parquet(canonical_path, index=False)
    dictionary = pd.DataFrame({
        "column_name": canonical.columns,
        "policy_class": ["IDENTIFIER", "TARGET_SOURCE", "CREDIT_SNAPSHOT", "APPLICATION_TIME", "APPLICATION_TIME"],
        "model_eligible_default": [False, False, True, True, True],
    })
    dictionary_path = tmp_path / "data_dictionary.csv"
    dictionary.to_csv(dictionary_path, index=False)
    manifest_path = tmp_path / "cleaned_dataset_manifest.json"
    manifest_path.write_text(json.dumps({
        "dataset_id": "lending_club_2007_2018",
        "run_status": "PASS",
        "quality_status": "PASS",
        "leakage_gate": "PASS",
        "labeled_rows": rows,
    }), encoding="utf-8")
    output_dir = tmp_path / "modeling"
    reports_dir = tmp_path / "reports"

    run_ml_lc_02(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )
    baseline = run_ml_lc_03(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )
    baseline_artifact = output_dir / "logistic_baseline.joblib"
    baseline_bytes_before = baseline_artifact.read_bytes()
    result = run_ml_lc_04(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )

    assert result["status"] == "PASS"
    assert result["baseline_class_weight"] is None
    assert result["weighted_class_weight"] == "balanced"
    assert result["actual_feature_count"] == baseline["actual_baseline_feature_count"]
    assert result["actual_baseline_features"] == baseline["actual_baseline_features"]
    assert result["transformed_feature_count"] == baseline["transformed_feature_count"]
    assert result["preprocessing_fit_partition"] == "train_only"
    assert result["frozen_test_used_for_training"] is False
    assert result["frozen_test_used_for_evaluation"] is False
    assert result["frozen_test_used_for_selection"] is False
    assert result["frozen_test_evaluation_rows"] == 0
    assert result["reference_threshold"] == 0.5
    assert result["threshold_selected"] is False
    assert result["resampling"] == "none"
    assert baseline_artifact.read_bytes() == baseline_bytes_before

    weighted_artifact = output_dir / "logistic_weighted.joblib"
    weighted_pipeline = joblib.load(weighted_artifact)
    assert weighted_pipeline.named_steps["model"].class_weight == "balanced"
    assert set(result["metric_comparison"][0]) == {"metric", "baseline", "weighted", "difference"}
    assert [row["metric"] for row in result["metric_comparison"]] == [
        "roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy",
    ]
    assert sum(sum(row) for row in result["weighted_metrics"]["confusion_matrix"]) == result["validation_rows"]
    assert sum(sum(row) for row in result["baseline_metrics"]["confusion_matrix"]) == result["validation_rows"]

    predictions = pd.read_parquet(output_dir / "ml_lc_04_weighted_validation_predictions.parquet")
    assert predictions.columns.tolist() == ["loan_id", "target", "predicted_pd"]
    assert len(predictions) == result["validation_rows"]
    assert predictions["loan_id"].is_unique
    assert predictions["predicted_pd"].between(0, 1).all()
    assert not (output_dir / "test_predictions.parquet").exists()
    assert not list(output_dir.glob("*.partial*"))

    rerun = run_ml_lc_04(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
    )
    rerun_predictions = pd.read_parquet(output_dir / "ml_lc_04_weighted_validation_predictions.parquet")
    np.testing.assert_allclose(
        predictions["predicted_pd"].to_numpy(),
        rerun_predictions["predicted_pd"].to_numpy(),
        rtol=1e-10,
        atol=1e-12,
    )
    assert rerun["weighted_metrics"] == result["weighted_metrics"]
    assert rerun["baseline_artifact_preserved"] is True
    assert baseline_artifact.read_bytes() == baseline_bytes_before
