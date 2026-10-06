"""Các utility quy đổi Probability of Default (PD) thành credit score/tier.

Các tham số PDO, base odds, score boundary và tier boundary đều là cấu hình do
caller cung cấp; module không khẳng định đây là business policy cuối cùng.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from numbers import Real
import os
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from src.config import (
    CANONICAL_DATASET_PATH,
    DATA_DICTIONARY_PATH,
    ML_LC_07_MANIFEST_PATH,
    ML_LC_08_MANIFEST_PATH,
    ML_LC_08_PREDICTIONS_PATH,
    ML_LC_09_MANIFEST_PATH,
    ML_LC_10_MANIFEST_PATH,
    ML_LC_10_RISK_TIER_SUMMARY_PATH,
    ML_LC_10_SCORE_SUMMARY_PATH,
    ML_LC_10_SCORED_TEST_PATH,
    MODELING_DIR,
    REPORTS_DIR,
)
from src.models.modeling_pipeline import GateError


ML_LC_10_STAGE = "ml-lc-10"
ML_LC_10_TITLE = "PD scoring and risk tier"
ML_LC_10_LOCKED_MODEL = "xgboost_candidate"
ML_LC_10_LOCKED_THRESHOLD = 0.22009515762329102
ML_LC_10_EXPECTED_ROWS = 269070
ML_LC_10_MODEL_VERSION = "xgboost_candidate_ml-lc-10"
ML_LC_10_TIER_LABELS = (
    "Tier A — Low",
    "Tier B — Moderate",
    "Tier C — High",
    "Tier D — Very High",
)
ML_LC_10_CONTEXT_COLUMNS = (
    "fico_avg",
    "dti",
    "loan_amnt",
    "annual_inc",
    "loan_to_income_ratio",
    "purpose",
    "home_ownership",
    "term_months",
    "issue_year",
)


@dataclass(frozen=True)
class CreditScoreConfig:
    """Cấu hình PDO scheme với odds được định nghĩa là bad-to-good odds.

    Với ``odds = PD / (1 - PD)``, PD cao hơn nghĩa là rủi ro cao hơn. Công thức
    trong module đảm bảo odds tăng gấp đôi thì score giảm ``pdo`` điểm, nên PD
    cao hơn luôn dẫn đến score thấp hơn (trước và sau khi áp dụng boundary).
    """

    base_score: float
    base_odds: float
    pdo: float
    min_score: float | None = None
    max_score: float | None = None
    epsilon: float = 1e-6


def validate_probability_of_default(
    probabilities: Sequence[float] | np.ndarray,
) -> np.ndarray:
    """Kiểm tra PD hữu hạn nằm trong đoạn đóng [0, 1]."""
    try:
        values = np.atleast_1d(np.asarray(probabilities, dtype=float))
    except (TypeError, ValueError) as exc:
        raise ValueError("PD phải là giá trị số trong [0, 1].") from exc
    if values.ndim != 1 or values.size == 0:
        raise ValueError("PD phải là vector một chiều không rỗng.")
    if not np.isfinite(values).all() or not np.all((values >= 0) & (values <= 1)):
        raise ValueError("PD phải là giá trị hữu hạn trong [0, 1].")
    return values


def probability_to_log_odds(
    probabilities: Sequence[float] | np.ndarray,
    *,
    epsilon: float = 1e-6,
) -> np.ndarray:
    """Đổi PD thành log bad-to-good odds với epsilon clipping an toàn.

    PD 0 và 1 được clip vào ``[epsilon, 1 - epsilon]`` trước khi lấy log để
    không sinh ``inf`` hoặc ``nan``.
    """
    values = validate_probability_of_default(probabilities)
    validated_epsilon = _validate_epsilon(epsilon)
    clipped = np.clip(values, validated_epsilon, 1 - validated_epsilon)
    return np.log(clipped / (1 - clipped))


def log_odds_to_probability(log_odds: Sequence[float] | np.ndarray) -> np.ndarray:
    """Đổi log bad-to-good odds hữu hạn về PD bằng sigmoid ổn định số học."""
    values = _validate_finite_vector(log_odds, value_name="log_odds")
    positive = values >= 0
    probabilities = np.empty_like(values, dtype=float)
    probabilities[positive] = 1 / (1 + np.exp(-values[positive]))
    exp_values = np.exp(values[~positive])
    probabilities[~positive] = exp_values / (1 + exp_values)
    return probabilities


def probability_to_credit_score(
    probabilities: Sequence[float] | np.ndarray,
    *,
    config: CreditScoreConfig,
) -> np.ndarray:
    """Quy đổi PD thành credit score theo PDO scheme và boundary cấu hình.

    Đây không phải final business policy. Caller phải ghi công thức, giả định,
    epsilon và score boundary vào model card trước khi xuất CREDIT_SCORE.
    """
    return log_odds_to_credit_score(
        probability_to_log_odds(probabilities, epsilon=config.epsilon),
        config=config,
    )


def log_odds_to_credit_score(
    log_odds: Sequence[float] | np.ndarray,
    *,
    config: CreditScoreConfig,
) -> np.ndarray:
    """Áp dụng score = base_score - PDO/log(2) * log(odds/base_odds).

    ``log_odds`` phải dùng định nghĩa bad-to-good odds. Do ``pdo`` bắt buộc
    dương, log odds/PD tăng sẽ làm score giảm; score không thể bị đảo chiều.
    """
    _validate_score_config(config)
    values = _validate_finite_vector(log_odds, value_name="log_odds")
    factor = config.pdo / np.log(2)
    scores = config.base_score - factor * (values - np.log(config.base_odds))
    if config.min_score is not None:
        scores = np.maximum(scores, config.min_score)
    if config.max_score is not None:
        scores = np.minimum(scores, config.max_score)
    if not np.isfinite(scores).all():
        raise RuntimeError("Credit score phải hữu hạn sau khi áp dụng cấu hình.")
    return scores


def assign_risk_tier(
    scores: Sequence[float] | np.ndarray,
    *,
    score_thresholds: Sequence[float],
    tier_labels: Sequence[str],
) -> np.ndarray:
    """Gán tier từ score theo threshold/label do caller cấu hình.

    Threshold phải tăng dần và có đúng ``len(tier_labels) - 1`` phần tử. Labels
    tương ứng với score tăng dần; ví dụ generic ``HIGH, MEDIUM, LOW`` khi score
    cao hơn có nghĩa là rủi ro thấp hơn. Boundary bằng threshold thuộc tier thấp
    hơn theo thứ tự score, nhờ ``searchsorted(..., side='left')``.
    """
    score_values = _validate_finite_vector(scores, value_name="scores")
    thresholds = _validate_tier_config(score_thresholds, tier_labels)
    indexes = np.searchsorted(thresholds, score_values, side="left")
    return np.asarray(tier_labels, dtype=object)[indexes]


def _validate_score_config(config: CreditScoreConfig) -> None:
    """Kiểm tra cấu hình PDO và boundary trước khi tính score."""
    if not isinstance(config, CreditScoreConfig):
        raise ValueError("config phải là CreditScoreConfig.")
    for value, name in (
        (config.base_score, "base_score"),
        (config.base_odds, "base_odds"),
        (config.pdo, "pdo"),
    ):
        if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(value):
            raise ValueError(f"{name} phải là số hữu hạn.")
    if config.base_odds <= 0:
        raise ValueError("base_odds phải dương theo định nghĩa bad-to-good odds.")
    if config.pdo <= 0:
        raise ValueError("pdo phải dương để PD cao hơn luôn cho score thấp hơn.")
    _validate_epsilon(config.epsilon)

    for value, name in ((config.min_score, "min_score"), (config.max_score, "max_score")):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(value)
        ):
            raise ValueError(f"{name} phải là số hữu hạn hoặc None.")
    if config.min_score is not None and config.max_score is not None:
        if config.min_score > config.max_score:
            raise ValueError("min_score không được lớn hơn max_score.")


def _validate_epsilon(epsilon: float) -> float:
    """Kiểm tra epsilon clipping nằm trong (0, 0.5)."""
    if isinstance(epsilon, bool) or not isinstance(epsilon, Real):
        raise ValueError("epsilon phải là số trong khoảng (0, 0.5).")
    if not 0 < epsilon < 0.5:
        raise ValueError("epsilon phải nằm trong khoảng (0, 0.5).")
    return float(epsilon)


def _validate_finite_vector(
    values: Sequence[float] | np.ndarray,
    *,
    value_name: str,
) -> np.ndarray:
    """Chuẩn hóa một vector số hữu hạn."""
    try:
        vector = np.atleast_1d(np.asarray(values, dtype=float))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{value_name} phải là vector số hữu hạn.") from exc
    if vector.ndim != 1 or vector.size == 0 or not np.isfinite(vector).all():
        raise ValueError(f"{value_name} phải là vector số hữu hạn không rỗng.")
    return vector


def _validate_tier_config(
    score_thresholds: Sequence[float],
    tier_labels: Sequence[str],
) -> np.ndarray:
    """Kiểm tra threshold monotonic và labels tier rõ ràng."""
    thresholds = _validate_finite_vector(
        score_thresholds,
        value_name="score_thresholds",
    )
    labels = tuple(tier_labels)
    if len(labels) != len(thresholds) + 1:
        raise ValueError("tier_labels phải nhiều hơn score_thresholds đúng một phần tử.")
    if any(not isinstance(label, str) or not label.strip() for label in labels):
        raise ValueError("Mỗi tier label phải là chuỗi không rỗng.")
    if len(set(labels)) != len(labels):
        raise ValueError("tier_labels không được trùng nhau.")
    if not np.all(np.diff(thresholds) > 0):
        raise ValueError("score_thresholds phải tăng dần nghiêm ngặt.")
    return thresholds


def probability_to_risk_score(
    probabilities: Sequence[float] | np.ndarray,
) -> np.ndarray:
    """Tạo project risk score tuyến tính trong [0, 100], cao là rủi ro cao."""
    return 100.0 * validate_probability_of_default(probabilities)


def probability_to_project_credit_score(
    probabilities: Sequence[float] | np.ndarray,
) -> np.ndarray:
    """Tạo project/model credit score 0–1000; đây không phải FICO."""
    values = validate_probability_of_default(probabilities)
    return np.rint(1000.0 * (1.0 - values)).astype(np.int64)


def risk_tier_boundaries(threshold: float) -> dict[str, float]:
    """Tính biên bốn risk tier theo operating threshold đã khóa."""
    if isinstance(threshold, bool) or not isinstance(threshold, Real):
        raise ValueError("decision_threshold phải là số hữu hạn trong (0, 1].")
    value = float(threshold)
    if not np.isfinite(value) or not 0 < value <= 1:
        raise ValueError("decision_threshold phải là số hữu hạn trong (0, 1].")
    first = value * 0.5
    second = value
    third = min(2.0 * value, 1.0)
    return {
        "tier_a_upper_exclusive": first,
        "tier_b_lower_inclusive": first,
        "tier_b_upper_exclusive": second,
        "tier_c_lower_inclusive": second,
        "tier_c_upper_exclusive": third,
        "tier_d_lower_inclusive": third,
        "pd_upper_inclusive": 1.0,
    }


def assign_pd_risk_tier(
    probabilities: Sequence[float] | np.ndarray,
    *,
    decision_threshold: float,
) -> np.ndarray:
    """Gán đúng một tier, với mỗi equality thuộc tier bắt đầu tại biên đó."""
    values = validate_probability_of_default(probabilities)
    boundaries = risk_tier_boundaries(decision_threshold)
    first = boundaries["tier_a_upper_exclusive"]
    second = boundaries["tier_b_upper_exclusive"]
    third = boundaries["tier_c_upper_exclusive"]
    tiers = np.select(
        [values < first, values < second, values < third],
        ML_LC_10_TIER_LABELS[:3],
        default=ML_LC_10_TIER_LABELS[3],
    )
    if tiers.shape != values.shape or pd.isna(tiers).any():
        raise RuntimeError("Mỗi PD phải được gán đúng một risk tier.")
    return tiers.astype(object)


def validate_score_monotonicity(
    probabilities: Sequence[float] | np.ndarray,
) -> None:
    """Đảm bảo PD tăng không làm risk score giảm hoặc credit score tăng."""
    values = np.sort(validate_probability_of_default(probabilities))
    risk_scores = probability_to_risk_score(values)
    credit_scores = probability_to_project_credit_score(values)
    if np.any(np.diff(risk_scores) < 0) or np.any(np.diff(credit_scores) > 0):
        raise GateError("Mapping PD→score không đơn điệu theo contract ML-LC-10.")


def build_ml_lc_10_scored_dataset(
    predictions: pd.DataFrame,
    context: pd.DataFrame,
    *,
    decision_threshold: float,
    model_version: str = ML_LC_10_MODEL_VERSION,
) -> pd.DataFrame:
    """Nối context đã chọn và biến đổi PD mà vẫn giữ loan rows theo nguồn."""
    required = ["loan_id", "target", "predicted_pd", "predicted_class"]
    if not set(required).issubset(predictions.columns):
        raise GateError("ML-LC-08 predictions thiếu cột bắt buộc.")
    source = predictions.copy()
    if (source["loan_id"].isna().any() or not source["loan_id"].is_unique
            or source["target"].isna().any()
            or not source["target"].isin([0, 1]).all()):
        raise GateError("loan_id phải unique/non-null và target phải binary.")
    probabilities = validate_probability_of_default(source["predicted_pd"].to_numpy())
    if (source["predicted_class"].isna().any()
            or not source["predicted_class"].isin([0, 1]).all()):
        raise GateError("predicted_class phải binary và không null.")
    expected_class = (probabilities >= decision_threshold).astype(np.int8)
    if not np.array_equal(source["predicted_class"].to_numpy(dtype=np.int8), expected_class):
        raise GateError("predicted_class không khớp locked decision threshold.")

    if ("loan_id" not in context.columns or context["loan_id"].isna().any()
            or not context["loan_id"].is_unique):
        raise GateError("Dashboard context phải có loan_id unique/non-null.")
    if {"target", "predicted_pd", "predicted_class", "risk_tier"}.intersection(context.columns):
        raise GateError("Dashboard context không được ghi đè outcome hoặc scoring fields.")
    if not set(source["loan_id"]).issubset(set(context["loan_id"])):
        raise GateError("Dashboard context thiếu loan_id từ source predictions.")

    source_rows = len(source)
    scored = source.merge(
        context,
        how="left",
        on="loan_id",
        validate="one_to_one",
        sort=False,
        indicator=True,
    )
    if (len(scored) != source_rows or not scored["_merge"].eq("both").all()
            or not scored["loan_id"].is_unique
            or scored["loan_id"].tolist() != source["loan_id"].tolist()):
        raise GateError("Join dashboard context làm mất/thêm/đổi thứ tự loan rows.")
    scored.drop(columns="_merge", inplace=True)
    scored["decision_threshold"] = float(decision_threshold)
    scored["risk_score"] = probability_to_risk_score(probabilities)
    scored["credit_score"] = probability_to_project_credit_score(probabilities)
    scored["risk_tier"] = assign_pd_risk_tier(
        probabilities, decision_threshold=decision_threshold,
    )
    scored["model_version"] = model_version
    validate_score_monotonicity(probabilities)
    if (not scored["risk_score"].between(0, 100).all()
            or not scored["credit_score"].between(0, 1000).all()
            or scored["risk_tier"].isna().any()
            or scored["risk_tier"].nunique() > len(ML_LC_10_TIER_LABELS)):
        raise GateError("Scored output vượt range hoặc có risk tier không hợp lệ.")
    return scored


def build_risk_tier_summary(scored: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp predicted PD và observed outcome riêng theo risk tier."""
    grouped = scored.groupby("risk_tier", sort=False, observed=False).agg(
        loan_count=("loan_id", "size"),
        min_pd=("predicted_pd", "min"),
        max_pd=("predicted_pd", "max"),
        mean_predicted_pd=("predicted_pd", "mean"),
        median_predicted_pd=("predicted_pd", "median"),
        observed_default_count=("target", "sum"),
    )
    grouped = grouped.reindex(ML_LC_10_TIER_LABELS)
    grouped["loan_count"] = grouped["loan_count"].fillna(0).astype("int64")
    grouped["observed_default_count"] = (
        grouped["observed_default_count"].fillna(0).astype("int64")
    )
    total = int(grouped["loan_count"].sum())
    if total < 1:
        raise GateError("Risk tier summary không thể tổng hợp population rỗng.")
    grouped["share"] = grouped["loan_count"] / total
    grouped["observed_default_rate"] = np.where(
        grouped["loan_count"] > 0,
        grouped["observed_default_count"] / grouped["loan_count"].replace(0, np.nan),
        np.nan,
    )
    grouped.index.name = "risk_tier"
    result = grouped.reset_index()
    if int(result["loan_count"].sum()) != len(scored) or not np.isclose(result["share"].sum(), 1):
        raise GateError("Risk tier summary không reconcile với scored source rows.")
    return result


def build_score_summary(scored: pd.DataFrame) -> pd.DataFrame:
    """Tính các thống kê phân vị cho PD và hai project score."""
    rows: list[dict[str, float | int | str]] = []
    for column in ("predicted_pd", "risk_score", "credit_score"):
        values = scored[column].to_numpy(dtype=float)
        rows.append({
            "variable": column,
            "count": int(values.size),
            "mean": float(np.mean(values)),
            "std": float(np.std(values, ddof=1)) if values.size > 1 else 0.0,
            "min": float(np.min(values)),
            "p10": float(np.quantile(values, 0.10)),
            "p25": float(np.quantile(values, 0.25)),
            "median": float(np.quantile(values, 0.50)),
            "p75": float(np.quantile(values, 0.75)),
            "p90": float(np.quantile(values, 0.90)),
            "max": float(np.max(values)),
        })
    return pd.DataFrame(rows)


def _read_stage_json(path: Path) -> dict:
    """Đọc manifest/state cần thiết và fail closed khi thiếu hoặc JSON lỗi."""
    if not path.is_file():
        raise GateError(f"Thiếu ML-LC prerequisite: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GateError(f"Không đọc được prerequisite JSON: {path}") from exc
    if not isinstance(value, dict):
        raise GateError(f"Prerequisite JSON phải là object: {path}")
    return value


def _file_sha256(path: Path) -> str:
    """Tính SHA-256 theo luồng để không nạp model/artifact lớn vào bộ nhớ."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_text(path: Path, content: str) -> None:
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        partial.write_text(content, encoding="utf-8")
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def _atomic_frame(path: Path, frame: pd.DataFrame, *, parquet: bool) -> None:
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if parquet:
            frame.to_parquet(partial, index=False)
        else:
            frame.to_csv(partial, index=False, float_format="%.12g")
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def _json_safe_records(frame: pd.DataFrame) -> list[dict]:
    """Chuyển bảng summary sang JSON mà không để NaN/NumPy scalar."""
    records: list[dict] = []
    for row in frame.to_dict("records"):
        safe_row: dict = {}
        for key, value in row.items():
            if pd.isna(value):
                safe_row[key] = None
            elif isinstance(value, np.generic):
                safe_row[key] = value.item()
            else:
                safe_row[key] = value
        records.append(safe_row)
    return records


def _ml_lc_10_report(manifest: dict, tier_summary: pd.DataFrame) -> str:
    """Rendre báo cáo ngắn, dùng ngôn ngữ dễ hiểu và số liệu đã tính."""
    boundaries = manifest["risk_tier_boundaries"]
    tier_boundary_text = (
        f"Tier A: PD < {boundaries['tier_a_upper_exclusive']:.12f}; "
        f"Tier B: {boundaries['tier_b_lower_inclusive']:.12f} ≤ PD < "
        f"{boundaries['tier_b_upper_exclusive']:.12f}; "
        f"Tier C: {boundaries['tier_c_lower_inclusive']:.12f} ≤ PD < "
        f"{boundaries['tier_c_upper_exclusive']:.12f}; "
        f"Tier D: PD ≥ {boundaries['tier_d_lower_inclusive']:.12f}."
    )
    lines = [
        "# ML-LC-10 — PD → Score / Risk Tier",
        "",
        "## 1. Mục tiêu",
        "",
        "PD là xác suất vỡ nợ do model ước lượng. Stage này đổi PD thành hai thang điểm dễ đọc và một nhóm rủi ro, không huấn luyện lại model.",
        "",
        "## 2. PD là gì?",
        "",
        "Ví dụ PD = 0.25 nghĩa là model ước lượng xác suất vỡ nợ là 25%; đây không phải lời khẳng định chắc chắn về kết quả của một khoản vay.",
        "",
        "## 3. Risk Score",
        "",
        "`risk_score = 100 × predicted_pd`. Điểm cao hơn tương ứng PD model dự đoán cao hơn.",
        "",
        "## 4. Project Credit Score",
        "",
        "`credit_score = round(1000 × (1 − predicted_pd))` (làm tròn half-to-even). Điểm cao hơn tương ứng PD model dự đoán thấp hơn. Đây là điểm do project/model tạo ra, **không phải FICO và không phải điểm bureau chính thức**.",
        "",
        "## 5. Risk Tier",
        "",
        f"Với threshold khóa T = `{manifest['decision_threshold']:.17g}`: {tier_boundary_text}",
        "Các tier mô tả mức PD do model dự đoán; chúng không phải grade pháp quy, Lending Club grade, FICO band hoặc bảo đảm tần suất vỡ nợ.",
        "",
        "## 6. Phân bố theo tier",
        "",
        "`Mean PD` là trung bình xác suất model dự đoán. `Observed default rate` là tỷ lệ target=1 quan sát trong population đánh giá; hai số đo này khác nhau.",
        "",
        "| Tier | Loans | Share | Mean PD | Observed default rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in tier_summary.to_dict("records"):
        mean_pd = "—" if pd.isna(row["mean_predicted_pd"]) else f"{row['mean_predicted_pd']:.4f}"
        observed = "—" if pd.isna(row["observed_default_rate"]) else f"{row['observed_default_rate']:.4f}"
        lines.append(
            f"| {row['risk_tier']} | {row['loan_count']:,} | {row['share']:.2%} | {mean_pd} | {observed} |"
        )
    lines.extend([
        "",
        "## 7. Dashboard outputs",
        "",
        "- **V02 — PD Distribution: READY**, dùng `predicted_pd`.",
        "- **V03 — Risk Tier Distribution: READY**, dùng `risk_tier` hoặc file summary.",
        "- **V04 — FICO vs Risk / PD: READY**, dùng `fico_avg`, `predicted_pd` và `risk_tier`.",
        "",
        "Population là 269.070 frozen-test predictions đã được ML-LC-08 đánh giá; đây là artifact cho reporting/demo, chưa phải scoring toàn bộ portfolio. Không có visual Power BI nào được dựng ở stage này.",
        "",
        "## 8. Giới hạn",
        "",
        "Score và tier chỉ mô tả output của model; không chứng minh quan hệ nhân quả, không phải score pháp quy và không đảm bảo outcome cá nhân. Observed default rate chỉ dùng để mô tả population, không tham gia tạo score/tier.",
        "",
        "## 9. Bước tiếp theo",
        "",
        "ML-LC-11 — Expected Loss; cần LGD/EAD assumption được duyệt trước khi tính.",
        "",
    ])
    return "\n".join(lines)


def run_ml_lc_10(
    *,
    canonical_path: Path = CANONICAL_DATASET_PATH,
    dictionary_path: Path = DATA_DICTIONARY_PATH,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
    expected_rows: int = ML_LC_10_EXPECTED_ROWS,
) -> dict:
    """Hậu xử lý frozen-test PD thành score/tier mà không nạp hay gọi model."""
    output_dir = Path(output_dir)
    reports_dir = Path(reports_dir)
    manifest_paths = {
        "ml_lc_07_manifest.json": output_dir / ML_LC_07_MANIFEST_PATH.name,
        "ml_lc_08_manifest.json": output_dir / ML_LC_08_MANIFEST_PATH.name,
        "ml_lc_09_manifest.json": output_dir / ML_LC_09_MANIFEST_PATH.name,
    }
    manifests = {name: _read_stage_json(path) for name, path in manifest_paths.items()}
    stage_names = ("ml-lc-07", "ml-lc-08", "ml-lc-09")
    states = {
        stage: _read_stage_json(reports_dir / "tv1_stages" / "state" / f"{stage}.json")
        for stage in stage_names
    }
    if any(
        manifests[f"{stage.replace('-', '_')}_manifest.json"].get("stage") != stage
        or manifests[f"{stage.replace('-', '_')}_manifest.json"].get("status") != "PASS"
        or states[stage].get("stage") != stage
        or states[stage].get("status") != "PASS"
        for stage in stage_names
    ):
        raise GateError("ML-LC-07/08/09 manifest và state đều phải PASS.")

    ml07 = manifests["ml_lc_07_manifest.json"]
    ml08 = manifests["ml_lc_08_manifest.json"]
    ml09 = manifests["ml_lc_09_manifest.json"]
    threshold = ml07.get("selected_threshold")
    if (ml07.get("locked_candidate") != ML_LC_10_LOCKED_MODEL
            or ml07.get("selection_partition") != "validation"
            or ml07.get("threshold_selected") is not True
            or ml07.get("model_retrained") is not False
            or ml07.get("frozen_test_used_for_threshold_selection") is not False
            or ml07.get("frozen_test_used_for_evaluation") is not False
            or states["ml-lc-07"].get("selected_threshold") != threshold
            or states["ml-lc-07"].get("selected_candidate") != ML_LC_10_LOCKED_MODEL):
        raise GateError("ML-LC-07 threshold/model lock không hợp lệ.")
    try:
        threshold = float(threshold)
    except (TypeError, ValueError) as exc:
        raise GateError("ML-LC-07 locked threshold không phải số.") from exc
    if threshold != ML_LC_10_LOCKED_THRESHOLD:
        raise GateError("ML-LC-07 threshold khác ngưỡng đã khóa trong contract.")
    if (ml08.get("selected_candidate") != ML_LC_10_LOCKED_MODEL
            or ml08.get("test_prediction_path") != str(output_dir / ML_LC_08_PREDICTIONS_PATH.name)
            or ml08.get("selected_threshold") != threshold
            or ml08.get("test_rows") != expected_rows
            or ml08.get("test_evaluated") is not True
            or ml08.get("frozen_test_used_for_final_evaluation") is not True
            or ml08.get("model_retrained") is not False
            or ml08.get("candidate_changed") is not False
            or ml08.get("threshold_changed") is not False):
        raise GateError("ML-LC-08 evaluated population/model/threshold không hợp lệ.")
    if (ml09.get("model") != ML_LC_10_LOCKED_MODEL
            or ml09.get("selected_threshold") != threshold
            or ml09.get("explainability_partition") != "validation"
            or ml09.get("model_retrained") is not False
            or ml09.get("candidate_changed") is not False
            or ml09.get("threshold_changed") is not False
            or ml09.get("frozen_test_used_for_explainability") is not False):
        raise GateError("ML-LC-09 model/threshold/provenance lock không hợp lệ.")

    model_path = output_dir / "xgboost_candidate.joblib"
    prediction_path = output_dir / ML_LC_08_PREDICTIONS_PATH.name
    required_files = [model_path, *manifest_paths.values(), prediction_path]
    if any(not path.is_file() for path in required_files):
        raise GateError("Thiếu model lock, prerequisite manifests hoặc frozen-test predictions.")
    protected_before = {path.name: _file_sha256(path) for path in required_files}
    dictionary_path = Path(dictionary_path)
    if not dictionary_path.is_file():
        raise GateError(f"Thiếu data dictionary cho context policy check: {dictionary_path}")
    dictionary_hash_before = _file_sha256(dictionary_path)
    if (ml07.get("source_model_sha256_after") != protected_before[model_path.name]
            or ml08.get("protected_sha256_before", {}).get(model_path.name) != protected_before[model_path.name]
            or ml08.get("protected_sha256_before", {}).get(ML_LC_07_MANIFEST_PATH.name)
            != protected_before[ML_LC_07_MANIFEST_PATH.name]
            or ml08.get("test_prediction_sha256") != protected_before[prediction_path.name]
            or ml09.get("model_sha256_after") != protected_before[model_path.name]
            or ml09.get("model_sha256_before") != protected_before[model_path.name]):
        raise GateError("Model/prediction/prior manifest hash không khớp provenance đã khóa.")

    predictions = pd.read_parquet(prediction_path)
    if len(predictions) != expected_rows:
        raise GateError(f"Frozen-test predictions phải có {expected_rows} dòng.")
    dictionary = pd.read_csv(dictionary_path, usecols=["column_name", "policy_class"])
    if (dictionary["column_name"].isna().any()
            or dictionary["column_name"].duplicated().any()):
        raise GateError("Data dictionary column_name phải unique/non-null.")
    policy_by_column = dictionary.set_index("column_name")["policy_class"]
    missing_policy = sorted(set(ML_LC_10_CONTEXT_COLUMNS) - set(policy_by_column.index))
    if missing_policy:
        raise GateError(f"Data dictionary thiếu context columns: {missing_policy}")
    context_policy_classes = {
        column: str(policy_by_column[column]) for column in ML_LC_10_CONTEXT_COLUMNS
    }
    allowed_context_classes = {"APPLICATION_TIME", "CREDIT_SNAPSHOT"}
    forbidden_context = {
        column: policy
        for column, policy in context_policy_classes.items()
        if policy not in allowed_context_classes
    }
    if forbidden_context:
        raise GateError(f"Dashboard context có policy class không an toàn: {forbidden_context}")
    # Đọc duy nhất key và các trường mô tả được duyệt; không kéo toàn bộ 113 cột.
    context = pd.read_parquet(
        canonical_path,
        columns=["loan_id", *ML_LC_10_CONTEXT_COLUMNS],
    )
    loan_ids = predictions["loan_id"]
    context = context.loc[context["loan_id"].isin(loan_ids)].copy()
    if (len(context) != len(predictions) or context["loan_id"].isna().any()
            or not context["loan_id"].is_unique
            or set(context["loan_id"]) != set(loan_ids)):
        raise GateError("Canonical context phải khớp một-một mọi frozen-test loan_id.")

    scored = build_ml_lc_10_scored_dataset(
        predictions,
        context,
        decision_threshold=threshold,
    )
    if len(scored) != expected_rows or scored["loan_id"].isna().any() or not scored["loan_id"].is_unique:
        raise GateError("Scored artifact phải giữ đúng một hàng cho mỗi source loan_id.")
    tier_summary = build_risk_tier_summary(scored)
    score_summary = build_score_summary(scored)
    boundaries = risk_tier_boundaries(threshold)
    counts = {
        row["risk_tier"]: int(row["loan_count"])
        for row in tier_summary.to_dict("records")
    }
    shares = {
        row["risk_tier"]: float(row["share"])
        for row in tier_summary.to_dict("records")
    }
    directional_pd = tier_summary["mean_predicted_pd"].dropna().to_numpy(dtype=float)
    if directional_pd.size > 1 and np.any(np.diff(directional_pd) < 0):
        raise GateError("Risk-tier mean predicted PD direction is unexpectedly inverted.")
    model_version = ML_LC_10_MODEL_VERSION
    tier_policy = (
        "A Low: PD < 0.5*T; B Moderate: 0.5*T <= PD < T; "
        "C High: T <= PD < min(2*T,1); D Very High: PD >= min(2*T,1)."
    )
    payload = {
        "stage": ML_LC_10_STAGE,
        "status": "PASS",
        "source_predictions": str(prediction_path),
        "source_rows": int(len(predictions)),
        "source_prediction_sha256": protected_before[prediction_path.name],
        "model": ML_LC_10_LOCKED_MODEL,
        "model_version": model_version,
        "decision_threshold": threshold,
        "score_policy": "deterministic linear PD mapping; model-derived and not FICO",
        "risk_score_formula": "100 * predicted_pd",
        "credit_score_formula": "round_half_to_even(1000 * (1 - predicted_pd))",
        "risk_tier_policy": tier_policy,
        "risk_tier_boundaries": boundaries,
        "score_direction": {
            "risk_score": "higher is higher model-predicted default risk",
            "credit_score": "higher is lower model-predicted default risk; not FICO",
        },
        "risk_tier_counts": counts,
        "risk_tier_shares": shares,
        "risk_tier_summary_metrics": _json_safe_records(tier_summary),
        "scored_artifact_path": str(output_dir / ML_LC_10_SCORED_TEST_PATH.name),
        "risk_tier_summary_path": str(output_dir / ML_LC_10_RISK_TIER_SUMMARY_PATH.name),
        "score_summary_path": str(output_dir / ML_LC_10_SCORE_SUMMARY_PATH.name),
        "dashboard_readiness": {
            "V02": {"status": "READY", "source": ML_LC_10_SCORED_TEST_PATH.name,
                    "field": "predicted_pd"},
            "V03": {"status": "READY", "source": ML_LC_10_SCORED_TEST_PATH.name,
                    "summary": ML_LC_10_RISK_TIER_SUMMARY_PATH.name, "field": "risk_tier"},
            "V04": {"status": "READY", "source": ML_LC_10_SCORED_TEST_PATH.name,
                    "fields": ["fico_avg", "predicted_pd", "risk_tier"]},
        },
        "context_columns": [column for column in ML_LC_10_CONTEXT_COLUMNS if column in scored.columns],
        "context_policy_classes": context_policy_classes,
        "context_dictionary_sha256": dictionary_hash_before,
        "model_retrained": False,
        "candidate_changed": False,
        "threshold_changed": False,
        "frozen_test_used_for_tuning": False,
        "frozen_test_used_for_artifact_and_descriptive_reporting": True,
        "target_used_for_score_or_tier": False,
        "next_stage": "ml-lc-11",
        "protected_sha256_before": protected_before,
    }

    # Kiểm tra hash trước/sau computation, rồi mới công bố PASS artifacts.
    protected_after = {path.name: _file_sha256(path) for path in required_files}
    if protected_after != protected_before or _file_sha256(dictionary_path) != dictionary_hash_before:
        raise GateError("ML-LC-10 đã làm thay đổi model/input/prior locked artifacts.")
    payload["protected_sha256_after"] = protected_after
    scored_path = output_dir / ML_LC_10_SCORED_TEST_PATH.name
    tier_path = output_dir / ML_LC_10_RISK_TIER_SUMMARY_PATH.name
    score_path = output_dir / ML_LC_10_SCORE_SUMMARY_PATH.name
    manifest_path = output_dir / ML_LC_10_MANIFEST_PATH.name
    report_path = reports_dir / "tv1_stages" / f"{ML_LC_10_STAGE}.md"
    marker_path = reports_dir / "tv1_stages" / "state" / f"{ML_LC_10_STAGE}.json"
    _atomic_frame(scored_path, scored, parquet=True)
    _atomic_frame(tier_path, tier_summary, parquet=False)
    _atomic_frame(score_path, score_summary, parquet=False)
    _atomic_text(manifest_path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
    _atomic_text(report_path, _ml_lc_10_report(payload, tier_summary))
    marker = {
        "stage": ML_LC_10_STAGE,
        "title": ML_LC_10_TITLE,
        "status": "PASS",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path),
        "report_path": str(report_path),
        "scored_artifact_path": str(scored_path),
        "decision_threshold": threshold,
    }
    _atomic_text(marker_path, json.dumps(marker, ensure_ascii=False, indent=2))
    final_protected = {path.name: _file_sha256(path) for path in required_files}
    if (final_protected != protected_before
            or _file_sha256(dictionary_path) != dictionary_hash_before):
        raise GateError("Protected hashes changed during ML-LC-10 artifact writing.")
    return payload
