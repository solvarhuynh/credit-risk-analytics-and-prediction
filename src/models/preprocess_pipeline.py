"""Tiền xử lý sklearn cho danh sách feature đã qua leakage gate."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.data.column_policy import assert_no_forbidden_features


class NormalizePandasMissing(BaseEstimator, TransformerMixin):
    """Chuẩn hóa ``pd.NA`` để sklearn imputers nhận missing ổn định."""

    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> "NormalizePandasMissing":
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Model input phải là pandas DataFrame.")
        self.feature_names_in_ = X.columns.to_numpy()
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Model input phải là pandas DataFrame.")
        result = X.copy()
        for column in result.columns:
            series = result[column]
            if pd.api.types.is_numeric_dtype(series):
                result[column] = pd.to_numeric(series, errors="coerce").astype(float)
            elif not pd.api.types.is_datetime64_any_dtype(series):
                result[column] = series.astype(object).where(series.notna(), np.nan)
        return result


def validate_modeling_columns(frame: pd.DataFrame, features: Sequence[str]) -> None:
    if not features:
        raise ValueError("Danh sách model feature đang rỗng.")
    missing = sorted(set(features) - set(frame.columns))
    if missing:
        raise ValueError(f"Thiếu model feature: {missing}")
    assert_no_forbidden_features(features)


def build_preprocessor(frame: pd.DataFrame, features: Sequence[str]) -> ColumnTransformer:
    validate_modeling_columns(frame, features)
    date_like = [
        column for column in features
        if pd.api.types.is_datetime64_any_dtype(frame[column])
    ]
    if date_like:
        raise ValueError(
            "Date-like feature phải được chuyển thành feature số deterministic "
            f"trước preprocessing Logistic: {date_like}"
        )
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
    ], remainder="drop", sparse_threshold=1.0)
