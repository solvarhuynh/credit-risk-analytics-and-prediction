import numpy as np
import pandas as pd

from src.features.engineering import engineer_lending_club_features, safe_ratio


def test_feature_engineering_and_safe_zero_denominator() -> None:
    frame = pd.DataFrame({
        "loan_amnt": [10000, 5000], "annual_inc": [50000, 0],
        "fico_range_low": [680, 700], "fico_range_high": [684, 704],
        "issue_d": pd.to_datetime(["2018-01-01", "2018-02-01"]),
        "earliest_cr_line": pd.to_datetime(["2008-01-01", "2020-01-01"]),
        "dti": [10, 35],
    })
    result, report = engineer_lending_club_features(frame)
    assert result.loc[0, "fico_avg"] == 682
    assert result.loc[0, "loan_to_income_ratio"] == 0.2
    assert pd.isna(result.loc[1, "loan_to_income_ratio"])
    assert result.loc[0, "credit_history_months"] == 120
    assert pd.isna(result.loc[1, "credit_history_months"])
    assert report["infinity_count"] == 0
    assert np.isnan(safe_ratio(pd.Series([1]), pd.Series([0])).iloc[0])
