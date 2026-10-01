import pandas as pd

from src.data.build_pipeline import build_data_dictionary, prepare_accepted_batch


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
    dictionary = build_data_dictionary(tables["canonical_labeled"])
    assert set(dictionary.columns) >= {"column_name", "policy_class", "model_eligible_default"}
