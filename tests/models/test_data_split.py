"""Tests cho src.models.data_split."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.data_split import create_development_split


@pytest.fixture
def sample_development_dataset() -> pd.DataFrame:
    """Fixture tạo tiny dataset tổng hợp có đủ hai lớp và ID duy nhất."""
    np.random.seed(42)
    n_samples = 100
    ids = [1000 + i for i in range(n_samples)]
    # Tỷ lệ target ~ 10% defaults (10 class 1, 90 class 0)
    target = [1] * 10 + [0] * 90
    feature_1 = np.random.randn(n_samples)
    feature_2 = np.random.rand(n_samples)

    return pd.DataFrame(
        {
            "SK_ID_CURR": ids,
            "TARGET": target,
            "feature_1": feature_1,
            "feature_2": feature_2,
        }
    )


def test_reproducibility_with_same_random_state(
    sample_development_dataset: pd.DataFrame,
) -> None:
    """Cùng random_state và input cho ra split hoàn toàn trùng khớp."""
    split_1 = create_development_split(
        sample_development_dataset,
        random_state=42,
        test_size=0.2,
        validation_size=0.2,
    )
    split_2 = create_development_split(
        sample_development_dataset,
        random_state=42,
        test_size=0.2,
        validation_size=0.2,
    )

    pd.testing.assert_series_equal(split_1.train.ids, split_2.train.ids)
    pd.testing.assert_series_equal(split_1.validation.ids, split_2.validation.ids)
    pd.testing.assert_series_equal(split_1.test.ids, split_2.test.ids)


def test_no_id_overlap_and_union_equals_input(
    sample_development_dataset: pd.DataFrame,
) -> None:
    """Train/validation/test không overlap SK_ID_CURR và union đúng bằng input."""
    result = create_development_split(
        sample_development_dataset,
        random_state=123,
        test_size=0.2,
        validation_size=0.2,
    )

    train_ids = set(result.train.ids)
    val_ids = set(result.validation.ids)
    test_ids = set(result.test.ids)

    # Không overlap
    assert len(train_ids.intersection(val_ids)) == 0
    assert len(train_ids.intersection(test_ids)) == 0
    assert len(val_ids.intersection(test_ids)) == 0

    # Union bằng đúng input population
    assert train_ids.union(val_ids).union(test_ids) == set(
        sample_development_dataset["SK_ID_CURR"]
    )


def test_features_exclude_target_and_id(
    sample_development_dataset: pd.DataFrame,
) -> None:
    """Cột TARGET và SK_ID_CURR không được xuất hiện trong feature set X."""
    result = create_development_split(
        sample_development_dataset,
        random_state=42,
    )
    for partition in (result.train, result.validation, result.test):
        assert "TARGET" not in partition.X.columns
        assert "SK_ID_CURR" not in partition.X.columns
        assert set(partition.X.columns) == {"feature_1", "feature_2"}


def test_stratification_preserves_target_ratio(
    sample_development_dataset: pd.DataFrame,
) -> None:
    """Tỷ lệ default được giữ hợp lý qua các phân vùng train/val/test."""
    result = create_development_split(
        sample_development_dataset,
        random_state=42,
        test_size=0.2,
        validation_size=0.2,
    )
    # Tỷ lệ target tổng thể là 0.1
    overall_rate = sample_development_dataset["TARGET"].mean()
    for rate in result.metadata.target_rates.values():
        assert pytest.approx(rate, abs=0.05) == overall_rate


def test_target_must_be_binary(sample_development_dataset: pd.DataFrame) -> None:
    """TARGET chứa giá trị ngoài 0 và 1 hoặc chỉ có 1 lớp phải raise ValueError."""
    df_invalid = sample_development_dataset.copy()
    df_invalid.loc[0, "TARGET"] = 2
    with pytest.raises(ValueError, match="phải chỉ chứa cả hai lớp 0 và 1"):
        create_development_split(df_invalid, random_state=42)

    df_single_class = sample_development_dataset.copy()
    df_single_class["TARGET"] = 0
    with pytest.raises(ValueError, match="phải chỉ chứa cả hai lớp 0 và 1"):
        create_development_split(df_single_class, random_state=42)


def test_null_target_rejected(sample_development_dataset: pd.DataFrame) -> None:
    """TARGET chứa null phải raise ValueError."""
    df_null = sample_development_dataset.copy()
    df_null.loc[0, "TARGET"] = np.nan
    with pytest.raises(ValueError, match="không được chứa giá trị null"):
        create_development_split(df_null, random_state=42)


def test_duplicate_id_rejected(sample_development_dataset: pd.DataFrame) -> None:
    """SK_ID_CURR bị duplicate phải raise ValueError."""
    df_dup = sample_development_dataset.copy()
    df_dup.loc[1, "SK_ID_CURR"] = df_dup.loc[0, "SK_ID_CURR"]
    with pytest.raises(ValueError, match="phải unique để audit split"):
        create_development_split(df_dup, random_state=42)


def test_null_id_rejected(sample_development_dataset: pd.DataFrame) -> None:
    """SK_ID_CURR chứa null phải raise ValueError."""
    df_null_id = sample_development_dataset.copy()
    df_null_id.loc[0, "SK_ID_CURR"] = np.nan
    with pytest.raises(ValueError, match="không được chứa giá trị null"):
        create_development_split(df_null_id, random_state=42)


@pytest.mark.parametrize(
    ("test_size", "validation_size"),
    [
        (0.0, 0.2),
        (1.0, 0.2),
        (0.2, 0.0),
        (0.2, 1.0),
        (0.6, 0.5),  # sum >= 1
    ],
)
def test_invalid_split_ratios_rejected(
    sample_development_dataset: pd.DataFrame,
    test_size: float,
    validation_size: float,
) -> None:
    """Tỷ lệ split không nằm trong (0, 1) hoặc tổng >= 1 phải raise ValueError."""
    with pytest.raises(ValueError):
        create_development_split(
            sample_development_dataset,
            random_state=42,
            test_size=test_size,
            validation_size=validation_size,
        )


def test_invalid_random_state_rejected(
    sample_development_dataset: pd.DataFrame,
) -> None:
    """random_state không phải số nguyên tường minh phải raise ValueError."""
    with pytest.raises(ValueError, match="random_state phải là số nguyên tường minh"):
        create_development_split(
            sample_development_dataset,
            random_state=None,  # type: ignore[arg-type]
        )

