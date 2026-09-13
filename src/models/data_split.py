"""Tiện ích chia dữ liệu labeled cho giai đoạn phát triển mô hình.

Module chỉ chia dữ liệu, không xây hoặc fit preprocessing và không train model.
Final production refit dùng toàn bộ labeled dataset chỉ được thực hiện sau khi
model configuration và frozen-test evaluation đã được khóa; vì vậy không dùng
hàm này cho final refit.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import Mapping

import pandas as pd
from sklearn.model_selection import train_test_split


@dataclass(frozen=True)
class ModelingPartition:
    """Một split chứa feature, label và ID audit đã được tách riêng."""

    X: pd.DataFrame
    y: pd.Series
    ids: pd.Series


@dataclass(frozen=True)
class SplitMetadata:
    """Metadata tái lập và phân phối nhãn của development split."""

    random_state: int
    test_size: float
    validation_size: float
    row_counts: Mapping[str, int]
    target_rates: Mapping[str, float]
    target_counts: Mapping[str, Mapping[int, int]]


@dataclass(frozen=True)
class DevelopmentSplitResult:
    """Kết quả Train/Validation/Test để dùng xuyên suốt một experiment."""

    train: ModelingPartition
    validation: ModelingPartition
    test: ModelingPartition
    metadata: SplitMetadata


def create_development_split(
    dataset: pd.DataFrame,
    *,
    random_state: int,
    test_size: float = 0.20,
    validation_size: float = 0.20,
    target_column: str = "TARGET",
    id_column: str = "SK_ID_CURR",
) -> DevelopmentSplitResult:
    """Tạo fixed stratified Train/Validation/Test split cho development phase.

    ``test_size`` và ``validation_size`` là tỷ lệ trên toàn bộ input. Test được
    tách trước; validation chỉ được tách từ development portion còn lại. Dùng
    cùng ``random_state`` và dataset snapshot cho tất cả candidate model của một
    experiment để giữ nguyên test population.

    Hàm trả ID riêng để audit nhưng đã loại ``target_column`` và ``id_column``
    khỏi ``X``. Caller chỉ fit preprocessing trên ``result.train.X``. Hàm này
    không dùng cho final production refit trên full labeled data.

    Raises:
        ValueError: Nếu schema/nhãn/ID không hợp lệ, tỷ lệ split không hợp lệ
            hoặc dữ liệu không đủ để stratify qua ba split.
    """
    _validate_dataset(
        dataset,
        target_column=target_column,
        id_column=id_column,
    )
    _validate_split_sizes(test_size=test_size, validation_size=validation_size)
    _validate_random_state(random_state)
    random_state = int(random_state)

    target = dataset[target_column]
    try:
        development_frame, test_frame = train_test_split(
            dataset,
            test_size=test_size,
            random_state=random_state,
            stratify=target,
        )
        validation_share_of_development = validation_size / (1 - test_size)
        train_frame, validation_frame = train_test_split(
            development_frame,
            test_size=validation_share_of_development,
            random_state=random_state,
            stratify=development_frame[target_column],
        )
    except ValueError as exc:
        raise ValueError(
            "Dataset không đủ samples cho stratified Train/Validation/Test với "
            "các tỷ lệ đã chọn. Tăng dữ liệu hoặc điều chỉnh test_size/"
            "validation_size."
        ) from exc

    result = DevelopmentSplitResult(
        train=_to_partition(train_frame, target_column=target_column, id_column=id_column),
        validation=_to_partition(
            validation_frame,
            target_column=target_column,
            id_column=id_column,
        ),
        test=_to_partition(test_frame, target_column=target_column, id_column=id_column),
        metadata=_build_metadata(
            train_frame,
            validation_frame,
            test_frame,
            target_column=target_column,
            random_state=random_state,
            test_size=test_size,
            validation_size=validation_size,
        ),
    )
    _validate_split_result(result, dataset[id_column])
    return result


def _validate_dataset(
    dataset: pd.DataFrame,
    *,
    target_column: str,
    id_column: str,
) -> None:
    """Kiểm tra schema và điều kiện tối thiểu để stratify nhãn nhị phân."""
    if not isinstance(dataset, pd.DataFrame):
        raise ValueError("dataset phải là pandas DataFrame.")
    if not dataset.columns.is_unique:
        raise ValueError("Dataset có tên cột trùng, không thể xác định schema an toàn.")

    missing_columns = [
        column
        for column in (target_column, id_column)
        if column not in dataset.columns
    ]
    if missing_columns:
        raise ValueError("Thiếu cột bắt buộc: " + ", ".join(missing_columns))

    target = dataset[target_column]
    if target.isna().any():
        raise ValueError(f"{target_column} không được chứa giá trị null.")
    target_values = set(target.unique())
    if not target_values.issubset({0, 1}) or len(target_values) != 2:
        raise ValueError(f"{target_column} phải chỉ chứa cả hai lớp 0 và 1.")

    ids = dataset[id_column]
    if ids.isna().any():
        raise ValueError(f"{id_column} không được chứa giá trị null.")
    if not ids.is_unique:
        raise ValueError(f"{id_column} phải unique để audit split.")

    if len(dataset.columns) <= 2:
        raise ValueError("Dataset phải có ít nhất một feature ngoài TARGET và SK_ID_CURR.")
    if target.value_counts().min() < 3:
        raise ValueError("Mỗi lớp TARGET cần tối thiểu ba samples cho ba split.")


def _validate_split_sizes(*, test_size: float, validation_size: float) -> None:
    """Đảm bảo ba split đều có phần dữ liệu dương."""
    if not 0 < test_size < 1:
        raise ValueError("test_size phải nằm trong khoảng (0, 1).")
    if not 0 < validation_size < 1:
        raise ValueError("validation_size phải nằm trong khoảng (0, 1).")
    if test_size + validation_size >= 1:
        raise ValueError("test_size + validation_size phải nhỏ hơn 1.")


def _validate_random_state(random_state: int) -> None:
    """Buộc caller truyền seed nguyên để split có thể tái lập."""
    if isinstance(random_state, bool) or not isinstance(random_state, Integral):
        raise ValueError("random_state phải là số nguyên tường minh, không được là None.")


def _to_partition(
    frame: pd.DataFrame,
    *,
    target_column: str,
    id_column: str,
) -> ModelingPartition:
    """Tách X, y và audit ID để ID không đi vào predictive features."""
    return ModelingPartition(
        X=frame.drop(columns=[target_column, id_column]).copy(),
        y=frame[target_column].copy(),
        ids=frame[id_column].copy(),
    )


def _build_metadata(
    train_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    *,
    target_column: str,
    random_state: int,
    test_size: float,
    validation_size: float,
) -> SplitMetadata:
    """Tạo metadata audit, không in console và không tính model metric."""
    frames = {
        "train": train_frame,
        "validation": validation_frame,
        "test": test_frame,
    }
    return SplitMetadata(
        random_state=random_state,
        test_size=test_size,
        validation_size=validation_size,
        row_counts={name: len(frame) for name, frame in frames.items()},
        target_rates={
            name: float(frame[target_column].mean()) for name, frame in frames.items()
        },
        target_counts={
            name: {
                0: int((frame[target_column] == 0).sum()),
                1: int((frame[target_column] == 1).sum()),
            }
            for name, frame in frames.items()
        },
    )


def _validate_split_result(
    result: DevelopmentSplitResult,
    input_ids: pd.Series,
) -> None:
    """Kiểm tra split không chồng ID và phủ đúng toàn bộ input."""
    split_ids = {
        "train": set(result.train.ids),
        "validation": set(result.validation.ids),
        "test": set(result.test.ids),
    }
    if (
        split_ids["train"].intersection(split_ids["validation"])
        or split_ids["train"].intersection(split_ids["test"])
        or split_ids["validation"].intersection(split_ids["test"])
    ):
        raise RuntimeError("Split result có SK_ID_CURR overlap giữa các partition.")

    combined_ids = set().union(*split_ids.values())
    if combined_ids != set(input_ids):
        raise RuntimeError("Split result không phủ đúng toàn bộ SK_ID_CURR đầu vào.")
