import json
import hashlib
import sys

import joblib
import numpy as np
import pandas as pd
import pytest

from src.models.modeling_pipeline import FeatureSchema, GateError, build_xgboost_pipeline
from src.models import tv1_runner
from src.models.tv1_runner import (
    run_ml_lc_02, run_ml_lc_03, run_ml_lc_04, run_ml_lc_05,
    run_ml_lc_06, run_ml_lc_07,
)


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


def test_xgboost_gate_rejects_forbidden_feature_and_missing_dependency(monkeypatch) -> None:
    frame = pd.DataFrame({"dti": [1.0, 2.0], "target": [0, 1]})
    schema = FeatureSchema(approved_features=("dti",), excluded_features=("target",))
    with pytest.raises(GateError, match="chưa được ML-LC-01"):
        build_xgboost_pipeline(frame, schema, feature_columns=["dti", "target"])
    monkeypatch.setitem(sys.modules, "xgboost", None)
    with pytest.raises(GateError, match="optional dependency xgboost"):
        build_xgboost_pipeline(frame, schema, feature_columns=["dti"])


def test_ml_lc_05_candidate_uses_frozen_split_and_preserves_logistic(tmp_path) -> None:
    canonical_path, dictionary_path, manifest_path = _write_model_input(tmp_path)
    output_dir, reports_dir = tmp_path / "modeling", tmp_path / "reports"
    inputs = dict(canonical_path=canonical_path, dictionary_path=dictionary_path,
                  manifest_path=manifest_path, output_dir=output_dir, reports_dir=reports_dir)
    run_ml_lc_02(**inputs)
    baseline = run_ml_lc_03(**inputs)
    weighted = run_ml_lc_04(**inputs)
    old_models = {
        name: (output_dir / name).read_bytes()
        for name in ("logistic_baseline.joblib", "logistic_weighted.joblib")
    }
    result = run_ml_lc_05(**inputs)
    predictions = pd.read_parquet(output_dir / "ml_lc_05_xgboost_validation_predictions.parquet")
    frozen_validation = pd.read_parquet(output_dir / "validation_ids.parquet")
    assert result["status"] == "PASS"
    assert result["train_rows"] == baseline["train_rows"] == weighted["train_rows"]
    assert result["validation_rows"] == baseline["validation_rows"] == weighted["validation_rows"]
    assert result["actual_features"] == baseline["actual_baseline_features"]
    assert result["model_parameters"]["random_state"] == 42
    assert result["preprocessing_fit_partition"] == "train_only"
    assert result["early_stopping_used"] is False
    assert result["frozen_test_used_for_training"] is False
    assert result["frozen_test_used_for_evaluation"] is False
    assert result["frozen_test_used_for_selection"] is False
    assert result["frozen_test_evaluation_rows"] == 0
    assert result["reference_threshold"] == 0.5
    assert result["threshold_selected"] is False
    assert result["final_model_selected"] is False
    assert [row["metric"] for row in result["comparison"]] == [
        "roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy",
    ]
    assert predictions.columns.tolist() == ["loan_id", "target", "predicted_pd"]
    assert predictions["loan_id"].tolist() == frozen_validation["loan_id"].tolist()
    assert predictions["loan_id"].notna().all() and predictions["loan_id"].is_unique
    assert predictions["predicted_pd"].between(0, 1).all()
    assert np.isfinite(predictions["predicted_pd"]).all()
    assert sum(map(sum, result["validation_metrics"]["confusion_matrix"])) == len(predictions)
    loaded = joblib.load(output_dir / "xgboost_candidate.joblib")
    assert loaded.named_steps["model"].random_state == 42
    assert result["sparse_output"] is False
    assert (reports_dir / "tv1_stages" / "ml-lc-05.md").is_file()
    assert json.loads((reports_dir / "tv1_stages" / "state" / "ml-lc-05.json").read_text())["status"] == "PASS"
    assert json.loads((output_dir / "ml_lc_05_manifest.json").read_text())["final_model_selected"] is False
    assert all((output_dir / name).read_bytes() == old for name, old in old_models.items())
    first = predictions["predicted_pd"].to_numpy()
    rerun = run_ml_lc_05(**inputs)
    second = pd.read_parquet(output_dir / "ml_lc_05_xgboost_validation_predictions.parquet")["predicted_pd"].to_numpy()
    np.testing.assert_allclose(first, second, rtol=1e-7, atol=1e-9)
    assert rerun["validation_metrics"] == result["validation_metrics"]


def test_ml_lc_06_locks_one_candidate_without_reading_frozen_test(tmp_path, monkeypatch) -> None:
    canonical_path, dictionary_path, manifest_path = _write_model_input(tmp_path)
    output_dir, reports_dir = tmp_path / "modeling", tmp_path / "reports"
    inputs = dict(canonical_path=canonical_path, dictionary_path=dictionary_path,
                  manifest_path=manifest_path, output_dir=output_dir, reports_dir=reports_dir)
    run_ml_lc_02(**inputs)
    run_ml_lc_03(**inputs)
    run_ml_lc_04(**inputs)
    run_ml_lc_05(**inputs)
    previous_models = {name: (output_dir / name).read_bytes() for name in (
        "logistic_baseline.joblib", "logistic_weighted.joblib", "xgboost_candidate.joblib",
    )}
    real_read_parquet = pd.read_parquet

    def guard_test_access(path, *args, **kwargs):
        if str(path).endswith("test_ids.parquet"):
            raise AssertionError("ML-LC-06 không được đọc frozen test IDs/labels")
        return real_read_parquet(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", guard_test_access)
    result = run_ml_lc_06(output_dir=output_dir, reports_dir=reports_dir)
    assert result["status"] == "PASS"
    assert result["validation_alignment"] == "PASS"
    assert set(result["metrics"]) == {"logistic_baseline", "logistic_weighted", "xgboost_candidate"}
    assert result["selected_candidate"] in result["candidate_models"]
    assert len(result["models_rejected"]) == 2
    assert result["selected_model_artifact_path"] == str(output_dir / f"{result['selected_candidate']}.joblib")
    assert result["threshold_selected"] is False
    assert result["final_model_selected"] is False
    assert result["frozen_test_used_for_training"] is False
    assert result["frozen_test_used_for_evaluation"] is False
    assert result["frozen_test_used_for_selection"] is False
    assert result["next_stage"] == "ml-lc-07"
    assert (reports_dir / "tv1_stages" / "ml-lc-06.md").is_file()
    assert json.loads((reports_dir / "tv1_stages" / "state" / "ml-lc-06.json").read_text())["status"] == "PASS"
    assert json.loads((output_dir / "ml_lc_06_manifest.json").read_text())["selected_candidate"] == result["selected_candidate"]
    assert all((output_dir / name).read_bytes() == old for name, old in previous_models.items())
    rerun = run_ml_lc_06(output_dir=output_dir, reports_dir=reports_dir)
    assert rerun["selected_candidate"] == result["selected_candidate"]
    assert rerun["metrics"] == result["metrics"]


def test_ml_lc_07_selects_threshold_without_mutating_locked_artifacts(tmp_path, monkeypatch) -> None:
    canonical_path, dictionary_path, manifest_path = _write_model_input(tmp_path)
    output_dir, reports_dir = tmp_path / "modeling", tmp_path / "reports"
    inputs = dict(canonical_path=canonical_path, dictionary_path=dictionary_path,
                  manifest_path=manifest_path, output_dir=output_dir, reports_dir=reports_dir)
    run_ml_lc_02(**inputs)
    run_ml_lc_03(**inputs)
    run_ml_lc_04(**inputs)
    run_ml_lc_05(**inputs)
    run_ml_lc_06(output_dir=output_dir, reports_dir=reports_dir)
    ml06_path = output_dir / "ml_lc_06_manifest.json"
    ml06_payload = json.loads(ml06_path.read_text(encoding="utf-8"))
    ml06_payload.update({
        "selected_candidate": "xgboost_candidate",
        "selected_model_artifact_path": str(output_dir / "xgboost_candidate.joblib"),
        "selected_validation_predictions_path": str(output_dir / "ml_lc_05_xgboost_validation_predictions.parquet"),
        "threshold_selected": False,
        "final_model_selected": False,
    })
    ml06_path.write_text(json.dumps(ml06_payload), encoding="utf-8")
    monkeypatch.setattr(tv1_runner, "ML_LC_07_EXPECTED_VALIDATION_ROWS", 4)
    protected = [
        output_dir / "xgboost_candidate.joblib",
        output_dir / "ml_lc_05_xgboost_validation_predictions.parquet",
        output_dir / "ml_lc_06_manifest.json",
    ]
    hashes_before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    real_read_parquet = pd.read_parquet

    def guard_test_access(path, *args, **kwargs):
        if str(path).endswith("test_ids.parquet"):
            raise AssertionError("ML-LC-07 attempted to access frozen test")
        return real_read_parquet(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", guard_test_access)
    result = run_ml_lc_07(output_dir=output_dir, reports_dir=reports_dir)
    table_path = output_dir / "ml_lc_07_threshold_table.csv"
    table = pd.read_csv(table_path)
    assert result["status"] == "PASS"
    assert result["locked_candidate"] == "xgboost_candidate"
    assert result["selection_rule"] == "maximize_f1"
    assert 0 <= result["selected_threshold"] <= 1
    assert result["selected_metrics"]["f1"] == pytest.approx(result["maximum_f1"])
    assert int(table["selected"].sum()) == result["selected_threshold_rows"] == 1
    assert result["candidate_changed"] is False
    assert result["model_retrained"] is False
    assert result["final_model_selected"] is False
    assert result["frozen_test_used_for_threshold_selection"] is False
    assert result["frozen_test_used_for_evaluation"] is False
    assert result["frozen_test_threshold_selection_rows"] == result["frozen_test_evaluation_rows"] == 0
    assert result["source_model_sha256_before"] == result["source_model_sha256_after"]
    assert result["source_validation_predictions_sha256_before"] == result["source_validation_predictions_sha256_after"]
    assert result["ml_lc_06_manifest_sha256_before"] == result["ml_lc_06_manifest_sha256_after"]
    assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected} == hashes_before
    payload = json.loads((output_dir / "ml_lc_07_manifest.json").read_text())
    assert payload["threshold_selected"] is True
    assert payload["next_stage"] == "ml-lc-08"
    assert (reports_dir / "tv1_stages" / "ml-lc-07.md").is_file()
    assert json.loads((reports_dir / "tv1_stages" / "state" / "ml-lc-07.json").read_text())["status"] == "PASS"
    first_csv = table_path.read_bytes()
    rerun = run_ml_lc_07(output_dir=output_dir, reports_dir=reports_dir)
    assert rerun["selected_threshold"] == result["selected_threshold"]
    assert rerun["selected_metrics"] == result["selected_metrics"]
    assert table_path.read_bytes() == first_csv

    payload["locked_candidate"] = "logistic_baseline"
    (output_dir / "ml_lc_06_manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Exception, match="locked candidate/manifest"):
        run_ml_lc_07(output_dir=output_dir, reports_dir=reports_dir)
