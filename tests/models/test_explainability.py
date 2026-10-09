"""Synthetic-only tests for validation explainability; frozen test is never read."""

import hashlib
import json
import math
import sys
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest

from src.models import explainability
from src.models.explainability import (
    aggregate_shap_by_original,
    deterministic_validation_sample,
    native_gain_tables,
    run_ml_lc_09,
    select_local_examples,
    transformed_feature_mapping,
)
from src.models.modeling_pipeline import GateError


class FakeBooster:
    def num_features(self):
        return 3

    def get_score(self, importance_type):
        return {"f0": 4.0, "f1": 2.0, "f2": 1.0} if importance_type == "gain" else {"f0": 2.0, "f1": 1.0, "f2": 1.0}


class FakePreprocessor:
    def get_feature_names_out(self):
        return np.array(["numeric__dti", "categorical__purpose_A", "categorical__purpose_B"])

    def transform(self, frame):
        return np.column_stack([
            frame["dti"].to_numpy(dtype=float),
            frame["purpose"].eq("A").to_numpy(dtype=float),
            frame["purpose"].eq("B").to_numpy(dtype=float),
        ])


class FakeEstimator:
    def get_booster(self):
        return FakeBooster()

    def predict(self, matrix, output_margin=False):
        margin = matrix[:, 0] * 0.3 + matrix[:, 1] * 0.2 - matrix[:, 2] * 0.2
        return margin if output_margin else (margin >= 0.22).astype(int)


class FakePipeline:
    def __init__(self):
        self.named_steps = {"normalize_missing": None, "preprocess": FakePreprocessor(), "model": FakeEstimator()}

    def predict_proba(self, frame):
        margin = self.named_steps["model"].predict(self.named_steps["preprocess"].transform(frame), output_margin=True)
        positive = 1 / (1 + np.exp(-margin))
        return np.column_stack([1 - positive, positive])

    def fit(self, *_args, **_kwargs):
        raise AssertionError("Explainability cannot retrain the model")


class FakeExplainer:
    expected_value = 0.0

    def __init__(self, *_args, **_kwargs):
        pass

    def shap_values(self, matrix, check_additivity=False):
        return np.column_stack([matrix[:, 0] * 0.3, matrix[:, 1] * 0.2, matrix[:, 2] * -0.2])


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _stage_fixture(tmp_path):
    output = tmp_path / "modeling"
    reports = tmp_path / "reports"
    output.mkdir()
    ids = np.arange(60)
    target = np.tile([0, 1], 30)
    dti = np.linspace(0.01, 1.0, 60)
    purpose = np.where(ids % 3, "A", "B")
    canonical = pd.DataFrame({"loan_id": ids, "target": target, "dti": dti, "purpose": purpose})
    canonical_path = tmp_path / "canonical.parquet"
    canonical.to_parquet(canonical_path, index=False)
    validation_ids = pd.DataFrame({"loan_id": ids, "target": target, "split": "validation"})
    validation_ids.to_parquet(output / "validation_ids.parquet", index=False)
    pd.DataFrame({"loan_id": [999], "target": [0], "split": ["test"]}).to_parquet(output / "test_ids.parquet", index=False)
    pd.DataFrame({"column_name": ["dti", "purpose"],
                  "policy_class": ["CREDIT_SNAPSHOT", "APPLICATION_TIME"],
                  "model_eligible_default": [True, True]}).to_csv(tmp_path / "dictionary.csv", index=False)
    model_path = output / "xgboost_candidate.joblib"
    joblib.dump(FakePipeline(), model_path)
    model_hash = _hash(model_path)
    pd_value = FakePipeline().predict_proba(canonical[["dti", "purpose"]])[:, 1]
    pd.DataFrame({"loan_id": ids, "target": target, "predicted_pd": pd_value}).to_parquet(
        output / "ml_lc_05_xgboost_validation_predictions.parquet", index=False,
    )
    _write_json(output / "ml_lc_05_manifest.json", {
        "stage": "ml-lc-05", "status": "PASS", "validation_rows": 60,
        "actual_features": ["dti", "purpose"], "actual_feature_count": 2,
        "transformed_feature_count": 3,
    })
    _write_json(output / "ml_lc_06_manifest.json", {"stage": "ml-lc-06", "status": "PASS",
        "selected_candidate": "xgboost_candidate", "validation_rows": 60})
    _write_json(output / "ml_lc_07_manifest.json", {"stage": "ml-lc-07", "status": "PASS",
        "locked_candidate": "xgboost_candidate", "selected_threshold": explainability.LOCKED_THRESHOLD,
        "validation_rows": 60})
    _write_json(output / "ml_lc_08_manifest.json", {"stage": "ml-lc-08", "status": "PASS",
        "selected_candidate": "xgboost_candidate", "selected_threshold": explainability.LOCKED_THRESHOLD,
        "frozen_test_used_for_model_selection": False,
        "frozen_test_used_for_threshold_selection": False, "test_evaluated": True,
        "protected_sha256_after": {"xgboost_candidate.joblib": model_hash}})
    (output / "ml_lc_08_one_shot.lock").write_text("synthetic", encoding="utf-8")
    return dict(canonical_path=canonical_path, dictionary_path=tmp_path / "dictionary.csv",
                output_dir=output, reports_dir=reports, sample_size=30, random_state=42,
                top_n=2), model_hash


def _install_fake_shap(monkeypatch):
    def summary_plot(*_args, **_kwargs):
        import matplotlib.pyplot as plt
        plt.figure()
        plt.plot([0, 1], [0, 1])
    monkeypatch.setitem(sys.modules, "shap", SimpleNamespace(TreeExplainer=FakeExplainer,
                                                               summary_plot=summary_plot))


def test_transformed_names_and_original_aggregation():
    transformed = ["numeric__dti", "categorical__home_ownership_RENT",
                  "categorical__home_ownership_RENT_SPECIAL", "categorical__purpose_A_B"]
    mapped = transformed_feature_mapping(transformed, ["dti", "home_ownership", "purpose"])
    assert mapped == ["dti", "home_ownership", "home_ownership", "purpose"]
    assert not any(name in {"f0", "f1"} for name in mapped)
    aggregate = aggregate_shap_by_original(
        np.array([[1., 2., -1., 3.], [-1., -2., 1., -3.]]), transformed, mapped,
    )
    assert aggregate["home_ownership"].tolist() == [1., -1.]
    assert aggregate["purpose"].tolist() == [3., -3.]
    with pytest.raises(GateError, match="dimensions"):
        aggregate_shap_by_original(np.ones((2, 3)), transformed, mapped)
    with pytest.raises(GateError, match="no source"):
        transformed_feature_mapping(["categorical__unknown_X"], ["dti"])


def test_native_gain_aggregates_original_features_without_anonymous_labels():
    transformed = ["numeric__dti", "categorical__purpose_A", "categorical__purpose_B"]
    mapping = ["dti", "purpose", "purpose"]
    transformed_table, original = native_gain_tables(FakeBooster(), transformed, mapping)
    assert transformed_table["transformed_feature"].tolist()[0].startswith(("numeric__", "categorical__"))
    assert set(original.original_feature) == {"dti", "purpose"}
    assert original.xgboost_gain.sum() == pytest.approx(1.0)
    assert int(original.loc[original.original_feature.eq("purpose"), "transformed_feature_count"].iloc[0]) == 2


def test_validation_sample_is_stratified_deterministic_and_uses_only_validation():
    validation = pd.DataFrame({"loan_id": range(100), "target": [0] * 80 + [1] * 20, "dti": range(100)})
    predictions = pd.DataFrame({"loan_id": range(100), "target": validation.target,
                                "predicted_pd": np.linspace(0.01, 0.99, 100)})
    first = deterministic_validation_sample(validation, predictions, sample_size=40, random_state=42)
    second = deterministic_validation_sample(validation, predictions, sample_size=40, random_state=42)
    assert first.sample.loan_id.tolist() == second.sample.loan_id.tolist()
    assert first.sample.target.value_counts().to_dict() == {0: 32, 1: 8}
    assert first.sample_predictions.loan_id.tolist() == first.sample.loan_id.tolist()
    with pytest.raises(GateError, match="membership"):
        deterministic_validation_sample(validation, predictions.iloc[:-1], sample_size=40)


def test_local_example_selection_and_locked_classification_are_deterministic():
    probability = np.linspace(0.02, 0.98, 100)
    ids = list(range(100))
    assert select_local_examples(probability, ids) == select_local_examples(probability, ids)
    selected = select_local_examples(probability, ids)
    assert [kind for kind, _ in selected] == ["low", "medium", "high"]
    assert [int(probability[index] >= explainability.LOCKED_THRESHOLD) for _, index in selected] == [0, 1, 1]


def test_ml_lc_09_full_synthetic_run_artifacts_integrity_and_repeatability(tmp_path, monkeypatch):
    inputs, model_hash = _stage_fixture(tmp_path)
    _install_fake_shap(monkeypatch)
    monkeypatch.setattr(explainability, "_plot_gain", lambda _table, path: (path.parent.mkdir(parents=True, exist_ok=True), path.write_bytes(b"synthetic")))
    monkeypatch.setattr(explainability, "_plot_shap_summary", lambda _shap, _values, _x, _names, _table, path: (path.parent.mkdir(parents=True, exist_ok=True), path.write_bytes(b"synthetic")))
    real_read_parquet = pd.read_parquet

    def no_test_read(path, *args, **kwargs):
        assert not str(path).endswith("test_ids.parquet"), "frozen test cannot be read by explainability"
        return real_read_parquet(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_parquet", no_test_read)
    first = run_ml_lc_09(**inputs)
    global_path = inputs["output_dir"] / "ml_lc_09_global_importance.csv"
    local_path = inputs["output_dir"] / "ml_lc_09_local_explanations.csv"
    sample_path = inputs["output_dir"] / "ml_lc_09_shap_sample.parquet"
    global_hash = _hash(global_path)
    local_hash = _hash(local_path)
    sample_hash = _hash(sample_path)
    second = run_ml_lc_09(**inputs)
    assert first["status"] == second["status"] == "PASS"
    assert first["shap_available"] is True
    assert first["shap_method"] == "shap.TreeExplainer(model_output='raw')"
    assert first["xgboost_gain_type"].startswith("gain;")
    assert first["model_sha256_before"] == first["model_sha256_after"] == model_hash
    assert first["model_retrained"] is first["candidate_changed"] is first["threshold_changed"] is False
    assert first["frozen_test_used_for_explainability"] is False
    assert first["validation_rows"] == 60 and first["shap_sample_rows"] == 30
    assert first["original_feature_count"] == 2 and first["transformed_feature_count"] == 3
    assert first["shap_additivity_max_abs_error"] <= 1e-3
    global_table = pd.read_csv(global_path)
    assert not global_table.original_feature.str.match(r"f\d+").any()
    assert global_table.feature.tolist() == global_table.original_feature.tolist()
    local = pd.read_csv(local_path)
    assert set(local.risk_example_type) == {"low", "medium", "high"}
    assert local.predicted_class.eq((local.predicted_pd >= explainability.LOCKED_THRESHOLD).astype(int)).all()
    assert set(local.direction) <= {"risk_increasing", "risk_decreasing"}
    assert pd.read_parquet(sample_path).groupby("loan_id").size().eq(2).all()
    assert _hash(global_path) == global_hash and _hash(local_path) == local_hash and _hash(sample_path) == sample_hash
    manifest = json.loads((inputs["output_dir"] / "ml_lc_09_manifest.json").read_text())
    assert manifest["status"] == "PASS" and manifest["explainability_partition"] == "validation"
    assert manifest["next_stage"] == "ml-lc-10"


def test_missing_shap_marks_partial_result_blocked_without_fabrication(tmp_path, monkeypatch):
    inputs, model_hash = _stage_fixture(tmp_path)
    monkeypatch.setitem(sys.modules, "shap", None)
    monkeypatch.setattr(explainability, "_plot_gain", lambda _table, path: (path.parent.mkdir(parents=True, exist_ok=True), path.write_bytes(b"gain")))
    result = run_ml_lc_09(**inputs)
    assert result["status"] == "BLOCKED"
    assert result["shap_available"] is False and result["shap_error"]
    assert result["model_sha256_before"] == result["model_sha256_after"] == model_hash
    gain = pd.read_csv(result["global_importance_path"])
    assert gain.xgboost_gain.notna().all()
    assert gain.mean_abs_shap.isna().all()
    assert result["local_explanations_path"] is None


def test_nonfinite_shap_rejected():
    with pytest.raises(GateError, match="non-finite"):
        aggregate_shap_by_original(np.array([[math.nan]]), ["numeric__dti"], ["dti"])
