import pandas as pd

from src.data.aggregate import (
    build_borrower_profile_table,
    build_credit_profile_table,
    build_loan_application_table,
    build_loan_outcome_table,
    join_canonical_modeling_table,
)


def test_business_tables_join_one_to_one_without_post_loan_features() -> None:
    frame = pd.DataFrame({
        "loan_id": ["a", "b"], "loan_amnt": [1000, 2000],
        "annual_inc": [50000, 60000], "fico_range_low": [680, 700],
        "fico_range_high": [684, 704], "loan_status": ["Fully Paid", "Default"],
        "target": [0, 1], "total_pymnt": [1100, 200],
    })
    app = build_loan_application_table(frame)
    borrower = build_borrower_profile_table(frame)
    credit = build_credit_profile_table(frame)
    outcome = build_loan_outcome_table(frame)
    joined = join_canonical_modeling_table(app, borrower, credit, outcome)
    assert len(joined) == 2
    assert joined["loan_id"].is_unique
    assert "total_pymnt" in outcome
    assert "total_pymnt" not in joined
