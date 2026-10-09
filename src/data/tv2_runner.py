"""Stage runner chính thức cho TV2 Lending Club.

Mỗi stage tạo một report nhỏ và một marker JSON. Stage sau chỉ chạy khi mọi
stage trước đã có marker ``PASS``. Runner hỗ trợ ``--raw-dir``, ``--reports-dir``,
``--interim-dir`` và ``--processed-dir`` để test bằng fixture nhỏ mà không đụng
vào raw thật.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator
from uuid import uuid4

import numpy as np
import pandas as pd
try:
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover - setup dependency is required for DE-LC-04+
    pq = None

from src.config import INTERIM_DIR, PROCESSED_DIR, REPORTS_DIR
from src.data.aggregate import (
    build_borrower_profile_table,
    build_credit_profile_table,
    build_date_dimension,
    build_loan_application_table,
    build_loan_outcome_table,
    build_loan_pricing_table,
    build_rejected_applications_table,
    build_state_dimension,
    join_canonical_modeling_table,
)
from src.data.build_pipeline import ParquetSink, prepare_accepted_batch
from src.data.cleaning import REJECTED_RENAME, clean_accepted_loans, clean_rejected_loans, derive_target
from src.data.column_policy import (
    ColumnClass,
    approved_model_features,
    classify_column,
    classify_columns,
    unknown_columns,
)
from src.data.load_data import inspect_raw_schema, load_accepted_loans, load_csv, load_rejected_loans, validate_raw_files
from src.data.quality_report import (
    render_quality_report,
    run_leakage_gate,
    validate_handoff_manifest,
)
from src.features.engineering import ENGINEERED_FEATURES, engineer_lending_club_features

STAGES: tuple[str, ...] = tuple(f"de-lc-{index:02d}" for index in range(1, 11))
STAGE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    stage: STAGES[:index] for index, stage in enumerate(STAGES)
}
STAGE_TITLES = {
    "de-lc-01": "Raw inventory & schema profiling",
    "de-lc-02": "Accepted/rejected cleaning verification",
    "de-lc-03": "Leakage classification",
    "de-lc-04": "Business-table normalization",
    "de-lc-05": "Target derivation",
    "de-lc-06": "Application-time feature engineering",
    "de-lc-07": "Canonical modeling join",
    "de-lc-08": "Dimensions and dashboard marts",
    "de-lc-09": "Dictionary, manifest and quality report",
    "de-lc-10": "Static EDA",
}

EDA_FIGURE_NAMES = (
    "eda_01_loan_amount_distribution.png",
    "eda_02_dti_by_target.png",
    "eda_03_default_by_fico.png",
    "eda_04_fico_dti_heatmap.png",
    "eda_05_accepted_loan_volume_over_time.png",
)
FICO_BAND_ORDER = ("<650", "650-699", "700-749", "750+")
DTI_BAND_ORDER = ("<=10", "10-20", "20-30", ">30")
EDA_SAMPLE_LIMIT = 200_000
FICO_MIN_GROUP_COUNT = 100
HEATMAP_MIN_CELL_COUNT = 100
EDA_02_DTI_Y_LABEL = "DTI (%)"


class StageValidationError(RuntimeError):
    """Stage đã chạy nhưng dữ liệu/contract không đạt."""


class StageBlocked(RuntimeError):
    """Stage bị chặn vì dependency chưa PASS."""


def _require_pyarrow() -> Any:
    if pq is None:
        raise StageValidationError(
            "pyarrow chưa được cài; chạy 'python -m pip install -r requirements.txt' trước stage tạo Parquet."
        )
    return pq


@dataclass(frozen=True)
class RunnerContext:
    raw_dir: Path
    reports_dir: Path
    interim_dir: Path
    processed_dir: Path
    chunksize: int = 100_000

    @property
    def stage_dir(self) -> Path:
        return self.reports_dir / "tv2_stages"

    @property
    def marker_dir(self) -> Path:
        return self.stage_dir / "state"


@dataclass(frozen=True)
class StageResult:
    stage: str
    status: str
    report_path: Path
    marker_path: Path
    message: str


def normalize_stage(stage: str) -> str:
    normalized = stage.strip().lower()
    if not re.fullmatch(r"de-lc-\d{2}", normalized) or normalized not in STAGES:
        raise ValueError(f"Stage không hợp lệ: {stage!r}. Chọn một trong: {', '.join(STAGES)}")
    return normalized


def _marker_path(context: RunnerContext, stage: str) -> Path:
    return context.marker_dir / f"{stage}.json"


def _read_marker(context: RunnerContext, stage: str) -> dict[str, Any] | None:
    path = _marker_path(context, stage)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StageBlocked(f"Marker hỏng: {path}") from exc


def check_stage_dependencies(context: RunnerContext, stage: str) -> None:
    missing_or_failed: list[str] = []
    for dependency in STAGE_DEPENDENCIES[stage]:
        marker = _read_marker(context, dependency)
        if marker is None or marker.get("status") != "PASS":
            status = "MISSING" if marker is None else str(marker.get("status"))
            missing_or_failed.append(f"{dependency}={status}")
    if missing_or_failed:
        raise StageBlocked(
            f"{stage} bị chặn; dependency phải PASS trước: {', '.join(missing_or_failed)}"
        )


def _write_result(context: RunnerContext, stage: str, status: str, message: str, payload: dict[str, Any]) -> StageResult:
    context.stage_dir.mkdir(parents=True, exist_ok=True)
    context.marker_dir.mkdir(parents=True, exist_ok=True)
    report_path = context.stage_dir / f"{stage}.md"
    marker_path = _marker_path(context, stage)
    completed_at = datetime.now(timezone.utc).isoformat()
    marker = {
        "stage": stage,
        "title": STAGE_TITLES[stage],
        "status": status,
        "completed_at_utc": completed_at,
        "report_path": str(report_path),
        "payload": payload,
    }
    marker_path.write_text(json.dumps(marker, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    lines = [
        f"# {stage.upper()} — {STAGE_TITLES[stage]}",
        "",
        f"**Status: {status}**",
        "",
        message,
        "",
        "```json",
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        "```",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return StageResult(stage, status, report_path, marker_path, message)


def _run_with_status(context: RunnerContext, stage: str, function: Any) -> StageResult:
    try:
        check_stage_dependencies(context, stage)
        payload = function(context)
        return _write_result(context, stage, "PASS", "Stage hoàn tất và có thể chuyển sang stage kế tiếp.", payload)
    except StageBlocked as exc:
        return _write_result(context, stage, "BLOCKED", str(exc), {})
    except (StageValidationError, FileNotFoundError, ValueError, OSError, RuntimeError) as exc:
        return _write_result(context, stage, "FAIL", str(exc), {})


def _sample_values(path: Path, usecols: list[str], rows: int = 5) -> list[dict[str, Any]]:
    frame = pd.read_csv(path, usecols=usecols, nrows=rows, low_memory=False)
    return frame.astype("string").fillna("<NA>").to_dict(orient="records")


def _status_counts(context: RunnerContext) -> dict[str, int]:
    counts: Counter[str] = Counter()
    reader = load_csv(
        "accepted",
        raw_dir=context.raw_dir,
        usecols=["loan_status"],
        chunksize=context.chunksize,
        dtype={"loan_status": "string"},
    )
    for chunk in reader:
        counts.update(chunk["loan_status"].astype("string").fillna("<NA>").tolist())
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _stage_01(context: RunnerContext) -> dict[str, Any]:
    paths = validate_raw_files(context.raw_dir)
    schema = inspect_raw_schema(context.raw_dir, sample_rows=5)
    accepted_header = pd.read_csv(paths["accepted"], nrows=0).columns.tolist()
    normalized_header = ["loan_id" if column == "id" else column for column in accepted_header]
    policy = classify_columns(normalized_header)
    unknown = unknown_columns(normalized_header)
    if unknown:
        raise StageValidationError(f"Raw accepted có cột UNKNOWN_REVIEW_REQUIRED: {unknown}")
    accepted_sample = _sample_values(paths["accepted"], ["id", "loan_status", "issue_d", "addr_state", "zip_code"])
    rejected_sample = _sample_values(paths["rejected"], ["Application Date", "State", "Zip Code", "Amount Requested"])
    return {
        "raw_schema": schema,
        "accepted_policy_counts": dict(Counter(str(value) for value in policy.values())),
        "accepted_unknown_columns": unknown,
        "accepted_sample": accepted_sample,
        "rejected_sample": rejected_sample,
        "loan_status_distribution": _status_counts(context),
        "semantic_notes": {
            "geography": "addr_state is the state-level field; zip_code remains a masked string.",
            "dates": "issue_d and application/date fields are profiled before parsing.",
            "target": "loan_status is the target source only; unresolved statuses are not forced to 0.",
        },
    }


def _stage_02(context: RunnerContext) -> dict[str, Any]:
    accepted_rows = rejected_rows = unresolved_rows = 0
    accepted_state_non_null = accepted_zip_non_null = 0
    for chunk in load_accepted_loans(raw_dir=context.raw_dir, chunksize=context.chunksize):
        cleaned, report = clean_accepted_loans(chunk)
        accepted_rows += len(cleaned)
        unresolved_rows += report["unresolved_status_rows"]
        accepted_state_non_null += int(cleaned.get("state_code", pd.Series(dtype="string")).notna().sum())
        accepted_zip_non_null += int(cleaned.get("zip_code", pd.Series(dtype="string")).notna().sum())
        if np.isinf(cleaned.select_dtypes(include=["number"]).to_numpy(dtype=float, na_value=np.nan)).any():
            raise StageValidationError("Accepted cleaning còn giá trị vô cực.")
    rejected_state_non_null = 0
    for chunk in load_rejected_loans(raw_dir=context.raw_dir, chunksize=context.chunksize):
        cleaned, _ = clean_rejected_loans(chunk)
        rejected_rows += len(cleaned)
        rejected_state_non_null += int(cleaned["state_code"].notna().sum())
    if accepted_rows == 0 or rejected_rows == 0:
        raise StageValidationError("Accepted và rejected đều phải có dữ liệu.")
    return {
        "accepted_rows_checked": accepted_rows,
        "rejected_rows_checked": rejected_rows,
        "accepted_unresolved_status_rows": unresolved_rows,
        "accepted_state_non_null": accepted_state_non_null,
        "accepted_zip_non_null": accepted_zip_non_null,
        "rejected_state_non_null": rejected_state_non_null,
        "statistical_imputation": False,
    }


def _stage_03(context: RunnerContext) -> dict[str, Any]:
    paths = validate_raw_files(context.raw_dir)
    accepted_header = ["loan_id" if column == "id" else column for column in pd.read_csv(paths["accepted"], nrows=0).columns]
    rejected_header = [REJECTED_RENAME.get(column, column) for column in pd.read_csv(paths["rejected"], nrows=0).columns]
    accepted_policy = classify_columns(accepted_header)
    rejected_policy = classify_columns(rejected_header)
    unknown = unknown_columns([*accepted_header, *rejected_header])
    if unknown:
        raise StageValidationError(f"UNKNOWN_REVIEW_REQUIRED: {unknown}")
    counts = Counter(str(value) for value in [*accepted_policy.values(), *rejected_policy.values()])
    return {
        "accepted_columns": len(accepted_header),
        "rejected_columns": len(rejected_header),
        "policy_counts": dict(counts),
        "unknown_columns": [],
        "post_loan_columns": [column for column in accepted_header if classify_column(column) == ColumnClass.POST_LOAN],
        "model_default_features": approved_model_features(accepted_header),
    }


BUSINESS_TABLE_NAMES = (
    "loan_application",
    "borrower_profile",
    "credit_profile",
    "loan_pricing",
    "loan_outcome",
    "rejected_applications",
)
BUSINESS_TABLE_PROGRESS_INTERVAL = 5


def _close_business_table_sinks(sinks: dict[str, ParquetSink]) -> None:
    """Đóng mọi sink một lần và không bỏ sót sink khi một sink lỗi."""

    errors: list[BaseException] = []
    for sink in tuple(sinks.values()):
        try:
            sink.close()
        except BaseException as exc:  # pragma: no cover - defensive cleanup path
            errors.append(exc)
    sinks.clear()
    if errors:
        raise errors[0]


def _remove_business_table_partials(partial_paths: dict[str, Path]) -> None:
    """Xóa đúng các artifact partial của DE-LC-04, không đụng canonical output."""

    for path in partial_paths.values():
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _validate_business_table_partials(partial_paths: dict[str, Path]) -> None:
    """Kiểm tra đủ sáu Parquet partial trước khi expose canonical names."""

    parquet = _require_pyarrow()
    for name, path in partial_paths.items():
        if not path.is_file() or path.stat().st_size == 0:
            raise StageValidationError(f"Thiếu business table partial: {path}")
        metadata = parquet.ParquetFile(path).metadata
        if metadata is None or metadata.num_rows == 0:
            raise StageValidationError(f"Business table partial rỗng hoặc không hợp lệ: {name}")


def _promote_business_table_partials(
    partial_paths: dict[str, Path],
    final_paths: dict[str, Path],
) -> None:
    """Promote sáu partial output, rollback canonical cũ nếu promotion bị lỗi."""

    token = uuid4().hex
    backups: dict[Path, Path] = {}
    promoted: list[Path] = []
    try:
        for name in BUSINESS_TABLE_NAMES:
            final_path = final_paths[name]
            if final_path.is_file():
                backup_path = final_path.with_name(f".{final_path.name}.{token}.rollback")
                os.replace(final_path, backup_path)
                backups[final_path] = backup_path
        for name in BUSINESS_TABLE_NAMES:
            final_path = final_paths[name]
            os.replace(partial_paths[name], final_path)
            promoted.append(final_path)
    except BaseException:
        for final_path in promoted:
            try:
                final_path.unlink(missing_ok=True)
            except OSError:
                pass
        for final_path, backup_path in backups.items():
            if backup_path.is_file():
                try:
                    os.replace(backup_path, final_path)
                except OSError:
                    pass
        raise
    else:
        for backup_path in backups.values():
            try:
                backup_path.unlink(missing_ok=True)
            except OSError:
                pass


def _report_business_table_progress(kind: str, chunks: int, rows: int, *, force: bool = False) -> None:
    """In tiến độ theo chunk, không in theo từng dòng."""

    if force:
        if chunks == 0 or chunks % BUSINESS_TABLE_PROGRESS_INTERVAL != 0:
            print(f"DE-LC-04 {kind} chunks={chunks} rows={rows}")
    elif chunks % BUSINESS_TABLE_PROGRESS_INTERVAL == 0:
        print(f"DE-LC-04 {kind} chunks={chunks} rows={rows}")


def _write_business_tables(context: RunnerContext) -> dict[str, Any]:
    """Ghi business tables qua partial files rồi mới promote thành một set."""

    context.interim_dir.mkdir(parents=True, exist_ok=True)
    partial_paths = {
        name: context.interim_dir / f"{name}.partial.parquet"
        for name in BUSINESS_TABLE_NAMES
    }
    final_paths = {
        name: context.interim_dir / f"{name}.parquet"
        for name in BUSINESS_TABLE_NAMES
    }
    _remove_business_table_partials(partial_paths)

    sinks: dict[str, ParquetSink] = {}
    seen: set[str] = set()
    accepted_chunks = accepted_rows = 0
    rejected_chunks = rejected_rows = 0
    try:
        for name in BUSINESS_TABLE_NAMES:
            sinks[name] = ParquetSink(partial_paths[name])

        for chunk in load_accepted_loans(raw_dir=context.raw_dir, chunksize=context.chunksize):
            cleaned, _ = clean_accepted_loans(chunk)
            ids = set(cleaned["loan_id"].astype(str))
            if seen.intersection(ids):
                raise StageValidationError("loan_id bị trùng giữa các accepted chunks.")
            seen.update(ids)
            tables = {
                "loan_application": build_loan_application_table(cleaned),
                "borrower_profile": build_borrower_profile_table(cleaned),
                "credit_profile": build_credit_profile_table(cleaned),
                "loan_pricing": build_loan_pricing_table(cleaned),
                "loan_outcome": build_loan_outcome_table(cleaned),
            }
            for name, table in tables.items():
                sinks[name].write(table)
            accepted_chunks += 1
            accepted_rows += len(cleaned)
            _report_business_table_progress("accepted", accepted_chunks, accepted_rows)
        _report_business_table_progress("accepted", accepted_chunks, accepted_rows, force=True)

        for chunk in load_rejected_loans(raw_dir=context.raw_dir, chunksize=context.chunksize):
            cleaned, _ = clean_rejected_loans(chunk)
            sinks["rejected_applications"].write(build_rejected_applications_table(cleaned))
            rejected_chunks += 1
            rejected_rows += len(cleaned)
            _report_business_table_progress("rejected", rejected_chunks, rejected_rows)
        _report_business_table_progress("rejected", rejected_chunks, rejected_rows, force=True)

        _close_business_table_sinks(sinks)
        _validate_business_table_partials(partial_paths)
        _promote_business_table_partials(partial_paths, final_paths)
    except BaseException:
        try:
            _close_business_table_sinks(sinks)
        except BaseException:
            pass
        _remove_business_table_partials(partial_paths)
        raise

    return {
        "accepted_rows": accepted_rows,
        "rejected_rows": rejected_rows,
        "tables": list(BUSINESS_TABLE_NAMES),
    }


def _stage_04(context: RunnerContext) -> dict[str, Any]:
    result = _write_business_tables(context)
    for name in result["tables"]:
        path = context.interim_dir / f"{name}.parquet"
        if not path.is_file() or path.stat().st_size == 0:
            raise StageValidationError(f"Thiếu business table: {path}")
    return result


def profile_target_statuses(frame: pd.DataFrame) -> dict[str, Any]:
    if "loan_status" not in frame:
        raise ValueError("Fixture/status frame phải có loan_status.")
    status = frame["loan_status"].astype("string")
    target = derive_target(status)
    return {
        "rows": len(frame),
        "status_counts": {str(key): int(value) for key, value in status.fillna("<NA>").value_counts().items()},
        "target_counts": {str(key): int(value) for key, value in target.dropna().value_counts().items()},
        "unresolved_rows": int(target.isna().sum()),
    }


def validate_unique_loan_ids(frame: pd.DataFrame) -> None:
    if "loan_id" not in frame or frame["loan_id"].isna().any() or frame["loan_id"].duplicated().any():
        raise StageValidationError("loan_id phải non-null và unique.")


def _stage_05(context: RunnerContext) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    target_counts: Counter[int] = Counter()
    unresolved = 0
    rows = 0
    seen: set[str] = set()
    reader = load_csv("accepted", raw_dir=context.raw_dir, usecols=["id", "loan_status"], chunksize=context.chunksize)
    for chunk in reader:
        cleaned = chunk.rename(columns={"id": "loan_id"})
        validate_unique_loan_ids(cleaned)
        ids = set(cleaned["loan_id"].astype(str))
        if seen.intersection(ids):
            raise StageValidationError("loan_id bị trùng giữa các chunks.")
        seen.update(ids)
        status = cleaned["loan_status"].astype("string")
        target = derive_target(status)
        counts.update(status.fillna("<NA>").tolist())
        target_counts.update(int(value) for value in target.dropna().tolist())
        unresolved += int(target.isna().sum())
        rows += len(cleaned)
    audit = pd.DataFrame({"loan_status": list(counts), "row_count": list(counts.values())})
    audit["mapped_target"] = audit["loan_status"].map({"Fully Paid": 0, "Charged Off": 1, "Default": 1})
    context.interim_dir.mkdir(parents=True, exist_ok=True)
    audit.to_csv(context.interim_dir / "target_audit.csv", index=False)
    if not target_counts or rows == unresolved:
        raise StageValidationError("Không có accepted loan status nào được map thành final target.")
    return {
        "rows_profiled": rows,
        "status_counts": dict(counts),
        "target_counts": {str(key): value for key, value in target_counts.items()},
        "unresolved_rows_excluded": unresolved,
        "target_audit_path": str(context.interim_dir / "target_audit.csv"),
    }


def _stage_06(context: RunnerContext) -> dict[str, Any]:
    usecols = ["id", "loan_status", "loan_amnt", "annual_inc", "fico_range_low", "fico_range_high", "issue_d", "earliest_cr_line", "dti"]
    rows = labeled = 0
    feature_inf = 0
    dependencies = {feature: [] for feature in ENGINEERED_FEATURES}
    for chunk in load_csv("accepted", raw_dir=context.raw_dir, usecols=usecols, chunksize=context.chunksize):
        cleaned, report = clean_accepted_loans(chunk)
        features, _ = engineer_lending_club_features(cleaned)
        rows += len(features)
        labeled += report["final_labeled_rows"]
        numeric = features.select_dtypes(include=["number"])
        feature_inf += int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum())
    if feature_inf:
        raise StageValidationError("Feature engineering tạo infinity.")
    forbidden_dependencies = [feature for feature in dependencies if classify_column(feature) in {ColumnClass.POST_LOAN, ColumnClass.TARGET_SOURCE}]
    if forbidden_dependencies:
        raise StageValidationError(f"Feature dependency bị cấm: {forbidden_dependencies}")
    return {
        "rows_checked": rows,
        "labeled_rows_available": labeled,
        "features_verified": list(ENGINEERED_FEATURES),
        "infinity_count": feature_inf,
        "post_loan_dependencies": [],
        "target_dependencies": [],
    }


def _stage_07(context: RunnerContext) -> dict[str, Any]:
    required = [context.interim_dir / f"{name}.parquet" for name in ("loan_application", "borrower_profile", "credit_profile", "loan_outcome")]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise StageValidationError(f"Thiếu safe business tables: {missing}")
    final_path = context.processed_dir / "cleaned_dataset.parquet"
    partial_path = context.processed_dir / "cleaned_dataset.partial.parquet"
    context.processed_dir.mkdir(parents=True, exist_ok=True)
    sink = ParquetSink(partial_path)
    rows = labeled = unresolved = 0
    target_counts: Counter[str] = Counter()
    baseline_features: list[str] = []
    seen: set[str] = set()
    try:
        for chunk in load_accepted_loans(raw_dir=context.raw_dir, chunksize=context.chunksize):
            tables = prepare_accepted_batch(chunk)
            ids = set(tables["loan_application"]["loan_id"].astype(str))
            if seen.intersection(ids):
                raise StageValidationError("loan_id bị trùng giữa các accepted chunks khi canonical join.")
            seen.update(ids)
            canonical = tables["canonical_labeled"]
            batch_audit = tables["canonical_audit"]
            baseline_features = batch_audit["baseline_features"]
            gate = batch_audit["leakage_gate"]
            if gate["status"] != "PASS":
                raise StageValidationError(f"LEAKAGE GATE FAIL: {gate}")
            sink.write(canonical)
            rows += batch_audit["input_accepted_rows"]
            labeled += len(canonical)
            unresolved += batch_audit["unresolved_rows"]
            target_counts.update(batch_audit["target_counts"])
    finally:
        sink.close()
    if not partial_path.is_file():
        raise StageValidationError("Canonical partial output is missing.")
    partial_path.replace(final_path)
    return {
        "accepted_rows_seen": rows,
        "resolved_labeled_rows": labeled,
        "unresolved_rows_excluded": unresolved,
        "target_counts": dict(target_counts),
        "baseline_features": baseline_features,
        "path": str(final_path),
        "leakage_gate": "PASS",
        "downstream_artifacts_created": [],
    }


def _iter_parquet_columns(path: Path, columns: list[str], batch_size: int = 100_000) -> Iterator[pd.DataFrame]:
    parquet = _require_pyarrow().ParquetFile(path)
    available = [column for column in columns if column in parquet.schema.names]
    for batch in parquet.iter_batches(batch_size=batch_size, columns=available):
        yield batch.to_pandas()


def _promote_stage08_partials(
    partial_paths: dict[str, Path],
    final_paths: dict[str, Path],
) -> None:
    """Promote DE-LC-08 outputs together and rollback on promotion failure."""

    token = uuid4().hex
    backups: dict[Path, Path] = {}
    promoted: list[Path] = []
    names = ("dim_date", "dim_state", "funnel")
    try:
        for name in names:
            final_path = final_paths[name]
            if final_path.is_file():
                backup_path = final_path.with_name(f".{final_path.name}.{token}.rollback")
                os.replace(final_path, backup_path)
                backups[final_path] = backup_path
        for name in names:
            final_path = final_paths[name]
            os.replace(partial_paths[name], final_path)
            promoted.append(final_path)
    except BaseException:
        for final_path in promoted:
            final_path.unlink(missing_ok=True)
        for final_path, backup_path in backups.items():
            if backup_path.is_file():
                os.replace(backup_path, final_path)
        raise
    else:
        for backup_path in backups.values():
            backup_path.unlink(missing_ok=True)


def _stage_08(context: RunnerContext) -> dict[str, Any]:
    required = [context.interim_dir / name for name in ("loan_application.parquet", "borrower_profile.parquet", "rejected_applications.parquet")]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise StageValidationError(f"Thiếu table cho dimensions/mart: {missing}")
    dates: list[pd.Series] = []
    states: list[pd.Series] = []
    for chunk in _iter_parquet_columns(required[0], ["issue_d"]):
        dates.append(pd.Series(pd.to_datetime(chunk["issue_d"], errors="coerce").dropna().unique()))
    for chunk in _iter_parquet_columns(required[1], ["state_code"]):
        states.append(pd.Series(chunk["state_code"].dropna().unique()))
    for chunk in _iter_parquet_columns(required[2], ["application_date", "state_code"]):
        dates.append(pd.Series(pd.to_datetime(chunk["application_date"], errors="coerce").dropna().unique()))
        states.append(pd.Series(chunk["state_code"].dropna().unique()))
    context.interim_dir.mkdir(parents=True, exist_ok=True)
    date_dim = build_date_dimension(*dates)
    state_dim = build_state_dimension(*states)
    if state_dim["state_code"].duplicated().any() or date_dim["date"].duplicated().any():
        raise StageValidationError("Dimension bị trùng key.")

    final_paths = {
        "dim_date": context.interim_dir / "dim_date.parquet",
        "dim_state": context.interim_dir / "dim_state.parquet",
        "funnel": context.interim_dir / "application_funnel.parquet",
    }
    partial_paths = {
        name: path.with_name(f"{path.stem}.partial{path.suffix}")
        for name, path in final_paths.items()
    }
    for path in partial_paths.values():
        path.unlink(missing_ok=True)
    try:
        date_dim.to_parquet(partial_paths["dim_date"], index=False)
        state_dim.to_parquet(partial_paths["dim_state"], index=False)
        funnel_sink = ParquetSink(partial_paths["funnel"])
        accepted_rows = rejected_rows = 0
        try:
            for raw_chunk in load_accepted_loans(raw_dir=context.raw_dir, chunksize=context.chunksize):
                cleaned, _ = clean_accepted_loans(raw_chunk)
                table = pd.DataFrame({
                    "application_id": cleaned["loan_id"].astype("string"),
                    "application_date": cleaned["issue_d"],
                    "requested_amount": cleaned["loan_amnt"],
                    "state_code": cleaned.get("state_code", pd.Series(pd.NA, index=cleaned.index, dtype="string")),
                    "zip_code": cleaned.get("zip_code", pd.Series(pd.NA, index=cleaned.index, dtype="string")),
                    "purpose": cleaned.get("purpose", pd.Series(pd.NA, index=cleaned.index, dtype="string")),
                    "decision": "accepted",
                })
                if len(table) != len(cleaned):
                    raise StageValidationError("Accepted funnel table làm thay đổi số dòng source.")
                funnel_sink.write(table)
                accepted_rows += len(table)
            rejected_offset = 0
            for raw_chunk in load_rejected_loans(raw_dir=context.raw_dir, chunksize=context.chunksize):
                cleaned, _ = clean_rejected_loans(raw_chunk)
                row_ids = pd.Series(
                    [f"rejected-{rejected_offset + index}" for index in range(len(cleaned))],
                    index=cleaned.index,
                    dtype="string",
                )
                table = pd.DataFrame({
                    "application_id": row_ids,
                    "application_date": cleaned["application_date"],
                    "requested_amount": cleaned["requested_amount"],
                    "state_code": cleaned["state_code"],
                    "zip_code": cleaned["zip_code"],
                    "purpose": cleaned["loan_title"],
                    "decision": "rejected",
                })
                if len(table) != len(cleaned):
                    raise StageValidationError("Rejected funnel table làm thay đổi số dòng source.")
                funnel_sink.write(table)
                rejected_offset += len(table)
                rejected_rows += len(table)
        finally:
            funnel_sink.close()

        expected_counts = {"accepted": accepted_rows, "rejected": rejected_rows}
        actual_counts = _count_funnel_decisions(partial_paths["funnel"])
        if actual_counts != expected_counts:
            raise StageValidationError(
                f"Funnel partial counts không khớp source: expected={expected_counts}, actual={actual_counts}"
            )
        partial_rows = _require_pyarrow().ParquetFile(partial_paths["funnel"]).metadata.num_rows
        if partial_rows != accepted_rows + rejected_rows:
            raise StageValidationError(
                f"Funnel partial total không khớp: expected={accepted_rows + rejected_rows}, actual={partial_rows}"
            )
        _promote_stage08_partials(partial_paths, final_paths)
    except BaseException:
        for path in partial_paths.values():
            path.unlink(missing_ok=True)
        raise
    return {
        "dim_date_path": str(final_paths["dim_date"]),
        "dim_state_path": str(final_paths["dim_state"]),
        "funnel_path": str(final_paths["funnel"]),
        "dim_date_unique_rows": len(date_dim),
        "dim_state_unique_rows": len(state_dim),
        "accepted_funnel_rows": accepted_rows,
        "rejected_funnel_rows": rejected_rows,
    }


def _scan_canonical(path: Path, columns: list[str], batch_size: int) -> dict[str, Any]:
    parquet = _require_pyarrow().ParquetFile(path)
    available = parquet.schema.names
    required = {"loan_id", "target"}
    if not required.issubset(available):
        raise StageValidationError(f"Canonical thiếu cột: {sorted(required - set(available))}")
    scan_columns = [column for column in ["loan_id", "target", "state_code", "issue_d"] if column in available]
    rows = null_ids = duplicate_ids = infinity_count = 0
    target_counts: Counter[str] = Counter()
    seen: set[str] = set()
    state_non_null = date_non_null = 0
    for batch in parquet.iter_batches(batch_size=batch_size, columns=scan_columns):
        frame = batch.to_pandas()
        rows += len(frame)
        ids = frame["loan_id"].astype("string")
        null_ids += int(ids.isna().sum())
        id_values = set(ids.dropna().tolist())
        duplicate_ids += len(seen.intersection(id_values))
        seen.update(id_values)
        target_counts.update(str(value) for value in frame["target"].dropna().tolist())
        if "state_code" in frame:
            state_non_null += int(frame["state_code"].notna().sum())
        if "issue_d" in frame:
            date_non_null += int(pd.to_datetime(frame["issue_d"], errors="coerce").notna().sum())
        numeric = frame.select_dtypes(include=["number"])
        if not numeric.empty:
            infinity_count += int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum())
    return {
        "rows": rows,
        "null_ids": null_ids,
        "duplicate_ids": duplicate_ids,
        "target_counts": dict(target_counts),
        "state_non_null": state_non_null,
        "issue_date_non_null": date_non_null,
        "infinity_count": infinity_count,
        "columns": available,
    }


def _parquet_row_count(path: Path) -> int:
    if not path.is_file():
        raise StageValidationError(f"Thiếu handoff source artifact: {path}")
    metadata = _require_pyarrow().ParquetFile(path).metadata
    if metadata is None:
        raise StageValidationError(f"Không đọc được Parquet metadata: {path}")
    return int(metadata.num_rows)


def _stage_09(context: RunnerContext) -> dict[str, Any]:
    canonical_path = context.processed_dir / "cleaned_dataset.parquet"
    if not canonical_path.is_file():
        raise StageValidationError(f"Thiếu canonical dataset: {canonical_path}")
    scan = _scan_canonical(canonical_path, [], context.chunksize)
    columns = scan["columns"]
    unknown = unknown_columns(columns)
    if unknown:
        raise StageValidationError(f"Dictionary/model handoff bị chặn bởi unknown columns: {unknown}")

    accepted_table_paths = {
        name: context.interim_dir / f"{name}.parquet"
        for name in (
            "loan_application",
            "borrower_profile",
            "credit_profile",
            "loan_pricing",
            "loan_outcome",
        )
    }
    accepted_table_rows = {
        name: _parquet_row_count(path) for name, path in accepted_table_paths.items()
    }
    if len(set(accepted_table_rows.values())) != 1:
        raise StageValidationError(
            f"Accepted business-table row counts không đồng nhất: {accepted_table_rows}"
        )
    accepted_rows = next(iter(accepted_table_rows.values()))
    rejected_path = context.interim_dir / "rejected_applications.parquet"
    rejected_rows = _parquet_row_count(rejected_path)
    labeled_rows = int(scan["rows"])
    unresolved_rows = accepted_rows - labeled_rows
    if unresolved_rows < 0:
        raise StageValidationError(
            f"Canonical rows vượt accepted source rows: accepted={accepted_rows}, labeled={labeled_rows}"
        )

    model_features = approved_model_features(columns)
    gate = run_leakage_gate(pd.DataFrame(columns=columns), model_features)
    forbidden_baseline_features = sorted(gate["not_model_eligible"])
    target_0 = int(scan["target_counts"].get("0", 0))
    target_1 = int(scan["target_counts"].get("1", 0))
    schema = _require_pyarrow().ParquetFile(canonical_path).schema_arrow
    dictionary = pd.DataFrame({
        "column_name": columns,
        "dtype": [str(schema.field(column).type) for column in columns],
        "policy_class": [str(classify_column(column)) for column in columns],
        "model_eligible_default": [classify_column(column).value in {"APPLICATION_TIME", "CREDIT_SNAPSHOT"} for column in columns],
        "canonical_grain": "accepted loan (loan_id)",
    })

    status = "PASS" if (
        accepted_rows > 0
        and rejected_rows > 0
        and labeled_rows > 0
        and accepted_rows == labeled_rows + unresolved_rows
        and target_0 + target_1 == labeled_rows
        and len(columns) == len(dictionary)
        and set(dictionary["column_name"]) == set(columns)
        and scan["null_ids"] == 0
        and scan["duplicate_ids"] == 0
        and set(scan["target_counts"]).issubset({"0", "1"})
        and scan["infinity_count"] == 0
        and gate["status"] == "PASS"
        and not forbidden_baseline_features
    ) else "FAIL"

    dictionary_path = context.processed_dir / "data_dictionary.csv"
    quality_path = context.reports_dir / "data_quality_report.md"
    manifest = {
        "dataset_id": "lending_club_2007_2018",
        "stage": "de-lc-09",
        "run_status": status,
        "stage_status": status,
        "accepted_rows": accepted_rows,
        "rejected_rows": rejected_rows,
        "labeled_rows": labeled_rows,
        "unresolved_rows": unresolved_rows,
        "target_counts": {"0": target_0, "1": target_1},
        "target_0": target_0,
        "target_1": target_1,
        "canonical_columns": len(columns),
        "dictionary_rows": len(dictionary),
        "dictionary_coverage": 1.0 if set(dictionary["column_name"]) == set(columns) else 0.0,
        "baseline_feature_count": len(model_features),
        "baseline_forbidden_features": forbidden_baseline_features,
        "quality_status": status,
        "leakage_gate": gate["status"],
        "canonical_path": str(canonical_path),
        "dictionary_path": str(dictionary_path),
        "quality_report_path": str(quality_path),
        "provenance": {
            "runner": "src.data.tv2_runner",
            "stage": "de-lc-09",
            "dependencies": list(STAGE_DEPENDENCIES["de-lc-09"]),
            "source_artifacts": {
                **{name: str(path) for name, path in accepted_table_paths.items()},
                "rejected_applications": str(rejected_path),
            },
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    }
    manifest_validation = validate_handoff_manifest(
        manifest,
        canonical_columns=columns,
        dictionary_columns=dictionary["column_name"].tolist(),
    )
    audit = {
        "status": status,
        "shape_and_grain": {"rows": scan["rows"], "null_keys": scan["null_ids"], "duplicate_keys": scan["duplicate_ids"]},
        "accepted_rows": accepted_rows,
        "rejected_rows": rejected_rows,
        "labeled_rows": labeled_rows,
        "target_counts": {"0": target_0, "1": target_1},
        "infinity_count": scan["infinity_count"],
        "state_code_coverage": scan["state_non_null"] / scan["rows"] if scan["rows"] else None,
        "issue_date_parse_success": scan["issue_date_non_null"] / scan["rows"] if scan["rows"] else None,
        "dictionary_missing_columns": [],
        "dictionary_coverage": manifest["dictionary_coverage"],
        "baseline_feature_count": len(model_features),
        "excluded_unresolved_status_rows": unresolved_rows,
        "baseline_forbidden_features": forbidden_baseline_features,
        "leakage_gate": gate,
    }

    if status != "PASS" or manifest_validation["status"] != "PASS":
        raise StageValidationError(f"DE-LC-09 handoff validation FAIL: {manifest}")

    context.processed_dir.mkdir(parents=True, exist_ok=True)
    dictionary.to_csv(dictionary_path, index=False)
    context.reports_dir.mkdir(parents=True, exist_ok=True)
    quality_path.write_text(render_quality_report(audit), encoding="utf-8")
    manifest_path = context.processed_dir / "cleaned_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {**manifest, "quality_report_path": str(quality_path)}


def _read_eda_sample(path: Path, limit: int = 200_000) -> pd.DataFrame:
    columns = ["loan_amnt", "dti", "target", "issue_d", "fico_band", "dti_band"]
    frames: list[pd.DataFrame] = []
    rows = 0
    for frame in _iter_parquet_columns(path, columns, batch_size=100_000):
        take = frame.iloc[: max(0, limit - rows)]
        frames.append(take)
        rows += len(take)
        if rows >= limit:
            break
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)


def ordered_eda_categories(values: pd.Series, order: tuple[str, ...]) -> pd.Categorical:
    """Đưa một dimension EDA về thứ tự hiển thị cố định."""

    return pd.Categorical(values, categories=list(order), ordered=True)


def prepare_dti_boxplot_data(
    frame: pd.DataFrame,
    percentile: float = 0.99,
) -> tuple[pd.DataFrame, float]:
    """Chuẩn bị DTI cho boxplot mà không mutate canonical source frame."""

    if not 0 < percentile <= 1:
        raise ValueError("percentile phải nằm trong khoảng (0, 1].")
    required = {"dti", "target"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Thiếu cột cho DTI boxplot: {missing}")
    dti = pd.to_numeric(frame["dti"], errors="coerce")
    target = pd.to_numeric(frame["target"], errors="coerce")
    valid = dti.notna() & target.isin([0, 1])
    result = pd.DataFrame({"dti": dti.loc[valid], "target": target.loc[valid]}).copy()
    result["target_label"] = result["target"].map({0: "Non-default", 1: "Default"})
    cap = float(result["dti"].quantile(percentile)) if not result.empty else float("nan")
    return result, cap


def mask_sparse_heatmap_cells(
    default_rates: pd.DataFrame,
    cell_counts: pd.DataFrame,
    minimum_count: int = HEATMAP_MIN_CELL_COUNT,
) -> pd.DataFrame:
    """Ẩn rate của các ô có ít hơn ``minimum_count`` quan sát."""

    if minimum_count < 1:
        raise ValueError("minimum_count phải lớn hơn 0.")
    return default_rates.where(cell_counts >= minimum_count)


def mask_sparse_fico_groups(
    fico_table: pd.DataFrame,
    minimum_count: int = FICO_MIN_GROUP_COUNT,
) -> pd.DataFrame:
    """Ẩn rate của FICO band có ít quan sát nhưng vẫn giữ category."""

    required = {"band", "count", "default_rate"}
    missing = sorted(required - set(fico_table.columns))
    if missing:
        raise ValueError(f"Thiếu cột cho FICO group masking: {missing}")
    if minimum_count < 1:
        raise ValueError("minimum_count phải lớn hơn 0.")
    result = fico_table.copy()
    result["insufficient_sample"] = result["count"] < minimum_count
    result["display_rate"] = result["default_rate"].where(~result["insufficient_sample"])
    return result


def aggregate_accepted_volume_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp số accepted loan theo tháng chỉ từ issue_d."""

    if "issue_d" not in frame:
        raise ValueError("Thiếu cột cho accepted-volume aggregation: ['issue_d']")
    dates = pd.to_datetime(frame["issue_d"], format="mixed", errors="coerce")
    valid = dates.notna()
    if not valid.any():
        return pd.DataFrame(columns=["year_month", "accepted_loan_count"])
    result = (
        dates.loc[valid]
        .dt.to_period("M")
        .dt.to_timestamp()
        .value_counts()
        .rename_axis("year_month")
        .rename("accepted_loan_count")
        .sort_index()
        .reset_index()
    )
    return result


def _aggregate_accepted_volume_from_parquet(path: Path) -> pd.DataFrame:
    """Đọc toàn bộ accepted loan_application theo chunk để tính volume tháng."""

    counts: Counter[pd.Timestamp] = Counter()
    for frame in _iter_parquet_columns(path, ["issue_d"], batch_size=100_000):
        metrics = aggregate_accepted_volume_metrics(frame)
        counts.update({row.year_month: int(row.accepted_loan_count) for row in metrics.itertuples(index=False)})
    rows = [
        {"year_month": year_month, "accepted_loan_count": count}
        for year_month, count in sorted(counts.items())
    ]
    return pd.DataFrame(rows, columns=["year_month", "accepted_loan_count"])


def aggregate_time_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp count/default rate theo tháng và sắp xếp theo thời gian."""

    required = {"issue_d", "target"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Thiếu cột cho time aggregation: {missing}")
    dates = pd.to_datetime(frame["issue_d"], format="mixed", errors="coerce")
    target = pd.to_numeric(frame["target"], errors="coerce")
    valid = dates.notna() & target.isin([0, 1])
    if not valid.any():
        return pd.DataFrame(columns=["year_month", "loan_count", "default_count", "default_rate"])
    grouped = pd.DataFrame({
        "year_month": dates.loc[valid].dt.to_period("M").dt.to_timestamp(),
        "target": target.loc[valid],
    }).groupby("year_month", sort=True, observed=True)["target"].agg(["count", "sum"])
    result = grouped.rename(columns={"count": "loan_count", "sum": "default_count"}).reset_index()
    result["default_rate"] = result["default_count"] / result["loan_count"]
    return result


def _metrics_frame(
    metrics: dict[str, list[int]],
    order: tuple[str, ...],
) -> pd.DataFrame:
    rows = []
    for key in order:
        count, default_count = metrics.get(key, [0, 0])
        rows.append({
            "band": key,
            "count": count,
            "default_count": default_count,
            "default_rate": default_count / count if count else np.nan,
        })
    return pd.DataFrame(rows)


def _aggregate_full_eda_metrics(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Tính FICO/DTI/time metrics từ toàn bộ canonical theo chunk."""

    fico_metrics: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
    heatmap_metrics: defaultdict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    time_metrics: defaultdict[pd.Timestamp, list[int]] = defaultdict(lambda: [0, 0])
    columns = ["target", "fico_band", "dti_band", "issue_d"]
    for frame in _iter_parquet_columns(path, columns, batch_size=100_000):
        target = pd.to_numeric(frame["target"], errors="coerce")
        valid_target = target.isin([0, 1])
        if not valid_target.any():
            continue
        valid = pd.DataFrame({
            "target": target.loc[valid_target],
            "fico_band": frame.loc[valid_target, "fico_band"].astype("string"),
            "dti_band": frame.loc[valid_target, "dti_band"].astype("string"),
            "issue_d": pd.to_datetime(frame.loc[valid_target, "issue_d"], format="mixed", errors="coerce"),
        })
        fico_grouped = valid.dropna(subset=["fico_band"]).groupby("fico_band", observed=True)["target"].agg(["count", "sum"])
        for band, row in fico_grouped.iterrows():
            values = fico_metrics[str(band)]
            values[0] += int(row["count"])
            values[1] += int(row["sum"])
        heatmap_grouped = valid.dropna(subset=["fico_band", "dti_band"]).groupby(
            ["fico_band", "dti_band"], observed=True
        )["target"].agg(["count", "sum"])
        for (fico_band, dti_band), row in heatmap_grouped.iterrows():
            values = heatmap_metrics[(str(fico_band), str(dti_band))]
            values[0] += int(row["count"])
            values[1] += int(row["sum"])
        dated = valid.dropna(subset=["issue_d"]).assign(
            year_month=valid.loc[valid["issue_d"].notna(), "issue_d"].dt.to_period("M").dt.to_timestamp()
        )
        time_grouped = dated.groupby("year_month", observed=True)["target"].agg(["count", "sum"])
        for year_month, row in time_grouped.iterrows():
            values = time_metrics[year_month]
            values[0] += int(row["count"])
            values[1] += int(row["sum"])

    fico_table = _metrics_frame(dict(fico_metrics), FICO_BAND_ORDER)
    counts = pd.DataFrame(0, index=FICO_BAND_ORDER, columns=DTI_BAND_ORDER, dtype="int64")
    defaults = pd.DataFrame(0, index=FICO_BAND_ORDER, columns=DTI_BAND_ORDER, dtype="int64")
    for (fico_band, dti_band), (count, default_count) in heatmap_metrics.items():
        if fico_band in counts.index and dti_band in counts.columns:
            counts.loc[fico_band, dti_band] = count
            defaults.loc[fico_band, dti_band] = default_count
    rates = defaults.astype("float64").div(counts.replace(0, np.nan))
    heatmap_table = rates
    heatmap_table.attrs["counts"] = counts

    time_rows = []
    for year_month in sorted(time_metrics):
        count, default_count = time_metrics[year_month]
        time_rows.append({
            "year_month": year_month,
            "loan_count": count,
            "default_count": default_count,
            "default_rate": default_count / count if count else np.nan,
        })
    time_table = pd.DataFrame(time_rows, columns=["year_month", "loan_count", "default_count", "default_rate"])
    return fico_table, heatmap_table, time_table


def _count_funnel_decisions(funnel_path: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    parquet = _require_pyarrow().ParquetFile(funnel_path)
    for batch in parquet.iter_batches(batch_size=100_000, columns=["decision"]):
        counts.update(str(value) for value in batch.column(0).to_pylist())
    return {"accepted": counts.get("accepted", 0), "rejected": counts.get("rejected", 0)}


def _audit_funnel_counts(context: RunnerContext, funnel_path: Path) -> dict[str, Any]:
    """Đếm decision trong funnel và đối chiếu raw row counts từ DE-LC-02."""

    actual = _count_funnel_decisions(funnel_path)
    marker = _read_marker(context, "de-lc-02") or {}
    expected_payload = marker.get("payload", {})
    expected = {
        "accepted": expected_payload.get("accepted_rows_checked"),
        "rejected": expected_payload.get("rejected_rows_checked"),
    }
    comparable = all(value is not None for value in expected.values())
    matches = comparable and actual == {key: int(value) for key, value in expected.items()}
    return {
        "status": "PASS" if matches else "FAIL" if comparable else "NOT_AVAILABLE",
        "expected_raw_rows": expected,
        "actual_funnel_rows": actual,
        "difference": {
            key: actual[key] - int(expected[key]) if expected[key] is not None else None
            for key in actual
        },
        "note": "Funnel counts không khớp DE-LC-02." if not matches else "Funnel counts khớp DE-LC-02.",
    }


def _stage_10(context: RunnerContext) -> dict[str, Any]:
    canonical_path = context.processed_dir / "cleaned_dataset.parquet"
    loan_application_path = context.interim_dir / "loan_application.parquet"
    funnel_path = context.interim_dir / "application_funnel.parquet"
    if not canonical_path.is_file() or not loan_application_path.is_file() or not funnel_path.is_file():
        raise StageValidationError(
            "DE-LC-10 cần canonical dataset, loan_application.parquet và application_funnel.parquet."
        )
    parquet_columns = set(_require_pyarrow().ParquetFile(canonical_path).schema.names)
    required_columns = {"loan_amnt", "dti", "target", "issue_d", "fico_band", "dti_band"}
    missing_columns = sorted(required_columns - parquet_columns)
    if missing_columns:
        raise StageValidationError(f"Canonical thiếu cột cho DE-LC-10: {missing_columns}")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    sample = _read_eda_sample(canonical_path, limit=EDA_SAMPLE_LIMIT)
    if sample.empty:
        raise StageValidationError("Canonical dataset không có dòng để EDA.")
    fico_table, heatmap_rates, _ = _aggregate_full_eda_metrics(canonical_path)
    accepted_volume_table = _aggregate_accepted_volume_from_parquet(loan_application_path)
    if fico_table["count"].sum() == 0 or accepted_volume_table.empty:
        raise StageValidationError("Không đủ dữ liệu để tạo DE-LC-10.")

    figure_dir = context.reports_dir / "figures" / "eda"
    figure_dir.mkdir(parents=True, exist_ok=True)
    obsolete_names = (
        "eda_01_loan_amount.png",
        "eda_02_annual_income.png",
        "eda_04_default_by_purpose.png",
        "eda_05_accepted_rejected.png",
        "eda_05_loan_volume_default_rate_over_time.png",
    )
    for name in obsolete_names:
        (figure_dir / name).unlink(missing_ok=True)

    figure_paths = {name: figure_dir / name for name in EDA_FIGURE_NAMES}
    figures: list[str] = []

    def save_figure(name: str, figure: Any) -> None:
        path = figure_paths[name]
        figure.tight_layout()
        figure.savefig(path, dpi=140)
        plt.close(figure)
        figures.append(str(path))

    loan_amounts = pd.to_numeric(sample["loan_amnt"], errors="coerce").dropna()
    if loan_amounts.empty:
        raise StageValidationError("Không có loan_amnt hợp lệ cho EDA-01.")
    figure, axis = plt.subplots(figsize=(8.5, 4.8))
    axis.hist(loan_amounts, bins=40, color="#4472C4", edgecolor="white")
    axis.set_title("Loan Amount Distribution")
    axis.set_xlabel("Loan amount")
    axis.set_ylabel("Count")
    axis.xaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    save_figure("eda_01_loan_amount_distribution.png", figure)

    dti_plot, dti_cap = prepare_dti_boxplot_data(sample)
    if dti_plot.empty or not np.isfinite(dti_cap):
        raise StageValidationError("Không có DTI hợp lệ cho EDA-02.")
    figure, axis = plt.subplots(figsize=(7.5, 4.8))
    groups = [dti_plot.loc[dti_plot["target"] == target, "dti"] for target in (0, 1)]
    axis.boxplot(groups, tick_labels=["Non-default", "Default"], showfliers=False, patch_artist=True,
                 boxprops={"facecolor": "#9DC3E6"}, medianprops={"color": "#C00000", "linewidth": 2})
    axis.set_title(f"DTI Distribution by Target\nDisplay limited to valid DTI values up to P99 = {dti_cap:.2f} for readability")
    axis.set_xlabel("Loan outcome")
    axis.set_ylabel(EDA_02_DTI_Y_LABEL)
    axis.set_ylim(top=dti_cap)
    save_figure("eda_02_dti_by_target.png", figure)

    present_fico = mask_sparse_fico_groups(fico_table).loc[fico_table["count"] > 0].copy()
    figure, axis = plt.subplots(figsize=(8, 4.8))
    positions = np.arange(len(present_fico))
    bars = axis.bar(positions, present_fico["display_rate"], color="#70AD47")
    axis.set_title("Observed Default Rate by FICO Band")
    axis.set_xlabel("FICO band")
    axis.set_ylabel("Default rate")
    axis.set_xticks(positions, labels=present_fico["band"])
    axis.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    valid_rates = present_fico["display_rate"].dropna()
    annotation_y = max(float(valid_rates.max()) * 0.5 if not valid_rates.empty else 0.0, 0.02)
    for position, bar, (_, row) in zip(positions, bars, present_fico.iterrows()):
        if bool(row["insufficient_sample"]):
            axis.text(position, annotation_y, f"Insufficient sample\n(n={int(row['count']):,})",
                      ha="center", va="center", fontsize=8, color="#7F6000")
        else:
            axis.annotate(f"n={int(row['count']):,}", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                          xytext=(0, 5), textcoords="offset points", ha="center", fontsize=8)
    save_figure("eda_03_default_by_fico.png", figure)

    heatmap_counts = heatmap_rates.attrs["counts"]
    display_rates = mask_sparse_heatmap_cells(heatmap_rates, heatmap_counts)
    figure, axis = plt.subplots(figsize=(8.5, 5.5))
    display_array = display_rates.to_numpy(dtype=float)
    finite_rates = display_array[np.isfinite(display_array)]
    vmax = max(0.01, float(finite_rates.max())) if finite_rates.size else 1.0
    masked = np.ma.masked_invalid(display_array)
    image = axis.imshow(masked, cmap="YlOrRd", vmin=0, vmax=vmax)
    axis.set_title("Observed Default Rate: FICO Band × DTI Band")
    axis.set_xlabel("DTI band")
    axis.set_ylabel("FICO band")
    axis.set_xticks(range(len(DTI_BAND_ORDER)), labels=DTI_BAND_ORDER)
    axis.set_yticks(range(len(FICO_BAND_ORDER)), labels=FICO_BAND_ORDER)
    figure.colorbar(image, ax=axis, format=mticker.PercentFormatter(1.0), label="Default rate")
    for row_index, fico_band in enumerate(FICO_BAND_ORDER):
        for column_index, dti_band in enumerate(DTI_BAND_ORDER):
            value = display_rates.loc[fico_band, dti_band]
            if pd.notna(value):
                axis.text(column_index, row_index, f"{value:.1%}\n(n={int(heatmap_counts.loc[fico_band, dti_band]):,})",
                          ha="center", va="center", fontsize=7)
    save_figure("eda_04_fico_dti_heatmap.png", figure)

    figure, axis = plt.subplots(figsize=(10, 4.8))
    dates = accepted_volume_table["year_month"]
    axis.plot(dates, accepted_volume_table["accepted_loan_count"], color="#4472C4", linewidth=1.8)
    axis.set_title("Accepted Loan Volume Over Time")
    axis.set_xlabel("Origination month")
    axis.set_ylabel("Accepted loan count")
    axis.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=12))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    figure.autofmt_xdate()
    save_figure("eda_05_accepted_loan_volume_over_time.png", figure)

    if len(figures) != len(EDA_FIGURE_NAMES):
        raise StageValidationError(f"DE-LC-10 phải tạo đúng 5 figures, hiện có {len(figures)}.")

    funnel_audit = _audit_funnel_counts(context, funnel_path)
    report_path = context.reports_dir / "eda_report.md"
    report_path.write_text(
        "# Static EDA — Lending Club\n\n"
        "## Output summary\n\n"
        f"Canonical source: `{canonical_path}`. EDA-01 và EDA-02 dùng deterministic plotting sample tối đa `{EDA_SAMPLE_LIMIT:,}` rows; "
        "EDA-03 và EDA-04 dùng aggregated metrics từ toàn bộ canonical labeled dataset theo chunk. "
        f"EDA-05 dùng toàn bộ accepted loans từ `{loan_application_path}` theo chunk.\n\n"
        "## Visual reasoning\n\n"
        "### EDA-01 — Loan Amount Distribution (Histogram)\n"
        "- BUSINESS QUESTION: Khoản vay tập trung ở những khoảng giá trị nào?\n"
        "- WHY THIS VISUAL: Histogram phù hợp để xem phân bố và vùng loan amount phổ biến.\n"
        "- INSIGHT: Candidate insight — kiểm tra vùng tập trung và độ lệch của loan amount; không suy ra nguyên nhân.\n"
        "- STORY CONNECTION: Overview → portfolio composition → risk segmentation.\n\n"
        "### EDA-02 — DTI by Target (Boxplot)\n"
        "- BUSINESS QUESTION: Phân bố DTI của non-default và default khác nhau thế nào?\n"
        "- WHY THIS VISUAL: Boxplot so sánh median, spread và outlier pattern giữa hai target group.\n"
        "- INSIGHT: Candidate insight — kiểm tra association giữa DTI và observed target; không diễn giải thành causation.\n"
        "- NOTE: Trục y dùng `DTI (%)`; display limited to valid DTI values up to P99 = 38.35 for readability; source values không đổi.\n"
        "- STORY CONNECTION: Portfolio overview → borrower/credit segmentation → risk.\n\n"
        "### EDA-03 — Default Rate by FICO Band (Bar chart)\n"
        "- BUSINESS QUESTION: Observed default rate thay đổi thế nào theo FICO band?\n"
        "- WHY THIS VISUAL: Bar chart giữ thứ tự FICO logic và cho phép so sánh rate giữa các band.\n"
        "- INSIGHT: Candidate insight — kiểm tra association giữa FICO band và observed default rate; count được ghi trên chart.\n"
        f"- LIMITATION: FICO group có n < {FICO_MIN_GROUP_COUNT} được giữ category nhưng hiển thị NA/insufficient sample, không vẽ numerical rate.\n"
        "- STORY CONNECTION: Credit segmentation → risk comparison → model feature context.\n\n"
        "### EDA-04 — FICO × DTI Risk Matrix (Heatmap)\n"
        "- BUSINESS QUESTION: Các tổ hợp FICO band và DTI band có observed default rate như thế nào?\n"
        "- WHY THIS VISUAL: Heatmap cho thấy pattern hai chiều mà từng biểu đồ một chiều có thể bỏ sót.\n"
        "- INSIGHT: Candidate insight — kiểm tra joint association; ô dưới minimum count được để trống để tránh diễn giải sparse cell.\n"
        "- STORY CONNECTION: Segmentation → risk matrix → candidate dashboard drill-down.\n\n"
        "### EDA-05 — Accepted Loan Volume Over Time (Line chart)\n"
        "- BUSINESS QUESTION: Số khoản vay accepted/issued thay đổi theo tháng như thế nào?\n"
        "- SOURCE / AGGREGATION: Toàn bộ accepted loans từ `loan_application.parquet`, group theo `issue_d` year-month, đếm accepted loan.\n"
        "- WHY THIS VISUAL: Line chart thể hiện thứ tự thời gian và volume theo một trục y đơn giản.\n"
        "- INSIGHT: Candidate insight — kiểm tra pattern volume theo thời gian; không suy ra nguyên nhân từ trend.\n"
        "- LIMITATION: Đây chỉ là volume accepted; figure không vẽ default rate vì canonical labeled chỉ chứa resolved outcomes.\n"
        "- STORY CONNECTION: Overview → temporal portfolio context → downstream risk analysis.\n\n"
        "## Technical limits and audit\n\n"
        f"- DTI y-axis: `{EDA_02_DTI_Y_LABEL}`; P99 visualization cap = `{dti_cap:.2f}`.\n"
        f"- FICO minimum group count: `{FICO_MIN_GROUP_COUNT}`; heatmap minimum cell count: `{HEATMAP_MIN_CELL_COUNT}`.\n"
        f"- FICO counts by band: `{json.dumps({row['band']: int(row['count']) for _, row in fico_table.iterrows()}, ensure_ascii=False)}`.\n"
        f"- Accepted-volume aggregation: `{accepted_volume_table['year_month'].min().strftime('%Y-%m')}` → `{accepted_volume_table['year_month'].max().strftime('%Y-%m')}` from all rows in `loan_application.parquet`; it does not use resolved-only canonical rows.\n"
        "- Default rate over origination time was intentionally not included in the canonical static time-series figure because the labeled canonical dataset contains only resolved outcomes; recent vintages have incomplete outcome resolution and would create maturity/selection bias.\n"
        f"- Funnel audit: `{json.dumps(funnel_audit, ensure_ascii=False)}`.\n\n"
        "## Canonical figures\n\n"
        + "\n".join(f"- `{path}`" for path in figures)
        + "\n",
        encoding="utf-8",
    )
    return {
        "figures": figures,
        "figure_count": len(figures),
        "figure_names": list(EDA_FIGURE_NAMES),
        "eda_sample_rows": len(sample),
        "dti_display_cap_99th_percentile": dti_cap,
        "heatmap_min_cell_count": HEATMAP_MIN_CELL_COUNT,
        "funnel_audit": funnel_audit,
        "report_path": str(report_path),
    }


STAGE_FUNCTIONS = {
    "de-lc-01": _stage_01,
    "de-lc-02": _stage_02,
    "de-lc-03": _stage_03,
    "de-lc-04": _stage_04,
    "de-lc-05": _stage_05,
    "de-lc-06": _stage_06,
    "de-lc-07": _stage_07,
    "de-lc-08": _stage_08,
    "de-lc-09": _stage_09,
    "de-lc-10": _stage_10,
}


def run_stage(
    stage: str,
    *,
    raw_dir: str | Path | None = None,
    reports_dir: str | Path = REPORTS_DIR,
    interim_dir: str | Path = INTERIM_DIR,
    processed_dir: str | Path = PROCESSED_DIR,
    chunksize: int = 100_000,
) -> StageResult:
    normalized = normalize_stage(stage)
    context = RunnerContext(
        raw_dir=Path(raw_dir) if raw_dir is not None else Path(REPORTS_DIR).parents[0] / "data" / "raw",
        reports_dir=Path(reports_dir),
        interim_dir=Path(interim_dir),
        processed_dir=Path(processed_dir),
        chunksize=chunksize,
    )
    return _run_with_status(context, normalized, STAGE_FUNCTIONS[normalized])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one gated TV2 Lending Club data-engineering stage.")
    parser.add_argument("--stage", required=True, help="One of de-lc-01 ... de-lc-10")
    parser.add_argument("--raw-dir", default=None, help="Optional raw directory for local fixture/testing")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--interim-dir", default=str(INTERIM_DIR))
    parser.add_argument("--processed-dir", default=str(PROCESSED_DIR))
    parser.add_argument("--chunksize", type=int, default=100_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = run_stage(
            args.stage,
            raw_dir=args.raw_dir,
            reports_dir=args.reports_dir,
            interim_dir=args.interim_dir,
            processed_dir=args.processed_dir,
            chunksize=args.chunksize,
        )
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({
        "stage": result.stage,
        "status": result.status,
        "report_path": str(result.report_path),
        "marker_path": str(result.marker_path),
        "message": result.message,
    }, ensure_ascii=False))
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[result.status]


if __name__ == "__main__":
    raise SystemExit(main())
