"""Ứng dụng Dash HCMUTE dự đoán rủi ro khoản vay từ sáu input."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dash import Dash, Input, Output, ctx, dcc, html

from apps.individual_prediction_dash.logic import (
    MODEL_LABELS,
    expected_loss_figure,
    expected_loss_insight,
    model_performance,
    result_view,
    run_form_prediction,
    shap_big_idea,
    shap_figure,
    vi_number,
)
from src.models.demo_5input import LGD_OPTIONS
from src.models.demo_6input import HOME_OWNERSHIP_FORM_LABELS


LOGGER = logging.getLogger(__name__)
ASSETS = Path(__file__).resolve().parent / "assets"
app = Dash(__name__, title="HCMUTE · Dự đoán rủi ro khoản vay", assets_folder=str(ASSETS))
server = app.server


def _number_input(component_id: str, label: str, placeholder: str) -> html.Div:
    """Tạo ô số trống với ví dụ nằm bên trong."""
    return html.Div(className="form-field", children=[
        html.Label(label, htmlFor=component_id),
        dcc.Input(id=component_id, type="number", step="any", placeholder=placeholder,
                  className="number-input"),
    ])


def _metric(
    label: str, value: str, *, emphasis: str = "", info: str | None = None,
) -> html.Div:
    """Một ô kết quả với nhãn, giá trị và chú thích khi cần."""
    label_children: list[Any] = [label]
    if info:
        label_children.append(html.Span("ⓘ", title=info, className="info-icon", role="img",
                                        **{"aria-label": info}))
    children: list[Any] = [
        html.Div(label_children, className="metric-label"),
        html.Div(value, className="metric-value"),
    ]
    return html.Div(className=f"metric-card {emphasis}".strip(), children=children)


def _performance_chip(label: str, value: str) -> html.Div:
    """Hiển thị một metric hiệu năng gọn."""
    return html.Div(className="performance-chip", children=[
        html.Span(label, className="performance-label"),
        html.Strong(value, className="performance-value"),
    ])


app.layout = html.Div(className="app-shell", children=[
    html.Div(className="ambient-background", children=[
        html.Span(className="ambient-glow ambient-glow-top"),
        html.Span(className="ambient-glow ambient-glow-bottom"),
        html.Span(className="ambient-glow ambient-glow-center"),
    ], **{"aria-hidden": "true"}),
    dcc.Store(id="result-store", storage_type="memory"),
    html.Header(className="page-header", children=[
        html.Div(className="school-brand", children=[
            html.Img(src=app.get_asset_url("hcmute-logo.png"), alt="Logo HCMUTE",
                     className="school-logo"),
            html.Div(children=[
                html.Span("TRƯỜNG ĐẠI HỌC", className="school-prefix"),
                html.Strong("CÔNG NGHỆ KỸ THUẬT TP. HỒ CHÍ MINH", className="school-name"),
                html.Span("HCMUTE", className="school-short"),
            ]),
        ]),
        html.Div(className="header-divider"),
        html.Div(className="app-brand", children=[
            html.H1("DỰ ĐOÁN RỦI RO KHOẢN VAY"),
            html.P("Hệ thống hỗ trợ đánh giá rủi ro tín dụng bằng Machine Learning"),
        ]),
    ]),
    html.Main(className="calculator-grid", children=[
        html.Section(className="panel input-panel", children=[
            html.H2("THÔNG TIN KHOẢN VAY"),
            html.Div(className="form-grid", children=[
                html.Div(className="form-field model-field", children=[
                    html.Div(className="model-field-heading", children=[
                        html.Label("MÔ HÌNH DỰ ĐOÁN", htmlFor="model-selector"),
                    ]),
                    dcc.Dropdown(
                        id="model-selector",
                        options=[{"label": label, "value": key} for key, label in MODEL_LABELS.items()],
                        value="xgboost", clearable=False, searchable=False,
                        className="model-select",
                    ),
                ]),
                _number_input("loan-amnt", "Số tiền vay", "VD: 12.000"),
                _number_input("annual-inc", "Thu nhập năm", "VD: 65.000"),
                _number_input("dti", "DTI", "VD: 18"),
                html.Div(className="form-field", children=[
                    html.Label("Kỳ hạn vay", htmlFor="term-months"),
                    dcc.RadioItems(id="term-months", options=[
                        {"label": "36 tháng", "value": 36},
                        {"label": "60 tháng", "value": 60},
                    ], value=36, inline=True, className="term-options"),
                ]),
                _number_input("fico-score", "Điểm FICO", "VD: 700"),
                html.Div(className="form-field", children=[
                    html.Label("Tình trạng nhà ở", htmlFor="home-ownership"),
                    dcc.Dropdown(
                        id="home-ownership",
                        options=[{"label": label, "value": category}
                                 for category, label in HOME_OWNERSHIP_FORM_LABELS.items()],
                        value="RENT", clearable=False, searchable=False,
                        className="model-select home-ownership-select",
                    ),
                ]),
            ]),
            html.Div(id="form-error", className="form-error", role="alert"),
            html.Button("DỰ ĐOÁN", id="predict-btn", n_clicks=0,
                        className="button button-primary"),
        ]),
        html.Section(className="panel result-panel", children=[
            html.Div(className="result-heading", children=[
                html.H2("KẾT QUẢ DỰ ĐOÁN"),
                html.Span(id="result-model-label", className="result-model-label"),
            ]),
            html.Div(id="result-content", className="kpi-grid"),
            html.Div(className="performance-area", children=[
                html.H3("HIỆU NĂNG MÔ HÌNH · VALIDATION"),
                html.Div(id="model-performance-content", className="performance-grid"),
                html.Details(className="model-details", children=[
                    html.Summary("CHI TIẾT MÔ HÌNH"),
                    html.Div(id="prediction-model-details", className="prediction-model-details"),
                    html.Div(id="model-details-content"),
                ]),
            ]),
        ]),
        html.Section(className="panel el-panel", children=[
            html.Div(className="panel-heading", children=[
                html.H2("TỔN THẤT KỲ VỌNG"),
                html.Span(
                    "ⓘ", className="info-icon",
                    title="Tổn thất kỳ vọng là mức tổn thất ước tính dựa trên rủi ro dự đoán, số tiền vay và LGD.",
                    role="img",
                    **{"aria-label": "Tổn thất kỳ vọng là mức tổn thất ước tính dựa trên rủi ro dự đoán, số tiền vay và LGD."},
                ),
                dcc.RadioItems(id="lgd-choice", options=[
                    {"label": f"{int(lgd * 100)}%", "value": lgd} for lgd in LGD_OPTIONS
                ], value=0.45, inline=True, className="lgd-options"),
            ]),
            html.Div(id="el-content", className="el-content"),
        ]),
        html.Section(className="panel shap-panel", children=[
            html.Div(id="shap-content"),
        ]),
    ]),
    html.Footer("HCMUTE · Credit Risk Analytics & Prediction", className="page-footer"),
])


@app.callback(
    Output("model-performance-content", "children"),
    Output("model-details-content", "children"),
    Input("model-selector", "value"),
)
def render_model_performance(model_key: str) -> tuple[Any, Any]:
    """Đổi metric khi chọn model; không chạy inference."""
    try:
        metrics = model_performance(model_key)
    except (ValueError, FileNotFoundError, KeyError):
        LOGGER.exception("Không nạp được metrics của model %s", model_key)
        return [_performance_chip(label, "—") for label in ("ROC-AUC", "PR-AUC", "F1")], "Chưa có metrics."
    chips = [_performance_chip(label, f"{metrics[field]:.3f}") for label, field in (
        ("ROC-AUC", "roc_auc"), ("PR-AUC", "pr_auc"), ("F1", "f1"),
    )]
    details = html.Dl(className="details-grid", children=[
        *[item for label, field in (
            ("ROC-AUC", "roc_auc"), ("PR-AUC", "pr_auc"), ("F1", "f1"),
            ("Recall", "recall"), ("Precision", "precision"), ("Accuracy", "accuracy"),
        ) for item in (html.Dt(label), html.Dd(f"{metrics[field]:.6f}"))],
    ])
    return chips, details


@app.callback(
    Output("result-store", "data"),
    Output("form-error", "children"),
    Input("predict-btn", "n_clicks"),
    Input("model-selector", "value"),
    Input("loan-amnt", "value"),
    Input("annual-inc", "value"),
    Input("dti", "value"),
    Input("term-months", "value"),
    Input("fico-score", "value"),
    Input("home-ownership", "value"),
    prevent_initial_call=True,
    running=[
        (Output("predict-btn", "disabled"), True, False),
        (Output("predict-btn", "children"), "ĐANG DỰ ĐOÁN…", "DỰ ĐOÁN"),
    ],
)
def predict_on_click(
    clicks: int,
    model_key: str,
    loan_amnt: Any,
    annual_inc: Any,
    dti: Any,
    term_months: Any,
    fico_score: Any,
    home_ownership: str,
) -> tuple[Any, str]:
    """Chỉ suy luận khi bấm nút; đổi bất kỳ input/model nào xóa kết quả cũ."""
    if ctx.triggered_id != "predict-btn":
        return None, ""
    try:
        result = run_form_prediction(
            loan_amnt, annual_inc, dti, term_months, fico_score, home_ownership, model_key,
        )
    except ValueError as exc:
        return None, str(exc)
    except FileNotFoundError:
        LOGGER.exception("Chưa có artifact model/reference sáu input")
        return None, "Mô hình dự đoán hiện chưa sẵn sàng."
    except Exception:
        LOGGER.exception("Không chạy được dự đoán sáu input")
        return None, "Không chạy được dự đoán. Hãy kiểm tra thông tin rồi thử lại."
    return result, ""


@app.callback(
    Output("result-content", "children"),
    Output("el-content", "children"),
    Output("shap-content", "children"),
    Output("result-model-label", "children"),
    Output("prediction-model-details", "children"),
    Input("result-store", "data"),
    Input("lgd-choice", "value"),
)
def render_outputs(payload: dict[str, Any] | None, lgd: float) -> tuple[Any, Any, Any, str, Any]:
    """Hiển thị dự đoán đã bấm và EL theo LGD đang chọn."""
    if payload is None:
        return ([
            _metric("Mức độ rủi ro tín dụng", "—", emphasis="metric-primary metric-severity"),
            _metric("Hạng rủi ro", "—", emphasis="metric-tier"),
            _metric("Điểm rủi ro cá nhân", "—"),
            _metric("Điểm an toàn mô hình", "—", info="Thang điểm nội bộ của project; điểm cao hơn nghĩa là mô hình đánh giá hồ sơ an toàn hơn."),
        ], html.Div([
            html.Div([
                _metric("Số tiền vay", "—", info="Trong công thức, số tiền vay được dùng làm EAD proxy."),
                _metric("LGD", "45%"),
                _metric("Tổn thất kỳ vọng", "—", emphasis="metric-primary"),
            ], className="el-grid"),
            html.Div("Nhập thông tin và bấm DỰ ĐOÁN", className="empty-value el-empty"),
        ], className="el-content-wrap"), html.Div("Nhập thông tin và bấm DỰ ĐOÁN", className="empty-value"), "",
        html.Div("PD và quyết định theo ngưỡng sẽ hiện tại đây sau khi dự đoán.", className="empty-value"))
    values = result_view(payload, float(lgd))
    result_cards = [
        _metric("Mức độ rủi ro tín dụng", values["risk_level"],
                emphasis=f"metric-primary metric-severity metric-{values['risk_color_class']}"),
        _metric("Hạng rủi ro", values["tier"],
                emphasis=f"metric-tier metric-{values['risk_color_class']}"),
        _metric("Điểm rủi ro cá nhân", values["personal_risk_score"],
                emphasis=f"metric-personal-risk metric-{values['personal_risk_color_class']}",
                info="Vị trí rủi ro tương đối của hồ sơ trong phân bố dự đoán của mô hình; điểm cao hơn nghĩa là rủi ro tương đối cao hơn."),
        _metric("Điểm an toàn mô hình", values["model_safety_score"], emphasis="metric-safety",
                info="Thang điểm nội bộ của project; điểm cao hơn nghĩa là mô hình đánh giá hồ sơ an toàn hơn."),
    ]
    threshold_decision = "Từ ngưỡng trở lên" if int(payload["predicted_class"]) == 1 else "Dưới ngưỡng"
    prediction_details = html.Dl(className="details-grid prediction-details", children=[
        html.Dt("Mô hình"), html.Dd(MODEL_LABELS[payload["model_key"]]),
        html.Dt("Xác suất dự đoán (PD)"), html.Dd(values["pd"]),
        html.Dt("Điểm rủi ro cá nhân"), html.Dd(values["personal_risk_score"]),
        html.Dt("Ngưỡng quyết định"),
        html.Dd(f"{vi_number(float(payload['threshold']) * 100)}%"),
        html.Dt("Quyết định theo ngưỡng"), html.Dd(threshold_decision),
    ])
    el_cards = [
        _metric("Số tiền vay", values["ead"], info="Trong công thức, số tiền vay được dùng làm EAD proxy."),
        _metric("LGD", values["lgd"]),
        _metric("Tổn thất kỳ vọng", values["el"], emphasis="metric-primary"),
    ]
    el_graph = dcc.Graph(
        figure=expected_loss_figure(payload, float(lgd)),
        config={"displayModeBar": False, "responsive": True},
        className="el-sensitivity-chart",
    )
    el_content = html.Div([
        html.Div(el_cards, className="el-grid"),
        html.P(expected_loss_insight(payload), className="el-insight"),
        html.H3("TỔN THẤT KỲ VỌNG THEO LGD", className="sensitivity-title"),
        el_graph,
    ], className="el-content-wrap")
    shap_content = html.Div([
        html.H2(shap_big_idea(payload["shap"]), className="shap-big-idea"),
        html.P("Đóng góp của các yếu tố vào dự đoán của hồ sơ hiện tại", className="shap-subtitle"),
        dcc.Graph(figure=shap_figure(payload["shap"]),
                  config={"displayModeBar": False, "responsive": True}),
        html.P("Dương: tăng rủi ro · Âm: giảm rủi ro", className="shap-note"),
    ], className="shap-content-wrap")
    return (
        result_cards, el_content, shap_content,
        MODEL_LABELS.get(payload.get("model_key"), ""), prediction_details,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="127.0.0.1", port=int(os.environ.get("DASH_PORT", "8050")),
            debug=False, use_reloader=False)
