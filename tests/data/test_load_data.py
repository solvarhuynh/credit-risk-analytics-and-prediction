import pandas as pd

from src.data.load_data import load_accepted_loans, load_rejected_loans


def test_loaders_accept_tiny_local_schemas(tmp_path) -> None:
    pd.DataFrame({"id": ["1"], "loan_status": ["Fully Paid"]}).to_csv(tmp_path / "accepted_loans.csv", index=False)
    pd.DataFrame({"Zip Code": ["021xx"], "State": ["MA"]}).to_csv(tmp_path / "rejected_loans.csv", index=False)
    accepted = load_accepted_loans(raw_dir=tmp_path, nrows=1)
    rejected = load_rejected_loans(raw_dir=tmp_path, nrows=1)
    assert accepted.columns.tolist() == ["id", "loan_status"]
    assert rejected.loc[0, "Zip Code"] == "021xx"
