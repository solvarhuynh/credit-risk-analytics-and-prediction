import pandas as pd
import pytest

from src.data.cleaning import clean_accepted_loans, clean_rejected_loans, derive_target


@pytest.mark.parametrize(
    ("status", "expected_target"),
    [
        ("Fully Paid", 0),
        ("Charged Off", 1),
        ("Default", 1),
        ("Current", None),
        ("Late (16-30 days)", None),
        ("Late (31-120 days)", None),
        ("In Grace Period", None),
        ("Does not meet the credit policy. Status:Fully Paid", None),
        ("Does not meet the credit policy. Status:Charged Off", None),
        (None, None),
    ],
)
def test_derive_target_uses_only_explicit_final_statuses(status, expected_target) -> None:
    result = derive_target(pd.Series([status], dtype="string"))

    if expected_target is None:
        assert pd.isna(result.iloc[0])
    else:
        assert result.iloc[0] == expected_target


def test_clean_accepted_and_target_policy() -> None:
    raw = pd.DataFrame({
        "id": ["1", "2", "3", "4"],
        "loan_status": ["Fully Paid", "Charged Off", "Default", "Current"],
        "int_rate": ["10.5%", "12%", None, "8%"],
        "term": ["36 months"] * 4,
        "emp_length": ["< 1 year", "10+ years", None, "3 years"],
        "addr_state": ["ca", "NY", "bad", None],
        "zip_code": ["941xx", "001xx", "oops", None],
    })
    cleaned, report = clean_accepted_loans(raw)
    assert cleaned["loan_id"].tolist() == ["1", "2", "3", "4"]
    assert cleaned["target"].tolist()[:3] == [0, 1, 1]
    assert pd.isna(cleaned.loc[3, "target"])
    assert cleaned["term_months"].tolist() == [36, 36, 36, 36]
    assert cleaned.loc[0, "emp_length_years"] == 0.5
    assert cleaned.loc[1, "emp_length_years"] == 10
    assert cleaned.loc[0, "state_code"] == "CA"
    assert pd.isna(cleaned.loc[2, "state_code"])
    assert report["unresolved_status_rows"] == 1


def test_legacy_status_is_not_mapped_blindly() -> None:
    raw = pd.DataFrame({"id": ["1"], "loan_status": ["Does not meet the credit policy. Status:Fully Paid"]})
    cleaned, _ = clean_accepted_loans(raw)
    assert cleaned["target"].isna().all()


def test_clean_rejected_schema() -> None:
    raw = pd.DataFrame({
        "Amount Requested": [5000], "Application Date": ["2018-01-02"],
        "Loan Title": ["car"], "Risk_Score": [700],
        "Debt-To-Income Ratio": ["12.5%"], "Zip Code": ["021xx"],
        "State": ["ma"], "Employment Length": ["2 years"], "Policy Code": [0],
    })
    cleaned, _ = clean_rejected_loans(raw)
    assert cleaned.loc[0, "state_code"] == "MA"
    assert cleaned.loc[0, "zip_code"] == "021xx"
    assert cleaned.loc[0, "dti"] == 12.5
