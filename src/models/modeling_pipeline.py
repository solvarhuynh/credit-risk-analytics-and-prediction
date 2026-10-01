"""Khung TV1 sau reset Lending Club; chưa chứa metric hay model đã huấn luyện."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.config import CANONICAL_DATASET_PATH, DATA_DICTIONARY_PATH, DATASET_MANIFEST_PATH
from src.data.column_policy import approved_model_features, unknown_columns
from src.models.preprocess_pipeline import build_preprocessor


class GateError(RuntimeError):
    """Model input không đạt contract TV2 → TV1."""


@dataclass(frozen=True)
class FeatureSchema:
    approved_features: tuple[str, ...]
    excluded_features: tuple[str, ...]


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


def build_logistic_pipeline(dataset: pd.DataFrame, schema: FeatureSchema) -> Pipeline:
    """Logistic Regression là baseline bắt buộc theo rubric."""

    preprocessor = build_preprocessor(dataset, schema.approved_features)
    return Pipeline([
        ("preprocess", preprocessor),
        ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
    ])


def optional_xgboost_available() -> bool:
    """XGBoost chỉ là so sánh tùy chọn, không thay Logistic Regression."""

    try:
        import xgboost  # noqa: F401
    except ImportError:
        return False
    return True
