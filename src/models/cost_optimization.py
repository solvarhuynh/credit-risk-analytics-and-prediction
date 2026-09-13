"""Utility Expected Loss và threshold-policy analysis không gắn với model cụ thể.

Expected Loss (EL) = PD * LGD * EAD. EL không phải lợi nhuận: module không có
interest/revenue, acquisition cost, opportunity cost hoặc recovery assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Sequence

import numpy as np
import pandas as pd


NumericInput = Sequence[float] | np.ndarray | pd.Series | Real


@dataclass(frozen=True)
class ThresholdPolicySummary:
    """Các quantity quan sát/tính toán cho một threshold đã do caller chọn."""

    threshold: float
    approved_count: int
    rejected_count: int
    observed_defaults_approved: int
    expected_loss_approved: float


def calculate_expected_loss(
    probability_of_default: NumericInput,
    loss_given_default: NumericInput,
    exposure_at_default: NumericInput,
) -> np.ndarray | pd.Series:
    """Tính vectorized Expected Loss = PD * LGD * EAD.

    PD và LGD phải thuộc [0, 1]; EAD phải không âm. LGD và EAD là input explicit
    do caller quyết định, không có default business assumption trong module. Nếu
    dùng Series, tất cả Series phải có cùng index chính xác; missing/inf không
    được tự động thay bằng 0.
    """
    pd_values, lgd_values, ead_values, index = _prepare_el_inputs(
        probability_of_default,
        loss_given_default,
        exposure_at_default,
    )
    expected_loss = pd_values * lgd_values * ead_values
    if index is not None:
        return pd.Series(expected_loss, index=index, name="EXPECTED_LOSS")
    return expected_loss


def calculate_portfolio_expected_loss(
    probability_of_default: NumericInput,
    loss_given_default: NumericInput,
    exposure_at_default: NumericInput,
) -> float:
    """Tính tổng Expected Loss danh mục, không diễn giải là profit/loss thực tế."""
    expected_loss = calculate_expected_loss(
        probability_of_default,
        loss_given_default,
        exposure_at_default,
    )
    return float(expected_loss.sum())


def evaluate_threshold_policy(
    target: Sequence[int] | np.ndarray | pd.Series,
    probability_of_default: NumericInput,
    loss_given_default: NumericInput,
    exposure_at_default: NumericInput,
    *,
    threshold: float,
) -> ThresholdPolicySummary:
    """Đánh giá một threshold policy đã chọn, không tối ưu threshold.

    Record được approve khi ``PD < threshold``; PD bằng threshold bị reject. Hàm
    chỉ trả count, observed defaults trong approved population và expected loss
    của approved portfolio. Không suy ra doanh thu hoặc lợi nhuận, và không được
    dùng để chọn threshold trên frozen test set.
    """
    pd_values, lgd_values, ead_values, index = _prepare_el_inputs(
        probability_of_default,
        loss_given_default,
        exposure_at_default,
    )
    target_values = _prepare_target(target, expected_length=len(pd_values), index=index)
    validated_threshold = _validate_threshold(threshold)
    approved = pd_values < validated_threshold
    expected_loss = pd_values * lgd_values * ead_values

    return ThresholdPolicySummary(
        threshold=validated_threshold,
        approved_count=int(approved.sum()),
        rejected_count=int((~approved).sum()),
        observed_defaults_approved=int(target_values[approved].sum()),
        expected_loss_approved=float(expected_loss[approved].sum()),
    )


def _prepare_el_inputs(
    probability_of_default: NumericInput,
    loss_given_default: NumericInput,
    exposure_at_default: NumericInput,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.Index | None]:
    """Chuẩn hóa EL inputs và buộc alignment trước khi nhân vectorized."""
    inputs = {
        "PD": probability_of_default,
        "LGD": loss_given_default,
        "EAD": exposure_at_default,
    }
    reference_index = _find_reference_index(inputs.values())
    raw_values = {name: _coerce_numeric(value, name=name) for name, value in inputs.items()}
    expected_length = _resolve_length(raw_values, reference_index=reference_index)
    aligned = {
        name: _align_numeric(
            value,
            name=name,
            expected_length=expected_length,
            reference_index=reference_index,
        )
        for name, value in inputs.items()
    }

    _validate_range(aligned["PD"], name="PD", minimum=0, maximum=1)
    _validate_range(aligned["LGD"], name="LGD", minimum=0, maximum=1)
    _validate_range(aligned["EAD"], name="EAD", minimum=0, maximum=None)
    return aligned["PD"], aligned["LGD"], aligned["EAD"], reference_index


def _find_reference_index(values: Sequence[NumericInput]) -> pd.Index | None:
    """Lấy index của Series đầu tiên và buộc Series còn lại khớp tuyệt đối."""
    series_values = [value for value in values if isinstance(value, pd.Series)]
    if not series_values:
        return None
    reference_index = series_values[0].index
    if not reference_index.is_unique:
        raise ValueError("Series index phải unique để kiểm tra alignment rõ ràng.")
    for series in series_values[1:]:
        if not series.index.equals(reference_index):
            raise ValueError("Các Series PD/LGD/EAD phải có cùng index và thứ tự.")
    return reference_index


def _coerce_numeric(value: NumericInput, *, name: str) -> np.ndarray:
    """Chuyển scalar/array/Series thành vector số, không xử lý missing ngầm."""
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} phải là giá trị số.") from exc
    if array.ndim > 1:
        raise ValueError(f"{name} phải là scalar hoặc vector một chiều.")
    if array.ndim == 0:
        array = array.reshape(1)
    if array.size == 0 or not np.isfinite(array).all():
        raise ValueError(f"{name} không được rỗng, missing hoặc vô hạn.")
    return array


def _resolve_length(
    values: dict[str, np.ndarray],
    *,
    reference_index: pd.Index | None,
) -> int:
    """Xác định length chung trước khi broadcast scalar."""
    if reference_index is not None:
        return len(reference_index)
    vector_lengths = {len(value) for value in values.values() if len(value) > 1}
    if len(vector_lengths) > 1:
        raise ValueError("PD, LGD và EAD phải có cùng length.")
    return vector_lengths.pop() if vector_lengths else 1


def _align_numeric(
    value: NumericInput,
    *,
    name: str,
    expected_length: int,
    reference_index: pd.Index | None,
) -> np.ndarray:
    """Broadcast scalar hoặc xác nhận length/index của vector đầu vào."""
    if isinstance(value, pd.Series) and reference_index is not None:
        if not value.index.equals(reference_index):
            raise ValueError(f"{name} Series không khớp index của input còn lại.")
    array = _coerce_numeric(value, name=name)
    if len(array) == 1:
        return np.full(expected_length, array[0], dtype=float)
    if len(array) != expected_length:
        raise ValueError(f"{name} phải có length {expected_length} hoặc là scalar.")
    return array


def _validate_range(
    values: np.ndarray,
    *,
    name: str,
    minimum: float,
    maximum: float | None,
) -> None:
    """Kiểm tra miền giá trị numeric đã được chuẩn hóa."""
    if np.any(values < minimum) or (maximum is not None and np.any(values > maximum)):
        interval = f"[{minimum}, {maximum}]" if maximum is not None else f">= {minimum}"
        raise ValueError(f"{name} phải nằm trong {interval}.")


def _prepare_target(
    target: Sequence[int] | np.ndarray | pd.Series,
    *,
    expected_length: int,
    index: pd.Index | None,
) -> np.ndarray:
    """Kiểm tra target nhị phân và alignment với policy input."""
    if isinstance(target, pd.Series) and index is not None and not target.index.equals(index):
        raise ValueError("TARGET Series phải có cùng index và thứ tự với PD/LGD/EAD.")
    try:
        values = np.asarray(target)
    except (TypeError, ValueError) as exc:
        raise ValueError("TARGET phải là vector nhị phân 0/1.") from exc
    if values.ndim != 1 or len(values) != expected_length or pd.isna(values).any():
        raise ValueError("TARGET phải không null và có cùng length với PD/LGD/EAD.")
    if not set(values).issubset({0, 1}):
        raise ValueError("TARGET chỉ được chứa 0 hoặc 1.")
    return values.astype(int)


def _validate_threshold(threshold: float) -> float:
    """Kiểm tra threshold xác suất đóng trong [0, 1]."""
    if isinstance(threshold, bool) or not isinstance(threshold, Real):
        raise ValueError("threshold phải là số trong [0, 1].")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold phải nằm trong [0, 1].")
    return float(threshold)
