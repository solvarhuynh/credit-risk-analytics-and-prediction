"""Unit tests for canonical Data Dictionary and Quality Report generation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.aggregate import AGGREGATE_FEATURE_DEFINITIONS
from src.data.build_pipeline import BOUNDED_RATE_COLUMNS, MINIMUM_CONTRACT_COLUMNS
from src.data.quality_report import (
    ALLOWED_FEATURE_GROUPS,
    ALLOWED_LOGICAL_TYPES,
    ALLOWED_ROLES,
    DATA_DICTIONARY_COLUMNS,
    _validate_data_dictionary,
    audit_canonical_dataset,
    build_data_dictionary,
    render_data_quality_report,
    write_data_dictionary_atomic,
    write_quality_report_atomic,
)


@pytest.fixture
def synthetic_canonical_dataset() -> pd.DataFrame:
    """Create a minimal synthetic canonical dataset covering all roles and groups."""
    n_rows = 10
    data: dict[str, list[object]] = {
        "SK_ID_CURR": list(range(100001, 100001 + n_rows)),
        "TARGET": [0, 1, 0, 0, 1, 0, 0, 0, 1, 0],
        # Application raw
        "NAME_CONTRACT_TYPE": ["Cash loans"] * 8 + ["Revolving loans"] * 2,
        "CODE_GENDER": ["M", "F"] * 5,
        "AMT_INCOME_TOTAL": [100000.0 + i * 10000.0 for i in range(n_rows)],
        "AMT_CREDIT": [200000.0 + i * 20000.0 for i in range(n_rows)],
        "AMT_ANNUITY": [10000.0 + i * 1000.0 for i in range(n_rows)],
        "AMT_GOODS_PRICE": [180000.0 + i * 18000.0 for i in range(n_rows)],
        "DAYS_BIRTH": [-10000 - i * 500 for i in range(n_rows)],
        "DAYS_EMPLOYED": [-1000 - i * 100 for i in range(n_rows)],
        # Application cleaning
        "DAYS_EMPLOYED_ANOM": [0] * n_rows,
        # Application derived
        "AGE_YEARS": [30.0 + i for i in range(n_rows)],
        "AGE_GROUP": ["25-34"] * 5 + ["35-44"] * 5,
        "EMPLOYED_YEARS": [3.0 + i * 0.5 for i in range(n_rows)],
        "CREDIT_TO_INCOME_RATIO": [2.0] * n_rows,
        "ANNUITY_TO_INCOME_RATIO": [0.1] * n_rows,
        "CREDIT_TO_ANNUITY_RATIO": [20.0] * n_rows,
    }

    # Add all 74 aggregate features
    for feat, meta in AGGREGATE_FEATURE_DEFINITIONS.items():
        if feat.endswith("_COUNT"):
            data[feat] = [i for i in range(n_rows)]
        elif feat in BOUNDED_RATE_COLUMNS:
            data[feat] = [0.1 * (i % 10) for i in range(n_rows)]
        elif "RATIO" in feat or "UTILIZATION" in feat:
            data[feat] = [1.5 + (i * 0.1) for i in range(n_rows)]  # Can exceed 1.0!
        else:
            data[feat] = [100.0 + i * 10.0 for i in range(n_rows)]

    df = pd.DataFrame(data)
    df["AGE_GROUP"] = df["AGE_GROUP"].astype("category")
    return df


@pytest.fixture
def synthetic_manifest(synthetic_canonical_dataset: pd.DataFrame) -> dict[str, object]:
    """Create a minimal synthetic manifest matching the synthetic dataset."""
    df = synthetic_canonical_dataset
    return {
        "task_id": "TV2-DE-05",
        "population": "application_train",
        "application_test_included": False,
        "base_commit": "2999510",
        "generation_timestamp_utc": "2026-09-20T09:18:06Z",
        "row_count": len(df),
        "column_count": len(df.columns),
        "feature_count": len(df.columns) - 2,
        "target_distribution": {"0": 7, "1": 3},
        "output_sha256": "mock_sha256_hash",
        "output_size_bytes": 12345,
        "join_audit": {
            "BUREAU": {
                "aggregate_input_rows": 10,
                "matched_application_customers": 10,
                "unmatched_application_customers": 0,
                "coverage_rate": 1.0,
                "aggregate_only_customers": 0,
            },
            "PREV": {
                "aggregate_input_rows": 10,
                "matched_application_customers": 10,
                "unmatched_application_customers": 0,
                "coverage_rate": 1.0,
                "aggregate_only_customers": 0,
            },
            "INSTAL": {
                "aggregate_input_rows": 10,
                "matched_application_customers": 10,
                "unmatched_application_customers": 0,
                "coverage_rate": 1.0,
                "aggregate_only_customers": 0,
            },
            "POS": {
                "aggregate_input_rows": 10,
                "matched_application_customers": 10,
                "unmatched_application_customers": 0,
                "coverage_rate": 1.0,
                "aggregate_only_customers": 0,
            },
            "CC": {
                "aggregate_input_rows": 10,
                "matched_application_customers": 10,
                "unmatched_application_customers": 0,
                "coverage_rate": 1.0,
                "aggregate_only_customers": 0,
            },
        },
    }


# ---------------------------------------------------------------------------
# 1. Dictionary Generation Tests
# ---------------------------------------------------------------------------


def test_build_data_dictionary_completeness(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Verify dictionary contains exactly one row per column and exact 22 headers."""
    df = synthetic_canonical_dataset
    dictionary = build_data_dictionary(df, manifest=synthetic_manifest)

    assert len(dictionary) == len(df.columns)
    assert list(dictionary["column_name"]) == list(df.columns)
    assert list(dictionary.columns) == list(DATA_DICTIONARY_COLUMNS)
    assert list(dictionary["position"]) == list(range(len(df.columns)))


def test_dictionary_roles_and_groups(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Verify role and feature group assignment logic."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)

    # Identifiers
    id_row = dictionary[dictionary["column_name"] == "SK_ID_CURR"].iloc[0]
    assert id_row["role"] == "identifier"
    assert id_row["feature_group"] == "identifier"
    assert "exclude from model features" in id_row["modeling_note"]

    # Target
    tgt_row = dictionary[dictionary["column_name"] == "TARGET"].iloc[0]
    assert tgt_row["role"] == "target"
    assert tgt_row["feature_group"] == "target"
    assert "never use as a predictor" in tgt_row["modeling_note"]

    # Aggregate features
    agg_rows = dictionary[dictionary["feature_group"].isin({"bureau", "previous_application", "installments", "pos_cash", "credit_card"})]
    assert len(agg_rows) == 74

    # All roles and groups are valid
    assert set(dictionary["role"]).issubset(ALLOWED_ROLES)
    assert set(dictionary["feature_group"]).issubset(ALLOWED_FEATURE_GROUPS)
    assert set(dictionary["logical_type"]).issubset(ALLOWED_LOGICAL_TYPES)


def test_dictionary_no_empty_metadata_cells(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Verify all 22 required metadata cells are populated with non-empty strings."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)

    for col in dictionary.columns:
        assert not dictionary[col].isna().any(), f"Column {col} has NaN values"
        assert not (dictionary[col].astype(str).str.strip() == "").any(), f"Column {col} has empty strings"


def test_dictionary_rate_vs_unbounded_ratio_distinction(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Verify bounded rates document [0.0, 1.0] while unbounded ratios document unbounded."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)

    # Bounded rate check
    for col in BOUNDED_RATE_COLUMNS:
        row = dictionary[dictionary["column_name"] == col].iloc[0]
        assert row["logical_type"] == "rate"
        assert row["valid_values_or_range"] == "[0.0, 1.0]"

    # Unbounded ratio check
    for col in ["CREDIT_TO_INCOME_RATIO", "ANNUITY_TO_INCOME_RATIO", "CC_UTILIZATION_MEAN"]:
        row = dictionary[dictionary["column_name"] == col].iloc[0]
        assert row["logical_type"] == "ratio"
        assert "unbounded" in row["valid_values_or_range"]
        assert row["valid_values_or_range"] != "[0.0, 1.0]"


# ---------------------------------------------------------------------------
# 2. Dictionary Quality Gate Failure Tests
# ---------------------------------------------------------------------------


def test_dictionary_rejects_column_mismatch(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Reject dictionary if row order does not match dataset column order."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)

    # Swap two rows
    swapped = dictionary.copy()
    swapped.iloc[0], swapped.iloc[1] = swapped.iloc[1].copy(), swapped.iloc[0].copy()

    with pytest.raises(ValueError, match="Data dictionary row order does not match"):
        _validate_data_dictionary(swapped, synthetic_canonical_dataset)


def test_dictionary_rejects_missing_column(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Reject dictionary if a canonical dataset column is missing."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)
    dropped = dictionary.iloc[:-1]

    with pytest.raises(ValueError, match="Dictionary row count"):
        _validate_data_dictionary(dropped, synthetic_canonical_dataset)


def test_dictionary_rejects_empty_cell(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Reject dictionary if a required metadata cell is blank."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)
    bad_dict = dictionary.copy()
    bad_dict.loc[0, "description"] = "   "

    with pytest.raises(ValueError, match="contains empty string"):
        _validate_data_dictionary(bad_dict, synthetic_canonical_dataset)


# ---------------------------------------------------------------------------
# 3. Dataset Audit Tests
# ---------------------------------------------------------------------------


def test_audit_canonical_dataset_metrics(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Audit metrics accurately reflect shape, target, and numeric properties."""
    df = synthetic_canonical_dataset
    dictionary = build_data_dictionary(df, manifest=synthetic_manifest)
    audit = audit_canonical_dataset(df, manifest=synthetic_manifest, dictionary=dictionary)

    assert audit["shape_and_grain"]["row_count"] == len(df)
    assert audit["shape_and_grain"]["column_count"] == len(df.columns)
    assert audit["shape_and_grain"]["unique_sk_id_curr"] == len(df)
    assert audit["shape_and_grain"]["null_sk_id_curr"] == 0
    assert audit["shape_and_grain"]["duplicate_sk_id_curr"] == 0
    assert audit["shape_and_grain"]["row_order_monotonic_increasing"] is True

    assert audit["target_integrity"]["class_counts"] == {0: 7, 1: 3}
    assert audit["target_integrity"]["target_null_count"] == 0
    assert audit["numeric_quality"]["positive_infinity_count"] == 0
    assert audit["numeric_quality"]["negative_infinity_count"] == 0
    assert len(audit["numeric_quality"]["bounded_rate_violations"]) == 0

    # Verify missingness bucket sum equals column count
    b_counts = audit["missingness_analysis"]["missingness_bucket_counts"]
    assert sum(b_counts.values()) == len(df.columns)


def test_missingness_bucket_exclusivity_and_boundaries() -> None:
    """Verify missingness bucket classification on all boundary values."""
    from src.data.quality_report import MISSINGNESS_BUCKETS, classify_missingness_rate

    # Boundary tests
    assert classify_missingness_rate(0.0) == "exactly 0%"
    assert classify_missingness_rate(0.0001) == "greater than 0% and less than 5%"
    assert classify_missingness_rate(0.0499) == "greater than 0% and less than 5%"
    assert classify_missingness_rate(0.05) == "greater than or equal to 5% and less than 20%"
    assert classify_missingness_rate(0.1999) == "greater than or equal to 5% and less than 20%"
    assert classify_missingness_rate(0.20) == "greater than or equal to 20% and less than 50%"
    assert classify_missingness_rate(0.4999) == "greater than or equal to 20% and less than 50%"
    assert classify_missingness_rate(0.50) == "greater than or equal to 50% and less than 80%"
    assert classify_missingness_rate(0.7999) == "greater than or equal to 50% and less than 80%"
    assert classify_missingness_rate(0.80) == "greater than or equal to 80% and less than 100%"
    assert classify_missingness_rate(0.9999) == "greater than or equal to 80% and less than 100%"
    assert classify_missingness_rate(1.0) == "exactly 100%"

    # Invalid values raise ValueError
    with pytest.raises(ValueError):
        classify_missingness_rate(-0.01)
    with pytest.raises(ValueError):
        classify_missingness_rate(1.01)


def test_constant_all_null_and_near_constant_classification(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Prove strict separation between all-null, constant, and near-constant features."""
    n = 10000
    test_df = pd.DataFrame({
        "SK_ID_CURR": list(range(1, n + 1)),
        "TARGET": [0] * (n - 100) + [1] * 100,
        "ALL_NULL_COL": [np.nan] * n,
        "CONSTANT_COL": [42.0] * n,
        "NEAR_CONST_9950": [1] * 9950 + [2] * 50,    # exactly 99.50%
        "NOT_NEAR_CONST_9949": [1] * 9949 + [2] * 51,  # 99.49% -> NOT near constant
        "DAYS_EMPLOYED_ANOM_STYLE": [0] * 8199 + [1] * 1801,  # ~81.99% -> NOT near constant
    })

    # Add required minimal columns
    for col in MINIMUM_CONTRACT_COLUMNS:
        if col not in test_df.columns:
            test_df[col] = [1.0] * n

    for feat in AGGREGATE_FEATURE_DEFINITIONS:
        if feat not in test_df.columns:
            test_df[feat] = [0] * n

    test_manifest = synthetic_manifest.copy()
    dict_df = build_data_dictionary(test_df, manifest=test_manifest)
    audit = audit_canonical_dataset(test_df, manifest=test_manifest, dictionary=dict_df)
    const = audit["constant_features"]

    # All-null: classified only as all-null
    assert "ALL_NULL_COL" in const["all_null_columns"]
    assert "ALL_NULL_COL" not in const["constant_columns"]
    assert "ALL_NULL_COL" not in [c["column_name"] for c in const["near_constant_columns"]]

    # Constant: classified only as constant
    assert "CONSTANT_COL" in const["constant_columns"]
    assert "CONSTANT_COL" not in const["all_null_columns"]
    assert "CONSTANT_COL" not in [c["column_name"] for c in const["near_constant_columns"]]

    # 99.50% threshold behavior
    nc_names = [c["column_name"] for c in const["near_constant_columns"]]
    assert "NEAR_CONST_9950" in nc_names
    assert "NOT_NEAR_CONST_9949" not in nc_names

    # 81.99% majority flag is NOT near-constant
    assert "DAYS_EMPLOYED_ANOM_STYLE" not in nc_names


# ---------------------------------------------------------------------------
# 4. Report Rendering Tests
# ---------------------------------------------------------------------------


def test_render_data_quality_report_sections(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Rendered markdown report contains all 19 required sections and no unauthorized roles."""
    df = synthetic_canonical_dataset
    dictionary = build_data_dictionary(df, manifest=synthetic_manifest)
    audit = audit_canonical_dataset(df, manifest=synthetic_manifest, dictionary=dictionary)
    report = render_data_quality_report(audit, dictionary)

    # 1. Exact 19 sections
    for i in range(1, 20):
        assert f"## {i}. " in report, f"Missing section {i} in quality report"

    # 2. TV1 Modeling & TV3 Dashboard handoff notes exist
    assert "## 16. TV1 modeling handoff notes" in report
    assert "## 17. TV3 dashboard handoff notes" in report

    # 3. No unauthorized team role reference
    unauthorized_role = "TV" + "4"
    assert unauthorized_role not in report

    # 4. No DE-07 analysis in DE-06 report
    forbidden_target = "target" + "_correlation"
    forbidden_multi = "multi" + "collinearity"
    forbidden_biv = "bi" + "variate feature ranking"
    forbidden_prs = "Pear" + "son"
    assert forbidden_target not in report
    assert forbidden_multi not in report.lower()
    assert forbidden_biv not in report.lower()
    assert forbidden_prs not in report


# ---------------------------------------------------------------------------
# 5. Atomic Publication Tests
# ---------------------------------------------------------------------------


def test_atomic_publication_data_dictionary(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
    tmp_path: Path,
) -> None:
    """Data Dictionary is written with UTF-8 BOM, LF, and passes readback validation."""
    df = synthetic_canonical_dataset
    dictionary = build_data_dictionary(df, manifest=synthetic_manifest)
    dest_csv = tmp_path / "data_dictionary.csv"

    meta = write_data_dictionary_atomic(dictionary, dest_csv)
    assert dest_csv.is_file()
    assert meta["row_count"] == len(dictionary)
    assert meta["column_count"] == len(dictionary.columns)

    # Read binary header to verify UTF-8 BOM (EF BB BF)
    with open(dest_csv, "rb") as f:
        header = f.read(3)
        assert header == b"\xef\xbb\xbf", "Missing UTF-8 BOM"

    # Verify LF line endings (no CR in file)
    with open(dest_csv, "rb") as f:
        raw_bytes = f.read()
        assert b"\r\n" not in raw_bytes, "Found CRLF instead of LF line endings"


def test_atomic_publication_quality_report(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
    tmp_path: Path,
) -> None:
    """Quality report is written atomically and read back accurately."""
    df = synthetic_canonical_dataset
    dictionary = build_data_dictionary(df, manifest=synthetic_manifest)
    audit = audit_canonical_dataset(df, manifest=synthetic_manifest, dictionary=dictionary)
    report = render_data_quality_report(audit, dictionary)

    dest_md = tmp_path / "data_quality_report.md"
    meta = write_quality_report_atomic(report, dest_md)

    assert dest_md.is_file()
    assert meta["section_count"] == 19

    # Verify LF line endings
    with open(dest_md, "rb") as f:
        raw_bytes = f.read()
        assert b"\r\n" not in raw_bytes, "Found CRLF instead of LF in report"


# ---------------------------------------------------------------------------
# 6. Specific Audit & Contract Tests
# ---------------------------------------------------------------------------


def test_days_employed_anom_metadata_no_retirement_claim(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Verify DAYS_EMPLOYED_ANOM metadata has exact required strings and no retirement claims."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)
    row = dictionary[dictionary["column_name"] == "DAYS_EMPLOYED_ANOM"].iloc[0]

    assert row["description"] == (
        "Binary indicator that the raw DAYS_EMPLOYED value equaled the anomalous sentinel 365243."
    )
    assert row["missing_value_meaning"] == (
        "Never missing; 1 means the sentinel was detected and DAYS_EMPLOYED was replaced by missing, "
        "while 0 means the sentinel was not detected."
    )
    assert row["as_of_time_rule"] == (
        "Derived only from DAYS_EMPLOYED observed in the application record at decision time."
    )
    assert row["leakage_note"] == (
        "Row-local application-time transformation; does not use TARGET or post-application outcomes."
    )
    assert row["modeling_note"] == (
        "Binary data-quality and anomaly indicator; do not interpret it as confirmed retirement or unemployment status."
    )

    # Ensure no claim that the flag directly identifies pensioners, retired customers, or unemployment
    combined_text = " ".join([
        str(row["description"]),
        str(row["missing_value_meaning"]),
        str(row["as_of_time_rule"]),
        str(row["leakage_note"]),
    ]).lower()
    assert "pension" not in combined_text
    assert "retire" not in combined_text
    assert "unemploy" not in combined_text


def test_bureau_bb_delinquent_month_rate_metadata(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Verify BUREAU_BB_DELINQUENT_MONTH_RATE metadata meets exact contract specification."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)
    row = dictionary[dictionary["column_name"] == "BUREAU_BB_DELINQUENT_MONTH_RATE"].iloc[0]

    assert row["source_table"] == "bureau, bureau_balance"
    assert row["source_columns"] == "SK_ID_CURR | SK_ID_BUREAU | STATUS | MONTHS_BALANCE"
    assert row["source_grain"] == "monthly bureau balance per SK_ID_BUREAU"
    assert row["canonical_grain"] == "customer (SK_ID_CURR)"
    assert row["transformation_formula"] == (
        "sum(delinquent months with STATUS in {1,2,3,4,5}) / sum(observed bureau-balance months), "
        "weighted across the customer's bureau loans"
    )
    assert row["as_of_time_rule"] == (
        "Uses only bureau records with DAYS_CREDIT <= 0 and bureau-balance records with MONTHS_BALANCE <= 0."
    )
    assert "no mapped observed bureau-balance months" in row["missing_value_meaning"]
    assert "zero delinquent months produces rate 0" in row["missing_value_meaning"]


def test_all_aggregate_rows_have_non_key_source_operands(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Verify all 74 aggregate rows have actual raw operand columns, not just SK_ID_CURR."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)

    for col in AGGREGATE_FEATURE_DEFINITIONS:
        row = dictionary[dictionary["column_name"] == col].iloc[0]
        src_cols = [c.strip() for c in row["source_columns"].split("|")]
        assert "SK_ID_CURR" in src_cols, f"{col} missing SK_ID_CURR in source_columns"
        assert len(src_cols) >= 2, f"{col} has no non-key operand columns in source_columns"


def test_every_aggregate_as_of_time_rule_contains_correct_temporal_constraint(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Verify every aggregate as_of_time_rule contains the required temporal constraint."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)

    for col in AGGREGATE_FEATURE_DEFINITIONS:
        row = dictionary[dictionary["column_name"] == col].iloc[0]
        rule = row["as_of_time_rule"]
        if col.startswith("BUREAU_"):
            assert "DAYS_CREDIT <= 0" in rule, f"{col} missing DAYS_CREDIT <= 0"
            assert "MONTHS_BALANCE <= 0" in rule, f"{col} missing MONTHS_BALANCE <= 0"
        elif col.startswith("PREV_"):
            assert "DAYS_DECISION <= 0." in rule, f"{col} missing DAYS_DECISION <= 0."
        elif col.startswith("INSTAL_"):
            assert "DAYS_INSTALMENT <= 0 and DAYS_ENTRY_PAYMENT <= 0." in rule, (
                f"{col} missing DAYS_INSTALMENT <= 0 and DAYS_ENTRY_PAYMENT <= 0."
            )
        elif col.startswith("POS_"):
            assert "MONTHS_BALANCE <= 0." in rule, f"{col} missing MONTHS_BALANCE <= 0."
        elif col.startswith("CC_"):
            assert "MONTHS_BALANCE <= 0." in rule, f"{col} missing MONTHS_BALANCE <= 0."


def test_missing_rate_semantics_distinguish_no_denominator_from_zero_rate(
    synthetic_canonical_dataset: pd.DataFrame,
    synthetic_manifest: dict[str, object],
) -> None:
    """Verify all bounded rate features distinguish no observed denominator from observed zero rate."""
    dictionary = build_data_dictionary(synthetic_canonical_dataset, manifest=synthetic_manifest)

    for col in BOUNDED_RATE_COLUMNS:
        row = dictionary[dictionary["column_name"] == col].iloc[0]
        meaning = row["missing_value_meaning"].lower()
        has_denom = ("no denominator" in meaning) or ("no observed" in meaning) or ("no mapped" in meaning)
        has_zero = ("0" in meaning) or ("zero" in meaning)
        assert has_denom, f"{col} does not distinguish missing denominator"
        assert has_zero, f"{col} does not distinguish observed zero rate"
