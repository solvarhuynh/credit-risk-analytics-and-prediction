"""Tests for canonical data cleaning and sentinel handling in src.data.cleaning."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data.cleaning import (
    DAYS_EMPLOYED_SENTINEL,
    PREV_APP_SENTINEL_DAY_COLUMNS,
    clean_table,
    summarize_missingness,
    validate_cleaned_table,
)


def test_input_dataframe_not_mutated() -> None:
    """1. Input DataFrame must not be mutated by clean_table."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [100001, 100002],
            "TARGET": [0, 1],
            "DAYS_EMPLOYED": [DAYS_EMPLOYED_SENTINEL, -1200],
            "NAME_CONTRACT_TYPE": ["  Cash loans ", "Revolving loans\t"],
        }
    )
    original_copy = raw_df.copy(deep=True)
    cleaned_df, _ = clean_table("application_train", raw_df)

    pd.testing.assert_frame_equal(raw_df, original_copy)
    assert not cleaned_df.equals(raw_df)


def test_days_employed_sentinel_becomes_missing() -> None:
    """2. DAYS_EMPLOYED == 365243 becomes NaN."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [100001, 100002],
            "TARGET": [0, 1],
            "DAYS_EMPLOYED": [DAYS_EMPLOYED_SENTINEL, -500],
        }
    )
    cleaned_df, report = clean_table("application_train", raw_df)

    assert pd.isna(cleaned_df.loc[0, "DAYS_EMPLOYED"])
    assert cleaned_df.loc[1, "DAYS_EMPLOYED"] == -500
    assert report["sentinel_replacements"]["DAYS_EMPLOYED"] == 1


def test_days_employed_anom_contains_binary_flags() -> None:
    """3. DAYS_EMPLOYED_ANOM is created with binary 0/1 int8."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [100001, 100002, 100003],
            "TARGET": [0, 1, 0],
            "DAYS_EMPLOYED": [DAYS_EMPLOYED_SENTINEL, -500, DAYS_EMPLOYED_SENTINEL],
        }
    )
    cleaned_df, _ = clean_table("application_train", raw_df)

    assert "DAYS_EMPLOYED_ANOM" in cleaned_df.columns
    assert cleaned_df["DAYS_EMPLOYED_ANOM"].tolist() == [1, 0, 1]
    assert cleaned_df["DAYS_EMPLOYED_ANOM"].dtype == np.int8


def test_existing_missing_days_employed_remains_missing() -> None:
    """4. Pre-existing NaN in DAYS_EMPLOYED remains NaN and anom flag is 0."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2, 3],
            "TARGET": [0, 1, 0],
            "DAYS_EMPLOYED": [np.nan, DAYS_EMPLOYED_SENTINEL, -200],
        }
    )
    cleaned_df, _ = clean_table("application_train", raw_df)

    assert pd.isna(cleaned_df.loc[0, "DAYS_EMPLOYED"])
    assert cleaned_df.loc[0, "DAYS_EMPLOYED_ANOM"] == 0
    assert pd.isna(cleaned_df.loc[1, "DAYS_EMPLOYED"])
    assert cleaned_df.loc[1, "DAYS_EMPLOYED_ANOM"] == 1
    assert cleaned_df.loc[2, "DAYS_EMPLOYED"] == -200
    assert cleaned_df.loc[2, "DAYS_EMPLOYED_ANOM"] == 0


def test_legitimate_negative_days_employed_unchanged() -> None:
    """5. Legitimate negative days in DAYS_EMPLOYED are preserved intact."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2],
            "TARGET": [0, 1],
            "DAYS_EMPLOYED": [-1500, -32],
        }
    )
    cleaned_df, _ = clean_table("application_train", raw_df)

    assert cleaned_df["DAYS_EMPLOYED"].tolist() == [-1500, -32]
    assert cleaned_df["DAYS_EMPLOYED_ANOM"].tolist() == [0, 0]


def test_application_train_requires_target() -> None:
    """6. application_train requires TARGET column."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2],
            "DAYS_EMPLOYED": [-100, -200],
        }
    )
    with pytest.raises(ValueError, match="must contain 'TARGET'"):
        clean_table("application_train", raw_df)


def test_application_train_rejects_invalid_target() -> None:
    """7. application_train rejects non-binary or null TARGET."""
    df_non_binary = pd.DataFrame({"SK_ID_CURR": [1, 2], "TARGET": [0, 2]})
    with pytest.raises(ValueError, match="invalid values"):
        clean_table("application_train", df_non_binary)

    df_null = pd.DataFrame({"SK_ID_CURR": [1, 2], "TARGET": [0, np.nan]})
    with pytest.raises(ValueError, match="null values"):
        clean_table("application_train", df_null)


def test_application_test_rejects_target() -> None:
    """8. application_test rejects the presence of TARGET."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2],
            "TARGET": [0, 1],
        }
    )
    with pytest.raises(ValueError, match="must not contain 'TARGET'"):
        clean_table("application_test", raw_df)


def test_null_or_duplicate_sk_id_curr_rejected() -> None:
    """9. Null or duplicate SK_ID_CURR in application tables raises ValueError."""
    df_null = pd.DataFrame({"SK_ID_CURR": [1, np.nan], "TARGET": [0, 1]})
    with pytest.raises(ValueError, match="null values"):
        clean_table("application_train", df_null)

    df_dup = pd.DataFrame({"SK_ID_CURR": [1, 1], "TARGET": [0, 1]})
    with pytest.raises(ValueError, match="duplicate values"):
        clean_table("application_train", df_dup)


def test_previous_application_day_sentinels_replaced() -> None:
    """10. Sentinel 365243 in documented day fields of previous_application is replaced with NaN."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_PREV": [101, 102],
            "DAYS_FIRST_DRAWING": [DAYS_EMPLOYED_SENTINEL, -10.0],
            "DAYS_FIRST_DUE": [DAYS_EMPLOYED_SENTINEL, -20.0],
            "DAYS_LAST_DUE_1ST_VERSION": [DAYS_EMPLOYED_SENTINEL, -30.0],
            "DAYS_LAST_DUE": [DAYS_EMPLOYED_SENTINEL, -40.0],
            "DAYS_TERMINATION": [DAYS_EMPLOYED_SENTINEL, -50.0],
        }
    )
    cleaned_df, report = clean_table("previous_application", raw_df)

    for col in PREV_APP_SENTINEL_DAY_COLUMNS:
        assert pd.isna(cleaned_df.loc[0, col])
        assert cleaned_df.loc[1, col] < 0
        assert report["sentinel_replacements"][col] == 1


def test_unrelated_column_sentinel_preserved() -> None:
    """11. 365243 in an unrelated numeric column is preserved."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1],
            "TARGET": [0],
            "AMT_CREDIT": [365243.0],
        }
    )
    cleaned_df, _ = clean_table("application_train", raw_df)

    assert cleaned_df.loc[0, "AMT_CREDIT"] == 365243.0


def test_infinity_replaced_with_missing() -> None:
    """12. Positive and negative infinity become NaN in numeric columns."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2, 3],
            "TARGET": [0, 1, 0],
            "VAL": [np.inf, -np.inf, 42.0],
        }
    )
    cleaned_df, report = clean_table("application_train", raw_df)

    assert pd.isna(cleaned_df.loc[0, "VAL"])
    assert pd.isna(cleaned_df.loc[1, "VAL"])
    assert cleaned_df.loc[2, "VAL"] == 42.0
    assert report["infinity_replacements"]["VAL"] == 2


def test_leading_trailing_whitespace_trimmed() -> None:
    """13. Leading and trailing whitespace in string columns is trimmed."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2],
            "TARGET": [0, 1],
            "CONTRACT": ["  Cash loans ", "Revolving loans\t\n"],
        }
    )
    cleaned_df, report = clean_table("application_train", raw_df)

    assert cleaned_df["CONTRACT"].tolist() == ["Cash loans", "Revolving loans"]
    assert report["trimmed_string_cells"] == 2


def test_empty_after_trimming_becomes_missing() -> None:
    """14. Strings that become empty after trimming are converted to NaN."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2],
            "TARGET": [0, 1],
            "TEXT": ["   ", "valid text"],
        }
    )
    cleaned_df, report = clean_table("application_train", raw_df)

    assert pd.isna(cleaned_df.loc[0, "TEXT"])
    assert cleaned_df.loc[1, "TEXT"] == "valid text"
    assert report["blank_strings_to_missing"] == 1


def test_letter_case_and_internal_whitespace_preserved() -> None:
    """15. Letter case and internal whitespace are preserved."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1],
            "TARGET": [0],
            "OCCUPATION": ["  Secondary / secondary special  "],
        }
    )
    cleaned_df, _ = clean_table("application_train", raw_df)

    assert cleaned_df.loc[0, "OCCUPATION"] == "Secondary / secondary special"


def test_xna_and_unknown_not_globally_missing() -> None:
    """16. XNA and Unknown values are preserved, not converted to missing."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2],
            "TARGET": [0, 1],
            "CODE_GENDER": ["XNA", "Unknown"],
        }
    )
    cleaned_df, _ = clean_table("application_train", raw_df)

    assert cleaned_df["CODE_GENDER"].tolist() == ["XNA", "Unknown"]


def test_exact_duplicates_reported_and_preserved() -> None:
    """17. Exact duplicate rows are counted/reported but preserved."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_BUREAU": [1, 2, 1],
            "MONTHS_BALANCE": [-1, -2, -1],
        }
    )
    cleaned_df, report = clean_table("bureau_balance", raw_df)

    assert report["exact_duplicate_count"] == 1
    assert len(cleaned_df) == 3


def test_legitimate_split_installment_payments_preserved() -> None:
    """18. Multiple payments for the same installment grain are preserved."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_PREV": [100, 100],
            "SK_ID_CURR": [200, 200],
            "NUM_INSTALMENT_VERSION": [1.0, 1.0],
            "NUM_INSTALMENT_NUMBER": [5, 5],
            "AMT_PAYMENT": [500.0, 300.0],
            "DAYS_ENTRY_PAYMENT": [-10.0, -5.0],
        }
    )
    cleaned_df, _ = clean_table("installments_payments", raw_df)

    assert len(cleaned_df) == 2
    assert cleaned_df["AMT_PAYMENT"].tolist() == [500.0, 300.0]


def test_unknown_table_name_raises_value_error() -> None:
    """19. Unknown table name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown table name"):
        clean_table("unknown_table", pd.DataFrame())


def test_missingness_summary_counts_and_percentages() -> None:
    """20. Missingness summary metrics are exact."""
    raw_df = pd.DataFrame(
        {
            "A": [1.0, np.nan, 3.0, np.nan],
            "B": ["a", "b", "c", "d"],
        }
    )
    summary = summarize_missingness(raw_df)

    row_a = summary.loc[summary["column"] == "A"].iloc[0]
    assert row_a["missing_count"] == 2
    assert row_a["missing_percentage"] == 50.0

    row_b = summary.loc[summary["column"] == "B"].iloc[0]
    assert row_b["missing_count"] == 0
    assert row_b["missing_percentage"] == 0.0


def test_cleaning_report_row_counts_correct() -> None:
    """21. Cleaning report records correct before/after dimensions."""
    raw_df = pd.DataFrame(
        {
            "SK_ID_CURR": [1, 2, 3],
            "TARGET": [0, 1, 0],
        }
    )
    _, report = clean_table("application_train", raw_df)

    assert report["input_row_count"] == 3
    assert report["output_row_count"] == 3
    assert report["input_column_count"] == 2
    assert report["output_column_count"] == 2
    assert report["validation_status"] == "VALIDATED"


def test_required_key_validation_for_bureau_and_previous_application() -> None:
    """22. Required keys for bureau and previous_application are validated."""
    # bureau
    df_bureau_dup = pd.DataFrame({"SK_ID_BUREAU": [1, 1]})
    with pytest.raises(ValueError, match="duplicate values"):
        clean_table("bureau", df_bureau_dup)

    df_bureau_null = pd.DataFrame({"SK_ID_BUREAU": [np.nan]})
    with pytest.raises(ValueError, match="null values"):
        clean_table("bureau", df_bureau_null)

    # previous_application
    df_prev_dup = pd.DataFrame({"SK_ID_PREV": [10, 10]})
    with pytest.raises(ValueError, match="duplicate values"):
        clean_table("previous_application", df_prev_dup)

    df_prev_null = pd.DataFrame({"SK_ID_PREV": [np.nan]})
    with pytest.raises(ValueError, match="null values"):
        clean_table("previous_application", df_prev_null)
