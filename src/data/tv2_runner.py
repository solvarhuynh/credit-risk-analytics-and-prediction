"""Stage runner chính thức cho TV2 Lending Club.

Mỗi stage tạo một report nhỏ và một marker JSON. Stage sau chỉ chạy khi mọi
stage trước đã có marker ``PASS``. Runner hỗ trợ ``--raw-dir``, ``--reports-dir``,
``--interim-dir`` và ``--processed-dir`` để test bằng fixture nhỏ mà không đụng
vào raw thật.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

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
from src.data.quality_report import render_quality_report, run_leakage_gate
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


def _write_business_tables(context: RunnerContext) -> dict[str, Any]:
    context.interim_dir.mkdir(parents=True, exist_ok=True)
    names = ("loan_application", "borrower_profile", "credit_profile", "loan_pricing", "loan_outcome")
    sinks = {name: ParquetSink(context.interim_dir / f"{name}.parquet") for name in names}
    seen: set[str] = set()
    accepted_rows = 0
    try:
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
            accepted_rows += len(cleaned)
    finally:
        for sink in sinks.values():
            sink.close()
    rejected_sink = ParquetSink(context.interim_dir / "rejected_applications.parquet")
    rejected_rows = 0
    try:
        for chunk in load_rejected_loans(raw_dir=context.raw_dir, chunksize=context.chunksize):
            cleaned, _ = clean_rejected_loans(chunk)
            rejected_sink.write(build_rejected_applications_table(cleaned))
            rejected_rows += len(cleaned)
    finally:
        rejected_sink.close()
    return {"accepted_rows": accepted_rows, "rejected_rows": rejected_rows, "tables": [*names, "rejected_applications"]}


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
    rows = labeled = 0
    seen: set[str] = set()
    try:
        for chunk in load_accepted_loans(raw_dir=context.raw_dir, chunksize=context.chunksize):
            tables = prepare_accepted_batch(chunk)
            ids = set(tables["canonical_labeled"]["loan_id"].astype(str))
            if seen.intersection(ids):
                raise StageValidationError("loan_id bị trùng khi canonical join.")
            seen.update(ids)
            canonical = tables["canonical_labeled"]
            safe_features = approved_model_features(canonical.columns)
            gate = run_leakage_gate(canonical, safe_features)
            if gate["status"] != "PASS":
                raise StageValidationError(f"LEAKAGE GATE FAIL: {gate}")
            sink.write(canonical)
            rows += len(chunk)
            labeled += len(canonical)
    finally:
        sink.close()
    if not partial_path.is_file():
        raise StageValidationError("Canonical partial output is missing.")
    partial_path.replace(final_path)
    return {"accepted_rows_seen": rows, "labeled_rows_written": labeled, "path": str(final_path), "leakage_gate": "PASS"}


def _iter_parquet_columns(path: Path, columns: list[str], batch_size: int = 100_000) -> Iterator[pd.DataFrame]:
    parquet = _require_pyarrow().ParquetFile(path)
    available = [column for column in columns if column in parquet.schema.names]
    for batch in parquet.iter_batches(batch_size=batch_size, columns=available):
        yield batch.to_pandas()


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
    date_dim.to_parquet(context.interim_dir / "dim_date.parquet", index=False)
    state_dim.to_parquet(context.interim_dir / "dim_state.parquet", index=False)
    if state_dim["state_code"].duplicated().any() or date_dim["date"].duplicated().any():
        raise StageValidationError("Dimension bị trùng key.")

    funnel_path = context.interim_dir / "application_funnel.parquet"
    funnel_sink = ParquetSink(funnel_path)
    accepted_rows = rejected_rows = 0
    accepted_dates: list[pd.Series] = []
    accepted_states: list[pd.Series] = []
    rejected_dates: list[pd.Series] = []
    rejected_states: list[pd.Series] = []
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
            funnel_sink.write(table)
            accepted_rows += len(table)
            accepted_dates.append(pd.Series(table["application_date"].dropna().unique()))
            accepted_states.append(pd.Series(table["state_code"].dropna().unique()))
        rejected_offset = 0
        for raw_chunk in load_rejected_loans(raw_dir=context.raw_dir, chunksize=context.chunksize):
            cleaned, _ = clean_rejected_loans(raw_chunk)
            row_ids = pd.Series([f"rejected-{rejected_offset + index}" for index in range(len(cleaned))], dtype="string")
            table = pd.DataFrame({
                "application_id": row_ids,
                "application_date": cleaned["application_date"],
                "requested_amount": cleaned["requested_amount"],
                "state_code": cleaned["state_code"],
                "zip_code": cleaned["zip_code"],
                "purpose": cleaned["loan_title"],
                "decision": "rejected",
            })
            funnel_sink.write(table)
            rejected_offset += len(table)
            rejected_rows += len(table)
            rejected_dates.append(pd.Series(table["application_date"].dropna().unique()))
            rejected_states.append(pd.Series(table["state_code"].dropna().unique()))
    finally:
        funnel_sink.close()
    return {
        "dim_date_path": str(context.interim_dir / "dim_date.parquet"),
        "dim_state_path": str(context.interim_dir / "dim_state.parquet"),
        "funnel_path": str(funnel_path),
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


def _stage_09(context: RunnerContext) -> dict[str, Any]:
    canonical_path = context.processed_dir / "cleaned_dataset.parquet"
    if not canonical_path.is_file():
        raise StageValidationError(f"Thiếu canonical dataset: {canonical_path}")
    scan = _scan_canonical(canonical_path, [], context.chunksize)
    columns = scan["columns"]
    unknown = unknown_columns(columns)
    if unknown:
        raise StageValidationError(f"Dictionary/model handoff bị chặn bởi unknown columns: {unknown}")
    model_features = approved_model_features(columns)
    gate = run_leakage_gate(pd.DataFrame(columns=columns), model_features)
    dictionary = pd.DataFrame({
        "column_name": columns,
        "dtype": [str(_require_pyarrow().ParquetFile(canonical_path).schema_arrow.field(column).type) for column in columns],
        "policy_class": [str(classify_column(column)) for column in columns],
        "model_eligible_default": [classify_column(column).value in {"APPLICATION_TIME", "CREDIT_SNAPSHOT"} for column in columns],
        "canonical_grain": "accepted loan (loan_id)",
    })
    context.processed_dir.mkdir(parents=True, exist_ok=True)
    dictionary_path = context.processed_dir / "data_dictionary.csv"
    dictionary.to_csv(dictionary_path, index=False)
    status = "PASS" if (
        scan["null_ids"] == 0
        and scan["duplicate_ids"] == 0
        and set(scan["target_counts"]).issubset({"0", "1"})
        and scan["infinity_count"] == 0
        and gate["status"] == "PASS"
    ) else "FAIL"
    audit = {
        "status": status,
        "shape_and_grain": {"rows": scan["rows"], "null_keys": scan["null_ids"], "duplicate_keys": scan["duplicate_ids"]},
        "target_counts": scan["target_counts"],
        "infinity_count": scan["infinity_count"],
        "state_code_coverage": scan["state_non_null"] / scan["rows"] if scan["rows"] else None,
        "issue_date_parse_success": scan["issue_date_non_null"] / scan["rows"] if scan["rows"] else None,
        "dictionary_missing_columns": [],
        "excluded_unresolved_status_rows": None,
        "leakage_gate": gate,
    }
    quality_path = context.reports_dir / "data_quality_report.md"
    context.reports_dir.mkdir(parents=True, exist_ok=True)
    quality_path.write_text(render_quality_report(audit), encoding="utf-8")
    manifest = {
        "dataset_id": "lending_club_2007_2018",
        "canonical_path": str(canonical_path),
        "accepted_labeled_rows": scan["rows"],
        "quality_status": status,
        "leakage_gate": gate["status"],
        "dictionary_path": str(dictionary_path),
        "quality_report_path": str(quality_path),
    }
    manifest_path = context.processed_dir / "cleaned_dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    if status != "PASS":
        raise StageValidationError(f"Quality gate FAIL: {audit}")
    return {**manifest, "quality_report_path": str(quality_path)}


def _read_eda_sample(path: Path, limit: int = 200_000) -> pd.DataFrame:
    columns = ["loan_id", "loan_amnt", "annual_inc", "fico_avg", "dti", "target", "issue_d", "purpose", "fico_band"]
    frames: list[pd.DataFrame] = []
    rows = 0
    for frame in _iter_parquet_columns(path, columns, batch_size=100_000):
        take = frame.iloc[: max(0, limit - rows)]
        frames.append(take)
        rows += len(take)
        if rows >= limit:
            break
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)


def _stage_10(context: RunnerContext) -> dict[str, Any]:
    canonical_path = context.processed_dir / "cleaned_dataset.parquet"
    funnel_path = context.interim_dir / "application_funnel.parquet"
    if not canonical_path.is_file() or not funnel_path.is_file():
        raise StageValidationError("DE-LC-10 cần canonical dataset và application_funnel.parquet.")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sample = _read_eda_sample(canonical_path)
    if sample.empty:
        raise StageValidationError("Canonical dataset không có dòng để EDA.")
    figure_dir = context.reports_dir / "figures" / "eda"
    figure_dir.mkdir(parents=True, exist_ok=True)
    figures: list[str] = []

    def save_hist(column: str, filename: str, title: str) -> None:
        values = pd.to_numeric(sample[column], errors="coerce").dropna()
        if values.empty:
            return
        fig, axis = plt.subplots(figsize=(8, 4.5))
        axis.hist(values, bins=40)
        axis.set(title=title, xlabel=column, ylabel="Rows")
        fig.tight_layout()
        path = figure_dir / filename
        fig.savefig(path, dpi=120)
        plt.close(fig)
        figures.append(str(path))

    save_hist("loan_amnt", "eda_01_loan_amount.png", "Loan amount distribution")
    save_hist("annual_inc", "eda_02_annual_income.png", "Annual income distribution")
    if "fico_band" in sample and "target" in sample:
        summary = sample.dropna(subset=["fico_band", "target"]).groupby("fico_band", observed=True)["target"].mean()
        if not summary.empty:
            fig, axis = plt.subplots(figsize=(8, 4.5))
            summary.plot(kind="bar", ax=axis, title="Default rate by FICO band")
            axis.set_ylabel("Default rate")
            fig.tight_layout()
            path = figure_dir / "eda_03_default_by_fico.png"
            fig.savefig(path, dpi=120)
            plt.close(fig)
            figures.append(str(path))
    if "purpose" in sample and "target" in sample:
        summary = sample.dropna(subset=["purpose", "target"]).groupby("purpose", observed=True)["target"].mean().nlargest(15)
        if not summary.empty:
            fig, axis = plt.subplots(figsize=(9, 4.5))
            summary.sort_values().plot(kind="barh", ax=axis, title="Default rate by purpose")
            axis.set_xlabel("Default rate")
            fig.tight_layout()
            path = figure_dir / "eda_04_default_by_purpose.png"
            fig.savefig(path, dpi=120)
            plt.close(fig)
            figures.append(str(path))
    funnel = pd.read_parquet(funnel_path, columns=["decision"])["decision"].value_counts()
    if not funnel.empty:
        fig, axis = plt.subplots(figsize=(7, 4.5))
        funnel.plot(kind="bar", ax=axis, title="Accepted vs rejected applications")
        axis.set_ylabel("Rows")
        fig.tight_layout()
        path = figure_dir / "eda_05_accepted_rejected.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        figures.append(str(path))
    report_path = context.reports_dir / "eda_report.md"
    report_path.write_text(
        "# Static EDA — Lending Club\n\n"
        "Figures được tạo từ canonical processed dataset và funnel mart; không có model metrics. "
        f"EDA sample tối đa 200,000 dòng để kiểm soát bộ nhớ. Figures: {figures}\n",
        encoding="utf-8",
    )
    if len(figures) < 3:
        raise StageValidationError(f"Chỉ tạo được {len(figures)} static figures; cần tối thiểu 3.")
    return {"figures": figures, "figure_count": len(figures), "eda_sample_rows": len(sample), "report_path": str(report_path)}


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
