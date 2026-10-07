"""Kiểm tra giao diện Dash 6-input và cách trình bày kết quả dự đoán."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest

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


def test_main_result_is_two_by_two_without_pd_or_probability_scale() -> None:
    """Bốn KPI theo thứ tự hai hàng; số PD chỉ ở chi tiết mô hình."""
    payload = _sample_payload(0.15, "B")
    cards = dash_app.render_outputs(payload, 0.45)[0]

    assert len(cards) == 4
    assert [_result_label(card) for card in cards] == [
        "Mức độ rủi ro tín dụng", "Hạng rủi ro",
        "Điểm rủi ro cá nhân", "Điểm an toàn mô hình",
    ]
    assert cards[2].children[1].children == "82 / 100"
    visible_main_text = " ".join(_component_text(cards))
    assert "PD" not in visible_main_text
    assert "NGƯỠNG" not in visible_main_text
    assert "15,00%" not in visible_main_text
    assert "Vị trí rủi ro tương đối của hồ sơ trong phân bố dự đoán của mô hình" in str(cards[2])
    assert "Thang điểm nội bộ của project" in str(cards[3])
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


@pytest.mark.parametrize(("score", "color"), [
    (0, "metric-risk-a"), (24, "metric-risk-a"),
    (25, "metric-risk-b"), (49, "metric-risk-b"),
    (50, "metric-risk-c"), (74, "metric-risk-c"),
    (75, "metric-risk-d"), (100, "metric-risk-d"),
])
def test_personal_score_color_boundaries(score: int, color: str) -> None:
    """Chỉ score card đổi màu theo bốn khoảng 0–100."""
    payload = _sample_payload(0.15, "B")
    payload["personal_risk_score"] = score
    cards = dash_app.render_outputs(payload, 0.45)[0]
    assert cards[2].children[1].children == f"{score} / 100"
    assert color in cards[2].className
    assert "metric-risk-b" in cards[0].className
    assert "metric-risk-b" in cards[1].className


def test_exact_pd_and_decision_threshold_are_inside_model_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PD chi tiết và threshold được trình bày trong phần kỹ thuật thu gọn."""
    payload = _sample_payload(0.23456, "C")
    prediction_details = dash_app.render_outputs(payload, 0.45)[4]
    prediction_pairs = list(zip(
        prediction_details.children[0::2], prediction_details.children[1::2], strict=True,
    ))
    assert ("Xác suất dự đoán (PD)", "23,46%") in [
        (dt.children, dd.children) for dt, dd in prediction_pairs
    ]
    assert ("Điểm rủi ro cá nhân", "82 / 100") in [
        (dt.children, dd.children) for dt, dd in prediction_pairs
    ]
    assert ("Ngưỡng quyết định", "22,01%") in [
        (dt.children, dd.children) for dt, dd in prediction_pairs
    ]
    assert ("Mô hình", "XGBoost") in [
        (dt.children, dd.children) for dt, dd in prediction_pairs
    ]
    assert ("Quyết định theo ngưỡng", "Từ ngưỡng trở lên") in [
        (dt.children, dd.children) for dt, dd in prediction_pairs
    ]

    app_module = importlib.import_module("apps.individual_prediction_dash.app")
    monkeypatch.setattr(app_module, "model_performance", lambda _key: {
        "roc_auc": 0.68, "pr_auc": 0.35, "f1": 0.40, "recall": 0.54,
        "precision": 0.32, "accuracy": 0.67, "threshold": ML_LC_10_LOCKED_THRESHOLD,
    })
    _, model_details = app_module.render_model_performance("xgboost")
    details = list(zip(model_details.children[0::2], model_details.children[1::2], strict=True))
    assert ("ROC-AUC", "0.680000") in [(dt.children, dd.children) for dt, dd in details]
    assert ("Accuracy", "0.670000") in [(dt.children, dd.children) for dt, dd in details]


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
    assert list(low[1].children[3].figure.data[0].y) == pytest.approx(
        list(high[1].children[3].figure.data[0].y)
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
