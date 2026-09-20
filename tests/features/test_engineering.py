"""Tests for application-level feature engineering in src.features.engineering."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.engineering import (
    APPLICATION_FEATURE_DEFINITIONS,
    ENGINEERED_FEATURE_NAMES,
    engineer_application_features,
    safe_ratio,
    validate_feature_parity,
)


@pytest.fixture
def valid_train_df() -> pd.DataFrame:
    """Fixture providing minimal valid cleaned application_train data."""
    return pd.DataFrame(
        {
            "SK_ID_CURR": [100001, 100002, 100003, 100004],
            "TARGET": [0, 1, 0, 1],
            "DAYS_BIRTH": [-9461, -16765, -19092, -19932],  # ~25.9, 45.9, 52.3, 54.6
            "DAYS_EMPLOYED": [-637.0, -1188.0, np.nan, -3038.0],
            "DAYS_EMPLOYED_ANOM": [0, 0, 1, 0],
            "AMT_INCOME_TOTAL": [202500.0, 270000.0, 67500.0, 135000.0],
            "AMT_CREDIT": [406597.5, 1293502.5, 135000.0, 512446.5],
            "AMT_ANNUITY": [24700.5, 35698.5, 6750.0, 22608.0],
        }
    )


@pytest.fixture
def valid_test_df() -> pd.DataFrame:
    """Fixture providing minimal valid cleaned application_test data (no TARGET)."""
    return pd.DataFrame(
        {
            "SK_ID_CURR": [200001, 200002],
            "DAYS_BIRTH": [-10000, -20000],
            "DAYS_EMPLOYED": [-500.0, -1500.0],
            "DAYS_EMPLOYED_ANOM": [0, 0],
            "AMT_INCOME_TOTAL": [100000.0, 200000.0],
            "AMT_CREDIT": [200000.0, 400000.0],
            "AMT_ANNUITY": [10000.0, 20000.0],
        }
    )


def test_input_dataframe_not_mutated(valid_train_df: pd.DataFrame) -> None:
    """1. Input DataFrame must not be modified."""
    copy_df = valid_train_df.copy(deep=True)
    enriched, _ = engineer_application_features(valid_train_df, table_name="application_train")
    pd.testing.assert_frame_equal(valid_train_df, copy_df)
    assert not enriched.equals(valid_train_df)


def test_row_count_preserved(valid_train_df: pd.DataFrame) -> None:
    """2. Row count must be exactly preserved."""
    enriched, report = engineer_application_features(valid_train_df, table_name="application_train")
    assert len(enriched) == len(valid_train_df)
    assert report["input_row_count"] == len(valid_train_df)
    assert report["output_row_count"] == len(valid_train_df)


def test_row_and_id_order_preserved(valid_train_df: pd.DataFrame) -> None:
    """3. Row order and SK_ID_CURR values/order must be preserved."""
    enriched, report = engineer_application_features(valid_train_df, table_name="application_train")
    assert (enriched["SK_ID_CURR"].values == valid_train_df["SK_ID_CURR"].values).all()
    assert (enriched.index == valid_train_df.index).all()
    assert report["row_order_preserved"] is True
    assert report["id_preserved"] is True


def test_target_remains_unchanged(valid_train_df: pd.DataFrame) -> None:
    """4. TARGET column in train must be preserved unchanged."""
    enriched, _ = engineer_application_features(valid_train_df, table_name="application_train")
    assert (enriched["TARGET"].values == valid_train_df["TARGET"].values).all()


def test_all_six_required_features_added(valid_train_df: pd.DataFrame) -> None:
    """5. All six required features must be present in output."""
    enriched, report = engineer_application_features(valid_train_df, table_name="application_train")
    for feat in ENGINEERED_FEATURE_NAMES:
        assert feat in enriched.columns
    assert report["features_added"] == list(ENGINEERED_FEATURE_NAMES)


def test_no_unexpected_feature_added(valid_train_df: pd.DataFrame) -> None:
    """6. Output must contain only original columns plus the six required features."""
    enriched, _ = engineer_application_features(valid_train_df, table_name="application_train")
    expected_cols = set(valid_train_df.columns) | set(ENGINEERED_FEATURE_NAMES)
    assert set(enriched.columns) == expected_cols
    assert len(enriched.columns) == len(valid_train_df.columns) + 6


def test_missing_required_source_columns_raises(valid_train_df: pd.DataFrame) -> None:
    """7. Missing required source columns raise an actionable ValueError."""
    dropped = valid_train_df.drop(columns=["DAYS_BIRTH"])
    with pytest.raises(ValueError, match="Missing required source columns"):
        engineer_application_features(dropped, table_name="application_train")


def test_unknown_or_non_application_table_name_raises(valid_train_df: pd.DataFrame) -> None:
    """8. Table names other than application_train/test raise ValueError."""
    with pytest.raises(ValueError, match="Unknown or non-application table name"):
        engineer_application_features(valid_train_df, table_name="bureau")
    with pytest.raises(ValueError, match="Unknown or non-application table name"):
        engineer_application_features(valid_train_df, table_name="custom_table")


def test_raw_days_employed_sentinel_rejected(valid_train_df: pd.DataFrame) -> None:
    """9. Raw uncleaned DAYS_EMPLOYED == 365243 raises ValueError instructing to run DE-02."""
    raw_like = valid_train_df.copy()
    raw_like.loc[0, "DAYS_EMPLOYED"] = 365243
    with pytest.raises(ValueError, match="Raw sentinel DAYS_EMPLOYED == 365243 detected"):
        engineer_application_features(raw_like, table_name="application_train")


def test_invalid_days_employed_anom_rejected(valid_train_df: pd.DataFrame) -> None:
    """10. DAYS_EMPLOYED_ANOM with non-binary values raises ValueError."""
    bad_df = valid_train_df.copy()
    bad_df.loc[0, "DAYS_EMPLOYED_ANOM"] = 2
    with pytest.raises(ValueError, match="must contain only binary values"):
        engineer_application_features(bad_df, table_name="application_train")


def test_existing_output_feature_column_rejected(valid_train_df: pd.DataFrame) -> None:
    """11. Input already containing an engineered feature raises ValueError to prevent overwrite."""
    colliding = valid_train_df.copy()
    colliding["AGE_YEARS"] = 30.0
    with pytest.raises(ValueError, match="Engineered feature columns already exist"):
        engineer_application_features(colliding, table_name="application_train")


def test_age_years_formula_correct(valid_train_df: pd.DataFrame) -> None:
    """12. AGE_YEARS = -DAYS_BIRTH / 365.25."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "DAYS_BIRTH"] = -7305  # exactly 20 * 365.25
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert enriched.loc[0, "AGE_YEARS"] == pytest.approx(20.0)


def test_non_negative_days_birth_produces_missing_age(valid_train_df: pd.DataFrame) -> None:
    """13. Zero or positive DAYS_BIRTH produces missing age."""
    df = valid_train_df.iloc[[0, 1]].copy()
    df.loc[0, "DAYS_BIRTH"] = 0
    df.loc[1, "DAYS_BIRTH"] = 100
    enriched, report = engineer_application_features(df, table_name="application_train")
    assert pd.isna(enriched.loc[0, "AGE_YEARS"])
    assert pd.isna(enriched.loc[1, "AGE_YEARS"])
    assert report["age_invalid_source_count"] == 2


def test_age_boundary_18_and_100_validity(valid_train_df: pd.DataFrame) -> None:
    """Explicitly verify:
    1. Age exactly 18 is valid.
    2. Age below 18 is missing.
    3. Age exactly 100 is valid.
    4. Age above 100 is missing.
    """
    df = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2, 3, 4],
            "TARGET": [0, 0, 0, 0],
            "DAYS_BIRTH": [
                -18.0 * 365.25,
                -17.999 * 365.25,
                -100.0 * 365.25,
                -100.001 * 365.25,
            ],
            "DAYS_EMPLOYED": [-100.0, -100.0, -100.0, -100.0],
            "DAYS_EMPLOYED_ANOM": [0, 0, 0, 0],
            "AMT_INCOME_TOTAL": [100000.0] * 4,
            "AMT_CREDIT": [200000.0] * 4,
            "AMT_ANNUITY": [10000.0] * 4,
        }
    )
    enriched, report = engineer_application_features(df, table_name="application_train")
    # 1. Age exactly 18 is valid
    assert enriched.loc[0, "AGE_YEARS"] == pytest.approx(18.0)
    assert enriched.loc[0, "AGE_GROUP"] == "Under 25"
    # 2. Age below 18 is missing
    assert pd.isna(enriched.loc[1, "AGE_YEARS"])
    assert pd.isna(enriched.loc[1, "AGE_GROUP"])
    # 3. Age exactly 100 is valid
    assert enriched.loc[2, "AGE_YEARS"] == pytest.approx(100.0)
    assert enriched.loc[2, "AGE_GROUP"] == "65+"
    # 4. Age above 100 is missing
    assert pd.isna(enriched.loc[3, "AGE_YEARS"])
    assert pd.isna(enriched.loc[3, "AGE_GROUP"])
    # Diagnostic counts
    assert report["age_below_18_count"] == 1
    assert report["age_above_100_count"] == 1
    assert report["age_implausible_result_count"] == 2


def test_age_group_exact_cut_mapping() -> None:
    """Explicitly verify:
    5. 24.999... maps to Under 25.
    6. 25.0 maps to 25-34.
    7. 35.0 maps to 35-44.
    8. 45.0 maps to 45-54.
    9. 55.0 maps to 55-64.
    10. 65.0 maps to 65+.
    11. 100.0 maps to 65+.
    """
    ages = [18.0, 24.9999, 25.0, 34.9999, 35.0, 44.9999, 45.0, 54.9999, 55.0, 64.9999, 65.0, 100.0]
    expected = [
        "Under 25",
        "Under 25",
        "25-34",
        "25-34",
        "35-44",
        "35-44",
        "45-54",
        "45-54",
        "55-64",
        "55-64",
        "65+",
        "65+",
    ]
    df = pd.DataFrame(
        {
            "SK_ID_CURR": list(range(len(ages))),
            "TARGET": [0] * len(ages),
            "DAYS_BIRTH": [-age * 365.25 for age in ages],
            "DAYS_EMPLOYED": [-100.0] * len(ages),
            "DAYS_EMPLOYED_ANOM": [0] * len(ages),
            "AMT_INCOME_TOTAL": [100000.0] * len(ages),
            "AMT_CREDIT": [200000.0] * len(ages),
            "AMT_ANNUITY": [10000.0] * len(ages),
        }
    )
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert enriched["AGE_GROUP"].astype(str).tolist() == expected


def test_missing_age_produces_missing_age_group(valid_train_df: pd.DataFrame) -> None:
    """12. Missing age maps to missing age group."""
    df = valid_train_df.iloc[[0, 1]].copy()
    df.loc[0, "DAYS_BIRTH"] = 50  # invalid -> missing age
    df.loc[1, "DAYS_BIRTH"] = -50000  # implausible >100 -> missing age
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert pd.isna(enriched.loc[0, "AGE_YEARS"])
    assert pd.isna(enriched.loc[0, "AGE_GROUP"])
    assert pd.isna(enriched.loc[1, "AGE_YEARS"])
    assert pd.isna(enriched.loc[1, "AGE_GROUP"])


def test_age_group_categories_and_absence_of_old_labels(valid_train_df: pd.DataFrame) -> None:
    """13. Category order exactly matches the six authorized labels.
    14. Old labels '<25', '35-49', and '50-64' do not appear.
    """
    enriched, _ = engineer_application_features(valid_train_df, table_name="application_train")
    cat_type = enriched["AGE_GROUP"].dtype
    assert isinstance(cat_type, pd.CategoricalDtype)
    assert cat_type.ordered is True
    authorized_labels = [
        "Under 25",
        "25-34",
        "35-44",
        "45-54",
        "55-64",
        "65+",
    ]
    assert list(cat_type.categories) == authorized_labels

    forbidden_old_labels = ["<25", "35-49", "50-64"]
    for old_label in forbidden_old_labels:
        assert old_label not in cat_type.categories
        assert not (enriched["AGE_GROUP"].astype(str) == old_label).any()


def test_employed_years_formula_correct(valid_train_df: pd.DataFrame) -> None:
    """18. EMPLOYED_YEARS = -DAYS_EMPLOYED / 365.25."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "DAYS_EMPLOYED"] = -730.5  # exactly 2 * 365.25
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert enriched.loc[0, "EMPLOYED_YEARS"] == pytest.approx(2.0)


def test_zero_employment_days_produces_zero_years(valid_train_df: pd.DataFrame) -> None:
    """19. Zero employment days produces 0.0 years."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "DAYS_EMPLOYED"] = 0.0
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert enriched.loc[0, "EMPLOYED_YEARS"] == 0.0


def test_positive_employment_days_produce_missing_years(valid_train_df: pd.DataFrame) -> None:
    """20. Positive employment days produce missing EMPLOYED_YEARS."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "DAYS_EMPLOYED"] = 100.0
    enriched, report = engineer_application_features(df, table_name="application_train")
    assert pd.isna(enriched.loc[0, "EMPLOYED_YEARS"])
    assert report["employment_invalid_positive_count"] == 1


def test_missing_employment_days_remain_missing(valid_train_df: pd.DataFrame) -> None:
    """21. Missing DAYS_EMPLOYED produces missing EMPLOYED_YEARS."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "DAYS_EMPLOYED"] = np.nan
    df.loc[0, "DAYS_EMPLOYED_ANOM"] = 1
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert pd.isna(enriched.loc[0, "EMPLOYED_YEARS"])


def test_days_employed_anom_preserved(valid_train_df: pd.DataFrame) -> None:
    """22. DAYS_EMPLOYED_ANOM column is preserved exactly."""
    enriched, _ = engineer_application_features(valid_train_df, table_name="application_train")
    assert (enriched["DAYS_EMPLOYED_ANOM"].values == valid_train_df["DAYS_EMPLOYED_ANOM"].values).all()


def test_credit_to_income_ratio_formula(valid_train_df: pd.DataFrame) -> None:
    """23. CREDIT_TO_INCOME_RATIO = AMT_CREDIT / AMT_INCOME_TOTAL."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "AMT_CREDIT"] = 500000.0
    df.loc[0, "AMT_INCOME_TOTAL"] = 100000.0
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert enriched.loc[0, "CREDIT_TO_INCOME_RATIO"] == pytest.approx(5.0)


def test_annuity_to_income_ratio_formula(valid_train_df: pd.DataFrame) -> None:
    """24. ANNUITY_TO_INCOME_RATIO = AMT_ANNUITY / AMT_INCOME_TOTAL."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "AMT_ANNUITY"] = 25000.0
    df.loc[0, "AMT_INCOME_TOTAL"] = 100000.0
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert enriched.loc[0, "ANNUITY_TO_INCOME_RATIO"] == pytest.approx(0.25)


def test_credit_to_annuity_ratio_formula(valid_train_df: pd.DataFrame) -> None:
    """25. CREDIT_TO_ANNUITY_RATIO = AMT_CREDIT / AMT_ANNUITY."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "AMT_CREDIT"] = 300000.0
    df.loc[0, "AMT_ANNUITY"] = 15000.0
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert enriched.loc[0, "CREDIT_TO_ANNUITY_RATIO"] == pytest.approx(20.0)


def test_zero_denominator_produces_missing_not_inf(valid_train_df: pd.DataFrame) -> None:
    """26. Zero denominator produces NaN, never positive/negative infinity."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "AMT_INCOME_TOTAL"] = 0.0
    enriched, report = engineer_application_features(df, table_name="application_train")
    assert pd.isna(enriched.loc[0, "CREDIT_TO_INCOME_RATIO"])
    assert pd.isna(enriched.loc[0, "ANNUITY_TO_INCOME_RATIO"])
    assert report["per_ratio_zero_denominator_count"]["CREDIT_TO_INCOME_RATIO"] == 1


def test_missing_denominator_produces_missing(valid_train_df: pd.DataFrame) -> None:
    """27. Missing denominator produces NaN."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "AMT_ANNUITY"] = np.nan
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert pd.isna(enriched.loc[0, "ANNUITY_TO_INCOME_RATIO"])
    assert pd.isna(enriched.loc[0, "CREDIT_TO_ANNUITY_RATIO"])


def test_negative_numerator_produces_missing(valid_train_df: pd.DataFrame) -> None:
    """28. Negative numerator produces NaN."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "AMT_CREDIT"] = -100.0
    enriched, report = engineer_application_features(df, table_name="application_train")
    assert pd.isna(enriched.loc[0, "CREDIT_TO_INCOME_RATIO"])
    assert report["per_ratio_invalid_numerator_count"]["CREDIT_TO_INCOME_RATIO"] == 1


def test_infinite_inputs_produce_missing_outputs(valid_train_df: pd.DataFrame) -> None:
    """29. Positive or negative infinity inputs produce NaN output."""
    df = valid_train_df.iloc[[0, 1]].copy()
    df.loc[0, "AMT_CREDIT"] = np.inf
    df.loc[1, "AMT_INCOME_TOTAL"] = -np.inf
    enriched, _ = engineer_application_features(df, table_name="application_train")
    assert pd.isna(enriched.loc[0, "CREDIT_TO_INCOME_RATIO"])
    assert pd.isna(enriched.loc[1, "CREDIT_TO_INCOME_RATIO"])


def test_engineered_outputs_contain_no_infinity(valid_train_df: pd.DataFrame) -> None:
    """30. Engineered outputs must contain zero infinity values."""
    enriched, report = engineer_application_features(valid_train_df, table_name="application_train")
    for feat in ENGINEERED_FEATURE_NAMES:
        if pd.api.types.is_numeric_dtype(enriched[feat]):
            assert not np.isinf(enriched[feat]).any()
    assert report["infinity_count"] == 0


def test_train_requires_valid_binary_non_null_target(valid_train_df: pd.DataFrame) -> None:
    """31. Train table rejects missing TARGET, null TARGET, or non-binary TARGET."""
    no_target = valid_train_df.drop(columns=["TARGET"])
    with pytest.raises(ValueError, match="must contain 'TARGET'"):
        engineer_application_features(no_target, table_name="application_train")

    null_target = valid_train_df.copy()
    null_target.loc[0, "TARGET"] = np.nan
    with pytest.raises(ValueError, match="'TARGET' contains null values"):
        engineer_application_features(null_target, table_name="application_train")

    non_binary_target = valid_train_df.copy()
    non_binary_target.loc[0, "TARGET"] = 2
    with pytest.raises(ValueError, match="only non-null binary values"):
        engineer_application_features(non_binary_target, table_name="application_train")


def test_test_rejects_target(valid_test_df: pd.DataFrame) -> None:
    """32. Test table rejects the presence of TARGET."""
    with_target = valid_test_df.copy()
    with_target["TARGET"] = 0
    with pytest.raises(ValueError, match="must not contain 'TARGET'"):
        engineer_application_features(with_target, table_name="application_test")


def test_feature_metadata_complete() -> None:
    """33. Metadata mapping defines all six features with required keys."""
    required_fields = {
        "feature_name",
        "source_columns",
        "formula_or_rule",
        "unit",
        "business_meaning",
        "missing_behavior",
        "leakage_note",
    }
    assert set(APPLICATION_FEATURE_DEFINITIONS.keys()) == set(ENGINEERED_FEATURE_NAMES)
    for feat, meta in APPLICATION_FEATURE_DEFINITIONS.items():
        assert required_fields.issubset(set(meta.keys()))
        assert meta["feature_name"] == feat


def test_structured_report_keys_and_counts(valid_train_df: pd.DataFrame) -> None:
    """34. Structured report contains all required diagnostic fields."""
    _, report = engineer_application_features(valid_train_df, table_name="application_train")
    expected_keys = {
        "table_name",
        "input_row_count",
        "output_row_count",
        "input_column_count",
        "output_column_count",
        "features_added",
        "row_order_preserved",
        "id_preserved",
        "per_feature_missing_count",
        "per_feature_missing_percentage",
        "per_ratio_invalid_numerator_count",
        "per_ratio_invalid_denominator_count",
        "per_ratio_zero_denominator_count",
        "age_invalid_source_count",
        "age_implausible_result_count",
        "employment_invalid_positive_count",
        "employment_age_inconsistency_diagnostic_count",
        "infinity_count",
        "validation_status",
    }
    assert expected_keys.issubset(set(report.keys()))
    assert report["validation_status"] == "VALIDATED"


def test_employment_age_inconsistency_reported_not_rewritten(valid_train_df: pd.DataFrame) -> None:
    """35. EMPLOYED_YEARS > AGE_YEARS is counted in diagnostics but not modified."""
    df = valid_train_df.iloc[[0]].copy()
    df.loc[0, "DAYS_BIRTH"] = -365.25 * 20  # age 20
    df.loc[0, "DAYS_EMPLOYED"] = -365.25 * 30  # employed 30 years (> age)
    enriched, report = engineer_application_features(df, table_name="application_train")
    assert enriched.loc[0, "EMPLOYED_YEARS"] == pytest.approx(30.0)
    assert enriched.loc[0, "AGE_YEARS"] == pytest.approx(20.0)
    assert report["employment_age_inconsistency_diagnostic_count"] == 1


def test_train_test_feature_parity_validation(
    valid_train_df: pd.DataFrame, valid_test_df: pd.DataFrame
) -> None:
    """36. Feature parity between train and test (excluding TARGET) passes."""
    enriched_train, _ = engineer_application_features(valid_train_df, table_name="application_train")
    enriched_test, _ = engineer_application_features(valid_test_df, table_name="application_test")

    parity = validate_feature_parity(enriched_train, enriched_test)
    assert parity["parity_status"] == "PASS"
    assert parity["target_in_train_only"] is True


def test_safe_ratio_helper_directly() -> None:
    """Bonus unit test for safe_ratio edge cases."""
    num = pd.Series([10.0, -1.0, np.nan, 0.0, np.inf])
    den = pd.Series([2.0, 5.0, 10.0, 0.0, 1.0])
    res, diag = safe_ratio(num, den, feature_name="TEST_RATIO")

    assert res.iloc[0] == 5.0
    assert pd.isna(res.iloc[1])  # negative num
    assert pd.isna(res.iloc[2])  # NaN num
    assert pd.isna(res.iloc[3])  # zero den
    assert pd.isna(res.iloc[4])  # inf num
    assert diag["zero_denominator_count"] == 1
    assert diag["missing_output_count"] == 4
