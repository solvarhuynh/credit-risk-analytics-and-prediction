"""Làm sạch xác định cho raw accepted và rejected của Lending Club."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

GOOD_FINAL_STATUSES = {"Fully Paid"}
BAD_FINAL_STATUSES = {"Charged Off", "Default"}
PERCENT_COLUMNS = {"int_rate", "revol_util"}
ACCEPTED_DATE_COLUMNS = {
    "issue_d", "earliest_cr_line", "last_pymnt_d", "next_pymnt_d",
    "last_credit_pull_d", "hardship_start_date", "hardship_end_date",
    "payment_plan_start_date", "debt_settlement_flag_date", "settlement_date",
    "sec_app_earliest_cr_line",
}
ACCEPTED_NUMERIC_COLUMNS = {
    "loan_amnt", "funded_amnt", "funded_amnt_inv", "installment", "annual_inc",
    "dti", "fico_range_low", "fico_range_high", "inq_last_6mths", "open_acc",
    "pub_rec", "revol_bal", "total_acc", "annual_inc_joint", "dti_joint",
}


def _strip_strings(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(column).strip() for column in result.columns]
    for column in result.select_dtypes(include=["object", "string"]).columns:
        values = result[column].astype("string").str.strip()
        result[column] = values.replace({"": pd.NA, "null": pd.NA, "NULL": pd.NA, "n/a": pd.NA})
    return result


def parse_percent(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.replace("%", "", regex=False), errors="coerce")


def parse_term_months(series: pd.Series) -> pd.Series:
    extracted = series.astype("string").str.extract(r"(\d+)", expand=False)
    return pd.to_numeric(extracted, errors="coerce").astype("Int64")


def parse_employment_years(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.lower().str.strip()
    result = pd.to_numeric(text.str.extract(r"(\d+)", expand=False), errors="coerce").astype("Float64")
    result = result.mask(text.str.startswith("< 1", na=False), 0.5)
    result = result.mask(text.str.contains(r"10\+", regex=True, na=False), 10.0)
    return result.astype("Float64")


def normalize_state(series: pd.Series) -> pd.Series:
    state = series.astype("string").str.strip().str.upper()
    return state.where(state.str.fullmatch(r"[A-Z]{2}", na=False), pd.NA)


def normalize_zip(series: pd.Series) -> pd.Series:
    zip_code = series.astype("string").str.strip().str.lower()
    return zip_code.where(zip_code.str.fullmatch(r"\d{3,5}x{0,2}", na=False), pd.NA)


def derive_target(status: pd.Series) -> pd.Series:
    """Map duy nhất trạng thái cuối cùng đã duyệt; còn lại là unresolved."""

    result = pd.Series(pd.NA, index=status.index, dtype="Int8")
    result.loc[status.isin(GOOD_FINAL_STATUSES)] = 0
    result.loc[status.isin(BAD_FINAL_STATUSES)] = 1
    return result


def clean_accepted_loans(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if "id" not in frame.columns and "loan_id" not in frame.columns:
        raise ValueError("Accepted raw phải có cột id.")
    if "loan_status" not in frame.columns:
        raise ValueError("Accepted raw phải có cột loan_status.")
    result = _strip_strings(frame)
    if "id" in result.columns:
        result = result.rename(columns={"id": "loan_id"})
    result["loan_id"] = result["loan_id"].astype("string").str.replace(r"\.0$", "", regex=True)
    if result["loan_id"].isna().any() or result["loan_id"].duplicated().any():
        raise ValueError("loan_id phải non-null và unique trong mỗi batch.")
    for column in PERCENT_COLUMNS & set(result.columns):
        result[column] = parse_percent(result[column])
    for column in ACCEPTED_NUMERIC_COLUMNS & set(result.columns):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if "term" in result:
        result["term_months"] = parse_term_months(result["term"])
    if "emp_length" in result:
        result["emp_length_years"] = parse_employment_years(result["emp_length"])
    for column in ACCEPTED_DATE_COLUMNS & set(result.columns):
        result[column] = pd.to_datetime(result[column], format="%b-%Y", errors="coerce")
    if "addr_state" in result:
        result["state_code"] = normalize_state(result["addr_state"])
        result["country"] = "United States"
    if "zip_code" in result:
        result["zip_code"] = normalize_zip(result["zip_code"])
    result["target"] = derive_target(result["loan_status"])
    result.replace([np.inf, -np.inf], np.nan, inplace=True)
    report = {
        "rows": len(result),
        "final_labeled_rows": int(result["target"].notna().sum()),
        "unresolved_status_rows": int(result["target"].isna().sum()),
        "target_counts": {str(k): int(v) for k, v in result["target"].value_counts().items()},
    }
    return result, report


REJECTED_RENAME = {
    "Amount Requested": "requested_amount", "Application Date": "application_date",
    "Loan Title": "loan_title", "Risk_Score": "risk_score",
    "Debt-To-Income Ratio": "dti", "Zip Code": "zip_code", "State": "state_code",
    "Employment Length": "emp_length_years", "Policy Code": "policy_code",
}


def clean_rejected_loans(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    missing = sorted(set(REJECTED_RENAME) - set(frame.columns))
    if missing:
        raise ValueError(f"Rejected raw thiếu cột: {missing}")
    result = _strip_strings(frame).rename(columns=REJECTED_RENAME)
    for column in ("requested_amount", "risk_score", "policy_code"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["dti"] = parse_percent(result["dti"])
    result["emp_length_years"] = parse_employment_years(result["emp_length_years"])
    result["application_date"] = pd.to_datetime(result["application_date"], errors="coerce")
    result["state_code"] = normalize_state(result["state_code"])
    result["zip_code"] = normalize_zip(result["zip_code"])
    result["country"] = "United States"
    result.replace([np.inf, -np.inf], np.nan, inplace=True)
    coverage = float(result["state_code"].notna().mean()) if len(result) else 0.0
    return result, {"rows": len(result), "state_coverage": coverage}
