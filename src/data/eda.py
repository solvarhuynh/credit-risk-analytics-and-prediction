"""Các hàm EDA Lending Club; module không tự sinh biểu đồ khi import."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def numeric_distribution(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        raise ValueError(f"Thiếu cột {column}.")
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def default_rate_by(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in frame or "target" not in frame:
        raise ValueError(f"Cần {column} và target.")
    return (
        frame.dropna(subset=[column, "target"])
        .groupby(column, observed=True)["target"]
        .agg(loan_count="size", default_rate="mean")
        .reset_index()
        .sort_values("loan_count", ascending=False)
    )


def loan_trend(frame: pd.DataFrame) -> pd.DataFrame:
    issue = pd.to_datetime(frame["issue_d"], errors="coerce")
    temp = frame.assign(year_month=issue.dt.to_period("M").astype("string"))
    return temp.dropna(subset=["year_month"]).groupby("year_month").agg(
        loan_count=("loan_id", "size"), loan_amount=("loan_amnt", "sum")
    ).reset_index()


def accepted_rejected_by_state(accepted: pd.DataFrame, rejected: pd.DataFrame) -> pd.DataFrame:
    accepted_counts = accepted.groupby("state_code").size().rename("accepted_count")
    rejected_counts = rejected.groupby("state_code").size().rename("rejected_count")
    return pd.concat([accepted_counts, rejected_counts], axis=1).fillna(0).reset_index()


def plot_histogram(frame: pd.DataFrame, column: str, *, bins: int = 40) -> plt.Figure:
    """Dùng được cho loan_amnt, annual_inc, fico_avg và dti."""

    values = numeric_distribution(frame, column)
    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.hist(values, bins=bins)
    axis.set(title=f"Phân phối {column}", xlabel=column, ylabel="Số hồ sơ")
    figure.tight_layout()
    return figure


def plot_default_rate(frame: pd.DataFrame, column: str) -> plt.Figure:
    summary = default_rate_by(frame, column)
    figure, axis = plt.subplots(figsize=(9, 4.5))
    axis.bar(summary[column].astype(str), summary["default_rate"])
    axis.set(title=f"Tỷ lệ default theo {column}", ylabel="Default rate")
    axis.tick_params(axis="x", rotation=45)
    figure.tight_layout()
    return figure
