"""Kiểm tra giao diện Dash 6-input và cách trình bày kết quả dự đoán."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest
import pandas as pd
import plotly.graph_objects as go

from apps.individual_prediction_dash import app as dash_app
from apps.individual_prediction_dash import logic as dash_logic
from src.models.demo_6input import HOME_OWNERSHIP_FORM_LABELS
from src.models.scoring import ML_LC_10_LOCKED_THRESHOLD


def _sample_payload(pd: float, tier: str, loan_amnt: float = 12_000) -> dict[str, Any]:
    """Tạo payload giao diện khớp một kết quả model đã có, không giả lập inference."""
    return {
        "predicted_pd": pd,
        "predicted_class": int(pd >= ML_LC_10_LOCKED_THRESHOLD),
        "threshold": ML_LC_10_LOCKED_THRESHOLD,
        "risk_tier": f"Tier {tier} — Example",
        "project_credit_score": round(1000 * (1 - pd)),
        "model_safety_score": round(1000 * (1 - pd)),
        "personal_risk_percentile": 82.4,
        "personal_risk_score": 82,
        "ead_proxy": loan_amnt,
        "expected_loss_lgd_30": pd * 0.30 * loan_amnt,
        "expected_loss_lgd_45": pd * 0.45 * loan_amnt,
        "expected_loss_lgd_60": pd * 0.60 * loan_amnt,
        "model_key": "xgboost",
        "shap": [
            {"label": label, "value": value, "shap_value": contribution}
            for label, value, contribution in (
                ("Số tiền vay", loan_amnt, 0.12),
                ("Thu nhập năm", 65_000, -0.21),
                ("DTI", 18, 0.08),
                ("Kỳ hạn vay", 36, -0.03),
                ("Điểm FICO", 700, 0.01),
                ("Tình trạng nhà ở", "RENT", 0.02),
            )
        ],
    }


def _component_text(node: Any) -> list[str]:
    """Lấy nội dung chữ từ cây component Dash để kiểm tra nhãn người dùng thấy."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, (list, tuple)):
        return [text for child in node for text in _component_text(child)]
    children = getattr(node, "children", None)
    return _component_text(children) if children is not None else []


def _find_class(node: Any, class_name: str) -> list[Any]:
    """Tìm các component theo class trong cây Dash để kiểm tra nội dung hiển thị."""
    found: list[Any] = []
    if node is None:
        return found
    if isinstance(node, (list, tuple)):
        for child in node:
            found.extend(_find_class(child, class_name))
    elif getattr(node, "className", None) and class_name in node.className.split():
        found.append(node)
        found.extend(_find_class(getattr(node, "children", None), class_name))
    else:
        found.extend(_find_class(getattr(node, "children", None), class_name))
    return found


def _find_props_by_id(node: Any, component_id: str) -> dict[str, Any]:
    """Tìm thuộc tính của một component trong JSON layout của Dash."""
    if isinstance(node, dict):
        props = node.get("props", {})
        if props.get("id") == component_id:
            return props
        for value in node.values():
            found = _find_props_by_id(value, component_id)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_props_by_id(value, component_id)
            if found:
                return found
    return {}


def _result_label(card: Any) -> str:
    """Trả label text đầu tiên trong metric card."""
    return str(card.children[0].children[0])


def test_dash_layout_has_six_inputs_and_current_model_selector() -> None:
    """Trang đang chạy là form sáu đầu vào, không phải bản 5-input cũ."""
    client = dash_app.server.test_client()
    assert client.get("/").status_code == 200
    layout = client.get("/_dash-layout").get_json()

    for component_id in (
        "loan-amnt", "annual-inc", "dti", "term-months", "fico-score", "home-ownership",
    ):
        assert _find_props_by_id(layout, component_id)
    assert [item["value"] for item in _find_props_by_id(layout, "model-selector")["options"]] == [
        "xgboost", "logistic",
    ]
    assert _find_props_by_id(layout, "predict-btn")["children"] == "DỰ ĐOÁN"
    assert not _find_props_by_id(layout, "probability-scale-content")


def test_flask_server_is_exported_for_wsgi() -> None:
    """Gunicorn must target the same Flask server used by local Dash."""
    assert dash_app.server is not None
    assert dash_app.app.server is dash_app.server


def test_threshold_slider_has_full_range_marks_reference_and_session_store() -> None:
    """Ngưỡng có toàn miền 0–1 và state riêng theo session trình duyệt/tab."""
    layout = dash_app.server.test_client().get("/_dash-layout").get_json()
    slider = _find_props_by_id(layout, "threshold-slider")
    store = _find_props_by_id(layout, "threshold-store")

    assert slider["min"] == 0 and slider["max"] == 1 and slider["step"] == 0.01
    assert slider["value"] == ML_LC_10_LOCKED_THRESHOLD
    assert set(slider["marks"]) == {"0", "0.25", "0.5", "0.75", "1"}
    assert store["storage_type"] == "session"
    assert store["data"] == {"value": ML_LC_10_LOCKED_THRESHOLD}
    assert _find_props_by_id(layout, "threshold-reset")["children"] == "Đặt lại"
    assert _find_props_by_id(layout, "predict-btn")["children"] == "DỰ ĐOÁN"


def test_home_ownership_choices_map_to_exact_canonical_categories() -> None:
    """Form chỉ cho ba nhóm phổ biến; backend giữ category hiếm riêng."""
    assert HOME_OWNERSHIP_FORM_LABELS == {
        "OWN": "Sở hữu nhà",
        "MORTGAGE": "Đang trả thế chấp",
        "RENT": "Thuê nhà",
    }
    props = _find_props_by_id(
        dash_app.server.test_client().get("/_dash-layout").get_json(), "home-ownership",
    )
    assert {option["value"]: option["label"] for option in props["options"]} == HOME_OWNERSHIP_FORM_LABELS
    assert props["value"] == "RENT"
    assert props["clearable"] is False and props["searchable"] is False
    assert "home-ownership-select" in props["className"]
    assert "Nhóm khác" not in [option["label"] for option in props["options"]]


def test_preset_selection_fills_six_fields_and_shows_outcome_only_for_same_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preset điền đúng form; nhãn thật biến mất nếu hồ sơ đầu vào khác."""
    props = _find_props_by_id(
        dash_app.server.test_client().get("/_dash-layout").get_json(), "preset-selector",
    )
    assert len(props["options"]) == 8
    preset = dash_logic.DEMO_PRESETS[0]
    assert dash_app.fill_preset(preset["id"]) == (
        10000, 103000, 12.23, 36, 787, "MORTGAGE",
    )
    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    monkeypatch.setattr(app_module, "validation_demo_sample", lambda _key: ((0.1,), {preset["id"]: 0.02498}))
    form = (10000, 103000, 12.23, 36, 787, "MORTGAGE")
    assert "2,50%" in dash_app.render_preset_preview(preset["id"], "xgboost", *form)
    payload = _sample_payload(0.02498, "A")
    payload["inputs"] = {
        "loan_amnt": 10000, "annual_inc": 103000, "dti": 12.23,
        "term_months": 36, "fico_avg": 787, "home_ownership": "MORTGAGE",
    }
    actual = dash_app.render_preset_actual(
        payload, preset["id"], {"value": ML_LC_10_LOCKED_THRESHOLD}, "xgboost", *form,
    )
    assert "Non-default" in _component_text(actual)
    assert "Phân loại đúng (TN)" in _component_text(actual)
    payload["inputs"]["loan_amnt"] = 11000
    assert dash_app.render_preset_actual(
        payload, preset["id"], {"value": ML_LC_10_LOCKED_THRESHOLD}, "xgboost", *form,
    ) == ""
    assert "đã được chỉnh sửa" in dash_app.render_preset_preview(
        preset["id"], "xgboost", 11000, *form[1:],
    )


def test_threshold_visual_keeps_pd_and_moves_only_decision_boundary() -> None:
    """Cùng mẫu/PD, kéo ngưỡng chỉ đổi đường và nhóm màu."""
    sample = (0.1, 0.3, 0.7)
    lower = dash_logic.threshold_demo_figure(sample, 0.35, 0.2)
    higher = dash_logic.threshold_demo_figure(sample, 0.35, 0.5)
    assert list(lower.data[2].x) == list(higher.data[2].x) == [0.35]
    assert list(lower.data[1].x) == [0.3, 0.7]
    assert list(higher.data[1].x) == [0.7]
    assert lower.layout.shapes[0].x0 == 0.2
    assert higher.layout.shapes[0].x0 == 0.5
    assert lower.layout.xaxis.range == higher.layout.xaxis.range == (0, 1)
    left_edge = dash_logic.threshold_demo_figure(sample, 0.35, 0.0)
    right_edge = dash_logic.threshold_demo_figure(sample, 0.35, 1.0)
    assert left_edge.layout.annotations[0].xanchor == "left"
    assert right_edge.layout.annotations[0].xanchor == "right"


@pytest.mark.parametrize(("actual", "pd", "threshold", "expected"), [
    (1, 0.7, 0.2, "Phát hiện đúng (TP)"),
    (0, 0.1, 0.2, "Phân loại đúng (TN)"),
    (0, 0.2, 0.2, "Cảnh báo nhầm (FP)"),
    (1, 0.1, 0.2, "Bỏ sót cảnh báo (FN)"),
])
def test_observed_comparison_uses_current_pd_and_threshold(
    actual: int, pd: float, threshold: float, expected: str,
) -> None:
    """TP/TN/FP/FN phụ thuộc nhãn thật và PD so với ngưỡng hiện tại."""
    assert dash_logic.compare_observed_outcome(actual, pd, threshold)[2] == expected


def test_preset_error_case_changes_with_threshold_and_model_without_changing_actual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tên ca tham chiếu không áp đặt kết quả cho model/ngưỡng đang dùng."""
    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    preset = next(item for item in dash_logic.DEMO_PRESETS if item["id"] == "92214524")
    assert preset["label"] == "Ca đối chiếu A"
    monkeypatch.setattr(app_module, "validation_demo_sample", lambda _key: ((0.1,), {preset["id"]: 0.35}))
    form = tuple(preset[key] for key in (
        "loan_amnt", "annual_inc", "dti", "term_months", "fico_score", "home_ownership",
    ))
    payload = _sample_payload(0.35, "C")
    payload["inputs"] = {
        "loan_amnt": form[0], "annual_inc": form[1], "dti": form[2],
        "term_months": form[3], "fico_avg": form[4], "home_ownership": form[5],
    }
    default = app_module.render_preset_actual(payload, preset["id"], {"value": 0.22}, "xgboost", *form)
    safe = app_module.render_preset_actual(payload, preset["id"], {"value": 0.5}, "xgboost", *form)
    assert "Cảnh báo nhầm (FP)" in _component_text(default)
    assert "Phân loại đúng (TN)" in _component_text(safe)
    assert "Non-default" in _component_text(default) and "Non-default" in _component_text(safe)
    assert app_module.render_preset_actual(payload, preset["id"], {"value": 0.22}, "logistic", *form) == ""
    payload["model_key"] = "logistic"
    payload["predicted_pd"] = 0.16
    model_result = app_module.render_preset_actual(payload, preset["id"], {"value": 0.22}, "logistic", *form)
    assert "Phân loại đúng (TN)" in _component_text(model_result)
    assert app_module.render_preset_actual(payload, preset["id"], {"value": 0.22}, "logistic", 36000, *form[1:]) == ""


def test_threshold_sample_counts_use_only_fixed_displayed_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tổng hai nhóm luôn bằng số chấm; biên 0/1 và equality đúng."""
    sample = (0.0, 0.2, 1.0)
    assert dash_logic.threshold_sample_counts(sample, 0) == (3, 0)
    assert dash_logic.threshold_sample_counts(sample, 0.2) == (2, 1)
    assert dash_logic.threshold_sample_counts(sample, 1) == (1, 2)
    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    monkeypatch.setattr(app_module, "validation_demo_sample", lambda _key: (sample, {}))
    payload = _sample_payload(0.35, "C")
    low = app_module.render_threshold_visual(payload, {"value": 0.2})
    high = app_module.render_threshold_visual(payload, {"value": 1.0})
    assert low.children[0].children[0].children[1].children == "2"
    assert high.children[0].children[0].children[1].children == "1"
    assert "Trong 3 hồ sơ tham chiếu đang hiển thị" in _component_text(high)
    assert list(low.children[1].figure.data[2].x) == list(high.children[1].figure.data[2].x)
    assert app_module.render_threshold_visual({**payload, "predicted_pd": float("nan")}, {"value": 0.2}).children.startswith(
        "Biểu đồ ngưỡng hiện không khả dụng"
    )


def test_main_result_is_two_by_two_with_pd() -> None:
    """Bốn KPI theo thứ tự hai hàng; PD hiện trực tiếp dạng phần trăm."""
    payload = _sample_payload(0.15, "B")
    cards = dash_app.render_outputs(payload, 0.45)[0]

    assert len(cards) == 4
    assert [_result_label(card) for card in cards] == [
        "Mức độ rủi ro tín dụng", "Hạng rủi ro",
        "Xác suất vỡ nợ dự báo (PD)", "Điểm an toàn mô hình",
    ]
    assert cards[2].children[1].children == "15,00%"
    visible_main_text = " ".join(_component_text(cards))
    assert "PD" in visible_main_text
    assert "±" not in visible_main_text
    assert "NGƯỠNG" not in visible_main_text
    assert "15,00%" in visible_main_text
    assert "không thay đổi PD" in str(cards[2])
    assert "không phải điểm FICO" in str(cards[3])
    empty_cards = dash_app.render_outputs(None, 0.45)[0]
    assert len(empty_cards) == 4
    assert all(card.children[1].children == "—" for card in empty_cards)


@pytest.mark.parametrize(("pd", "tier", "risk_level", "risk_color"), [
    (0.05, "A", "THẤP", "metric-risk-a"),
    (0.15, "B", "TRUNG BÌNH", "metric-risk-b"),
    (0.30, "C", "CAO", "metric-risk-c"),
    (0.55, "D", "RẤT CAO", "metric-risk-d"),
])
def test_tier_drives_main_risk_label_and_ordered_color(
    pd: float, tier: str, risk_level: str, risk_color: str,
) -> None:
    """Bốn tier dùng đúng ngôn ngữ/màu có thứ tự; không tạo thang rủi ro thứ hai."""
    cards = dash_app.render_outputs(_sample_payload(pd, tier), 0.45)[0]
    assert len(cards) == 4
    assert cards[0].children[1].children == risk_level
    assert cards[1].children[1].children == tier
    assert risk_color in cards[0].className
    assert risk_color in cards[1].className


def test_pd_card_does_not_depend_on_old_percentile() -> None:
    """Percentile cũ không thay đổi PD hoặc màu card PD."""
    payload = _sample_payload(0.15, "B")
    payload["personal_risk_score"] = 100
    cards = dash_app.render_outputs(payload, 0.45)[0]
    assert cards[2].children[1].children == "15,00%"
    assert "metric-personal-risk" not in cards[2].className
    assert "metric-risk-b" in cards[0].className
    assert "metric-risk-b" in cards[1].className


def test_model_details_are_compact_without_duplicate_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chi tiết chỉ còn model và hai ngưỡng/quyết định; KPI/metric không lặp."""
    payload = _sample_payload(0.23456, "C")
    prediction_details = dash_app.render_outputs(payload, 0.45)[4]
    prediction_pairs = list(zip(
        prediction_details.children[0::2], prediction_details.children[1::2], strict=True,
    ))
    assert ("Ngưỡng tham chiếu từ mô hình chính", "0.2201") in [
        (dt.children, dd.children) for dt, dd in prediction_pairs
    ]
    assert ("Mô hình đang dùng", "XGBoost") in [
        (dt.children, dd.children) for dt, dd in prediction_pairs
    ]
    assert ("Kết luận theo threshold tham chiếu", "CẦN CẢNH BÁO (Default)") in [
        (dt.children, dd.children) for dt, dd in prediction_pairs
    ]
    assert len(prediction_pairs) == 3

    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    monkeypatch.setattr(app_module, "model_performance", lambda _key: {
        "roc_auc": 0.68, "pr_auc": 0.35, "f1": 0.40, "recall": 0.54,
        "precision": 0.32, "accuracy": 0.67, "brier_score": 0.1482,
        "log_loss": 0.4641, "threshold": ML_LC_10_LOCKED_THRESHOLD,
        "validation_rows": 269_070, "model_artifact": "xgboost_6input_demo.joblib",
    })
    monkeypatch.setattr(app_module, "validation_calibration_figure", lambda _key: go.Figure())
    performance, model_details = app_module.render_model_performance("xgboost")
    detail_text = _component_text(model_details)
    assert "CHỈ SỐ PHÂN LOẠI BỔ SUNG · VALIDATION" in detail_text
    assert "Recall" in detail_text and "Precision" in detail_text and "Accuracy" in detail_text
    assert "0.2201" in " ".join(detail_text)
    assert "ROC-AUC" not in detail_text and "Brier Score" not in detail_text
    assert "Brier Score" in _component_text(performance)
    assert "0.1482" in _component_text(performance)
    assert "Log Loss" in _component_text(performance)
    assert "0.4641" in _component_text(performance)
    assert "SAI SỐ & ĐỘ TIN CẬY MÔ HÌNH" in _component_text(performance)


def test_supplemental_metrics_follow_model_and_keep_evaluation_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recall/Precision/Accuracy của đúng demo model và ngưỡng đánh giá tĩnh."""
    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    def metrics_for(model_key: str) -> dict[str, float]:
        return {
            "recall": 0.54 if model_key == "xgboost" else 0.53,
            "precision": 0.32 if model_key == "xgboost" else 0.31,
            "accuracy": 0.68 if model_key == "xgboost" else 0.67,
            "threshold": ML_LC_10_LOCKED_THRESHOLD,
        }
    monkeypatch.setattr(app_module, "model_performance", metrics_for)
    _, xgb = app_module.render_model_performance("xgboost")
    _, logistic = app_module.render_model_performance("logistic")
    assert "0.540" in _component_text(xgb)
    assert "0.530" in _component_text(logistic)
    for node in (xgb, logistic):
        text = " ".join(_component_text(node))
        assert "0.2201" in text and "không đổi theo ngưỡng đang kéo" in text
        assert all(label not in text for label in ("ROC-AUC", "PR-AUC", "F1", "Brier Score", "Log Loss"))


@pytest.mark.parametrize(("model_key", "brier", "artifact"), [
    ("xgboost", 0.1481706174924988, "xgboost_6input_demo.joblib"),
    ("logistic", 0.149154336059764, "logistic_6input_demo.joblib"),
])
def test_model_metrics_come_from_selected_validation_manifest(
    monkeypatch: pytest.MonkeyPatch, model_key: str, brier: float, artifact: str,
) -> None:
    """Selector đọc metric/provenance của đúng manifest, không lấy test hoặc model chính."""
    manifest = {
        "validation_metrics": {"brier_score": brier, "rows": 269_070},
        "validation_rows": 269_070,
        "threshold": ML_LC_10_LOCKED_THRESHOLD,
        "stage": f"{model_key}-6input-demo-validation-candidate",
        "model_sha256": f"sha-{model_key}",
        "frozen_test_metrics": {"brier_score": 999},
    }
    monkeypatch.setattr(dash_logic, "get_six_demo", lambda selected: (object(), manifest)
                        if selected == model_key else pytest.fail("Chọn sai model."))
    metrics = dash_logic.model_performance(model_key)

    assert metrics["brier_score"] == brier
    assert metrics["validation_rows"] == 269_070
    assert metrics["threshold"] == ML_LC_10_LOCKED_THRESHOLD
    assert metrics["validation_stage"] == f"{model_key}-6input-demo-validation-candidate"
    assert metrics["model_artifact"] == artifact
    assert metrics["model_sha256"] == f"sha-{model_key}"
    assert metrics["metric_partition"] == "Validation"
    assert "frozen_test_metrics" not in metrics


@pytest.mark.parametrize("threshold", [0.0, 0.22, 0.35, 0.57, 1.0])
def test_interactive_threshold_accepts_full_range_and_intermediate_values(
    monkeypatch: pytest.MonkeyPatch, threshold: float,
) -> None:
    """Slider values within the complete inclusive range are preserved as selected."""
    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    monkeypatch.setattr(app_module, "ctx", SimpleNamespace(triggered_id="threshold-slider"))
    state, slider, display = app_module.sync_threshold_state(threshold, 0, None)
    assert state == {"value": threshold}
    assert slider == threshold
    assert display == f"{threshold:.4f}"


def test_initial_hydration_and_reset_keep_exact_canonical_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hydration/default and reset retain the non-rounded canonical value internally."""
    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    monkeypatch.setattr(app_module, "ctx", SimpleNamespace(triggered_id="threshold-store"))
    assert app_module.sync_threshold_state(
        0.22, 0, {"value": ML_LC_10_LOCKED_THRESHOLD},
    ) == ({"value": ML_LC_10_LOCKED_THRESHOLD}, ML_LC_10_LOCKED_THRESHOLD, "0.2201")
    monkeypatch.setattr(app_module, "ctx", SimpleNamespace(triggered_id="threshold-reset"))
    assert app_module.sync_threshold_state(
        0.22, 1, {"value": 0.91},
    ) == ({"value": ML_LC_10_LOCKED_THRESHOLD}, ML_LC_10_LOCKED_THRESHOLD, "0.2201")


@pytest.mark.parametrize(("threshold", "expected_flag", "expected_label"), [
    (0.0, True, "CẦN CẢNH BÁO (Default)"),
    (0.22, True, "CẦN CẢNH BÁO (Default)"),
    (0.35, True, "CẦN CẢNH BÁO (Default)"),
    (0.350001, False, "CHƯA VƯỢT NGƯỠNG (Non-default)"),
    (1.0, False, "CHƯA VƯỢT NGƯỠNG (Non-default)"),
])
def test_threshold_changes_classification_only_for_fixed_pd(
    threshold: float, expected_flag: bool, expected_label: str,
) -> None:
    """PD=0.35 là fixture tổng hợp; slider chỉ chọn nhãn theo PD >= threshold."""
    payload = _sample_payload(0.35, "C")
    classification, class_name, details = dash_app.render_threshold_classification(
        payload, {"value": threshold},
    )
    assert expected_flag is ("warning" in class_name)
    assert expected_label in _component_text(classification)
    assert ("Kết luận theo threshold đang chọn" in _component_text(details))
    assert payload["predicted_pd"] == 0.35
    assert payload["risk_tier"].startswith("Tier C")
    assert payload["expected_loss_lgd_45"] == 0.35 * 0.45 * payload["ead_proxy"]


def test_threshold_equality_is_flagged_and_invalid_values_fail_closed() -> None:
    """Đúng tại biên là flagged; helper từ chối ngưỡng/PD ngoài miền hoặc không hữu hạn."""
    assert dash_logic.classify_at_threshold(0.35, 0.35)
    assert not dash_logic.classify_at_threshold(0.349999, 0.35)
    for invalid in (-0.01, 1.01, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            dash_logic.classify_at_threshold(0.35, invalid)


def test_threshold_interaction_never_runs_prediction_or_explanation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kéo slider chỉ đồng bộ state/nhãn; các phép tính nặng không được gọi."""
    app_module = importlib.import_module("apps.individual_prediction_dash.app")

    def must_not_run(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Threshold-only update không được chạy inference/SHAP/EL.")

    monkeypatch.setattr(app_module, "run_form_prediction", must_not_run)
    monkeypatch.setattr(app_module, "shap_figure", must_not_run)
    monkeypatch.setattr(app_module, "expected_loss_figure", must_not_run)
    monkeypatch.setattr(app_module, "ctx", SimpleNamespace(triggered_id="threshold-slider"))
    state = app_module.sync_threshold_state(0.4, 0, {"value": ML_LC_10_LOCKED_THRESHOLD})[0]
    before = _sample_payload(0.35, "C")
    classification = app_module.render_threshold_classification(before, state)
    assert "CHƯA VƯỢT NGƯỠNG (Non-default)" in _component_text(classification[0])
    assert classification[1].endswith("threshold-status-safe")


@pytest.mark.parametrize("model_key", ["xgboost", "logistic"])
def test_threshold_classification_works_for_both_selected_models(model_key: str) -> None:
    """Hai demo model dùng chung nguyên tắc classification trên PD đã lưu."""
    payload = _sample_payload(0.35, "C")
    payload["model_key"] = model_key
    classification = dash_app.render_threshold_classification(payload, {"value": 0.5})
    assert "CHƯA VƯỢT NGƯỠNG (Non-default)" in _component_text(classification[0])


def test_threshold_classification_without_prediction_shows_prompt() -> None:
    """Không tạo kết quả cảnh báo trước khi người dùng chạy một inference hợp lệ."""
    result = dash_app.render_threshold_classification(None, {"value": 0.5})
    assert "bấm DỰ ĐOÁN" in _component_text(result[0])[0]
    assert result[1].endswith("threshold-status-empty")


def test_threshold_ui_does_not_add_personal_error_or_confidence_claims() -> None:
    """Slider và cảnh báo không trình bày sai số/xác suất cá nhân giả định."""
    layout_text = " ".join(_component_text(dash_app.app.layout))
    assert "khoảng tin cậy" not in layout_text.lower()
    assert "độ chính xác cá nhân" not in layout_text.lower()
    assert "±" not in layout_text
    assert "PD của hồ sơ không đổi khi thay threshold;" not in layout_text
    assert "PD VÀ NGƯỠNG CẢNH BÁO" in layout_text


def test_expected_loss_layout_is_compact_and_help_expands_in_flow() -> None:
    """EL giữ ba KPI/bar và thông tin công thức trong disclosure có thể mở."""
    layout = dash_app.server.test_client().get("/_dash-layout").get_json()
    assert "TỔN THẤT KỲ VỌNG (EL)" in " ".join(_component_text(dash_app.app.layout))
    assert _find_props_by_id(layout, "lgd-choice")["value"] == 0.45
    children = dash_app.render_outputs(_sample_payload(0.2, "B"), 0.45)[1].children
    assert [_result_label(card) for card in children[0].children] == ["Số tiền vay", "LGD", "EL dự kiến"]
    assert children[1].children == "EL THEO KỊCH BẢN LGD"
    assert len(children) == 3
    assert "Tổn thất kỳ vọng tăng từ" not in " ".join(_component_text(children))
    help_nodes = _find_class(dash_app.app.layout, "el-help")
    assert len(help_nodes) == 1
    assert "EL = PD × LGD × EAD" in " ".join(_component_text(help_nodes[0]))
    assert not getattr(help_nodes[0], "open", False)


def test_missing_validation_metric_is_unavailable_not_filled_with_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nếu manifest không có Brier/Log Loss thì UI hiện dấu gạch, không bịa giá trị."""
    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    monkeypatch.setattr(app_module, "model_performance", lambda _key: {
        "roc_auc": 0.68, "pr_auc": 0.35, "f1": 0.40,
    })
    monkeypatch.setattr(app_module, "validation_calibration_figure", lambda _key: go.Figure())
    performance, details = app_module.render_model_performance("xgboost")
    reliability_chips = _find_class(performance, "reliability-chip-grid")[0]
    assert [chip.children[1].children for chip in reliability_chips.children] == ["—", "—"]
    assert [child.children for child in details.children[2].children[0::2]] == [
        "Recall", "Precision", "Accuracy",
    ]
    assert [child.children for child in details.children[2].children[1::2]] == ["—", "—", "—"]


def test_calibration_bins_counts_rates_sparse_warning_and_perfect_reference() -> None:
    """Chart gộp đúng Validation theo bin 10%, hiển thị N và cờ bin thưa."""
    predictions = pd.DataFrame({
        "predicted_pd": [0.05] * 600 + [0.15] * 600 + [0.25] * 20,
        "target": [1] * 120 + [0] * 480 + [1] * 300 + [0] * 300 + [1] * 10 + [0] * 10,
    })
    figure = dash_logic.build_calibration_figure(predictions, "XGBoost")

    assert list(figure.data[0].x) == [0, 1]
    assert list(figure.data[0].y) == [0, 1]
    assert list(figure.data[1].x) == pytest.approx([0.05, 0.15, 0.25])
    assert list(figure.data[1].y) == pytest.approx([0.20, 0.50, 0.50])
    assert [row[1] for row in figure.data[1].customdata] == [600, 600, 20]
    assert sum(int(row[1]) for row in figure.data[1].customdata) == len(predictions)
    assert figure.data[1].customdata[0][2] == "Cỡ mẫu đạt ngưỡng"
    assert figure.data[1].customdata[2][2] == "Ít mẫu — đọc thận trọng"
    assert figure.layout.yaxis.scaleanchor == "x"


def test_calibration_loader_checks_manifest_model_prediction_and_split_hashes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
) -> None:
    """Chart accepte l'artifact Validation apparié et fail-closed si le contenu change."""
    model_path = tmp_path / "xgboost_6input_demo.joblib"
    predictions_path = tmp_path / "xgboost_6input_demo_validation_predictions.parquet"
    validation_ids_path = tmp_path / "validation_ids.parquet"
    model_path.write_bytes(b"candidate-model")
    ids = pd.DataFrame({"loan_id": ["L1", "L2"], "target": [0, 1]})
    ids.to_parquet(validation_ids_path, index=False)
    predictions = pd.DataFrame({
        "loan_id": ["L1", "L2"], "target": [0, 1],
        "predicted_pd": [0.2, 0.8], "predicted_class": [0, 1],
    })
    predictions.to_parquet(predictions_path, index=False)
    manifest = {
        "stage": "xgboost-6input-demo-validation-candidate",
        "frozen_test_accessed": False,
        "model_sha256": dash_logic._sha256(model_path),
        "validation_prediction_sha256": dash_logic._sha256(predictions_path),
        "split_artifact_sha256": {"validation": dash_logic._sha256(validation_ids_path)},
        "validation_rows": 2, "threshold": ML_LC_10_LOCKED_THRESHOLD,
        "validation_metrics": {"rows": 2, "threshold": ML_LC_10_LOCKED_THRESHOLD},
    }
    monkeypatch.setattr(dash_logic, "get_six_demo", lambda _key: (object(), manifest))
    monkeypatch.setattr(dash_logic, "MODELING_DIR", tmp_path)
    monkeypatch.setattr(dash_logic, "VALIDATION_PREDICTION_ARTIFACTS", {
        "xgboost": (model_path, predictions_path),
        "logistic": (model_path, predictions_path),
    })

    figure = dash_logic.validation_calibration_figure("xgboost")
    assert len(figure.data[1].x) == 2

    predictions.loc[0, "predicted_pd"] = 0.3
    predictions.to_parquet(predictions_path, index=False)
    with pytest.raises(ValueError, match="Provenance"):
        dash_logic.validation_calibration_figure("xgboost")

    predictions.loc[0, "predicted_pd"] = 0.2
    predictions.loc[0, "target"] = 1
    predictions.to_parquet(predictions_path, index=False)
    manifest["validation_prediction_sha256"] = dash_logic._sha256(predictions_path)
    with pytest.raises(ValueError, match="IDs/target"):
        dash_logic.load_verified_validation_predictions("xgboost")


@pytest.mark.parametrize("threshold", [0.0, 0.2, 0.5, 0.8, 1.0])
def test_validation_threshold_index_matches_sklearn(threshold: float) -> None:
    """Confusion và chỉ số của index khớp sklearn, kể cả biên và PD bằng ngưỡng."""
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

    frame = pd.DataFrame({"target": [0, 1, 1, 0, 1, 0],
                          "predicted_pd": [0.0, 0.2, 0.5, 0.5, 0.8, 1.0]})
    index = dash_logic.build_validation_threshold_index(frame)
    result = dash_logic.threshold_metrics_from_index(index, threshold)
    predicted = (frame["predicted_pd"].to_numpy() >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(frame["target"], predicted, labels=[0, 1]).ravel()
    assert (result["tn"], result["fp"], result["fn"], result["tp"]) == (tn, fp, fn, tp)
    assert sum(result[key] for key in ("tn", "fp", "fn", "tp")) == len(frame)
    assert result["flagged"] == int(predicted.sum())
    assert result["precision"] == pytest.approx(precision_score(frame["target"], predicted, zero_division=0))
    assert result["recall"] == pytest.approx(recall_score(frame["target"], predicted, zero_division=0))
    assert result["f1"] == pytest.approx(f1_score(frame["target"], predicted, zero_division=0))
    assert result["accuracy"] == pytest.approx(accuracy_score(frame["target"], predicted))


def test_threshold_index_flagged_count_is_monotonic() -> None:
    """Ngưỡng tăng không thể làm tăng số hồ sơ được gắn cờ."""
    frame = pd.DataFrame({"target": [0, 1, 1, 0], "predicted_pd": [0.1, 0.2, 0.8, 1.0]})
    index = dash_logic.build_validation_threshold_index(frame)
    flagged = [dash_logic.threshold_metrics_from_index(index, value)["flagged"]
               for value in (0.0, 0.2, 0.8, 1.0)]
    assert flagged == [4, 3, 2, 1]


def test_dynamic_validation_panel_uses_selected_model_and_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Panel đổi theo model/ngưỡng mà không gọi model inference hoặc SHAP."""
    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    source = {
        "xgboost": pd.DataFrame({"target": [0, 1, 1, 0], "predicted_pd": [0.1, 0.2, 0.8, 0.9]}),
        "logistic": pd.DataFrame({"target": [0, 1, 1, 0], "predicted_pd": [0.1, 0.6, 0.7, 0.9]}),
    }
    def checked_metrics(model_key: str, threshold: float) -> dict[str, float | int]:
        return dash_logic.threshold_metrics_from_index(
            dash_logic.build_validation_threshold_index(source[model_key]), threshold,
        )
    monkeypatch.setattr(app_module, "validation_threshold_metrics", checked_metrics)
    monkeypatch.setattr(app_module, "run_form_prediction", lambda *args: pytest.fail("Inference không được chạy"))
    monkeypatch.setattr(app_module, "shap_figure", lambda *args: pytest.fail("SHAP không được tính"))
    xgb = " ".join(_component_text(app_module.render_validation_threshold_metrics("xgboost", {"value": 0.5})))
    logistic = " ".join(_component_text(app_module.render_validation_threshold_metrics("logistic", {"value": 0.5})))
    assert "XGBoost" in xgb and "Logistic Regression" in logistic
    assert "Toàn bộ 4 hồ sơ Validation" in xgb
    assert xgb != logistic
    assert "Validation ở ngưỡng đang kéo" in xgb


def test_demo_validation_predictions_do_not_include_frozen_test_ids() -> None:
    """Hai prediction artifacts demo có đúng ID/nhãn Validation và rời Test IDs."""
    from src.config import MODELING_DIR
    validation_path = MODELING_DIR / "validation_ids.parquet"
    test_path = MODELING_DIR / "test_ids.parquet"
    if not validation_path.is_file() or not test_path.is_file():
        pytest.skip("Không có split artifacts cục bộ.")
    validation = pd.read_parquet(validation_path, columns=["loan_id", "target"])
    test_ids = set(pd.read_parquet(test_path, columns=["loan_id"])["loan_id"])
    for model_key in ("xgboost", "logistic"):
        predictions = dash_logic.load_verified_validation_predictions(model_key)
        assert len(predictions) == len(validation) == 269_070
        assert predictions["loan_id"].tolist() == validation["loan_id"].tolist()
        assert predictions["target"].tolist() == validation["target"].tolist()
        assert test_ids.isdisjoint(predictions["loan_id"])


def test_form_home_ownership_value_is_forwarded_without_remapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Form truyền nguyên category đã chọn tới model predictor."""
    received: dict[str, Any] = {}
    result = _sample_payload(0.12, "B")

    def fake_predict(values: dict[str, Any], model_key: str) -> dict[str, Any]:
        received.update(values)
        received["model_key"] = model_key
        return result

    monkeypatch.setattr(dash_logic, "predict_six_demo", fake_predict)
    monkeypatch.setattr(
        dash_logic, "personal_risk_percentile_for_model",
        lambda model_key, pd: 82.4 if model_key == "xgboost" and pd == 0.12 else -1,
    )
    predicted = dash_logic.run_form_prediction(15_000, 200_000, 10, 36, 800, "OWN", "xgboost")

    assert received == {
        "loan_amnt": 15_000, "annual_inc": 200_000, "dti": 10,
        "term_months": 36, "fico_score": 800, "home_ownership": "OWN",
        "model_key": "xgboost",
    }
    assert predicted["predicted_pd"] == 0.12
    assert predicted["personal_risk_score"] == 82


@pytest.mark.parametrize("triggered_id", ["home-ownership", "model-selector", "fico-score"])
def test_editing_input_clears_stale_prediction_without_inference(
    monkeypatch: pytest.MonkeyPatch, triggered_id: str,
) -> None:
    """Kết quả cũ không còn hiện khi category/model/input đã đổi."""
    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    monkeypatch.setattr(app_module, "ctx", SimpleNamespace(triggered_id=triggered_id))
    monkeypatch.setattr(
        app_module, "run_form_prediction",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Không được chạy inference.")),
    )
    assert app_module.predict_on_click(1, "xgboost", 12_000, 65_000, 18, 36, 700, "OWN") == (
        None, "",
    )


def test_switching_model_repredicts_matching_profile_and_never_keeps_old_pd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Đổi model sau khi đã chấm tự tính lại; input khác thì xóa kết quả cũ."""
    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    monkeypatch.setattr(app_module, "ctx", SimpleNamespace(triggered_id="model-selector"))
    previous = _sample_payload(0.35, "C")
    previous["inputs"] = {
        "loan_amnt": 12000, "annual_inc": 65000, "dti": 18,
        "term_months": 36, "fico_avg": 700, "home_ownership": "OWN",
    }
    calls: list[str] = []
    def predict(*values: Any) -> dict[str, Any]:
        calls.append(values[-1])
        return {**previous, "model_key": values[-1], "predicted_pd": 0.16}
    monkeypatch.setattr(app_module, "run_form_prediction", predict)
    result, error = app_module.predict_on_click(
        1, "logistic", 12000, 65000, 18, 36, 700, "OWN", previous,
    )
    assert not error and result["model_key"] == "logistic" and result["predicted_pd"] == 0.16
    assert calls == ["logistic"]
    assert app_module.predict_on_click(
        1, "logistic", 13000, 65000, 18, 36, 700, "OWN", previous,
    ) == (None, "")
    assert calls == ["logistic"]


def test_lgd_changes_expected_loss_but_keeps_prediction_and_shap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sensitivity dùng lại cùng inference payload/SHAP, chỉ thay EL presentation."""
    app_module = importlib.import_module("apps.individual_prediction_dash.app")

    def inference_must_not_run(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Render/đổi LGD không được chạy inference lại.")

    monkeypatch.setattr(app_module, "run_form_prediction", inference_must_not_run)
    payload = _sample_payload(0.20, "B")
    low = app_module.render_outputs(payload, 0.30)
    high = app_module.render_outputs(payload, 0.60)

    assert low[1].children[0].children[2].children[1].children == "720,00"
    assert high[1].children[0].children[2].children[1].children == "1.440,00"
    assert list(low[1].children[2].figure.data[0].y) == pytest.approx(
        list(high[1].children[2].figure.data[0].y)
    )
    assert list(low[2].children[2].figure.data[0].x) == list(high[2].children[2].figure.data[0].x)
    assert list(low[2].children[2].figure.data[0].y) == list(high[2].children[2].figure.data[0].y)


def test_shap_home_ownership_headline_is_neutral() -> None:
    """Một contribution nhà ở chỉ nói về dự đoán hiện tại, không khái quát nhân quả."""
    rows = _sample_payload(0.2, "B")["shap"]
    rows[-1]["shap_value"] = 0.7
    assert dash_logic.shap_big_idea(rows) == (
        "Tình trạng nhà ở có đóng góp tăng rủi ro lớn nhất trong dự đoán hiện tại"
    )
    rows[-1]["shap_value"] = -0.7
    assert dash_logic.shap_big_idea(rows) == (
        "Tình trạng nhà ở có đóng góp giảm rủi ro lớn nhất trong dự đoán hiện tại"
    )
