"""Pipeline TV2 cho Lending Club.

File này chỉ định luồng chạy tương lai. Migration không gọi ``run_build_pipeline``.
Việc đọc raw dùng chunk để không bắt buộc nạp hai CSV nhiều GB vào RAM.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover - exercised only before setup install
    pa = None
    pq = None

from src.config import DATASET_ID, INTERIM_DIR, PROCESSED_DIR
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
from src.data.cleaning import clean_accepted_loans, clean_rejected_loans
from src.data.column_policy import approved_model_features, classify_column
from src.data.load_data import load_accepted_loans, load_rejected_loans
from src.data.quality_report import validate_canonical_modeling_dataset
from src.features.engineering import engineer_lending_club_features


class ParquetSink:
    def __init__(self, path: Path):
        if pa is None or pq is None:
            raise RuntimeError(
                "pyarrow is required for Parquet outputs. Run 'python -m pip install -r requirements.txt'."
            )
        self.path = path
        self.writer: pq.ParquetWriter | None = None
        self.schema: Any | None = None

    def write(self, frame: pd.DataFrame) -> None:
        table = pa.Table.from_pandas(frame, preserve_index=False)
        if self.writer is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.schema = table.schema
            self.writer = pq.ParquetWriter(self.path, self.schema, compression="snappy")
        else:
            table = table.cast(self.schema, safe=False)
        self.writer.write_table(table)

    def close(self) -> None:
        if self.writer is not None:
            self.writer.close()


def prepare_accepted_batch(frame: pd.DataFrame) -> dict[str, Any]:
    cleaned, _ = clean_accepted_loans(frame)
    tables = {
        "loan_application": build_loan_application_table(cleaned),
        "borrower_profile": build_borrower_profile_table(cleaned),
        "credit_profile": build_credit_profile_table(cleaned),
        "loan_pricing": build_loan_pricing_table(cleaned),
        "loan_outcome": build_loan_outcome_table(cleaned),
    }
    canonical = join_canonical_modeling_table(
        tables["loan_application"], tables["borrower_profile"],
        tables["credit_profile"], tables["loan_outcome"],
    )
    if len(canonical) != len(cleaned):
        raise ValueError("Canonical join làm thay đổi số dòng accepted.")
    canonical, _ = engineer_lending_club_features(canonical)
    canonical_labeled = canonical.loc[canonical["target"].notna()].copy()
    baseline_features = approved_model_features(canonical_labeled.columns)
    validation = validate_canonical_modeling_dataset(canonical_labeled, baseline_features)
    tables["canonical_labeled"] = canonical_labeled
    tables["canonical_audit"] = {
        "input_accepted_rows": len(cleaned),
        "joined_rows": len(canonical),
        "resolved_labeled_rows": int(canonical["target"].notna().sum()),
        "unresolved_rows": int(canonical["target"].isna().sum()),
        "canonical_labeled_rows": len(canonical_labeled),
        "unique_loan_id_count": int(cleaned["loan_id"].nunique(dropna=True)),
        "duplicate_loan_id_count": int(cleaned["loan_id"].duplicated().sum()),
        "null_loan_id_count": int(cleaned["loan_id"].isna().sum()),
        "target_counts": validation["target_counts"],
        "baseline_features": baseline_features,
        "leakage_gate": validation["leakage_gate"],
    }
    return tables


def build_data_dictionary(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "column_name": frame.columns,
        "dtype": [str(frame[column].dtype) for column in frame.columns],
        "policy_class": [str(classify_column(column)) for column in frame.columns],
        "model_eligible_default": [classify_column(column).value in {"APPLICATION_TIME", "CREDIT_SNAPSHOT"} for column in frame.columns],
        "canonical_grain": "accepted loan (loan_id)",
    })


def run_build_pipeline(*, chunksize: int = 100_000) -> dict[str, Any]:
    """Chạy pipeline thật trong task DE-LC sau migration, không dùng trong reset."""

    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    sink_names = ["loan_application", "borrower_profile", "credit_profile", "loan_pricing", "loan_outcome"]
    sinks = {name: ParquetSink(INTERIM_DIR / f"{name}.parquet") for name in sink_names}
    canonical_sink = ParquetSink(PROCESSED_DIR / "cleaned_dataset.parquet")
    accepted_rows = labeled_rows = unresolved_rows = 0
    seen_loan_ids: set[str] = set()
    dates: list[pd.Series] = []
    states: list[pd.Series] = []
    dictionary_sample: pd.DataFrame | None = None
    try:
        for raw_chunk in load_accepted_loans(chunksize=chunksize):
            tables = prepare_accepted_batch(raw_chunk)
            chunk_ids = set(tables["loan_application"]["loan_id"].astype(str))
            duplicate_across_chunks = seen_loan_ids & chunk_ids
            if duplicate_across_chunks:
                raise ValueError("loan_id bị trùng giữa các chunk accepted.")
            seen_loan_ids.update(chunk_ids)
            accepted_rows += len(raw_chunk)
            labeled_rows += len(tables["canonical_labeled"])
            unresolved_rows += len(raw_chunk) - len(tables["canonical_labeled"])
            for name in sink_names:
                sinks[name].write(tables[name])
            canonical_sink.write(tables["canonical_labeled"])
            dictionary_sample = tables["canonical_labeled"]
            dates.append(pd.Series(tables["loan_application"]["issue_d"].dropna().unique()))
            states.append(pd.Series(tables["borrower_profile"]["state_code"].dropna().unique()))
    finally:
        for sink in sinks.values():
            sink.close()
        canonical_sink.close()

    rejected_sink = ParquetSink(INTERIM_DIR / "rejected_applications.parquet")
    rejected_rows = 0
    rejected_dates: list[pd.Series] = []
    rejected_states: list[pd.Series] = []
    try:
        for raw_chunk in load_rejected_loans(chunksize=chunksize):
            cleaned, _ = clean_rejected_loans(raw_chunk)
            table = build_rejected_applications_table(cleaned)
            rejected_sink.write(table)
            rejected_rows += len(table)
            rejected_dates.append(pd.Series(table["application_date"].dropna().unique()))
            rejected_states.append(pd.Series(table["state_code"].dropna().unique()))
    finally:
        rejected_sink.close()

    build_date_dimension(*dates, *rejected_dates).to_parquet(INTERIM_DIR / "dim_date.parquet", index=False)
    build_state_dimension(*states, *rejected_states).to_parquet(INTERIM_DIR / "dim_state.parquet", index=False)
    if dictionary_sample is None:
        raise ValueError("Accepted source không có batch dữ liệu để tạo dictionary.")
    build_data_dictionary(dictionary_sample).to_csv(PROCESSED_DIR / "data_dictionary.csv", index=False)
    manifest = {
        "dataset_id": DATASET_ID,
        "accepted_rows": accepted_rows,
        "rejected_rows": rejected_rows,
        "labeled_rows": labeled_rows,
        "excluded_unresolved_status_rows": unresolved_rows,
        "status": "GENERATED_BY_TV2",
    }
    (PROCESSED_DIR / "cleaned_dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
