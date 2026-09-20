"""Comprehensive unit tests for canonical dataset build pipeline in src.data.build_pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.aggregate import AGGREGATE_FEATURE_DEFINITIONS
from src.data.build_pipeline import (
    APPLICATION_DERIVED_ORDER,
    BOUNDED_RATE_COLUMNS,
    MINIMUM_CONTRACT_COLUMNS,
    UNMATCHED_ZERO_COUNT_COLUMNS,
    join_customer_aggregates,
    validate_canonical_dataset,
    write_canonical_dataset_atomic,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_application_df() -> pd.DataFrame:
    """Fixture providing a minimal valid application DataFrame with contract columns."""
    return pd.DataFrame(
        {
            "SK_ID_CURR": [100003, 100001, 100002],  # Unsorted initially to test sorting
            "TARGET": [0, 1, 0],
            "CODE_GENDER": ["M", "F", "F"],
            "NAME_CONTRACT_TYPE": ["Cash loans", "Revolving loans", "Cash loans"],
            "AMT_INCOME_TOTAL": [150000.0, 200000.0, 100000.0],
            "AMT_CREDIT": [300000.0, 400000.0, 200000.0],
            "AMT_ANNUITY": [15000.0, 20000.0, 10000.0],
            "AMT_GOODS_PRICE": [250000.0, 350000.0, 180000.0],
            "DAYS_EMPLOYED_ANOM": [0, 0, 1],
            "AGE_YEARS": [35.0, 28.0, 45.0],
            "AGE_GROUP": ["35-44", "25-34", "45-54"],
            "EMPLOYED_YEARS": [5.0, 3.0, np.nan],
            "CREDIT_TO_INCOME_RATIO": [2.0, 2.0, 2.0],
            "ANNUITY_TO_INCOME_RATIO": [0.1, 0.1, 0.1],
            "CREDIT_TO_ANNUITY_RATIO": [20.0, 20.0, 20.0],
        }
    )


@pytest.fixture
def complete_synthetic_aggregates() -> dict[str, pd.DataFrame]:
    """Fixture providing all 74 features across the 5 historical aggregates for customers 100001 & 100002.

    Customer 100003 is intentionally UNMATCHED in all aggregates.
    Customer 999999 is intentionally AGGREGATE-ONLY (must not enter canonical).
    """
    aggs: dict[str, pd.DataFrame] = {}

    # 1. BUREAU (20 features)
    bureau_features = [f for f in AGGREGATE_FEATURE_DEFINITIONS if f.startswith("BUREAU_")]
    b_data: dict[str, list[Any]] = {
        "SK_ID_CURR": [100001, 100002, 999999],
    }
    for f in bureau_features:
        if f.endswith("_COUNT"):
            b_data[f] = [2, 1, 5]
        elif f.endswith("_RATE"):
            b_data[f] = [0.5, 0.0, 0.2]
        else:
            b_data[f] = [100.0, 200.0, 500.0]
    aggs["bureau"] = pd.DataFrame(b_data)

    # 2. PREV (15 features)
    prev_features = [f for f in AGGREGATE_FEATURE_DEFINITIONS if f.startswith("PREV_")]
    p_data: dict[str, list[Any]] = {
        "SK_ID_CURR": [100001, 100002, 999999],
    }
    for f in prev_features:
        if f.endswith("_COUNT"):
            p_data[f] = [1, 2, 3]
        elif f.endswith("_RATE"):
            p_data[f] = [1.0, 0.5, 0.33]
        else:
            p_data[f] = [50000.0, 75000.0, 100000.0]
    aggs["previous_application"] = pd.DataFrame(p_data)

    # 3. INSTAL (10 features)
    instal_features = [f for f in AGGREGATE_FEATURE_DEFINITIONS if f.startswith("INSTAL_")]
    i_data: dict[str, list[Any]] = {
        "SK_ID_CURR": [100001, 100002, 999999],
    }
    for f in instal_features:
        if f.endswith("_COUNT"):
            i_data[f] = [5, 10, 20]
        elif f.endswith("_RATE"):
            i_data[f] = [0.2, 0.1, 0.0]
        else:
            i_data[f] = [10.0, 5.0, 0.0]
    aggs["installments_payments"] = pd.DataFrame(i_data)

    # 4. POS (11 features)
    pos_features = [f for f in AGGREGATE_FEATURE_DEFINITIONS if f.startswith("POS_")]
    pos_data: dict[str, list[Any]] = {
        "SK_ID_CURR": [100001, 100002, 999999],
    }
    for f in pos_features:
        if f.endswith("_COUNT"):
            pos_data[f] = [4, 6, 12]
        elif f.endswith("_RATE"):
            pos_data[f] = [0.0, 0.0, 0.0]
        else:
            pos_data[f] = [0.0, 2.0, 5.0]
    aggs["pos_cash_balance"] = pd.DataFrame(pos_data)

    # 5. CC (18 features)
    cc_features = [f for f in AGGREGATE_FEATURE_DEFINITIONS if f.startswith("CC_")]
    cc_data: dict[str, list[Any]] = {
        "SK_ID_CURR": [100001, 100002, 999999],
    }
    for f in cc_features:
        if f.endswith("_COUNT"):
            cc_data[f] = [1, 2, 4]
        elif f.endswith("_RATE"):
            cc_data[f] = [0.0, 0.0, 0.0]
        else:
            cc_data[f] = [1000.0, 2000.0, 5000.0]
    aggs["credit_card_balance"] = pd.DataFrame(cc_data)

    return aggs


# ---------------------------------------------------------------------------
# 16.1 Join Integrity Tests
# ---------------------------------------------------------------------------


def test_join_customer_aggregates_preserves_application_rows(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """All application rows and IDs are preserved exactly without multiplication."""
    joined, audit = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    assert len(joined) == len(minimal_application_df)
    assert set(joined["SK_ID_CURR"]) == set(minimal_application_df["SK_ID_CURR"])
    # 999999 must NOT enter
    assert 999999 not in joined["SK_ID_CURR"].values


def test_join_customer_aggregates_immutability(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Input DataFrames are not modified."""
    app_copy = minimal_application_df.copy(deep=True)
    agg_copies = {k: v.copy(deep=True) for k, v in complete_synthetic_aggregates.items()}

    join_customer_aggregates(minimal_application_df, complete_synthetic_aggregates)

    pd.testing.assert_frame_equal(minimal_application_df, app_copy)
    for k in complete_synthetic_aggregates:
        pd.testing.assert_frame_equal(complete_synthetic_aggregates[k], agg_copies[k])


def test_join_rejects_duplicate_aggregate_keys(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Duplicate keys in aggregate DataFrame raise ValueError (one_to_one validation)."""
    bad_aggs = dict(complete_synthetic_aggregates)
    bureau_dup = bad_aggs["bureau"].copy()
    bureau_dup = pd.concat([bureau_dup, bureau_dup.iloc[[0]]], ignore_index=True)
    bad_aggs["bureau"] = bureau_dup

    with pytest.raises(ValueError, match="duplicate SK_ID_CURR"):
        join_customer_aggregates(minimal_application_df, bad_aggs)


def test_join_rejects_null_aggregate_keys(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Null keys in aggregate DataFrame raise ValueError."""
    bad_aggs = dict(complete_synthetic_aggregates)
    bureau_null = bad_aggs["bureau"].copy()
    bureau_null.loc[0, "SK_ID_CURR"] = np.nan
    bad_aggs["bureau"] = bureau_null

    with pytest.raises(ValueError, match="null SK_ID_CURR"):
        join_customer_aggregates(minimal_application_df, bad_aggs)


# ---------------------------------------------------------------------------
# 16.2 Target Integrity Tests
# ---------------------------------------------------------------------------


def test_target_preserved_by_customer_id(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """TARGET values remain byte-for-byte identical by SK_ID_CURR."""
    orig_target_map = dict(zip(minimal_application_df["SK_ID_CURR"], minimal_application_df["TARGET"]))
    joined, _ = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    for cid, target_val in orig_target_map.items():
        act_target = joined.loc[joined["SK_ID_CURR"] == cid, "TARGET"].iloc[0]
        assert act_target == target_val


def test_aggregate_containing_target_rejected(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Aggregate containing TARGET column raises ValueError (target leakage)."""
    bad_aggs = dict(complete_synthetic_aggregates)
    bureau_target = bad_aggs["bureau"].copy()
    bureau_target["TARGET"] = 0
    bad_aggs["bureau"] = bureau_target

    with pytest.raises(ValueError, match="Target leakage"):
        join_customer_aggregates(minimal_application_df, bad_aggs)


def test_missing_or_non_binary_target_rejected(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Application frame with missing or non-binary TARGET raises ValueError."""
    no_target = minimal_application_df.drop(columns=["TARGET"])
    with pytest.raises(ValueError, match="missing required label 'TARGET'"):
        join_customer_aggregates(no_target, complete_synthetic_aggregates)

    bad_target = minimal_application_df.copy()
    bad_target.loc[0, "TARGET"] = 2
    with pytest.raises(ValueError, match="only binary values"):
        join_customer_aggregates(bad_target, complete_synthetic_aggregates)


# ---------------------------------------------------------------------------
# 16.3 Schema Integrity Tests
# ---------------------------------------------------------------------------


def test_feature_collision_rejected(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Column name collision (other than SK_ID_CURR) raises ValueError."""
    bad_aggs = dict(complete_synthetic_aggregates)
    colliding = bad_aggs["bureau"].copy()
    colliding["AMT_CREDIT"] = 100.0  # Collides with application column
    bad_aggs["bureau"] = colliding

    with pytest.raises(ValueError, match="Column collision"):
        join_customer_aggregates(minimal_application_df, bad_aggs)


def test_wrong_prefix_rejected(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Aggregate column not matching expected prefix raises ValueError."""
    bad_aggs = dict(complete_synthetic_aggregates)
    bad_prefix = bad_aggs["bureau"].copy()
    bad_prefix["WRONG_PREFIX_FEAT"] = 10.0
    bad_aggs["bureau"] = bad_prefix

    with pytest.raises(ValueError, match="does not start with expected prefix"):
        join_customer_aggregates(minimal_application_df, bad_aggs)


def test_unapproved_aggregate_feature_rejected(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Feature with valid prefix but not in AGGREGATE_FEATURE_DEFINITIONS raises ValueError."""
    bad_aggs = dict(complete_synthetic_aggregates)
    unknown_feat = bad_aggs["bureau"].copy()
    unknown_feat["BUREAU_UNKNOWN_RANDOM_FEATURE"] = 10.0
    bad_aggs["bureau"] = unknown_feat

    with pytest.raises(ValueError, match="not defined in AGGREGATE_FEATURE_DEFINITIONS"):
        join_customer_aggregates(minimal_application_df, bad_aggs)


def test_complete_synthetic_fixture_satisfies_quality_gate(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """All 74 aggregate features are present and satisfy the canonical quality gate."""
    joined, _ = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    gate = validate_canonical_dataset(
        joined,
        expected_ids=minimal_application_df["SK_ID_CURR"],
        expected_target_by_id=dict(zip(minimal_application_df["SK_ID_CURR"], minimal_application_df["TARGET"])),
    )
    assert gate["status"] == "PASSED"
    assert gate["row_count"] == 3


# ---------------------------------------------------------------------------
# 16.4 Missing-History Policy Tests
# ---------------------------------------------------------------------------


def test_missing_history_policy_fills_only_approved_counts(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Unmatched customer (100003) has approved counts filled with 0, while rates remain NaN."""
    joined, audit = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    row_100003 = joined.loc[joined["SK_ID_CURR"] == 100003].iloc[0]

    # Approved count features must be 0
    assert row_100003["BUREAU_CREDIT_COUNT"] == 0
    assert row_100003["BUREAU_ACTIVE_COUNT"] == 0
    assert row_100003["PREV_APPLICATION_COUNT"] == 0
    assert row_100003["INSTAL_INSTALLMENT_COUNT"] == 0
    assert row_100003["POS_RECORD_COUNT"] == 0
    assert row_100003["CC_RECORD_COUNT"] == 0

    # Rates and means must remain NaN (missing)
    assert pd.isna(row_100003["BUREAU_ACTIVE_RATE"])
    assert pd.isna(row_100003["BUREAU_DAYS_CREDIT_MEAN"])
    assert pd.isna(row_100003["PREV_APPROVED_RATE"])
    assert pd.isna(row_100003["INSTAL_LATE_RATE"])
    assert pd.isna(row_100003["POS_DPD_MEAN"])
    assert pd.isna(row_100003["CC_UTILIZATION_MEAN"])

    # Count columns must have integer-compatible dtype
    assert pd.api.types.is_integer_dtype(joined["BUREAU_CREDIT_COUNT"])
    assert pd.api.types.is_integer_dtype(joined["PREV_APPLICATION_COUNT"])


def test_missing_counts_in_matched_aggregate_raises(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Missing count in a matched aggregate row raises upstream integrity failure."""
    bad_aggs = dict(complete_synthetic_aggregates)
    bureau_missing_count = bad_aggs["bureau"].copy()
    bureau_missing_count.loc[0, "BUREAU_CREDIT_COUNT"] = np.nan
    bad_aggs["bureau"] = bureau_missing_count

    with pytest.raises(ValueError, match="Integrity failure: matched aggregate"):
        join_customer_aggregates(minimal_application_df, bad_aggs)


# ---------------------------------------------------------------------------
# 16.5 Audit Metrics Tests
# ---------------------------------------------------------------------------


def test_join_audit_metrics_accuracy(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Audit metrics accurately reflect matched, unmatched, and aggregate-only counts."""
    _, audit = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    bureau_audit = audit["BUREAU"]
    assert bureau_audit["application_rows_before_join"] == 3
    assert bureau_audit["application_rows_after_join"] == 3
    assert bureau_audit["matched_application_customers"] == 2  # 100001, 100002
    assert bureau_audit["unmatched_application_customers"] == 1  # 100003
    assert bureau_audit["aggregate_only_customers"] == 1  # 999999
    assert bureau_audit["row_multiplication_count"] == 0
    assert bureau_audit["target_mismatch_count"] == 0
    assert bureau_audit["coverage_rate"] == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# 16.6 Determinism Tests
# ---------------------------------------------------------------------------


def test_join_determinism_and_sorting(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Rows are sorted by SK_ID_CURR ascending, and column order is strictly deterministic."""
    joined, _ = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    # Check row sorting
    assert list(joined["SK_ID_CURR"]) == [100001, 100002, 100003]

    # Check primary column positions
    cols = list(joined.columns)
    assert cols[0] == "SK_ID_CURR"
    assert cols[1] == "TARGET"

    # All BUREAU columns appear before PREV, before INSTAL, before POS, before CC
    bureau_idx = max(cols.index(c) for c in cols if c.startswith("BUREAU_"))
    prev_idx = min(cols.index(c) for c in cols if c.startswith("PREV_"))
    assert bureau_idx < prev_idx

    prev_max_idx = max(cols.index(c) for c in cols if c.startswith("PREV_"))
    instal_min_idx = min(cols.index(c) for c in cols if c.startswith("INSTAL_"))
    assert prev_max_idx < instal_min_idx


# ---------------------------------------------------------------------------
# 16.7 Publication and Manifest Tests
# ---------------------------------------------------------------------------


def test_write_canonical_dataset_atomic(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
    tmp_path: Path,
) -> None:
    """Parquet is written atomically and can be read back and verified."""
    joined, _ = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    out_file = tmp_path / "cleaned_dataset.parquet"
    pub_meta = write_canonical_dataset_atomic(joined, out_file)

    assert out_file.exists()
    assert pub_meta["row_count"] == 3
    assert pub_meta["column_count"] == len(joined.columns)

    # Independent readback
    read_back = pd.read_parquet(out_file)
    assert len(read_back) == 3
    pd.testing.assert_frame_equal(read_back, joined)


# ---------------------------------------------------------------------------
# 16.8 Data Contract & Rate-Bound Regression Tests
# ---------------------------------------------------------------------------


def test_mandatory_data_contract_columns_presence_and_preservation(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Canonical dataset contains all required data contract columns including AGE_GROUP and EMPLOYED_YEARS."""
    joined, _ = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    for col in MINIMUM_CONTRACT_COLUMNS:
        assert col in joined.columns, f"Missing contract column {col}"

    assert "AGE_GROUP" in joined.columns
    assert "EMPLOYED_YEARS" in joined.columns
    assert "AGE_YEARS" in joined.columns
    assert "DAYS_EMPLOYED_ANOM" in joined.columns

    # Verify that missing one of them fails the quality gate
    dropped = joined.drop(columns=["AGE_GROUP"])
    with pytest.raises(ValueError, match="Missing required contract column: 'AGE_GROUP'"):
        validate_canonical_dataset(dropped)

    dropped_emp = joined.drop(columns=["EMPLOYED_YEARS"])
    with pytest.raises(ValueError, match="Missing required contract column: 'EMPLOYED_YEARS'"):
        validate_canonical_dataset(dropped_emp)


def test_exact_approved_count_feature_names() -> None:
    """Approved canonical count names are used and legacy/unapproved names are rejected."""
    expected_bureau_counts = {
        "BUREAU_CREDIT_COUNT",
        "BUREAU_ACTIVE_COUNT",
        "BUREAU_CLOSED_COUNT",
        "BUREAU_BB_MONTH_COUNT",
        "BUREAU_BB_DELINQUENT_MONTH_COUNT",
        "BUREAU_BB_SEVERE_MONTH_COUNT",
    }
    assert set(UNMATCHED_ZERO_COUNT_COLUMNS["BUREAU"]) == expected_bureau_counts
    assert "BUREAU_LOAN_COUNT" not in UNMATCHED_ZERO_COUNT_COLUMNS["BUREAU"]

    expected_cc_counts = {
        "CC_RECORD_COUNT",
        "CC_CONTRACT_COUNT",
        "CC_LATE_MONTH_COUNT",
    }
    assert set(UNMATCHED_ZERO_COUNT_COLUMNS["CC"]) == expected_cc_counts
    assert "CC_BALANCE_RECORD_COUNT" not in UNMATCHED_ZERO_COUNT_COLUMNS["CC"]
    assert "CC_DRAWING_COUNT_SUM" not in UNMATCHED_ZERO_COUNT_COLUMNS["CC"]


def test_bounded_rate_below_zero_rejected(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """A bounded rate column with value below 0 must be rejected."""
    joined, _ = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    for rate_col in BOUNDED_RATE_COLUMNS:
        bad_df = joined.copy()
        bad_df.loc[0, rate_col] = -0.05
        with pytest.raises(ValueError, match=f"Bounded rate column '{rate_col}' contains values outside"):
            validate_canonical_dataset(bad_df)


def test_bounded_rate_above_one_rejected(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """A bounded rate column with value above 1 must be rejected."""
    joined, _ = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    for rate_col in BOUNDED_RATE_COLUMNS:
        bad_df = joined.copy()
        bad_df.loc[0, rate_col] = 1.05
        with pytest.raises(ValueError, match=f"Bounded rate column '{rate_col}' contains values outside"):
            validate_canonical_dataset(bad_df)


def test_unbounded_ratios_greater_than_one_accepted(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Valid unbounded ratios (such as Debt/Income, Utilization) > 1 are accepted."""
    joined, _ = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    # Legitimate values exceeding 1.0
    joined.loc[0, "CREDIT_TO_INCOME_RATIO"] = 5.2
    joined.loc[0, "ANNUITY_TO_INCOME_RATIO"] = 1.2
    joined.loc[0, "CREDIT_TO_ANNUITY_RATIO"] = 28.5
    joined.loc[0, "PREV_CREDIT_TO_APPLICATION_RATIO_MEAN"] = 1.8
    joined.loc[0, "INSTAL_PAYMENT_RATIO_MEAN"] = 1.15
    joined.loc[0, "CC_UTILIZATION_MEAN"] = 1.5
    joined.loc[0, "CC_UTILIZATION_MAX"] = 2.4

    # Quality gate must pass without raising ValueError
    res = validate_canonical_dataset(joined)
    assert res["status"] == "PASSED"


def test_infinity_rejected_for_every_numeric_feature(
    minimal_application_df: pd.DataFrame,
    complete_synthetic_aggregates: dict[str, pd.DataFrame],
) -> None:
    """Any numeric column containing +inf or -inf is rejected."""
    joined, _ = join_customer_aggregates(
        minimal_application_df, complete_synthetic_aggregates
    )
    # Positive infinity
    bad_pos_inf = joined.copy()
    bad_pos_inf.loc[0, "CREDIT_TO_INCOME_RATIO"] = float("inf")
    with pytest.raises(ValueError, match="Infinity detected in column 'CREDIT_TO_INCOME_RATIO'"):
        validate_canonical_dataset(bad_pos_inf)

    # Negative infinity
    bad_neg_inf = joined.copy()
    bad_neg_inf.loc[0, "AMT_CREDIT"] = float("-inf")
    with pytest.raises(ValueError, match="Infinity detected in column 'AMT_CREDIT'"):
        validate_canonical_dataset(bad_neg_inf)
