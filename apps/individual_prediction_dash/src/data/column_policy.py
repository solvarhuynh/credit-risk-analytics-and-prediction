"""Phân loại cột Lending Club theo thời điểm sẵn có và rủi ro leakage.

Chính sách đóng mặc định: cột không được nhận diện sẽ thuộc
``UNKNOWN_REVIEW_REQUIRED`` và không được đi vào mô hình.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Iterable


class ColumnClass(StrEnum):
    IDENTIFIER = "IDENTIFIER"
    APPLICATION_TIME = "APPLICATION_TIME"
    CREDIT_SNAPSHOT = "CREDIT_SNAPSHOT"
    POLICY_DERIVED = "POLICY_DERIVED"
    GEOGRAPHY_ANALYTICS = "GEOGRAPHY_ANALYTICS"
    TEXT_HIGH_CARDINALITY = "TEXT_HIGH_CARDINALITY"
    TARGET_SOURCE = "TARGET_SOURCE"
    POST_LOAN = "POST_LOAN"
    ANALYTICS_ONLY = "ANALYTICS_ONLY"
    UNKNOWN_REVIEW_REQUIRED = "UNKNOWN_REVIEW_REQUIRED"


MODEL_ELIGIBLE_CLASSES = {ColumnClass.APPLICATION_TIME, ColumnClass.CREDIT_SNAPSHOT}
IDENTIFIERS = {"id", "loan_id", "member_id", "url", "rejected_application_id"}
TARGET_SOURCES = {"loan_status"}
GEOGRAPHY = {"addr_state", "state", "state_code", "zip_code", "country"}
HIGH_CARDINALITY_TEXT = {"emp_title", "title", "desc", "loan_title"}
POLICY_DERIVED = {
    "funded_amnt", "funded_amnt_inv", "int_rate", "installment", "grade",
    "sub_grade", "initial_list_status", "policy_code", "risk_score",
}
APPLICATION_TIME = {
    "loan_amnt", "requested_amount", "term", "term_months", "emp_length",
    "emp_length_years", "home_ownership", "annual_inc", "verification_status",
    "issue_d", "application_date", "purpose", "application_type",
    "annual_inc_joint", "verification_status_joint", "issue_year",
    "issue_quarter", "issue_month", "loan_to_income_ratio", "loan_amount_band",
    "income_band",
}
CREDIT_SNAPSHOT = {
    "dti", "dti_joint", "delinq_2yrs", "earliest_cr_line", "fico_range_low",
    "fico_range_high", "fico_avg", "inq_last_6mths", "mths_since_last_delinq",
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
    "credit_history_months", "fico_band", "dti_band",
}
POST_LOAN_EXACT = {
    "out_prncp", "out_prncp_inv", "total_pymnt", "total_pymnt_inv",
    "total_rec_prncp", "total_rec_int", "total_rec_late_fee", "recoveries",
    "collection_recovery_fee", "last_pymnt_d", "last_pymnt_amnt", "next_pymnt_d",
    "last_credit_pull_d", "last_fico_range_high", "last_fico_range_low",
    "debt_settlement_flag", "deferral_term", "payment_plan_start_date",
    "orig_projected_additional_accrued_interest",
}
POST_LOAN_PREFIXES = ("hardship_", "settlement_", "debt_settlement_")
ANALYTICS_ONLY = {"pymnt_plan", "disbursement_method", "target"}


def classify_column(column: str) -> ColumnClass:
    name = column.strip().lower()
    if name in IDENTIFIERS:
        return ColumnClass.IDENTIFIER
    if name in TARGET_SOURCES:
        return ColumnClass.TARGET_SOURCE
    if name in POST_LOAN_EXACT or name.startswith(POST_LOAN_PREFIXES):
        return ColumnClass.POST_LOAN
    if name in POLICY_DERIVED:
        return ColumnClass.POLICY_DERIVED
    if name in GEOGRAPHY:
        return ColumnClass.GEOGRAPHY_ANALYTICS
    if name in HIGH_CARDINALITY_TEXT:
        return ColumnClass.TEXT_HIGH_CARDINALITY
    if name in APPLICATION_TIME:
        return ColumnClass.APPLICATION_TIME
    if name in CREDIT_SNAPSHOT:
        return ColumnClass.CREDIT_SNAPSHOT
    if name in ANALYTICS_ONLY:
        return ColumnClass.ANALYTICS_ONLY
    return ColumnClass.UNKNOWN_REVIEW_REQUIRED


def classify_columns(columns: Iterable[str]) -> dict[str, ColumnClass]:
    return {column: classify_column(column) for column in columns}


def approved_model_features(columns: Iterable[str]) -> list[str]:
    return [column for column in columns if classify_column(column) in MODEL_ELIGIBLE_CLASSES]


def unknown_columns(columns: Iterable[str]) -> list[str]:
    return [column for column in columns if classify_column(column) == ColumnClass.UNKNOWN_REVIEW_REQUIRED]


def assert_no_forbidden_features(columns: Iterable[str]) -> None:
    forbidden = [column for column in columns if classify_column(column) not in MODEL_ELIGIBLE_CLASSES]
    if forbidden:
        raise ValueError(f"Model feature list chứa cột chưa được phép: {sorted(forbidden)}")
