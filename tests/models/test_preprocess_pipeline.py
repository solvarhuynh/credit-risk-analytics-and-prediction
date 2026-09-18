"""Tests cho src.models.preprocess_pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer

from src.models.preprocess_pipeline import (
    DEFAULT_FORBIDDEN_FEATURE_COLUMNS,
    build_preprocessor,
    validate_modeling_columns,
)


def test_build_preprocessor_is_not_fitted_immediately() -> None:
    """Preprocessor trả về là ColumnTransformer chưa được fit."""
    preprocessor = build_preprocessor(
        numeric_features=["age", "income"],
        categorical_features=["education"],
    )
    assert isinstance(preprocessor, ColumnTransformer)
    # Chưa fit thì không có attribute transformers_ kết thúc bằng underscore
    assert not hasattr(preprocessor, "transformers_")


def test_numeric_and_categorical_transformation_works() -> None:
    """Preprocessor fit_transform thành công trên in-memory DataFrame."""
    df = pd.DataFrame(
        {
            "age": [25.0, 40.0, 35.0],
            "income": [50000.0, 80000.0, 65000.0],
            "education": ["Secondary", "Higher", "Secondary"],
        }
    )
    preprocessor = build_preprocessor(
        numeric_features=["age", "income"],
        categorical_features=["education"],
    )
    transformed = preprocessor.fit_transform(df)
    assert transformed.ndim == 2
    assert transformed.shape[0] == 3
    # 2 numeric features + 2 distinct categories (Higher, Secondary)
    assert transformed.shape[1] == 4


def test_numeric_missing_imputed_with_median() -> None:
    """Missing value ở cột numeric được imputer xử lý mà không crash."""
    df_train = pd.DataFrame(
        {
            "age": [20.0, np.nan, 40.0],
            "education": ["A", "B", "A"],
        }
    )
    preprocessor = build_preprocessor(
        numeric_features=["age"],
        categorical_features=["education"],
        scale_numeric=False,
    )
    transformed = preprocessor.fit_transform(df_train)
    assert not np.isnan(transformed).any()
    # Median của [20, 40] là 30.0; giá trị NaN ở dòng 1 phải được thay bằng 30.0
    assert transformed[1, 0] == 30.0


def test_categorical_missing_imputed_with_constant() -> None:
    """Missing value ở cột categorical được thay bằng __MISSING__ và encode."""
    df_train = pd.DataFrame(
        {
            "age": [30.0, 40.0],
            "education": [None, "Higher"],
        }
    )
    preprocessor = build_preprocessor(
        numeric_features=["age"],
        categorical_features=["education"],
        scale_numeric=False,
    )
    transformed = preprocessor.fit_transform(df_train)
    assert not np.isnan(transformed).any()
    assert transformed.shape[0] == 2


def test_unknown_category_does_not_crash() -> None:
    """Category mới xuất hiện khi transform được encode toàn 0 (handle_unknown='ignore')."""
    df_train = pd.DataFrame(
        {
            "age": [30.0, 40.0],
            "education": ["Secondary", "Higher"],
        }
    )
    df_test = pd.DataFrame(
        {
            "age": [50.0],
            "education": ["Academic degree"],  # Category mới chưa gặp lúc fit
        }
    )
    preprocessor = build_preprocessor(
        numeric_features=["age"],
        categorical_features=["education"],
        scale_numeric=False,
    )
    preprocessor.fit(df_train)
    transformed_test = preprocessor.transform(df_test)
    assert transformed_test.shape == (1, 3)
    # OneHot columns cho education phải toàn 0 khi gặp unseen category
    assert np.all(transformed_test[0, 1:] == 0.0)


def test_target_in_feature_list_rejected() -> None:
    """Cột TARGET trong feature list bị chặn bởi validation."""
    with pytest.raises(ValueError, match="bị cấm"):
        validate_modeling_columns(
            numeric_features=["age", "TARGET"],
            categorical_features=["education"],
        )


def test_forbidden_modeling_outputs_rejected() -> None:
    """Các cột định danh và hậu xử lý mô hình bị chặn hoàn toàn."""
    for forbidden_col in DEFAULT_FORBIDDEN_FEATURE_COLUMNS:
        with pytest.raises(ValueError, match="bị cấm"):
            validate_modeling_columns(
                numeric_features=[forbidden_col],
                categorical_features=["education"],
            )


def test_numeric_categorical_overlap_rejected() -> None:
    """Một cột vừa khai báo numeric vừa categorical phải raise ValueError."""
    with pytest.raises(ValueError, match="không thể vừa numeric vừa categorical"):
        validate_modeling_columns(
            numeric_features=["age", "income"],
            categorical_features=["income", "education"],
        )


def test_missing_requested_column_in_available_columns_rejected() -> None:
    """Feature yêu cầu không có trong available_columns phải raise ValueError."""
    with pytest.raises(ValueError, match="không có trong schema đầu vào"):
        validate_modeling_columns(
            numeric_features=["age", "non_existent_feature"],
            categorical_features=["education"],
            available_columns=["age", "education"],
        )


def test_duplicate_feature_within_same_role_rejected() -> None:
    """Cột bị lặp lại trong cùng một role phải raise ValueError."""
    with pytest.raises(ValueError, match="chứa feature trùng"):
        validate_modeling_columns(
            numeric_features=["age", "age"],
            categorical_features=["education"],
        )


def test_scale_numeric_flag_works() -> None:
    """Tùy chọn scale_numeric=True/False thêm hoặc bỏ StandardScaler."""
    prep_scaled = build_preprocessor(
        numeric_features=["age"],
        categorical_features=["education"],
        scale_numeric=True,
    )
    prep_unscaled = build_preprocessor(
        numeric_features=["age"],
        categorical_features=["education"],
        scale_numeric=False,
    )

    numeric_steps_scaled = [
        name for name, _ in prep_scaled.named_transformers["numeric"].steps
    ]
    numeric_steps_unscaled = [
        name for name, _ in prep_unscaled.named_transformers["numeric"].steps
    ]

    assert "scaler" in numeric_steps_scaled
    assert "scaler" not in numeric_steps_unscaled

