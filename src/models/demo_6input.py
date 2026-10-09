"""Candidate demo sáu input, chỉ fit trên train và đánh giá trên validation."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.config import (
    CANONICAL_DATASET_PATH,
    DATA_DICTIONARY_PATH,
    DATASET_MANIFEST_PATH,
    LOGISTIC_5INPUT_DEMO_MANIFEST_PATH,
    LOGISTIC_5INPUT_DEMO_PATH,
    LOGISTIC_6INPUT_DEMO_MANIFEST_PATH,
    LOGISTIC_6INPUT_DEMO_PATH,
    LOGISTIC_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
    ML_LC_12_MANIFEST_PATH,
    MODELING_DIR,
    XGBOOST_5INPUT_DEMO_MANIFEST_PATH,
    XGBOOST_5INPUT_DEMO_PATH,
    XGBOOST_6INPUT_DEMO_MANIFEST_PATH,
    XGBOOST_6INPUT_DEMO_PATH,
    XGBOOST_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
)
from src.models.demo_5input import _metrics
from src.models.preprocess_pipeline import (
    NormalizePandasMissing,
    build_preprocessor,
    build_xgboost_preprocessor,
)
from src.models.scoring import (
    ML_LC_10_LOCKED_THRESHOLD,
    assign_pd_risk_tier,
    probability_to_project_credit_score,
    probability_to_risk_score,
    validate_probability_of_default,
)
from src.models.cost_optimization import calculate_expected_loss
from src.models.demo_5input import LGD_OPTIONS
from src.models.demo_5input import MODEL_PARAMETERS as XGBOOST_PARAMETERS


DEMO_6_FEATURES = ("loan_amnt", "annual_inc", "dti", "term_months", "fico_avg", "home_ownership")
VISIBLE_INPUTS = ("loan_amnt", "annual_inc", "dti", "term_months", "fico_score", "home_ownership")
DISPLAY_FEATURES = {
    "loan_amnt": "Số tiền vay",
    "annual_inc": "Thu nhập năm",
    "dti": "DTI",
    "term_months": "Kỳ hạn vay",
    "fico_avg": "Điểm FICO",
    "home_ownership": "Tình trạng nhà ở",
}
HOME_OWNERSHIP_LABELS = {
    "MORTGAGE": "Đang trả thế chấp",
    "RENT": "Thuê nhà",
    "OWN": "Sở hữu nhà",
    "ANY": "Nhóm rất hiếm (ANY)",
    "NONE": "Nhóm rất hiếm (NONE)",
    "OTHER": "Nhóm rất hiếm (OTHER)",
}
HOME_OWNERSHIP_FORM_LABELS = {
    "OWN": "Sở hữu nhà",
    "MORTGAGE": "Đang trả thế chấp",
    "RENT": "Thuê nhà",
}
LOGISTIC_PARAMETERS = {"max_iter": 1000, "solver": "lbfgs", "C": 1.0, "random_state": 42}


class SanitizeSixInput(BaseEstimator, TransformerMixin):
    """Chuẩn hóa numeric invalid trước imputation, giữ nguyên category đã xác nhận."""

    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> "SanitizeSixInput":
        self._validate(X)
        self.feature_names_in_ = np.asarray(DEMO_6_FEATURES, dtype=object)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        self._validate(X)
        result = X.loc[:, list(DEMO_6_FEATURES)].copy()
        for column in DEMO_6_FEATURES[:-1]:
            result[column] = pd.to_numeric(result[column], errors="coerce")
        result.loc[result["annual_inc"] <= 0, "annual_inc"] = np.nan
        result.loc[result["dti"] < 0, "dti"] = np.nan
        result["home_ownership"] = result["home_ownership"].astype(object)
        return result

    @staticmethod
    def _validate(X: pd.DataFrame) -> None:
        if not isinstance(X, pd.DataFrame) or tuple(X.columns) != DEMO_6_FEATURES:
            raise ValueError(f"Input pipeline phải đúng schema sáu field: {list(DEMO_6_FEATURES)}.")


SanitizeSixInput.__module__ = "src.models.demo_6input"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Manifest phải là JSON object: {path}.")
    return value


def _atomic_save(path: Path, writer: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.stem}-", suffix=path.suffix,
                                     delete=False) as stream:
        temporary = Path(stream.name)
    try:
        writer(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_split(path: Path, split_name: str) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["loan_id", "target", "split"])
    if (frame.isna().any().any() or not frame.loan_id.is_unique
            or not frame.target.isin([0, 1]).all() or not frame.split.eq(split_name).all()):
        raise ValueError(f"Partition {split_name} không đạt ID/target/split contract.")
    return frame.reset_index(drop=True)


def _read_rows(partition: pd.DataFrame) -> pd.DataFrame:
    columns = ["loan_id", "target", *DEMO_6_FEATURES, "fico_range_low", "fico_range_high"]
    parquet = pq.ParquetFile(CANONICAL_DATASET_PATH)
    missing = sorted(set(columns) - set(parquet.schema_arrow.names))
    if missing:
        raise ValueError(f"Canonical dataset thiếu input: {missing}.")
    wanted = set(partition.loan_id.tolist())
    pieces: list[pd.DataFrame] = []
    found: set[Any] = set()
    for group_id in range(parquet.num_row_groups):
        group = parquet.read_row_group(group_id, columns=columns).to_pandas()
        match = group.loc[group.loan_id.isin(wanted)].copy()
        if not match.empty:
            pieces.append(match)
            found.update(match.loan_id.tolist())
    if found != wanted:
        raise ValueError(f"Canonical thiếu {len(wanted - found)} ID của partition.")
    rows = pd.concat(pieces, ignore_index=True)
    if rows.loan_id.isna().any() or not rows.loan_id.is_unique or len(rows) != len(partition):
        raise ValueError("Canonical partition không còn một dòng trên mỗi loan_id.")
    rows = rows.set_index("loan_id").loc[partition.loan_id.tolist()].reset_index()
    if not rows.target.astype(int).equals(partition.target.astype(int)):
        raise ValueError("Canonical target lệch với frozen split IDs.")
    expected_fico = (rows.fico_range_low + rows.fico_range_high) / 2
    if not np.allclose(
        rows.fico_avg.to_numpy(dtype=float), expected_fico.to_numpy(dtype=float), rtol=0, atol=0,
    ):
        raise ValueError("fico_avg không khớp nguồn canonical.")
    return rows


def _protected_hashes() -> dict[str, str]:
    paths = (
        MODELING_DIR / "xgboost_full_refit.joblib",
        ML_LC_12_MANIFEST_PATH,
        XGBOOST_5INPUT_DEMO_PATH,
        XGBOOST_5INPUT_DEMO_MANIFEST_PATH,
        LOGISTIC_5INPUT_DEMO_PATH,
        LOGISTIC_5INPUT_DEMO_MANIFEST_PATH,
    )
    return {path.name: _sha256(path) for path in paths}


def build_xgboost_six_pipeline(
    frame: pd.DataFrame, *, model_parameters: Mapping[str, Any] = XGBOOST_PARAMETERS,
) -> Pipeline:
    """Tạo pipeline candidate XGBoost; numeric/OHE chỉ fit trong pipeline train."""
    from xgboost import XGBClassifier

    return Pipeline([
        ("sanitize", SanitizeSixInput()),
        ("normalize_missing", NormalizePandasMissing()),
        ("preprocess", build_xgboost_preprocessor(frame, DEMO_6_FEATURES)),
        ("model", XGBClassifier(**dict(model_parameters))),
    ])


def build_logistic_six_pipeline(
    frame: pd.DataFrame, *, model_parameters: Mapping[str, Any] = LOGISTIC_PARAMETERS,
) -> Pipeline:
    """Tạo Logistic pipeline có imputer, scaler và OHE fit trên train."""
    return Pipeline([
        ("sanitize", SanitizeSixInput()),
        ("normalize_missing", NormalizePandasMissing()),
        ("preprocess", build_preprocessor(frame, DEMO_6_FEATURES)),
        ("model", LogisticRegression(**dict(model_parameters))),
    ])


def train_six_input_candidates() -> dict[str, Any]:
    """Fit hai candidate trên train và tính metrics validation; tuyệt đối không đọc test."""
    outputs = (
        XGBOOST_6INPUT_DEMO_PATH, XGBOOST_6INPUT_DEMO_MANIFEST_PATH,
        XGBOOST_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
        LOGISTIC_6INPUT_DEMO_PATH, LOGISTIC_6INPUT_DEMO_MANIFEST_PATH,
        LOGISTIC_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
    )
    if any(path.exists() for path in outputs):
        raise FileExistsError("6-input candidate/output đã tồn tại; không ghi đè hoặc train lại.")

    data_manifest = _json(DATASET_MANIFEST_PATH)
    split_manifest = _json(MODELING_DIR / "split_manifest.json")
    refit_manifest = _json(ML_LC_12_MANIFEST_PATH)
    xgb5 = _json(XGBOOST_5INPUT_DEMO_MANIFEST_PATH)
    lr5 = _json(LOGISTIC_5INPUT_DEMO_MANIFEST_PATH)
    dictionary = pd.read_csv(DATA_DICTIONARY_PATH).set_index("column_name")
    if (data_manifest.get("run_status") != "PASS" or data_manifest.get("quality_status") != "PASS"
            or data_manifest.get("leakage_gate") != "PASS"
            or split_manifest.get("stage_status") != "PASS"
            or split_manifest.get("coverage_status") != "PASS"
            or refit_manifest.get("status") != "PASS"):
        raise ValueError("Canonical handoff, split hoặc ML-LC-12 gate chưa PASS.")
    if refit_manifest.get("carried_forward_threshold") != ML_LC_10_LOCKED_THRESHOLD:
        raise ValueError("Threshold candidate khác threshold đã khóa.")
    if not set(DEMO_6_FEATURES).issubset(dictionary.index):
        raise ValueError("Data dictionary thiếu một trong sáu input.")
    selected = dictionary.loc[list(DEMO_6_FEATURES)]
    if (not selected.policy_class.isin(["APPLICATION_TIME", "CREDIT_SNAPSHOT"]).all()
            or not selected.model_eligible_default.astype(str).str.lower().eq("true").all()):
        raise ValueError("Có input sáu biến không qua model-eligibility policy.")
    if any(item.get("status") != "PASS" or item.get("features") != list(DEMO_6_FEATURES[:-1])
           for item in (xgb5, lr5)):
        raise ValueError("Baseline 5-input manifests không khớp cấu hình so sánh.")

    protected_before = _protected_hashes()
    canonical_hash = _sha256(CANONICAL_DATASET_PATH)
    if (canonical_hash != refit_manifest.get("canonical_dataset_sha256")
            or canonical_hash != xgb5.get("canonical_dataset_sha256")
            or canonical_hash != lr5.get("canonical_dataset_sha256")):
        raise ValueError("Candidate input dataset không khớp canonical đã khóa.")
    train_ids = _read_split(MODELING_DIR / "train_ids.parquet", "train")
    valid_ids = _read_split(MODELING_DIR / "validation_ids.parquet", "validation")
    if set(train_ids.loan_id).intersection(valid_ids.loan_id):
        raise ValueError("Train và validation bị overlap.")
    split_hashes = {
        "train": _sha256(MODELING_DIR / "train_ids.parquet"),
        "validation": _sha256(MODELING_DIR / "validation_ids.parquet"),
    }
    if any(item.get("split_artifact_sha256", {}).get(name) != digest
           for item in (xgb5, lr5) for name, digest in split_hashes.items()):
        raise ValueError("Train/validation IDs khác split của baseline 5-input.")

    train = _read_rows(train_ids)
    validation = _read_rows(valid_ids)
    train_x, train_y = train.loc[:, list(DEMO_6_FEATURES)], train.target.astype(np.int8)
    valid_x, valid_y = validation.loc[:, list(DEMO_6_FEATURES)], validation.target.astype(np.int8)
    categories = sorted(train_x.home_ownership.dropna().astype(str).unique().tolist())
    if not categories or not set(valid_x.home_ownership.dropna().astype(str).unique()).issubset(categories):
        raise ValueError("Validation có home_ownership category chưa xuất hiện ở train.")
    category_counts = Counter(train_x.home_ownership.fillna("<MISSING>").astype(str))
    numeric_bounds = {
        field: {"min": float(pd.to_numeric(train_x[field], errors="coerce").min()),
                "max": float(pd.to_numeric(train_x[field], errors="coerce").max())}
        for field in DEMO_6_FEATURES[:-1]
    }

    outputs_by_model: dict[str, Any] = {}
    definitions = (
        ("xgboost", build_xgboost_six_pipeline, XGBOOST_6INPUT_DEMO_PATH,
         XGBOOST_6INPUT_DEMO_MANIFEST_PATH, XGBOOST_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
         XGBOOST_PARAMETERS),
        ("logistic", build_logistic_six_pipeline, LOGISTIC_6INPUT_DEMO_PATH,
         LOGISTIC_6INPUT_DEMO_MANIFEST_PATH, LOGISTIC_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
         LOGISTIC_PARAMETERS),
    )
    for name, builder, model_path, manifest_path, predictions_path, parameters in definitions:
        pipeline = builder(train_x)
        pipeline.fit(train_x, train_y)
        probabilities = validate_probability_of_default(pipeline.predict_proba(valid_x)[:, 1])
        metrics = _metrics(valid_y, probabilities, ML_LC_10_LOCKED_THRESHOLD)
        transformed = pipeline.named_steps["preprocess"].transform(
            pipeline.named_steps["normalize_missing"].transform(
                pipeline.named_steps["sanitize"].transform(train_x.head(1))
            )
        )
        names = pipeline.named_steps["preprocess"].get_feature_names_out().tolist()
        if transformed.shape[1] != len(names) or not np.isfinite(probabilities).all():
            raise ValueError(f"Preprocess {name} tạo schema/PD không hợp lệ.")
        _atomic_save(model_path, lambda temp, fitted=pipeline: joblib.dump(fitted, temp))
        valid_predictions = pd.DataFrame({
            "loan_id": valid_ids.loan_id.to_numpy(), "target": valid_y.to_numpy(),
            "predicted_pd": probabilities,
            "predicted_class": (probabilities >= ML_LC_10_LOCKED_THRESHOLD).astype(np.int8),
        })
        _atomic_save(predictions_path, lambda temp, frame=valid_predictions: frame.to_parquet(temp, index=False))
        manifest = {
            "stage": f"{name}-6input-demo-validation-candidate", "status": "PASS",
            "model_role": "secondary_ui_demo_candidate_only",
            "primary_model": "xgboost_full_refit_ml-lc-12",
            "features": list(DEMO_6_FEATURES), "feature_count": 6,
            "transformed_feature_count": len(names), "transformed_feature_names": names,
            "dataset_id": split_manifest["dataset_id"],
            "canonical_dataset_sha256": canonical_hash, "split_artifact_sha256": split_hashes,
            "home_ownership_categories_from_train": categories,
            "home_ownership_train_counts": dict(category_counts),
            "numeric_input_bounds_from_train": numeric_bounds,
            "preprocessing_fit_partition": "train only",
            "preprocessing": "train-fit median numeric imputation + standard scaling for Logistic; train-fit categorical most-frequent imputation + OneHotEncoder(handle_unknown=ignore)",
            "model_parameters": parameters,
            "threshold": ML_LC_10_LOCKED_THRESHOLD,
            "validation_rows": len(validation), "train_rows": len(train),
            "validation_metrics": metrics,
            "validation_prediction_artifact": str(predictions_path.resolve()),
            "validation_prediction_sha256": _sha256(predictions_path),
            "model_artifact": str(model_path.resolve()), "model_sha256": _sha256(model_path),
            "frozen_test_accessed": False, "frozen_test_metrics": None,
            "frozen_test_status": "NOT_EVALUATED_BY_USER_SELECTED_VALIDATION_ONLY_PROTOCOL",
            "protected_artifact_hashes_before": protected_before,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        _atomic_save(manifest_path, lambda temp, payload=manifest: temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
        ))
        outputs_by_model[name] = manifest

    if _protected_hashes() != protected_before:
        raise RuntimeError("Primary/5-input artifacts changed during candidate training.")
    return outputs_by_model


def validate_six_input(values: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate exact six form fields, including category membership observed in train."""
    if set(values) != set(VISIBLE_INPUTS):
        raise ValueError("Cần nhập đủ sáu thông tin khoản vay.")
    categories = manifest.get("home_ownership_categories_from_train", [])
    category = values["home_ownership"]
    if not isinstance(category, str) or category not in categories:
        raise ValueError("Tình trạng nhà ở không thuộc category đã được model hỗ trợ.")
    bounds = manifest["numeric_input_bounds_from_train"]
    result: dict[str, Any] = {"home_ownership": category}
    for visible, field in (("loan_amnt", "loan_amnt"), ("annual_inc", "annual_inc"),
                           ("dti", "dti"), ("term_months", "term_months"),
                           ("fico_score", "fico_avg")):
        raw = values[visible]
        if isinstance(raw, bool) or raw is None or isinstance(raw, str):
            raise ValueError(f"{DISPLAY_FEATURES[field]} cần có giá trị số hợp lệ.")
        try:
            number = float(raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{DISPLAY_FEATURES[field]} cần có giá trị số hợp lệ.") from exc
        if not math.isfinite(number):
            raise ValueError(f"{DISPLAY_FEATURES[field]} cần là số hữu hạn.")
        if field == "term_months":
            if number not in (36.0, 60.0):
                raise ValueError("Kỳ hạn chỉ hỗ trợ 36 hoặc 60 tháng.")
            result[field] = int(number)
            continue
        limits = bounds[field]
        if not limits["min"] <= number <= limits["max"]:
            raise ValueError(f"{DISPLAY_FEATURES[field]} phải từ {limits['min']:g} đến {limits['max']:g}.")
        if field == "annual_inc" and number <= 0:
            raise ValueError("Thu nhập năm phải lớn hơn 0.")
        if field == "dti" and number < 0:
            raise ValueError("DTI không được âm.")
        result[field] = number
    return result


def _group_transformed_features(names: list[str], contributions: np.ndarray) -> dict[str, float]:
    """Cộng one-hot contributions về sáu input gốc; dừng nếu schema không ánh xạ đủ."""
    grouped = {field: 0.0 for field in DEMO_6_FEATURES}
    if len(names) != len(contributions):
        raise ValueError("SHAP/coefficient length không khớp transformed feature names.")
    for name, value in zip(names, contributions, strict=True):
        transformed_name = str(name).split("__", 1)[-1]
        source = next((field for field in DEMO_6_FEATURES
                       if transformed_name == field or transformed_name.startswith(field + "_")), None)
        if source is None:
            raise ValueError(f"Không truy được transformed feature về input gốc: {name}.")
        grouped[source] += float(value)
    return grouped


def predict_six_using_model(
    pipeline: Pipeline, values: Mapping[str, Any], manifest: Mapping[str, Any], model_key: str,
) -> dict[str, Any]:
    """Dự đoán bằng candidate 6-input và giải thích sáu input thực tế."""
    checked = validate_six_input(values, manifest)
    frame = pd.DataFrame([{feature: checked[feature] for feature in DEMO_6_FEATURES}],
                         columns=list(DEMO_6_FEATURES))
    pd_value = float(validate_probability_of_default(pipeline.predict_proba(frame)[:, 1])[0])
    transformed = pipeline.named_steps["preprocess"].transform(
        pipeline.named_steps["normalize_missing"].transform(
            pipeline.named_steps["sanitize"].transform(frame)
        )
    )
    names = pipeline.named_steps["preprocess"].get_feature_names_out().tolist()
    model = pipeline.named_steps["model"]
    if model_key == "xgboost":
        import shap
        explainer = shap.TreeExplainer(model, model_output="raw")
        values_array = explainer.shap_values(transformed, check_additivity=False)
        if isinstance(values_array, list):
            if len(values_array) != 1:
                raise ValueError("SHAP returned unexpected outputs.")
            values_array = values_array[0]
        contributions = np.asarray(values_array, dtype=float).reshape(-1)
        margin = float(np.asarray(model.predict(transformed, output_margin=True)).reshape(-1)[0])
        base = float(np.asarray(explainer.expected_value).reshape(-1)[0])
        output_space = "raw margin/log-odds"
        method = "TreeSHAP aggregated from one-hot to original input"
    elif model_key == "logistic":
        dense = transformed.toarray().reshape(-1) if hasattr(transformed, "toarray") else np.asarray(transformed).reshape(-1)
        contributions = dense * np.asarray(model.coef_[0], dtype=float)
        margin = float(np.asarray(model.decision_function(transformed)).reshape(-1)[0])
        base = float(model.intercept_[0])
        output_space = "log-odds"
        method = "signed coefficient × transformed input, aggregated by original input"
    else:
        raise ValueError("Model key không hợp lệ.")
    if (len(contributions) != len(names) or not np.isfinite(contributions).all()
            or abs(base + float(contributions.sum()) - margin) > 1e-3):
        raise ValueError("Local explanation không đạt schema/finite/additivity check.")
    grouped = _group_transformed_features(names, contributions)
    rows = [{
        "feature": field, "label": DISPLAY_FEATURES[field],
        "value": checked[field], "shap_value": grouped[field],
    } for field in DEMO_6_FEATURES]
    rows.sort(key=lambda row: abs(row["shap_value"]), reverse=True)
    amount = float(checked["loan_amnt"])
    el = {f"expected_loss_lgd_{int(lgd * 100)}": float(
        calculate_expected_loss([pd_value], lgd, [amount])[0]
    ) for lgd in LGD_OPTIONS}
    return {
        "predicted_pd": pd_value, "predicted_class": int(pd_value >= ML_LC_10_LOCKED_THRESHOLD),
        "threshold": ML_LC_10_LOCKED_THRESHOLD,
        "risk_score": float(probability_to_risk_score([pd_value])[0]),
        "project_credit_score": int(probability_to_project_credit_score([pd_value])[0]),
        "risk_tier": str(assign_pd_risk_tier([pd_value], decision_threshold=ML_LC_10_LOCKED_THRESHOLD)[0]),
        "ead_proxy": amount, "expected_loss": el["expected_loss_lgd_45"], **el,
        "inputs": checked, "shap": rows, "shap_output_space": output_space,
        "explanation_method": method,
    }


def _load_model(model_key: str) -> tuple[Pipeline, dict[str, Any]]:
    paths = {
        "xgboost": (XGBOOST_6INPUT_DEMO_PATH, XGBOOST_6INPUT_DEMO_MANIFEST_PATH),
        "logistic": (LOGISTIC_6INPUT_DEMO_PATH, LOGISTIC_6INPUT_DEMO_MANIFEST_PATH),
    }
    if model_key not in paths:
        raise ValueError("Model key không hợp lệ.")
    model_path, manifest_path = paths[model_key]
    if not model_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("Candidate 6-input chưa được huấn luyện.")
    manifest = _json(manifest_path)
    if (manifest.get("status") != "PASS" or manifest.get("features") != list(DEMO_6_FEATURES)
            or manifest.get("frozen_test_accessed") is not False
            or manifest.get("model_sha256") != _sha256(model_path)):
        raise ValueError("Artifact/manifest 6-input không khớp.")
    pipeline = joblib.load(model_path)
    if (not isinstance(pipeline, Pipeline)
            or tuple(pipeline.named_steps["normalize_missing"].feature_names_in_) != DEMO_6_FEATURES):
        raise ValueError("Loaded pipeline không khớp six-input schema.")
    return pipeline, manifest


def get_six_demo(model_key: str) -> tuple[Pipeline, dict[str, Any]]:
    """Nạp model demo theo artifact key."""
    return _load_model(model_key)


def predict_six_demo(values: Mapping[str, Any], model_key: str) -> dict[str, Any]:
    """Chạy candidate 6-input đã lưu theo model selector."""
    pipeline, manifest = get_six_demo(model_key)
    return predict_six_using_model(pipeline, values, manifest, model_key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", action="store_true", help="Fit train, đánh giá validation; không mở test.")
    args = parser.parse_args()
    if not args.train:
        parser.error("Dùng --train để fit validation candidates một lần.")
    results = train_six_input_candidates()
    print(json.dumps({name: value["validation_metrics"] for name, value in results.items()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.modules.setdefault("src.models.demo_6input", sys.modules[__name__])
    raise SystemExit(main())
