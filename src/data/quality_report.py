"""Quality gate và leakage gate cho handoff TV2 → TV1."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd

from src.data.column_policy import (
    ColumnClass,
    classify_column,
    unknown_columns,
)


def validate_table_grain(frame: pd.DataFrame, key: str = "loan_id") -> dict[str, Any]:
    if key not in frame:
        raise ValueError(f"Thiếu khóa {key}.")
    audit = {
        "rows": len(frame),
        "null_keys": int(frame[key].isna().sum()),
        "duplicate_keys": int(frame[key].duplicated().sum()),
    }
    if audit["null_keys"] or audit["duplicate_keys"]:
        raise ValueError(f"Grain không hợp lệ: {audit}")
    return audit


def run_leakage_gate(
    dataset: pd.DataFrame,
    model_features: Iterable[str],
) -> dict[str, Any]:
    features = list(model_features)
    missing = sorted(set(features) - set(dataset.columns))
    unknown = unknown_columns(features)
    post_loan = [c for c in features if classify_column(c) == ColumnClass.POST_LOAN]
    policy_derived = [c for c in features if classify_column(c) == ColumnClass.POLICY_DERIVED]
    geography = [c for c in features if classify_column(c) == ColumnClass.GEOGRAPHY_ANALYTICS]
    target_or_id = [
        c for c in features
        if classify_column(c) in {ColumnClass.IDENTIFIER, ColumnClass.TARGET_SOURCE, ColumnClass.ANALYTICS_ONLY}
    ]
    failures = {
        "missing": missing,
        "unknown": unknown,
        "post_loan": post_loan,
        "policy_derived": policy_derived,
        "geography": geography,
        "target_or_identifier": target_or_id,
    }
    passed = not any(failures.values())
    return {"status": "PASS" if passed else "FAIL", **failures}


def audit_canonical_dataset(
    dataset: pd.DataFrame,
    model_features: Iterable[str],
    *,
    dictionary: pd.DataFrame | None = None,
    accepted_rows: int | None = None,
    rejected_rows: int | None = None,
    unresolved_status_rows: int | None = None,
) -> dict[str, Any]:
    grain = validate_table_grain(dataset)
    if "target" not in dataset:
        raise ValueError("Thiếu target.")
    target_values = set(dataset["target"].dropna().astype(int).unique())
    if dataset["target"].isna().any() or not target_values.issubset({0, 1}):
        raise ValueError("target phải non-null và chỉ gồm 0/1.")
    numeric = dataset.select_dtypes(include=["number"])
    infinity_count = int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum())
    leakage = run_leakage_gate(dataset, model_features)
    state_coverage = (
        float(dataset["state_code"].notna().mean()) if "state_code" in dataset and len(dataset) else None
    )
    issue_date_coverage = (
        float(pd.to_datetime(dataset["issue_d"], errors="coerce").notna().mean())
        if "issue_d" in dataset and len(dataset) else None
    )
    dictionary_missing: list[str] = []
    if dictionary is not None:
        if "column_name" not in dictionary:
            raise ValueError("Data dictionary thiếu column_name.")
        dictionary_missing = sorted(set(dataset.columns) - set(dictionary["column_name"]))
    status = "PASS" if infinity_count == 0 and leakage["status"] == "PASS" and not dictionary_missing else "FAIL"
    return {
        "status": status,
        "shape_and_grain": grain,
        "target_counts": {str(k): int(v) for k, v in dataset["target"].value_counts().items()},
        "infinity_count": infinity_count,
        "state_code_coverage": state_coverage,
        "issue_date_parse_success": issue_date_coverage,
        "dictionary_missing_columns": dictionary_missing,
        "accepted_rows": accepted_rows,
        "rejected_rows": rejected_rows,
        "excluded_unresolved_status_rows": unresolved_status_rows,
        "leakage_gate": leakage,
    }


def render_quality_report(audit: dict[str, Any]) -> str:
    gate = audit["leakage_gate"]
    return f"""# Báo cáo chất lượng dữ liệu Lending Club

Trạng thái tổng: **{audit['status']}**

## LEAKAGE GATE

LEAKAGE GATE = **{gate['status']}**

- Post-loan trong feature: {gate['post_loan']}
- Policy-derived trong baseline: {gate['policy_derived']}
- Geography trong baseline: {gate['geography']}
- Unknown cần review: {gate['unknown']}
- Identifier/target trong feature: {gate['target_or_identifier']}

## Kiểm tra chính

- Số dòng canonical: {audit['shape_and_grain']['rows']}
- Khóa null/trùng: {audit['shape_and_grain']['null_keys']} / {audit['shape_and_grain']['duplicate_keys']}
- Giá trị vô cực: {audit['infinity_count']}
- Coverage state_code: {audit['state_code_coverage']}
- Tỷ lệ parse issue_d: {audit['issue_date_parse_success']}
- Khoản vay unresolved đã loại khỏi nhãn: {audit['excluded_unresolved_status_rows']}
"""
