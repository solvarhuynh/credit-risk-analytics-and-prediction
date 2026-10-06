"""Tests cho src.models.scoring."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models.scoring import (
    CreditScoreConfig,
    assign_risk_tier,
    log_odds_to_probability,
    probability_to_credit_score,
    probability_to_log_odds,
    ML_LC_10_LOCKED_MODEL,
    ML_LC_10_LOCKED_THRESHOLD,
    ML_LC_10_MODEL_VERSION,
    ML_LC_10_TIER_LABELS,
    assign_pd_risk_tier,
    build_ml_lc_10_scored_dataset,
    build_risk_tier_summary,
    build_score_summary,
    probability_to_project_credit_score,
    probability_to_risk_score,
    risk_tier_boundaries,
    run_ml_lc_10,
    validate_score_monotonicity,
    validate_probability_of_default,
)


@pytest.fixture
def default_score_config() -> CreditScoreConfig:
    """Fixture cấu hình PDO chuẩn (base 600, base odds 1:19, pdo 20)."""
    return CreditScoreConfig(
        base_score=600.0,
        base_odds=0.05,
        pdo=20.0,
        min_score=300.0,
        max_score=850.0,
    )


def test_monotonicity_higher_pd_lower_score(
    default_score_config: CreditScoreConfig,
) -> None:
    """PD tăng thì credit score phải giảm nghiêm ngặt."""
    probabilities = np.array([0.01, 0.05, 0.10, 0.20, 0.50, 0.80])
    scores = probability_to_credit_score(probabilities, config=default_score_config)

    # Đảm bảo hiệu số score liền kề luôn âm (giảm dần)
    assert np.all(np.diff(scores) < 0)


def test_pd_extremes_do_not_produce_inf(
    default_score_config: CreditScoreConfig,
) -> None:
    """PD tại biên 0.0 và 1.0 không gây ra inf hay nan nhờ epsilon clipping."""
    extreme_pds = np.array([0.0, 1e-12, 0.5, 1.0 - 1e-12, 1.0])
    log_odds = probability_to_log_odds(extreme_pds, epsilon=1e-6)
    assert np.isfinite(log_odds).all()

    scores = probability_to_credit_score(extreme_pds, config=default_score_config)
    assert np.isfinite(scores).all()


def test_score_clipping_bounds(default_score_config: CreditScoreConfig) -> None:
    """Điểm số được clip chuẩn xác trong khoảng [min_score, max_score]."""
    # Cấu hình boundary hẹp để kiểm tra clipping
    bounded_config = CreditScoreConfig(
        base_score=600.0,
        base_odds=0.05,
        pdo=100.0,
        min_score=500.0,
        max_score=700.0,
    )
    pds = np.array([0.0001, 0.5, 0.9999])
    scores = probability_to_credit_score(pds, config=bounded_config)

    assert np.all(scores >= 500.0)
    assert np.all(scores <= 700.0)
    assert scores[0] == 700.0  # Rủi ro cực thấp chạm max_score
    assert scores[-1] == 500.0  # Rủi ro cực cao chạm min_score


def test_score_calculation_reproducibility(
    default_score_config: CreditScoreConfig,
) -> None:
    """Cùng PD và cùng config luôn trả về kết quả số học giống nhau hoàn toàn."""
    pds = np.array([0.02, 0.08, 0.25])
    run_1 = probability_to_credit_score(pds, config=default_score_config)
    run_2 = probability_to_credit_score(pds, config=default_score_config)
    np.testing.assert_array_equal(run_1, run_2)


def test_round_trip_probability_conversion() -> None:
    """Chuyển đổi PD -> log_odds -> PD xấp xỉ giá trị gốc trong khoảng (0, 1)."""
    original_pds = np.array([0.05, 0.1, 0.3, 0.7, 0.9])
    log_odds = probability_to_log_odds(original_pds, epsilon=1e-6)
    reconstructed_pds = log_odds_to_probability(log_odds)
    np.testing.assert_allclose(reconstructed_pds, original_pds, rtol=1e-4)


def test_invalid_probability_rejected() -> None:
    """PD ngoài [0, 1] hoặc chứa inf/nan phải raise ValueError."""
    with pytest.raises(ValueError, match="giá trị hữu hạn trong"):
        validate_probability_of_default([-0.1, 0.5])

    with pytest.raises(ValueError, match="giá trị hữu hạn trong"):
        validate_probability_of_default([0.5, 1.1])

    with pytest.raises(ValueError, match="giá trị hữu hạn trong"):
        validate_probability_of_default([np.nan, 0.5])


def test_risk_tier_assignment_deterministic() -> None:
    """Gán risk tier theo ngưỡng score chính xác và tất định."""
    thresholds = [550.0, 650.0]
    labels = ["HIGH_RISK", "MEDIUM_RISK", "LOW_RISK"]
    scores = np.array([500.0, 550.0, 600.0, 650.0, 700.0])

    tiers = assign_risk_tier(scores, score_thresholds=thresholds, tier_labels=labels)

    # searchsorted side='left':
    # 500 < 550 -> index 0 (HIGH_RISK)
    # 550 <= 550 -> index 0 (HIGH_RISK)
    # 600 in (550, 650] -> index 1 (MEDIUM_RISK)
    # 650 <= 650 -> index 1 (MEDIUM_RISK)
    # 700 > 650 -> index 2 (LOW_RISK)
    expected = ["HIGH_RISK", "HIGH_RISK", "MEDIUM_RISK", "MEDIUM_RISK", "LOW_RISK"]
    assert list(tiers) == expected


def test_non_monotonic_tier_thresholds_rejected() -> None:
    """score_thresholds không tăng dần nghiêm ngặt phải raise ValueError."""
    with pytest.raises(ValueError, match="tăng dần nghiêm ngặt"):
        assign_risk_tier(
            [600.0],
            score_thresholds=[650.0, 550.0],
            tier_labels=["HIGH", "MED", "LOW"],
        )


def test_tier_labels_mismatch_rejected() -> None:
    """Số lượng tier_labels không khớp đúng len(thresholds) + 1 phải raise ValueError."""
    with pytest.raises(ValueError, match="nhiều hơn score_thresholds đúng một phần tử"):
        assign_risk_tier(
            [600.0],
            score_thresholds=[550.0, 650.0],
            tier_labels=["HIGH", "LOW"],  # 2 labels nhưng có 2 thresholds
        )


def test_invalid_score_config_rejected() -> None:
    """Cấu hình pdo <= 0, base_odds <= 0 hoặc min > max phải raise ValueError."""
    with pytest.raises(ValueError, match="pdo phải dương"):
        CreditScoreConfig(base_score=600, base_odds=0.05, pdo=-10)
        probability_to_credit_score(
            [0.1], config=CreditScoreConfig(base_score=600, base_odds=0.05, pdo=-10)
        )

    with pytest.raises(ValueError, match="min_score không được lớn hơn max_score"):
        probability_to_credit_score(
            [0.1],
            config=CreditScoreConfig(
                base_score=600,
                base_odds=0.05,
                pdo=20,
                min_score=800,
                max_score=400,
            ),
        )


def test_ml_lc_10_score_endpoints_bounds_and_directions() -> None:
    """Project scores have the contracted range and inverse directions."""
    pd_values = np.array([0.0, 0.25, 0.5, 1.0])
    risk = probability_to_risk_score(pd_values)
    credit = probability_to_project_credit_score(pd_values)

    np.testing.assert_array_equal(risk, [0.0, 25.0, 50.0, 100.0])
    np.testing.assert_array_equal(credit, [1000, 750, 500, 0])
    assert risk.min() == 0 and risk.max() == 100
    assert credit.min() == 0 and credit.max() == 1000
    validate_score_monotonicity(pd_values)


def test_ml_lc_10_risk_tier_exact_boundaries_cover_all_pd_values() -> None:
    """Tier lower boundaries are inclusive and tiers cover closed PD [0,1]."""
    boundaries = risk_tier_boundaries(ML_LC_10_LOCKED_THRESHOLD)
    first = ML_LC_10_LOCKED_THRESHOLD / 2
    second = ML_LC_10_LOCKED_THRESHOLD
    third = min(2 * ML_LC_10_LOCKED_THRESHOLD, 1.0)
    assert boundaries["tier_a_upper_exclusive"] == first
    assert boundaries["tier_b_upper_exclusive"] == second
    assert boundaries["tier_c_upper_exclusive"] == third

    points = np.array([0.0, first, second, third, 1.0])
    tiers = assign_pd_risk_tier(points, decision_threshold=ML_LC_10_LOCKED_THRESHOLD)
    assert tiers.tolist() == [
        ML_LC_10_TIER_LABELS[0],
        ML_LC_10_TIER_LABELS[1],
        ML_LC_10_TIER_LABELS[2],
        ML_LC_10_TIER_LABELS[3],
        ML_LC_10_TIER_LABELS[3],
    ]
    assert len(tiers) == len(points) and not pd.isna(tiers).any()
    assert len(set(tiers.tolist())) == 4


def test_ml_lc_10_scores_and_tiers_do_not_use_target() -> None:
    """Changing labels cannot alter deterministic PD-derived outputs."""
    pds = np.array([0.01, 0.15, 0.3, 0.8])
    context = pd.DataFrame({"loan_id": [1, 2, 3, 4], "fico_avg": [650, 670, 690, 710]})
    base = pd.DataFrame({
        "loan_id": [1, 2, 3, 4],
        "target": [0, 1, 0, 1],
        "predicted_pd": pds,
        "predicted_class": (pds >= ML_LC_10_LOCKED_THRESHOLD).astype(int),
    })
    changed_target = base.assign(target=[1, 0, 1, 0])

    first = build_ml_lc_10_scored_dataset(
        base, context, decision_threshold=ML_LC_10_LOCKED_THRESHOLD,
    )
    second = build_ml_lc_10_scored_dataset(
        changed_target, context, decision_threshold=ML_LC_10_LOCKED_THRESHOLD,
    )
    np.testing.assert_array_equal(first["risk_score"], second["risk_score"])
    np.testing.assert_array_equal(first["credit_score"], second["credit_score"])
    np.testing.assert_array_equal(first["risk_tier"], second["risk_tier"])
    assert set(first["model_version"]) == {ML_LC_10_MODEL_VERSION}


def test_ml_lc_10_context_join_preserves_rows_and_rejects_expansion() -> None:
    """A one-to-one context join preserves source order and fails on duplicate keys."""
    pds = np.array([0.03, 0.16, 0.3])
    predictions = pd.DataFrame({
        "loan_id": [30, 10, 20],
        "target": [0, 1, 0],
        "predicted_pd": pds,
        "predicted_class": (pds >= ML_LC_10_LOCKED_THRESHOLD).astype(int),
    })
    context = pd.DataFrame({"loan_id": [10, 20, 30], "fico_avg": [601, 702, 803]})
    scored = build_ml_lc_10_scored_dataset(
        predictions, context, decision_threshold=ML_LC_10_LOCKED_THRESHOLD,
    )
    assert len(scored) == len(predictions)
    assert scored["loan_id"].tolist() == predictions["loan_id"].tolist()
    assert scored["loan_id"].is_unique
    assert scored["fico_avg"].tolist() == [803, 601, 702]

    duplicate_context = pd.concat([context, context.iloc[[0]]], ignore_index=True)
    with pytest.raises(Exception, match="unique/non-null"):
        build_ml_lc_10_scored_dataset(
            predictions, duplicate_context, decision_threshold=ML_LC_10_LOCKED_THRESHOLD,
        )


def test_ml_lc_10_summaries_reconcile_rows_and_keep_pd_separate_from_outcome() -> None:
    """Tier and score summaries reconcile the evaluated population."""
    pds = np.array([0.02, 0.12, 0.3, 0.6, 0.8])
    predictions = pd.DataFrame({
        "loan_id": np.arange(5),
        "target": [0, 0, 1, 0, 1],
        "predicted_pd": pds,
        "predicted_class": (pds >= ML_LC_10_LOCKED_THRESHOLD).astype(int),
    })
    context = pd.DataFrame({"loan_id": np.arange(5), "fico_avg": [600, 620, 640, 660, 680]})
    scored = build_ml_lc_10_scored_dataset(
        predictions, context, decision_threshold=ML_LC_10_LOCKED_THRESHOLD,
    )
    tier_summary = build_risk_tier_summary(scored)
    score_summary = build_score_summary(scored)

    assert tier_summary["loan_count"].sum() == len(scored)
    assert tier_summary["share"].sum() == pytest.approx(1.0)
    assert {"mean_predicted_pd", "observed_default_rate"}.issubset(tier_summary.columns)
    assert score_summary["count"].eq(len(scored)).all()
    assert set(score_summary["variable"]) == {"predicted_pd", "risk_score", "credit_score"}
    assert (tier_summary["mean_predicted_pd"].dropna().diff().dropna() >= 0).all()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_ml_lc_10_prerequisites(
    root: Path,
) -> tuple[Path, Path, Path, dict[str, str]]:
    """Create a small locked synthetic population and prerequisite evidence."""
    output_dir = root / "modeling"
    reports_dir = root / "reports"
    output_dir.mkdir(parents=True)
    model_path = output_dir / "xgboost_candidate.joblib"
    model_path.write_bytes(b"frozen fitted artifact; test must never load/fit it")
    prediction_path = output_dir / "ml_lc_08_frozen_test_predictions.parquet"
    pds = np.array([
        0.0,
        ML_LC_10_LOCKED_THRESHOLD / 2,
        ML_LC_10_LOCKED_THRESHOLD,
        2 * ML_LC_10_LOCKED_THRESHOLD,
        0.03,
        0.16,
        0.30,
        0.80,
    ])
    predictions = pd.DataFrame({
        "loan_id": np.arange(100, 108),
        "target": [0, 0, 1, 1, 0, 1, 0, 1],
        "predicted_pd": pds,
        "predicted_class": (pds >= ML_LC_10_LOCKED_THRESHOLD).astype(int),
    })
    predictions.to_parquet(prediction_path, index=False)

    ml07_path = output_dir / "ml_lc_07_manifest.json"
    ml07 = {
        "stage": "ml-lc-07",
        "status": "PASS",
        "locked_candidate": ML_LC_10_LOCKED_MODEL,
        "selected_threshold": ML_LC_10_LOCKED_THRESHOLD,
        "selection_partition": "validation",
        "threshold_selected": True,
        "model_retrained": False,
        "frozen_test_used_for_threshold_selection": False,
        "frozen_test_used_for_evaluation": False,
        "source_model_sha256_after": _sha256_file(model_path),
    }
    ml07_path.write_text(json.dumps(ml07), encoding="utf-8")
    ml08_path = output_dir / "ml_lc_08_manifest.json"
    ml08 = {
        "stage": "ml-lc-08",
        "status": "PASS",
        "selected_candidate": ML_LC_10_LOCKED_MODEL,
        "selected_threshold": ML_LC_10_LOCKED_THRESHOLD,
        "test_prediction_path": str(prediction_path),
        "test_rows": len(predictions),
        "test_evaluated": True,
        "frozen_test_used_for_final_evaluation": True,
        "model_retrained": False,
        "candidate_changed": False,
        "threshold_changed": False,
        "protected_sha256_before": {
            model_path.name: _sha256_file(model_path),
            ml07_path.name: _sha256_file(ml07_path),
        },
        "test_prediction_sha256": _sha256_file(prediction_path),
    }
    ml08_path.write_text(json.dumps(ml08), encoding="utf-8")
    ml09_path = output_dir / "ml_lc_09_manifest.json"
    ml09_path.write_text(json.dumps({
        "stage": "ml-lc-09",
        "status": "PASS",
        "model": ML_LC_10_LOCKED_MODEL,
        "selected_threshold": ML_LC_10_LOCKED_THRESHOLD,
        "explainability_partition": "validation",
        "model_retrained": False,
        "candidate_changed": False,
        "threshold_changed": False,
        "frozen_test_used_for_explainability": False,
        "model_sha256_before": _sha256_file(model_path),
        "model_sha256_after": _sha256_file(model_path),
    }), encoding="utf-8")

    for stage in ("ml-lc-07", "ml-lc-08", "ml-lc-09"):
        marker = {
            "stage": stage,
            "status": "PASS",
            "selected_candidate": ML_LC_10_LOCKED_MODEL,
            "selected_threshold": ML_LC_10_LOCKED_THRESHOLD,
        }
        marker_path = reports_dir / "tv1_stages" / "state" / f"{stage}.json"
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps(marker), encoding="utf-8")

    canonical_path = root / "canonical.parquet"
    canonical = pd.DataFrame({
        "loan_id": np.arange(100, 108),
        "fico_avg": np.arange(650, 658),
        "dti": np.linspace(2, 20, 8),
        "loan_amnt": np.arange(1000, 9000, 1000),
        "annual_inc": np.arange(30000, 110000, 10000),
        "loan_to_income_ratio": np.linspace(0.01, 0.08, 8),
        "purpose": ["debt_consolidation"] * 8,
        "home_ownership": ["RENT"] * 8,
        "term_months": [36] * 8,
        "issue_year": [2015] * 8,
        "sensitive_unneeded_column": ["do not join"] * 8,
    })
    canonical.to_parquet(canonical_path, index=False)
    dictionary_path = root / "data_dictionary.csv"
    pd.DataFrame({
        "column_name": ["fico_avg", "dti", "loan_amnt", "annual_inc",
                        "loan_to_income_ratio", "purpose", "home_ownership",
                        "term_months", "issue_year"],
        "policy_class": ["CREDIT_SNAPSHOT", "CREDIT_SNAPSHOT", "APPLICATION_TIME",
                         "APPLICATION_TIME", "APPLICATION_TIME", "APPLICATION_TIME",
                         "APPLICATION_TIME", "APPLICATION_TIME", "APPLICATION_TIME"],
    }).to_csv(dictionary_path, index=False)
    protected_paths = [model_path, ml07_path, ml08_path, prediction_path]
    return canonical_path, dictionary_path, output_dir, {
        str(path): _sha256_file(path) for path in protected_paths
    }


def test_run_ml_lc_10_is_deterministic_and_preserves_locked_inputs(tmp_path) -> None:
    """Stage uses existing predictions, keeps model locks, and reruns deterministically."""
    canonical_path, dictionary_path, output_dir, protected_before = _write_ml_lc_10_prerequisites(tmp_path)
    reports_dir = tmp_path / "reports"
    first = run_ml_lc_10(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
        expected_rows=8,
    )
    scored_path = output_dir / "ml_lc_10_scored_frozen_test.parquet"
    tier_path = output_dir / "ml_lc_10_risk_tier_summary.csv"
    score_path = output_dir / "ml_lc_10_score_summary.csv"
    first_scored = pd.read_parquet(scored_path)
    first_tiers = pd.read_csv(tier_path)
    first_scores = pd.read_csv(score_path)
    assert len(first_scored) == 8 and first_scored["loan_id"].is_unique
    source_predictions = pd.read_parquet(output_dir / "ml_lc_08_frozen_test_predictions.parquet")
    pd.testing.assert_frame_equal(
        first_scored[source_predictions.columns], source_predictions,
        check_dtype=False,
    )
    assert "sensitive_unneeded_column" not in first_scored.columns
    assert first["model_retrained"] is False
    assert first["candidate_changed"] is False
    assert first["threshold_changed"] is False
    assert first["frozen_test_used_for_tuning"] is False
    assert first["decision_threshold"] == ML_LC_10_LOCKED_THRESHOLD
    assert first["risk_tier_counts"] == dict(zip(first_tiers["risk_tier"], first_tiers["loan_count"]))
    assert first_tiers["loan_count"].sum() == 8
    assert first_tiers["share"].sum() == pytest.approx(1.0)
    assert first_scores["count"].eq(8).all()

    second = run_ml_lc_10(
        canonical_path=canonical_path,
        dictionary_path=dictionary_path,
        output_dir=output_dir,
        reports_dir=reports_dir,
        expected_rows=8,
    )
    pd.testing.assert_frame_equal(first_scored, pd.read_parquet(scored_path))
    pd.testing.assert_frame_equal(first_tiers, pd.read_csv(tier_path))
    pd.testing.assert_frame_equal(first_scores, pd.read_csv(score_path))
    assert first["risk_tier_counts"] == second["risk_tier_counts"]
    assert first["risk_tier_shares"] == second["risk_tier_shares"]
    assert {
        str(path): _sha256_file(Path(path)) for path in protected_before
    } == protected_before
    marker = json.loads((reports_dir / "tv1_stages/state/ml-lc-10.json").read_text())
    assert marker["status"] == "PASS"


def test_build_scored_dataset_fails_closed_when_class_or_context_is_invalid() -> None:
    """The locked class and a complete one-to-one context join are enforced."""
    pds = np.array([0.1, 0.3])
    predictions = pd.DataFrame({
        "loan_id": [1, 2],
        "target": [0, 1],
        "predicted_pd": pds,
        "predicted_class": [0, 0],
    })
    context = pd.DataFrame({"loan_id": [1, 2], "fico_avg": [650, 700]})
    with pytest.raises(Exception, match="predicted_class.*threshold"):
        build_ml_lc_10_scored_dataset(
            predictions, context, decision_threshold=ML_LC_10_LOCKED_THRESHOLD,
        )
    with pytest.raises(Exception, match="thiếu loan_id"):
        build_ml_lc_10_scored_dataset(
            predictions.iloc[[0]], context.iloc[[1]], decision_threshold=ML_LC_10_LOCKED_THRESHOLD,
        )


def test_ml_lc_10_rejects_context_columns_outside_safe_dictionary_classes(tmp_path) -> None:
    """Context policy changes to post-loan/leakage classes block the scoring stage."""
    canonical_path, dictionary_path, output_dir, _ = _write_ml_lc_10_prerequisites(tmp_path)
    dictionary = pd.read_csv(dictionary_path)
    dictionary.loc[dictionary["column_name"].eq("purpose"), "policy_class"] = "POST_LOAN"
    dictionary.to_csv(dictionary_path, index=False)
    with pytest.raises(Exception, match="policy class không an toàn"):
        run_ml_lc_10(
            canonical_path=canonical_path,
            dictionary_path=dictionary_path,
            output_dir=output_dir,
            reports_dir=tmp_path / "reports",
            expected_rows=8,
        )

