"""Tính Expected Loss theo scenario trên PD và risk tier đã khóa ở ML-LC-10."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import (
    ML_LC_07_MANIFEST_PATH,
    ML_LC_08_MANIFEST_PATH,
    ML_LC_10_MANIFEST_PATH,
    ML_LC_10_SCORED_TEST_PATH,
    ML_LC_11_EXPECTED_LOSS_PATH,
    ML_LC_11_PORTFOLIO_SUMMARY_PATH,
    ML_LC_11_RISK_TIER_SUMMARY_PATH,
    MODELING_DIR,
    REPORTS_DIR,
    XGBOOST_CANDIDATE_PATH,
)
from src.models.cost_optimization import calculate_expected_loss
from src.models.modeling_pipeline import GateError


ML_LC_11_STAGE = "ml-lc-11"
ML_LC_11_TITLE = "Expected Loss Scenario Analysis"
EXPECTED_ROWS = 269070
LOCKED_THRESHOLD = 0.22009515762329102
BASELINE_LGD = 0.45
SENSITIVITY_LGDS = (0.30, 0.45, 0.60)
TIER_ORDER = ("Tier A — Low", "Tier B — Moderate", "Tier C — High", "Tier D — Very High")
REQUIRED_SOURCE_COLUMNS = (
    "loan_id", "target", "predicted_pd", "risk_score", "credit_score",
    "risk_tier", "loan_amnt",
)
CONTEXT_COLUMNS = ("fico_avg", "dti", "annual_inc", "purpose", "issue_year")
PROTECTED_NAMES = (
    "xgboost_candidate.joblib",
    "ml_lc_07_manifest.json",
    "ml_lc_08_manifest.json",
    "ml_lc_10_manifest.json",
)


def _sha256(path: Path) -> str:
    """Tính SHA-256 theo luồng cho model/manifests đã khóa."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write(path: Path, writer: Any) -> None:
    """Ghi output qua file partial cùng thư mục rồi thay thế atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    try:
        writer(partial)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    """Ghi JSON UTF-8, không cho phép NaN/Infinity."""
    _atomic_write(path, lambda target: target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    ))


def build_expected_loss_dataset(
    scored: pd.DataFrame,
    *,
    baseline_lgd: float = BASELINE_LGD,
    expected_rows: int = EXPECTED_ROWS,
) -> pd.DataFrame:
    """Tạo EL baseline và sensitivity, không dùng target trong phép tính."""
    missing = sorted(set(REQUIRED_SOURCE_COLUMNS) - set(scored.columns))
    if missing:
        raise ValueError(f"Scored input thiếu cột bắt buộc: {missing}.")
    if len(scored) != expected_rows:
        raise ValueError(f"Source phải có đúng {expected_rows} dòng.")
    if scored["loan_id"].isna().any() or not scored["loan_id"].is_unique:
        raise ValueError("loan_id phải non-null và unique.")
    if not scored["risk_tier"].isin(TIER_ORDER).all():
        raise ValueError("risk_tier phải thuộc đủ taxonomy A–D đã khóa.")
    target = pd.to_numeric(scored["target"], errors="coerce")
    if target.isna().any() or not target.isin([0, 1]).all():
        raise ValueError("target phải nhị phân, non-null; chỉ dùng cho mô tả hồi cứu.")
    pd_values = pd.to_numeric(scored["predicted_pd"], errors="coerce")
    ead = pd.to_numeric(scored["loan_amnt"], errors="coerce")
    if (pd_values.isna().any() or not np.isfinite(pd_values).all()
            or not pd_values.between(0, 1).all()):
        raise ValueError("predicted_pd phải hữu hạn và thuộc [0, 1].")
    if (ead.isna().any() or not np.isfinite(ead).all() or (ead < 0).any()):
        raise ValueError("loan_amnt / EAD proxy phải hữu tính, hữu hạn và không âm.")
    if not 0 <= baseline_lgd <= 1:
        raise ValueError("baseline_lgd phải thuộc [0, 1].")

    columns = [*REQUIRED_SOURCE_COLUMNS, *[c for c in CONTEXT_COLUMNS if c in scored.columns]]
    output = scored[columns].copy()
    output["ead_proxy"] = ead.to_numpy(dtype=float)
    output["lgd_assumption"] = float(baseline_lgd)
    output["expected_loss"] = calculate_expected_loss(
        pd_values.reset_index(drop=True), baseline_lgd, ead.reset_index(drop=True)
    ).to_numpy(dtype=float)
    output["expected_loss_rate"] = np.divide(
        output["expected_loss"].to_numpy(dtype=float), output["ead_proxy"].to_numpy(dtype=float),
        out=np.full(len(output), np.nan, dtype=float), where=output["ead_proxy"].to_numpy(dtype=float) > 0,
    )
    for lgd in SENSITIVITY_LGDS:
        suffix = int(round(lgd * 100))
        output[f"expected_loss_lgd_{suffix}"] = calculate_expected_loss(
            pd_values.reset_index(drop=True), lgd, ead.reset_index(drop=True)
        ).to_numpy(dtype=float)
    return output


def build_el_summaries(el_data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tạo summary danh mục và tier; target chỉ dùng cho observed rate."""
    total_ead = float(el_data["ead_proxy"].sum())
    total_el = float(el_data["expected_loss"].sum())
    weighted_pd = float(np.average(el_data["predicted_pd"], weights=el_data["ead_proxy"])) if total_ead else 0.0
    portfolio = pd.DataFrame([{
        "loan_count": int(len(el_data)),
        "total_ead": total_ead,
        "total_expected_loss": total_el,
        "average_expected_loss": float(el_data["expected_loss"].mean()),
        "median_expected_loss": float(el_data["expected_loss"].median()),
        "average_expected_loss_rate": total_el / total_ead if total_ead else 0.0,
        "weighted_average_pd": weighted_pd,
        "baseline_lgd": BASELINE_LGD,
        "ead_proxy": "loan_amnt",
        "amount_unit": "loan_amnt source units; currency not specified by data dictionary",
    }])
    rows: list[dict[str, Any]] = []
    for tier in TIER_ORDER:
        group = el_data.loc[el_data["risk_tier"].eq(tier)]
        exposure = float(group["ead_proxy"].sum())
        expected = float(group["expected_loss"].sum())
        rows.append({
            "risk_tier": tier,
            "loan_count": int(len(group)),
            "share": float(len(group) / len(el_data)),
            "total_ead": exposure,
            "exposure_share": float(exposure / total_ead) if total_ead else 0.0,
            "total_expected_loss": expected,
            "share_of_expected_loss": float(expected / total_el) if total_el else 0.0,
            "mean_pd": float(group["predicted_pd"].mean()),
            "mean_expected_loss": float(group["expected_loss"].mean()),
            "observed_default_rate": float(group["target"].mean()),
        })
    tiers = pd.DataFrame(rows)
    return portfolio, tiers


def validate_reconciliation(el_data: pd.DataFrame, portfolio: pd.DataFrame, tiers: pd.DataFrame) -> None:
    """Fail closed nếu row-level formula, totals, tiers hay sensitivity không khớp."""
    expected = el_data["predicted_pd"].to_numpy() * el_data["lgd_assumption"].to_numpy() * el_data["ead_proxy"].to_numpy()
    if not np.allclose(el_data["expected_loss"], expected, rtol=1e-12, atol=1e-10):
        raise ValueError("Row-level EL không khớp PD × LGD × EAD.")
    if (el_data["expected_loss"].lt(0).any()
            or (el_data["expected_loss"] - el_data["ead_proxy"] > 1e-9).any()):
        raise ValueError("Expected Loss phải trong [0, EAD proxy].")
    if not (el_data["expected_loss_lgd_30"].le(el_data["expected_loss_lgd_45"] + 1e-10).all()
            and el_data["expected_loss_lgd_45"].le(el_data["expected_loss_lgd_60"] + 1e-10).all()):
        raise ValueError("Sensitivity EL phải không giảm khi LGD tăng.")
    if int(tiers["loan_count"].sum()) != len(el_data):
        raise ValueError("Tier counts không reconcile với source rows.")
    if not np.isclose(float(portfolio.loc[0, "total_expected_loss"]), float(el_data["expected_loss"].sum()), rtol=1e-12):
        raise ValueError("Portfolio EL không khớp tổng row-level EL.")
    if not np.isclose(float(tiers["total_expected_loss"].sum()), float(el_data["expected_loss"].sum()), rtol=1e-12):
        raise ValueError("Tier EL không reconcile với portfolio EL.")
    if not np.isclose(float(tiers["total_ead"].sum()), float(el_data["ead_proxy"].sum()), rtol=1e-12):
        raise ValueError("Tier EAD không reconcile với portfolio EAD.")


def _render_report(manifest: dict[str, Any], portfolio: pd.DataFrame, tiers: pd.DataFrame) -> str:
    """Tạo báo cáo tiếng Việt từ summary đã tính."""
    p = portfolio.iloc[0]
    rows = [
        "# ML-LC-11 — Expected Loss",
        "",
        "## 1. Expected Loss là gì?",
        "",
        "`EL = PD × LGD × EAD`: PD là xác suất vỡ nợ model dự đoán, LGD là tỷ lệ tổn thất giả định khi vỡ nợ, EAD là quy mô exposure đưa vào kịch bản.",
        "",
        "## 2. Model output và scenario assumptions",
        "",
        "- **Model output:** `predicted_pd` đã khóa từ XGBoost; không dự đoán lại.",
        "- **EAD proxy:** `loan_amnt`, số tiền gốc tại thời điểm cấp khoản vay; không phải outstanding balance thực tế.",
        "- **LGD:** baseline 45%, sensitivity 30% / 45% / 60%. Đây là assumption minh họa cho project, không phải estimate thực nghiệm hay quy định.",
        "- Dictionary không xác nhận currency unit; báo cáo giữ nguyên loan_amnt source units, không tự gắn USD.",
        "",
        "## 3. Baseline portfolio scenario",
        "",
        f"- Số khoản vay: {int(p.loan_count):,}",
        f"- Tổng EAD proxy: {p.total_ead:,.2f} loan_amnt source units",
        f"- Tổng Expected Loss: {p.total_expected_loss:,.2f} loan_amnt source units",
        f"- EL trung bình/khoản: {p.average_expected_loss:,.2f}",
        f"- Portfolio EL rate (total EL / total EAD proxy): {p.average_expected_loss_rate:.4%}",
        f"- EAD-weighted mean PD: {p.weighted_average_pd:.4%}",
        "",
        "## 4. Expected Loss theo risk tier",
        "",
        "| Tier | Loans | Loan share | Exposure share | EL share | Mean PD | Mean EL | Observed default rate* |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in tiers.itertuples(index=False):
        rows.append(f"| {row.risk_tier} | {row.loan_count:,} | {row.share:.2%} | {row.exposure_share:.2%} | {row.share_of_expected_loss:.2%} | {row.mean_pd:.2%} | {row.mean_expected_loss:,.2f} | {row.observed_default_rate:.2%} |")
    rows += [
        "",
        "*Observed default rate dùng `target` để mô tả outcome hồi cứu; target không tham gia công thức EL.*",
        "",
        "Expected Loss cao có thể đến từ PD cao, exposure cao hoặc cả hai. Tier rủi ro cao nhất không nhất thiết đóng góp phần EL lớn nhất; so sánh cả PD, exposure share và EL share.",
        "",
        "## 5. Sensitivity",
        "",
        "| LGD scenario | Total Expected Loss |",
        "|---:|---:|",
    ]
    for lgd in SENSITIVITY_LGDS:
        rows.append(f"| {lgd:.0%} | {manifest['sensitivity_totals'][f'{int(lgd * 100)}%']:,.2f} loan_amnt source units |")
    rows += [
        "",
        "PD giữ nguyên; chỉ thay LGD assumption. Đây không phải model tuning.",
        "",
        "## 6. V06 readiness",
        "",
        "Nguồn data-ready: `ml_lc_11_expected_loss.parquet` và `ml_lc_11_risk_tier_el_summary.csv`. Visual trả lời tier/segment nào đóng góp EL nhiều nhất và liệu tỷ trọng đó đi cùng PD cao, exposure lớn hay cả hai. Power BI chưa được dựng/tích hợp.",
        "",
        "## 7. Giới hạn",
        "",
        "EL là kịch bản kỳ vọng, không phải realized loss hay profit; không mang hàm ý nhân quả, không phải regulatory capital model. LGD là assumption, loan_amnt là EAD proxy, currency unit không được nêu trong data dictionary; chưa mô hình hóa recovery, thời gian hoặc outstanding balance.",
        "",
        "## 8. Next stage",
        "",
        "ML-LC-12 = NOT STARTED. Không thực hiện full-data refit trong stage này.",
        "",
    ]
    return "\n".join(rows)


def run_ml_lc_11(
    *,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
    expected_rows: int = EXPECTED_ROWS,
) -> dict[str, Any]:
    """Chạy ML-LC-11 từ artifact ML-LC-10; không load/fit model hoặc tái dự đoán."""
    output_dir, reports_dir = Path(output_dir), Path(reports_dir)
    scored_path = output_dir / ML_LC_10_SCORED_TEST_PATH.name
    manifest_path = output_dir / ML_LC_10_MANIFEST_PATH.name
    ml07_path = output_dir / ML_LC_07_MANIFEST_PATH.name
    ml08_path = output_dir / ML_LC_08_MANIFEST_PATH.name
    model_path = output_dir / XGBOOST_CANDIDATE_PATH.name
    paths = {path.name: path for path in (model_path, ml07_path, ml08_path, manifest_path)}
    if any(not path.is_file() for path in (*paths.values(), scored_path)):
        raise GateError("Thiếu model, manifest khóa hoặc scored artifact cần cho ML-LC-11.")
    before = {name: _sha256(path) for name, path in paths.items()}
    ml07 = json.loads(ml07_path.read_text(encoding="utf-8"))
    ml08 = json.loads(ml08_path.read_text(encoding="utf-8"))
    ml10 = json.loads(manifest_path.read_text(encoding="utf-8"))
    state_path = reports_dir / "tv1_stages/state/ml-lc-10.json"
    if not state_path.is_file():
        raise GateError("Thiếu ML-LC-10 PASS state marker.")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    threshold = ml07.get("selected_threshold")
    if (ml07.get("stage") != "ml-lc-07" or ml07.get("status") != "PASS"
            or ml07.get("locked_candidate") != "xgboost_candidate"
            or ml07.get("selection_partition") != "validation"
            or threshold != LOCKED_THRESHOLD):
        raise GateError("ML-LC-07 candidate/threshold lock is invalid.")
    if (ml08.get("stage") != "ml-lc-08" or ml08.get("status") != "PASS"
            or ml08.get("selected_candidate") != "xgboost_candidate"
            or ml08.get("selected_threshold") != LOCKED_THRESHOLD
            or ml08.get("test_rows") != expected_rows
            or ml08.get("test_evaluated") is not True):
        raise GateError("ML-LC-08 evaluated population lock is invalid.")
    if (ml10.get("stage") != "ml-lc-10" or ml10.get("status") != "PASS"
            or ml10.get("model") != "xgboost_candidate"
            or ml10.get("decision_threshold") != LOCKED_THRESHOLD
            or ml10.get("source_rows") != expected_rows
            or ml10.get("model_retrained") is not False
            or ml10.get("candidate_changed") is not False
            or ml10.get("threshold_changed") is not False
            or state.get("stage") != "ml-lc-10" or state.get("status") != "PASS"):
        raise GateError("ML-LC-10 score/tier handoff is not PASS or lock changed.")
    scored = pd.read_parquet(scored_path)
    if len(scored) != expected_rows:
        raise GateError(f"ML-LC-10 scored input must have {expected_rows} rows.")
    el_data = build_expected_loss_dataset(scored, expected_rows=expected_rows)
    portfolio, tiers = build_el_summaries(el_data)
    validate_reconciliation(el_data, portfolio, tiers)
    expected_totals = {
        f"{int(lgd * 100)}%": float(calculate_expected_loss(
            el_data["predicted_pd"].reset_index(drop=True), lgd,
            el_data["ead_proxy"].reset_index(drop=True),
        ).sum()) for lgd in SENSITIVITY_LGDS
    }
    protected_after_compute = {name: _sha256(path) for name, path in paths.items()}
    if protected_after_compute != before:
        raise GateError("Protected model/lock manifests changed during ML-LC-11.")

    expected_path = output_dir / ML_LC_11_EXPECTED_LOSS_PATH.name
    portfolio_path = output_dir / ML_LC_11_PORTFOLIO_SUMMARY_PATH.name
    tier_path = output_dir / ML_LC_11_RISK_TIER_SUMMARY_PATH.name
    manifest_out_path = output_dir / "ml_lc_11_manifest.json"
    report_path = reports_dir / "tv1_stages/ml-lc-11.md"
    state_out_path = reports_dir / "tv1_stages/state/ml-lc-11.json"
    _atomic_write(expected_path, lambda path: el_data.to_parquet(path, index=False))
    _atomic_write(portfolio_path, lambda path: portfolio.to_csv(path, index=False, float_format="%.12g"))
    _atomic_write(tier_path, lambda path: tiers.to_csv(path, index=False, float_format="%.12g"))

    manifest: dict[str, Any] = {
        "stage": ML_LC_11_STAGE, "status": "PASS",
        "source_artifact": str(scored_path), "source_rows": len(scored),
        "pd_source": "locked xgboost predictions; predicted_pd from ML-LC-10",
        "expected_loss_formula": "predicted_pd * lgd_assumption * ead_proxy",
        "ead_policy": "application/origination principal amount proxy; not observed outstanding EAD",
        "ead_proxy_field": "loan_amnt",
        "amount_unit": "loan_amnt source units; currency not specified by data dictionary",
        "lgd_policy": "illustrative/project assumption for scenario analysis; not empirically estimated, regulatory, or bank policy",
        "baseline_lgd": BASELINE_LGD, "sensitivity_lgd_values": list(SENSITIVITY_LGDS),
        "sensitivity_totals": expected_totals,
        "portfolio_summary": str(portfolio_path), "portfolio_summary_path": str(portfolio_path),
        "risk_tier_summary_path": str(tier_path), "expected_loss_artifact_path": str(expected_path),
        "portfolio_total_ead": float(portfolio.loc[0, "total_ead"]),
        "portfolio_total_expected_loss": float(portfolio.loc[0, "total_expected_loss"]),
        "average_expected_loss": float(portfolio.loc[0, "average_expected_loss"]),
        "average_expected_loss_rate": float(portfolio.loc[0, "average_expected_loss_rate"]),
        "risk_tier_summary": tiers.to_dict("records"),
        "dashboard_readiness": {"V06": True},
        "target_used_in_el_formula": False,
        "target_use": "descriptive retrospective observed_default_rate only",
        "model_retrained": False, "candidate_changed": False, "threshold_changed": False,
        "decision_threshold": LOCKED_THRESHOLD, "business_cost_optimized": False,
        "model_fit_called": False, "predict_proba_called": False,
        "protected_sha256_before": before,
        "next_stage": "ml-lc-12",
    }
    _write_json(manifest_out_path, manifest)
    _atomic_write(report_path, lambda path: path.write_text(
        _render_report(manifest, portfolio, tiers), encoding="utf-8"
    ))
    marker = {
        "stage": ML_LC_11_STAGE, "title": ML_LC_11_TITLE, "status": "PASS",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_out_path), "report_path": str(report_path),
        "expected_loss_artifact_path": str(expected_path),
        "portfolio_summary_path": str(portfolio_path), "risk_tier_summary_path": str(tier_path),
    }
    _write_json(state_out_path, marker)
    after = {name: _sha256(path) for name, path in paths.items()}
    if after != before:
        raise GateError("Protected model/lock hashes changed while writing ML-LC-11 outputs.")
    manifest["protected_sha256_after"] = after
    _write_json(manifest_out_path, manifest)
    return manifest
