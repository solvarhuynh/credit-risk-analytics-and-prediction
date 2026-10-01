import pandas as pd

from src.data.quality_report import audit_canonical_dataset, run_leakage_gate


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
