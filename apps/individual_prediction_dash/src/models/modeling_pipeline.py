"""Khung TV1 sau reset Lending Club; chưa chứa metric hay model đã huấn luyện."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.config import CANONICAL_DATASET_PATH, DATA_DICTIONARY_PATH, DATASET_MANIFEST_PATH
from src.data.column_policy import approved_model_features, classify_column, unknown_columns
from src.models.preprocess_pipeline import NormalizePandasMissing, build_preprocessor, build_xgboost_preprocessor


class GateError(RuntimeError):
    """Model input không đạt contract TV2 → TV1."""


@dataclass(frozen=True)
class FeatureSchema:
    approved_features: tuple[str, ...]
    excluded_features: tuple[str, ...]


@dataclass(frozen=True)
class BaselineFeatureSelection:
    """Danh sách feature thực sự đưa vào baseline và audit loại trừ."""

    approved_features: tuple[str, ...]
    baseline_features: tuple[str, ...]
    excluded_safe_features: tuple[str, ...]
    exclusion_reasons: dict[str, str]
    audit: pd.DataFrame


DATE_LIKE_FEATURE_NAMES = frozenset({
    "issue_d",
    "earliest_cr_line",
    "sec_app_earliest_cr_line",
})
HIGH_CARDINALITY_CATEGORICAL_THRESHOLD = 50


def load_canonical_input(
    dataset_path: Path = CANONICAL_DATASET_PATH,
    dictionary_path: Path = DATA_DICTIONARY_PATH,
    manifest_path: Path = DATASET_MANIFEST_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    missing = [path for path in (dataset_path, dictionary_path, manifest_path) if not path.is_file()]
    if missing:
        raise GateError(f"WAITING FOR TV2 LENDING CLUB CANONICAL HANDOFF: {missing}")
    dataset = pd.read_parquet(dataset_path)
    dictionary = pd.read_csv(dictionary_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return dataset, dictionary, manifest


def build_feature_schema(dataset: pd.DataFrame, dictionary: pd.DataFrame) -> FeatureSchema:
    required_dictionary_columns = {"column_name", "policy_class", "model_eligible_default"}
    if not required_dictionary_columns.issubset(dictionary.columns):
        raise GateError("Data dictionary thiếu metadata leakage bắt buộc.")
    uncovered = sorted(set(dataset.columns) - set(dictionary["column_name"]))
    if uncovered:
        raise GateError(f"Dictionary chưa bao phủ cột: {uncovered}")
    unknown = unknown_columns(dataset.columns)
    if unknown:
        raise GateError(f"Cột UNKNOWN_REVIEW_REQUIRED chặn model handoff: {unknown}")
    approved = tuple(approved_model_features(dataset.columns))
    if not approved:
        raise GateError("Không có feature APPLICATION_TIME/CREDIT_SNAPSHOT được duyệt.")
    excluded = tuple(column for column in dataset.columns if column not in approved)
    return FeatureSchema(approved_features=approved, excluded_features=excluded)


def build_baseline_feature_selection(
    dataset: pd.DataFrame,
    schema: FeatureSchema,
    *,
    audit_frame: pd.DataFrame | None = None,
) -> BaselineFeatureSelection:
    """Audit và chọn feature an toàn cho Logistic baseline.

    Các cột ngày raw vẫn model-safe theo policy nhưng không được one-hot trực
    tiếp. Canonical đã có feature số deterministic (`issue_year`,
    `issue_month`, `credit_history_months`), nên raw date columns được giữ
    ngoài baseline và ghi rõ lý do trong audit.
    """

    frame = dataset if audit_frame is None else audit_frame
    missing = sorted(set(schema.approved_features) - set(dataset.columns))
    if missing:
        raise GateError(f"Approved feature thiếu trong canonical dataset: {missing}")
    missing_audit = sorted(set(schema.approved_features) - set(frame.columns))
    if missing_audit:
        raise GateError(f"Approved feature thiếu trong audit frame: {missing_audit}")

    rows: list[dict[str, Any]] = []
    baseline_features: list[str] = []
    excluded_safe_features: list[str] = []
    exclusion_reasons: dict[str, str] = {}
    for feature in schema.approved_features:
        series = frame[feature]
        dtype = str(series.dtype)
        is_datetime_like = (
            pd.api.types.is_datetime64_any_dtype(series)
            or feature in DATE_LIKE_FEATURE_NAMES
        )
        is_numeric = bool(pd.api.types.is_numeric_dtype(series)) and not is_datetime_like
        is_categorical = not is_numeric and not is_datetime_like
        missing_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))
        cardinality_concern = bool(
            is_categorical and unique_count > HIGH_CARDINALITY_CATEGORICAL_THRESHOLD
        )
        if is_datetime_like:
            if feature == "issue_d":
                reason = (
                    "Raw issue date is not one-hot encoded; issue_year/issue_quarter/"
                    "issue_month are the deterministic application-time representation."
                )
            elif feature == "earliest_cr_line":
                reason = (
                    "Raw credit-history date is not one-hot encoded; credit_history_months "
                    "is the deterministic numeric representation."
                )
            else:
                reason = (
                    "Raw secondary-applicant date is not one-hot encoded because it is "
                    "date-like and sparsely observed; no post-loan information is added."
                )
            used_in_baseline = False
            intended_preprocessing = "excluded: use deterministic engineered date features"
            excluded_safe_features.append(feature)
            exclusion_reasons[feature] = reason
        else:
            used_in_baseline = True
            baseline_features.append(feature)
            intended_preprocessing = (
                "median imputation + StandardScaler"
                if is_numeric
                else "most_frequent imputation + OneHotEncoder(handle_unknown='ignore')"
            )
        rows.append({
            "feature_name": feature,
            "policy_class": str(classify_column(feature)),
            "pandas_dtype": dtype,
            "is_numeric": is_numeric,
            "is_categorical": is_categorical,
            "is_datetime_like": is_datetime_like,
            "missing_count": missing_count,
            "missing_rate": float(series.isna().mean()),
            "unique_count": unique_count,
            "cardinality_concern": cardinality_concern,
            "intended_preprocessing": intended_preprocessing,
            "used_in_baseline": used_in_baseline,
            "exclusion_reason": exclusion_reasons.get(feature, ""),
        })

    audit = pd.DataFrame(rows)
    return BaselineFeatureSelection(
        approved_features=tuple(schema.approved_features),
        baseline_features=tuple(baseline_features),
        excluded_safe_features=tuple(excluded_safe_features),
        exclusion_reasons=exclusion_reasons,
        audit=audit,
    )


def build_logistic_pipeline(
    dataset: pd.DataFrame,
    schema: FeatureSchema,
    *,
    feature_columns: Sequence[str] | None = None,
    class_weight: str | dict[str, float] | None = None,
    max_iter: int = 1000,
    solver: str = "lbfgs",
    penalty: str = "l2",
    random_state: int = 42,
) -> Pipeline:
    """Tạo Logistic Regression pipeline; chưa fit model.

    ``class_weight=None`` là baseline ML-LC-03. ML-LC-04 có thể gọi lại hàm
    với ``class_weight='balanced'`` mà không thay đổi preprocessing contract.
    """

    features = tuple(schema.approved_features if feature_columns is None else feature_columns)
    unknown = sorted(set(features) - set(schema.approved_features))
    if unknown:
        raise GateError(f"Baseline feature chưa được ML-LC-01 approve: {unknown}")
    if not features:
        raise GateError("Baseline feature list đang rỗng.")

    preprocessor = build_preprocessor(dataset, features)
    return Pipeline([
        ("normalize_missing", NormalizePandasMissing()),
        ("preprocess", preprocessor),
        ("model", LogisticRegression(
            max_iter=max_iter,
            class_weight=class_weight,
            random_state=random_state,
            solver=solver,
            penalty=penalty,
        )),
    ])


def optional_xgboost_available() -> bool:
    """XGBoost chỉ là so sánh tùy chọn, không thay Logistic Regression."""

    try:
        import xgboost  # noqa: F401
    except ImportError:
        return False
    return True


def build_xgboost_pipeline(
    dataset: pd.DataFrame,
    schema: FeatureSchema,
    *,
    feature_columns: Sequence[str],
    random_state: int = 42,
    n_estimators: int = 200,
    max_depth: int = 4,
    learning_rate: float = 0.05,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
) -> Pipeline:
    """Tạo một XGBoost candidate; dependency được nạp khi gọi hàm."""

    features = tuple(feature_columns)
    if not features or len(features) != len(set(features)):
        raise GateError("XGBoost feature list rỗng hoặc trùng cột.")
    unapproved = sorted(set(features) - set(schema.approved_features))
    if unapproved:
        raise GateError(f"XGBoost feature chưa được ML-LC-01 duyệt: {unapproved}")
    try:
        from xgboost import XGBClassifier
    except ImportError as exc:
        raise GateError("Thiếu optional dependency xgboost; cài requirements.txt trước khi chạy ML-LC-05.") from exc
    preprocessor = build_xgboost_preprocessor(dataset, features)
    return Pipeline([
        ("normalize_missing", NormalizePandasMissing()),
        ("preprocess", preprocessor),
        ("model", XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            random_state=random_state,
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            n_jobs=4,
        )),
    ])
