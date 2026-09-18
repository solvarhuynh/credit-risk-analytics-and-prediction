"""Tests cho src.models.cost_optimization."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.cost_optimization import (
    calculate_expected_loss,
    calculate_portfolio_expected_loss,
    evaluate_threshold_policy,
)


def test_expected_loss_formula_and_zeros() -> None:
    """Expected Loss = PD * LGD * EAD; một trong các thành phần bằng 0 thì EL bằng 0."""
    # PD = 0 -> EL = 0
    el_zero_pd = calculate_expected_loss(
        probability_of_default=0.0,
        loss_given_default=0.45,
        exposure_at_default=100000.0,
    )
    assert el_zero_pd[0] == 0.0

    # LGD = 0 -> EL = 0
    el_zero_lgd = calculate_expected_loss(
        probability_of_default=0.1,
        loss_given_default=0.0,
        exposure_at_default=100000.0,
    )
    assert el_zero_lgd[0] == 0.0

    # EAD = 0 -> EL = 0
    el_zero_ead = calculate_expected_loss(
        probability_of_default=0.1,
        loss_given_default=0.45,
        exposure_at_default=0.0,
    )
    assert el_zero_ead[0] == 0.0

    # Tính toán chuẩn: 0.1 * 0.5 * 200000 = 10000
    el_standard = calculate_expected_loss(
        probability_of_default=0.1,
        loss_given_default=0.5,
        exposure_at_default=200000.0,
    )
    assert el_standard[0] == 10000.0


def test_portfolio_expected_loss_is_sum_of_individual_losses() -> None:
    """Portfolio EL phải bằng chính xác tổng các Expected Loss của từng khoản vay."""
    pds = np.array([0.05, 0.10, 0.20])
    lgd = 0.45
    eads = np.array([100000.0, 50000.0, 200000.0])

    individual_el = calculate_expected_loss(pds, lgd, eads)
    portfolio_el = calculate_portfolio_expected_loss(pds, lgd, eads)

    assert portfolio_el == pytest.approx(float(individual_el.sum()))


def test_series_index_preservation_and_alignment() -> None:
    """pd.Series đầu vào có index trùng khớp thì kết quả trả về Series cùng index."""
    idx = pd.Index([101, 102, 103], name="SK_ID_CURR")
    pd_series = pd.Series([0.05, 0.1, 0.2], index=idx)
    lgd_series = pd.Series([0.4, 0.4, 0.4], index=idx)
    ead_series = pd.Series([10000.0, 20000.0, 30000.0], index=idx)

    result = calculate_expected_loss(pd_series, lgd_series, ead_series)

    assert isinstance(result, pd.Series)
    pd.testing.assert_index_equal(result.index, idx)
    assert result.name == "EXPECTED_LOSS"


def test_series_index_mismatch_rejected() -> None:
    """Các Series đầu vào khác index phải raise ValueError."""
    idx_1 = pd.Index([1, 2, 3])
    idx_2 = pd.Index([1, 2, 4])
    pd_series = pd.Series([0.1, 0.2, 0.3], index=idx_1)
    lgd_series = pd.Series([0.5, 0.5, 0.5], index=idx_2)

    with pytest.raises(ValueError, match="cùng index và thứ tự"):
        calculate_expected_loss(pd_series, lgd_series, 10000.0)


def test_invalid_input_ranges_rejected() -> None:
    """PD ngoài [0, 1], LGD ngoài [0, 1], hoặc EAD âm phải raise ValueError."""
    with pytest.raises(ValueError, match="PD phải nằm trong"):
        calculate_expected_loss(probability_of_default=1.5, loss_given_default=0.4, exposure_at_default=1000.0)

    with pytest.raises(ValueError, match="LGD phải nằm trong"):
        calculate_expected_loss(probability_of_default=0.1, loss_given_default=-0.1, exposure_at_default=1000.0)

    with pytest.raises(ValueError, match="EAD phải nằm trong"):
        calculate_expected_loss(probability_of_default=0.1, loss_given_default=0.4, exposure_at_default=-500.0)


def test_missing_or_nan_values_rejected() -> None:
    """Đầu vào chứa NaN hoặc inf không được tự thay bằng 0 mà phải raise ValueError."""
    with pytest.raises(ValueError, match="không được rỗng, missing hoặc vô hạn"):
        calculate_expected_loss(
            probability_of_default=[0.1, np.nan],
            loss_given_default=0.5,
            exposure_at_default=10000.0,
        )


def test_evaluate_threshold_policy() -> None:
    """Đánh giá threshold policy: record approve khi PD < threshold, reject khi PD >= threshold."""
    # 4 records:
    # 0: PD=0.1 (target=0, approved), EL = 0.1 * 0.5 * 1000 = 50
    # 1: PD=0.2 (target=1, approved), EL = 0.2 * 0.5 * 1000 = 100
    # 2: PD=0.3 (target=0, rejected)
    # 3: PD=0.4 (target=1, rejected)
    targets = [0, 1, 0, 1]
    pds = [0.1, 0.2, 0.3, 0.4]
    lgd = 0.5
    ead = 1000.0

    summary = evaluate_threshold_policy(
        target=targets,
        probability_of_default=pds,
        loss_given_default=lgd,
        exposure_at_default=ead,
        threshold=0.25,
    )

    assert summary.threshold == 0.25
    assert summary.approved_count == 2
    assert summary.rejected_count == 2
    assert summary.observed_defaults_approved == 1
    assert summary.expected_loss_approved == pytest.approx(150.0)


def test_evaluate_threshold_policy_target_mismatch_rejected() -> None:
    """TARGET length hoặc series index không khớp phải raise ValueError."""
    with pytest.raises(ValueError, match="TARGET phải không null và có cùng length"):
        evaluate_threshold_policy(
            target=[0, 1],  # length 2
            probability_of_default=[0.1, 0.2, 0.3],  # length 3
            loss_given_default=0.5,
            exposure_at_default=1000.0,
            threshold=0.5,
        )

