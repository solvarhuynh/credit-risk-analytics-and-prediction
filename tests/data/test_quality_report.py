import pytest
import pandas as pd

from src.data.quality_report import (
    audit_canonical_dataset,
    render_quality_report,
    run_leakage_gate,
    validate_handoff_manifest,
)


def _valid_manifest() -> dict:
    return {
        "dataset_id": "fixture",
        "stage": "de-lc-09",
        "run_status": "PASS",
        "stage_status": "PASS",
        "accepted_rows": 3,
        "rejected_rows": 2,
        "labeled_rows": 2,
        "unresolved_rows": 1,
        "target_counts": {"0": 1, "1": 1},
        "target_0": 1,
        "target_1": 1,
        "canonical_columns": 3,
        "dictionary_rows": 3,
        "dictionary_coverage": 1.0,
        "baseline_feature_count": 1,
        "baseline_forbidden_features": [],
        "leakage_gate": "PASS",
        "quality_status": "PASS",
        "canonical_path": "canonical.parquet",
        "dictionary_path": "dictionary.csv",
        "quality_report_path": "quality.md",
        "provenance": {"runner": "fixture"},
    }


def test_leakage_gate_blocks_post_loan_policy_geo_and_unknown() -> None:
    frame = pd.DataFrame({"loan_id": ["1"], "target": [0], "dti": [10], "total_pymnt": [1], "grade": ["A"], "state_code": ["CA"], "mystery": [1]})
    audit = run_leakage_gate(frame, ["dti", "total_pymnt", "grade", "state_code", "mystery"])
    assert audit["status"] == "FAIL"
    assert audit["post_loan"] == ["total_pymnt"]
    assert audit["policy_derived"] == ["grade"]
    assert audit["unknown"] == ["mystery"]


def test_quality_report_passes_safe_synthetic_handoff() -> None:
    frame = pd.DataFrame({"loan_id": ["1", "2"], "target": [0, 1], "dti": [10.0, 20.0], "issue_d": pd.to_datetime(["2018-01-01", "2018-02-01"]), "state_code": ["CA", "NY"]})
    dictionary = pd.DataFrame({"column_name": frame.columns})
    audit = audit_canonical_dataset(frame, ["dti"], dictionary=dictionary)
    assert audit["status"] == "PASS"
    assert audit["leakage_gate"]["status"] == "PASS"


def test_handoff_manifest_validates_counts_and_provenance() -> None:
    manifest = _valid_manifest()

    result = validate_handoff_manifest(
        manifest,
        canonical_columns=["loan_id", "target", "dti"],
        dictionary_columns=["loan_id", "target", "dti"],
    )

    assert result["status"] == "PASS"
    assert manifest["accepted_rows"] == manifest["labeled_rows"] + manifest["unresolved_rows"]
    assert manifest["target_0"] + manifest["target_1"] == manifest["labeled_rows"]


def test_handoff_manifest_missing_required_field_fails_closed() -> None:
    manifest = _valid_manifest()
    manifest.pop("run_status")

    with pytest.raises(ValueError, match="required fields"):
        validate_handoff_manifest(
            manifest,
            canonical_columns=["loan_id", "target", "dti"],
            dictionary_columns=["loan_id", "target", "dti"],
        )


def test_handoff_manifest_rejects_inconsistent_counts_or_dictionary_coverage() -> None:
    manifest = _valid_manifest()
    manifest["unresolved_rows"] = 2
    with pytest.raises(ValueError, match="accepted_rows"):
        validate_handoff_manifest(
            manifest,
            canonical_columns=["loan_id", "target", "dti"],
            dictionary_columns=["loan_id", "target", "dti"],
        )

    manifest = _valid_manifest()
    with pytest.raises(ValueError, match="dictionary coverage"):
        validate_handoff_manifest(
            manifest,
            canonical_columns=["loan_id", "target", "dti"],
            dictionary_columns=["loan_id", "target", "stale"],
        )


def test_success_quality_report_requires_integer_unresolved_count() -> None:
    audit = {
        "status": "PASS",
        "shape_and_grain": {"rows": 2, "null_keys": 0, "duplicate_keys": 0},
        "target_counts": {"0": 1, "1": 1},
        "infinity_count": 0,
        "state_code_coverage": 1.0,
        "issue_date_parse_success": 1.0,
        "excluded_unresolved_status_rows": None,
        "leakage_gate": {
            "status": "PASS",
            "post_loan": [],
            "policy_derived": [],
            "geography": [],
            "unknown": [],
            "target_or_identifier": [],
        },
    }

    with pytest.raises(ValueError, match="unresolved_status_rows"):
        render_quality_report(audit)
