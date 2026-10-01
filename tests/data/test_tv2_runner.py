import pandas as pd
import pytest
import json

from src.data.quality_report import run_leakage_gate
from src.data.tv2_runner import (
    RunnerContext,
    StageBlocked,
    StageValidationError,
    check_stage_dependencies,
    profile_target_statuses,
    normalize_stage,
    run_stage,
    validate_unique_loan_ids,
)


def _context(tmp_path):
    return RunnerContext(
        raw_dir=tmp_path / "raw",
        reports_dir=tmp_path / "reports",
        interim_dir=tmp_path / "interim",
        processed_dir=tmp_path / "processed",
        chunksize=2,
    )


def test_stage_dependency_blocks_without_pass_marker(tmp_path) -> None:
    context = _context(tmp_path)
    with pytest.raises(StageBlocked):
        check_stage_dependencies(context, "de-lc-02")


def test_invalid_stage_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_stage("de-lc-99")


def test_target_profile_keeps_unresolved_statuses_out_of_target() -> None:
    audit = profile_target_statuses(pd.DataFrame({"loan_status": ["Fully Paid", "Charged Off", "Current"]}))
    assert audit["target_counts"] == {"0": 1, "1": 1}
    assert audit["unresolved_rows"] == 1


def test_duplicate_loan_id_fails_closed() -> None:
    with pytest.raises(StageValidationError):
        validate_unique_loan_ids(pd.DataFrame({"loan_id": ["1", "1"]}))


def test_leakage_gate_propagates_failure() -> None:
    frame = pd.DataFrame({"dti": [10], "total_pymnt": [100], "grade": ["A"], "state_code": ["CA"]})
    gate = run_leakage_gate(frame, ["dti", "total_pymnt", "grade", "state_code"])
    assert gate["status"] == "FAIL"
    assert gate["post_loan"] == ["total_pymnt"]
    assert gate["policy_derived"] == ["grade"]
    assert gate["geography"] == ["state_code"]


def test_runner_returns_blocked_and_does_not_read_raw_when_dependency_fails(tmp_path) -> None:
    context = _context(tmp_path)
    result = run_stage(
        "de-lc-03",
        raw_dir=context.raw_dir,
        reports_dir=context.reports_dir,
        interim_dir=context.interim_dir,
        processed_dir=context.processed_dir,
    )
    assert result.status == "BLOCKED"
    assert "de-lc-01=MISSING" in result.message


def test_failed_marker_blocks_following_stage(tmp_path) -> None:
    context = _context(tmp_path)
    context.marker_dir.mkdir(parents=True)
    for stage, status in (("de-lc-01", "PASS"), ("de-lc-02", "FAIL")):
        (context.marker_dir / f"{stage}.json").write_text(json.dumps({"status": status}), encoding="utf-8")
    result = run_stage(
        "de-lc-03",
        raw_dir=context.raw_dir,
        reports_dir=context.reports_dir,
        interim_dir=context.interim_dir,
        processed_dir=context.processed_dir,
    )
    assert result.status == "BLOCKED"
    assert "de-lc-02=FAIL" in result.message
