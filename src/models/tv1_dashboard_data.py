"""Chuẩn bị fact Power BI tối thiểu cho các visual TV1 V02–V06."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from src.config import (
    CANONICAL_DATASET_PATH,
    ML_LC_10_MANIFEST_PATH,
    ML_LC_10_SCORED_TEST_PATH,
    ML_LC_11_EXPECTED_LOSS_PATH,
    ML_LC_11_MANIFEST_PATH,
    PROCESSED_DIR,
)

EXPECTED_ROWS: Final = 269_070
EXPECTED_THRESHOLD: Final = 0.22009515762329102
EXPECTED_TIER_COUNTS: Final = {"A": 66_275, "B": 109_146, "C": 80_423, "D": 13_226}
EXPECTED_BASELINE_EL: Final = 372_579_342.1934409
PD_BIN_WIDTH: Final = 0.05
RISK_TIER_LABELS: Final = {
    "Tier A — Low": ("A", "Tier A — Low", 1),
    "Tier B — Moderate": ("B", "Tier B — Moderate", 2),
    "Tier C — High": ("C", "Tier C — High", 3),
    "Tier D — Very High": ("D", "Tier D — Very High", 4),
}
FICO_BAND_ORDER: Final = {"<650": 1, "650-699": 2, "700-749": 3, "750+": 4, "Missing": 5}
SCORE_COLUMNS: Final = (
    "loan_id", "target", "predicted_pd", "predicted_class", "risk_score", "credit_score",
    "risk_tier", "fico_avg", "loan_amnt", "annual_inc", "dti", "loan_to_income_ratio",
    "home_ownership", "purpose",
)
EL_COLUMNS: Final = (
    "loan_id", "target", "predicted_pd", "risk_score", "credit_score", "risk_tier",
    "loan_amnt", "ead_proxy", "expected_loss", "expected_loss_rate",
    "expected_loss_lgd_30", "expected_loss_lgd_45", "expected_loss_lgd_60",
)
FACT_COLUMNS: Final = (
    "loan_id", "target", "predicted_pd", "predicted_class", "risk_score", "credit_score",
    "risk_tier", "risk_tier_label", "tier_sort_order", "fico_avg", "fico_band",
    "fico_band_sort_order", "loan_amnt", "annual_inc", "dti", "loan_to_income_ratio",
    "home_ownership", "purpose", "ead_proxy", "expected_loss", "expected_loss_rate",
    "expected_loss_lgd_30", "expected_loss_lgd_45", "expected_loss_lgd_60",
    "pd_bin", "pd_bin_label", "pd_bin_sort_order",
)


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{name}: thiếu cột bắt buộc {missing}.")


def _require_unique_ids(frame: pd.DataFrame, name: str) -> None:
    if frame["loan_id"].isna().any() or frame["loan_id"].duplicated().any():
        raise ValueError(f"{name}: loan_id phải non-null và unique.")


def _require_same_ids(left: pd.DataFrame, right: pd.DataFrame, right_name: str) -> None:
    if len(left) != len(right) or set(left["loan_id"]) != set(right["loan_id"]):
        raise ValueError(f"{right_name}: loan_id không khớp chính xác với frozen-test scores.")


def _require_matching_values(
    scores: pd.DataFrame, expected_loss: pd.DataFrame, columns: tuple[str, ...]
) -> None:
    aligned = scores[["loan_id", *columns]].merge(
        expected_loss[["loan_id", *columns]],
        on="loan_id",
        how="left",
        suffixes=("_score", "_el"),
        validate="one_to_one",
        indicator=True,
    )
    if not aligned["_merge"].eq("both").all():
        raise ValueError("ML-LC-10 và ML-LC-11 bị thiếu loan_id sau khi căn chỉnh.")
    for column in columns:
        left = aligned[f"{column}_score"]
        right = aligned[f"{column}_el"]
        if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
            equal = np.isclose(left, right, rtol=0, atol=0, equal_nan=True)
        else:
            equal = left.eq(right) | (left.isna() & right.isna())
        if not bool(np.asarray(equal).all()):
            raise ValueError(f"ML-LC-10 và ML-LC-11 không khớp trường {column}.")


def _pd_bins(values: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Tạo 20 bin xác suất cố định rộng 0.05; bin cuối bao gồm PD=1."""
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.isna().any() or not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("predicted_pd phải hữu hạn và không thiếu để gán PD bin.")
    if not numeric.between(0, 1).all():
        raise ValueError("predicted_pd phải thuộc [0, 1].")
    upper_edges = np.arange(1, 21, dtype="float64") / 20.0
    order = np.minimum(np.searchsorted(upper_edges, numeric.to_numpy(), side="right") + 1, 20)
    labels = [f"{i / 20:.2f}–<{(i + 1) / 20:.2f}" for i in range(19)]
    labels.append("0.95–1.00 (inclusive)")
    label_by_order = dict(enumerate(labels, start=1))
    return (
        pd.Series((order - 1) * PD_BIN_WIDTH, index=values.index, dtype="float64"),
        pd.Series([label_by_order[item] for item in order], index=values.index, dtype="string"),
        pd.Series(order, index=values.index, dtype="int64"),
    )


def build_tv1_evaluated_fact(
    scores: pd.DataFrame,
    expected_loss: pd.DataFrame,
    canonical_fico: pd.DataFrame,
    *,
    expected_rows: int = EXPECTED_ROWS,
) -> pd.DataFrame:
    """Ghép scores/EL/context 1:1 và thêm cột sắp xếp/bin phục vụ V02–V06."""
    _require_columns(scores, SCORE_COLUMNS, "ML-LC-10 scores")
    _require_columns(expected_loss, EL_COLUMNS, "ML-LC-11 Expected Loss")
    _require_columns(canonical_fico, ("loan_id", "fico_band"), "canonical FICO context")
    if len(scores) != expected_rows or len(expected_loss) != expected_rows:
        raise ValueError(f"Scores và Expected Loss phải có {expected_rows} dòng.")
    for frame, name in (
        (scores, "ML-LC-10 scores"),
        (expected_loss, "ML-LC-11 Expected Loss"),
        (canonical_fico, "canonical FICO context"),
    ):
        _require_unique_ids(frame, name)
    _require_same_ids(scores, expected_loss, "ML-LC-11 Expected Loss")
    if not set(scores["loan_id"]).issubset(set(canonical_fico["loan_id"])):
        raise ValueError("canonical FICO context thiếu loan_id thuộc frozen-test scores.")
    score_target = pd.to_numeric(scores["target"], errors="coerce")
    score_pd = pd.to_numeric(scores["predicted_pd"], errors="coerce")
    if score_target.isna().any() or not score_target.isin([0, 1]).all():
        raise ValueError("target phải non-null và chỉ thuộc {0,1}.")
    if score_pd.isna().any() or not np.isfinite(score_pd).all() or not score_pd.between(0, 1).all():
        raise ValueError("predicted_pd phải hữu hạn và thuộc [0,1].")

    aligned_el = expected_loss.loc[:, EL_COLUMNS]
    _require_matching_values(
        scores,
        aligned_el,
        ("target", "predicted_pd", "risk_score", "credit_score", "risk_tier", "loan_amnt"),
    )

    fact = scores.loc[:, SCORE_COLUMNS].merge(
        aligned_el.loc[:, [
            "loan_id", "ead_proxy", "expected_loss", "expected_loss_rate",
            "expected_loss_lgd_30", "expected_loss_lgd_45", "expected_loss_lgd_60",
        ]],
        on="loan_id",
        how="left",
        validate="one_to_one",
    ).merge(
        canonical_fico.loc[:, ["loan_id", "fico_band"]],
        on="loan_id",
        how="left",
        validate="one_to_one",
        indicator="_fico_merge",
    )
    if len(fact) != expected_rows or not fact["_fico_merge"].eq("both").all():
        raise ValueError("Join phải giữ nguyên frozen-test rows và ghép đủ canonical FICO band.")
    fact = fact.drop(columns="_fico_merge")

    if not fact["target"].isin([0, 1]).all() or fact["target"].isna().any():
        raise ValueError("target phải non-null và chỉ thuộc {0,1}.")
    pd_values = pd.to_numeric(fact["predicted_pd"], errors="coerce")
    if pd_values.isna().any() or not np.isfinite(pd_values).all() or not pd_values.between(0, 1).all():
        raise ValueError("predicted_pd phải hữu hạn và thuộc [0,1].")
    if fact["risk_tier"].isna().any() or not fact["risk_tier"].isin(RISK_TIER_LABELS).all():
        raise ValueError("risk_tier không thuộc taxonomy ML-LC-10 A–D.")
    if fact["predicted_class"].isna().any() or not fact["predicted_class"].isin([0, 1]).all():
        raise ValueError("predicted_class phải non-null và nhị phân.")
    finite_columns = (
        "risk_score", "credit_score", "loan_amnt", "ead_proxy", "expected_loss",
        "expected_loss_rate", "expected_loss_lgd_30", "expected_loss_lgd_45",
        "expected_loss_lgd_60",
    )
    for column in finite_columns:
        values = pd.to_numeric(fact[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values).all():
            raise ValueError(f"{column} phải hữu hạn và non-null.")

    tier_parts = fact["risk_tier"].map(RISK_TIER_LABELS)
    fact["risk_tier"] = tier_parts.map(lambda item: item[0]).astype("string")
    fact["risk_tier_label"] = tier_parts.map(lambda item: item[1]).astype("string")
    fact["tier_sort_order"] = tier_parts.map(lambda item: item[2]).astype("int8")

    fact["fico_band"] = fact["fico_band"].astype("string").fillna("Missing")
    unknown_bands = sorted(set(fact["fico_band"]) - set(FICO_BAND_ORDER))
    if unknown_bands:
        raise ValueError(f"Canonical fico_band có nhãn ngoài policy: {unknown_bands}.")
    fact["fico_band_sort_order"] = fact["fico_band"].map(FICO_BAND_ORDER).astype("int8")

    fact["pd_bin"], fact["pd_bin_label"], fact["pd_bin_sort_order"] = _pd_bins(pd_values)
    if fact["expected_loss_lgd_45"].isna().any() or not np.isfinite(fact["expected_loss_lgd_45"]).all():
        raise ValueError("EL 45% phải hữu hạn và non-null.")
    if not np.allclose(fact["expected_loss"], fact["expected_loss_lgd_45"], rtol=0, atol=0):
        raise ValueError("expected_loss phải giữ đúng baseline scenario LGD=45%.")
    if not np.allclose(fact["ead_proxy"], fact["loan_amnt"], rtol=0, atol=0, equal_nan=True):
        raise ValueError("ead_proxy không khớp loan_amnt theo ML-LC-11.")

    fact = fact.sort_values("loan_id", kind="mergesort").reset_index(drop=True)
    fact = fact.loc[:, FACT_COLUMNS]
    if fact["loan_id"].isna().any() or not fact["loan_id"].is_unique:
        raise ValueError("Output loan_id phải non-null và unique.")
    if fact["pd_bin"].isna().any() or fact["pd_bin_label"].isna().any():
        raise ValueError("PD bin phải bao phủ toàn bộ score.")
    if fact["fico_band"].isna().any() or fact["fico_band_sort_order"].isna().any():
        raise ValueError("FICO band phải exhaustive; missing dùng category Missing.")
    return fact


def validate_tv1_dashboard_controls(fact: pd.DataFrame) -> None:
    """Đối chiếu hàng, tier và baseline EL với các control totals đã khóa."""
    if len(fact) != EXPECTED_ROWS:
        raise ValueError(f"Fact phải có đúng {EXPECTED_ROWS} dòng.")
    counts = fact["risk_tier"].value_counts().reindex(("A", "B", "C", "D"), fill_value=0).to_dict()
    if counts != EXPECTED_TIER_COUNTS:
        raise ValueError(f"Risk-tier counts lệch ML-LC-10: {counts}.")
    total_el = float(fact["expected_loss"].sum())
    if not np.isclose(total_el, EXPECTED_BASELINE_EL, rtol=1e-12, atol=1e-6):
        raise ValueError(f"Tổng EL baseline lệch ML-LC-11: {total_el}.")


def _atomic_write_parquet(frame: pd.DataFrame, path: Path) -> None:
    """Ghi parquet tạm, đọc kiểm tra rồi promote atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    try:
        frame.to_parquet(partial, index=False)
        reread = pd.read_parquet(partial)
        pd.testing.assert_frame_equal(frame, reread, check_dtype=True)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def run_tv1_dashboard_data_export(
    *,
    scores_path: Path = ML_LC_10_SCORED_TEST_PATH,
    expected_loss_path: Path = ML_LC_11_EXPECTED_LOSS_PATH,
    canonical_path: Path = CANONICAL_DATASET_PATH,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Tạo fact TV1 từ artifacts PASS; không nạp full canonical columns hay chạy model."""
    import json

    scores_path, expected_loss_path, canonical_path = map(
        Path, (scores_path, expected_loss_path, canonical_path)
    )
    destination = Path(output_path) if output_path else PROCESSED_DIR / "dashboard/fact_evaluated_loan.parquet"
    for path in (scores_path, expected_loss_path, canonical_path):
        if not path.is_file():
            raise FileNotFoundError(f"Thiếu input bắt buộc: {path}")
    score_manifest_path = scores_path.with_name(ML_LC_10_MANIFEST_PATH.name)
    el_manifest_path = expected_loss_path.with_name(ML_LC_11_MANIFEST_PATH.name)
    for path, expected_stage in ((score_manifest_path, "ml-lc-10"), (el_manifest_path, "ml-lc-11")):
        if not path.is_file():
            raise FileNotFoundError(f"Thiếu stage manifest: {path}")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("stage") != expected_stage or manifest.get("status") != "PASS":
            raise ValueError(f"Manifest {path.name} không xác nhận {expected_stage} PASS.")
    score_manifest = json.loads(score_manifest_path.read_text(encoding="utf-8"))
    if score_manifest.get("decision_threshold") != EXPECTED_THRESHOLD:
        raise ValueError("ML-LC-10 threshold không khớp operating threshold đã khóa.")

    scores = pd.read_parquet(scores_path, columns=list(SCORE_COLUMNS))
    expected_class = (pd.to_numeric(scores["predicted_pd"], errors="coerce") >= EXPECTED_THRESHOLD).astype("int64")
    if not np.array_equal(pd.to_numeric(scores["predicted_class"], errors="coerce"), expected_class):
        raise ValueError("predicted_class không khớp threshold đã khóa ở ML-LC-10.")
    expected_loss = pd.read_parquet(expected_loss_path, columns=list(EL_COLUMNS))
    canonical_fico = pd.read_parquet(canonical_path, columns=["loan_id", "fico_band"])
    fact = build_tv1_evaluated_fact(scores, expected_loss, canonical_fico)
    validate_tv1_dashboard_controls(fact)
    _atomic_write_parquet(fact, destination)
    return fact


def main() -> None:
    """CLI tạo fact TV1 để nạp vào Power BI."""
    fact = run_tv1_dashboard_data_export()
    output_path = PROCESSED_DIR / "dashboard/fact_evaluated_loan.parquet"
    print(f"PASS: {output_path} rows={len(fact)} columns={len(fact.columns)}")


if __name__ == "__main__":
    main()
