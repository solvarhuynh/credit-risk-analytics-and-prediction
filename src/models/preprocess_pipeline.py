"""Tiền xử lý sklearn cho danh sách feature đã qua leakage gate."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.data.column_policy import assert_no_forbidden_features


def validate_modeling_columns(frame: pd.DataFrame, features: Sequence[str]) -> None:
    if not features:
        raise ValueError("Danh sách model feature đang rỗng.")
    missing = sorted(set(features) - set(frame.columns))
    if missing:
        raise ValueError(f"Thiếu model feature: {missing}")
    assert_no_forbidden_features(features)


def build_preprocessor(frame: pd.DataFrame, features: Sequence[str]) -> ColumnTransformer:
    validate_modeling_columns(frame, features)
    numeric = [column for column in features if pd.api.types.is_numeric_dtype(frame[column])]
    categorical = [column for column in features if column not in numeric]
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("one_hot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
    ])
    return ColumnTransformer([
        ("numeric", numeric_pipeline, numeric),
        ("categorical", categorical_pipeline, categorical),
    ], remainder="drop")
