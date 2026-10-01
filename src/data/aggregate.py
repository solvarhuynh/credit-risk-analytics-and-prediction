"""Chuẩn hóa accepted loan thành các bảng nghiệp vụ một dòng mỗi khoản vay."""

from __future__ import annotations

import pandas as pd

from src.data.column_policy import ColumnClass, classify_column

LOAN_APPLICATION_COLUMNS = (
    "loan_id", "loan_amnt", "issue_d", "purpose", "term_months", "application_type",
)
BORROWER_PROFILE_COLUMNS = (
    "loan_id", "emp_title", "emp_length", "emp_length_years", "home_ownership",
    "annual_inc", "verification_status", "addr_state", "state_code", "zip_code",
    "country", "annual_inc_joint", "verification_status_joint",
)
CREDIT_PROFILE_COLUMNS = (
    "loan_id", "dti", "dti_joint", "delinq_2yrs", "earliest_cr_line",
    "fico_range_low", "fico_range_high", "inq_last_6mths", "mths_since_last_delinq",
    "mths_since_last_record", "open_acc", "pub_rec", "revol_bal", "revol_util",
    "total_acc", "collections_12_mths_ex_med", "mths_since_last_major_derog",
    "acc_now_delinq", "tot_coll_amt", "tot_cur_bal", "open_acc_6m", "open_act_il",
    "open_il_12m", "open_il_24m", "mths_since_rcnt_il", "total_bal_il", "il_util",
    "open_rv_12m", "open_rv_24m", "max_bal_bc", "all_util", "total_rev_hi_lim",
    "inq_fi", "total_cu_tl", "inq_last_12m", "acc_open_past_24mths", "avg_cur_bal",
    "bc_open_to_buy", "bc_util", "chargeoff_within_12_mths", "delinq_amnt",
    "mo_sin_old_il_acct", "mo_sin_old_rev_tl_op", "mo_sin_rcnt_rev_tl_op",
    "mo_sin_rcnt_tl", "mort_acc", "mths_since_recent_bc",
    "mths_since_recent_bc_dlq", "mths_since_recent_inq",
    "mths_since_recent_revol_delinq", "num_accts_ever_120_pd", "num_actv_bc_tl",
    "num_actv_rev_tl", "num_bc_sats", "num_bc_tl", "num_il_tl", "num_op_rev_tl",
    "num_rev_accts", "num_rev_tl_bal_gt_0", "num_sats", "num_tl_120dpd_2m",
    "num_tl_30dpd", "num_tl_90g_dpd_24m", "num_tl_op_past_12m", "pct_tl_nvr_dlq",
    "percent_bc_gt_75", "pub_rec_bankruptcies", "tax_liens", "tot_hi_cred_lim",
    "total_bal_ex_mort", "total_bc_limit", "total_il_high_credit_limit",
    "revol_bal_joint", "sec_app_fico_range_low", "sec_app_fico_range_high",
    "sec_app_earliest_cr_line", "sec_app_inq_last_6mths", "sec_app_mort_acc",
    "sec_app_open_acc", "sec_app_revol_util", "sec_app_open_act_il",
    "sec_app_num_rev_accts", "sec_app_chargeoff_within_12_mths",
    "sec_app_collections_12_mths_ex_med", "sec_app_mths_since_last_major_derog",
)
LOAN_PRICING_COLUMNS = (
    "loan_id", "funded_amnt", "funded_amnt_inv", "int_rate", "installment",
    "grade", "sub_grade", "initial_list_status",
)


def _select(frame: pd.DataFrame, columns: tuple[str, ...], table_name: str) -> pd.DataFrame:
    if "loan_id" not in frame:
        raise ValueError(f"{table_name}: thiếu loan_id.")
    result = frame.loc[:, [column for column in columns if column in frame]].copy()
    if result["loan_id"].isna().any() or result["loan_id"].duplicated().any():
        raise ValueError(f"{table_name}: loan_id phải non-null và unique.")
    return result


def build_loan_application_table(frame: pd.DataFrame) -> pd.DataFrame:
    return _select(frame, LOAN_APPLICATION_COLUMNS, "loan_application")


def build_borrower_profile_table(frame: pd.DataFrame) -> pd.DataFrame:
    return _select(frame, BORROWER_PROFILE_COLUMNS, "borrower_profile")


def build_credit_profile_table(frame: pd.DataFrame) -> pd.DataFrame:
    return _select(frame, CREDIT_PROFILE_COLUMNS, "credit_profile")


def build_loan_pricing_table(frame: pd.DataFrame) -> pd.DataFrame:
    return _select(frame, LOAN_PRICING_COLUMNS, "loan_pricing")


def build_loan_outcome_table(frame: pd.DataFrame) -> pd.DataFrame:
    outcome_columns = [
        column for column in frame.columns
        if column in {"loan_id", "loan_status", "target"}
        or classify_column(column) == ColumnClass.POST_LOAN
    ]
    return _select(frame, tuple(outcome_columns), "loan_outcome")


def build_rejected_applications_table(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.copy()


def join_canonical_modeling_table(
    loan_application: pd.DataFrame,
    borrower_profile: pd.DataFrame,
    credit_profile: pd.DataFrame,
    loan_outcome: pd.DataFrame,
) -> pd.DataFrame:
    """Join 1:1 và chỉ lấy target từ outcome, không mang post-loan vào X."""

    base_rows = len(loan_application)
    result = loan_application.copy()
    for table in (borrower_profile, credit_profile):
        result = result.merge(table, on="loan_id", how="left", validate="one_to_one")
    target_only = loan_outcome.loc[:, ["loan_id", "target"]]
    result = result.merge(target_only, on="loan_id", how="left", validate="one_to_one")
    if len(result) != base_rows or not result["loan_id"].is_unique:
        raise ValueError("Join làm thay đổi grain một dòng mỗi loan_id.")
    return result


def build_date_dimension(*date_series: pd.Series) -> pd.DataFrame:
    valid = [pd.to_datetime(series, errors="coerce").dropna() for series in date_series]
    if not valid:
        return pd.DataFrame(columns=["date", "year", "quarter", "month", "month_name", "year_month"])
    dates = pd.Series(pd.concat(valid, ignore_index=True).dt.normalize().unique()).sort_values()
    return pd.DataFrame({
        "date": dates,
        "year": dates.dt.year,
        "quarter": "Q" + dates.dt.quarter.astype(str),
        "month": dates.dt.month,
        "month_name": dates.dt.month_name(),
        "year_month": dates.dt.to_period("M").astype(str),
    }).reset_index(drop=True)


def build_state_dimension(*state_series: pd.Series) -> pd.DataFrame:
    values = [series.dropna().astype("string").str.upper() for series in state_series]
    if not values:
        return pd.DataFrame(columns=["state_code", "country"])
    states = pd.concat(values, ignore_index=True).drop_duplicates().sort_values()
    return pd.DataFrame({"state_code": states, "country": "United States"}).reset_index(drop=True)
