"""Quality gate và leakage gate cho handoff TV2 → TV1."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from src.data.column_policy import (
    ColumnClass,
    MODEL_ELIGIBLE_CLASSES,
    classify_column,
    unknown_columns,
)


HANDOFF_MANIFEST_REQUIRED_FIELDS = frozenset({
    "dataset_id",
    "stage",
    "run_status",
    "stage_status",
    "accepted_rows",
    "rejected_rows",
    "labeled_rows",
    "unresolved_rows",
    "target_counts",
    "target_0",
    "target_1",
    "canonical_columns",
    "dictionary_rows",
    "dictionary_coverage",
    "baseline_feature_count",
    "baseline_forbidden_features",
    "leakage_gate",
    "quality_status",
    "canonical_path",
    "dictionary_path",
    "quality_report_path",
    "provenance",
})


def _is_non_bool_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_handoff_manifest(
    manifest: Mapping[str, Any],
    *,
    canonical_columns: Sequence[str],
    dictionary_columns: Sequence[str],
) -> dict[str, Any]:
    """Validate the DE-LC-09 manifest against the current canonical schema.

    Validation is intentionally independent from the manifest writer so a
    missing field or stale dictionary cannot be presented as a successful
    handoff artifact.
    """

    missing_fields = sorted(HANDOFF_MANIFEST_REQUIRED_FIELDS - set(manifest))
    if missing_fields:
        raise ValueError(f"Manifest thiếu required fields: {missing_fields}")

    expected_columns = list(canonical_columns)
    actual_dictionary_columns = list(dictionary_columns)
    if len(actual_dictionary_columns) != len(set(actual_dictionary_columns)):
        raise ValueError("Data dictionary chứa column_name bị trùng.")
    if set(actual_dictionary_columns) != set(expected_columns):
        missing_columns = sorted(set(expected_columns) - set(actual_dictionary_columns))
        stale_columns = sorted(set(actual_dictionary_columns) - set(expected_columns))
        raise ValueError(
            "Data dictionary coverage không khớp canonical schema: "
            f"missing={missing_columns}, stale={stale_columns}"
        )

    integer_fields = (
        "accepted_rows",
        "rejected_rows",
        "labeled_rows",
        "unresolved_rows",
        "target_0",
        "target_1",
        "canonical_columns",
        "dictionary_rows",
        "baseline_feature_count",
    )
    invalid_integer_fields = [
        field for field in integer_fields if not _is_non_bool_int(manifest[field])
    ]
    if invalid_integer_fields:
        raise ValueError(f"Manifest integer fields không hợp lệ: {invalid_integer_fields}")

    if manifest["accepted_rows"] <= 0:
        raise ValueError("Manifest accepted_rows phải lớn hơn 0.")
    if manifest["rejected_rows"] <= 0:
        raise ValueError("Manifest rejected_rows phải lớn hơn 0.")
    if manifest["labeled_rows"] <= 0:
        raise ValueError("Manifest labeled_rows phải lớn hơn 0.")
    if manifest["unresolved_rows"] < 0:
        raise ValueError("Manifest unresolved_rows không được âm.")
    if manifest["accepted_rows"] != manifest["labeled_rows"] + manifest["unresolved_rows"]:
        raise ValueError("accepted_rows phải bằng labeled_rows + unresolved_rows.")
    if manifest["target_0"] + manifest["target_1"] != manifest["labeled_rows"]:
        raise ValueError("target_0 + target_1 phải bằng labeled_rows.")
    if manifest["canonical_columns"] != len(expected_columns):
        raise ValueError("Manifest canonical_columns không khớp canonical schema.")
    if manifest["dictionary_rows"] != len(actual_dictionary_columns):
        raise ValueError("Manifest dictionary_rows không khớp dictionary.")
    if manifest["dictionary_coverage"] != 1.0:
        raise ValueError("Manifest dictionary_coverage phải bằng 1.0.")
    if manifest["baseline_feature_count"] < 0:
        raise ValueError("Manifest baseline_feature_count không được âm.")
    if manifest["baseline_forbidden_features"] != []:
        raise ValueError("Baseline forbidden feature list phải rỗng.")
    if manifest["leakage_gate"] != "PASS":
        raise ValueError("Manifest leakage_gate phải là PASS.")
    if manifest["quality_status"] != "PASS":
        raise ValueError("Manifest quality_status phải là PASS.")
    if manifest["run_status"] != "PASS" or manifest["stage_status"] != "PASS":
        raise ValueError("Manifest run/stage status phải là PASS.")
    if not isinstance(manifest["provenance"], Mapping):
        raise ValueError("Manifest provenance phải là object.")

    return {
        "status": "PASS",
        "dictionary_coverage": 1.0,
        "canonical_columns": len(expected_columns),
        "dictionary_rows": len(actual_dictionary_columns),
    }


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
    text_high_cardinality = [c for c in features if classify_column(c) == ColumnClass.TEXT_HIGH_CARDINALITY]
    target_or_id = [
        c for c in features
        if classify_column(c) in {ColumnClass.IDENTIFIER, ColumnClass.TARGET_SOURCE, ColumnClass.ANALYTICS_ONLY}
    ]
    not_model_eligible = [c for c in features if classify_column(c) not in MODEL_ELIGIBLE_CLASSES]
    failures = {
        "missing": missing,
        "unknown": unknown,
        "post_loan": post_loan,
        "policy_derived": policy_derived,
        "geography": geography,
        "text_high_cardinality": text_high_cardinality,
        "target_or_identifier": target_or_id,
        "not_model_eligible": not_model_eligible,
    }
    passed = not any(failures.values())
    return {"status": "PASS" if passed else "FAIL", **failures}


def validate_canonical_modeling_dataset(
    dataset: pd.DataFrame,
    model_features: Iterable[str],
) -> dict[str, Any]:
    """Validate canonical labeled grain, target, numeric safety and baseline gate.

    The canonical dataset may retain analytics columns, but ``model_features``
    must be derived from the shared column policy and contain only model-eligible
    application-time or credit-snapshot fields.
    """

    grain = validate_table_grain(dataset)
    if "target" not in dataset:
        raise ValueError("Canonical thiếu target.")
    if dataset["target"].isna().any():
        raise ValueError("Canonical target phải non-null; unresolved rows không được vào labeled set.")
    target_values = set(dataset["target"].tolist())
    if not target_values.issubset({0, 1}):
        raise ValueError(f"Canonical target phải chỉ gồm 0/1, nhận được: {sorted(target_values, key=str)}")
    numeric = dataset.select_dtypes(include=["number"])
    infinity_count = int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum())
    if infinity_count:
        raise ValueError(f"Canonical chứa {infinity_count} giá trị numeric vô cực.")
    leakage = run_leakage_gate(dataset, model_features)
    if leakage["status"] != "PASS":
        raise ValueError(f"LEAKAGE GATE FAIL: {leakage}")
    return {
        "rows": len(dataset),
        "shape_and_grain": grain,
        "target_counts": {str(key): int(value) for key, value in dataset["target"].value_counts().items()},
        "infinity_count": infinity_count,
        "model_features": list(model_features),
        "leakage_gate": leakage,
    }


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
    unresolved_rows = audit.get("excluded_unresolved_status_rows")
    if audit["status"] == "PASS" and not _is_non_bool_int(unresolved_rows):
        raise ValueError(
            "Quality report PASS phải có excluded_unresolved_status_rows là integer."
        )

    def format_count(value: Any) -> Any:
        return f"{value:,}" if _is_non_bool_int(value) else value

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

- Số dòng accepted source: {format_count(audit.get('accepted_rows'))}
- Số dòng rejected source: {format_count(audit.get('rejected_rows'))}
- Số dòng canonical labeled: {format_count(audit['shape_and_grain']['rows'])}
- Khóa null/trùng: {audit['shape_and_grain']['null_keys']} / {audit['shape_and_grain']['duplicate_keys']}
- Giá trị vô cực: {audit['infinity_count']}
- Coverage state_code: {audit['state_code_coverage']}
- Tỷ lệ parse issue_d: {audit['issue_date_parse_success']}
- Target counts: {audit.get('target_counts', {})}
- Baseline feature count: {audit.get('baseline_feature_count')}
- Dictionary coverage: {audit.get('dictionary_coverage')}
- Khoản vay unresolved đã loại khỏi nhãn: {format_count(unresolved_rows)}
"""
