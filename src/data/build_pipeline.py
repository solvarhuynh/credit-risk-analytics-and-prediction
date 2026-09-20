"""Canonical end-to-end dataset build pipeline for credit risk prediction.

Orchestrates the complete TV2 data engineering pipeline:
1. Loads labeled population from application_train.csv
2. Applies canonical DE-02 cleaning layer
3. Applies canonical DE-03 application feature engineering
4. Validates and left-joins the 5 DE-04 historical aggregates (BUREAU, PREV, INSTAL, POS, CC)
5. Applies missing-history policy
6. Executes canonical quality gate
7. Publishes data/processed/cleaned_dataset.parquet and cleaned_dataset_manifest.json atomically.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sys
import uuid
from collections.abc import Collection, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.aggregate import (
    AGGREGATE_FEATURE_DEFINITIONS,
    compute_file_sha256,
    run_historical_aggregation,
)
from src.data.cleaning import clean_table
from src.data.load_data import default_raw_dir, validate_raw_files
from src.features.engineering import ENGINEERED_FEATURE_NAMES, engineer_application_features

# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------

JOIN_SOURCE_ORDER: tuple[tuple[str, str, str], ...] = (
    ("bureau", "BUREAU", "BUREAU_"),
    ("previous_application", "PREV", "PREV_"),
    ("installments_payments", "INSTAL", "INSTAL_"),
    ("pos_cash_balance", "POS", "POS_"),
    ("credit_card_balance", "CC", "CC_"),
)

UNMATCHED_ZERO_COUNT_COLUMNS: dict[str, tuple[str, ...]] = {
    "BUREAU": (
        "BUREAU_CREDIT_COUNT",
        "BUREAU_ACTIVE_COUNT",
        "BUREAU_CLOSED_COUNT",
        "BUREAU_BB_MONTH_COUNT",
        "BUREAU_BB_DELINQUENT_MONTH_COUNT",
        "BUREAU_BB_SEVERE_MONTH_COUNT",
    ),
    "PREV": (
        "PREV_APPLICATION_COUNT",
        "PREV_APPROVED_COUNT",
        "PREV_REFUSED_COUNT",
    ),
    "INSTAL": (
        "INSTAL_INSTALLMENT_COUNT",
        "INSTAL_LATE_COUNT",
        "INSTAL_UNDERPAYMENT_COUNT",
    ),
    "POS": (
        "POS_RECORD_COUNT",
        "POS_CONTRACT_COUNT",
        "POS_LATE_MONTH_COUNT",
    ),
    "CC": (
        "CC_RECORD_COUNT",
        "CC_CONTRACT_COUNT",
        "CC_LATE_MONTH_COUNT",
    ),
}

# Direct count columns that must be non-null in matched rows
MATCHED_NON_NULL_COUNT_COLUMNS: dict[str, tuple[str, ...]] = {
    "BUREAU": (
        "BUREAU_CREDIT_COUNT",
        "BUREAU_ACTIVE_COUNT",
        "BUREAU_CLOSED_COUNT",
    ),
    "PREV": (
        "PREV_APPLICATION_COUNT",
        "PREV_APPROVED_COUNT",
        "PREV_REFUSED_COUNT",
    ),
    "INSTAL": (
        "INSTAL_INSTALLMENT_COUNT",
        "INSTAL_LATE_COUNT",
        "INSTAL_UNDERPAYMENT_COUNT",
    ),
    "POS": (
        "POS_RECORD_COUNT",
        "POS_CONTRACT_COUNT",
        "POS_LATE_MONTH_COUNT",
    ),
    "CC": (
        "CC_RECORD_COUNT",
        "CC_CONTRACT_COUNT",
        "CC_LATE_MONTH_COUNT",
    ),
}

MINIMUM_CONTRACT_COLUMNS: tuple[str, ...] = (
    "SK_ID_CURR",
    "TARGET",
    "AMT_INCOME_TOTAL",
    "AMT_CREDIT",
    "AMT_ANNUITY",
    "AMT_GOODS_PRICE",
    "CODE_GENDER",
    "NAME_CONTRACT_TYPE",
    "AGE_YEARS",
    "AGE_GROUP",
    "ANNUITY_TO_INCOME_RATIO",
    "CREDIT_TO_INCOME_RATIO",
    "EMPLOYED_YEARS",
    "DAYS_EMPLOYED_ANOM",
)

BOUNDED_RATE_COLUMNS: tuple[str, ...] = (
    "BUREAU_ACTIVE_RATE",
    "BUREAU_CLOSED_RATE",
    "BUREAU_BB_DELINQUENT_MONTH_RATE",
    "BUREAU_BB_SEVERE_MONTH_RATE",
    "PREV_APPROVED_RATE",
    "PREV_REFUSED_RATE",
    "INSTAL_LATE_RATE",
    "INSTAL_UNDERPAYMENT_RATE",
    "POS_LATE_MONTH_RATE",
    "CC_LATE_MONTH_RATE",
)

APPLICATION_DERIVED_ORDER: tuple[str, ...] = (
    "DAYS_EMPLOYED_ANOM",
    "AGE_YEARS",
    "AGE_GROUP",
    "EMPLOYED_YEARS",
    "CREDIT_TO_INCOME_RATIO",
    "ANNUITY_TO_INCOME_RATIO",
    "CREDIT_TO_ANNUITY_RATIO",
)


# ---------------------------------------------------------------------------
# Join Implementation
# ---------------------------------------------------------------------------


def join_customer_aggregates(
    application: pd.DataFrame,
    aggregates: Mapping[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Deterministically left-join the 5 customer aggregates to the application frame.

    Enforces:
    - Left join with validate="one_to_one"
    - Deterministic join order: BUREAU -> PREV -> INSTAL -> POS -> CC
    - Row and target preservation by customer ID
    - Collision rejection (no _x, _y suffixes)
    - Missing-history count-filling policy
    - Exact canonical column ordering

    Args:
        application: Cleaned and feature-engineered application DataFrame.
        aggregates: Mapping of source identifiers to aggregate DataFrames.

    Returns:
        Tuple of (joined_df, join_audit_dict).

    Raises:
        ValueError: On key invalidity, row multiplication, collision, or leakage.
    """
    if not isinstance(application, pd.DataFrame):
        raise ValueError(f"Expected pandas DataFrame for application, got {type(application)}")

    if "SK_ID_CURR" not in application.columns:
        raise ValueError("Application frame missing required primary key 'SK_ID_CURR'.")
    if "TARGET" not in application.columns:
        raise ValueError("Application frame missing required label 'TARGET'.")

    # Validate input application grain
    if application["SK_ID_CURR"].isna().any():
        raise ValueError("Application frame contains null SK_ID_CURR values.")
    if application["SK_ID_CURR"].duplicated().any():
        raise ValueError("Application frame contains duplicate SK_ID_CURR values.")

    target_series = application["TARGET"]
    if target_series.isna().any():
        raise ValueError("Application frame contains null TARGET values.")
    if not set(target_series.unique()).issubset({0, 1}):
        raise ValueError("Application frame TARGET must contain only binary values {0, 1}.")

    # Capture baseline state
    orig_row_count = len(application)
    orig_ids = list(application["SK_ID_CURR"])
    orig_id_set = set(orig_ids)
    target_by_id: dict[int, int] = dict(zip(application["SK_ID_CURR"], application["TARGET"]))

    # Do not mutate input DataFrame
    joined = application.copy(deep=True)
    join_audit: dict[str, Any] = {}

    for table_name, short_key, prefix in JOIN_SOURCE_ORDER:
        # Find aggregate DataFrame from mapping
        agg_df: pd.DataFrame | None = None
        for candidate_key in (table_name, short_key, prefix, prefix.rstrip("_")):
            if candidate_key in aggregates:
                agg_df = aggregates[candidate_key]
                break

        if agg_df is None:
            raise ValueError(
                f"Missing aggregate DataFrame for source '{short_key}' (tried keys: {table_name}, {short_key}, {prefix})"
            )

        if not isinstance(agg_df, pd.DataFrame):
            raise ValueError(f"Aggregate for '{short_key}' must be a DataFrame, got {type(agg_df)}")

        # 1. Pre-join validation of aggregate
        if "SK_ID_CURR" not in agg_df.columns:
            raise ValueError(f"Aggregate '{short_key}' missing primary key 'SK_ID_CURR'.")
        if agg_df["SK_ID_CURR"].isna().any():
            raise ValueError(f"Aggregate '{short_key}' contains null SK_ID_CURR values.")
        if agg_df["SK_ID_CURR"].duplicated().any():
            raise ValueError(f"Aggregate '{short_key}' contains duplicate SK_ID_CURR values.")
        if "TARGET" in agg_df.columns:
            raise ValueError(f"Target leakage: Aggregate '{short_key}' contains 'TARGET' column.")

        # Check overlapping columns (must only be SK_ID_CURR)
        overlap = set(joined.columns) & set(agg_df.columns)
        if overlap != {"SK_ID_CURR"}:
            collision_cols = overlap - {"SK_ID_CURR"}
            raise ValueError(f"Column collision between application and '{short_key}': {collision_cols}")

        # Check prefix and metadata definitions on all non-key columns
        non_key_cols = [c for c in agg_df.columns if c != "SK_ID_CURR"]
        for col in non_key_cols:
            if not col.startswith(prefix):
                raise ValueError(
                    f"Aggregate '{short_key}' column '{col}' does not start with expected prefix '{prefix}'"
                )
            if col not in AGGREGATE_FEATURE_DEFINITIONS:
                raise ValueError(
                    f"Aggregate '{short_key}' column '{col}' is not defined in AGGREGATE_FEATURE_DEFINITIONS"
                )

        # Confirm matched non-null count columns
        for count_col in MATCHED_NON_NULL_COUNT_COLUMNS.get(short_key, ()):
            if count_col in agg_df.columns and agg_df[count_col].isna().any():
                raise ValueError(
                    f"Integrity failure: matched aggregate '{short_key}' column '{count_col}' contains missing values."
                )

        # Check aggregate-only IDs
        agg_id_set = set(agg_df["SK_ID_CURR"])
        matched_ids = orig_id_set & agg_id_set
        unmatched_ids = orig_id_set - agg_id_set
        agg_only_ids = agg_id_set - orig_id_set

        rows_before = len(joined)
        cols_before = len(joined.columns)

        # 2. Perform left join
        merged = pd.merge(
            joined,
            agg_df,
            on="SK_ID_CURR",
            how="left",
            validate="one_to_one",
        )

        # 3. Post-join validation
        rows_after = len(merged)
        if rows_after != orig_row_count:
            raise ValueError(
                f"Row multiplication/loss during join of '{short_key}': before={rows_before}, after={rows_after}"
            )

        if len(merged["SK_ID_CURR"].unique()) != orig_row_count:
            raise ValueError(f"Unique customer count changed after join of '{short_key}'.")

        if set(merged["SK_ID_CURR"]) != orig_id_set:
            raise ValueError(f"Set of customer IDs changed after join of '{short_key}'.")

        # Verify no merge suffixes
        suffix_cols = [c for c in merged.columns if c.endswith("_x") or c.endswith("_y")]
        if suffix_cols:
            raise ValueError(f"Merge suffixes detected after join of '{short_key}': {suffix_cols}")

        # Verify target integrity
        current_target_by_id = dict(zip(merged["SK_ID_CURR"], merged["TARGET"]))
        if current_target_by_id != target_by_id:
            mismatches = sum(
                1 for cid, t in current_target_by_id.items() if t != target_by_id[cid]
            )
            raise ValueError(f"TARGET mismatch detected after join of '{short_key}': {mismatches} mismatches.")

        # 4. Apply missing-history policy
        unmatched_mask = ~merged["SK_ID_CURR"].isin(agg_id_set)
        filled_count_cells = 0

        for count_col in UNMATCHED_ZERO_COUNT_COLUMNS.get(short_key, ()):
            if count_col in merged.columns:
                to_fill = unmatched_mask & merged[count_col].isna()
                fill_count = int(to_fill.sum())
                if fill_count > 0:
                    merged.loc[to_fill, count_col] = 0
                    filled_count_cells += fill_count

                # Cast whole, non-null count columns to integer-compatible dtype
                if not merged[count_col].isna().any():
                    merged[count_col] = merged[count_col].astype(np.int64)
                else:
                    merged[count_col] = merged[count_col].astype("Int64")

        # Audit remaining null cells in joined columns
        remaining_null_cells = int(merged[non_key_cols].isna().sum().sum())

        join_audit[short_key] = {
            "source": table_name,
            "prefix": prefix,
            "aggregate_input_rows": len(agg_df),
            "aggregate_input_columns": len(agg_df.columns),
            "aggregate_unique_customers": len(agg_id_set),
            "application_rows_before_join": rows_before,
            "application_rows_after_join": rows_after,
            "application_unique_customers_before_join": orig_row_count,
            "application_unique_customers_after_join": len(merged["SK_ID_CURR"].unique()),
            "matched_application_customers": len(matched_ids),
            "unmatched_application_customers": len(unmatched_ids),
            "coverage_rate": round(len(matched_ids) / orig_row_count, 6),
            "aggregate_only_customers": len(agg_only_ids),
            "features_joined": len(non_key_cols),
            "filled_count_cells": filled_count_cells,
            "remaining_null_cells": remaining_null_cells,
            "duplicate_application_keys_after_join": int(merged["SK_ID_CURR"].duplicated().sum()),
            "null_application_keys_after_join": int(merged["SK_ID_CURR"].isna().sum()),
            "target_mismatch_count": 0,
            "row_multiplication_count": 0,
        }

        joined = merged

    # 5. Deterministic canonical column ordering
    # Group 1: SK_ID_CURR
    # Group 2: TARGET
    # Group 3: Cleaned application raw columns
    # Group 4: Application-derived fields
    # Group 5: Aggregate features by prefix in JOIN_SOURCE_ORDER
    known_app_derived = set(APPLICATION_DERIVED_ORDER)
    all_aggregate_features = [
        c
        for c in joined.columns
        if any(c.startswith(p) for _, _, p in JOIN_SOURCE_ORDER)
    ]
    raw_app_cols = [
        c
        for c in application.columns
        if c not in {"SK_ID_CURR", "TARGET"}
        and c not in known_app_derived
        and c not in all_aggregate_features
    ]
    app_derived_present = [c for c in APPLICATION_DERIVED_ORDER if c in joined.columns]

    ordered_cols: list[str] = ["SK_ID_CURR", "TARGET"] + raw_app_cols + app_derived_present

    for _, _, prefix in JOIN_SOURCE_ORDER:
        prefix_features = [
            feat
            for feat in AGGREGATE_FEATURE_DEFINITIONS
            if feat.startswith(prefix) and feat in joined.columns
        ]
        ordered_cols.extend(prefix_features)

    # Any remaining columns (if any, preserving stability)
    remaining = [c for c in joined.columns if c not in set(ordered_cols)]
    ordered_cols.extend(remaining)

    joined = joined[ordered_cols]

    # Sort rows by SK_ID_CURR ascending and reset index
    joined = joined.sort_values("SK_ID_CURR", ascending=True).reset_index(drop=True)

    return joined, join_audit


# ---------------------------------------------------------------------------
# Quality Gate
# ---------------------------------------------------------------------------


def validate_canonical_dataset(
    frame: pd.DataFrame,
    *,
    expected_ids: Collection[int] | pd.Series | None = None,
    expected_target_by_id: Mapping[int, int] | None = None,
) -> dict[str, Any]:
    """Execute the full canonical quality gate on the published dataset.

    Validates all requirements from Section 11 of the specification.

    Args:
        frame: Candidate canonical DataFrame.
        expected_ids: Optional collection of expected SK_ID_CURR values.
        expected_target_by_id: Optional mapping of SK_ID_CURR -> TARGET.

    Returns:
        Quality gate summary dict with status='PASSED'.

    Raises:
        ValueError: If any quality gate requirement fails.
    """
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"Expected DataFrame, got {type(frame)}")

    row_count = len(frame)
    if row_count == 0:
        raise ValueError("Canonical dataset is empty.")

    # 1. Key validation
    if "SK_ID_CURR" not in frame.columns:
        raise ValueError("Missing 'SK_ID_CURR' in canonical dataset.")
    if frame["SK_ID_CURR"].isna().any():
        null_cnt = int(frame["SK_ID_CURR"].isna().sum())
        raise ValueError(f"SK_ID_CURR contains {null_cnt} null values.")
    if frame["SK_ID_CURR"].duplicated().any():
        dup_cnt = int(frame["SK_ID_CURR"].duplicated().sum())
        raise ValueError(f"SK_ID_CURR contains {dup_cnt} duplicate values.")

    # 2. Row order and ID set
    if not frame["SK_ID_CURR"].is_monotonic_increasing:
        raise ValueError("Rows are not sorted by SK_ID_CURR ascending.")

    if expected_ids is not None:
        exp_id_set = set(expected_ids)
        act_id_set = set(frame["SK_ID_CURR"])
        if act_id_set != exp_id_set:
            diff_missing = len(exp_id_set - act_id_set)
            diff_extra = len(act_id_set - exp_id_set)
            raise ValueError(
                f"ID mismatch with expected population: missing={diff_missing}, extra={diff_extra}"
            )

    # 3. Target validation
    if "TARGET" not in frame.columns:
        raise ValueError("Missing 'TARGET' in canonical dataset.")
    if frame["TARGET"].isna().any():
        raise ValueError("TARGET contains null values.")
    target_vals = set(frame["TARGET"].unique())
    if not target_vals.issubset({0, 1}):
        raise ValueError(f"TARGET must contain only binary values {{0, 1}}, got: {target_vals}")

    if expected_target_by_id is not None:
        act_targets = dict(zip(frame["SK_ID_CURR"], frame["TARGET"]))
        mismatches = sum(
            1 for cid, t in act_targets.items() if expected_target_by_id.get(cid) != t
        )
        if mismatches > 0:
            raise ValueError(f"TARGET assignment mismatch: {mismatches} mismatches detected.")

    # 4. Minimum data contract columns
    for col in MINIMUM_CONTRACT_COLUMNS:
        if col not in frame.columns:
            raise ValueError(f"Missing required contract column: '{col}'")

    # 5. Aggregate features validation
    for feat_name, meta in AGGREGATE_FEATURE_DEFINITIONS.items():
        if feat_name not in frame.columns:
            raise ValueError(f"Missing approved aggregate feature: '{feat_name}'")

    # Verify no aggregate features exist outside metadata
    for col in frame.columns:
        if any(col.startswith(p) for _, _, p in JOIN_SOURCE_ORDER):
            if col not in AGGREGATE_FEATURE_DEFINITIONS:
                raise ValueError(f"Unapproved aggregate feature detected: '{col}'")

    # 6. Column name integrity
    if len(frame.columns) != len(set(frame.columns)):
        dup_cols = [c for c in frame.columns if list(frame.columns).count(c) > 1]
        raise ValueError(f"Duplicate column names in canonical dataset: {set(dup_cols)}")

    suffix_cols = [c for c in frame.columns if c.endswith("_x") or c.endswith("_y")]
    if suffix_cols:
        raise ValueError(f"Merge suffix columns detected: {suffix_cols}")

    # 7. Absence of infinity
    for col in frame.columns:
        if pd.api.types.is_numeric_dtype(frame[col]):
            inf_mask = np.isinf(frame[col])
            if inf_mask.any():
                raise ValueError(f"Infinity detected in column '{col}': {int(inf_mask.sum())} cells.")

    # 8. Bounded rates and counts validation
    for col in BOUNDED_RATE_COLUMNS:
        if col in frame.columns:
            s = frame[col].dropna()
            if (s < -1e-6).any() or (s > 1.0 + 1e-6).any():
                raise ValueError(f"Bounded rate column '{col}' contains values outside [0, 1].")

    count_cols = [c for c in frame.columns if c.endswith("_COUNT")]
    for col in count_cols:
        s = frame[col].dropna()
        if (s < 0).any():
            raise ValueError(f"Count column '{col}' contains negative values.")

    target_dist = {int(k): int(v) for k, v in frame["TARGET"].value_counts().items()}

    return {
        "status": "PASSED",
        "row_count": row_count,
        "column_count": len(frame.columns),
        "target_distribution": target_dist,
        "unique_customer_count": len(frame["SK_ID_CURR"]),
        "null_key_count": 0,
        "duplicate_key_count": 0,
        "infinity_count": 0,
    }


# ---------------------------------------------------------------------------
# Atomic Publication
# ---------------------------------------------------------------------------


def write_canonical_dataset_atomic(
    frame: pd.DataFrame,
    destination: Path,
) -> dict[str, Any]:
    """Atomically write canonical dataset to Parquet and validate readback.

    Args:
        frame: Candidate canonical DataFrame.
        destination: Final target file path.

    Returns:
        Dict of publication metadata.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.parent / f"{destination.name}.tmp.{uuid.uuid4().hex}"

    try:
        frame.to_parquet(temp_path, index=False, engine="pyarrow")

        # Read back independently and validate
        read_back = pd.read_parquet(temp_path, engine="pyarrow")
        validate_canonical_dataset(
            read_back,
            expected_ids=frame["SK_ID_CURR"],
            expected_target_by_id=dict(zip(frame["SK_ID_CURR"], frame["TARGET"])),
        )

        row_count = len(read_back)
        col_count = len(read_back.columns)
        del read_back

        os.replace(temp_path, destination)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    file_size = destination.stat().st_size
    file_sha256 = compute_file_sha256(destination)

    return {
        "output_path": str(destination),
        "output_size_bytes": file_size,
        "output_sha256": file_sha256,
        "row_count": row_count,
        "column_count": col_count,
    }


# ---------------------------------------------------------------------------
# Pipeline Orchestration
# ---------------------------------------------------------------------------


def run_build_pipeline(
    raw_dir: Path | str | None = None,
    interim_dir: Path | str | None = None,
    processed_dir: Path | str | None = None,
    *,
    rebuild_aggregates: bool = False,
) -> dict[str, Any]:
    """Execute the canonical end-to-end data engineering build pipeline.

    Args:
        raw_dir: Directory with raw CSV files.
        interim_dir: Directory with interim DE-04 parquet files.
        processed_dir: Directory for final canonical publication.
        rebuild_aggregates: If True, forces re-running DE-04 aggregation.

    Returns:
        Canonical build manifest dict.
    """
    raw_paths = validate_raw_files(raw_dir)
    target_interim = Path(interim_dir) if interim_dir else Path("data/interim")
    target_processed = Path(processed_dir) if processed_dir else Path("data/processed")
    target_processed.mkdir(parents=True, exist_ok=True)

    app_train_path = raw_paths["application_train"]
    raw_train_sha256 = compute_file_sha256(app_train_path)

    # 1. Manage DE-04 interim aggregates
    aggregate_files = {
        "bureau": target_interim / "bureau_aggregated.parquet",
        "previous_application": target_interim / "previous_application_aggregated.parquet",
        "installments_payments": target_interim / "installments_payments_aggregated.parquet",
        "pos_cash_balance": target_interim / "pos_cash_balance_aggregated.parquet",
        "credit_card_balance": target_interim / "credit_card_balance_aggregated.parquet",
    }
    manifest_interim_path = target_interim / "aggregation_manifest.json"

    needs_rebuild = rebuild_aggregates or not manifest_interim_path.exists()
    rebuild_reason = "rebuild_aggregates requested" if rebuild_aggregates else "manifest missing"

    if not needs_rebuild:
        for key, p in aggregate_files.items():
            if not p.exists():
                needs_rebuild = True
                rebuild_reason = f"aggregate file missing: {p.name}"
                break

    if needs_rebuild:
        run_historical_aggregation(raw_dir=raw_dir, interim_dir=target_interim)
    else:
        # Validate interim manifest
        with open(manifest_interim_path, encoding="utf-8") as f:
            interim_manifest = json.load(f)
        for key, p in aggregate_files.items():
            expected_hash = interim_manifest.get("outputs", {}).get(key, {}).get("sha256")
            actual_hash = compute_file_sha256(p)
            if expected_hash and actual_hash != expected_hash:
                needs_rebuild = True
                rebuild_reason = f"checksum mismatch on {p.name}"
                run_historical_aggregation(raw_dir=raw_dir, interim_dir=target_interim)
                break

    # Re-read verified interim checksums
    interim_input_sha256 = {k: compute_file_sha256(p) for k, p in aggregate_files.items()}
    interim_manifest_sha256 = compute_file_sha256(manifest_interim_path)

    # 2. Load application_train raw
    raw_app = pd.read_csv(app_train_path)
    raw_row_count = len(raw_app)
    raw_col_count = len(raw_app.columns)
    orig_target_dist = {int(k): int(v) for k, v in raw_app["TARGET"].value_counts().items()}
    expected_ids = set(raw_app["SK_ID_CURR"])
    expected_target_by_id = dict(zip(raw_app["SK_ID_CURR"], raw_app["TARGET"]))

    # 3. DE-02 Cleaning
    cleaned_app, cleaning_report = clean_table("application_train", raw_app)
    del raw_app
    gc.collect()

    # 4. DE-03 Feature Engineering
    enriched_app, feature_report = engineer_application_features(
        cleaned_app, table_name="application_train"
    )
    del cleaned_app
    gc.collect()

    # 5. Load historical aggregates
    aggregates: dict[str, pd.DataFrame] = {}
    for key, p in aggregate_files.items():
        aggregates[key] = pd.read_parquet(p, engine="pyarrow")

    # 6. Join aggregates
    canonical_df, join_audit = join_customer_aggregates(enriched_app, aggregates)
    del enriched_app
    del aggregates
    gc.collect()

    # 7. Validate canonical dataset
    quality_gate = validate_canonical_dataset(
        canonical_df,
        expected_ids=expected_ids,
        expected_target_by_id=expected_target_by_id,
    )

    # 8. Write Parquet atomically
    output_parquet_path = target_processed / "cleaned_dataset.parquet"
    pub_meta = write_canonical_dataset_atomic(canonical_df, output_parquet_path)

    # 9. Build Manifest
    final_cols = list(canonical_df.columns)
    feature_cols = [c for c in final_cols if c not in {"SK_ID_CURR", "TARGET"}]
    numeric_cols = [c for c in feature_cols if pd.api.types.is_numeric_dtype(canonical_df[c])]
    categorical_cols = [c for c in feature_cols if not pd.api.types.is_numeric_dtype(canonical_df[c])]

    output_schema = {c: str(canonical_df[c].dtype) for c in final_cols}
    del canonical_df
    gc.collect()

    manifest: dict[str, Any] = {
        "task_id": "TV2-DE-05",
        "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "population": "application_train_only",
        "application_test_included": False,
        "git_branch": "tv2",
        "base_commit": "6984c30",
        "command": "python -m src.data.build_pipeline",
        "raw_input_paths": {
            "application_train": str(app_train_path),
        },
        "raw_input_sha256": {
            "application_train.csv": raw_train_sha256,
        },
        "interim_input_paths": {k: str(p) for k, p in aggregate_files.items()},
        "interim_input_sha256": interim_input_sha256,
        "interim_manifest_sha256": interim_manifest_sha256,
        "aggregate_rebuilt": needs_rebuild,
        "aggregate_rebuild_reason": rebuild_reason if needs_rebuild else None,
        "pipeline_stage_order": [
            "raw_loading",
            "de02_cleaning",
            "de03_application_features",
            "de04_aggregate_loading",
            "de05_customer_joins",
            "quality_gate",
            "atomic_parquet_publication",
            "manifest_publication",
        ],
        "cleaning_summary": {
            "input_rows": cleaning_report["input_row_count"],
            "output_rows": cleaning_report["output_row_count"],
            "sentinel_replacements": cleaning_report["sentinel_replacements"],
            "infinity_replacements": cleaning_report["infinity_replacements"],
            "exact_duplicate_count": cleaning_report["exact_duplicate_count"],
        },
        "application_feature_summary": {
            "features_added": feature_report["features_added"],
            "row_order_preserved": feature_report["row_order_preserved"],
            "id_preserved": feature_report["id_preserved"],
        },
        "join_order": [short for _, short, _ in JOIN_SOURCE_ORDER],
        "join_audit": join_audit,
        "missing_history_policy": {
            "unmatched_count_features_filled_with_zero": UNMATCHED_ZERO_COUNT_COLUMNS,
            "unmatched_rates_and_statistics_preserved_as_missing": True,
        },
        "row_count": pub_meta["row_count"],
        "column_count": pub_meta["column_count"],
        "feature_count": len(feature_cols),
        "numeric_column_count": len(numeric_cols),
        "categorical_column_count": len(categorical_cols),
        "sk_id_curr_null_count": 0,
        "sk_id_curr_duplicate_count": 0,
        "sk_id_curr_min": int(min(expected_ids)),
        "sk_id_curr_max": int(max(expected_ids)),
        "target_distribution": orig_target_dist,
        "target_mismatch_count": 0,
        "infinity_count": 0,
        "required_contract_columns": list(MINIMUM_CONTRACT_COLUMNS),
        "aggregate_feature_count": len(AGGREGATE_FEATURE_DEFINITIONS),
        "output_path": str(output_parquet_path),
        "output_size_bytes": pub_meta["output_size_bytes"],
        "output_sha256": pub_meta["output_sha256"],
        "output_schema": output_schema,
        "quality_gate_results": quality_gate,
        "warnings": [
            "Historical aggregate coverage is below 100% for all sources (expected domain behavior).",
            "bureau_balance contains 43,041 orphan SK_ID_BUREAU values excluded from customer mapping in DE-04.",
            "installments_payments contains repeated installment-grain rows consolidated in DE-04.",
            "Features for unmatched customers retain genuine missing values for rates and statistics.",
        ],
    }

    manifest_output_path = target_processed / "cleaned_dataset_manifest.json"
    temp_manifest = target_processed / f"cleaned_dataset_manifest.json.tmp.{uuid.uuid4().hex}"

    with open(temp_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    os.replace(temp_manifest, manifest_output_path)

    manifest["manifest_path"] = str(manifest_output_path)
    manifest["manifest_sha256"] = compute_file_sha256(manifest_output_path)

    return manifest


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI runner for build_pipeline."""
    parser = argparse.ArgumentParser(description="Canonical Dataset Build Pipeline")
    parser.add_argument(
        "--rebuild-aggregates",
        action="store_true",
        help="Force rebuild of historical interim aggregates via DE-04.",
    )
    args = parser.parse_args()

    manifest = run_build_pipeline(rebuild_aggregates=args.rebuild_aggregates)

    summary = {
        "status": "SUCCESS",
        "task_id": manifest["task_id"],
        "output_parquet": manifest["output_path"],
        "output_size_bytes": manifest["output_size_bytes"],
        "output_sha256": manifest["output_sha256"],
        "row_count": manifest["row_count"],
        "column_count": manifest["column_count"],
        "feature_count": manifest["feature_count"],
        "target_distribution": manifest["target_distribution"],
        "manifest_path": manifest["manifest_path"],
        "manifest_sha256": manifest["manifest_sha256"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
