import pandas as pd
import pytest
import json

import src.data.tv2_runner as tv2_runner

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


def _write_de04_fixture(context: RunnerContext) -> None:
    context.raw_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "id": ["loan-1", "loan-2"],
        "loan_status": ["Fully Paid", "Charged Off"],
        "loan_amnt": [1000, 2000],
        "issue_d": ["Jan-2018", "Feb-2018"],
        "purpose": ["debt_consolidation", "credit_card"],
    }).to_csv(context.raw_dir / "accepted_loans.csv", index=False)
    pd.DataFrame({
        "Amount Requested": [500, 700],
        "Application Date": ["2018-01-01", "2018-01-02"],
        "Loan Title": ["small loan", "repair"],
        "Risk_Score": [500, 600],
        "Debt-To-Income Ratio": ["10%", "20%"],
        "Zip Code": ["123xx", "456xx"],
        "State": ["CA", "NY"],
        "Employment Length": ["1 year", "5 years"],
        "Policy Code": [1, 1],
    }).to_csv(context.raw_dir / "rejected_loans.csv", index=False)


def _write_de08_fixture(context: RunnerContext) -> None:
    context.raw_dir.mkdir(parents=True, exist_ok=True)
    accepted = pd.DataFrame({
        "id": ["loan-1", "loan-2", "loan-3"],
        "loan_status": ["Fully Paid", "Charged Off", "Default"],
        "loan_amnt": [1000, 2000, 3000],
        "issue_d": ["Jan-2018", "Feb-2018", "Feb-2018"],
        "addr_state": ["CA", "NY", "CA"],
        "zip_code": ["900xx", "100xx", "900xx"],
        "purpose": ["card", "repair", "card"],
    })
    rejected = pd.DataFrame({
        "Amount Requested": [500, 700, 900, 1100, 1300],
        "Application Date": ["2018-01-01", "2018-01-02", "2018-01-03", "2018-01-04", "2018-01-05"],
        "Loan Title": ["small", "repair", "card", "home", "car"],
        "Risk_Score": [500, 600, 610, 620, 630],
        "Debt-To-Income Ratio": ["10%", "20%", "30%", "40%", "50%"],
        "Zip Code": ["123xx", "456xx", "789xx", "111xx", "222xx"],
        "State": ["CA", "NY", "CA", "TX", "WA"],
        "Employment Length": ["1 year", "2 years", "3 years", "4 years", "5 years"],
        "Policy Code": [1, 1, 1, 1, 1],
    })
    accepted.to_csv(context.raw_dir / "accepted_loans.csv", index=False)
    rejected.to_csv(context.raw_dir / "rejected_loans.csv", index=False)

    context.interim_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"issue_d": accepted["issue_d"]}).to_parquet(
        context.interim_dir / "loan_application.parquet", index=False
    )
    pd.DataFrame({"state_code": accepted["addr_state"]}).to_parquet(
        context.interim_dir / "borrower_profile.parquet", index=False
    )
    pd.DataFrame({
        "application_date": rejected["Application Date"],
        "state_code": rejected["State"],
    }).to_parquet(context.interim_dir / "rejected_applications.parquet", index=False)


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


def test_de04_success_promotes_all_outputs_only_after_full_fixture_run(tmp_path, capsys, monkeypatch) -> None:
    context = RunnerContext(
        raw_dir=tmp_path / "raw",
        reports_dir=tmp_path / "reports",
        interim_dir=tmp_path / "interim",
        processed_dir=tmp_path / "processed",
        chunksize=1,
    )
    _write_de04_fixture(context)
    original_clean_rejected = tv2_runner.clean_rejected_loans

    def inspect_rejected_processing(frame):
        assert not any(
            (context.interim_dir / f"{name}.parquet").exists()
            for name in tv2_runner.BUSINESS_TABLE_NAMES
        )
        return original_clean_rejected(frame)

    monkeypatch.setattr(tv2_runner, "clean_rejected_loans", inspect_rejected_processing)

    result = tv2_runner._write_business_tables(context)

    assert result["accepted_rows"] == 2
    assert result["rejected_rows"] == 2
    for name in tv2_runner.BUSINESS_TABLE_NAMES:
        assert (context.interim_dir / f"{name}.parquet").is_file()
        assert not (context.interim_dir / f"{name}.partial.parquet").exists()
    assert len(pd.read_parquet(context.interim_dir / "loan_application.parquet")) == 2
    assert len(pd.read_parquet(context.interim_dir / "rejected_applications.parquet")) == 2
    output = capsys.readouterr().out
    assert "DE-LC-04 accepted chunks=2 rows=2" in output
    assert "DE-LC-04 rejected chunks=2 rows=2" in output


def test_de04_rejected_failure_cleans_partials_and_preserves_no_new_canonical_outputs(
    tmp_path, monkeypatch
) -> None:
    context = _context(tmp_path)
    _write_de04_fixture(context)

    def fail_rejected_processing(frame):
        raise RuntimeError("fixture rejected failure")

    monkeypatch.setattr(tv2_runner, "clean_rejected_loans", fail_rejected_processing)
    with pytest.raises(RuntimeError, match="fixture rejected failure"):
        tv2_runner._write_business_tables(context)

    for name in tv2_runner.BUSINESS_TABLE_NAMES:
        assert not (context.interim_dir / f"{name}.partial.parquet").exists()
        assert not (context.interim_dir / f"{name}.parquet").exists()


def test_de04_keyboard_interrupt_cleans_partials_and_preserves_existing_canonical_outputs(
    tmp_path, monkeypatch
) -> None:
    context = _context(tmp_path)
    _write_de04_fixture(context)
    context.interim_dir.mkdir(parents=True, exist_ok=True)
    existing = {
        name: f"existing-{name}".encode("utf-8")
        for name in tv2_runner.BUSINESS_TABLE_NAMES
    }
    for name, payload in existing.items():
        (context.interim_dir / f"{name}.parquet").write_bytes(payload)

    def interrupt_rejected_processing(frame):
        raise KeyboardInterrupt()

    monkeypatch.setattr(tv2_runner, "clean_rejected_loans", interrupt_rejected_processing)
    with pytest.raises(KeyboardInterrupt):
        tv2_runner._write_business_tables(context)

    for name, payload in existing.items():
        assert (context.interim_dir / f"{name}.parquet").read_bytes() == payload
        assert not (context.interim_dir / f"{name}.partial.parquet").exists()


def test_de08_funnel_preserves_multi_chunk_counts_and_dimension_keys(tmp_path) -> None:
    context = _context(tmp_path)
    _write_de08_fixture(context)

    result = tv2_runner._stage_08(context)
    funnel = pd.read_parquet(context.interim_dir / "application_funnel.parquet")

    assert result["accepted_funnel_rows"] == 3
    assert result["rejected_funnel_rows"] == 5
    assert len(funnel) == 8
    assert funnel["decision"].value_counts().to_dict() == {"rejected": 5, "accepted": 3}
    assert funnel["application_id"].nunique() == 8
    assert not funnel["application_id"].duplicated().any()
    assert not any(context.interim_dir.glob("*.partial.parquet"))
    assert not pd.read_parquet(context.interim_dir / "dim_date.parquet")["date"].duplicated().any()
    assert not pd.read_parquet(context.interim_dir / "dim_state.parquet")["state_code"].duplicated().any()


def test_de08_rerun_is_idempotent_and_does_not_duplicate_funnel_rows(tmp_path) -> None:
    context = _context(tmp_path)
    _write_de08_fixture(context)

    tv2_runner._stage_08(context)
    first = pd.read_parquet(context.interim_dir / "application_funnel.parquet")
    tv2_runner._stage_08(context)
    second = pd.read_parquet(context.interim_dir / "application_funnel.parquet")

    assert len(first) == len(second) == 8
    assert first["decision"].value_counts().to_dict() == second["decision"].value_counts().to_dict()
    assert second["application_id"].nunique() == 8


def test_de09_writes_complete_manifest_and_quality_report(tmp_path) -> None:
    context = _context(tmp_path)
    context.interim_dir.mkdir(parents=True, exist_ok=True)
    context.processed_dir.mkdir(parents=True, exist_ok=True)

    canonical = pd.DataFrame({
        "loan_id": ["loan-1", "loan-2"],
        "target": [0, 1],
        "annual_inc": [50000, 60000],
        "dti": [10.0, 20.0],
        "issue_d": ["Jan-2018", "Feb-2018"],
        "state_code": ["CA", "NY"],
    })
    canonical.to_parquet(context.processed_dir / "cleaned_dataset.parquet", index=False)

    for name in (
        "loan_application",
        "borrower_profile",
        "credit_profile",
        "loan_pricing",
        "loan_outcome",
    ):
        pd.DataFrame({"loan_id": ["loan-1", "loan-2", "loan-3"]}).to_parquet(
            context.interim_dir / f"{name}.parquet", index=False
        )
    pd.DataFrame({"application_id": ["rejected-1", "rejected-2"]}).to_parquet(
        context.interim_dir / "rejected_applications.parquet", index=False
    )

    context.marker_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, 9):
        (context.marker_dir / f"de-lc-{index:02d}.json").write_text(
            json.dumps({"status": "PASS"}), encoding="utf-8"
        )

    result = run_stage(
        "de-lc-09",
        raw_dir=context.raw_dir,
        reports_dir=context.reports_dir,
        interim_dir=context.interim_dir,
        processed_dir=context.processed_dir,
        chunksize=2,
    )

    assert result.status == "PASS"
    manifest = json.loads((context.processed_dir / "cleaned_dataset_manifest.json").read_text())
    assert manifest["accepted_rows"] == 3
    assert manifest["rejected_rows"] == 2
    assert manifest["labeled_rows"] == 2
    assert manifest["unresolved_rows"] == 1
    assert manifest["target_0"] + manifest["target_1"] == manifest["labeled_rows"]
    assert manifest["canonical_columns"] == manifest["dictionary_rows"] == 6
    assert manifest["baseline_forbidden_features"] == []
    assert manifest["run_status"] == manifest["stage_status"] == "PASS"
    assert manifest["provenance"]["stage"] == "de-lc-09"

    quality_report = (context.reports_dir / "data_quality_report.md").read_text()
    assert "unresolved đã loại khỏi nhãn: 1" in quality_report
    assert "None" not in quality_report
