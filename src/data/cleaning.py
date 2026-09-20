"""Canonical data cleaning and sentinel/missing handling module.

This module provides deterministic, leakage-safe cleaning rules for raw Home
Credit tables. It replaces known domain sentinels, standardizes infinity and
whitespace, validates primary keys and targets, but deliberately performs NO
statistical imputation or destructive deduplication.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.load_data import (
    RAW_TABLE_FILENAMES,
    default_raw_dir,
    validate_raw_files,
)

CANONICAL_TABLE_NAMES: tuple[str, ...] = tuple(RAW_TABLE_FILENAMES.keys())

DAYS_EMPLOYED_SENTINEL: int = 365243

PREV_APP_SENTINEL_DAY_COLUMNS: tuple[str, ...] = (
    "DAYS_FIRST_DRAWING",
    "DAYS_FIRST_DUE",
    "DAYS_LAST_DUE_1ST_VERSION",
    "DAYS_LAST_DUE",
    "DAYS_TERMINATION",
)


def summarize_missingness(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a tabular summary of missing values for all columns.

    Args:
        frame: Input DataFrame to summarize.

    Returns:
        DataFrame with columns: column, dtype, missing_count, missing_percentage.
    """
    total_rows = len(frame)
    records: list[dict[str, Any]] = []

    for col in frame.columns:
        missing_count = int(frame[col].isna().sum())
        missing_pct = (
            round((missing_count / total_rows) * 100.0, 4) if total_rows > 0 else 0.0
        )
        records.append(
            {
                "column": col,
                "dtype": str(frame[col].dtype),
                "missing_count": missing_count,
                "missing_percentage": missing_pct,
            }
        )

    return pd.DataFrame(
        records,
        columns=["column", "dtype", "missing_count", "missing_percentage"],
    )


def validate_cleaned_table(table_name: str, frame: pd.DataFrame) -> None:
    """Validate data contract and integrity rules on a cleaned table.

    Args:
        table_name: Logical name of the table.
        frame: Cleaned DataFrame to validate.

    Raises:
        ValueError: If any contract or structural rule is violated.
    """
    if table_name not in CANONICAL_TABLE_NAMES:
        raise ValueError(
            f"Unknown table name: '{table_name}'. Expected one of: {CANONICAL_TABLE_NAMES}"
        )

    if table_name == "application_train":
        if "TARGET" not in frame.columns:
            raise ValueError("application_train must contain 'TARGET' column.")
        target_series = frame["TARGET"]
        if target_series.isna().any():
            raise ValueError("application_train 'TARGET' contains null values.")
        unique_targets = set(target_series.unique())
        if not unique_targets.issubset({0, 1}):
            raise ValueError(
                f"application_train 'TARGET' contains invalid values: {unique_targets}. "
                "Only non-null binary values {0, 1} are allowed."
            )
        if "SK_ID_CURR" in frame.columns:
            if frame["SK_ID_CURR"].isna().any():
                raise ValueError("application_train 'SK_ID_CURR' contains null values.")
            if frame["SK_ID_CURR"].duplicated().any():
                raise ValueError(
                    "application_train 'SK_ID_CURR' contains duplicate values."
                )
        if "DAYS_EMPLOYED" in frame.columns:
            if (frame["DAYS_EMPLOYED"] == DAYS_EMPLOYED_SENTINEL).any():
                raise ValueError(
                    f"application_train contains unreplaced sentinel {DAYS_EMPLOYED_SENTINEL} in DAYS_EMPLOYED."
                )
        if "DAYS_EMPLOYED_ANOM" in frame.columns:
            anom_vals = set(frame["DAYS_EMPLOYED_ANOM"].unique())
            if not anom_vals.issubset({0, 1}):
                raise ValueError(
                    f"application_train 'DAYS_EMPLOYED_ANOM' contains non-binary values: {anom_vals}"
                )

    elif table_name == "application_test":
        if "TARGET" in frame.columns:
            raise ValueError("application_test must not contain 'TARGET' column.")
        if "SK_ID_CURR" in frame.columns:
            if frame["SK_ID_CURR"].isna().any():
                raise ValueError("application_test 'SK_ID_CURR' contains null values.")
            if frame["SK_ID_CURR"].duplicated().any():
                raise ValueError(
                    "application_test 'SK_ID_CURR' contains duplicate values."
                )
        if "DAYS_EMPLOYED" in frame.columns:
            if (frame["DAYS_EMPLOYED"] == DAYS_EMPLOYED_SENTINEL).any():
                raise ValueError(
                    f"application_test contains unreplaced sentinel {DAYS_EMPLOYED_SENTINEL} in DAYS_EMPLOYED."
                )
        if "DAYS_EMPLOYED_ANOM" in frame.columns:
            anom_vals = set(frame["DAYS_EMPLOYED_ANOM"].unique())
            if not anom_vals.issubset({0, 1}):
                raise ValueError(
                    f"application_test 'DAYS_EMPLOYED_ANOM' contains non-binary values: {anom_vals}"
                )

    elif table_name == "bureau":
        if "SK_ID_BUREAU" in frame.columns:
            if frame["SK_ID_BUREAU"].isna().any():
                raise ValueError("bureau 'SK_ID_BUREAU' contains null values.")
            if frame["SK_ID_BUREAU"].duplicated().any():
                raise ValueError("bureau 'SK_ID_BUREAU' contains duplicate values.")

    elif table_name == "previous_application":
        if "SK_ID_PREV" in frame.columns:
            if frame["SK_ID_PREV"].isna().any():
                raise ValueError("previous_application 'SK_ID_PREV' contains null values.")
            if frame["SK_ID_PREV"].duplicated().any():
                raise ValueError(
                    "previous_application 'SK_ID_PREV' contains duplicate values."
                )
        for col in PREV_APP_SENTINEL_DAY_COLUMNS:
            if col in frame.columns and (frame[col] == DAYS_EMPLOYED_SENTINEL).any():
                raise ValueError(
                    f"previous_application contains unreplaced sentinel {DAYS_EMPLOYED_SENTINEL} in {col}."
                )


def clean_table(
    table_name: str,
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Clean a raw table deterministically without mutating the input DataFrame.

    Applies conservative string trimming, infinity standardization, and table-specific
    sentinel replacements. Never imputes missing values or deletes rows.

    Args:
        table_name: Logical name of the table.
        frame: Raw input DataFrame.

    Returns:
        Tuple of (cleaned_df, cleaning_report).

    Raises:
        ValueError: If table_name is unknown or validation fails.
    """
    if table_name not in CANONICAL_TABLE_NAMES:
        raise ValueError(
            f"Unknown table name: '{table_name}'. Expected one of: {CANONICAL_TABLE_NAMES}"
        )

    # 1. Never mutate caller's DataFrame
    df = frame.copy(deep=True)
    input_row_count = len(frame)
    input_col_count = len(frame.columns)

    # 2. Duplicate detection without destructive deduplication
    exact_duplicate_count = int(df.duplicated().sum())

    # 3. Conservative string normalization
    trimmed_string_cells = 0
    blank_strings_to_missing = 0

    for col in df.columns:
        col_dtype = df[col].dtype
        if pd.api.types.is_object_dtype(col_dtype) or pd.api.types.is_string_dtype(col_dtype):
            mask_str = df[col].apply(lambda x: isinstance(x, str))
            if mask_str.any():
                orig_series = df.loc[mask_str, col]
                stripped_series = orig_series.str.strip()
                trimmed_count = int((orig_series != stripped_series).sum())
                trimmed_string_cells += trimmed_count

                blank_mask = stripped_series == ""
                blank_count = int(blank_mask.sum())
                blank_strings_to_missing += blank_count

                df.loc[mask_str, col] = stripped_series
                if blank_count > 0:
                    df.loc[mask_str & (df[col] == ""), col] = np.nan

    # 4. Infinity handling in numeric columns
    infinity_replacements: dict[str, int] = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            inf_mask = np.isinf(df[col])
            inf_count = int(inf_mask.sum())
            if inf_count > 0:
                infinity_replacements[col] = inf_count
                df.loc[inf_mask, col] = np.nan

    # 5. Table-specific sentinel replacement
    sentinel_replacements: dict[str, int] = {}

    if table_name in {"application_train", "application_test"}:
        if "DAYS_EMPLOYED" in df.columns:
            anom_mask = df["DAYS_EMPLOYED"] == DAYS_EMPLOYED_SENTINEL
            anom_count = int(anom_mask.sum())
            sentinel_replacements["DAYS_EMPLOYED"] = anom_count
            df["DAYS_EMPLOYED_ANOM"] = anom_mask.astype("int8")
            df.loc[anom_mask, "DAYS_EMPLOYED"] = np.nan

    elif table_name == "previous_application":
        for col in PREV_APP_SENTINEL_DAY_COLUMNS:
            if col in df.columns:
                sentinel_mask = df[col] == DAYS_EMPLOYED_SENTINEL
                s_count = int(sentinel_mask.sum())
                sentinel_replacements[col] = s_count
                df.loc[sentinel_mask, col] = np.nan

    # 6. Validate cleaned table
    validate_cleaned_table(table_name, df)

    # 7. Missingness summary
    missing_summary = summarize_missingness(df)

    report: dict[str, Any] = {
        "table_name": table_name,
        "input_row_count": input_row_count,
        "output_row_count": len(df),
        "input_column_count": input_col_count,
        "output_column_count": len(df.columns),
        "exact_duplicate_count": exact_duplicate_count,
        "sentinel_replacements": sentinel_replacements,
        "infinity_replacements": infinity_replacements,
        "trimmed_string_cells": trimmed_string_cells,
        "blank_strings_to_missing": blank_strings_to_missing,
        "missingness_summary": missing_summary.to_dict(orient="records"),
        "validation_status": "VALIDATED",
    }

    return df, report


def audit_sentinel_bearing_raw_tables(
    raw_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run real-data cleaning audit on the sentinel-bearing tables one at a time.

    Releases memory immediately after each table inspection.

    Args:
        raw_dir: Optional directory containing raw CSV files.

    Returns:
        Summary report dict with measured sentinel replacements and validation results.
    """
    paths = validate_raw_files(raw_dir)
    target_tables = ("application_train", "application_test", "previous_application")

    audit_results: dict[str, Any] = {}

    for table_name in target_tables:
        path = paths[table_name]
        raw_df = pd.read_csv(path)
        cleaned_df, report = clean_table(table_name, raw_df)

        # Record concise audit summary
        table_summary: dict[str, Any] = {
            "input_rows": report["input_row_count"],
            "output_rows": report["output_row_count"],
            "input_columns": report["input_column_count"],
            "output_columns": report["output_column_count"],
            "exact_duplicates": report["exact_duplicate_count"],
            "sentinel_replacements": report["sentinel_replacements"],
            "infinity_replacements": report["infinity_replacements"],
            "trimmed_string_cells": report["trimmed_string_cells"],
            "blank_strings_to_missing": report["blank_strings_to_missing"],
            "validation_status": report["validation_status"],
        }

        # Check remaining sentinels in cleaned_df
        remaining_sentinels: dict[str, int] = {}
        if table_name in {"application_train", "application_test"}:
            if "DAYS_EMPLOYED" in cleaned_df.columns:
                remaining_sentinels["DAYS_EMPLOYED"] = int(
                    (cleaned_df["DAYS_EMPLOYED"] == DAYS_EMPLOYED_SENTINEL).sum()
                )
            if "DAYS_EMPLOYED_ANOM" in cleaned_df.columns:
                table_summary["anomaly_flag_count"] = int(
                    (cleaned_df["DAYS_EMPLOYED_ANOM"] == 1).sum()
                )
        elif table_name == "previous_application":
            for col in PREV_APP_SENTINEL_DAY_COLUMNS:
                if col in cleaned_df.columns:
                    remaining_sentinels[col] = int(
                        (cleaned_df[col] == DAYS_EMPLOYED_SENTINEL).sum()
                    )

        table_summary["remaining_sentinels"] = remaining_sentinels
        audit_results[table_name] = table_summary

        # Explicitly release memory before next iteration
        del raw_df
        del cleaned_df

    return audit_results


if __name__ == "__main__":
    audit_summary = audit_sentinel_bearing_raw_tables()
    print(json.dumps(audit_summary, indent=2, ensure_ascii=False))
