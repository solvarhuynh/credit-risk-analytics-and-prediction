"""Kiểm thử full-data refit và handoff audit ML-LC-12/13."""

from __future__ import annotations

import hashlib
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from src.models.final_model import run_ml_lc_12, run_ml_lc_13_audit
from src.models.scoring import (
    ML_LC_10_LOCKED_THRESHOLD,
    assign_pd_risk_tier,
    probability_to_project_credit_score,
    probability_to_risk_score,
)
from src.models.modeling_pipeline import build_feature_schema, build_xgboost_pipeline


LOCKED_FEATURES = ["loan_amnt", "fico_avg", "purpose"]
PARAMS = {
    "n_estimators": 5, "max_depth": 2, "learning_rate": 0.08,
    "subsample": 0.8, "colsample_bytree": 0.9, "random_state": 42,
    "objective": "binary:logistic", "eval_metric": "logloss",
    "tree_method": "hist", "n_jobs": 4,
}


def _source_frame(rows: int = 60) -> pd.DataFrame:
    """Kanonical synthetic data có đủ ML-LC-10 context và 2 lớp target."""
    idx = np.arange(rows)
    return pd.DataFrame({
        "loan_id": [f"loan-{i}" for i in idx],
        "target": (idx % 3 == 0).astype(int),
        "loan_amnt": 1000.0 + 100 * idx,
        "fico_avg": 620.0 + idx % 90,
        "purpose": np.where(idx % 2, "car", "debt"),
        "dti": 5.0 + idx % 20,
        "annual_inc": 35000.0 + 500 * idx,
        "loan_to_income_ratio": 0.01 + idx / 1000,
        "home_ownership": np.where(idx % 2, "RENT", "OWN"),
        "term_months": np.where(idx % 2, 36, 60),
        "issue_year": 2015 + idx % 4,
    })


def _write_prerequisites(tmp_path):
    """Tạo lock/history files synthetic để test stage độc lập với production data."""
    output = tmp_path / "modeling"
    output.mkdir()
    reports = tmp_path / "reports"
    state_dir = reports / "tv1_stages/state"
    state_dir.mkdir(parents=True)
    dataset = _source_frame()
    canonical = tmp_path / "cleaned_dataset.parquet"
    dataset.to_parquet(canonical, index=False)
    dictionary = pd.DataFrame({
        "column_name": dataset.columns,
        "policy_class": [
            "IDENTIFIER", "TARGET_SOURCE", "APPLICATION_TIME", "CREDIT_SNAPSHOT",
            "APPLICATION_TIME", "CREDIT_SNAPSHOT", "APPLICATION_TIME", "APPLICATION_TIME",
            "APPLICATION_TIME", "APPLICATION_TIME", "APPLICATION_TIME",
        ],
        "model_eligible_default": [False, False, True, True, True, True, True, True, True, True, True],
    })
    dictionary_path = tmp_path / "data_dictionary.csv"
    dictionary.to_csv(dictionary_path, index=False)
    labels = dataset.target.value_counts().sort_index().to_dict()
    tv2_manifest_path = tmp_path / "cleaned_dataset_manifest.json"
    tv2_manifest_path.write_text(json.dumps({
        "dataset_id": "lending_club_2007_2018", "run_status": "PASS",
        "quality_status": "PASS", "leakage_gate": "PASS", "labeled_rows": len(dataset),
        "target_counts": {str(k): int(v) for k, v in labels.items()},
    }), encoding="utf-8")

    schema = build_feature_schema(dataset, dictionary)
    candidate = build_xgboost_pipeline(
        dataset, schema, feature_columns=LOCKED_FEATURES,
        random_state=PARAMS["random_state"], n_estimators=PARAMS["n_estimators"],
        max_depth=PARAMS["max_depth"], learning_rate=PARAMS["learning_rate"],
        subsample=PARAMS["subsample"], colsample_bytree=PARAMS["colsample_bytree"],
    )
    candidate.fit(dataset[LOCKED_FEATURES], dataset.target)
    candidate_path = output / "xgboost_candidate.joblib"
    joblib.dump(candidate, candidate_path)
    transformed = len(candidate.named_steps["preprocess"].get_feature_names_out())
    ml05 = {
        "stage": "ml-lc-05", "status": "PASS", "actual_features": LOCKED_FEATURES,
        "actual_feature_count": len(LOCKED_FEATURES), "approved_feature_count": len(schema.approved_features),
        "transformed_feature_count": transformed, "model_parameters": PARAMS,
        "excluded_safe_features": [],
    }
    (output / "ml_lc_05_manifest.json").write_text(json.dumps(ml05), encoding="utf-8")
    (state_dir / "ml-lc-05.json").write_text(json.dumps({"stage": "ml-lc-05", "status": "PASS"}), encoding="utf-8")
    records = {
        "ml_lc_06_manifest.json": {"stage": "ml-lc-06", "status": "PASS", "selected_candidate": "xgboost_candidate"},
        "ml_lc_07_manifest.json": {"stage": "ml-lc-07", "status": "PASS", "locked_candidate": "xgboost_candidate", "selected_threshold": ML_LC_10_LOCKED_THRESHOLD},
        "ml_lc_08_manifest.json": {"stage": "ml-lc-08", "status": "PASS", "selected_candidate": "xgboost_candidate", "selected_threshold": ML_LC_10_LOCKED_THRESHOLD, "test_evaluated": True, "test_metrics": {"roc_auc": 0.72}},
        "ml_lc_09_manifest.json": {"stage": "ml-lc-09", "status": "PASS", "model_retrained": False},
        "ml_lc_10_manifest.json": {"stage": "ml-lc-10", "status": "PASS", "model": "xgboost_candidate", "threshold_changed": False},
        "ml_lc_11_manifest.json": {"stage": "ml-lc-11", "status": "PASS"},
    }
    for filename, manifest in records.items():
        (output / filename).write_text(json.dumps(manifest), encoding="utf-8")
        stage = filename.removesuffix("_manifest.json").replace("_", "-")
        (state_dir / f"{stage}.json").write_text(json.dumps({"stage": stage, "status": "PASS"}), encoding="utf-8")
    candidate_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    ml07_path = output / "ml_lc_07_manifest.json"
    ml07 = records["ml_lc_07_manifest.json"]
    ml07.update({"selection_partition": "validation", "threshold_selected": True,
                 "source_model_sha256_after": candidate_hash})
    ml07_path.write_text(json.dumps(ml07), encoding="utf-8")
    records["ml_lc_08_manifest.json"].update({
        "frozen_test_used_for_model_selection": False,
        "protected_sha256_before": {
            "xgboost_candidate.joblib": candidate_hash,
            "ml_lc_07_manifest.json": hashlib.sha256(ml07_path.read_bytes()).hexdigest(),
        },
        "input_sha256": {"cleaned_dataset.parquet": hashlib.sha256(canonical.read_bytes()).hexdigest()},
    })
    records["ml_lc_09_manifest.json"]["model_sha256_after"] = candidate_hash
    records["ml_lc_10_manifest.json"].update({
        "decision_threshold": ML_LC_10_LOCKED_THRESHOLD,
        "protected_sha256_before": {"xgboost_candidate.joblib": candidate_hash},
    })
    for filename in ["ml_lc_08_manifest.json", "ml_lc_09_manifest.json", "ml_lc_10_manifest.json"]:
        (output / filename).write_text(json.dumps(records[filename]), encoding="utf-8")
    paths = {
        "canonical_path": canonical, "dictionary_path": dictionary_path,
        "tv2_manifest_path": tv2_manifest_path, "output_dir": output, "reports_dir": reports,
    }
    hashes = {
        name: hashlib.sha256((output / name).read_bytes()).hexdigest()
        for name in ["xgboost_candidate.joblib", *records]
    }
    return dataset, paths, hashes


def test_ml12_fits_all_labeled_rows_keeps_features_params_and_candidate(tmp_path) -> None:
    """Refit uses every labeled row and preserves the evaluated candidate/lock."""
    frame, paths, original_hashes = _write_prerequisites(tmp_path)
    manifest = run_ml_lc_12(
        **paths, expected_rows=len(frame), expected_approved_features=9,
        expected_actual_features=len(LOCKED_FEATURES),
    )
    assert manifest["full_refit_rows"] == len(frame)
    assert manifest["target_counts"] == {"0": int((frame.target == 0).sum()), "1": int((frame.target == 1).sum())}
    assert manifest["actual_features"] == LOCKED_FEATURES
    assert manifest["actual_feature_count"] == len(LOCKED_FEATURES)
    assert manifest["approved_feature_count"] == 9
    assert manifest["locked_hyperparameters"] == PARAMS
    assert manifest["preprocessing_fit_partition"] == "full_labeled_canonical"
    assert manifest["carried_forward_threshold"] == ML_LC_10_LOCKED_THRESHOLD
    assert manifest["threshold_retuned"] is False
    assert manifest["model_selection_changed"] is False
    assert manifest["hyperparameters_changed"] is False
    assert manifest["feature_policy_changed"] is False
    assert manifest["frozen_test_reused_for_selection"] is False
    assert manifest["frozen_test_metrics_recomputed"] is False
    assert manifest["unbiased_performance_source"] == "ml-lc-08 evaluated candidate"
    assert manifest["unbiased_performance_source_path"].endswith("ml_lc_08_manifest.json")
    assert manifest["protected_sha256_before"] == manifest["protected_sha256_after"]
    for name, digest in original_hashes.items():
        assert hashlib.sha256((paths["output_dir"] / name).read_bytes()).hexdigest() == digest

    refit = joblib.load(manifest["full_refit_model_artifact"])
    assert refit.named_steps["model"].get_params()["n_estimators"] == PARAMS["n_estimators"]
    assert list(refit.named_steps["normalize_missing"].feature_names_in_) == LOCKED_FEATURES
    scores = pd.read_parquet(manifest["full_refit_score_artifact"])
    assert len(scores) == len(frame) and scores.loan_id.is_unique and scores.loan_id.notna().all()
    assert np.isfinite(scores.predicted_pd).all() and scores.predicted_pd.between(0, 1).all()
    assert (scores.predicted_class == (scores.predicted_pd >= ML_LC_10_LOCKED_THRESHOLD).astype(int)).all()
    np.testing.assert_allclose(scores.risk_score, probability_to_risk_score(scores.predicted_pd))
    np.testing.assert_array_equal(scores.credit_score, probability_to_project_credit_score(scores.predicted_pd))
    np.testing.assert_array_equal(scores.risk_tier, assign_pd_risk_tier(scores.predicted_pd, decision_threshold=ML_LC_10_LOCKED_THRESHOLD))
    assert scores.model_version.eq("xgboost_full_refit_ml-lc-12").all()
    assert "unbiased_test_predictions" not in scores.columns


def test_ml13_reuses_existing_handoff_and_marks_visuals_ready_without_dashboard_claim(tmp_path) -> None:
    """ML-LC-13 audit reuses existing sources and does not create combined parquet."""
    _, paths, _ = _write_prerequisites(tmp_path)
    output, reports = paths["output_dir"], paths["reports_dir"]
    score_path = output / "ml_lc_12_full_refit_scores.parquet"
    pd.DataFrame({
        "loan_id": [1], "target": [0], "predicted_pd": [0.1],
        "decision_threshold": [ML_LC_10_LOCKED_THRESHOLD], "predicted_class": [0],
        "risk_score": [10.0], "credit_score": [900], "risk_tier": ["Tier A — Low"],
        "model_version": ["xgboost_full_refit_ml-lc-12"],
    }).to_parquet(score_path, index=False)
    ml12_path = output / "ml_lc_12_manifest.json"
    ml12_path.write_text(json.dumps({
        "status": "PASS", "full_refit_model_artifact": str(output / "xgboost_full_refit.joblib"),
        "full_refit_score_artifact": str(score_path), "actual_features": LOCKED_FEATURES,
        "approved_feature_count": 9, "canonical_dataset_path": str(paths["canonical_path"]),
    }), encoding="utf-8")
    joblib.dump(joblib.load(output / "xgboost_candidate.joblib"), output / "xgboost_full_refit.joblib")
    (reports / "tv1_stages/state/ml-lc-12.json").write_text(json.dumps({"stage": "ml-lc-12", "status": "PASS"}), encoding="utf-8")
    pd.DataFrame({
        "loan_id": [1], "predicted_pd": [0.1], "risk_score": [10.0],
        "credit_score": [900], "risk_tier": ["Tier A — Low"],
    }).to_parquet(output / "ml_lc_10_scored_frozen_test.parquet", index=False)
    pd.DataFrame({"feature": ["fico_avg"], "mean_abs_shap": [0.1], "xgboost_gain": [0.2]}).to_csv(output / "ml_lc_09_global_importance.csv", index=False)
    pd.DataFrame({"loan_id": [1], "feature": ["fico_avg"], "contribution": [0.1]}).to_csv(output / "ml_lc_09_local_explanations.csv", index=False)
    pd.DataFrame({"loan_id": [1], "feature": ["fico_avg"], "shap_value": [0.1]}).to_parquet(output / "ml_lc_09_shap_sample.parquet", index=False)
    pd.DataFrame({"loan_id": [1], "expected_loss": [10.0], "risk_tier": ["Tier A — Low"]}).to_parquet(output / "ml_lc_11_expected_loss.parquet", index=False)
    pd.DataFrame({"risk_tier": ["Tier A — Low"], "total_expected_loss": [10.0]}).to_csv(output / "ml_lc_11_risk_tier_el_summary.csv", index=False)
    handoff = run_ml_lc_13_audit(output_dir=output, reports_dir=reports)
    assert handoff["audit_outcome"].startswith("PASS — satisfied")
    assert handoff["handoff_artifact_created"] is False
    assert handoff["dashboard_readiness"] == {"V02": True, "V03": True, "V04": True, "V05": True, "V06": True}
    assert handoff["individual_prediction_contract_ready"] is True
    assert handoff["power_bi_dashboard_built_or_reviewed"] is False
    assert not (output / "ml_lc_13_dashboard_handoff.parquet").exists()
    assert (reports / "tv1_stages/ml-lc-13.md").is_file()
