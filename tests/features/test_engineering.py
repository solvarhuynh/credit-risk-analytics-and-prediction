import numpy as np
import pandas as pd

from src.data.column_policy import ColumnClass, MODEL_ELIGIBLE_CLASSES, classify_column
from src.features.engineering import ENGINEERED_FEATURES, engineer_lending_club_features, safe_ratio


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


def test_fico_band_uses_left_closed_boundaries() -> None:
    frame = pd.DataFrame({
        "loan_amnt": [10000] * 6,
        "annual_inc": [50000] * 6,
        "fico_range_low": [640, 650, 699, 700, 749, 750],
        "fico_range_high": [640, 650, 699, 700, 749, 750],
        "issue_d": pd.to_datetime(["2018-01-01"] * 6),
        "earliest_cr_line": pd.to_datetime(["2008-01-01"] * 6),
        "dti": [10] * 6,
    })

    result, _ = engineer_lending_club_features(frame)

    assert result["fico_band"].astype("string").tolist() == [
        "<650", "650-699", "650-699", "700-749", "700-749", "750+",
    ]


def test_engineered_features_handle_missing_values_and_never_create_infinity() -> None:
    frame = pd.DataFrame({
        "loan_amnt": [10000, 10000, 10000, 10000],
        "annual_inc": [0, -1, np.nan, 50000],
        "fico_range_low": [680, np.nan, 680, 680],
        "fico_range_high": [684, 700, 684, 684],
        "issue_d": pd.to_datetime(["2018-01-01", "2018-01-01", None, "2018-01-01"]),
        "earliest_cr_line": pd.to_datetime(["2008-01-01", "2020-01-01", "2008-01-01", None]),
        "dti": [10, 20, 30, 40],
    })

    result, report = engineer_lending_club_features(frame)

    assert result["loan_to_income_ratio"].isna().tolist() == [True, True, True, False]
    assert pd.isna(result.loc[1, "fico_avg"])
    assert pd.isna(result.loc[1, "credit_history_months"])
    assert pd.isna(result.loc[2, "credit_history_months"])
    assert pd.isna(result.loc[3, "credit_history_months"])
    assert pd.isna(result.loc[2, "issue_year"])
    assert pd.isna(result.loc[2, "issue_quarter"])
    assert pd.isna(result.loc[2, "issue_month"])
    assert report["infinity_count"] == 0
    assert not np.isinf(result.select_dtypes(include=["number"]).to_numpy(dtype=float, na_value=np.nan)).any()


def test_amount_income_and_dti_band_boundaries_match_labels() -> None:
    frame = pd.DataFrame({
        "loan_amnt": [5000, 5000.01, 10000, 10000.01, 20000, 20000.01],
        "annual_inc": [40000, 40000.01, 80000, 80000.01, 150000, 150000.01],
        "fico_range_low": [700] * 6,
        "fico_range_high": [700] * 6,
        "issue_d": pd.to_datetime(["2018-01-01"] * 6),
        "earliest_cr_line": pd.to_datetime(["2008-01-01"] * 6),
        "dti": [10, 10.01, 20, 20.01, 30, 30.01],
    })

    result, _ = engineer_lending_club_features(frame)

    assert result["loan_amount_band"].astype("string").tolist() == [
        "<=5k", "5k-10k", "5k-10k", "10k-20k", "10k-20k", ">20k",
    ]
    assert result["income_band"].astype("string").tolist() == [
        "<=40k", "40k-80k", "40k-80k", "80k-150k", "80k-150k", ">150k",
    ]
    assert result["dti_band"].astype("string").tolist() == [
        "<=10", "10-20", "10-20", "20-30", "20-30", ">30",
    ]


def test_engineered_features_have_approved_policy_classes() -> None:
    policy = {feature: classify_column(feature) for feature in ENGINEERED_FEATURES}

    assert set(policy) == set(ENGINEERED_FEATURES)
    assert all(policy[feature] in MODEL_ELIGIBLE_CLASSES for feature in ENGINEERED_FEATURES)
    assert all(
        policy[feature] not in {
            ColumnClass.UNKNOWN_REVIEW_REQUIRED,
            ColumnClass.POST_LOAN,
            ColumnClass.TARGET_SOURCE,
            ColumnClass.POLICY_DERIVED,
        }
        for feature in ENGINEERED_FEATURES
    )
