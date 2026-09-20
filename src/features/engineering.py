"""Canonical application-level feature engineering module.

Derives deterministic, row-local, leakage-safe features for application_train
and application_test:
- AGE_YEARS
- AGE_GROUP
- EMPLOYED_YEARS
- CREDIT_TO_INCOME_RATIO
- ANNUITY_TO_INCOME_RATIO
- CREDIT_TO_ANNUITY_RATIO
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.cleaning import clean_table
from src.data.load_data import default_raw_dir, validate_raw_files

ENGINEERED_FEATURE_NAMES: tuple[str, ...] = (
    "AGE_YEARS",
    "AGE_GROUP",
    "EMPLOYED_YEARS",
    "CREDIT_TO_INCOME_RATIO",
    "ANNUITY_TO_INCOME_RATIO",
    "CREDIT_TO_ANNUITY_RATIO",
)

REQUIRED_SOURCE_COLUMNS: tuple[str, ...] = (
    "SK_ID_CURR",
    "DAYS_BIRTH",
    "DAYS_EMPLOYED",
    "DAYS_EMPLOYED_ANOM",
    "AMT_INCOME_TOTAL",
    "AMT_CREDIT",
    "AMT_ANNUITY",
)

AGE_GROUP_BINS: list[float] = [18.0, 25.0, 35.0, 45.0, 55.0, 65.0, 101.0]
AGE_GROUP_LABELS: list[str] = [
    "Under 25",
    "25-34",
    "35-44",
    "45-54",
    "55-64",
    "65+",
]

APPLICATION_FEATURE_DEFINITIONS: dict[str, dict[str, str]] = {
    "AGE_YEARS": {
        "feature_name": "AGE_YEARS",
        "source_columns": "DAYS_BIRTH",
        "formula_or_rule": "-DAYS_BIRTH / 365.25",
        "unit": "years",
        "business_meaning": "Client age in continuous years at application time",
        "missing_behavior": "Missing if DAYS_BIRTH is non-negative, non-finite, missing, or age outside [18, 100]",
        "leakage_note": "Row-local as-of application time; no future or target leakage",
    },
    "AGE_GROUP": {
        "feature_name": "AGE_GROUP",
        "source_columns": "AGE_YEARS",
        "formula_or_rule": "Categorical bins: [18, 25) -> 'Under 25', [25, 35) -> '25-34', [35, 45) -> '35-44', [45, 55) -> '45-54', [55, 65) -> '55-64', [65, 101) -> '65+'",
        "unit": "category (ordered)",
        "business_meaning": "Policy age demographic bracket",
        "missing_behavior": "Missing if AGE_YEARS is missing",
        "leakage_note": "Fixed policy intervals; not learned from data or target",
    },
    "EMPLOYED_YEARS": {
        "feature_name": "EMPLOYED_YEARS",
        "source_columns": "DAYS_EMPLOYED",
        "formula_or_rule": "-DAYS_EMPLOYED / 365.25",
        "unit": "years",
        "business_meaning": "Client employment tenure in continuous years at application time",
        "missing_behavior": "Missing if DAYS_EMPLOYED was 365243 sentinel, missing, non-finite, or positive",
        "leakage_note": "Row-local as-of application time; anomaly flag DAYS_EMPLOYED_ANOM preserved separately",
    },
    "CREDIT_TO_INCOME_RATIO": {
        "feature_name": "CREDIT_TO_INCOME_RATIO",
        "source_columns": "AMT_CREDIT, AMT_INCOME_TOTAL",
        "formula_or_rule": "AMT_CREDIT / AMT_INCOME_TOTAL",
        "unit": "ratio (multiple)",
        "business_meaning": "Credit amount as a multiple of total client income (canonical Debt/Credit-to-Income)",
        "missing_behavior": "Missing if AMT_CREDIT < 0 or AMT_INCOME_TOTAL <= 0, missing, non-finite, or zero denominator",
        "leakage_note": "Row-local as-of application time; division by zero produces NaN, not infinity",
    },
    "ANNUITY_TO_INCOME_RATIO": {
        "feature_name": "ANNUITY_TO_INCOME_RATIO",
        "source_columns": "AMT_ANNUITY, AMT_INCOME_TOTAL",
        "formula_or_rule": "AMT_ANNUITY / AMT_INCOME_TOTAL",
        "unit": "ratio (multiple)",
        "business_meaning": "Annual loan annuity payment as a fraction of total income (Payment Burden)",
        "missing_behavior": "Missing if AMT_ANNUITY < 0 or AMT_INCOME_TOTAL <= 0, missing, non-finite, or zero denominator",
        "leakage_note": "Row-local as-of application time; division by zero produces NaN, not infinity",
    },
    "CREDIT_TO_ANNUITY_RATIO": {
        "feature_name": "CREDIT_TO_ANNUITY_RATIO",
        "source_columns": "AMT_CREDIT, AMT_ANNUITY",
        "formula_or_rule": "AMT_CREDIT / AMT_ANNUITY",
        "unit": "ratio (approximate installments/duration)",
        "business_meaning": "Loan credit amount relative to payment annuity (Proxy for loan duration/term)",
        "missing_behavior": "Missing if AMT_CREDIT < 0 or AMT_ANNUITY <= 0, missing, non-finite, or zero denominator",
        "leakage_note": "Row-local as-of application time; division by zero produces NaN, not infinity",
    },
}


def safe_ratio(
    numerator: pd.Series,
    denominator: pd.Series,
    *,
    feature_name: str,
) -> tuple[pd.Series, dict[str, int]]:
    """Compute element-wise ratio safely without division by zero or infinity.

    Args:
        numerator: Series of numerator values (must be >= 0).
        denominator: Series of denominator values (must be > 0).
        feature_name: Name of the resulting Series.

    Returns:
        Tuple of (ratio_series, diagnostic_dict).
    """
    valid_num = pd.to_numeric(numerator, errors="coerce")
    valid_den = pd.to_numeric(denominator, errors="coerce")

    mask_num_valid = valid_num.notna() & np.isfinite(valid_num) & (valid_num >= 0)
    mask_den_valid = valid_den.notna() & np.isfinite(valid_den) & (valid_den > 0)
    mask_den_zero = valid_den.notna() & (valid_den == 0)

    valid_pair = mask_num_valid & mask_den_valid

    result = pd.Series(np.nan, index=numerator.index, dtype="float64", name=feature_name)
    result.loc[valid_pair] = valid_num.loc[valid_pair] / valid_den.loc[valid_pair]

    diag = {
        "invalid_numerator_count": int((~mask_num_valid).sum()),
        "invalid_denominator_count": int((~mask_den_valid).sum()),
        "zero_denominator_count": int(mask_den_zero.sum()),
        "missing_output_count": int(result.isna().sum()),
    }
    return result, diag


def engineer_application_features(
    frame: pd.DataFrame,
    *,
    table_name: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Derive canonical application-level features deterministically and safely.

    Args:
        frame: Cleaned application DataFrame (output of clean_table).
        table_name: Exactly 'application_train' or 'application_test'.

    Returns:
        Tuple of (enriched_df, feature_report).

    Raises:
        ValueError: If inputs violate contracts or required columns are missing.
    """
    if table_name not in ("application_train", "application_test"):
        raise ValueError(
            f"Unknown or non-application table name: '{table_name}'. "
            "Expected 'application_train' or 'application_test'."
        )

    # 1. Validate required source columns
    missing_cols = [col for col in REQUIRED_SOURCE_COLUMNS if col not in frame.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required source columns in {table_name}: {missing_cols}. "
            f"Expected all of: {list(REQUIRED_SOURCE_COLUMNS)}"
        )

    # 2. Check collision with existing engineered columns
    existing_cols = [col for col in ENGINEERED_FEATURE_NAMES if col in frame.columns]
    if existing_cols:
        raise ValueError(
            f"Engineered feature columns already exist in {table_name}: {existing_cols}. "
            "Aborting to prevent accidental overwrite."
        )

    # 3. Validate primary key
    if frame["SK_ID_CURR"].isna().any():
        raise ValueError(f"{table_name} 'SK_ID_CURR' contains null values.")
    if frame["SK_ID_CURR"].duplicated().any():
        raise ValueError(f"{table_name} 'SK_ID_CURR' contains duplicate values.")

    # 4. Validate DE-02 preconditions (sentinels cleaned, anomaly flag exists)
    if (frame["DAYS_EMPLOYED"] == 365243).any():
        raise ValueError(
            f"Raw sentinel DAYS_EMPLOYED == 365243 detected in {table_name}. "
            "Please run DE-02 cleaning (clean_table) before feature engineering."
        )
    anom_vals = set(frame["DAYS_EMPLOYED_ANOM"].dropna().unique())
    if not anom_vals.issubset({0, 1}):
        raise ValueError(
            f"{table_name} 'DAYS_EMPLOYED_ANOM' must contain only binary values {{0, 1}}, found: {anom_vals}"
        )

    # 5. Validate TARGET contract
    if table_name == "application_train":
        if "TARGET" not in frame.columns:
            raise ValueError("application_train must contain 'TARGET' column.")
        target_series = frame["TARGET"]
        if target_series.isna().any():
            raise ValueError("application_train 'TARGET' contains null values.")
        if not set(target_series.unique()).issubset({0, 1}):
            raise ValueError(
                "application_train 'TARGET' must contain only non-null binary values {0, 1}."
            )
    else:  # application_test
        if "TARGET" in frame.columns:
            raise ValueError("application_test must not contain 'TARGET' column.")

    # 6. Never mutate caller DataFrame
    df = frame.copy(deep=True)
    input_row_count = len(frame)
    input_col_count = len(frame.columns)

    # 7. Compute AGE_YEARS
    birth_num = pd.to_numeric(df["DAYS_BIRTH"], errors="coerce")
    valid_source_age = birth_num.notna() & np.isfinite(birth_num) & (birth_num < 0)
    age_invalid_source_count = int((~valid_source_age).sum())

    raw_age = pd.Series(np.nan, index=df.index, dtype="float64")
    raw_age.loc[valid_source_age] = -birth_num.loc[valid_source_age] / 365.25

    plausible_age_mask = (raw_age >= 18.0) & (raw_age <= 100.0)
    age_below_18_count = int((valid_source_age & (raw_age < 18.0)).sum())
    age_above_100_count = int((valid_source_age & (raw_age > 100.0)).sum())
    age_implausible_result_count = age_below_18_count + age_above_100_count

    age_years = pd.Series(np.nan, index=df.index, dtype="float64", name="AGE_YEARS")
    valid_age_mask = valid_source_age & plausible_age_mask
    age_years.loc[valid_age_mask] = raw_age.loc[valid_age_mask]
    df["AGE_YEARS"] = age_years

    # 8. Compute AGE_GROUP
    age_group = pd.cut(
        df["AGE_YEARS"],
        bins=AGE_GROUP_BINS,
        labels=AGE_GROUP_LABELS,
        right=False,
        ordered=True,
    )
    df["AGE_GROUP"] = age_group

    # 9. Compute EMPLOYED_YEARS
    emp_num = pd.to_numeric(df["DAYS_EMPLOYED"], errors="coerce")
    valid_source_emp = emp_num.notna() & np.isfinite(emp_num) & (emp_num <= 0)
    employment_invalid_positive_count = int((emp_num.notna() & (emp_num > 0)).sum())

    employed_years = pd.Series(np.nan, index=df.index, dtype="float64", name="EMPLOYED_YEARS")
    employed_years.loc[valid_source_emp] = -emp_num.loc[valid_source_emp] / 365.25
    df["EMPLOYED_YEARS"] = employed_years

    # Inconsistency diagnostic count: employed > age
    inconsistency_mask = (
        df["EMPLOYED_YEARS"].notna()
        & df["AGE_YEARS"].notna()
        & (df["EMPLOYED_YEARS"] > df["AGE_YEARS"])
    )
    employment_age_inconsistency_diagnostic_count = int(inconsistency_mask.sum())

    # 10. Compute Safe Ratios
    credit_to_income, diag_credit_income = safe_ratio(
        df["AMT_CREDIT"],
        df["AMT_INCOME_TOTAL"],
        feature_name="CREDIT_TO_INCOME_RATIO",
    )
    df["CREDIT_TO_INCOME_RATIO"] = credit_to_income

    annuity_to_income, diag_annuity_income = safe_ratio(
        df["AMT_ANNUITY"],
        df["AMT_INCOME_TOTAL"],
        feature_name="ANNUITY_TO_INCOME_RATIO",
    )
    df["ANNUITY_TO_INCOME_RATIO"] = annuity_to_income

    credit_to_annuity, diag_credit_annuity = safe_ratio(
        df["AMT_CREDIT"],
        df["AMT_ANNUITY"],
        feature_name="CREDIT_TO_ANNUITY_RATIO",
    )
    df["CREDIT_TO_ANNUITY_RATIO"] = credit_to_annuity

    # 11. Check absence of infinity in engineered outputs
    infinity_count = 0
    for col in ENGINEERED_FEATURE_NAMES:
        if pd.api.types.is_numeric_dtype(df[col]):
            infinity_count += int(np.isinf(df[col]).sum())

    # 12. Check row & ID preservation
    row_order_preserved = bool((df.index == frame.index).all())
    id_preserved = bool((df["SK_ID_CURR"].values == frame["SK_ID_CURR"].values).all())

    # 13. Summarize missingness in added features
    per_feature_missing_count: dict[str, int] = {}
    per_feature_missing_pct: dict[str, float] = {}
    for col in ENGINEERED_FEATURE_NAMES:
        m_count = int(df[col].isna().sum())
        per_feature_missing_count[col] = m_count
        per_feature_missing_pct[col] = (
            round((m_count / input_row_count) * 100.0, 4) if input_row_count > 0 else 0.0
        )

    report: dict[str, Any] = {
        "table_name": table_name,
        "input_row_count": input_row_count,
        "output_row_count": len(df),
        "input_column_count": input_col_count,
        "output_column_count": len(df.columns),
        "features_added": list(ENGINEERED_FEATURE_NAMES),
        "row_order_preserved": row_order_preserved,
        "id_preserved": id_preserved,
        "per_feature_missing_count": per_feature_missing_count,
        "per_feature_missing_percentage": per_feature_missing_pct,
        "per_ratio_invalid_numerator_count": {
            "CREDIT_TO_INCOME_RATIO": diag_credit_income["invalid_numerator_count"],
            "ANNUITY_TO_INCOME_RATIO": diag_annuity_income["invalid_numerator_count"],
            "CREDIT_TO_ANNUITY_RATIO": diag_credit_annuity["invalid_numerator_count"],
        },
        "per_ratio_invalid_denominator_count": {
            "CREDIT_TO_INCOME_RATIO": diag_credit_income["invalid_denominator_count"],
            "ANNUITY_TO_INCOME_RATIO": diag_annuity_income["invalid_denominator_count"],
            "CREDIT_TO_ANNUITY_RATIO": diag_credit_annuity["invalid_denominator_count"],
        },
        "per_ratio_zero_denominator_count": {
            "CREDIT_TO_INCOME_RATIO": diag_credit_income["zero_denominator_count"],
            "ANNUITY_TO_INCOME_RATIO": diag_annuity_income["zero_denominator_count"],
            "CREDIT_TO_ANNUITY_RATIO": diag_credit_annuity["zero_denominator_count"],
        },
        "age_invalid_source_count": age_invalid_source_count,
        "age_implausible_result_count": age_implausible_result_count,
        "age_below_18_count": age_below_18_count,
        "age_above_100_count": age_above_100_count,
        "age_years_min": float(age_years.min()) if age_years.notna().any() else None,
        "age_years_max": float(age_years.max()) if age_years.notna().any() else None,
        "age_group_distribution": {
            str(k): int(v) for k, v in age_group.value_counts(dropna=False).items()
        },
        "employment_invalid_positive_count": employment_invalid_positive_count,
        "employment_age_inconsistency_diagnostic_count": (
            employment_age_inconsistency_diagnostic_count
        ),
        "infinity_count": infinity_count,
        "validation_status": "VALIDATED",
    }

    return df, report


def validate_feature_parity(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> dict[str, Any]:
    """Validate that train and test have identical features excluding TARGET.

    Args:
        train_df: Enriched application_train DataFrame.
        test_df: Enriched application_test DataFrame.

    Returns:
        Parity summary dict.

    Raises:
        ValueError: If feature names or types mismatch between train and test.
    """
    train_cols = [c for c in train_df.columns if c != "TARGET"]
    test_cols = list(test_df.columns)

    if set(train_cols) != set(test_cols):
        diff_train = set(train_cols) - set(test_cols)
        diff_test = set(test_cols) - set(train_cols)
        raise ValueError(
            f"Feature parity mismatch between train and test. "
            f"Columns only in train: {diff_train}, only in test: {diff_test}"
        )

    dtype_mismatches: dict[str, tuple[str, str]] = {}
    for col in train_cols:
        t_dtype = str(train_df[col].dtype)
        te_dtype = str(test_df[col].dtype)
        if t_dtype != te_dtype:
            dtype_mismatches[col] = (t_dtype, te_dtype)

    if dtype_mismatches:
        raise ValueError(
            f"Feature dtype mismatch between train and test: {dtype_mismatches}"
        )

    return {
        "parity_status": "PASS",
        "common_feature_count": len(train_cols),
        "target_in_train_only": "TARGET" in train_df.columns and "TARGET" not in test_df.columns,
    }


def audit_application_features(
    raw_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run sequential real-data audit on application_train and application_test.

    Releases memory immediately after each table inspection.

    Args:
        raw_dir: Optional directory containing raw CSV files.

    Returns:
        Structured audit report dict.
    """
    paths = validate_raw_files(raw_dir)
    results: dict[str, Any] = {}

    # 1. Process application_train
    raw_train = pd.read_csv(paths["application_train"])
    cleaned_train, _ = clean_table("application_train", raw_train)
    del raw_train

    feat_train, train_report = engineer_application_features(
        cleaned_train, table_name="application_train"
    )
    results["application_train"] = train_report
    train_cols_schema = {c: str(feat_train[c].dtype) for c in feat_train.columns if c != "TARGET"}
    del cleaned_train
    del feat_train

    # 2. Process application_test
    raw_test = pd.read_csv(paths["application_test"])
    cleaned_test, _ = clean_table("application_test", raw_test)
    del raw_test

    feat_test, test_report = engineer_application_features(
        cleaned_test, table_name="application_test"
    )
    results["application_test"] = test_report
    test_cols_schema = {c: str(feat_test[c].dtype) for c in feat_test.columns}
    del cleaned_test
    del feat_test

    # 3. Check feature parity
    if set(train_cols_schema.keys()) != set(test_cols_schema.keys()):
        diff = set(train_cols_schema.keys()) ^ set(test_cols_schema.keys())
        raise ValueError(f"Feature parity mismatch: {diff}")

    dtype_diff = {
        k: (train_cols_schema[k], test_cols_schema[k])
        for k in train_cols_schema
        if train_cols_schema[k] != test_cols_schema[k]
    }
    if dtype_diff:
        raise ValueError(f"Dtype parity mismatch: {dtype_diff}")

    results["feature_parity"] = {
        "status": "PASS",
        "total_shared_columns": len(train_cols_schema),
        "engineered_features_in_both": list(ENGINEERED_FEATURE_NAMES),
    }

    return results


if __name__ == "__main__":
    audit_results = audit_application_features()
    print(json.dumps(audit_results, indent=2, ensure_ascii=False))
