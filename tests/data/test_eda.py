import pandas as pd

from src.data.eda import accepted_rejected_by_state, default_rate_by, loan_trend


def test_eda_summaries() -> None:
    accepted = pd.DataFrame({"loan_id": ["1", "2"], "target": [0, 1], "purpose": ["car", "car"], "issue_d": ["2018-01-01", "2018-02-01"], "loan_amnt": [1000, 2000], "state_code": ["CA", "NY"]})
    rejected = pd.DataFrame({"state_code": ["CA", "CA"]})
    assert default_rate_by(accepted, "purpose").loc[0, "default_rate"] == 0.5
    assert len(loan_trend(accepted)) == 2
    state = accepted_rejected_by_state(accepted, rejected).set_index("state_code")
    assert state.loc["CA", "rejected_count"] == 2
