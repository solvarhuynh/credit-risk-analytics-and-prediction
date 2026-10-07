"""Định dạng kết quả và biểu đồ cho ứng dụng Dash mô hình demo sáu input."""

from __future__ import annotations

from typing import Any, Mapping

import plotly.graph_objects as go

from src.models.demo_5input import LGD_OPTIONS
from src.models.demo_6input import get_six_demo, predict_six_demo
from src.models.risk_index import display_risk_index, personal_risk_percentile_for_model


MODEL_LABELS = {
    "xgboost": "XGBoost",
    "logistic": "Logistic Regression",
}


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
    personal_score = int(payload["personal_risk_score"])
    if not 0 <= personal_score <= 100:
        raise ValueError("Điểm rủi ro cá nhân phải nằm trong [0, 100].")
    score_color = ("risk-a" if personal_score < 25 else
                   "risk-b" if personal_score < 50 else
                   "risk-c" if personal_score < 75 else "risk-d")
    return {
        "pd": f"{vi_number(float(payload['predicted_pd']) * 100)}%",
        "personal_risk_score": f"{personal_score} / 100",
        "personal_risk_color_class": score_color,
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
    """Lấy validation metrics của đúng model sáu input đang hoạt động."""
    if model_key not in MODEL_LABELS:
        raise ValueError("Mô hình dự đoán không hợp lệ.")
    _, manifest = get_six_demo(model_key)
    return dict(manifest["validation_metrics"])


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
        font=dict(family="Segoe UI, Arial, sans-serif", color="#19304f", size=11),
        showlegend=False,
        xaxis=dict(title=None, categoryorder="array", categoryarray=["30%", "45%", "60%"]),
        yaxis=dict(title="Tổn thất kỳ vọng (đơn vị nguồn)", gridcolor="#e6edf5", rangemode="tozero"),
    )
    return figure
