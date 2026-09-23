"""Comprehensive tests for historical table aggregation in src.data.aggregate."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.aggregate import (
    AGGREGATE_FEATURE_DEFINITIONS,
    aggregate_bureau,
    aggregate_credit_card_balance,
    aggregate_installments_payments,
    aggregate_pos_cash_balance,
    aggregate_previous_application,
    validate_customer_aggregate,
    validate_temporal_bounds,
    write_parquet_atomic,
)


# ---------------------------------------------------------------------------
# General Validation Tests
# ---------------------------------------------------------------------------


def test_validate_customer_aggregate_success() -> None:
    """Valid aggregate DataFrame passes validation."""
    df = pd.DataFrame(
        {
            "SK_ID_CURR": [100001, 100002],
            "TEST_COUNT": [2, 0],
            "TEST_RATE": [0.5, 0.0],
            "TEST_VAL": [10.0, 20.0],
        }
    )
    validate_customer_aggregate(df, prefix="TEST_")


def test_validate_customer_aggregate_missing_key() -> None:
    """Aggregate missing SK_ID_CURR raises ValueError."""
    df = pd.DataFrame({"TEST_VAL": [10.0]})
    with pytest.raises(ValueError, match="Missing primary key 'SK_ID_CURR'"):
        validate_customer_aggregate(df, prefix="TEST_")


def test_validate_customer_aggregate_null_key() -> None:
    """Aggregate with null SK_ID_CURR raises ValueError."""
    df = pd.DataFrame({"SK_ID_CURR": [100001, None], "TEST_COUNT": [1, 2]})
    with pytest.raises(ValueError, match="null values"):
        validate_customer_aggregate(df, prefix="TEST_")


def test_validate_customer_aggregate_duplicate_key() -> None:
    """Aggregate with duplicate SK_ID_CURR raises ValueError."""
    df = pd.DataFrame({"SK_ID_CURR": [100001, 100001], "TEST_COUNT": [1, 2]})
    with pytest.raises(ValueError, match="duplicate values"):
        validate_customer_aggregate(df, prefix="TEST_")


def test_validate_customer_aggregate_target_leakage() -> None:
    """Aggregate containing TARGET column raises ValueError."""
    df = pd.DataFrame(
        {
            "SK_ID_CURR": [100001],
            "TARGET": [0],
            "TEST_COUNT": [1],
        }
    )
    with pytest.raises(ValueError, match="Target leakage violation"):
        validate_customer_aggregate(df, prefix="TEST_")


def test_validate_customer_aggregate_duplicate_columns() -> None:
    """Aggregate with duplicate column names raises ValueError."""
    df = pd.DataFrame([[100001, 1, 2]], columns=["SK_ID_CURR", "TEST_VAL", "TEST_VAL"])
    with pytest.raises(ValueError, match="Duplicate column names"):
        validate_customer_aggregate(df, prefix="TEST_")


def test_validate_customer_aggregate_wrong_prefix() -> None:
    """Aggregate with column not matching prefix raises ValueError."""
    df = pd.DataFrame({"SK_ID_CURR": [100001], "OTHER_VAL": [10.0]})
    with pytest.raises(ValueError, match="does not start with required prefix"):
        validate_customer_aggregate(df, prefix="TEST_")


def test_validate_customer_aggregate_infinity_rejected() -> None:
    """Aggregate with positive or negative infinity raises ValueError."""
    df_pos = pd.DataFrame({"SK_ID_CURR": [100001], "TEST_VAL": [np.inf]})
    with pytest.raises(ValueError, match="infinity values"):
        validate_customer_aggregate(df_pos, prefix="TEST_")

    df_neg = pd.DataFrame({"SK_ID_CURR": [100001], "TEST_VAL": [-np.inf]})
    with pytest.raises(ValueError, match="infinity values"):
        validate_customer_aggregate(df_neg, prefix="TEST_")


def test_validate_customer_aggregate_negative_count_rejected() -> None:
    """Aggregate with negative count raises ValueError."""
    df = pd.DataFrame({"SK_ID_CURR": [100001], "TEST_COUNT": [-1]})
    with pytest.raises(ValueError, match="contains negative values"):
        validate_customer_aggregate(df, prefix="TEST_")


def test_validate_customer_aggregate_rate_out_of_bounds_rejected() -> None:
    """Aggregate with rate outside [0, 1] raises ValueError."""
    df_high = pd.DataFrame({"SK_ID_CURR": [100001], "TEST_RATE": [1.5]})
    with pytest.raises(ValueError, match="outside \\[0, 1\\]"):
        validate_customer_aggregate(df_high, prefix="TEST_")

    df_low = pd.DataFrame({"SK_ID_CURR": [100001], "TEST_RATE": [-0.1]})
    with pytest.raises(ValueError, match="outside \\[0, 1\\]"):
        validate_customer_aggregate(df_low, prefix="TEST_")


def test_temporal_bounds_rejection() -> None:
    """Positive temporal offsets raise descriptive ValueError."""
    df = pd.DataFrame({"DAYS_CREDIT": [-10, -5, 1, 2]})
    with pytest.raises(ValueError, match="Leakage violation in bureau.DAYS_CREDIT"):
        validate_temporal_bounds(df, "DAYS_CREDIT", "bureau")


def test_feature_metadata_completeness() -> None:
    """Metadata mapping contains required documentation fields for all features."""
    required_keys = {
        "source_table",
        "source_grain",
        "formula",
        "unit",
        "business_meaning",
        "missing_value_interpretation",
        "as_of_leakage_note",
    }
    assert len(AGGREGATE_FEATURE_DEFINITIONS) == 74
    for feat, meta in AGGREGATE_FEATURE_DEFINITIONS.items():
        assert required_keys.issubset(set(meta.keys())), f"Incomplete metadata for {feat}"


# ---------------------------------------------------------------------------
# Bureau & Bureau Balance Aggregation Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_bureau() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SK_ID_CURR": [101, 101, 102],
            "SK_ID_BUREAU": [201, 202, 203],
            "CREDIT_ACTIVE": ["Active", "Closed", "Active"],
            "DAYS_CREDIT": [-100.0, -200.0, -300.0],
            "CREDIT_DAY_OVERDUE": [0.0, 10.0, 0.0],
            "AMT_CREDIT_SUM": [100000.0, 50000.0, 200000.0],
            "AMT_CREDIT_SUM_DEBT": [50000.0, 0.0, 150000.0],
            "AMT_CREDIT_SUM_OVERDUE": [0.0, 500.0, 0.0],
        }
    )


@pytest.fixture
def synthetic_bureau_balance() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SK_ID_BUREAU": [201, 201, 201, 202, 999, 999],  # 999 is orphan
            "MONTHS_BALANCE": [-1, -2, -3, -1, -1, -2],
            "STATUS": ["C", "1", "3", "0", "1", "5"],
        }
    )


def test_aggregate_bureau_immutability(
    synthetic_bureau: pd.DataFrame, synthetic_bureau_balance: pd.DataFrame
) -> None:
    """Caller DataFrames are not modified during aggregation."""
    b_copy = synthetic_bureau.copy(deep=True)
    bb_copy = synthetic_bureau_balance.copy(deep=True)
    aggregate_bureau(synthetic_bureau, synthetic_bureau_balance)
    pd.testing.assert_frame_equal(synthetic_bureau, b_copy)
    pd.testing.assert_frame_equal(synthetic_bureau_balance, bb_copy)


def test_aggregate_bureau_orphan_handling(
    synthetic_bureau: pd.DataFrame, synthetic_bureau_balance: pd.DataFrame
) -> None:
    """Orphan SK_ID_BUREAU in bureau_balance are counted and excluded from customer results."""
    res, diag = aggregate_bureau(synthetic_bureau, synthetic_bureau_balance)
    assert diag["orphan_bureau_balance_ids"] == 1
    assert diag["orphan_bureau_balance_rows"] == 2
    assert 999 not in res["SK_ID_CURR"].values
    assert len(res) == 2  # exactly customer 101 and 102


def test_aggregate_bureau_feature_calculations(
    synthetic_bureau: pd.DataFrame, synthetic_bureau_balance: pd.DataFrame
) -> None:
    """Feature formulas and weighted delinquency rates are correct."""
    res, _ = aggregate_bureau(synthetic_bureau, synthetic_bureau_balance)
    row_101 = res.loc[res["SK_ID_CURR"] == 101].iloc[0]

    assert row_101["BUREAU_CREDIT_COUNT"] == 2
    assert row_101["BUREAU_ACTIVE_COUNT"] == 1
    assert row_101["BUREAU_ACTIVE_RATE"] == pytest.approx(0.5)
    assert row_101["BUREAU_CLOSED_COUNT"] == 1
    assert row_101["BUREAU_CLOSED_RATE"] == pytest.approx(0.5)
    assert row_101["BUREAU_DAYS_CREDIT_MEAN"] == pytest.approx(-150.0)
    assert row_101["BUREAU_DAYS_CREDIT_MAX"] == pytest.approx(-100.0)
    assert row_101["BUREAU_AMT_CREDIT_SUM_SUM"] == pytest.approx(150000.0)
    assert row_101["BUREAU_AMT_CREDIT_SUM_MEAN"] == pytest.approx(75000.0)
    assert row_101["BUREAU_AMT_DEBT_SUM"] == pytest.approx(50000.0)
    assert row_101["BUREAU_AMT_OVERDUE_SUM"] == pytest.approx(500.0)
    assert row_101["BUREAU_AMT_OVERDUE_MAX"] == pytest.approx(500.0)

    # Bureau balance on customer 101:
    # loan 201 has 3 months: STATUS 'C' (ok), '1' (delinq), '3' (delinq + severe)
    # loan 202 has 1 month: STATUS '0' (ok)
    # Total observed: 4 months. Delinquent: 2 months. Severe: 1 month.
    assert row_101["BUREAU_BB_MONTH_COUNT"] == 4
    assert row_101["BUREAU_BB_DELINQUENT_MONTH_COUNT"] == 2
    assert row_101["BUREAU_BB_DELINQUENT_MONTH_RATE"] == pytest.approx(2 / 4)
    assert row_101["BUREAU_BB_SEVERE_MONTH_COUNT"] == 1
    assert row_101["BUREAU_BB_SEVERE_MONTH_RATE"] == pytest.approx(1 / 4)

    # Customer 102 has loan 203 which has NO records in bureau_balance
    row_102 = res.loc[res["SK_ID_CURR"] == 102].iloc[0]
    assert pd.isna(row_102["BUREAU_BB_MONTH_COUNT"])
    assert pd.isna(row_102["BUREAU_BB_DELINQUENT_MONTH_RATE"])
    assert pd.isna(row_102["BUREAU_BB_SEVERE_MONTH_RATE"])


def test_aggregate_bureau_missing_columns_raises() -> None:
    """Missing required columns raises ValueError."""
    bad_bureau = pd.DataFrame({"SK_ID_CURR": [101]})
    bad_bb = pd.DataFrame({"SK_ID_BUREAU": [201]})
    with pytest.raises(ValueError, match="missing required columns"):
        aggregate_bureau(bad_bureau, bad_bb)


def test_aggregate_bureau_duplicate_loan_key_rejected(
    synthetic_bureau: pd.DataFrame, synthetic_bureau_balance: pd.DataFrame
) -> None:
    """A duplicated bureau loan key must fail before the one-to-one internal merge."""
    duplicate_bureau = pd.concat(
        [synthetic_bureau, synthetic_bureau.iloc[[0]]], ignore_index=True
    )

    with pytest.raises(ValueError, match="SK_ID_BUREAU.*duplicate values"):
        aggregate_bureau(duplicate_bureau, synthetic_bureau_balance)


# ---------------------------------------------------------------------------
# Previous Application Aggregation Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_prev_app() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SK_ID_PREV": [301, 302, 303],
            "SK_ID_CURR": [101, 101, 102],
            "NAME_CONTRACT_STATUS": ["Approved", "Refused", "Approved"],
            "AMT_APPLICATION": [100000.0, 50000.0, 0.0],
            "AMT_CREDIT": [120000.0, 0.0, 50000.0],
            "AMT_ANNUITY": [10000.0, 5000.0, 2000.0],
            "DAYS_DECISION": [-50.0, -150.0, -20.0],
        }
    )


def test_aggregate_previous_application_immutability(synthetic_prev_app: pd.DataFrame) -> None:
    """Caller DataFrame is not modified."""
    copy_df = synthetic_prev_app.copy(deep=True)
    aggregate_previous_application(synthetic_prev_app)
    pd.testing.assert_frame_equal(synthetic_prev_app, copy_df)


def test_aggregate_previous_application_features(synthetic_prev_app: pd.DataFrame) -> None:
    """Features and ratios are correctly calculated."""
    res, diag = aggregate_previous_application(synthetic_prev_app)
    assert len(res) == 2
    row_101 = res.loc[res["SK_ID_CURR"] == 101].iloc[0]

    assert row_101["PREV_APPLICATION_COUNT"] == 2
    assert row_101["PREV_APPROVED_COUNT"] == 1
    assert row_101["PREV_APPROVED_RATE"] == pytest.approx(0.5)
    assert row_101["PREV_REFUSED_COUNT"] == 1
    assert row_101["PREV_REFUSED_RATE"] == pytest.approx(0.5)
    assert row_101["PREV_AMT_APPLICATION_SUM"] == pytest.approx(150000.0)
    assert row_101["PREV_AMT_CREDIT_SUM"] == pytest.approx(120000.0)
    assert row_101["PREV_AMT_ANNUITY_MEAN"] == pytest.approx(7500.0)
    assert row_101["PREV_DAYS_DECISION_MAX"] == pytest.approx(-50.0)

    # Row 101 credit to app ratios:
    # 301: 120000 / 100000 = 1.2
    # 302: 0 / 50000 = 0.0
    # Average: 0.6
    assert row_101["PREV_CREDIT_TO_APPLICATION_RATIO_MEAN"] == pytest.approx(0.6)

    # Customer 102 has AMT_APPLICATION == 0.0 -> ratio is NaN
    row_102 = res.loc[res["SK_ID_CURR"] == 102].iloc[0]
    assert pd.isna(row_102["PREV_CREDIT_TO_APPLICATION_RATIO_MEAN"])


# ---------------------------------------------------------------------------
# Installments Payments Aggregation Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_installments() -> pd.DataFrame:
    # Customer 101: Contract 401 has installment 1 split into 2 payments
    # Installment 2 paid on time in single payment
    return pd.DataFrame(
        {
            "SK_ID_PREV": [401, 401, 401, 402],
            "SK_ID_CURR": [101, 101, 101, 102],
            "NUM_INSTALMENT_VERSION": [1.0, 1.0, 1.0, 1.0],
            "NUM_INSTALMENT_NUMBER": [1, 1, 2, 1],
            "DAYS_INSTALMENT": [-100.0, -100.0, -50.0, -30.0],
            "DAYS_ENTRY_PAYMENT": [-105.0, -90.0, -50.0, -20.0],
            "AMT_INSTALMENT": [1000.0, 1000.0, 1000.0, 2000.0],
            "AMT_PAYMENT": [400.0, 500.0, 1000.0, 1500.0],
        }
    )


def test_aggregate_installments_split_payment_consolidation(
    synthetic_installments: pd.DataFrame,
) -> None:
    """Split payments within the same installment are consolidated correctly without double-summing."""
    res, diag = aggregate_installments_payments(synthetic_installments)
    assert diag["raw_installment_rows"] == 4
    assert diag["unique_installment_grains"] == 3
    assert diag["repeated_installment_keys"] == 1
    assert diag["rows_in_repeated_keys"] == 2

    # Customer 101: 2 consolidated installments
    # Inst 1: scheduled 1000 on day -100. Max entry -90. Delay: max(-90 - (-100), 0) = 10 days.
    # Total paid: 400 + 500 = 900. Shortfall: 100. Late: True, Underpaid: True.
    # Inst 2: scheduled 1000 on day -50. Max entry -50. Delay: 0. Paid: 1000. Shortfall: 0. Late: False, Underpaid: False.
    row_101 = res.loc[res["SK_ID_CURR"] == 101].iloc[0]
    assert row_101["INSTAL_INSTALLMENT_COUNT"] == 2
    assert row_101["INSTAL_LATE_COUNT"] == 1
    assert row_101["INSTAL_LATE_RATE"] == pytest.approx(0.5)
    assert row_101["INSTAL_DELAY_DAYS_MEAN"] == pytest.approx(5.0)
    assert row_101["INSTAL_DELAY_DAYS_MAX"] == pytest.approx(10.0)
    assert row_101["INSTAL_UNDERPAYMENT_COUNT"] == 1
    assert row_101["INSTAL_UNDERPAYMENT_RATE"] == pytest.approx(0.5)
    assert row_101["INSTAL_PAYMENT_SHORTFALL_SUM"] == pytest.approx(100.0)
    assert row_101["INSTAL_PAYMENT_SHORTFALL_MEAN"] == pytest.approx(50.0)
    # Ratios: 900/1000 = 0.9, 1000/1000 = 1.0 -> mean 0.95
    assert row_101["INSTAL_PAYMENT_RATIO_MEAN"] == pytest.approx(0.95)


def test_aggregate_installments_conflicting_dates_rejected() -> None:
    """Conflicting scheduled dates within same installment key raise ValueError."""
    bad_df = pd.DataFrame(
        {
            "SK_ID_PREV": [401, 401],
            "SK_ID_CURR": [101, 101],
            "NUM_INSTALMENT_VERSION": [1.0, 1.0],
            "NUM_INSTALMENT_NUMBER": [1, 1],
            "DAYS_INSTALMENT": [-100.0, -90.0],  # conflicting
            "DAYS_ENTRY_PAYMENT": [-100.0, -100.0],
            "AMT_INSTALMENT": [1000.0, 1000.0],
            "AMT_PAYMENT": [500.0, 500.0],
        }
    )
    with pytest.raises(ValueError, match="conflicting DAYS_INSTALMENT"):
        aggregate_installments_payments(bad_df)


def test_aggregate_installments_excludes_unknown_timing_from_late_rate() -> None:
    """Missing payment or due dates are unknown, not implicit on-time installments."""
    frame = pd.DataFrame(
        {
            "SK_ID_PREV": [701, 701, 701, 701],
            "SK_ID_CURR": [101, 101, 101, 101],
            "NUM_INSTALMENT_VERSION": [1.0, 1.0, 1.0, 1.0],
            "NUM_INSTALMENT_NUMBER": [1, 2, 3, 4],
            "DAYS_INSTALMENT": [-100.0, -80.0, -60.0, np.nan],
            "DAYS_ENTRY_PAYMENT": [-90.0, -80.0, np.nan, -40.0],
            "AMT_INSTALMENT": [1000.0, 1000.0, 1000.0, 1000.0],
            "AMT_PAYMENT": [1000.0, 1000.0, 1000.0, 1000.0],
        }
    )

    result, diagnostics = aggregate_installments_payments(frame)
    row = result.iloc[0]

    # The first two installments are observed: one late and one on time.
    # The other two have unknown timing and are excluded from the denominator.
    assert row["INSTAL_INSTALLMENT_COUNT"] == 4
    assert row["INSTAL_LATE_COUNT"] == 1
    assert row["INSTAL_LATE_RATE"] == pytest.approx(1 / 2)
    assert row["INSTAL_DELAY_DAYS_MEAN"] == pytest.approx(5.0)
    assert row["INSTAL_DELAY_DAYS_MAX"] == pytest.approx(10.0)
    assert diagnostics["valid_timing_installment_count"] == 2
    assert diagnostics["unknown_timing_installment_count"] == 2


# ---------------------------------------------------------------------------
# POS CASH Balance Aggregation Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_pos() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SK_ID_PREV": [501, 501, 502],
            "SK_ID_CURR": [101, 101, 101],
            "MONTHS_BALANCE": [-1, -2, -1],
            "CNT_INSTALMENT_FUTURE": [10.0, 11.0, 5.0],
            "SK_DPD": [0, 5, 0],
            "SK_DPD_DEF": [0, 2, 0],
        }
    )


def test_aggregate_pos_cash_balance(synthetic_pos: pd.DataFrame) -> None:
    """POS features are aggregated correctly."""
    res, diag = aggregate_pos_cash_balance(synthetic_pos)
    assert len(res) == 1
    row = res.iloc[0]
    assert row["POS_RECORD_COUNT"] == 3
    assert row["POS_CONTRACT_COUNT"] == 2
    assert row["POS_MONTHS_BALANCE_MIN"] == -2
    assert row["POS_MONTHS_BALANCE_MAX"] == -1
    assert row["POS_DPD_MEAN"] == pytest.approx(5 / 3)
    assert row["POS_DPD_MAX"] == 5
    assert row["POS_LATE_MONTH_COUNT"] == 1
    assert row["POS_LATE_MONTH_RATE"] == pytest.approx(1 / 3)
    assert row["POS_INSTALMENT_FUTURE_MEAN"] == pytest.approx((10 + 11 + 5) / 3)


# ---------------------------------------------------------------------------
# Credit Card Balance Aggregation Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_cc() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SK_ID_PREV": [601, 601, 602],
            "SK_ID_CURR": [101, 101, 101],
            "MONTHS_BALANCE": [-1, -2, -1],
            "AMT_BALANCE": [20000.0, 10000.0, 0.0],
            "AMT_CREDIT_LIMIT_ACTUAL": [100000.0, 100000.0, 0.0],  # 602 limit 0
            "SK_DPD": [0, 10, 0],
            "SK_DPD_DEF": [0, 5, 0],
            "AMT_PAYMENT_TOTAL_CURRENT": [5000.0, 4000.0, 0.0],
        }
    )


def test_aggregate_credit_card_balance(synthetic_cc: pd.DataFrame) -> None:
    """Credit card features, zero limit handling, and row-wise utilization are correct."""
    res, diag = aggregate_credit_card_balance(synthetic_cc)
    assert len(res) == 1
    row = res.iloc[0]
    assert row["CC_RECORD_COUNT"] == 3
    assert row["CC_CONTRACT_COUNT"] == 2
    assert row["CC_BALANCE_MEAN"] == pytest.approx(30000.0 / 3)
    assert row["CC_BALANCE_MAX"] == pytest.approx(20000.0)
    assert row["CC_CREDIT_LIMIT_MAX"] == pytest.approx(100000.0)

    # Utilization:
    # 601 month -1: 20000 / 100000 = 0.2
    # 601 month -2: 10000 / 100000 = 0.1
    # 602 month -1: limit 0 -> NaN (excluded from mean/max)
    assert row["CC_UTILIZATION_MEAN"] == pytest.approx(0.15)
    assert row["CC_UTILIZATION_MAX"] == pytest.approx(0.20)

    assert row["CC_DPD_MAX"] == 10
    assert row["CC_LATE_MONTH_COUNT"] == 1
    assert row["CC_LATE_MONTH_RATE"] == pytest.approx(1 / 3)
    assert row["CC_PAYMENT_TOTAL_SUM"] == pytest.approx(9000.0)
    assert row["CC_PAYMENT_TOTAL_MEAN"] == pytest.approx(3000.0)


# ---------------------------------------------------------------------------
# Atomic Publication Tests
# ---------------------------------------------------------------------------


def test_write_parquet_atomic(tmp_path: Path) -> None:
    """write_parquet_atomic safely writes and validates readback."""
    df = pd.DataFrame(
        {
            "SK_ID_CURR": [101, 102],
            "TEST_COUNT": [1, 2],
            "TEST_VAL": [10.5, 20.5],
        }
    )
    target = tmp_path / "test_output.parquet"
    meta = write_parquet_atomic(df, target, prefix="TEST_")

    assert target.exists()
    assert meta["row_count"] == 2
    assert meta["column_count"] == 3
    assert meta["unique_customer_count"] == 2

    # Read back independently
    read_df = pd.read_parquet(target)
    assert len(read_df) == 2
    assert list(read_df.columns) == ["SK_ID_CURR", "TEST_COUNT", "TEST_VAL"]
