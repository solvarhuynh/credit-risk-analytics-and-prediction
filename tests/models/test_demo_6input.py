"""Contract tests cho candidate demo sáu input và categorical explanations."""

from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
import pytest

from src.models.demo_6input import (
    DEMO_6_FEATURES,
    HOME_OWNERSHIP_LABELS,
    SanitizeSixInput,
    build_logistic_six_pipeline,
    build_xgboost_six_pipeline,
    predict_six_using_model,
    validate_six_input,
)
from src.models.scoring import ML_LC_10_LOCKED_THRESHOLD, assign_pd_risk_tier


@pytest.fixture(scope="module")
def sample() -> tuple[pd.DataFrame, np.ndarray, dict]:
    rng = np.random.default_rng(334)
    n_rows = 240
    frame = pd.DataFrame({
        "loan_amnt": rng.uniform(500, 40_000, n_rows),
        "annual_inc": rng.uniform(12_000, 180_000, n_rows),
        "dti": rng.uniform(0, 50, n_rows),
        "term_months": rng.choice([36, 60], n_rows),
        "fico_avg": rng.uniform(630, 840, n_rows),
        "home_ownership": rng.choice(["MORTGAGE", "RENT", "OWN", "OTHER"], n_rows),
    }, columns=list(DEMO_6_FEATURES))
    signal = (frame.loan_amnt / 40_000 + frame.dti / 50
              - frame.fico_avg / 900 + (frame.home_ownership == "RENT") * 0.25
              + (frame.term_months == 60) * 0.15)
    target = (signal > signal.median()).astype(np.int8).to_numpy()
    manifest = {
        "home_ownership_categories_from_train": ["MORTGAGE", "RENT", "OWN", "OTHER"],
        "numeric_input_bounds_from_train": {
            field: {"min": float(frame[field].min()), "max": float(frame[field].max())}
            for field in DEMO_6_FEATURES[:-1]
        },
    }
    return frame, target, manifest


def _inputs() -> dict[str, object]:
    return {
        "loan_amnt": 12_000,
        "annual_inc": 65_000,
        "dti": 18,
        "term_months": 36,
        "fico_score": 700,
        "home_ownership": "RENT",
    }


def test_categories_are_exact_and_rare_values_are_not_collapsed() -> None:
    assert set(HOME_OWNERSHIP_LABELS) == {"MORTGAGE", "RENT", "OWN", "ANY", "NONE", "OTHER"}
    assert len(set(HOME_OWNERSHIP_LABELS.values())) == len(HOME_OWNERSHIP_LABELS)
    assert HOME_OWNERSHIP_LABELS["OTHER"] != HOME_OWNERSHIP_LABELS["NONE"]


def test_invalid_home_ownership_is_rejected(sample: tuple) -> None:
    _, _, manifest = sample
    values = _inputs()
    values["home_ownership"] = "UNSEEN_CATEGORY"
    with pytest.raises(ValueError, match="category đã được model hỗ trợ"):
        validate_six_input(values, manifest)


@pytest.mark.parametrize("category", ["Sở hữu nhà", "own", "OWN ", None])
def test_ui_label_or_malformed_category_never_silently_falls_back(
    sample: tuple, category: object,
) -> None:
    """Encoder không được nhận nhãn tiếng Việt, sai hoa/thừa cách hay null."""
    _, _, manifest = sample
    values = _inputs()
    values["home_ownership"] = category
    with pytest.raises(ValueError, match="category đã được model hỗ trợ"):
        validate_six_input(values, manifest)


def test_rare_category_remains_supported_internally(sample: tuple) -> None:
    """Ẩn OTHER khỏi form không được làm mất hỗ trợ category đã fit."""
    _, _, manifest = sample
    values = _inputs()
    values["home_ownership"] = "OTHER"
    assert validate_six_input(values, manifest)["home_ownership"] == "OTHER"


def test_negative_dti_is_rejected_instead_of_being_silently_imputed(sample: tuple) -> None:
    """DTI nhập tay âm không được biến ngầm thành missing rồi impute."""
    _, _, manifest = sample
    bounds = dict(manifest["numeric_input_bounds_from_train"])
    bounds["dti"] = {**bounds["dti"], "min": -1.0}
    manifest = {**manifest, "numeric_input_bounds_from_train": bounds}
    values = _inputs()
    values["dti"] = -0.5
    with pytest.raises(ValueError, match="DTI không được âm"):
        validate_six_input(values, manifest)


def test_sanitizer_preserves_category_and_enforces_six_column_schema(sample: tuple) -> None:
    frame, _, _ = sample
    sanitizer = SanitizeSixInput().fit(frame)
    transformed = sanitizer.transform(frame.head(2))
    assert tuple(transformed.columns) == DEMO_6_FEATURES
    assert transformed.home_ownership.tolist() == frame.home_ownership.head(2).tolist()
    with pytest.raises(ValueError, match="schema sáu field"):
        sanitizer.transform(frame.drop(columns="home_ownership"))


def test_xgboost_six_input_prediction_shap_and_joblib_round_trip(sample: tuple, tmp_path) -> None:
    frame, target, manifest = sample
    model = build_xgboost_six_pipeline(frame, model_parameters={
        "n_estimators": 10, "max_depth": 2, "learning_rate": 0.1,
        "subsample": 1.0, "colsample_bytree": 1.0, "random_state": 42,
        "objective": "binary:logistic", "eval_metric": "logloss",
        "tree_method": "hist", "n_jobs": 1,
    }).fit(frame.iloc[:190], target[:190])
    artifact = tmp_path / "six-input-xgb.joblib"
    joblib.dump(model, artifact)
    loaded = joblib.load(artifact)
    result = predict_six_using_model(loaded, _inputs(), manifest, "xgboost")
    expected = loaded.predict_proba(pd.DataFrame([{
        "loan_amnt": 12_000, "annual_inc": 65_000, "dti": 18,
        "term_months": 36, "fico_avg": 700, "home_ownership": "RENT",
    }], columns=list(DEMO_6_FEATURES)))[:, 1][0]
    assert result["predicted_pd"] == pytest.approx(expected)
    assert len(result["shap"]) == 6
    ownership = next(row for row in result["shap"] if row["feature"] == "home_ownership")
    assert ownership["value"] == "RENT"
    assert np.isfinite([row["shap_value"] for row in result["shap"]]).all()
    assert result["shap_output_space"] == "raw margin/log-odds"


def test_logistic_six_input_prediction_has_real_categorical_contribution(sample: tuple) -> None:
    frame, target, manifest = sample
    model = build_logistic_six_pipeline(frame).fit(frame.iloc[:190], target[:190])
    result = predict_six_using_model(model, _inputs(), manifest, "logistic")
    assert 0 <= result["predicted_pd"] <= 1
    assert len(result["shap"]) == 6
    assert any(row["feature"] == "home_ownership" for row in result["shap"])
    assert result["explanation_method"].startswith("signed coefficient")
    assert result["expected_loss_lgd_45"] == pytest.approx(result["predicted_pd"] * 0.45 * 12_000)


@pytest.mark.parametrize("model_key", ["xgboost", "logistic"])
def test_home_ownership_swap_preserves_numeric_inputs_and_explanation(
    sample: tuple, model_key: str,
) -> None:
    """Ba category phải kích hoạt đúng OHE, PD cột dương và SHAP gộp đủ."""
    frame, target, manifest = sample
    if model_key == "xgboost":
        pipeline = build_xgboost_six_pipeline(frame, model_parameters={
            "n_estimators": 10, "max_depth": 2, "learning_rate": 0.1,
            "subsample": 1.0, "colsample_bytree": 1.0, "random_state": 42,
            "objective": "binary:logistic", "eval_metric": "logloss",
            "tree_method": "hist", "n_jobs": 1,
        }).fit(frame.iloc[:190], target[:190])
    else:
        pipeline = build_logistic_six_pipeline(frame).fit(frame.iloc[:190], target[:190])

    names = pipeline.named_steps["preprocess"].get_feature_names_out().tolist()
    home_indices = [index for index, name in enumerate(names) if "home_ownership_" in name]
    numeric_indices = [index for index in range(len(names)) if index not in home_indices]
    baseline_numeric: np.ndarray | None = None
    for category in ("OWN", "MORTGAGE", "RENT"):
        values = {**_inputs(), "home_ownership": category}
        result = predict_six_using_model(pipeline, values, manifest, model_key)
        assert result["inputs"]["home_ownership"] == category
        assert {key: value for key, value in result["inputs"].items() if key != "home_ownership"} == {
            "loan_amnt": 12_000, "annual_inc": 65_000, "dti": 18,
            "term_months": 36, "fico_avg": 700,
        }
        input_frame = pd.DataFrame([result["inputs"]], columns=list(DEMO_6_FEATURES))
        transformed = pipeline.named_steps["preprocess"].transform(
            pipeline.named_steps["normalize_missing"].transform(
                pipeline.named_steps["sanitize"].transform(input_frame)
            )
        )
        dense = transformed.toarray().reshape(-1) if hasattr(transformed, "toarray") else np.asarray(transformed).reshape(-1)
        active = [names[index] for index in home_indices if dense[index] == 1]
        assert active == [f"categorical__home_ownership_{category}"]
        assert sum(dense[home_indices]) == pytest.approx(1)
        if baseline_numeric is None:
            baseline_numeric = dense[numeric_indices].copy()
        np.testing.assert_allclose(dense[numeric_indices], baseline_numeric)

        direct_pd = float(pipeline.predict_proba(input_frame)[0, 1])
        assert result["predicted_pd"] == pytest.approx(direct_pd)
        assert 0 <= direct_pd <= 1
        assert result["predicted_class"] == int(direct_pd >= ML_LC_10_LOCKED_THRESHOLD)
        assert result["risk_tier"] == assign_pd_risk_tier(
            [direct_pd], decision_threshold=ML_LC_10_LOCKED_THRESHOLD,
        )[0]
        assert 0 <= result["project_credit_score"] <= 1000
        assert result["expected_loss_lgd_45"] == pytest.approx(direct_pd * 0.45 * 12_000)

        model = pipeline.named_steps["model"]
        if model_key == "xgboost":
            import shap
            explainer = shap.TreeExplainer(model, model_output="raw")
            contributions = np.asarray(
                explainer.shap_values(transformed, check_additivity=False), dtype=float,
            ).reshape(-1)
            base = float(np.asarray(explainer.expected_value).reshape(-1)[0])
            margin = float(np.asarray(model.predict(transformed, output_margin=True)).reshape(-1)[0])
        else:
            contributions = dense * np.asarray(model.coef_[0], dtype=float)
            base = float(model.intercept_[0])
            margin = float(model.decision_function(transformed)[0])
        home_sum = sum(contributions[index] for index in home_indices)
        grouped_home = next(
            row["shap_value"] for row in result["shap"] if row["feature"] == "home_ownership"
        )
        assert grouped_home == pytest.approx(home_sum)
        assert base + sum(row["shap_value"] for row in result["shap"]) == pytest.approx(
            margin, abs=1e-3,
        )
