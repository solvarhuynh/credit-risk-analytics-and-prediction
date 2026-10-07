"""Kiểm thử inference thật trên full-refit và validation fail-closed cho What-if."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from src.config import CANONICAL_DATASET_PATH, ML_LC_12_MANIFEST_PATH
from src.models.individual_prediction import (
    export_power_bi_artifacts,
    fetch_baseline,
    load_final_model,
    prepare_scenario,
    run_prediction,
    validate_overrides,
)
from src.models.scoring import ML_LC_10_LOCKED_THRESHOLD


LOAN_ID = "68407277"


@pytest.fixture(scope="module")
def source():
    """Lấy đúng một bản ghi canonical, không dùng frozen-test predictions."""
    _, manifest, _ = load_final_model()
    features = manifest["actual_features"]
    return features, fetch_baseline(LOAN_ID, features)


@pytest.fixture(scope="module")
def runs():
    """Hai inference thật, tuyệt đối không fit lại model."""
    return run_prediction(LOAN_ID), run_prediction(LOAN_ID, {"loan_amnt": 8600})


def test_locked_schema_and_baseline(source):
    features, baseline = source
    model, manifest, model_hash = load_final_model()
    assert len(features) == 103 == manifest["actual_feature_count"]
    assert len(model.named_steps["preprocess"].get_feature_names_out()) == 151
    assert list(model.feature_names_in_) == features
    assert model_hash == manifest["refit_model_sha256"]
    assert baseline.loc[0, "loan_id"] == LOAN_ID
    assert float(baseline.loc[0, "loan_amnt"]) == 3600


def test_baseline_and_what_if_real_outputs(runs):
    baseline, scenario = runs
    base, base_shap, base_inputs, base_meta = baseline
    changed, shap, inputs, meta = scenario
    assert base["scenario_type"] == "baseline"
    assert changed["scenario_type"] == "what_if"
    assert base["predicted_pd"] == pytest.approx(0.11998604238033295, abs=2e-7)
    assert changed["predicted_pd"] == pytest.approx(0.14499987661838531, abs=2e-7)
    assert base["predicted_class"] == changed["predicted_class"] == 0
    assert base["risk_score"] == pytest.approx(11.998604238, abs=2e-5)
    assert changed["risk_score"] == pytest.approx(14.499987662, abs=2e-5)
    assert base["project_credit_score"] == 880
    assert changed["project_credit_score"] == 855
    assert base["risk_tier"] == changed["risk_tier"] == "Tier B — Moderate"
    assert base["expected_loss_lgd_45"] == pytest.approx(194.377388656, abs=0.002)
    assert changed["expected_loss_lgd_45"] == pytest.approx(561.149522513, abs=0.002)
    assert changed["threshold"] == ML_LC_10_LOCKED_THRESHOLD
    assert changed["ead_proxy"] == 8600
    assert changed["expected_loss"] == changed["expected_loss_lgd_45"]
    assert meta["dependency_recomputation"] == ["loan_amount_band", "loan_to_income_ratio"]
    assert list(inputs["input_role"]) == ["baseline", "current"]
    assert float(inputs.loc[1, "loan_to_income_ratio"]) == pytest.approx(8600 / 55000)
    assert inputs.loc[1, "loan_amount_band"] == "5k-10k"
    assert float(base_inputs.loc[0, "loan_to_income_ratio"]) == pytest.approx(3600 / 55000)
    for table, info in ((base_shap, base_meta), (shap, meta)):
        assert len(table) == 10
        assert set(table["direction"]) <= {"risk_increasing", "risk_decreasing", "neutral"}
        assert list(table["rank_by_abs_shap"]) == list(range(1, 11))
        assert table["abs_shap_value"].is_monotonic_decreasing
        assert info["shap_output_space"].startswith("raw margin")
        assert info["shap_additivity_abs_error"] < 1e-3


@pytest.mark.parametrize("field,value,expected", [
    ("annual_inc", 30000, {"income_band": "<=40k", "loan_to_income_ratio": 3600 / 30000}),
    ("dti", 24.0, {"dti_band": "20-30"}),
    ("term_months", 60, {"term_months": 60}),
])
def test_single_override_dependencies(source, field, value, expected):
    features, baseline = source
    row, applied, recomputed = prepare_scenario(baseline, features, {field: value})
    assert applied[field] == value
    for name, expected_value in expected.items():
        if isinstance(expected_value, float):
            assert float(row.loc[0, name]) == pytest.approx(expected_value)
        else:
            assert str(row.loc[0, name]) == str(expected_value)
    if field == "term_months":
        assert recomputed == []
    assert list(row.columns) == features


def test_two_override_ratio_uses_both_new_values(source):
    features, baseline = source
    row, applied, recomputed = prepare_scenario(
        baseline, features, {"loan_amnt": 8600, "annual_inc": 30000},
    )
    assert applied == {"loan_amnt": 8600.0, "annual_inc": 30000.0}
    assert set(recomputed) == {"loan_to_income_ratio", "loan_amount_band", "income_band"}
    assert float(row.loc[0, "loan_to_income_ratio"]) == pytest.approx(8600 / 30000)
    assert row.loc[0, "loan_amount_band"] == "5k-10k"
    assert row.loc[0, "income_band"] == "<=40k"


@pytest.mark.parametrize("overrides", [
    {"term_months": 48}, {"term_months": float("nan")},
    {"annual_inc": -1}, {"annual_inc": 0}, {"annual_inc": 10999201},
    {"loan_amnt": 499}, {"loan_amnt": 40001},
    {"dti": -1}, {"dti": 1000},
    {"dti": "not-a-number"}, {"dti": float("inf")},
    {"fico_range_low": 700},
])
def test_invalid_overrides_fail_closed(overrides):
    with pytest.raises(ValueError):
        validate_overrides(overrides)


def test_missing_schema_or_unknown_and_duplicate_loan_id_fail(source, tmp_path):
    features, baseline = source
    with pytest.raises(ValueError, match="Thiếu hoặc trùng input"):
        prepare_scenario(baseline, features[:-1], {})
    with pytest.raises(ValueError, match="Không tìm thấy"):
        fetch_baseline("not-a-loan", features, CANONICAL_DATASET_PATH)
    duplicated = pd.concat([baseline, baseline], ignore_index=True)
    path = tmp_path / "duplicate.parquet"
    duplicated.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="trùng"):
        fetch_baseline(LOAN_ID, features, path)


def test_model_hash_mismatch_fails(tmp_path):
    manifest = json.loads(ML_LC_12_MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["refit_model_sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        load_final_model(manifest_path=path)


def test_model_schema_order_mismatch_fails(tmp_path):
    manifest = json.loads(ML_LC_12_MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["actual_features"][:2] = list(reversed(manifest["actual_features"][:2]))
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="thứ tự"):
        load_final_model(manifest_path=path)


def test_current_csv_handoff_and_deterministic_rerun(runs, tmp_path):
    result, shap, inputs, metadata = runs[1]
    paths = export_power_bi_artifacts(result, shap, inputs, metadata, output_dir=tmp_path)
    result_csv = pd.read_csv(paths["result"])
    shap_csv = pd.read_csv(paths["shap"])
    inputs_csv = pd.read_csv(paths["inputs"])
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert (len(result_csv), len(shap_csv), len(inputs_csv)) == (1, 10, 2)
    assert result_csv.loc[0, "scenario_id"] == manifest["scenario_id"]
    assert shap_csv["scenario_id"].eq(manifest["scenario_id"]).all()
    assert inputs_csv["scenario_id"].eq(manifest["scenario_id"]).all()
    assert manifest["overrides"] == {"loan_amnt": 8600.0}
    again, again_shap, _, again_meta = run_prediction(LOAN_ID, {"loan_amnt": 8600})
    assert again["scenario_id"] == result["scenario_id"]
    for field in ("predicted_pd", "risk_score", "expected_loss", "expected_loss_lgd_30"):
        assert again[field] == pytest.approx(result[field], rel=1e-7, abs=1e-7)
    np.testing.assert_allclose(again_shap["shap_value"], shap["shap_value"], rtol=1e-6, atol=1e-7)
    assert again_meta["shap_additivity_abs_error"] < 1e-3
    assert math.isfinite(again["predicted_pd"])
