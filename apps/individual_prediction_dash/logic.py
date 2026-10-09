"""Định dạng kết quả và biểu đồ cho ứng dụng Dash mô hình demo sáu input."""

from __future__ import annotations

import hashlib
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.config import (
    LOGISTIC_6INPUT_DEMO_PATH,
    LOGISTIC_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
    MODELING_DIR,
    XGBOOST_6INPUT_DEMO_PATH,
    XGBOOST_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
)
from src.models.demo_5input import LGD_OPTIONS
from src.models.demo_6input import get_six_demo, predict_six_demo
from src.models.risk_index import display_risk_index, personal_risk_percentile_for_model
from src.models.scoring import ML_LC_10_LOCKED_THRESHOLD


MODEL_LABELS = {
    "xgboost": "XGBoost",
    "logistic": "Logistic Regression",
}
CALIBRATION_BIN_COUNT = 10
CALIBRATION_MIN_BIN_COUNT = 500
VALIDATION_PREDICTION_ARTIFACTS = {
    "xgboost": (XGBOOST_6INPUT_DEMO_PATH, XGBOOST_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH),
    "logistic": (LOGISTIC_6INPUT_DEMO_PATH, LOGISTIC_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH),
}

DEMO_PRESETS: tuple[dict[str, Any], ...] = (
    {"id": "6925546", "label": "Rất an toàn", "loan_amnt": 10000, "annual_inc": 103000, "dti": 12.23, "term_months": 36, "fico_score": 787, "home_ownership": "MORTGAGE", "target": 0},
    {"id": "77570711", "label": "An toàn", "loan_amnt": 13000, "annual_inc": 50000, "dti": 20.24, "term_months": 36, "fico_score": 732, "home_ownership": "MORTGAGE", "target": 0},
    {"id": "126453130", "label": "Trung bình", "loan_amnt": 10100, "annual_inc": 192000, "dti": 4.92, "term_months": 36, "fico_score": 662, "home_ownership": "OWN", "target": 0},
    {"id": "34954120", "label": "Gần ngưỡng", "loan_amnt": 5000, "annual_inc": 68000, "dti": 23.16, "term_months": 36, "fico_score": 677, "home_ownership": "RENT", "target": 0},
    {"id": "67266660", "label": "Rủi ro cao", "loan_amnt": 12800, "annual_inc": 35000, "dti": 39.71, "term_months": 60, "fico_score": 707, "home_ownership": "OWN", "target": 1},
    {"id": "94290852", "label": "Rủi ro rất cao", "loan_amnt": 32750, "annual_inc": 92000, "dti": 34.89, "term_months": 60, "fico_score": 662, "home_ownership": "RENT", "target": 1},
    {"id": "92214524", "label": "Ca đối chiếu A", "reference_case": "XGBoost tại ngưỡng tham chiếu: cảnh báo nhầm (FP)", "loan_amnt": 35000, "annual_inc": 96734, "dti": 9.83, "term_months": 60, "fico_score": 667, "home_ownership": "MORTGAGE", "target": 0},
    {"id": "96513927", "label": "Ca đối chiếu B", "reference_case": "XGBoost tại ngưỡng tham chiếu: bỏ sót cảnh báo (FN)", "loan_amnt": 30000, "annual_inc": 145000, "dti": 24.45, "term_months": 36, "fico_score": 727, "home_ownership": "MORTGAGE", "target": 1},
)


def classify_at_threshold(predicted_pd: float, threshold: float) -> bool:
    """Cho biết PD có chạm/vượt ngưỡng quyết định đang chọn hay không."""
    probability = float(predicted_pd)
    decision_threshold = float(threshold)
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("PD phải là số hữu hạn trong [0, 1].")
    if not math.isfinite(decision_threshold) or not 0 <= decision_threshold <= 1:
        raise ValueError("Ngưỡng phân loại phải là số hữu hạn trong [0, 1].")
    return probability >= decision_threshold


def compare_observed_outcome(actual: int, predicted_pd: float, threshold: float) -> tuple[str, str, str]:
    """Đối chiếu nhãn Validation với phân loại tại ngưỡng tương tác hiện tại."""
    if actual not in (0, 1) or isinstance(actual, bool):
        raise ValueError("Nhãn quan sát phải là 0 hoặc 1.")
    flagged = classify_at_threshold(predicted_pd, threshold)
    labels = {
        (1, True): ("TP", "Phát hiện đúng"),
        (0, False): ("TN", "Phân loại đúng"),
        (0, True): ("FP", "Cảnh báo nhầm"),
        (1, False): ("FN", "Bỏ sót cảnh báo"),
    }
    code, explanation = labels[(actual, flagged)]
    return ("Default" if actual == 1 else "Non-default",
            "Default" if flagged else "Non-default", f"{explanation} ({code})")


def threshold_sample_counts(sample_pds: tuple[float, ...], threshold: float) -> tuple[int, int]:
    """Đếm đúng số chấm Validation đang hiển thị ở hai phía ngưỡng."""
    classify_at_threshold(0.0, threshold)
    probabilities = np.asarray(sample_pds, dtype=float)
    if (probabilities.size == 0 or not np.isfinite(probabilities).all()
            or ((probabilities < 0) | (probabilities > 1)).any()):
        raise ValueError("Mẫu PD Validation không hợp lệ.")
    flagged = int(np.count_nonzero(probabilities >= threshold))
    return flagged, len(probabilities) - flagged


def vi_number(value: float | int, decimals: int = 2) -> str:
    """Định dạng số theo cách viết tiếng Việt."""
    return f"{float(value):,.{decimals}f}".replace(",", "~").replace(".", ",").replace("~", ".")


def result_view(payload: Mapping[str, Any], lgd: float) -> dict[str, str]:
    """Chuyển kết quả canonical thành nhãn ngắn để đưa lên UI."""
    if lgd not in LGD_OPTIONS:
        raise ValueError("LGD chỉ chọn 30%, 45% hoặc 60%.")
    safety_score = int(payload.get("model_safety_score", payload["project_credit_score"]))
    tier = str(payload["risk_tier"]).replace("Tier ", "").split(" — ")[0]
    risk_level = {
        "A": "THẤP",
        "B": "TRUNG BÌNH",
        "C": "CAO",
        "D": "RẤT CAO",
    }.get(tier)
    if risk_level is None:
        raise ValueError("Hạng rủi ro không hợp lệ.")
    return {
        "pd": f"{vi_number(float(payload['predicted_pd']) * 100)}%",
        "risk_level": risk_level,
        "risk_color_class": f"risk-{tier.lower()}",
        "model_safety_score": vi_number(safety_score, 0),
        "tier": tier,
        "ead": vi_number(payload["ead_proxy"], 0),
        "lgd": f"{int(lgd * 100)}%",
        "el": vi_number(payload[f"expected_loss_lgd_{int(lgd * 100)}"]),
    }


def run_form_prediction(
    loan_amnt: Any,
    annual_inc: Any,
    dti: Any,
    term_months: Any,
    fico_score: Any,
    home_ownership: str,
    model_key: str = "xgboost",
) -> dict[str, Any]:
    """Gọi đúng model sáu input được chọn sau khi người dùng bấm DỰ ĐOÁN."""
    values = {
        "loan_amnt": loan_amnt,
        "annual_inc": annual_inc,
        "dti": dti,
        "term_months": term_months,
        "fico_score": fico_score,
        "home_ownership": home_ownership,
    }
    if model_key not in MODEL_LABELS:
        raise ValueError("Mô hình dự đoán không hợp lệ.")
    result = predict_six_demo(values, model_key)
    percentile = personal_risk_percentile_for_model(model_key, float(result["predicted_pd"]))
    return {
        **result,
        "model_key": model_key,
        "model_safety_score": int(result["project_credit_score"]),
        "personal_risk_percentile": percentile,
        "personal_risk_score": display_risk_index(percentile),
    }


def model_performance(model_key: str) -> dict[str, Any]:
    """Lấy metrics Validation và provenance của đúng model sáu input."""
    if model_key not in MODEL_LABELS:
        raise ValueError("Mô hình dự đoán không hợp lệ.")
    _, manifest = get_six_demo(model_key)
    metrics = dict(manifest.get("validation_metrics") or {})
    model_path, _ = VALIDATION_PREDICTION_ARTIFACTS[model_key]
    return {
        **metrics,
        "validation_rows": manifest.get("validation_rows"),
        "threshold": manifest.get("threshold"),
        "validation_stage": manifest.get("stage"),
        "model_artifact": model_path.name,
        "model_sha256": manifest.get("model_sha256"),
        "metric_partition": "Validation",
    }


def _sha256(path: Path) -> str:
    """Tính SHA-256 của artifact prediction đã lưu."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_calibration_figure(predictions: pd.DataFrame, model_label: str) -> go.Figure:
    """Tổng hợp PD và default theo bin xác suất; giữ lại và gắn cờ bin thưa."""
    required = {"target", "predicted_pd"}
    if not required.issubset(predictions.columns) or predictions.empty:
        raise ValueError("Prediction Validation thiếu target/predicted_pd hoặc rỗng.")
    target = pd.to_numeric(predictions["target"], errors="coerce").to_numpy(dtype=float)
    probability = pd.to_numeric(predictions["predicted_pd"], errors="coerce").to_numpy(dtype=float)
    if (not np.isfinite(target).all() or not np.isin(target, [0, 1]).all()
            or not np.isfinite(probability).all() or (probability < 0).any()
            or (probability > 1).any()):
        raise ValueError("Nhãn/PD Validation không hợp lệ để lập biểu đồ hiệu chuẩn.")

    bin_index = np.minimum((probability * CALIBRATION_BIN_COUNT).astype(int), CALIBRATION_BIN_COUNT - 1)
    xs: list[float] = []
    ys: list[float] = []
    customdata: list[list[Any]] = []
    colors: list[str] = []
    for index in range(CALIBRATION_BIN_COUNT):
        selected = bin_index == index
        count = int(selected.sum())
        if count == 0:
            continue
        mean_pd = float(probability[selected].mean())
        observed_rate = float(target[selected].mean())
        sparse = count < CALIBRATION_MIN_BIN_COUNT
        lower, upper = index * 10, (index + 1) * 10
        label = f"{lower}–{upper}%" if index < CALIBRATION_BIN_COUNT - 1 else "90–100%"
        xs.append(mean_pd)
        ys.append(observed_rate)
        customdata.append([label, count, "Ít mẫu — đọc thận trọng" if sparse else "Cỡ mẫu đạt ngưỡng"])
        colors.append("#D97832" if sparse else "#2476B8")

    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode="lines", name="Tham chiếu hoàn hảo (y = x)",
        line={"color": "#8493A3", "dash": "dash", "width": 1.5},
        hovertemplate="Tham chiếu: PD = tỷ lệ default<extra></extra>",
    ))
    figure.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers", name="Tập Validation",
        customdata=customdata,
        marker={"size": 9, "color": colors, "line": {"color": "white", "width": 1}},
        hovertemplate=("Bin PD: %{customdata[0]}<br>Số hồ sơ: %{customdata[1]:,}"
                       "<br>PD trung bình: %{x:.2%}<br>Default quan sát: %{y:.2%}"
                       "<br>%{customdata[2]}<extra></extra>"),
    ))
    figure.update_layout(
        title=f"Độ hiệu chuẩn xác suất — {model_label}",
        height=300, margin={"l": 52, "r": 16, "t": 46, "b": 48},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "y": 1.16, "x": 0},
        xaxis={"title": "PD dự đoán trung bình trong bin", "range": [0, 1], "tickformat": ".0%",
               "gridcolor": "#E8EEF4"},
        yaxis={"title": "Tỷ lệ default quan sát", "range": [0, 1], "tickformat": ".0%",
               "gridcolor": "#E8EEF4", "scaleanchor": "x", "scaleratio": 1},
        font={"family": "Segoe UI, Arial, sans-serif", "color": "#36536D", "size": 12},
    )
    return figure


def validation_calibration_figure(model_key: str) -> go.Figure:
    """Đọc đúng prediction artifact Validation đã lưu và xác thực lineage trước khi vẽ."""
    return build_calibration_figure(load_verified_validation_predictions(model_key), MODEL_LABELS[model_key])


def load_verified_validation_predictions(model_key: str) -> pd.DataFrame:
    """Xác thực model, split và prediction Validation trước khi dùng cho visual/preset."""
    if model_key not in MODEL_LABELS:
        raise ValueError("Mô hình dự đoán không hợp lệ.")
    _, manifest = get_six_demo(model_key)
    model_path, prediction_path = VALIDATION_PREDICTION_ARTIFACTS[model_key]
    validation_ids_path = MODELING_DIR / "validation_ids.parquet"
    if not prediction_path.is_file() or not validation_ids_path.is_file():
        raise FileNotFoundError("Thiếu prediction hoặc ID artifact của Validation.")
    split_hashes = manifest.get("split_artifact_sha256") or {}
    metrics = manifest.get("validation_metrics") or {}
    if (manifest.get("stage") != f"{model_key}-6input-demo-validation-candidate"
            or manifest.get("frozen_test_accessed") is not False
            or manifest.get("model_sha256") != _sha256(model_path)
            or manifest.get("validation_prediction_sha256") != _sha256(prediction_path)
            or split_hashes.get("validation") != _sha256(validation_ids_path)
            or metrics.get("rows") != manifest.get("validation_rows")
            or metrics.get("threshold") != manifest.get("threshold")):
        raise ValueError("Provenance prediction Validation không khớp manifest/model/split.")

    predictions = pd.read_parquet(
        prediction_path, columns=["loan_id", "target", "predicted_pd", "predicted_class"],
    )
    validation_ids = pd.read_parquet(validation_ids_path, columns=["loan_id"])["loan_id"]
    if (len(predictions) != manifest.get("validation_rows")
            or not np.array_equal(predictions["loan_id"].to_numpy(), validation_ids.to_numpy())
            or predictions["loan_id"].isna().any()
            or not predictions["loan_id"].is_unique
            or not predictions["target"].isin([0, 1]).all()
            or not np.array_equal(
                predictions["predicted_class"].to_numpy(),
                (predictions["predicted_pd"].to_numpy() >= manifest["threshold"]).astype("int8"),
            )):
        raise ValueError("Prediction artifact không khớp đầy đủ validation IDs/target/threshold.")
    return predictions


@lru_cache(maxsize=2)
def validation_demo_sample(model_key: str) -> tuple[tuple[float, ...], dict[str, float]]:
    """Lấy mẫu cố định từ Validation của đúng model và PD của tám hồ sơ có nhãn."""
    predictions = load_verified_validation_predictions(model_key)
    lookup = predictions.set_index("loan_id")
    preset_pds: dict[str, float] = {}
    for preset in DEMO_PRESETS:
        loan_id = preset["id"]
        if loan_id not in lookup.index or int(lookup.at[loan_id, "target"]) != preset["target"]:
            raise ValueError(f"Hồ sơ mẫu {loan_id} không khớp nhãn Validation.")
        preset_pds[loan_id] = float(lookup.at[loan_id, "predicted_pd"])
    sample = predictions.sample(n=min(120, len(predictions)), random_state=42)
    return tuple(float(value) for value in sample["predicted_pd"]), preset_pds


def threshold_demo_figure(sample_pds: tuple[float, ...], current_pd: float, threshold: float) -> go.Figure:
    """Vẽ các PD cố định và đường ngưỡng; chỉ màu/đường đổi khi kéo slider."""
    classify_at_threshold(current_pd, threshold)
    threshold_sample_counts(sample_pds, threshold)
    probabilities = np.asarray(sample_pds, dtype=float)
    jitter = np.random.default_rng(42).uniform(0.16, 0.60, len(probabilities))
    figure = go.Figure()
    for flagged, label, hover_label, color in (
        (False, "Chưa vượt ngưỡng", "CHƯA VƯỢT NGƯỠNG (Non-default)", "#278a85"),
        (True, "Cần cảnh báo", "CẦN CẢNH BÁO (Default)", "#d46b45"),
    ):
        selected = (probabilities >= threshold) == flagged
        figure.add_trace(go.Scatter(
            x=probabilities[selected], y=jitter[selected], mode="markers", name=label,
            marker={"size": 8, "color": color, "opacity": 0.72},
            hovertemplate="PD hồ sơ Validation: %{x:.2%}<br>" + hover_label + "<extra></extra>",
        ))
    figure.add_trace(go.Scatter(
        x=[current_pd], y=[0.82], mode="markers", name="Hồ sơ đang nhập",
        marker={"size": 18, "symbol": "diamond", "color": "#173b5d", "line": {"color": "white", "width": 2}},
        hovertemplate="PD hồ sơ đang nhập: %{x:.2%}<br>"
        + ("CẦN CẢNH BÁO (Default)" if current_pd >= threshold else "CHƯA VƯỢT NGƯỠNG (Non-default)")
        + "<extra></extra>",
    ))
    figure.add_vline(
        x=threshold, line_width=2, line_dash="dash", line_color="#954f28",
        annotation_text="Ngưỡng đang chọn",
        annotation_position="top right" if threshold < 0.1 else "top left",
        annotation_font_color="#954f28", annotation_font_size=11,
    )
    figure.update_layout(
        height=260, margin={"l": 18, "r": 18, "t": 34, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, Arial, sans-serif", "size": 12, "color": "#36536D"},
        legend={"orientation": "h", "y": 1.14, "x": 0},
        xaxis={"range": [0, 1], "tickformat": ".1f", "dtick": 0.1, "title": "Xác suất vỡ nợ dự báo (PD, 0–1)", "gridcolor": "#e8eef4"},
        yaxis={"range": [0, 1], "visible": False},
    )
    return figure


def shap_figure(records: list[Mapping[str, Any]]) -> go.Figure:
    """Vẽ sáu đóng góp có dấu; category giữ nguyên nhãn trong tooltip."""
    if len(records) != 6:
        raise ValueError("Biểu đồ cần đúng sáu đóng góp từ model 6-input.")
    ranked = sorted(records, key=lambda row: abs(float(row["shap_value"])), reverse=True)
    colors = []
    for index, row in enumerate(ranked):
        positive = float(row["shap_value"]) > 0
        if positive:
            colors.append("#d85642" if index == 0 else "#eab0a2")
        else:
            colors.append("#246db4" if index == 0 else "#9bbddd")
    figure = go.Figure(go.Bar(
        x=[float(row["shap_value"]) for row in ranked],
        y=[str(row["label"]) for row in ranked],
        orientation="h",
        marker_color=colors,
        customdata=[[
            vi_number(float(row["value"]), 2)
            if isinstance(row["value"], (int, float)) else str(row["value"])
        ] for row in ranked],
        hovertemplate="%{y}<br>Giá trị: %{customdata[0]}<br>Đóng góp: %{x:.4f}<extra></extra>",
    ))
    figure.update_layout(
        height=340,
        margin=dict(l=20, r=24, t=12, b=42),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, Arial, sans-serif", color="#19304f", size=13),
        showlegend=False,
        xaxis=dict(title="Đóng góp vào dự đoán", zeroline=True, zerolinecolor="#566a83",
                   zerolinewidth=2, gridcolor="#e6edf5"),
        yaxis=dict(autorange="reversed", title=None),
    )
    return figure


def shap_big_idea(records: list[Mapping[str, Any]]) -> str:
    """Tóm tắt đóng góp lớn nhất chỉ cho dự đoán của hồ sơ hiện tại."""
    if len(records) != 6:
        raise ValueError("Big Idea cần đúng sáu đóng góp của model 6-input.")
    top = max(records, key=lambda row: abs(float(row["shap_value"])))
    label = str(top["label"])
    if float(top["shap_value"]) > 0:
        direction = "có đóng góp tăng rủi ro lớn nhất"
    elif float(top["shap_value"]) < 0:
        direction = "có đóng góp giảm rủi ro lớn nhất"
    else:
        direction = "có đóng góp lớn nhất"
    return f"{label} {direction} trong dự đoán hiện tại"


def expected_loss_insight(payload: Mapping[str, Any]) -> str:
    """Tóm tắt Expected Loss từ LGD 30% lên 60%."""
    low = vi_number(payload["expected_loss_lgd_30"])
    high = vi_number(payload["expected_loss_lgd_60"])
    return f"Tổn thất kỳ vọng tăng từ {low} lên {high} khi LGD tăng từ 30% lên 60%."


def expected_loss_figure(payload: Mapping[str, Any], lgd: float) -> go.Figure:
    """Vẽ ba cột EL theo LGD và nhấn mạnh kịch bản đang chọn."""
    if lgd not in LGD_OPTIONS:
        raise ValueError("LGD chỉ chọn 30%, 45% hoặc 60%.")
    percentages = [int(option * 100) for option in LGD_OPTIONS]
    values = [float(payload[f"expected_loss_lgd_{percentage}"]) for percentage in percentages]
    selected = int(lgd * 100)
    colors = ["#0872bc" if percentage == selected else "#b9d7ea" for percentage in percentages]
    figure = go.Figure(go.Bar(
        x=[f"{percentage}%" for percentage in percentages],
        y=values,
        marker_color=colors,
        text=[vi_number(value) for value in values],
        textposition="outside",
        hovertemplate="LGD %{x}<br>Tổn thất kỳ vọng: %{y:,.2f}<extra></extra>",
    ))
    figure.update_layout(
        height=195,
        margin=dict(l=20, r=20, t=8, b=32),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, Arial, sans-serif", color="#19304f", size=12),
        showlegend=False,
        xaxis=dict(title=None, categoryorder="array", categoryarray=["30%", "45%", "60%"]),
        yaxis=dict(title="Đơn vị dữ liệu nguồn", gridcolor="#e6edf5", rangemode="tozero"),
    )
    return figure
