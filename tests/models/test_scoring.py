"""Tests cho src.models.scoring."""

from __future__ import annotations

import numpy as np
import pytest

from src.models.scoring import (
    CreditScoreConfig,
    assign_risk_tier,
    log_odds_to_probability,
    probability_to_credit_score,
    probability_to_log_odds,
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

