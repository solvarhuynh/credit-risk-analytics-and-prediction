"""Chia train/validation/test xác định cho canonical Lending Club."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.model_selection import train_test_split

from src.config import ID_COLUMN, TARGET_COLUMN


@dataclass(frozen=True)
class ModelingPartition:
    X: pd.DataFrame
    y: pd.Series
    ids: pd.Series


@dataclass(frozen=True)
class DevelopmentSplitResult:
    train: ModelingPartition
    validation: ModelingPartition
    test: ModelingPartition
    random_state: int


def _validate(frame: pd.DataFrame, target_column: str, id_column: str) -> None:
    missing = {target_column, id_column} - set(frame.columns)
    if missing:
        raise ValueError(f"Thiếu cột bắt buộc: {sorted(missing)}")
    if frame[id_column].isna().any() or not frame[id_column].is_unique:
        raise ValueError(f"{id_column} phải non-null và unique.")
    if frame[target_column].isna().any() or set(frame[target_column].unique()) != {0, 1}:
        raise ValueError(f"{target_column} phải chứa đủ hai lớp 0/1 và không null.")


def _partition(frame: pd.DataFrame, target_column: str, id_column: str) -> ModelingPartition:
    return ModelingPartition(
        X=frame.drop(columns=[target_column, id_column]).copy(),
        y=frame[target_column].astype(int).copy(),
        ids=frame[id_column].copy(),
    )


def create_development_split(
    dataset: pd.DataFrame,
    *,
    target_column: str = TARGET_COLUMN,
    id_column: str = ID_COLUMN,
    test_size: float = 0.20,
    validation_size: float = 0.20,
    random_state: int = 42,
) -> DevelopmentSplitResult:
    _validate(dataset, target_column, id_column)
    if not 0 < test_size < 1 or not 0 < validation_size < 1 or test_size + validation_size >= 1:
        raise ValueError("Tỷ lệ validation/test không hợp lệ.")
    development, test = train_test_split(
        dataset, test_size=test_size, random_state=random_state,
        stratify=dataset[target_column],
    )
    relative_validation = validation_size / (1 - test_size)
    train, validation = train_test_split(
        development, test_size=relative_validation, random_state=random_state,
        stratify=development[target_column],
    )
    return DevelopmentSplitResult(
        train=_partition(train, target_column, id_column),
        validation=_partition(validation, target_column, id_column),
        test=_partition(test, target_column, id_column),
        random_state=random_state,
    )
