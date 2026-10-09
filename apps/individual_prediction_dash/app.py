"""Ứng dụng Dash HCMUTE dự đoán rủi ro khoản vay từ sáu input."""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Any

from dash import Dash, Input, Output, State, ctx, dcc, html, no_update

from apps.individual_prediction_dash.logic import (
    MODEL_LABELS,
    DEMO_PRESETS,
    ML_LC_10_LOCKED_THRESHOLD,
    classify_at_threshold,
    compare_observed_outcome,
    expected_loss_figure,
    model_performance,
    result_view,
    run_form_prediction,
    shap_big_idea,
    shap_figure,
    threshold_demo_figure,
    threshold_sample_counts,
    validation_demo_sample,
    validation_calibration_figure,
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


def _performance_chip(label: str, value: str, info: str | None = None) -> html.Div:
    """Hiển thị một metric hiệu năng gọn."""
    return html.Div(className="performance-chip", children=[
        html.Span([
            label,
            html.Span(" ⓘ", title=info, className="info-icon", role="img", **{"aria-label": info})
            if info else None,
        ], className="performance-label"),
        html.Strong(value, className="performance-value"),
    ])


def _metric_text(metrics: dict[str, Any], field: str, decimals: int = 6) -> str:
    """Định dạng metric có kiểm tra; không tự điền giá trị thay thế."""
    value = metrics.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "—"
    return f"{value:.{decimals}f}"


def _decision_text(flagged: bool) -> str:
    """Nhãn nhất quán cho quyết định nhị phân tại một ngưỡng."""
    return "CẦN CẢNH BÁO (Default)" if flagged else "CHƯA VƯỢT NGƯỠNG (Non-default)"


def _form_matches_preset(
    preset: dict[str, Any], loan_amnt: Any, annual_inc: Any, dti: Any,
    term_months: Any, fico_score: Any, home_ownership: Any,
) -> bool:
    """Chỉ nhận nhãn thật nếu cả sáu input vẫn là hồ sơ lịch sử nguyên bản."""
    return all(current == preset[field] for current, field in zip(
        (loan_amnt, annual_inc, dti, term_months, fico_score, home_ownership),
        ("loan_amnt", "annual_inc", "dti", "term_months", "fico_score", "home_ownership"),
        strict=True,
    ))


def _payload_matches_form(
    payload: dict[str, Any] | None, model_key: str, loan_amnt: Any, annual_inc: Any,
    dti: Any, term_months: Any, fico_score: Any, home_ownership: Any,
) -> bool:
    """Loại kết quả cũ trước khi dùng cho model hoặc form vừa đổi."""
    if not payload or payload.get("model_key") != model_key:
        return False
    inputs = payload.get("inputs") or {}
    return all(inputs.get(raw) == current for raw, current in (
        ("loan_amnt", loan_amnt), ("annual_inc", annual_inc), ("dti", dti),
        ("term_months", term_months), ("fico_avg", fico_score),
        ("home_ownership", home_ownership),
    ))


app.layout = html.Div(className="app-shell", children=[
    html.Div(className="ambient-background", children=[
        html.Span(className="ambient-glow ambient-glow-top"),
        html.Span(className="ambient-glow ambient-glow-bottom"),
        html.Span(className="ambient-glow ambient-glow-center"),
    ], **{"aria-hidden": "true"}),
    dcc.Store(id="result-store", storage_type="memory"),
    dcc.Store(
        id="threshold-store", storage_type="session",
        data={"value": ML_LC_10_LOCKED_THRESHOLD},
    ),
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
            html.Div(className="preset-area", children=[
                html.Label("THỬ NHANH VỚI HỒ SƠ MẪU", htmlFor="preset-selector"),
                dcc.Dropdown(
                    id="preset-selector", placeholder="Chọn một hồ sơ Validation có nhãn",
                    options=[{"label": item["label"], "value": item["id"]} for item in DEMO_PRESETS],
                    clearable=True, searchable=False, className="model-select",
                ),
                html.Div(id="preset-preview", className="preset-preview"),
            ]),
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
            html.Div(className="threshold-control", children=[
                html.Div(className="threshold-heading", children=[
                    html.Label("NGƯỠNG PHÂN LOẠI (THRESHOLD)", htmlFor="threshold-slider"),
                html.Strong("0.2201", id="threshold-value", className="threshold-value"),
                ]),
                dcc.Slider(
                    id="threshold-slider", min=0, max=1, step=0.01,
                    value=ML_LC_10_LOCKED_THRESHOLD,
                    marks={
                        0: "0", 0.25: "0.25", 0.5: "0.50", 0.75: "0.75", 1: "1",
                    }, updatemode="drag", className="threshold-slider",
                ),
                html.Div(className="threshold-footer", children=[
                    html.Small(
                        "Ngưỡng tham chiếu tối ưu F1 trên Validation của mô hình chính: 0,2201.",
                        className="threshold-note",
                    ),
                    html.Button("Đặt lại", id="threshold-reset", n_clicks=0,
                                className="button button-reset", type="button"),
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
            html.Div(
                id="threshold-classification", className="threshold-status threshold-status-empty",
                role="status", **{"aria-live": "polite"},
            ),
            html.Div(className="threshold-visual", children=[
                html.H3("PD VÀ NGƯỠNG CẢNH BÁO"),
                html.Div(id="threshold-visual-content"),
            ]),
            html.Div(id="preset-actual", className="preset-actual"),
            html.Div(className="performance-area", children=[
                html.H3("HIỆU NĂNG MÔ HÌNH · VALIDATION"),
                html.Div(id="model-performance-content", className="performance-content"),
                html.Details(className="model-details", children=[
                    html.Summary("CHI TIẾT MÔ HÌNH"),
                    html.H4("THÔNG TIN NGƯỠNG"),
                    html.Div(id="prediction-model-details", className="prediction-model-details"),
                    html.Div(id="interactive-threshold-details", className="interactive-threshold-details"),
                    html.Div(id="model-details-content"),
                ]),
            ]),
        ]),
        html.Section(className="panel el-panel", children=[
            html.Div(className="panel-heading", children=[
                html.H2("TỔN THẤT KỲ VỌNG (EL)"),
                dcc.RadioItems(id="lgd-choice", options=[
                    {"label": f"{int(lgd * 100)}%", "value": lgd} for lgd in LGD_OPTIONS
                ], value=0.45, inline=True, className="lgd-options"),
            ]),
            html.Details(className="el-help", children=[
                html.Summary("ⓘ Giải thích EL"),
                html.Div([
                    html.P("EL là tổn thất trung bình ước tính theo mô hình và giả định: EL = PD × LGD × EAD."),
                    html.P("PD: xác suất vỡ nợ. LGD: tỷ lệ tổn thất khi vỡ nợ. EAD: giá trị chịu rủi ro; ở đây lấy số tiền vay làm đại diện."),
                    html.P("EL không phải tổn thất chắc chắn xảy ra."),
                ], className="el-help-content"),
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
    Output("threshold-store", "data"),
    Output("threshold-slider", "value"),
    Output("threshold-value", "children"),
    Input("threshold-slider", "value"),
    Input("threshold-reset", "n_clicks"),
    Input("threshold-store", "data"),
)
def sync_threshold_state(
    slider_value: float | None, reset_clicks: int, stored_threshold: dict[str, Any] | None,
) -> tuple[dict[str, float], float, str]:
    """Giữ ngưỡng trong session tab; lần đầu/reset dùng chính xác ngưỡng chuẩn."""
    if ctx.triggered_id == "threshold-reset":
        threshold = ML_LC_10_LOCKED_THRESHOLD
    elif ctx.triggered_id == "threshold-store":
        threshold = float((stored_threshold or {}).get("value", ML_LC_10_LOCKED_THRESHOLD))
    else:
        threshold = float(slider_value if slider_value is not None else ML_LC_10_LOCKED_THRESHOLD)
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        threshold = ML_LC_10_LOCKED_THRESHOLD
    return {"value": threshold}, threshold, f"{threshold:.4f}"


@app.callback(
    Output("threshold-classification", "children"),
    Output("threshold-classification", "className"),
    Output("interactive-threshold-details", "children"),
    Input("result-store", "data"),
    Input("threshold-store", "data"),
)
def render_threshold_classification(
    payload: dict[str, Any] | None, threshold_state: dict[str, Any] | None,
) -> tuple[Any, str, Any]:
    """Chỉ đổi nhãn phân loại; không gọi inference, SHAP, percentile hoặc EL."""
    if payload is None:
        return (
            "Nhập thông tin và bấm DỰ ĐOÁN để xem phân loại theo ngưỡng.",
            "threshold-status threshold-status-empty",
            html.P("Ngưỡng đang chọn sẽ áp dụng sau khi có kết quả dự đoán.", className="threshold-details-note"),
        )
    try:
        threshold = float((threshold_state or {}).get("value", ML_LC_10_LOCKED_THRESHOLD))
        is_flagged = classify_at_threshold(float(payload["predicted_pd"]), threshold)
    except (TypeError, ValueError, KeyError):
        return "Kết quả dự đoán chưa hợp lệ.", "threshold-status threshold-status-empty", ""
    decision = _decision_text(is_flagged)
    details = html.Dl(className="details-grid threshold-details", children=[
        html.Dt("Threshold đang chọn"), html.Dd(f"{threshold:.4f}"),
        html.Dt("Kết luận theo threshold đang chọn"), html.Dd(decision),
    ])
    return (
        html.Div([html.Span("KẾT LUẬN THEO NGƯỠNG ĐANG CHỌN"), html.Strong(decision)]),
        "threshold-status threshold-status-warning" if is_flagged
        else "threshold-status threshold-status-safe",
        details,
    )


@app.callback(
    Output("threshold-visual-content", "children"),
    Input("result-store", "data"), Input("threshold-store", "data"),
)
def render_threshold_visual(
    payload: dict[str, Any] | None, threshold_state: dict[str, Any] | None,
) -> Any:
    """Cập nhật đường ngưỡng/màu từ PD đã lưu, không suy luận lại."""
    if payload is None:
        return html.P("Dự đoán một hồ sơ để xem vị trí PD trên tập mẫu Validation.", className="threshold-visual-empty")
    try:
        sample, _ = validation_demo_sample(payload["model_key"])
        threshold = float((threshold_state or {}).get("value", ML_LC_10_LOCKED_THRESHOLD))
        figure = threshold_demo_figure(sample, float(payload["predicted_pd"]), threshold)
        flagged, below = threshold_sample_counts(sample, threshold)
    except (TypeError, ValueError, FileNotFoundError, KeyError):
        LOGGER.exception("Không nạp được mẫu Validation để vẽ ngưỡng")
        return html.P("Biểu đồ ngưỡng hiện không khả dụng: thiếu dữ liệu Validation đã xác thực.")
    return html.Div([
        html.Div([
            html.Div([html.Span("Số hồ sơ được gắn cờ"), html.Strong(str(flagged))],
                     className="threshold-summary-item threshold-summary-warning"),
            html.Div([html.Span("Số hồ sơ dưới ngưỡng"), html.Strong(str(below))],
                     className="threshold-summary-item threshold-summary-safe"),
            html.Small(f"Trong {len(sample)} hồ sơ tham chiếu đang hiển thị",
                       className="threshold-summary-population"),
        ], className="threshold-summary"),
        dcc.Graph(figure=figure, config={"displayModeBar": False, "responsive": True}),
    ])


@app.callback(
    Output("loan-amnt", "value"), Output("annual-inc", "value"), Output("dti", "value"),
    Output("term-months", "value"), Output("fico-score", "value"),
    Output("home-ownership", "value"), Input("preset-selector", "value"),
    prevent_initial_call=True,
)
def fill_preset(preset_id: str | None) -> tuple[Any, ...]:
    """Điền đúng sáu trường gốc từ hồ sơ đã đối chiếu; clear giữ nguyên form."""
    preset = next((item for item in DEMO_PRESETS if item["id"] == preset_id), None)
    if preset is None:
        return (no_update,) * 6
    return tuple(preset[field] for field in (
        "loan_amnt", "annual_inc", "dti", "term_months", "fico_score", "home_ownership",
    ))


@app.callback(
    Output("preset-preview", "children"),
    Input("preset-selector", "value"), Input("model-selector", "value"),
    Input("loan-amnt", "value"), Input("annual-inc", "value"), Input("dti", "value"),
    Input("term-months", "value"), Input("fico-score", "value"),
    Input("home-ownership", "value"),
)
def render_preset_preview(
    preset_id: str | None, model_key: str, loan_amnt: Any, annual_inc: Any,
    dti: Any, term_months: Any, fico_score: Any, home_ownership: Any,
) -> Any:
    """Hiện PD Validation của model đang chọn, theo loan_id có nhãn thật."""
    if not preset_id:
        return ""
    preset = next((item for item in DEMO_PRESETS if item["id"] == preset_id), None)
    if preset is None:
        return ""
    if not _form_matches_preset(
        preset, loan_amnt, annual_inc, dti, term_months, fico_score, home_ownership,
    ):
        return "Hồ sơ mẫu đã được chỉnh sửa; nhãn thực tế của ca gốc không áp dụng."
    try:
        _, preset_pds = validation_demo_sample(model_key)
        pd_value = preset_pds[preset_id]
    except (ValueError, FileNotFoundError, KeyError):
        LOGGER.exception("Không nạp được PD Validation của hồ sơ mẫu")
        return "PD mẫu chưa khả dụng; hãy kiểm tra artifact Validation."
    reference = f" · {preset['reference_case']}." if preset.get("reference_case") else ""
    return f"PD Validation ({MODEL_LABELS[model_key]}): {vi_number(pd_value * 100)}% · Bấm DỰ ĐOÁN để tính lại{reference}"


@app.callback(
    Output("preset-actual", "children"),
    Input("result-store", "data"), Input("preset-selector", "value"),
    Input("threshold-store", "data"), Input("model-selector", "value"),
    Input("loan-amnt", "value"), Input("annual-inc", "value"), Input("dti", "value"),
    Input("term-months", "value"), Input("fico-score", "value"),
    Input("home-ownership", "value"),
)
def render_preset_actual(
    payload: dict[str, Any] | None, preset_id: str | None,
    threshold_state: dict[str, Any] | None, model_key: str,
    loan_amnt: Any, annual_inc: Any, dti: Any, term_months: Any,
    fico_score: Any, home_ownership: Any,
) -> Any:
    """Đối chiếu outcome cố định với PD/ngưỡng hiện tại khi form còn nguyên gốc."""
    if payload is None or not preset_id:
        return ""
    preset = next((item for item in DEMO_PRESETS if item["id"] == preset_id), None)
    if (preset is None or not _form_matches_preset(
        preset, loan_amnt, annual_inc, dti, term_months, fico_score, home_ownership,
    ) or not _payload_matches_form(
        payload, model_key, loan_amnt, annual_inc, dti, term_months, fico_score, home_ownership,
    )):
        return ""
    try:
        validation_demo_sample(model_key)
        threshold = float((threshold_state or {}).get("value", ML_LC_10_LOCKED_THRESHOLD))
        actual, predicted, comparison = compare_observed_outcome(
            preset["target"], float(payload["predicted_pd"]), threshold,
        )
    except (TypeError, ValueError, FileNotFoundError, KeyError):
        return ""
    return html.Div([
        html.Div([
            html.Span(["THỰC TẾ", html.Strong(actual)]),
            html.Span(["PHÂN LOẠI HIỆN TẠI", html.Strong(predicted)]),
            html.Span(["ĐỐI CHIẾU", html.Strong(comparison)]),
        ], className="preset-actual-grid"),
        html.Small("Một trường hợp quan sát trên Validation; không bảo đảm kết quả cho hồ sơ khác."),
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
        return html.Div("Metrics Validation hiện không khả dụng.", className="empty-value"), "Chưa có metrics."
    primary_metrics = html.Div([
        html.H4("XẾP HẠNG & PHÂN LOẠI · VALIDATION"),
        html.Div([_performance_chip(label, _metric_text(metrics, field, 3))
                  for label, field in (("ROC-AUC", "roc_auc"), ("PR-AUC", "pr_auc"))]
                 + [_performance_chip(
                     "F1", _metric_text(metrics, "f1", 3),
                     f"F1 trên Validation tại ngưỡng đánh giá {_metric_text(metrics, 'threshold', 4)}; không đổi theo thanh trượt.",
                 )],
                 className="performance-chip-grid"),
    ], className="performance-group")
    reliability_metrics = html.Div([
        html.H4([
            "SAI SỐ & ĐỘ TIN CẬY MÔ HÌNH",
            html.Span(
                "ⓘ", className="info-icon",
                title=("Các chỉ số sai số được đo trên dữ liệu kiểm định của mô hình. "
                       "Chúng phản ánh chất lượng dự báo chung, không phải sai số xác định cho hồ sơ đang nhập."),
                role="img",
                **{"aria-label": "Các chỉ số sai số được đo trên Validation, không phải sai số của hồ sơ đang nhập."},
            ),
        ]),
        html.Div([
            _performance_chip(
                "Brier Score", _metric_text(metrics, "brier_score", 4),
                "Sai số bình phương trung bình giữa xác suất dự đoán và kết quả thực tế "
                "trên tập Validation. Càng thấp càng tốt.",
            ),
            _performance_chip(
                "Log Loss", _metric_text(metrics, "log_loss", 4),
                "Chỉ số đo chất lượng xác suất dự đoán; phạt mạnh những dự đoán rất chắc chắn "
                "nhưng sai. Càng thấp càng tốt.",
            ),
        ], className="performance-chip-grid reliability-chip-grid"),
    ], className="performance-group reliability-group")
    performance_content = html.Div([primary_metrics, reliability_metrics], className="performance-groups")
    details_content = html.Div(className="supplemental-metrics", children=[
        html.H4("CHỈ SỐ PHÂN LOẠI BỔ SUNG · VALIDATION"),
        html.P(
            f"Đánh giá tại ngưỡng {_metric_text(metrics, 'threshold', 4)} trong artifact; "
            "không đổi theo ngưỡng đang kéo.",
        ),
        html.Dl(className="details-grid", children=[
            *[item for label, field in (
                ("Recall", "recall"), ("Precision", "precision"), ("Accuracy", "accuracy"),
            ) for item in (html.Dt(label), html.Dd(_metric_text(metrics, field, 3)))],
        ]),
    ])
    return performance_content, details_content


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
    State("result-store", "data"),
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
    previous_result: dict[str, Any] | None = None,
) -> tuple[Any, str]:
    """Bấm nút để dự đoán; đổi model dự đoán lại khi có hồ sơ hợp lệ."""
    trigger = ctx.triggered_id
    if trigger == "model-selector":
        old_model = (previous_result or {}).get("model_key")
        if old_model == model_key or not old_model or not _payload_matches_form(
            previous_result, old_model, loan_amnt, annual_inc, dti, term_months,
            fico_score, home_ownership,
        ):
            return None, ""
    elif trigger != "predict-btn":
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
            _metric("Xác suất vỡ nợ dự báo (PD)", "—"),
            _metric("Điểm an toàn mô hình", "—", info="Điểm quy đổi từ PD; điểm cao hơn nghĩa là rủi ro dự báo thấp hơn. Đây không phải điểm FICO người dùng nhập."),
        ], html.Div([
            html.Div([
                _metric("Số tiền vay", "—", info="Trong công thức, số tiền vay được dùng làm EAD proxy."),
                _metric("LGD", "45%"),
            _metric("EL dự kiến", "—", emphasis="metric-primary"),
            ], className="el-grid"),
            html.Div("Nhập thông tin và bấm DỰ ĐOÁN", className="empty-value el-empty"),
        ], className="el-content-wrap"), html.Div("Nhập thông tin và bấm DỰ ĐOÁN", className="empty-value"), "",
        html.Div("Thông tin mô hình sẽ hiện sau khi dự đoán.", className="empty-value"))
    values = result_view(payload, float(lgd))
    result_cards = [
        _metric("Mức độ rủi ro tín dụng", values["risk_level"],
                emphasis=f"metric-primary metric-severity metric-{values['risk_color_class']}",
                info="Mức rủi ro được suy ra từ dải PD của mô hình."),
        _metric("Hạng rủi ro", values["tier"],
                emphasis=f"metric-tier metric-{values['risk_color_class']}",
                info="Hạng A/B/C/D được suy ra từ dải PD cố định, không đổi theo ngưỡng tương tác."),
        _metric("Xác suất vỡ nợ dự báo (PD)", values["pd"], emphasis="metric-pd",
                info="Xác suất do mô hình dự báo cho hồ sơ; kéo ngưỡng không thay đổi PD."),
        _metric("Điểm an toàn mô hình", values["model_safety_score"], emphasis="metric-safety",
                info="Điểm quy đổi từ PD; điểm cao hơn nghĩa là rủi ro dự báo thấp hơn. Đây không phải điểm FICO người dùng nhập."),
    ]
    prediction_details = html.Dl(className="details-grid prediction-details", children=[
        html.Dt("Mô hình đang dùng"), html.Dd(MODEL_LABELS[payload["model_key"]]),
        html.Dt("Threshold tham chiếu tối ưu"), html.Dd(f"{float(payload['threshold']):.4f}"),
        html.Dt("Kết luận theo threshold tham chiếu"),
        html.Dd(_decision_text(classify_at_threshold(float(payload["predicted_pd"]), float(payload["threshold"])))),
    ])
    el_cards = [
        _metric("Số tiền vay", values["ead"], info="Trong công thức, số tiền vay được dùng làm EAD proxy."),
        _metric("LGD", values["lgd"]),
        _metric("EL dự kiến", values["el"], emphasis="metric-primary"),
    ]
    el_graph = dcc.Graph(
        figure=expected_loss_figure(payload, float(lgd)),
        config={"displayModeBar": False, "responsive": True},
        className="el-sensitivity-chart",
    )
    el_content = html.Div([
        html.Div(el_cards, className="el-grid"),
        html.H3("EL THEO KỊCH BẢN LGD", className="sensitivity-title"),
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
