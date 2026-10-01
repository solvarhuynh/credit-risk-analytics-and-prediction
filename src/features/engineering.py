"""Đặc trưng Lending Club chỉ dùng dữ liệu có tại/giáp thời điểm cấp khoản vay."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

ENGINEERED_FEATURES = (
    "fico_avg", "loan_to_income_ratio", "credit_history_months", "issue_year",
    "issue_quarter", "issue_month", "loan_amount_band", "income_band", "fico_band",
    "dti_band",
)


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    result = pd.Series(np.nan, index=numerator.index, dtype="float64")
    valid = num.notna() & den.notna() & np.isfinite(num) & np.isfinite(den) & (den > 0)
    result.loc[valid] = num.loc[valid] / den.loc[valid]
    return result


def engineer_lending_club_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {"loan_amnt", "annual_inc", "fico_range_low", "fico_range_high", "issue_d", "earliest_cr_line"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Thiếu cột nguồn để tạo feature: {missing}")
    result = frame.copy()
    low = pd.to_numeric(result["fico_range_low"], errors="coerce")
    high = pd.to_numeric(result["fico_range_high"], errors="coerce")
    result["fico_avg"] = pd.concat([low, high], axis=1).mean(axis=1, skipna=False)
    result["loan_to_income_ratio"] = safe_ratio(result["loan_amnt"], result["annual_inc"])
    issue = pd.to_datetime(result["issue_d"], errors="coerce")
    earliest = pd.to_datetime(result["earliest_cr_line"], errors="coerce")
    months = (issue.dt.year - earliest.dt.year) * 12 + issue.dt.month - earliest.dt.month
    result["credit_history_months"] = months.where(months >= 0).astype("Float64")
    result["issue_year"] = issue.dt.year.astype("Int64")
    result["issue_quarter"] = ("Q" + issue.dt.quarter.astype("Int64").astype("string")).where(issue.notna())
    result["issue_month"] = issue.dt.month.astype("Int64")
    result["loan_amount_band"] = pd.cut(
        pd.to_numeric(result["loan_amnt"], errors="coerce"),
        bins=[-np.inf, 5000, 10000, 20000, np.inf], labels=["<=5k", "5k-10k", "10k-20k", ">20k"],
    )
    result["income_band"] = pd.cut(
        pd.to_numeric(result["annual_inc"], errors="coerce"),
        bins=[-np.inf, 40000, 80000, 150000, np.inf], labels=["<=40k", "40k-80k", "80k-150k", ">150k"],
    )
    result["fico_band"] = pd.cut(
        result["fico_avg"], bins=[-np.inf, 650, 700, 750, np.inf], labels=["<650", "650-699", "700-749", "750+"],
    )
    dti = pd.to_numeric(result["dti"], errors="coerce") if "dti" in result else pd.Series(np.nan, index=result.index)
    result["dti_band"] = pd.cut(dti, bins=[-np.inf, 10, 20, 30, np.inf], labels=["<=10", "10-20", "20-30", ">30"])
    numeric = result.select_dtypes(include=["number"])
    infinity_count = int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum())
    if infinity_count:
        raise ValueError("Feature engineering tạo giá trị vô cực.")
    return result, {"rows": len(result), "features_added": list(ENGINEERED_FEATURES), "infinity_count": 0}
