"""Raw Home Credit loading and schema preflight utilities.

This module deliberately performs *inspection only*.  It never cleans,
aggregates, joins, or combines the labeled training population with the
unlabeled competition-test population.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd


# The names below are stable logical names used throughout the pipeline.  The
# files themselves remain local-only under data/raw (see .gitignore).
RAW_TABLE_FILENAMES: dict[str, str] = {
    "application_train": "application_train.csv",
    "application_test": "application_test.csv",
    "bureau": "bureau.csv",
    "bureau_balance": "bureau_balance.csv",
    "previous_application": "previous_application.csv",
    "installments_payments": "installments_payments.csv",
    "credit_card_balance": "credit_card_balance.csv",
    "POS_CASH_balance": "POS_CASH_balance.csv",
}
OPTIONAL_RAW_TABLE_FILENAMES: dict[str, str] = {
    "columns_description": "HomeCredit_columns_description.csv",
}

KEY_COLUMNS: dict[str, tuple[str, ...]] = {
    "application_train": ("SK_ID_CURR",),
    "application_test": ("SK_ID_CURR",),
    "bureau": ("SK_ID_BUREAU", "SK_ID_CURR"),
    "bureau_balance": ("SK_ID_BUREAU", "MONTHS_BALANCE"),
    "previous_application": ("SK_ID_PREV", "SK_ID_CURR"),
    "installments_payments": ("SK_ID_PREV", "SK_ID_CURR"),
    "POS_CASH_balance": ("SK_ID_PREV", "SK_ID_CURR", "MONTHS_BALANCE"),
    "credit_card_balance": ("SK_ID_PREV", "SK_ID_CURR", "MONTHS_BALANCE"),
}


def project_root() -> Path:
    """Return the repository root without relying on an absolute OS path."""

    return Path(__file__).resolve().parents[2]


def default_raw_dir() -> Path:
    """Return the canonical local directory for immutable source CSV files."""

    return project_root() / "data" / "raw"


def validate_raw_files(raw_dir: str | Path | None = None) -> dict[str, Path]:
    """Validate all required source files and return their resolved paths.

    Raises:
        FileNotFoundError: if one or more required tables are unavailable.
    """

    directory = Path(raw_dir) if raw_dir is not None else default_raw_dir()
    paths = {name: directory / filename for name, filename in RAW_TABLE_FILENAMES.items()}
    missing = [path.name for path in paths.values() if not path.is_file()]
    if missing:
        missing_text = ", ".join(missing)
        raise FileNotFoundError(
            f"Required Home Credit raw files are missing from '{directory}': {missing_text}. "
            "Add the original Kaggle CSV files to data/raw and rerun the preflight."
        )
    return paths


def load_raw_tables(
    raw_dir: str | Path | None = None,
    *,
    table_names: Iterable[str] | None = None,
    include_optional: bool = False,
    **read_csv_kwargs: Any,
) -> dict[str, pd.DataFrame]:
    """Load selected raw CSV tables without modifying their values.

    This function is intended for callers that genuinely need DataFrames in
    memory.  For a lower-memory inspection of the whole collection, use
    :func:`run_raw_schema_preflight`, which reads and releases one table at a
    time.
    """

    paths = validate_raw_files(raw_dir)
    if table_names is None:
        requested = tuple(paths) + (tuple(OPTIONAL_RAW_TABLE_FILENAMES) if include_optional else ())
    else:
        requested = tuple(table_names)
    unknown = sorted(set(requested) - set(paths) - set(OPTIONAL_RAW_TABLE_FILENAMES))
    if unknown:
        raise ValueError(f"Unknown raw table name(s): {', '.join(unknown)}")

    directory = Path(raw_dir) if raw_dir is not None else default_raw_dir()
    loaded: dict[str, pd.DataFrame] = {}
    for name in requested:
        if name in paths:
            loaded[name] = pd.read_csv(paths[name], **read_csv_kwargs)
        elif include_optional:
            optional_path = directory / OPTIONAL_RAW_TABLE_FILENAMES[name]
            if optional_path.is_file():
                # Kaggle's supplementary description file is Latin-1 encoded.
                # Caller-supplied read_csv options still take precedence.
                optional_kwargs = {"encoding": "latin1", **read_csv_kwargs}
                loaded[name] = pd.read_csv(optional_path, **optional_kwargs)
        else:
            raise ValueError(
                f"'{name}' is optional. Pass include_optional=True to load it explicitly."
            )
    return loaded


def _key_metrics(frame: pd.DataFrame, columns: Iterable[str]) -> dict[str, dict[str, int] | None]:
    """Measure nulls, distinct values, and duplicate occurrences for keys."""

    metrics: dict[str, dict[str, int] | None] = {}
    for column in columns:
        if column not in frame.columns:
            metrics[column] = None
            continue
        values = frame[column]
        metrics[column] = {
            "null_count": int(values.isna().sum()),
            # `duplicated().sum()` counts repeats after the first occurrence.
            "duplicate_count": int(values.duplicated().sum()),
            "nunique": int(values.nunique(dropna=True)),
            "row_count": int(len(frame)),
        }
    return metrics


def _composite_key_metrics(frame: pd.DataFrame, columns: Iterable[str]) -> dict[str, Any] | None:
    """Measure a candidate composite grain only when every column exists."""

    key_columns = tuple(columns)
    if any(column not in frame.columns for column in key_columns):
        return None
    key_frame = frame.loc[:, list(key_columns)]
    return {
        "columns": list(key_columns),
        "rows_with_null_key": int(key_frame.isna().any(axis=1).sum()),
        "duplicate_key_count": int(key_frame.duplicated().sum()),
        "nunique": int(key_frame.drop_duplicates().shape[0]),
    }


def _multiplicity(frame: pd.DataFrame, key: str) -> dict[str, float | int] | None:
    """Return the observed number of rows per non-null value of ``key``."""

    if key not in frame.columns:
        return None
    counts = frame.loc[frame[key].notna(), key].value_counts(sort=False)
    if counts.empty:
        return None
    return {
        "entities": int(counts.size),
        "min": int(counts.min()),
        "median": float(counts.median()),
        "mean": float(counts.mean()),
        "max": int(counts.max()),
    }


def profile_raw_table(table_name: str, frame: pd.DataFrame, path: str | Path) -> dict[str, Any]:
    """Return a reusable raw schema report for one already-loaded table."""

    key_columns = KEY_COLUMNS.get(table_name, ())
    dtype_counts = frame.dtypes.astype(str).value_counts().sort_index()
    return {
        "table": table_name,
        "path": str(Path(path)),
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": frame.columns.tolist(),
        "dtype_summary": {dtype: int(count) for dtype, count in dtype_counts.items()},
        "duplicate_full_rows": int(frame.duplicated().sum()),
        "key_metrics": _key_metrics(frame, key_columns),
        "candidate_key_metrics": _composite_key_metrics(frame, key_columns),
    }


def _current_id_coverage(frame: pd.DataFrame, application_ids: set[Any]) -> dict[str, Any] | None:
    """Measure coverage of a table's customer IDs in train union test IDs."""

    if "SK_ID_CURR" not in frame.columns:
        return None
    child_ids = set(frame.loc[frame["SK_ID_CURR"].notna(), "SK_ID_CURR"].unique())
    matched = len(child_ids & application_ids)
    orphan = len(child_ids - application_ids)
    return {
        "child_unique_keys": len(child_ids),
        "matched_keys": matched,
        "orphan_keys": orphan,
        "match_percentage": round((matched / len(child_ids) * 100) if child_ids else 100.0, 6),
    }


def _append_table_specific_audit(report: dict[str, Any], table_name: str, frame: pd.DataFrame) -> None:
    """Add grain observations that are meaningful for a known Home Credit table."""

    special = report.setdefault("table_specific", {})
    if table_name == "application_train":
        target = frame["TARGET"] if "TARGET" in frame.columns else None
        special["target_unique_values"] = (
            sorted(target.dropna().unique().tolist()) if target is not None else None
        )
    elif table_name == "application_test":
        special["has_target_column"] = "TARGET" in frame.columns
    elif table_name == "bureau":
        special["records_per_sk_id_curr"] = _multiplicity(frame, "SK_ID_CURR")
    elif table_name == "bureau_balance":
        special["records_per_sk_id_bureau"] = _multiplicity(frame, "SK_ID_BUREAU")
        special["grain_candidate"] = _composite_key_metrics(
            frame, ("SK_ID_BUREAU", "MONTHS_BALANCE")
        )
    elif table_name == "previous_application":
        special["records_per_sk_id_curr"] = _multiplicity(frame, "SK_ID_CURR")
    elif table_name == "installments_payments":
        special["records_per_sk_id_prev"] = _multiplicity(frame, "SK_ID_PREV")
        special["payment_record_grain_candidate"] = _composite_key_metrics(
            frame, ("SK_ID_PREV", "NUM_INSTALMENT_VERSION", "NUM_INSTALMENT_NUMBER")
        )
    elif table_name in {"POS_CASH_balance", "credit_card_balance"}:
        special["records_per_sk_id_prev"] = _multiplicity(frame, "SK_ID_PREV")
        special["grain_candidate"] = _composite_key_metrics(
            frame, ("SK_ID_PREV", "SK_ID_CURR", "MONTHS_BALANCE")
        )


def run_raw_schema_preflight(raw_dir: str | Path | None = None) -> dict[str, Any]:
    """Run the full raw-data preflight with bounded table-at-a-time memory.

    The result contains measured schema, key/grain, train/test, and foreign-key
    coverage facts.  It does not retain the raw DataFrames after each table has
    been inspected.
    """

    paths = validate_raw_files(raw_dir)
    report: dict[str, Any] = {
        "raw_dir": str((Path(raw_dir) if raw_dir is not None else default_raw_dir()).resolve()),
        "tables": {},
        "relationships": {},
        "train_test": {},
    }
    application_ids: set[Any] = set()
    train_ids: set[Any] = set()
    bureau_ids: set[Any] | None = None
    bureau_balance_ids: set[Any] | None = None

    for table_name, path in paths.items():
        frame = pd.read_csv(path)
        table_report = profile_raw_table(table_name, frame, path)
        _append_table_specific_audit(table_report, table_name, frame)
        report["tables"][table_name] = table_report

        if table_name == "application_train":
            train_ids = set(frame.loc[frame["SK_ID_CURR"].notna(), "SK_ID_CURR"].unique())
            application_ids.update(train_ids)
            report["train_test"]["application_train_rows"] = int(len(frame))
            report["train_test"]["train_sk_id_curr_unique"] = len(train_ids)
            report["train_test"]["target_in_train"] = "TARGET" in frame.columns
        elif table_name == "application_test":
            test_ids = set(frame.loc[frame["SK_ID_CURR"].notna(), "SK_ID_CURR"].unique())
            application_ids.update(test_ids)
            report["train_test"]["application_test_rows"] = int(len(frame))
            report["train_test"]["test_sk_id_curr_unique"] = len(test_ids)
            report["train_test"]["sk_id_curr_overlap"] = len(train_ids & test_ids)
            report["train_test"]["target_in_test"] = "TARGET" in frame.columns
        elif table_name == "bureau":
            bureau_ids = set(frame.loc[frame["SK_ID_BUREAU"].notna(), "SK_ID_BUREAU"].unique())
        elif table_name == "bureau_balance":
            bureau_balance_ids = set(
                frame.loc[frame["SK_ID_BUREAU"].notna(), "SK_ID_BUREAU"].unique()
            )

        # The application tables are read first by RAW_TABLE_FILENAMES, so the
        # reference population is complete before any SK_ID_CURR coverage check.
        coverage = _current_id_coverage(frame, application_ids)
        if coverage is not None and table_name not in {"application_train", "application_test"}:
            parent_key_unique = len(application_ids) == len(train_ids) + report["train_test"].get(
                "test_sk_id_curr_unique", 0
            )
            report["relationships"][f"applications_to_{table_name}"] = {
                "parent": "application_train union application_test",
                "child": table_name,
                "join_key": "SK_ID_CURR",
                "parent_key_unique": parent_key_unique,
                **coverage,
            }

        # Explicitly release each large CSV before reading the next source.
        del frame

    if bureau_ids is not None and bureau_balance_ids is not None:
        matched = len(bureau_balance_ids & bureau_ids)
        orphan = len(bureau_balance_ids - bureau_ids)
        report["relationships"]["bureau_to_bureau_balance"] = {
            "parent": "bureau",
            "child": "bureau_balance",
            "join_key": "SK_ID_BUREAU",
            "parent_key_unique": report["tables"]["bureau"]["key_metrics"]["SK_ID_BUREAU"]["duplicate_count"] == 0,
            "child_unique_keys": len(bureau_balance_ids),
            "matched_keys": matched,
            "orphan_keys": orphan,
            "match_percentage": round(
                (matched / len(bureau_balance_ids) * 100) if bureau_balance_ids else 100.0, 6
            ),
        }
    return report


if __name__ == "__main__":
    print(json.dumps(run_raw_schema_preflight(), indent=2, ensure_ascii=False))
