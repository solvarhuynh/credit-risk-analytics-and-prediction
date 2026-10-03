import pandas as pd
import pytest

from src.data.aggregate import (
    build_borrower_profile_table,
    build_credit_profile_table,
    build_loan_application_table,
    build_loan_outcome_table,
    build_loan_pricing_table,
    build_rejected_applications_table,
    join_canonical_modeling_table,
)


ACCEPTED_BUILDERS = (
    build_loan_application_table,
    build_borrower_profile_table,
    build_credit_profile_table,
    build_loan_pricing_table,
    build_loan_outcome_table,
)


def _accepted_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "loan_id": ["a", "b"],
        "loan_amnt": [1000, 2000],
        "annual_inc": [50000, 60000],
        "fico_range_low": [680, 700],
        "fico_range_high": [684, 704],
        "loan_status": ["Fully Paid", "Default"],
        "target": [0, 1],
        "funded_amnt": [1000, 2000],
        "funded_amnt_inv": [1000, 2000],
        "int_rate": [5.0, 10.0],
        "installment": [30.0, 60.0],
        "grade": ["A", "B"],
        "sub_grade": ["A1", "B2"],
        "initial_list_status": ["w", "f"],
        "total_pymnt": [1100, 200],
    })


@pytest.mark.parametrize("builder", ACCEPTED_BUILDERS)
def test_all_accepted_business_tables_preserve_valid_one_to_one_grain(builder) -> None:
    result = builder(_accepted_frame())

    assert len(result) == 2
    assert "loan_id" in result.columns
    assert result["loan_id"].notna().all()
    assert result["loan_id"].is_unique


@pytest.mark.parametrize("builder", ACCEPTED_BUILDERS)
@pytest.mark.parametrize("bad_loan_ids", [["a", "a"], ["a", None]])
def test_accepted_business_tables_fail_closed_on_duplicate_or_null_loan_id(
    builder, bad_loan_ids
) -> None:
    frame = _accepted_frame()
    frame["loan_id"] = bad_loan_ids

    with pytest.raises(ValueError, match="loan_id phải non-null và unique"):
        builder(frame)


def test_business_tables_join_one_to_one_without_post_loan_features() -> None:
    frame = _accepted_frame()
    app = build_loan_application_table(frame)
    borrower = build_borrower_profile_table(frame)
    credit = build_credit_profile_table(frame)
    pricing = build_loan_pricing_table(frame)
    outcome = build_loan_outcome_table(frame)
    joined = join_canonical_modeling_table(app, borrower, credit, outcome)
    assert len(joined) == 2
    assert joined["loan_id"].is_unique
    assert set(pricing.columns) == {
        "loan_id", "funded_amnt", "funded_amnt_inv", "int_rate", "installment",
        "grade", "sub_grade", "initial_list_status",
    }
    assert "total_pymnt" in outcome
    assert "total_pymnt" not in joined
    assert not {"funded_amnt", "funded_amnt_inv", "int_rate", "installment"}.intersection(joined)


def test_rejected_applications_remain_separate_and_preserve_existing_grain() -> None:
    rejected = pd.DataFrame({
        "requested_amount": [1000, 2000],
        "application_date": ["2018-01-01", "2018-01-02"],
        "loan_title": ["A", "B"],
        "risk_score": [500, 600],
        "dti": [10, 20],
        "zip_code": ["123xx", "456xx"],
        "state_code": ["CA", "NY"],
        "emp_length_years": [2, 5],
        "policy_code": [1, 1],
        "country": ["United States", "United States"],
    })

    result = build_rejected_applications_table(rejected)

    assert len(result) == len(rejected)
    assert list(result.columns) == list(rejected.columns)
    assert result.equals(rejected)
    assert "loan_id" not in result.columns
    assert "rejected_application_id" not in result.columns
