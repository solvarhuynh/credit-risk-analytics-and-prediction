"""Kiểm tra hợp đồng fact Power BI cho nhóm visual TV1."""

import numpy as np
import pandas as pd
import pytest

from src.models.tv1_dashboard_data import (
    FACT_COLUMNS,
    build_tv1_evaluated_fact,
)


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    scores = pd.DataFrame({
        "loan_id": ["l-05", "l-01", "l-04", "l-02", "l-03", "l-06"],
        "target": [1, 0, 1, 0, 0, 0],
        "predicted_pd": [1.0, 0.02, 0.95, 0.05, 0.22, np.nextafter(0.05, 0.0)],
        "predicted_class": [1, 0, 1, 0, 1, 0],
        "risk_score": [100.0, 2.0, 95.0, 5.0, 22.0, np.nextafter(0.05, 0.0) * 100],
        "credit_score": [0, 980, 50, 950, 780, 995],
        "risk_tier": ["Tier D — Very High", "Tier A — Low", "Tier D — Very High",
                      "Tier A — Low", "Tier C — High", "Tier A — Low"],
        "fico_avg": [800.0, 620.0, 770.0, 675.0, 725.0, 640.0],
        "loan_amnt": [1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0],
        "annual_inc": [50000.0, 60000.0, 70000.0, 80000.0, 90000.0, 100000.0],
        "dti": [10.0, 12.0, 14.0, 16.0, 18.0, 20.0],
        "loan_to_income_ratio": [0.02, 0.03, 0.04, 0.05, 0.06, 0.07],
        "home_ownership": ["RENT", "OWN", "MORTGAGE", "RENT", "OWN", "OWN"],
        "purpose": ["other", "car", "debt_consolidation", "credit_card", "other", "other"],
    })
    el = scores[["loan_id", "target", "predicted_pd", "risk_score", "credit_score",
                 "risk_tier", "loan_amnt"]].copy()
    el["ead_proxy"] = el["loan_amnt"]
    el["expected_loss_lgd_30"] = el["predicted_pd"] * 0.30 * el["ead_proxy"]
    el["expected_loss_lgd_45"] = el["predicted_pd"] * 0.45 * el["ead_proxy"]
    el["expected_loss_lgd_60"] = el["predicted_pd"] * 0.60 * el["ead_proxy"]
    el["expected_loss"] = el["expected_loss_lgd_45"]
    el["expected_loss_rate"] = el["predicted_pd"] * 0.45
    fico = pd.DataFrame({
        "loan_id": scores["loan_id"],
        "fico_band": ["750+", "<650", None, "650-699", "700-749", "<650"],
    })
    return scores, el, fico


def test_build_tv1_fact_assigns_bins_bands_order_and_keeps_minimal_schema() -> None:
    scores, el, fico = _inputs()

    fact = build_tv1_evaluated_fact(scores, el, fico, expected_rows=6)

    assert list(fact.columns) == list(FACT_COLUMNS)
    assert fact["loan_id"].tolist() == ["l-01", "l-02", "l-03", "l-04", "l-05", "l-06"]
    assert fact["risk_tier"].tolist() == ["A", "A", "C", "D", "D", "A"]
    assert fact["tier_sort_order"].tolist() == [1, 1, 3, 4, 4, 1]
    assert fact["fico_band"].tolist() == ["<650", "650-699", "700-749", "Missing", "750+", "<650"]
    assert fact["fico_band_sort_order"].tolist() == [1, 2, 3, 5, 4, 1]
    assert fact["pd_bin_sort_order"].tolist() == [1, 2, 5, 20, 20, 1]
    assert fact["pd_bin_label"].tolist() == [
        "0.00–<0.05", "0.05–<0.10", "0.20–<0.25", "0.95–1.00 (inclusive)",
        "0.95–1.00 (inclusive)", "0.00–<0.05",
    ]
    assert fact.loc[fact["loan_id"].eq("l-06"), "pd_bin"].item() == 0.0
    assert fact["expected_loss"].equals(fact["expected_loss_lgd_45"])
    assert fact["loan_id"].notna().all() and fact["loan_id"].is_unique
    assert fact["fico_band"].notna().all() and fact["pd_bin_label"].notna().all()


def test_build_tv1_fact_is_deterministic() -> None:
    inputs = _inputs()
    first = build_tv1_evaluated_fact(*inputs, expected_rows=6)
    second = build_tv1_evaluated_fact(*inputs, expected_rows=6)

    pd.testing.assert_frame_equal(first, second, check_dtype=True)


@pytest.mark.parametrize("bad_id", [None, "l-01"])
def test_build_tv1_fact_rejects_null_or_duplicate_score_ids(bad_id) -> None:
    scores, el, fico = _inputs()
    scores.loc[0, "loan_id"] = bad_id

    with pytest.raises(ValueError, match="loan_id phải non-null và unique"):
        build_tv1_evaluated_fact(scores, el, fico, expected_rows=6)


def test_build_tv1_fact_rejects_id_mismatch_and_invalid_pd() -> None:
    scores, el, fico = _inputs()
    el.loc[0, "loan_id"] = "not-in-scores"
    with pytest.raises(ValueError, match="loan_id không khớp chính xác"):
        build_tv1_evaluated_fact(scores, el, fico, expected_rows=6)

    scores, el, fico = _inputs()
    scores.loc[0, "predicted_pd"] = np.inf
    with pytest.raises(ValueError, match="predicted_pd phải hữu hạn"):
        build_tv1_evaluated_fact(scores, el, fico, expected_rows=6)
