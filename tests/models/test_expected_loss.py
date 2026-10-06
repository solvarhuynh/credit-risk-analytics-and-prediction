"""Kiểm thử ML-LC-11 Expected Loss scenario analysis."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from src.models.expected_loss import (
    LOCKED_THRESHOLD,
    build_el_summaries,
    build_expected_loss_dataset,
    run_ml_lc_11,
    validate_reconciliation,
)


def _scored() -> pd.DataFrame:
    """Fixture scored sample nhỏ, đủ bốn tier và dashboard context."""
    return pd.DataFrame({
        "loan_id": [f"id-{i}" for i in range(8)],
        "target": [0, 1, 0, 1, 0, 1, 0, 1],
        "predicted_pd": [0.05, 0.10, 0.15, 0.20, 0.25, 0.35, 0.50, 0.80],
        "risk_score": [5, 10, 15, 20, 25, 35, 50, 80],
        "credit_score": [950, 900, 850, 800, 750, 650, 500, 200],
        "risk_tier": ["Tier A — Low", "Tier A — Low", "Tier B — Moderate", "Tier B — Moderate",
                      "Tier C — High", "Tier C — High", "Tier D — Very High", "Tier D — Very High"],
        "loan_amnt": [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000],
        "fico_avg": [650, 660, 670, 680, 690, 700, 710, 720],
        "dti": [5, 6, 7, 8, 9, 10, 11, 12],
        "annual_inc": [40000] * 8,
        "purpose": ["car", "debt", "car", "debt", "car", "debt", "car", "debt"],
        "issue_year": [2018] * 8,
    })


def test_el_formula_exact_and_zero_components() -> None:
    """EL dùng PD × LGD × EAD; từng thành phần zero cho EL bằng zero."""
    frame = _scored().iloc[:2].copy()
    frame.loc[frame.index[0], "predicted_pd"] = 0.0
    frame.loc[frame.index[1], "loan_amnt"] = 0.0
    result = build_expected_loss_dataset(frame, expected_rows=2)
    assert result.loc[0, "expected_loss"] == 0
    assert result.loc[1, "expected_loss"] == 0
    baseline = build_expected_loss_dataset(_scored(), expected_rows=8)
    assert baseline.loc[0, "expected_loss"] == pytest.approx(0.05 * 0.45 * 1000)
    assert baseline.loc[0, "expected_loss_lgd_30"] == pytest.approx(0.05 * 0.30 * 1000)
    assert baseline.loc[0, "expected_loss_lgd_60"] == pytest.approx(0.05 * 0.60 * 1000)


@pytest.mark.parametrize("column,value,match", [
    ("loan_amnt", -1, "EAD proxy"),
    ("predicted_pd", 1.1, "predicted_pd"),
])
def test_invalid_ead_and_pd_are_rejected(column: str, value: float, match: str) -> None:
    """EAD âm và PD ngoài [0,1] fail closed."""
    frame = _scored()
    frame.loc[0, column] = value
    with pytest.raises(ValueError, match=match):
        build_expected_loss_dataset(frame, expected_rows=len(frame))


def test_lgd_outside_unit_interval_and_duplicate_loan_id_are_rejected() -> None:
    """LGD ngoài [0,1] và duplicate loan_id fail closed."""
    frame = _scored()
    with pytest.raises(ValueError, match="baseline_lgd"):
        build_expected_loss_dataset(frame, baseline_lgd=1.01, expected_rows=8)
    frame.loc[1, "loan_id"] = frame.loc[0, "loan_id"]
    with pytest.raises(ValueError, match="loan_id"):
        build_expected_loss_dataset(frame, expected_rows=8)


def test_target_is_not_used_in_el_formula_and_is_only_descriptive() -> None:
    """Đổi target không đổi EL; observed default rate chỉ đổi ở summary."""
    first = _scored()
    flipped = first.copy()
    flipped.loc[0, "target"] = 1 - flipped.loc[0, "target"]
    el_first = build_expected_loss_dataset(first, expected_rows=8)
    el_flipped = build_expected_loss_dataset(flipped, expected_rows=8)
    pd.testing.assert_series_equal(el_first["expected_loss"], el_flipped["expected_loss"])
    _, tier_first = build_el_summaries(el_first)
    _, tier_flipped = build_el_summaries(el_flipped)
    assert not tier_first["observed_default_rate"].equals(tier_flipped["observed_default_rate"])


def test_rows_unique_reconciliation_and_sensitivity_monotonicity() -> None:
    """Rows and loan keys remain intact; portfolio/tier totals reconcile."""
    result = build_expected_loss_dataset(_scored(), expected_rows=8)
    portfolio, tiers = build_el_summaries(result)
    validate_reconciliation(result, portfolio, tiers)
    assert len(result) == 8 and result["loan_id"].is_unique
    assert result["loan_id"].notna().all()
    assert tiers["loan_count"].sum() == len(result)
    assert tiers["total_expected_loss"].sum() == pytest.approx(portfolio.loc[0, "total_expected_loss"])
    assert result["expected_loss_lgd_30"].le(result["expected_loss_lgd_45"]).all()
    assert result["expected_loss_lgd_45"].le(result["expected_loss_lgd_60"]).all()


def _write_runtime_inputs(tmp_path):
    """Tạo lock artifacts hợp lệ và ML-LC-10 source giả lập cho stage runner."""
    output = tmp_path / "modeling"
    output.mkdir()
    reports = tmp_path / "reports"
    (reports / "tv1_stages/state").mkdir(parents=True)
    scored = _scored()
    scored.to_parquet(output / "ml_lc_10_scored_frozen_test.parquet", index=False)
    for filename, value in {
        "xgboost_candidate.joblib": b"model-artifact-must-not-be-loaded",
    }.items():
        (output / filename).write_bytes(value)
    (output / "ml_lc_07_manifest.json").write_text(json.dumps({
        "stage": "ml-lc-07", "status": "PASS", "locked_candidate": "xgboost_candidate",
        "selection_partition": "validation", "selected_threshold": LOCKED_THRESHOLD,
    }), encoding="utf-8")
    (output / "ml_lc_08_manifest.json").write_text(json.dumps({
        "stage": "ml-lc-08", "status": "PASS", "selected_candidate": "xgboost_candidate",
        "selected_threshold": LOCKED_THRESHOLD, "test_rows": 8, "test_evaluated": True,
    }), encoding="utf-8")
    (output / "ml_lc_10_manifest.json").write_text(json.dumps({
        "stage": "ml-lc-10", "status": "PASS", "model": "xgboost_candidate",
        "decision_threshold": LOCKED_THRESHOLD, "source_rows": 8,
        "model_retrained": False, "candidate_changed": False, "threshold_changed": False,
    }), encoding="utf-8")
    (reports / "tv1_stages/state/ml-lc-10.json").write_text(json.dumps({
        "stage": "ml-lc-10", "status": "PASS",
    }), encoding="utf-8")
    protected = [output / name for name in (
        "xgboost_candidate.joblib", "ml_lc_07_manifest.json",
        "ml_lc_08_manifest.json", "ml_lc_10_manifest.json",
    )]
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    return output, reports, hashes


def test_runner_is_deterministic_preserves_hashes_and_marks_v06_ready(tmp_path) -> None:
    """Runtime deterministically writes artifacts without modifying locked inputs."""
    output, reports, hashes = _write_runtime_inputs(tmp_path)
    first = run_ml_lc_11(output_dir=output, reports_dir=reports, expected_rows=8)
    first_data = pd.read_parquet(output / "ml_lc_11_expected_loss.parquet")
    first_portfolio = pd.read_csv(output / "ml_lc_11_portfolio_el_summary.csv")
    first_tiers = pd.read_csv(output / "ml_lc_11_risk_tier_el_summary.csv")
    assert first["dashboard_readiness"]["V06"] is True
    assert first["target_used_in_el_formula"] is False
    assert first["model_fit_called"] is False and first["predict_proba_called"] is False
    assert first["decision_threshold"] == LOCKED_THRESHOLD
    assert first["protected_sha256_before"] == first["protected_sha256_after"] == hashes
    assert first["sensitivity_totals"]["30%"] <= first["sensitivity_totals"]["45%"]
    assert first["sensitivity_totals"]["45%"] <= first["sensitivity_totals"]["60%"]
    second = run_ml_lc_11(output_dir=output, reports_dir=reports, expected_rows=8)
    pd.testing.assert_frame_equal(first_data, pd.read_parquet(output / "ml_lc_11_expected_loss.parquet"))
    pd.testing.assert_frame_equal(first_portfolio, pd.read_csv(output / "ml_lc_11_portfolio_el_summary.csv"))
    pd.testing.assert_frame_equal(first_tiers, pd.read_csv(output / "ml_lc_11_risk_tier_el_summary.csv"))
    assert second["portfolio_total_expected_loss"] == first["portfolio_total_expected_loss"]
    assert json.loads((reports / "tv1_stages/state/ml-lc-11.json").read_text())["status"] == "PASS"
