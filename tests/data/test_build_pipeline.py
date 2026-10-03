import json

import pandas as pd
import pytest

from src.data.build_pipeline import ParquetSink, build_data_dictionary, prepare_accepted_batch
from src.data.column_policy import (
    ColumnClass,
    approved_model_features,
    classify_column,
)
from src.data.quality_report import (
    run_leakage_gate,
    validate_canonical_modeling_dataset,
)
from src.data.tv2_runner import RunnerContext, run_stage


def test_prepare_accepted_batch_excludes_unresolved_and_keeps_grain() -> None:
    raw = pd.DataFrame({
        "id": ["1", "2"], "loan_status": ["Fully Paid", "Current"],
        "loan_amnt": [10000, 5000], "annual_inc": [50000, 0],
        "fico_range_low": [680, 700], "fico_range_high": [684, 704],
        "issue_d": ["Jan-2018", "Feb-2018"], "earliest_cr_line": ["Jan-2008", "Jan-2010"],
        "dti": [10, 20], "addr_state": ["CA", "NY"], "zip_code": ["900xx", "100xx"],
    })
    tables = prepare_accepted_batch(raw)
    assert len(tables["loan_application"]) == 2
    assert len(tables["canonical_labeled"]) == 1
    assert "fico_avg" in tables["canonical_labeled"]
    batch_audit = tables["canonical_audit"]
    assert batch_audit["input_accepted_rows"] == 2
    assert batch_audit["joined_rows"] == 2
    assert batch_audit["resolved_labeled_rows"] == 1
    assert batch_audit["unresolved_rows"] == 1
    assert batch_audit["canonical_labeled_rows"] == 1
    assert batch_audit["unique_loan_id_count"] == 2
    assert batch_audit["duplicate_loan_id_count"] == 0
    assert batch_audit["null_loan_id_count"] == 0
    assert batch_audit["target_counts"] == {"0": 1}
    assert {"loan_amnt", "annual_inc", "dti", "fico_avg", "loan_to_income_ratio"}.issubset(
        batch_audit["baseline_features"]
    )
    assert batch_audit["leakage_gate"]["status"] == "PASS"
    dictionary = build_data_dictionary(tables["canonical_labeled"])
    assert set(dictionary.columns) >= {"column_name", "policy_class", "model_eligible_default"}


def test_prepare_accepted_batch_applies_target_policy_and_isolates_outcomes() -> None:
    statuses = [
        "Fully Paid",
        "Charged Off",
        "Default",
        "Current",
        "Late (16-30 days)",
        "Late (31-120 days)",
        "In Grace Period",
        "Does not meet the credit policy. Status:Fully Paid",
        "Does not meet the credit policy. Status:Charged Off",
        None,
    ]
    raw = pd.DataFrame({
        "id": [str(index) for index in range(len(statuses))],
        "loan_status": statuses,
        "loan_amnt": [10000] * len(statuses),
        "annual_inc": [50000] * len(statuses),
        "fico_range_low": [680] * len(statuses),
        "fico_range_high": [684] * len(statuses),
        "issue_d": ["Jan-2018"] * len(statuses),
        "earliest_cr_line": ["Jan-2008"] * len(statuses),
        "dti": [10] * len(statuses),
        "addr_state": ["CA"] * len(statuses),
        "zip_code": ["900xx"] * len(statuses),
        "total_pymnt": [11000] * len(statuses),
        "last_pymnt_d": ["Jan-2019"] * len(statuses),
    })

    tables = prepare_accepted_batch(raw)
    accepted_table_names = [
        "loan_application", "borrower_profile", "credit_profile",
        "loan_pricing", "loan_outcome",
    ]

    for name in accepted_table_names:
        table = tables[name]
        assert len(table) == len(statuses)
        assert table["loan_id"].notna().all()
        assert table["loan_id"].is_unique

    canonical = tables["canonical_labeled"]
    assert len(canonical) == 3
    assert canonical["loan_id"].notna().all()
    assert canonical["loan_id"].is_unique
    assert set(canonical["target"].dropna().astype(int)) == {0, 1}

    feature_columns = [column for column in canonical.columns if column not in {"loan_id", "target"}]
    assert all(
        classify_column(column) not in {ColumnClass.TARGET_SOURCE, ColumnClass.POST_LOAN}
        for column in feature_columns
    )
    assert "loan_status" not in canonical.columns
    assert "total_pymnt" not in canonical.columns
    assert "last_pymnt_d" not in canonical.columns
    assert "total_pymnt" in tables["loan_outcome"].columns


def test_prepare_accepted_batch_all_unresolved_keeps_business_rows_and_empty_labeled_table() -> None:
    raw = pd.DataFrame({
        "id": ["1", "2"], "loan_status": ["Current", "In Grace Period"],
        "loan_amnt": [10000, 5000], "annual_inc": [50000, 60000],
        "fico_range_low": [680, 700], "fico_range_high": [684, 704],
        "issue_d": ["Jan-2018", "Feb-2018"], "earliest_cr_line": ["Jan-2008", "Jan-2010"],
        "dti": [10, 20],
    })

    tables = prepare_accepted_batch(raw)

    assert len(tables["loan_application"]) == 2
    assert tables["canonical_labeled"].empty
    assert tables["canonical_labeled"]["target"].isna().all()
    assert tables["canonical_audit"]["resolved_labeled_rows"] == 0
    assert tables["canonical_audit"]["unresolved_rows"] == 2
    assert tables["canonical_audit"]["canonical_labeled_rows"] == 0
    assert tables["canonical_audit"]["target_counts"] == {}


def test_prepare_accepted_batch_rejects_duplicate_loan_id() -> None:
    raw = pd.DataFrame({
        "id": ["1", "1"], "loan_status": ["Fully Paid", "Default"],
        "loan_amnt": [10000, 5000], "annual_inc": [50000, 60000],
        "fico_range_low": [680, 700], "fico_range_high": [684, 704],
        "issue_d": ["Jan-2018", "Feb-2018"], "earliest_cr_line": ["Jan-2008", "Jan-2010"],
        "dti": [10, 20],
    })

    with pytest.raises(ValueError, match="loan_id phải non-null và unique"):
        prepare_accepted_batch(raw)


def test_canonical_validator_allows_analytics_columns_but_derives_safe_baseline_features() -> None:
    frame = pd.DataFrame({
        "loan_id": ["1", "2"], "target": [0, 1],
        "annual_inc": [50000, 60000], "fico_avg": [682, 702],
        "dti": [10, 20], "loan_to_income_ratio": [0.2, 0.1],
        "total_pymnt": [11000, 5500], "loan_status": ["Fully Paid", "Default"],
        "grade": ["A", "B"], "int_rate": [5.0, 10.0],
        "state_code": ["CA", "NY"], "zip_code": ["900xx", "100xx"],
    })
    baseline = approved_model_features(frame.columns)

    assert {"annual_inc", "fico_avg", "dti", "loan_to_income_ratio"}.issubset(baseline)
    assert not {
        "total_pymnt", "loan_status", "target", "grade", "int_rate",
        "state_code", "zip_code", "loan_id",
    }.intersection(baseline)
    audit = validate_canonical_modeling_dataset(frame, baseline)
    assert audit["leakage_gate"]["status"] == "PASS"

    forbidden = [
        "total_pymnt", "loan_status", "target", "grade", "int_rate",
        "state_code", "zip_code", "loan_id",
    ]
    gate = run_leakage_gate(frame, forbidden)
    assert gate["status"] == "FAIL"
    assert set(gate["not_model_eligible"]) == set(forbidden)


@pytest.mark.parametrize(
    "invalid_frame",
    [
        pd.DataFrame({"loan_id": ["1", "1"], "target": [0, 1], "dti": [10, 20]}),
        pd.DataFrame({"loan_id": ["1", None], "target": [0, 1], "dti": [10, 20]}),
        pd.DataFrame({"loan_id": ["1"], "target": [None], "dti": [10]}),
        pd.DataFrame({"loan_id": ["1"], "target": [2], "dti": [10]}),
        pd.DataFrame({"loan_id": ["1"], "target": [0], "dti": [float("inf")]}),
    ],
)
def test_canonical_validator_fails_closed(invalid_frame: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        validate_canonical_modeling_dataset(invalid_frame, ["dti"])


def test_parquet_sink_handles_empty_then_non_empty_chunk_and_safe_close(tmp_path) -> None:
    output = tmp_path / "canonical.parquet"
    empty = pd.DataFrame({
        "loan_id": pd.Series(dtype="string"),
        "target": pd.Series(dtype="Int8"),
    })
    non_empty = pd.DataFrame({
        "loan_id": pd.Series(["1"], dtype="string"),
        "target": pd.Series([0], dtype="Int8"),
    })

    sink = ParquetSink(output)
    sink.write(empty)
    sink.write(non_empty)
    sink.close()
    sink.close()

    saved = pd.read_parquet(output)
    assert saved["loan_id"].tolist() == ["1"]
    assert saved["target"].tolist() == [0]

    unused = ParquetSink(tmp_path / "unused.parquet")
    unused.close()
    unused.close()


def test_de_lc_07_only_path_writes_canonical_without_de_lc_08_outputs(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    reports_dir = tmp_path / "reports"
    interim_dir = tmp_path / "interim"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    raw = pd.DataFrame({
        "id": ["1", "2", "3"],
        "loan_status": ["Fully Paid", "Current", "Default"],
        "loan_amnt": [10000, 5000, 7000], "annual_inc": [50000, 60000, 70000],
        "fico_range_low": [680, 700, 720], "fico_range_high": [684, 704, 724],
        "issue_d": ["Jan-2018", "Feb-2018", "Mar-2018"],
        "earliest_cr_line": ["Jan-2008", "Jan-2010", "Jan-2012"],
        "dti": [10, 20, 30],
    })
    raw.to_csv(raw_dir / "accepted_loans.csv", index=False)
    tables = prepare_accepted_batch(raw)
    interim_dir.mkdir()
    for name in ("loan_application", "borrower_profile", "credit_profile", "loan_outcome"):
        sink = ParquetSink(interim_dir / f"{name}.parquet")
        sink.write(tables[name])
        sink.close()

    context = RunnerContext(raw_dir, reports_dir, interim_dir, processed_dir, chunksize=2)
    context.marker_dir.mkdir(parents=True)
    for index in range(1, 7):
        (context.marker_dir / f"de-lc-{index:02d}.json").write_text(
            json.dumps({"status": "PASS"}), encoding="utf-8"
        )

    result = run_stage(
        "de-lc-07", raw_dir=raw_dir, reports_dir=reports_dir,
        interim_dir=interim_dir, processed_dir=processed_dir, chunksize=2,
    )

    assert result.status == "PASS"
    assert (processed_dir / "cleaned_dataset.parquet").is_file()
    assert not (interim_dir / "dim_date.parquet").exists()
    assert not (interim_dir / "dim_state.parquet").exists()
    assert not (processed_dir / "data_dictionary.csv").exists()
    assert result.message
