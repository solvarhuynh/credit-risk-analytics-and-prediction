"""Factory cho preprocessing của các modeling run.

Module này chỉ xây dựng transformer chưa được fit. Caller phải split dữ liệu trước
và chỉ gọi ``fit`` hoặc ``fit_transform`` trên training fold để tránh leakage.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


DEFAULT_FORBIDDEN_FEATURE_COLUMNS = frozenset(
    {
        "TARGET",
        "SK_ID_CURR",
        "PREDICTED_PD",
        "CREDIT_SCORE",
        "RISK_TIER",
        "EXPECTED_LOSS",
        "RECOMMENDATION",
        "DECISION_THRESHOLD",
        "MODEL_VERSION",
    }
)
"""Các cột nhãn, định danh và hậu xử lý không được dùng làm model feature."""


def validate_modeling_columns(
    numeric_features: Sequence[str],
    categorical_features: Sequence[str],
    *,
    available_columns: Collection[str] | None = None,
    additional_forbidden_feature_columns: Collection[str] = (),
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Kiểm tra danh sách feature trước khi tạo preprocessing pipeline.

    Args:
        numeric_features: Cột số do caller xác định rõ.
        categorical_features: Cột phân loại do caller xác định rõ.
        available_columns: Schema dữ liệu nếu cần kiểm tra feature bị thiếu.
        additional_forbidden_feature_columns: Cột cấm bổ sung theo modeling run.
            Các cột cấm mặc định luôn được giữ nguyên.

    Returns:
        Hai tuple feature numeric và categorical đã được xác thực.

    Raises:
        ValueError: Khi có tên cột trùng, overlap, cột bị cấm hoặc không có
            trong ``available_columns``.

    Note:
        Hàm chỉ kiểm tra metadata; không đọc dữ liệu và không fit transformer.
    """
    numeric = _normalise_feature_names(numeric_features, role="numeric_features")
    categorical = _normalise_feature_names(
        categorical_features,
        role="categorical_features",
    )

    overlap = sorted(set(numeric).intersection(categorical))
    if overlap:
        raise ValueError(
            "Feature không thể vừa numeric vừa categorical: " + ", ".join(overlap)
        )

    selected = set(numeric).union(categorical)
    forbidden = set(DEFAULT_FORBIDDEN_FEATURE_COLUMNS).union(
        additional_forbidden_feature_columns
    )
    prohibited = sorted(selected.intersection(forbidden))
    if prohibited:
        raise ValueError(
            "Feature list chứa nhãn, ID hoặc modeling output bị cấm: "
            + ", ".join(prohibited)
        )

    if available_columns is not None:
        missing = sorted(selected.difference(available_columns))
        if missing:
            raise ValueError(
                "Feature được yêu cầu không có trong schema đầu vào: "
                + ", ".join(missing)
            )

    return numeric, categorical


def build_preprocessor(
    numeric_features: Sequence[str],
    categorical_features: Sequence[str],
    *,
    scale_numeric: bool = True,
    available_columns: Collection[str] | None = None,
    numeric_imputation_strategy: str = "median",
) -> ColumnTransformer:
    """Tạo sklearn ``ColumnTransformer`` chưa fit cho một modeling run.

    ``scale_numeric=True`` phù hợp với Logistic Regression; tree model có thể đặt
    thành ``False``. Danh sách feature phải được caller quyết định từ data
    dictionary/snapshot của TV2; module không tự suy luận feature cuối cùng.

    Caller chỉ được fit object trả về trên training fold sau khi split. Không fit
    object này trên full dataset trong development hoặc final-test evaluation.
    """
    numeric, categorical = validate_modeling_columns(
        numeric_features,
        categorical_features,
        available_columns=available_columns,
    )

    numeric_steps: list[tuple[str, object]] = [
        ("imputer", SimpleImputer(strategy=numeric_imputation_strategy)),
    ]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))

    numeric_pipeline = Pipeline(steps=numeric_steps)
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="__MISSING__")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, list(numeric)),
            ("categorical", categorical_pipeline, list(categorical)),
        ],
        remainder="drop",
    )


def _normalise_feature_names(
    feature_names: Sequence[str],
    *,
    role: str,
) -> tuple[str, ...]:
    """Trả feature names dạng tuple và chặn tên rỗng/trùng trong cùng role."""
    names = tuple(feature_names)
    invalid = [name for name in names if not isinstance(name, str) or not name]
    if invalid:
        raise ValueError(f"{role} chỉ nhận tên cột là chuỗi không rỗng.")

    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"{role} chứa feature trùng: " + ", ".join(duplicates))

    return names
