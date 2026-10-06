"""Synthetic checks; this module never opens the real frozen test."""

import hashlib
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from src.models.frozen_test import LOCKED_THRESHOLD, run_ml_lc_08
from src.models.modeling_pipeline import GateError


class NoFitProbabilityPipeline:
    """Serialized synthetic fitted-like pipeline whose fit must never run."""

    named_steps = {"preprocess": object(), "model": object()}
    feature_names_in_ = np.array(["dti"])

    def __init__(self, *, invalid=False):
        self.invalid = invalid

    def fit(self, *_args, **_kwargs):
        raise AssertionError("ML-LC-08 must not fit")

    def predict_proba(self, frame):
        p = frame["dti"].to_numpy() / 10
        if self.invalid:
            p[0] = np.nan
        return np.column_stack((1 - p, p))


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path, *, invalid=False):
    output = tmp_path / "modeling"
    reports = tmp_path / "reports"
    output.mkdir()
    canonical = tmp_path / "cleaned_dataset.parquet"
    dictionary = tmp_path / "data_dictionary.csv"
    tv2_path = tmp_path / "cleaned_dataset_manifest.json"
    pd.DataFrame({"loan_id": list(range(12)), "target": [0, 1] * 6,
                  "dti": [1., 4., 2., 9.] * 3}).to_parquet(canonical, index=False)
    pd.DataFrame({"column_name": ["loan_id", "target", "dti"],
                  "policy_class": ["IDENTIFIER", "TARGET_SOURCE", "CREDIT_SNAPSHOT"],
                  "model_eligible_default": [False, False, True]}).to_csv(dictionary, index=False)
    _json(tv2_path, {"dataset_id": "lending_club_2007_2018", "run_status": "PASS",
                     "quality_status": "PASS", "leakage_gate": "PASS", "labeled_rows": 12})
    for name, ids in (("train", [4, 5, 6, 7, 8, 9]), ("validation", [10, 11]), ("test", [0, 1, 2, 3])):
        pd.DataFrame({"loan_id": ids, "target": [i % 2 for i in ids],
                      "split": name}).to_parquet(output / f"{name}_ids.parquet", index=False)
    _json(output / "split_manifest.json", {
        "stage": "ml-lc-02", "stage_status": "PASS", "frozen": True,
        "dataset_id": "lending_club_2007_2018", "source_rows": 12, "union_rows": 12,
        "train_rows": 6, "validation_rows": 2, "test_rows": 4,
        "train_target_counts": {"0": 3, "1": 3},
        "validation_target_counts": {"0": 1, "1": 1},
        "test_target_counts": {"0": 2, "1": 2},
    })
    model = output / "xgboost_candidate.joblib"
    joblib.dump(NoFitProbabilityPipeline(invalid=invalid), model)
    m05 = output / "ml_lc_05_manifest.json"
    _json(m05, {"stage": "ml-lc-05", "status": "PASS", "dataset_id": "lending_club_2007_2018",
                "actual_features": ["dti"], "actual_feature_count": 1})
    m06 = output / "ml_lc_06_manifest.json"
    _json(m06, {"stage": "ml-lc-06", "status": "PASS", "selected_candidate": "xgboost_candidate",
                "threshold_selected": False, "frozen_test_used_for_selection": False,
                "frozen_test_used_for_evaluation": False, "selected_model_artifact_path": str(model),
                "validation_rows": 2, "frozen_test_rows": 4,
                "source_artifact_sha256": {model.name: _hash(model), m05.name: _hash(m05)},
                "metrics": {"xgboost_candidate": {"roc_auc": 0.8, "pr_auc": 0.7}}})
    m07 = output / "ml_lc_07_manifest.json"
    _json(m07, {"stage": "ml-lc-07", "status": "PASS", "locked_candidate": "xgboost_candidate",
                "selected_threshold": LOCKED_THRESHOLD, "selection_partition": "validation",
                "selection_rule": "maximize_f1", "threshold_selected": True,
                "candidate_changed": False, "model_retrained": False,
                "frozen_test_used_for_threshold_selection": False,
                "frozen_test_used_for_evaluation": False, "source_model_artifact": str(model),
                "source_model_sha256_after": _hash(model),
                "ml_lc_06_manifest_sha256_after": _hash(m06), "validation_rows": 2,
                "selected_metrics": {"precision": 0.6, "recall": 0.7, "f1": 0.65,
                                     "accuracy": 0.75, "confusion_matrix": [[1, 0], [0, 1]]}})
    _json(reports / "tv1_stages/state/ml-lc-06.json", {"stage": "ml-lc-06", "status": "PASS"})
    _json(reports / "tv1_stages/state/ml-lc-07.json", {
        "stage": "ml-lc-07", "status": "PASS", "selected_candidate": "xgboost_candidate",
        "selected_threshold": LOCKED_THRESHOLD})
    inputs = dict(canonical_path=canonical, dictionary_path=dictionary,
                  manifest_path=tv2_path, output_dir=output, reports_dir=reports,
                  expected_test_rows=4)
    return inputs


def test_synthetic_one_shot_evaluates_locked_config_and_blocks_rerun(tmp_path, monkeypatch):
    inputs = _fixture(tmp_path)
    protected = [inputs["output_dir"] / name for name in (
        "xgboost_candidate.joblib", "ml_lc_06_manifest.json", "ml_lc_07_manifest.json")]
    original_hashes = [_hash(path) for path in protected]
    monkeypatch.setattr("src.models.evaluation.select_validation_threshold",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("No threshold search")))
    result = run_ml_lc_08(**inputs)
    assert result["status"] == "PASS"
    assert result["selected_threshold"] == LOCKED_THRESHOLD
    assert result["test_metrics"]["confusion_matrix"] == [[2, 0], [0, 2]]
    assert result["test_metrics"]["roc_auc"] == 1
    assert result["test_metrics"]["pr_auc"] == 1
    assert result["test_metrics"]["log_loss"] > 0
    assert result["test_metrics"]["brier_score"] > 0
    assert result["test_metrics"]["precision"] == result["test_metrics"]["recall"] == 1
    assert result["model_retrained"] is result["candidate_changed"] is result["threshold_changed"] is False
    assert result["frozen_test_used_for_model_selection"] is False
    assert result["frozen_test_used_for_threshold_selection"] is False
    pred = pd.read_parquet(inputs["output_dir"] / "ml_lc_08_frozen_test_predictions.parquet")
    assert pred.columns.tolist() == ["loan_id", "target", "predicted_pd", "predicted_class"]
    assert pred["loan_id"].tolist() == [0, 1, 2, 3]
    assert pred["predicted_class"].tolist() == (pred["predicted_pd"] >= LOCKED_THRESHOLD).astype(int).tolist()
    assert [_hash(path) for path in protected] == original_hashes
    with pytest.raises(GateError, match="đã được đánh giá"):
        run_ml_lc_08(**inputs)


@pytest.mark.parametrize("path,key,value,match", [
    ("ml_lc_06_manifest.json", "status", "FAIL", "candidate lock"),
    ("ml_lc_07_manifest.json", "status", "FAIL", "threshold lock"),
    ("ml_lc_06_manifest.json", "selected_candidate", "logistic_baseline", "candidate lock"),
    ("ml_lc_07_manifest.json", "selected_threshold", 0.5, "threshold lock"),
])
def test_lock_changes_fail_before_test_access(tmp_path, monkeypatch, path, key, value, match):
    inputs = _fixture(tmp_path)
    target = inputs["output_dir"] / path
    data = json.loads(target.read_text())
    data[key] = value
    _json(target, data)
    real_read = pd.read_parquet

    def guarded(path_to_read, *args, **kwargs):
        if str(path_to_read).endswith("test_ids.parquet"):
            raise AssertionError("opened real/synthetic test before lock gate")
        return real_read(path_to_read, *args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", guarded)
    with pytest.raises(GateError, match=match):
        run_ml_lc_08(**inputs)


@pytest.mark.parametrize("mutation,match", [
    ("duplicate", "test_ids"), ("null", "test_ids"),
    ("train_overlap", "overlap"), ("validation_overlap", "overlap"),
    ("target_mismatch", "Canonical target mismatch"),
])
def test_population_fail_closed(tmp_path, mutation, match):
    inputs = _fixture(tmp_path)
    output = inputs["output_dir"]
    test_path = output / "test_ids.parquet"
    test = pd.read_parquet(test_path)
    if mutation == "duplicate":
        test.loc[1, "loan_id"] = test.loc[0, "loan_id"]
    elif mutation == "null":
        test.loc[1, "loan_id"] = None
    elif mutation == "train_overlap":
        test.loc[0, "loan_id"] = 4
    elif mutation == "validation_overlap":
        test.loc[0, "loan_id"] = 10
    else:
        canonical = pd.read_parquet(inputs["canonical_path"])
        canonical.loc[0, "target"] = 1
        canonical.to_parquet(inputs["canonical_path"], index=False)
    if mutation in {"train_overlap", "validation_overlap"}:
        test.loc[0, "target"] = 0
    test.to_parquet(test_path, index=False)
    with pytest.raises(GateError, match=match):
        run_ml_lc_08(**inputs)
    assert not (output / "ml_lc_08_frozen_test_predictions.parquet").exists()


def test_invalid_probabilities_leave_one_shot_lock(tmp_path):
    inputs = _fixture(tmp_path, invalid=True)
    with pytest.raises(GateError, match="probabilities"):
        run_ml_lc_08(**inputs)
    assert (inputs["output_dir"] / "ml_lc_08_one_shot.lock").exists()
    with pytest.raises(GateError, match="output/lock"):
        run_ml_lc_08(**inputs)
