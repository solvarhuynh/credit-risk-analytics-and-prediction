"""Production-safe historical table aggregation module.

Converts each historical table into exactly one row per customer identified
by SK_ID_CURR:
- bureau.csv + bureau_balance.csv -> bureau_aggregated.parquet (prefix BUREAU_)
- previous_application.csv -> previous_application_aggregated.parquet (prefix PREV_)
- installments_payments.csv -> installments_payments_aggregated.parquet (prefix INSTAL_)
- POS_CASH_balance.csv -> pos_cash_balance_aggregated.parquet (prefix POS_)
- credit_card_balance.csv -> credit_card_balance_aggregated.parquet (prefix CC_)
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.load_data import default_raw_dir, validate_raw_files

KNOWN_RAW_CHECKSUMS: dict[str, str] = {
    "bureau.csv": "9d799143423f280720cf51c1bfbbab2a0422da8ff2763335bb30bf43155494f7",
    "bureau_balance.csv": "33e09f06174c26f0be6b8b7398886c69e7bf0abbb29b4122f7841ffe545729a9",
    "installments_payments.csv": "428c2e2496e4d6d697ee8270e98497e5213c41be16d882eed1bc95b133726797",
    "previous_application.csv": "5046cd657ee04df2eaa6dc8308ae86be6b3b1763674a3f63574886a2f2896505",
    "POS_CASH_balance.csv": "0e13bc573ffa8fc29b3f00d975e557143193a405d675b0e4694b06fbdffcb0cd",
    "credit_card_balance.csv": "a9cdc48900d55131c90f3128b991859aeb94ca1326fb5f4d1624b9fd03782247",
}

# ---------------------------------------------------------------------------
# Feature definitions metadata mapping
# ---------------------------------------------------------------------------

AGGREGATE_FEATURE_DEFINITIONS: dict[str, dict[str, str]] = {
    # ------------------ Bureau (20 features) ------------------
    "BUREAU_CREDIT_COUNT": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "count(SK_ID_BUREAU)",
        "unit": "count",
        "business_meaning": "Total number of previous credits reported by credit bureau for customer",
        "missing_value_interpretation": "Zero or missing if customer has no bureau credit records",
        "as_of_leakage_note": "As of application date; loan records opened prior to application",
    },
    "BUREAU_ACTIVE_COUNT": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "sum(CREDIT_ACTIVE == 'Active')",
        "unit": "count",
        "business_meaning": "Number of currently active bureau credits",
        "missing_value_interpretation": "Zero if customer has bureau credits but none are active",
        "as_of_leakage_note": "As of application date; status reported prior to application",
    },
    "BUREAU_ACTIVE_RATE": {
        "source_table": "bureau",
        "source_grain": "customer",
        "formula": "BUREAU_ACTIVE_COUNT / BUREAU_CREDIT_COUNT",
        "unit": "rate [0, 1]",
        "business_meaning": "Share of active credits among all reported bureau credits",
        "missing_value_interpretation": "Missing if customer has zero bureau credit records",
        "as_of_leakage_note": "Derived from as-of status; float ratio",
    },
    "BUREAU_CLOSED_COUNT": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "sum(CREDIT_ACTIVE == 'Closed')",
        "unit": "count",
        "business_meaning": "Number of closed bureau credits",
        "missing_value_interpretation": "Zero if customer has bureau credits but none are closed",
        "as_of_leakage_note": "As of application date",
    },
    "BUREAU_CLOSED_RATE": {
        "source_table": "bureau",
        "source_grain": "customer",
        "formula": "BUREAU_CLOSED_COUNT / BUREAU_CREDIT_COUNT",
        "unit": "rate [0, 1]",
        "business_meaning": "Share of closed credits among all reported bureau credits",
        "missing_value_interpretation": "Missing if customer has zero bureau credit records",
        "as_of_leakage_note": "Derived from as-of status; float ratio",
    },
    "BUREAU_DAYS_CREDIT_MEAN": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "mean(DAYS_CREDIT)",
        "unit": "days relative to application (negative)",
        "business_meaning": "Average days before application when bureau credits were applied for",
        "missing_value_interpretation": "Missing if DAYS_CREDIT is missing for all loans",
        "as_of_leakage_note": "DAYS_CREDIT <= 0 validated",
    },
    "BUREAU_DAYS_CREDIT_MAX": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "max(DAYS_CREDIT)",
        "unit": "days relative to application (negative, closest to application)",
        "business_meaning": "Most recent bureau credit application day relative to current application",
        "missing_value_interpretation": "Missing if DAYS_CREDIT is missing for all loans",
        "as_of_leakage_note": "DAYS_CREDIT <= 0 validated",
    },
    "BUREAU_CREDIT_DAY_OVERDUE_MEAN": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "mean(CREDIT_DAY_OVERDUE)",
        "unit": "days",
        "business_meaning": "Average number of overdue days across bureau credits",
        "missing_value_interpretation": "Missing if CREDIT_DAY_OVERDUE is missing for all loans",
        "as_of_leakage_note": "Historical delinquency duration as of application",
    },
    "BUREAU_CREDIT_DAY_OVERDUE_MAX": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "max(CREDIT_DAY_OVERDUE)",
        "unit": "days",
        "business_meaning": "Maximum overdue days on any bureau credit",
        "missing_value_interpretation": "Missing if CREDIT_DAY_OVERDUE is missing for all loans",
        "as_of_leakage_note": "Peak delinquency duration as of application",
    },
    "BUREAU_AMT_CREDIT_SUM_SUM": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "sum(AMT_CREDIT_SUM)",
        "unit": "currency",
        "business_meaning": "Total credit amount granted across all bureau loans",
        "missing_value_interpretation": "Missing if AMT_CREDIT_SUM is missing for all loans",
        "as_of_leakage_note": "Sum of historical credit limits as of application",
    },
    "BUREAU_AMT_CREDIT_SUM_MEAN": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "mean(AMT_CREDIT_SUM)",
        "unit": "currency",
        "business_meaning": "Average credit amount granted across bureau loans",
        "missing_value_interpretation": "Missing if AMT_CREDIT_SUM is missing for all loans",
        "as_of_leakage_note": "Historical credit scale indicator",
    },
    "BUREAU_AMT_DEBT_SUM": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "sum(AMT_CREDIT_SUM_DEBT)",
        "unit": "currency",
        "business_meaning": "Total outstanding debt on bureau credits",
        "missing_value_interpretation": "Missing if AMT_CREDIT_SUM_DEBT is missing for all loans",
        "as_of_leakage_note": "Current debt obligation as of application date",
    },
    "BUREAU_AMT_DEBT_MEAN": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "mean(AMT_CREDIT_SUM_DEBT)",
        "unit": "currency",
        "business_meaning": "Average outstanding debt across bureau credits",
        "missing_value_interpretation": "Missing if AMT_CREDIT_SUM_DEBT is missing for all loans",
        "as_of_leakage_note": "Average debt load per bureau loan",
    },
    "BUREAU_AMT_OVERDUE_SUM": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "sum(AMT_CREDIT_SUM_OVERDUE)",
        "unit": "currency",
        "business_meaning": "Total overdue amount on bureau credits",
        "missing_value_interpretation": "Missing if AMT_CREDIT_SUM_OVERDUE is missing for all loans",
        "as_of_leakage_note": "Past-due balance obligation as of application",
    },
    "BUREAU_AMT_OVERDUE_MAX": {
        "source_table": "bureau",
        "source_grain": "loan",
        "formula": "max(AMT_CREDIT_SUM_OVERDUE)",
        "unit": "currency",
        "business_meaning": "Maximum overdue amount on any single bureau credit",
        "missing_value_interpretation": "Missing if AMT_CREDIT_SUM_OVERDUE is missing for all loans",
        "as_of_leakage_note": "Worst past-due severity",
    },
    "BUREAU_BB_MONTH_COUNT": {
        "source_table": "bureau_balance",
        "source_grain": "loan-month",
        "formula": "sum(BB_MONTH_COUNT across loans)",
        "unit": "months count",
        "business_meaning": "Total monthly balance records observed across all bureau credits",
        "missing_value_interpretation": "Missing if customer has no loans with bureau balance records",
        "as_of_leakage_note": "MONTHS_BALANCE <= 0 validated",
    },
    "BUREAU_BB_DELINQUENT_MONTH_COUNT": {
        "source_table": "bureau_balance",
        "source_grain": "loan-month",
        "formula": "sum(BB_DELINQUENT_MONTH_COUNT across loans)",
        "unit": "months count",
        "business_meaning": "Total delinquent months (STATUS in {'1','2','3','4','5'}) across bureau credits",
        "missing_value_interpretation": "Missing if customer has no loans with bureau balance records",
        "as_of_leakage_note": "Historical delinquency months as of application",
    },
    "BUREAU_BB_DELINQUENT_MONTH_RATE": {
        "source_table": "bureau_balance",
        "source_grain": "customer",
        "formula": "sum(delinquent months) / sum(observed months)",
        "unit": "rate [0, 1]",
        "business_meaning": "Weighted rate of delinquent months over total observed bureau-balance months",
        "missing_value_interpretation": "Missing if observed month count is zero or missing",
        "as_of_leakage_note": "Globally weighted across customer's loans",
    },
    "BUREAU_BB_SEVERE_MONTH_COUNT": {
        "source_table": "bureau_balance",
        "source_grain": "loan-month",
        "formula": "sum(BB_SEVERE_MONTH_COUNT across loans)",
        "unit": "months count",
        "business_meaning": "Total severe delinquent months (STATUS in {'3','4','5'}) across bureau credits",
        "missing_value_interpretation": "Missing if customer has no loans with bureau balance records",
        "as_of_leakage_note": "Historical severe delinquency as of application",
    },
    "BUREAU_BB_SEVERE_MONTH_RATE": {
        "source_table": "bureau_balance",
        "source_grain": "customer",
        "formula": "sum(severe months) / sum(observed months)",
        "unit": "rate [0, 1]",
        "business_meaning": "Weighted rate of severe delinquent months over total observed bureau-balance months",
        "missing_value_interpretation": "Missing if observed month count is zero or missing",
        "as_of_leakage_note": "Globally weighted across customer's loans",
    },
    # ------------------ Previous Application (15 features) ------------------
    "PREV_APPLICATION_COUNT": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "count(SK_ID_PREV)",
        "unit": "count",
        "business_meaning": "Total number of previous Home Credit loan applications for customer",
        "missing_value_interpretation": "Zero or missing if customer has no previous applications",
        "as_of_leakage_note": "DAYS_DECISION <= 0 validated",
    },
    "PREV_APPROVED_COUNT": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "sum(NAME_CONTRACT_STATUS == 'Approved')",
        "unit": "count",
        "business_meaning": "Number of approved previous applications",
        "missing_value_interpretation": "Zero if customer has previous applications but none approved",
        "as_of_leakage_note": "Contract status decided prior to application date",
    },
    "PREV_APPROVED_RATE": {
        "source_table": "previous_application",
        "source_grain": "customer",
        "formula": "PREV_APPROVED_COUNT / PREV_APPLICATION_COUNT",
        "unit": "rate [0, 1]",
        "business_meaning": "Approval rate across all previous applications",
        "missing_value_interpretation": "Missing if customer has zero previous applications",
        "as_of_leakage_note": "Customer historical creditworthiness proxy",
    },
    "PREV_REFUSED_COUNT": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "sum(NAME_CONTRACT_STATUS == 'Refused')",
        "unit": "count",
        "business_meaning": "Number of refused previous applications",
        "missing_value_interpretation": "Zero if customer has previous applications but none refused",
        "as_of_leakage_note": "Refusal decision prior to application date",
    },
    "PREV_REFUSED_RATE": {
        "source_table": "previous_application",
        "source_grain": "customer",
        "formula": "PREV_REFUSED_COUNT / PREV_APPLICATION_COUNT",
        "unit": "rate [0, 1]",
        "business_meaning": "Refusal rate across all previous applications",
        "missing_value_interpretation": "Missing if customer has zero previous applications",
        "as_of_leakage_note": "Historical rejection frequency proxy",
    },
    "PREV_AMT_APPLICATION_SUM": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "sum(AMT_APPLICATION)",
        "unit": "currency",
        "business_meaning": "Total amount applied for across previous applications",
        "missing_value_interpretation": "Missing if AMT_APPLICATION is missing for all applications",
        "as_of_leakage_note": "Historical loan demand indicator",
    },
    "PREV_AMT_APPLICATION_MEAN": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "mean(AMT_APPLICATION)",
        "unit": "currency",
        "business_meaning": "Average loan amount applied for in previous applications",
        "missing_value_interpretation": "Missing if AMT_APPLICATION is missing for all applications",
        "as_of_leakage_note": "Average credit demand scale",
    },
    "PREV_AMT_APPLICATION_MAX": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "max(AMT_APPLICATION)",
        "unit": "currency",
        "business_meaning": "Maximum loan amount applied for in previous applications",
        "missing_value_interpretation": "Missing if AMT_APPLICATION is missing for all applications",
        "as_of_leakage_note": "Peak credit demand scale",
    },
    "PREV_AMT_CREDIT_SUM": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "sum(AMT_CREDIT)",
        "unit": "currency",
        "business_meaning": "Total credit amount granted in previous applications",
        "missing_value_interpretation": "Missing if AMT_CREDIT is missing for all applications",
        "as_of_leakage_note": "Total past credit extended by Home Credit",
    },
    "PREV_AMT_CREDIT_MEAN": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "mean(AMT_CREDIT)",
        "unit": "currency",
        "business_meaning": "Average credit amount granted in previous applications",
        "missing_value_interpretation": "Missing if AMT_CREDIT is missing for all applications",
        "as_of_leakage_note": "Average credit size extended",
    },
    "PREV_AMT_CREDIT_MAX": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "max(AMT_CREDIT)",
        "unit": "currency",
        "business_meaning": "Maximum credit amount granted in any previous application",
        "missing_value_interpretation": "Missing if AMT_CREDIT is missing for all applications",
        "as_of_leakage_note": "Peak credit line extended",
    },
    "PREV_AMT_ANNUITY_MEAN": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "mean(AMT_ANNUITY)",
        "unit": "currency",
        "business_meaning": "Average annuity payment across previous applications",
        "missing_value_interpretation": "Missing if AMT_ANNUITY is missing for all applications",
        "as_of_leakage_note": "Past payment burden indicator",
    },
    "PREV_CREDIT_TO_APPLICATION_RATIO_MEAN": {
        "source_table": "previous_application",
        "source_grain": "customer",
        "formula": "mean(AMT_CREDIT / AMT_APPLICATION)",
        "unit": "ratio (multiple)",
        "business_meaning": "Average ratio of granted credit to applied amount across applications",
        "missing_value_interpretation": "Missing if AMT_APPLICATION is missing, zero, or negative",
        "as_of_leakage_note": "Calculated row-wise on valid amounts then averaged per customer",
    },
    "PREV_DAYS_DECISION_MEAN": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "mean(DAYS_DECISION)",
        "unit": "days relative to application (negative)",
        "business_meaning": "Average days before application when previous decisions were made",
        "missing_value_interpretation": "Missing if DAYS_DECISION is missing for all applications",
        "as_of_leakage_note": "DAYS_DECISION <= 0 validated",
    },
    "PREV_DAYS_DECISION_MAX": {
        "source_table": "previous_application",
        "source_grain": "previous application",
        "formula": "max(DAYS_DECISION)",
        "unit": "days relative to application (negative, closest to application)",
        "business_meaning": "Most recent decision day among previous applications",
        "missing_value_interpretation": "Missing if DAYS_DECISION is missing for all applications",
        "as_of_leakage_note": "DAYS_DECISION <= 0 validated",
    },
    # ------------------ Installments Payments (10 features) ------------------
    "INSTAL_INSTALLMENT_COUNT": {
        "source_table": "installments_payments",
        "source_grain": "consolidated installment",
        "formula": "count(unique installment grains)",
        "unit": "count",
        "business_meaning": "Total consolidated installments scheduled across previous loans",
        "missing_value_interpretation": "Zero or missing if customer has no installment records",
        "as_of_leakage_note": "Split payments consolidated to prevent artificial count inflation",
    },
    "INSTAL_LATE_COUNT": {
        "source_table": "installments_payments",
        "source_grain": "consolidated installment",
        "formula": "sum(delay_days > 0)",
        "unit": "count",
        "business_meaning": "Number of installments paid after scheduled due date",
        "missing_value_interpretation": "Zero if customer has installments but none paid late",
        "as_of_leakage_note": "delay_days = max(DAYS_ENTRY_PAYMENT - DAYS_INSTALMENT, 0)",
    },
    "INSTAL_LATE_RATE": {
        "source_table": "installments_payments",
        "source_grain": "customer",
        "formula": "INSTAL_LATE_COUNT / INSTAL_INSTALLMENT_COUNT",
        "unit": "rate [0, 1]",
        "business_meaning": "Proportion of installments paid late",
        "missing_value_interpretation": "Missing if customer has zero installments",
        "as_of_leakage_note": "Installment payment discipline indicator",
    },
    "INSTAL_DELAY_DAYS_MEAN": {
        "source_table": "installments_payments",
        "source_grain": "consolidated installment",
        "formula": "mean(delay_days)",
        "unit": "days",
        "business_meaning": "Average payment delay days across scheduled installments",
        "missing_value_interpretation": "Missing if customer has zero installments",
        "as_of_leakage_note": "Nonnegative; clipped at 0 for on-time/early payments",
    },
    "INSTAL_DELAY_DAYS_MAX": {
        "source_table": "installments_payments",
        "source_grain": "consolidated installment",
        "formula": "max(delay_days)",
        "unit": "days",
        "business_meaning": "Maximum payment delay in days for any installment",
        "missing_value_interpretation": "Missing if customer has zero installments",
        "as_of_leakage_note": "Peak historical payment delay",
    },
    "INSTAL_UNDERPAYMENT_COUNT": {
        "source_table": "installments_payments",
        "source_grain": "consolidated installment",
        "formula": "sum(payment_shortfall > 0)",
        "unit": "count",
        "business_meaning": "Number of installments where total paid was less than scheduled amount",
        "missing_value_interpretation": "Zero if customer has installments but none underpaid",
        "as_of_leakage_note": "payment_shortfall = max(scheduled - paid, 0)",
    },
    "INSTAL_UNDERPAYMENT_RATE": {
        "source_table": "installments_payments",
        "source_grain": "customer",
        "formula": "INSTAL_UNDERPAYMENT_COUNT / INSTAL_INSTALLMENT_COUNT",
        "unit": "rate [0, 1]",
        "business_meaning": "Proportion of underpaid installments",
        "missing_value_interpretation": "Missing if customer has zero installments",
        "as_of_leakage_note": "Underpayment frequency indicator",
    },
    "INSTAL_PAYMENT_SHORTFALL_SUM": {
        "source_table": "installments_payments",
        "source_grain": "consolidated installment",
        "formula": "sum(payment_shortfall)",
        "unit": "currency",
        "business_meaning": "Total accumulated payment shortfall across all installments",
        "missing_value_interpretation": "Missing if customer has zero installments",
        "as_of_leakage_note": "Total unpaid installment obligation",
    },
    "INSTAL_PAYMENT_SHORTFALL_MEAN": {
        "source_table": "installments_payments",
        "source_grain": "consolidated installment",
        "formula": "mean(payment_shortfall)",
        "unit": "currency",
        "business_meaning": "Average payment shortfall per installment",
        "missing_value_interpretation": "Missing if customer has zero installments",
        "as_of_leakage_note": "Average shortfall severity",
    },
    "INSTAL_PAYMENT_RATIO_MEAN": {
        "source_table": "installments_payments",
        "source_grain": "customer",
        "formula": "mean(total_paid / scheduled_amount)",
        "unit": "ratio",
        "business_meaning": "Average ratio of amount paid to amount scheduled per installment",
        "missing_value_interpretation": "Missing if scheduled amount is zero or missing",
        "as_of_leakage_note": "Calculated row-wise on valid scheduled amounts then averaged",
    },
    # ------------------ POS CASH Balance (11 features) ------------------
    "POS_RECORD_COUNT": {
        "source_table": "POS_CASH_balance",
        "source_grain": "contract-month",
        "formula": "count(*)",
        "unit": "count",
        "business_meaning": "Total monthly balance records observed across POS/CASH loans",
        "missing_value_interpretation": "Zero or missing if customer has no POS CASH records",
        "as_of_leakage_note": "MONTHS_BALANCE <= 0 validated",
    },
    "POS_CONTRACT_COUNT": {
        "source_table": "POS_CASH_balance",
        "source_grain": "contract",
        "formula": "nunique(SK_ID_PREV)",
        "unit": "count",
        "business_meaning": "Number of unique POS/CASH contracts for customer",
        "missing_value_interpretation": "Zero or missing if customer has no POS CASH records",
        "as_of_leakage_note": "Unique contracts represented in POS balance",
    },
    "POS_MONTHS_BALANCE_MIN": {
        "source_table": "POS_CASH_balance",
        "source_grain": "contract-month",
        "formula": "min(MONTHS_BALANCE)",
        "unit": "months relative to application (negative, oldest)",
        "business_meaning": "Oldest month relative to application date observed in POS balance",
        "missing_value_interpretation": "Missing if customer has no POS CASH records",
        "as_of_leakage_note": "Historical window depth",
    },
    "POS_MONTHS_BALANCE_MAX": {
        "source_table": "POS_CASH_balance",
        "source_grain": "contract-month",
        "formula": "max(MONTHS_BALANCE)",
        "unit": "months relative to application (negative, most recent)",
        "business_meaning": "Most recent month relative to application date observed in POS balance",
        "missing_value_interpretation": "Missing if customer has no POS CASH records",
        "as_of_leakage_note": "Recency of POS balance observation",
    },
    "POS_DPD_MEAN": {
        "source_table": "POS_CASH_balance",
        "source_grain": "contract-month",
        "formula": "mean(SK_DPD)",
        "unit": "days",
        "business_meaning": "Average days past due across POS CASH monthly records",
        "missing_value_interpretation": "Missing if SK_DPD is missing for all records",
        "as_of_leakage_note": "Historical delinquency severity",
    },
    "POS_DPD_MAX": {
        "source_table": "POS_CASH_balance",
        "source_grain": "contract-month",
        "formula": "max(SK_DPD)",
        "unit": "days",
        "business_meaning": "Maximum days past due on any POS CASH monthly record",
        "missing_value_interpretation": "Missing if SK_DPD is missing for all records",
        "as_of_leakage_note": "Peak delinquency duration on POS loans",
    },
    "POS_DPD_DEF_MEAN": {
        "source_table": "POS_CASH_balance",
        "source_grain": "contract-month",
        "formula": "mean(SK_DPD_DEF)",
        "unit": "days",
        "business_meaning": "Average days past due with tolerance across POS records",
        "missing_value_interpretation": "Missing if SK_DPD_DEF is missing for all records",
        "as_of_leakage_note": "Default-tolerance delinquency average",
    },
    "POS_DPD_DEF_MAX": {
        "source_table": "POS_CASH_balance",
        "source_grain": "contract-month",
        "formula": "max(SK_DPD_DEF)",
        "unit": "days",
        "business_meaning": "Maximum days past due with tolerance across POS records",
        "missing_value_interpretation": "Missing if SK_DPD_DEF is missing for all records",
        "as_of_leakage_note": "Peak default-tolerance delinquency",
    },
    "POS_LATE_MONTH_COUNT": {
        "source_table": "POS_CASH_balance",
        "source_grain": "contract-month",
        "formula": "sum(SK_DPD > 0)",
        "unit": "count",
        "business_meaning": "Number of monthly records where customer had days past due > 0",
        "missing_value_interpretation": "Zero if customer has POS records but none past due",
        "as_of_leakage_note": "Delinquency frequency indicator",
    },
    "POS_LATE_MONTH_RATE": {
        "source_table": "POS_CASH_balance",
        "source_grain": "customer",
        "formula": "POS_LATE_MONTH_COUNT / POS_RECORD_COUNT",
        "unit": "rate [0, 1]",
        "business_meaning": "Proportion of POS monthly records with days past due > 0",
        "missing_value_interpretation": "Missing if customer has zero POS records",
        "as_of_leakage_note": "Late-month occurrence rate",
    },
    "POS_INSTALMENT_FUTURE_MEAN": {
        "source_table": "POS_CASH_balance",
        "source_grain": "contract-month",
        "formula": "mean(CNT_INSTALMENT_FUTURE)",
        "unit": "installments count",
        "business_meaning": "Average remaining installments future term across POS records",
        "missing_value_interpretation": "Missing if CNT_INSTALMENT_FUTURE is missing for all records",
        "as_of_leakage_note": "Remaining repayment horizon indicator",
    },
    # ------------------ Credit Card Balance (18 features) ------------------
    "CC_RECORD_COUNT": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "count(*)",
        "unit": "count",
        "business_meaning": "Total monthly credit card balance records observed for customer",
        "missing_value_interpretation": "Zero or missing if customer has no credit card records",
        "as_of_leakage_note": "MONTHS_BALANCE <= 0 validated",
    },
    "CC_CONTRACT_COUNT": {
        "source_table": "credit_card_balance",
        "source_grain": "contract",
        "formula": "nunique(SK_ID_PREV)",
        "unit": "count",
        "business_meaning": "Number of unique credit card contracts for customer",
        "missing_value_interpretation": "Zero or missing if customer has no credit card records",
        "as_of_leakage_note": "Unique credit cards held",
    },
    "CC_MONTHS_BALANCE_MIN": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "min(MONTHS_BALANCE)",
        "unit": "months relative to application (negative, oldest)",
        "business_meaning": "Oldest month observed in credit card history",
        "missing_value_interpretation": "Missing if customer has no credit card records",
        "as_of_leakage_note": "Credit card history depth",
    },
    "CC_MONTHS_BALANCE_MAX": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "max(MONTHS_BALANCE)",
        "unit": "months relative to application (negative, most recent)",
        "business_meaning": "Most recent month observed in credit card history",
        "missing_value_interpretation": "Missing if customer has no credit card records",
        "as_of_leakage_note": "Recency of credit card activity",
    },
    "CC_BALANCE_MEAN": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "mean(AMT_BALANCE)",
        "unit": "currency",
        "business_meaning": "Average outstanding balance across credit card months",
        "missing_value_interpretation": "Missing if AMT_BALANCE is missing for all records",
        "as_of_leakage_note": "Average revolving debt load",
    },
    "CC_BALANCE_MAX": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "max(AMT_BALANCE)",
        "unit": "currency",
        "business_meaning": "Maximum outstanding balance across credit card months",
        "missing_value_interpretation": "Missing if AMT_BALANCE is missing for all records",
        "as_of_leakage_note": "Peak revolving balance",
    },
    "CC_CREDIT_LIMIT_MEAN": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "mean(AMT_CREDIT_LIMIT_ACTUAL)",
        "unit": "currency",
        "business_meaning": "Average credit card limit across monthly records",
        "missing_value_interpretation": "Missing if AMT_CREDIT_LIMIT_ACTUAL is missing for all records",
        "as_of_leakage_note": "Average revolving credit line",
    },
    "CC_CREDIT_LIMIT_MAX": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "max(AMT_CREDIT_LIMIT_ACTUAL)",
        "unit": "currency",
        "business_meaning": "Maximum credit card limit across monthly records",
        "missing_value_interpretation": "Missing if AMT_CREDIT_LIMIT_ACTUAL is missing for all records",
        "as_of_leakage_note": "Peak revolving credit capacity",
    },
    "CC_UTILIZATION_MEAN": {
        "source_table": "credit_card_balance",
        "source_grain": "customer",
        "formula": "mean(AMT_BALANCE / AMT_CREDIT_LIMIT_ACTUAL)",
        "unit": "ratio",
        "business_meaning": "Average monthly credit card utilization rate",
        "missing_value_interpretation": "Missing if credit limit is zero, negative, or missing",
        "as_of_leakage_note": "Row-level utilization calculated when limit > 0, then averaged",
    },
    "CC_UTILIZATION_MAX": {
        "source_table": "credit_card_balance",
        "source_grain": "customer",
        "formula": "max(AMT_BALANCE / AMT_CREDIT_LIMIT_ACTUAL)",
        "unit": "ratio",
        "business_meaning": "Maximum monthly credit card utilization rate",
        "missing_value_interpretation": "Missing if credit limit is zero, negative, or missing",
        "as_of_leakage_note": "Peak revolving credit utilization",
    },
    "CC_DPD_MEAN": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "mean(SK_DPD)",
        "unit": "days",
        "business_meaning": "Average days past due on credit card records",
        "missing_value_interpretation": "Missing if SK_DPD is missing for all records",
        "as_of_leakage_note": "Credit card delinquency average",
    },
    "CC_DPD_MAX": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "max(SK_DPD)",
        "unit": "days",
        "business_meaning": "Maximum days past due on credit card records",
        "missing_value_interpretation": "Missing if SK_DPD is missing for all records",
        "as_of_leakage_note": "Peak credit card delinquency",
    },
    "CC_DPD_DEF_MEAN": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "mean(SK_DPD_DEF)",
        "unit": "days",
        "business_meaning": "Average default-tolerance days past due on credit cards",
        "missing_value_interpretation": "Missing if SK_DPD_DEF is missing for all records",
        "as_of_leakage_note": "Tolerated delinquency severity",
    },
    "CC_DPD_DEF_MAX": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "max(SK_DPD_DEF)",
        "unit": "days",
        "business_meaning": "Maximum default-tolerance days past due on credit cards",
        "missing_value_interpretation": "Missing if SK_DPD_DEF is missing for all records",
        "as_of_leakage_note": "Peak tolerated delinquency duration",
    },
    "CC_LATE_MONTH_COUNT": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "sum(SK_DPD > 0)",
        "unit": "count",
        "business_meaning": "Number of monthly credit card records with days past due > 0",
        "missing_value_interpretation": "Zero if customer has credit card records but none past due",
        "as_of_leakage_note": "Late credit card payment frequency",
    },
    "CC_LATE_MONTH_RATE": {
        "source_table": "credit_card_balance",
        "source_grain": "customer",
        "formula": "CC_LATE_MONTH_COUNT / CC_RECORD_COUNT",
        "unit": "rate [0, 1]",
        "business_meaning": "Proportion of credit card months with payment delay",
        "missing_value_interpretation": "Missing if customer has zero credit card records",
        "as_of_leakage_note": "Credit card late payment rate",
    },
    "CC_PAYMENT_TOTAL_SUM": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "sum(AMT_PAYMENT_TOTAL_CURRENT)",
        "unit": "currency",
        "business_meaning": "Total payments made by customer across credit card history",
        "missing_value_interpretation": "Missing if AMT_PAYMENT_TOTAL_CURRENT is missing for all records",
        "as_of_leakage_note": "Cumulative debt servicing on credit cards",
    },
    "CC_PAYMENT_TOTAL_MEAN": {
        "source_table": "credit_card_balance",
        "source_grain": "contract-month",
        "formula": "mean(AMT_PAYMENT_TOTAL_CURRENT)",
        "unit": "currency",
        "business_meaning": "Average monthly payment made on credit cards",
        "missing_value_interpretation": "Missing if AMT_PAYMENT_TOTAL_CURRENT is missing for all records",
        "as_of_leakage_note": "Average monthly revolving debt payment",
    },
}

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_temporal_bounds(
    frame: pd.DataFrame,
    column: str,
    table_name: str,
) -> None:
    """Validate that temporal field values do not extend past application date (<= 0).

    Args:
        frame: Source DataFrame.
        column: Name of temporal column.
        table_name: Source table name for diagnostic messages.

    Raises:
        ValueError: If any non-null positive temporal offset is detected.
    """
    if column not in frame.columns:
        return

    series = frame[column].dropna()
    if series.empty:
        return

    pos_mask = series > 0
    pos_count = int(pos_mask.sum())
    if pos_count > 0:
        max_val = float(series.max())
        sample_vals = series[pos_mask].head(5).tolist()
        raise ValueError(
            f"Leakage violation in {table_name}.{column}: detected {pos_count} "
            f"positive temporal offsets (max: {max_val}, sample: {sample_vals}). "
            "All historical events must have occurred on or before application date (<= 0)."
        )


def validate_customer_aggregate(
    frame: pd.DataFrame,
    prefix: str,
) -> None:
    """Validate customer-level aggregate contract requirements.

    Requirements:
    1. Exactly one row per represented SK_ID_CURR.
    2. SK_ID_CURR must never be null.
    3. SK_ID_CURR must be unique.
    4. No TARGET column.
    5. No duplicate column names.
    6. No positive or negative infinity.
    7. Every feature column must start with source prefix.
    8. Counts must be nonnegative.
    9. Rates must fall within [0, 1] when non-null.

    Args:
        frame: Customer aggregate DataFrame.
        prefix: Required column prefix (e.g., 'BUREAU_').

    Raises:
        ValueError: If any contract requirement is violated.
    """
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"Expected pandas DataFrame, got {type(frame)}")

    if "SK_ID_CURR" not in frame.columns:
        raise ValueError("Missing primary key 'SK_ID_CURR' in aggregate DataFrame.")

    if frame["SK_ID_CURR"].isna().any():
        null_count = int(frame["SK_ID_CURR"].isna().sum())
        raise ValueError(f"SK_ID_CURR contains {null_count} null values.")

    if frame["SK_ID_CURR"].duplicated().any():
        dup_count = int(frame["SK_ID_CURR"].duplicated().sum())
        raise ValueError(f"SK_ID_CURR contains {dup_count} duplicate values.")

    if "TARGET" in frame.columns:
        raise ValueError("Target leakage violation: 'TARGET' column found in historical aggregate.")

    if len(frame.columns) != len(set(frame.columns)):
        dup_cols = [c for c in frame.columns if list(frame.columns).count(c) > 1]
        raise ValueError(f"Duplicate column names found: {set(dup_cols)}")

    # Check prefix on all feature columns
    feature_cols = [c for c in frame.columns if c != "SK_ID_CURR"]
    for col in feature_cols:
        if not col.startswith(prefix):
            raise ValueError(f"Column '{col}' does not start with required prefix '{prefix}'.")

    # Check infinity
    for col in feature_cols:
        if pd.api.types.is_numeric_dtype(frame[col]):
            inf_mask = np.isinf(frame[col])
            if inf_mask.any():
                inf_count = int(inf_mask.sum())
                raise ValueError(f"Column '{col}' contains {inf_count} infinity values.")

    # Check nonnegative counts
    count_cols = [c for c in feature_cols if c.endswith("_COUNT")]
    for col in count_cols:
        s = frame[col].dropna()
        if (s < 0).any():
            raise ValueError(f"Count column '{col}' contains negative values.")

    # Check rates in [0, 1]
    rate_cols = [c for c in feature_cols if c.endswith("_RATE")]
    for col in rate_cols:
        s = frame[col].dropna()
        if (s < -1e-6).any() or (s > 1.0 + 1e-6).any():
            raise ValueError(f"Rate column '{col}' contains values outside [0, 1].")


# ---------------------------------------------------------------------------
# Individual table aggregation functions
# ---------------------------------------------------------------------------


def aggregate_bureau(
    bureau: pd.DataFrame,
    bureau_balance: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aggregate bureau and bureau_balance to customer grain (SK_ID_CURR).

    Strict two-stage aggregation:
    1. Aggregate bureau_balance to one row per SK_ID_BUREAU.
    2. Attach loan-level balance aggregate to bureau via SK_ID_BUREAU.
    3. Aggregate combined bureau data to one row per SK_ID_CURR.

    Args:
        bureau: Raw or pre-filtered bureau DataFrame.
        bureau_balance: Raw or pre-filtered bureau_balance DataFrame.

    Returns:
        Tuple of (aggregated_df, diagnostics_dict).

    Raises:
        ValueError: On schema violation or positive temporal offset.
    """
    # 1. Validate required source columns
    req_bureau = [
        "SK_ID_CURR",
        "SK_ID_BUREAU",
        "CREDIT_ACTIVE",
        "DAYS_CREDIT",
        "CREDIT_DAY_OVERDUE",
        "AMT_CREDIT_SUM",
        "AMT_CREDIT_SUM_DEBT",
        "AMT_CREDIT_SUM_OVERDUE",
    ]
    missing_b = [c for c in req_bureau if c not in bureau.columns]
    if missing_b:
        raise ValueError(f"bureau is missing required columns: {missing_b}")

    req_bb = ["SK_ID_BUREAU", "MONTHS_BALANCE", "STATUS"]
    missing_bb = [c for c in req_bb if c not in bureau_balance.columns]
    if missing_bb:
        raise ValueError(f"bureau_balance is missing required columns: {missing_bb}")

    # 2. Validate temporal bounds
    validate_temporal_bounds(bureau, "DAYS_CREDIT", "bureau")
    validate_temporal_bounds(bureau_balance, "MONTHS_BALANCE", "bureau_balance")

    # 3. Orphan bureau_balance detection
    bb_bureau_ids = set(bureau_balance["SK_ID_BUREAU"].dropna().unique())
    b_bureau_ids = set(bureau["SK_ID_BUREAU"].dropna().unique())
    orphan_ids = bb_bureau_ids - b_bureau_ids
    orphan_bureau_count = len(orphan_ids)
    orphan_row_count = int(bureau_balance["SK_ID_BUREAU"].isin(orphan_ids).sum())

    # 4. Stage 1: Aggregate bureau_balance by SK_ID_BUREAU
    if bureau_balance.empty:
        bb_agg = pd.DataFrame(
            columns=[
                "SK_ID_BUREAU",
                "bb_month_count",
                "bb_delinquent_month_count",
                "bb_severe_month_count",
            ]
        )
    else:
        bb_df = bureau_balance[["SK_ID_BUREAU", "MONTHS_BALANCE", "STATUS"]].copy()
        status_str = bb_df["STATUS"].astype(str)
        bb_df["is_delinquent"] = status_str.isin({"1", "2", "3", "4", "5"})
        bb_df["is_severe"] = status_str.isin({"3", "4", "5"})

        bb_agg = (
            bb_df.groupby("SK_ID_BUREAU", as_index=False)
            .agg(
                bb_month_count=("MONTHS_BALANCE", "count"),
                bb_delinquent_month_count=("is_delinquent", "sum"),
                bb_severe_month_count=("is_severe", "sum"),
            )
        )

    # 5. Stage 2: Join loan-level balance aggregate to bureau
    b_df = bureau[req_bureau].copy()
    b_joined = b_df.merge(bb_agg, on="SK_ID_BUREAU", how="left")

    # 6. Stage 3: Aggregate by SK_ID_CURR
    b_joined["is_active"] = (b_joined["CREDIT_ACTIVE"] == "Active").astype(int)
    b_joined["is_closed"] = (b_joined["CREDIT_ACTIVE"] == "Closed").astype(int)

    def agg_sum(s: pd.Series) -> Any:
        return s.sum(min_count=1)

    grouped = b_joined.groupby("SK_ID_CURR")
    res = grouped.agg(
        BUREAU_CREDIT_COUNT=("SK_ID_BUREAU", "count"),
        BUREAU_ACTIVE_COUNT=("is_active", "sum"),
        BUREAU_CLOSED_COUNT=("is_closed", "sum"),
        BUREAU_DAYS_CREDIT_MEAN=("DAYS_CREDIT", "mean"),
        BUREAU_DAYS_CREDIT_MAX=("DAYS_CREDIT", "max"),
        BUREAU_CREDIT_DAY_OVERDUE_MEAN=("CREDIT_DAY_OVERDUE", "mean"),
        BUREAU_CREDIT_DAY_OVERDUE_MAX=("CREDIT_DAY_OVERDUE", "max"),
        BUREAU_AMT_CREDIT_SUM_SUM=("AMT_CREDIT_SUM", agg_sum),
        BUREAU_AMT_CREDIT_SUM_MEAN=("AMT_CREDIT_SUM", "mean"),
        BUREAU_AMT_DEBT_SUM=("AMT_CREDIT_SUM_DEBT", agg_sum),
        BUREAU_AMT_DEBT_MEAN=("AMT_CREDIT_SUM_DEBT", "mean"),
        BUREAU_AMT_OVERDUE_SUM=("AMT_CREDIT_SUM_OVERDUE", agg_sum),
        BUREAU_AMT_OVERDUE_MAX=("AMT_CREDIT_SUM_OVERDUE", "max"),
        BUREAU_BB_MONTH_COUNT=("bb_month_count", agg_sum),
        BUREAU_BB_DELINQUENT_MONTH_COUNT=("bb_delinquent_month_count", agg_sum),
        BUREAU_BB_SEVERE_MONTH_COUNT=("bb_severe_month_count", agg_sum),
    ).reset_index()

    # Float rates
    res["BUREAU_ACTIVE_RATE"] = res["BUREAU_ACTIVE_COUNT"] / res["BUREAU_CREDIT_COUNT"]
    res["BUREAU_CLOSED_RATE"] = res["BUREAU_CLOSED_COUNT"] / res["BUREAU_CREDIT_COUNT"]

    # Weighted bureau-balance rates: delinquent / observed, NaN if observed == 0 or missing
    valid_bb = res["BUREAU_BB_MONTH_COUNT"].notna() & (res["BUREAU_BB_MONTH_COUNT"] > 0)
    delinq_rate = pd.Series(np.nan, index=res.index, dtype="float64")
    delinq_rate.loc[valid_bb] = (
        res.loc[valid_bb, "BUREAU_BB_DELINQUENT_MONTH_COUNT"] / res.loc[valid_bb, "BUREAU_BB_MONTH_COUNT"]
    )
    res["BUREAU_BB_DELINQUENT_MONTH_RATE"] = delinq_rate

    severe_rate = pd.Series(np.nan, index=res.index, dtype="float64")
    severe_rate.loc[valid_bb] = (
        res.loc[valid_bb, "BUREAU_BB_SEVERE_MONTH_COUNT"] / res.loc[valid_bb, "BUREAU_BB_MONTH_COUNT"]
    )
    res["BUREAU_BB_SEVERE_MONTH_RATE"] = severe_rate

    # Enforce exact column order
    ordered_cols = [
        "SK_ID_CURR",
        "BUREAU_CREDIT_COUNT",
        "BUREAU_ACTIVE_COUNT",
        "BUREAU_ACTIVE_RATE",
        "BUREAU_CLOSED_COUNT",
        "BUREAU_CLOSED_RATE",
        "BUREAU_DAYS_CREDIT_MEAN",
        "BUREAU_DAYS_CREDIT_MAX",
        "BUREAU_CREDIT_DAY_OVERDUE_MEAN",
        "BUREAU_CREDIT_DAY_OVERDUE_MAX",
        "BUREAU_AMT_CREDIT_SUM_SUM",
        "BUREAU_AMT_CREDIT_SUM_MEAN",
        "BUREAU_AMT_DEBT_SUM",
        "BUREAU_AMT_DEBT_MEAN",
        "BUREAU_AMT_OVERDUE_SUM",
        "BUREAU_AMT_OVERDUE_MAX",
        "BUREAU_BB_MONTH_COUNT",
        "BUREAU_BB_DELINQUENT_MONTH_COUNT",
        "BUREAU_BB_DELINQUENT_MONTH_RATE",
        "BUREAU_BB_SEVERE_MONTH_COUNT",
        "BUREAU_BB_SEVERE_MONTH_RATE",
    ]
    res = res[ordered_cols]
    validate_customer_aggregate(res, prefix="BUREAU_")

    diagnostics = {
        "table": "bureau",
        "raw_bureau_rows": len(bureau),
        "raw_bureau_balance_rows": len(bureau_balance),
        "unique_customers": len(res),
        "orphan_bureau_balance_ids": orphan_bureau_count,
        "orphan_bureau_balance_rows": orphan_row_count,
    }

    return res, diagnostics


def aggregate_previous_application(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aggregate previous_application to customer grain (SK_ID_CURR).

    Args:
        frame: Raw previous_application DataFrame.

    Returns:
        Tuple of (aggregated_df, diagnostics_dict).

    Raises:
        ValueError: On schema violation or positive temporal offset.
    """
    req_cols = [
        "SK_ID_PREV",
        "SK_ID_CURR",
        "NAME_CONTRACT_STATUS",
        "AMT_APPLICATION",
        "AMT_CREDIT",
        "AMT_ANNUITY",
        "DAYS_DECISION",
    ]
    missing = [c for c in req_cols if c not in frame.columns]
    if missing:
        raise ValueError(f"previous_application is missing required columns: {missing}")

    validate_temporal_bounds(frame, "DAYS_DECISION", "previous_application")

    df = frame[req_cols].copy()

    # Calculate row-level ratio: AMT_CREDIT / AMT_APPLICATION
    valid_app = (df["AMT_APPLICATION"] > 0) & np.isfinite(df["AMT_APPLICATION"])
    credit_to_app = pd.Series(np.nan, index=df.index, dtype="float64")
    credit_to_app.loc[valid_app] = df.loc[valid_app, "AMT_CREDIT"] / df.loc[valid_app, "AMT_APPLICATION"]
    df["credit_to_app_ratio"] = credit_to_app

    df["is_approved"] = (df["NAME_CONTRACT_STATUS"] == "Approved").astype(int)
    df["is_refused"] = (df["NAME_CONTRACT_STATUS"] == "Refused").astype(int)

    def agg_sum(s: pd.Series) -> Any:
        return s.sum(min_count=1)

    grouped = df.groupby("SK_ID_CURR")
    res = grouped.agg(
        PREV_APPLICATION_COUNT=("SK_ID_PREV", "count"),
        PREV_APPROVED_COUNT=("is_approved", "sum"),
        PREV_REFUSED_COUNT=("is_refused", "sum"),
        PREV_AMT_APPLICATION_SUM=("AMT_APPLICATION", agg_sum),
        PREV_AMT_APPLICATION_MEAN=("AMT_APPLICATION", "mean"),
        PREV_AMT_APPLICATION_MAX=("AMT_APPLICATION", "max"),
        PREV_AMT_CREDIT_SUM=("AMT_CREDIT", agg_sum),
        PREV_AMT_CREDIT_MEAN=("AMT_CREDIT", "mean"),
        PREV_AMT_CREDIT_MAX=("AMT_CREDIT", "max"),
        PREV_AMT_ANNUITY_MEAN=("AMT_ANNUITY", "mean"),
        PREV_CREDIT_TO_APPLICATION_RATIO_MEAN=("credit_to_app_ratio", "mean"),
        PREV_DAYS_DECISION_MEAN=("DAYS_DECISION", "mean"),
        PREV_DAYS_DECISION_MAX=("DAYS_DECISION", "max"),
    ).reset_index()

    res["PREV_APPROVED_RATE"] = res["PREV_APPROVED_COUNT"] / res["PREV_APPLICATION_COUNT"]
    res["PREV_REFUSED_RATE"] = res["PREV_REFUSED_COUNT"] / res["PREV_APPLICATION_COUNT"]

    ordered_cols = [
        "SK_ID_CURR",
        "PREV_APPLICATION_COUNT",
        "PREV_APPROVED_COUNT",
        "PREV_APPROVED_RATE",
        "PREV_REFUSED_COUNT",
        "PREV_REFUSED_RATE",
        "PREV_AMT_APPLICATION_SUM",
        "PREV_AMT_APPLICATION_MEAN",
        "PREV_AMT_APPLICATION_MAX",
        "PREV_AMT_CREDIT_SUM",
        "PREV_AMT_CREDIT_MEAN",
        "PREV_AMT_CREDIT_MAX",
        "PREV_AMT_ANNUITY_MEAN",
        "PREV_CREDIT_TO_APPLICATION_RATIO_MEAN",
        "PREV_DAYS_DECISION_MEAN",
        "PREV_DAYS_DECISION_MAX",
    ]
    res = res[ordered_cols]
    validate_customer_aggregate(res, prefix="PREV_")

    diagnostics = {
        "table": "previous_application",
        "raw_rows": len(frame),
        "unique_customers": len(res),
    }
    return res, diagnostics


def aggregate_installments_payments(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aggregate installments_payments consolidating split payments.

    Consolidates data to installment grain:
    (SK_ID_PREV, SK_ID_CURR, NUM_INSTALMENT_VERSION, NUM_INSTALMENT_NUMBER)
    Validates stability of scheduled date and scheduled amount.

    Args:
        frame: Raw installments_payments DataFrame.

    Returns:
        Tuple of (aggregated_df, diagnostics_dict).

    Raises:
        ValueError: On schema violation, positive temporal offset, or conflicting scheduled values.
    """
    req_cols = [
        "SK_ID_PREV",
        "SK_ID_CURR",
        "NUM_INSTALMENT_VERSION",
        "NUM_INSTALMENT_NUMBER",
        "DAYS_INSTALMENT",
        "DAYS_ENTRY_PAYMENT",
        "AMT_INSTALMENT",
        "AMT_PAYMENT",
    ]
    missing = [c for c in req_cols if c not in frame.columns]
    if missing:
        raise ValueError(f"installments_payments is missing required columns: {missing}")

    validate_temporal_bounds(frame, "DAYS_INSTALMENT", "installments_payments")
    validate_temporal_bounds(frame, "DAYS_ENTRY_PAYMENT", "installments_payments")

    df = frame[req_cols].copy()
    raw_row_count = len(df)

    key_cols = [
        "SK_ID_PREV",
        "SK_ID_CURR",
        "NUM_INSTALMENT_VERSION",
        "NUM_INSTALMENT_NUMBER",
    ]

    # Stage 1: Consolidate to installment grain
    # Validate scheduled stability within key groups
    agg_funcs = {
        "DAYS_INSTALMENT": ["min", "max"],
        "DAYS_ENTRY_PAYMENT": "max",
        "AMT_INSTALMENT": ["min", "max"],
        "AMT_PAYMENT": "sum",
    }
    grouped_raw = df.groupby(key_cols).agg(agg_funcs)

    d_min = grouped_raw[("DAYS_INSTALMENT", "min")]
    d_max = grouped_raw[("DAYS_INSTALMENT", "max")]
    date_conflicts = int((d_min != d_max).sum())
    if date_conflicts > 0:
        raise ValueError(
            f"installments_payments has {date_conflicts} installment keys with conflicting DAYS_INSTALMENT."
        )

    a_min = grouped_raw[("AMT_INSTALMENT", "min")]
    a_max = grouped_raw[("AMT_INSTALMENT", "max")]
    amt_conflicts = int((np.abs(a_min - a_max) > 1e-4).sum())
    if amt_conflicts > 0:
        raise ValueError(
            f"installments_payments has {amt_conflicts} installment keys with conflicting AMT_INSTALMENT."
        )

    consolidated = pd.DataFrame(
        {
            "SK_ID_PREV": grouped_raw.index.get_level_values(0),
            "SK_ID_CURR": grouped_raw.index.get_level_values(1),
            "DAYS_INSTALMENT": d_min.values,
            "DAYS_ENTRY_PAYMENT": grouped_raw[("DAYS_ENTRY_PAYMENT", "max")].values,
            "AMT_INSTALMENT": a_min.values,
            "AMT_PAYMENT": grouped_raw[("AMT_PAYMENT", "sum")].values,
        }
    )
    unique_grain_count = len(consolidated)
    repeated_key_count = int((df.groupby(key_cols).size() > 1).sum())
    rows_in_repeated_keys = raw_row_count - unique_grain_count + repeated_key_count

    # Calculate metrics on consolidated installments
    delay_days = (consolidated["DAYS_ENTRY_PAYMENT"] - consolidated["DAYS_INSTALMENT"]).clip(lower=0.0)
    shortfall = (consolidated["AMT_INSTALMENT"] - consolidated["AMT_PAYMENT"]).clip(lower=0.0)

    valid_sched = (consolidated["AMT_INSTALMENT"] > 0) & np.isfinite(consolidated["AMT_INSTALMENT"])
    payment_ratio = pd.Series(np.nan, index=consolidated.index, dtype="float64")
    payment_ratio.loc[valid_sched] = (
        consolidated.loc[valid_sched, "AMT_PAYMENT"] / consolidated.loc[valid_sched, "AMT_INSTALMENT"]
    )

    consolidated["delay_days"] = delay_days
    consolidated["shortfall"] = shortfall
    consolidated["payment_ratio"] = payment_ratio
    consolidated["is_late"] = (delay_days > 0).astype(int)
    consolidated["is_underpaid"] = (shortfall > 0).astype(int)

    def agg_sum(s: pd.Series) -> Any:
        return s.sum(min_count=1)

    # Stage 2: Aggregate by SK_ID_CURR
    cust_grouped = consolidated.groupby("SK_ID_CURR")
    res = cust_grouped.agg(
        INSTAL_INSTALLMENT_COUNT=("SK_ID_PREV", "count"),
        INSTAL_LATE_COUNT=("is_late", "sum"),
        INSTAL_DELAY_DAYS_MEAN=("delay_days", "mean"),
        INSTAL_DELAY_DAYS_MAX=("delay_days", "max"),
        INSTAL_UNDERPAYMENT_COUNT=("is_underpaid", "sum"),
        INSTAL_PAYMENT_SHORTFALL_SUM=("shortfall", agg_sum),
        INSTAL_PAYMENT_SHORTFALL_MEAN=("shortfall", "mean"),
        INSTAL_PAYMENT_RATIO_MEAN=("payment_ratio", "mean"),
    ).reset_index()

    res["INSTAL_LATE_RATE"] = res["INSTAL_LATE_COUNT"] / res["INSTAL_INSTALLMENT_COUNT"]
    res["INSTAL_UNDERPAYMENT_RATE"] = (
        res["INSTAL_UNDERPAYMENT_COUNT"] / res["INSTAL_INSTALLMENT_COUNT"]
    )

    ordered_cols = [
        "SK_ID_CURR",
        "INSTAL_INSTALLMENT_COUNT",
        "INSTAL_LATE_COUNT",
        "INSTAL_LATE_RATE",
        "INSTAL_DELAY_DAYS_MEAN",
        "INSTAL_DELAY_DAYS_MAX",
        "INSTAL_UNDERPAYMENT_COUNT",
        "INSTAL_UNDERPAYMENT_RATE",
        "INSTAL_PAYMENT_SHORTFALL_SUM",
        "INSTAL_PAYMENT_SHORTFALL_MEAN",
        "INSTAL_PAYMENT_RATIO_MEAN",
    ]
    res = res[ordered_cols]
    validate_customer_aggregate(res, prefix="INSTAL_")

    diagnostics = {
        "table": "installments_payments",
        "raw_installment_rows": raw_row_count,
        "unique_installment_grains": unique_grain_count,
        "repeated_installment_keys": repeated_key_count,
        "rows_in_repeated_keys": rows_in_repeated_keys,
        "unique_customers": len(res),
    }
    return res, diagnostics


def aggregate_pos_cash_balance(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aggregate POS_CASH_balance to customer grain (SK_ID_CURR).

    Args:
        frame: Raw POS_CASH_balance DataFrame.

    Returns:
        Tuple of (aggregated_df, diagnostics_dict).

    Raises:
        ValueError: On schema violation or positive temporal offset.
    """
    req_cols = [
        "SK_ID_PREV",
        "SK_ID_CURR",
        "MONTHS_BALANCE",
        "CNT_INSTALMENT_FUTURE",
        "SK_DPD",
        "SK_DPD_DEF",
    ]
    missing = [c for c in req_cols if c not in frame.columns]
    if missing:
        raise ValueError(f"POS_CASH_balance is missing required columns: {missing}")

    validate_temporal_bounds(frame, "MONTHS_BALANCE", "POS_CASH_balance")

    df = frame[req_cols].copy()
    df["is_late"] = (df["SK_DPD"] > 0).astype(int)

    grouped = df.groupby("SK_ID_CURR")
    res = grouped.agg(
        POS_RECORD_COUNT=("SK_ID_PREV", "count"),
        POS_CONTRACT_COUNT=("SK_ID_PREV", "nunique"),
        POS_MONTHS_BALANCE_MIN=("MONTHS_BALANCE", "min"),
        POS_MONTHS_BALANCE_MAX=("MONTHS_BALANCE", "max"),
        POS_DPD_MEAN=("SK_DPD", "mean"),
        POS_DPD_MAX=("SK_DPD", "max"),
        POS_DPD_DEF_MEAN=("SK_DPD_DEF", "mean"),
        POS_DPD_DEF_MAX=("SK_DPD_DEF", "max"),
        POS_LATE_MONTH_COUNT=("is_late", "sum"),
        POS_INSTALMENT_FUTURE_MEAN=("CNT_INSTALMENT_FUTURE", "mean"),
    ).reset_index()

    res["POS_LATE_MONTH_RATE"] = res["POS_LATE_MONTH_COUNT"] / res["POS_RECORD_COUNT"]

    ordered_cols = [
        "SK_ID_CURR",
        "POS_RECORD_COUNT",
        "POS_CONTRACT_COUNT",
        "POS_MONTHS_BALANCE_MIN",
        "POS_MONTHS_BALANCE_MAX",
        "POS_DPD_MEAN",
        "POS_DPD_MAX",
        "POS_DPD_DEF_MEAN",
        "POS_DPD_DEF_MAX",
        "POS_LATE_MONTH_COUNT",
        "POS_LATE_MONTH_RATE",
        "POS_INSTALMENT_FUTURE_MEAN",
    ]
    res = res[ordered_cols]
    validate_customer_aggregate(res, prefix="POS_")

    diagnostics = {
        "table": "POS_CASH_balance",
        "raw_rows": len(frame),
        "unique_customers": len(res),
    }
    return res, diagnostics


def aggregate_credit_card_balance(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aggregate credit_card_balance to customer grain (SK_ID_CURR).

    Args:
        frame: Raw credit_card_balance DataFrame.

    Returns:
        Tuple of (aggregated_df, diagnostics_dict).

    Raises:
        ValueError: On schema violation or positive temporal offset.
    """
    req_cols = [
        "SK_ID_PREV",
        "SK_ID_CURR",
        "MONTHS_BALANCE",
        "AMT_BALANCE",
        "AMT_CREDIT_LIMIT_ACTUAL",
        "SK_DPD",
        "SK_DPD_DEF",
        "AMT_PAYMENT_TOTAL_CURRENT",
    ]
    missing = [c for c in req_cols if c not in frame.columns]
    if missing:
        raise ValueError(f"credit_card_balance is missing required columns: {missing}")

    validate_temporal_bounds(frame, "MONTHS_BALANCE", "credit_card_balance")

    df = frame[req_cols].copy()

    # Calculate row-level utilization
    valid_limit = (df["AMT_CREDIT_LIMIT_ACTUAL"] > 0) & np.isfinite(df["AMT_CREDIT_LIMIT_ACTUAL"])
    utilization = pd.Series(np.nan, index=df.index, dtype="float64")
    utilization.loc[valid_limit] = (
        df.loc[valid_limit, "AMT_BALANCE"] / df.loc[valid_limit, "AMT_CREDIT_LIMIT_ACTUAL"]
    )
    df["utilization"] = utilization
    df["is_late"] = (df["SK_DPD"] > 0).astype(int)

    def agg_sum(s: pd.Series) -> Any:
        return s.sum(min_count=1)

    grouped = df.groupby("SK_ID_CURR")
    res = grouped.agg(
        CC_RECORD_COUNT=("SK_ID_PREV", "count"),
        CC_CONTRACT_COUNT=("SK_ID_PREV", "nunique"),
        CC_MONTHS_BALANCE_MIN=("MONTHS_BALANCE", "min"),
        CC_MONTHS_BALANCE_MAX=("MONTHS_BALANCE", "max"),
        CC_BALANCE_MEAN=("AMT_BALANCE", "mean"),
        CC_BALANCE_MAX=("AMT_BALANCE", "max"),
        CC_CREDIT_LIMIT_MEAN=("AMT_CREDIT_LIMIT_ACTUAL", "mean"),
        CC_CREDIT_LIMIT_MAX=("AMT_CREDIT_LIMIT_ACTUAL", "max"),
        CC_UTILIZATION_MEAN=("utilization", "mean"),
        CC_UTILIZATION_MAX=("utilization", "max"),
        CC_DPD_MEAN=("SK_DPD", "mean"),
        CC_DPD_MAX=("SK_DPD", "max"),
        CC_DPD_DEF_MEAN=("SK_DPD_DEF", "mean"),
        CC_DPD_DEF_MAX=("SK_DPD_DEF", "max"),
        CC_LATE_MONTH_COUNT=("is_late", "sum"),
        CC_PAYMENT_TOTAL_SUM=("AMT_PAYMENT_TOTAL_CURRENT", agg_sum),
        CC_PAYMENT_TOTAL_MEAN=("AMT_PAYMENT_TOTAL_CURRENT", "mean"),
    ).reset_index()

    res["CC_LATE_MONTH_RATE"] = res["CC_LATE_MONTH_COUNT"] / res["CC_RECORD_COUNT"]

    ordered_cols = [
        "SK_ID_CURR",
        "CC_RECORD_COUNT",
        "CC_CONTRACT_COUNT",
        "CC_MONTHS_BALANCE_MIN",
        "CC_MONTHS_BALANCE_MAX",
        "CC_BALANCE_MEAN",
        "CC_BALANCE_MAX",
        "CC_CREDIT_LIMIT_MEAN",
        "CC_CREDIT_LIMIT_MAX",
        "CC_UTILIZATION_MEAN",
        "CC_UTILIZATION_MAX",
        "CC_DPD_MEAN",
        "CC_DPD_MAX",
        "CC_DPD_DEF_MEAN",
        "CC_DPD_DEF_MAX",
        "CC_LATE_MONTH_COUNT",
        "CC_LATE_MONTH_RATE",
        "CC_PAYMENT_TOTAL_SUM",
        "CC_PAYMENT_TOTAL_MEAN",
    ]
    res = res[ordered_cols]
    validate_customer_aggregate(res, prefix="CC_")

    diagnostics = {
        "table": "credit_card_balance",
        "raw_rows": len(frame),
        "unique_customers": len(res),
    }
    return res, diagnostics


# ---------------------------------------------------------------------------
# File and pipeline orchestration
# ---------------------------------------------------------------------------


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024 * 8):
            h.update(chunk)
    return h.hexdigest()


def write_parquet_atomic(
    df: pd.DataFrame,
    target_path: Path,
    prefix: str,
) -> dict[str, Any]:
    """Write DataFrame to Parquet atomically and validate readback.

    Args:
        df: DataFrame to write.
        target_path: Final destination path.
        prefix: Source feature prefix.

    Returns:
        Metadata dict describing the published artifact.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.parent / f"{target_path.name}.tmp.{uuid.uuid4().hex}"

    try:
        df.to_parquet(temp_path, index=False, engine="pyarrow")

        # Read back and validate
        read_back = pd.read_parquet(temp_path, engine="pyarrow")
        validate_customer_aggregate(read_back, prefix=prefix)

        row_count = len(read_back)
        col_count = len(read_back.columns)
        min_id = int(read_back["SK_ID_CURR"].min()) if row_count > 0 else None
        max_id = int(read_back["SK_ID_CURR"].max()) if row_count > 0 else None
        del read_back

        os.replace(temp_path, target_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    file_size = target_path.stat().st_size
    file_sha256 = compute_file_sha256(target_path)

    return {
        "output_filename": target_path.name,
        "output_path": str(target_path),
        "feature_prefix": prefix,
        "row_count": row_count,
        "column_count": col_count,
        "feature_count": col_count - 1,
        "unique_customer_count": row_count,
        "null_key_count": 0,
        "duplicate_key_count": 0,
        "min_sk_id_curr": min_id,
        "max_sk_id_curr": max_id,
        "file_size_bytes": file_size,
        "sha256": file_sha256,
    }


def run_historical_aggregation(
    raw_dir: Path | str | None = None,
    interim_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Run production historical table aggregation on all 5 sources.

    Processes one source at a time with memory-safe column projection.

    Args:
        raw_dir: Path to directory containing raw CSVs. Defaults to data/raw.
        interim_dir: Path to directory for interim parquet outputs. Defaults to data/interim.

    Returns:
        Detailed operational manifest dict.

    Raises:
        ValueError: On checksum mismatch, schema violation, or leakage.
    """
    raw_paths = validate_raw_files(raw_dir)
    target_interim = Path(interim_dir) if interim_dir else Path("data/interim")
    target_interim.mkdir(parents=True, exist_ok=True)

    # 1. Preflight raw file checksums
    raw_checksums: dict[str, str] = {}
    for filename, expected_hash in KNOWN_RAW_CHECKSUMS.items():
        file_path = raw_paths[Path(filename).stem]
        actual_hash = compute_file_sha256(file_path)
        raw_checksums[filename] = actual_hash
        if actual_hash != expected_hash:
            raise ValueError(
                f"Raw checksum mismatch for {filename}: expected {expected_hash}, got {actual_hash}"
            )

    results: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_identifier": "TV2-DE-04",
        "raw_checksums": raw_checksums,
        "outputs": {},
        "diagnostics": {},
        "warnings": [
            "bureau_balance contains approximately 43,041 orphan SK_ID_BUREAU values excluded from customer mapping.",
            "installments_payments contains repeated installment-grain rows consolidated rather than discarded.",
        ],
    }

    # 2. Bureau + Bureau Balance
    bb_df = pd.read_csv(
        raw_paths["bureau_balance"],
        usecols=["SK_ID_BUREAU", "MONTHS_BALANCE", "STATUS"],
        dtype={"SK_ID_BUREAU": "int32", "MONTHS_BALANCE": "int16", "STATUS": "category"},
    )
    b_df = pd.read_csv(
        raw_paths["bureau"],
        usecols=[
            "SK_ID_CURR",
            "SK_ID_BUREAU",
            "CREDIT_ACTIVE",
            "DAYS_CREDIT",
            "CREDIT_DAY_OVERDUE",
            "AMT_CREDIT_SUM",
            "AMT_CREDIT_SUM_DEBT",
            "AMT_CREDIT_SUM_OVERDUE",
        ],
        dtype={
            "SK_ID_CURR": "int32",
            "SK_ID_BUREAU": "int32",
            "CREDIT_ACTIVE": "category",
            "DAYS_CREDIT": "float32",
            "CREDIT_DAY_OVERDUE": "float32",
            "AMT_CREDIT_SUM": "float64",
            "AMT_CREDIT_SUM_DEBT": "float64",
            "AMT_CREDIT_SUM_OVERDUE": "float64",
        },
    )
    b_agg, b_diag = aggregate_bureau(b_df, bb_df)
    del bb_df
    del b_df
    gc.collect()

    b_meta = write_parquet_atomic(
        b_agg, target_interim / "bureau_aggregated.parquet", prefix="BUREAU_"
    )
    del b_agg
    gc.collect()
    results["outputs"]["bureau"] = b_meta
    results["diagnostics"]["bureau"] = b_diag

    # 3. Previous Application
    prev_df = pd.read_csv(
        raw_paths["previous_application"],
        usecols=[
            "SK_ID_PREV",
            "SK_ID_CURR",
            "NAME_CONTRACT_STATUS",
            "AMT_APPLICATION",
            "AMT_CREDIT",
            "AMT_ANNUITY",
            "DAYS_DECISION",
        ],
        dtype={
            "SK_ID_PREV": "int32",
            "SK_ID_CURR": "int32",
            "NAME_CONTRACT_STATUS": "category",
            "AMT_APPLICATION": "float64",
            "AMT_CREDIT": "float64",
            "AMT_ANNUITY": "float64",
            "DAYS_DECISION": "float32",
        },
    )
    prev_agg, prev_diag = aggregate_previous_application(prev_df)
    del prev_df
    gc.collect()

    prev_meta = write_parquet_atomic(
        prev_agg,
        target_interim / "previous_application_aggregated.parquet",
        prefix="PREV_",
    )
    del prev_agg
    gc.collect()
    results["outputs"]["previous_application"] = prev_meta
    results["diagnostics"]["previous_application"] = prev_diag

    # 4. Installments Payments
    instal_df = pd.read_csv(
        raw_paths["installments_payments"],
        usecols=[
            "SK_ID_PREV",
            "SK_ID_CURR",
            "NUM_INSTALMENT_VERSION",
            "NUM_INSTALMENT_NUMBER",
            "DAYS_INSTALMENT",
            "DAYS_ENTRY_PAYMENT",
            "AMT_INSTALMENT",
            "AMT_PAYMENT",
        ],
        dtype={
            "SK_ID_PREV": "int32",
            "SK_ID_CURR": "int32",
            "NUM_INSTALMENT_VERSION": "float32",
            "NUM_INSTALMENT_NUMBER": "int32",
            "DAYS_INSTALMENT": "float32",
            "DAYS_ENTRY_PAYMENT": "float32",
            "AMT_INSTALMENT": "float64",
            "AMT_PAYMENT": "float64",
        },
    )
    instal_agg, instal_diag = aggregate_installments_payments(instal_df)
    del instal_df
    gc.collect()

    instal_meta = write_parquet_atomic(
        instal_agg,
        target_interim / "installments_payments_aggregated.parquet",
        prefix="INSTAL_",
    )
    del instal_agg
    gc.collect()
    results["outputs"]["installments_payments"] = instal_meta
    results["diagnostics"]["installments_payments"] = instal_diag

    # 5. POS CASH Balance
    pos_df = pd.read_csv(
        raw_paths["POS_CASH_balance"],
        usecols=[
            "SK_ID_PREV",
            "SK_ID_CURR",
            "MONTHS_BALANCE",
            "CNT_INSTALMENT_FUTURE",
            "SK_DPD",
            "SK_DPD_DEF",
        ],
        dtype={
            "SK_ID_PREV": "int32",
            "SK_ID_CURR": "int32",
            "MONTHS_BALANCE": "int16",
            "CNT_INSTALMENT_FUTURE": "float32",
            "SK_DPD": "int32",
            "SK_DPD_DEF": "int32",
        },
    )
    pos_agg, pos_diag = aggregate_pos_cash_balance(pos_df)
    del pos_df
    gc.collect()

    pos_meta = write_parquet_atomic(
        pos_agg,
        target_interim / "pos_cash_balance_aggregated.parquet",
        prefix="POS_",
    )
    del pos_agg
    gc.collect()
    results["outputs"]["pos_cash_balance"] = pos_meta
    results["diagnostics"]["pos_cash_balance"] = pos_diag

    # 6. Credit Card Balance
    cc_df = pd.read_csv(
        raw_paths["credit_card_balance"],
        usecols=[
            "SK_ID_PREV",
            "SK_ID_CURR",
            "MONTHS_BALANCE",
            "AMT_BALANCE",
            "AMT_CREDIT_LIMIT_ACTUAL",
            "SK_DPD",
            "SK_DPD_DEF",
            "AMT_PAYMENT_TOTAL_CURRENT",
        ],
        dtype={
            "SK_ID_PREV": "int32",
            "SK_ID_CURR": "int32",
            "MONTHS_BALANCE": "int16",
            "AMT_BALANCE": "float64",
            "AMT_CREDIT_LIMIT_ACTUAL": "float64",
            "SK_DPD": "int32",
            "SK_DPD_DEF": "int32",
            "AMT_PAYMENT_TOTAL_CURRENT": "float64",
        },
    )
    cc_agg, cc_diag = aggregate_credit_card_balance(cc_df)
    del cc_df
    gc.collect()

    cc_meta = write_parquet_atomic(
        cc_agg,
        target_interim / "credit_card_balance_aggregated.parquet",
        prefix="CC_",
    )
    del cc_agg
    gc.collect()
    results["outputs"]["credit_card_balance"] = cc_meta
    results["diagnostics"]["credit_card_balance"] = cc_diag

    # 7. Write Manifest
    manifest_path = target_interim / "aggregation_manifest.json"
    temp_manifest = target_interim / f"aggregation_manifest.json.tmp.{uuid.uuid4().hex}"
    with open(temp_manifest, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    os.replace(temp_manifest, manifest_path)

    results["manifest_path"] = str(manifest_path)
    return results


if __name__ == "__main__":
    summary = run_historical_aggregation()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
