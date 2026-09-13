"""Các utility quy đổi Probability of Default (PD) thành credit score/tier.

Các tham số PDO, base odds, score boundary và tier boundary đều là cấu hình do
caller cung cấp; module không khẳng định đây là business policy cuối cùng.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class CreditScoreConfig:
    """Cấu hình PDO scheme với odds được định nghĩa là bad-to-good odds.

    Với ``odds = PD / (1 - PD)``, PD cao hơn nghĩa là rủi ro cao hơn. Công thức
    trong module đảm bảo odds tăng gấp đôi thì score giảm ``pdo`` điểm, nên PD
    cao hơn luôn dẫn đến score thấp hơn (trước và sau khi áp dụng boundary).
    """

    base_score: float
    base_odds: float
    pdo: float
    min_score: float | None = None
    max_score: float | None = None
    epsilon: float = 1e-6


def validate_probability_of_default(
    probabilities: Sequence[float] | np.ndarray,
) -> np.ndarray:
    """Kiểm tra PD hữu hạn nằm trong đoạn đóng [0, 1]."""
    try:
        values = np.atleast_1d(np.asarray(probabilities, dtype=float))
    except (TypeError, ValueError) as exc:
        raise ValueError("PD phải là giá trị số trong [0, 1].") from exc
    if values.ndim != 1 or values.size == 0:
        raise ValueError("PD phải là vector một chiều không rỗng.")
    if not np.isfinite(values).all() or not np.all((values >= 0) & (values <= 1)):
        raise ValueError("PD phải là giá trị hữu hạn trong [0, 1].")
    return values


def probability_to_log_odds(
    probabilities: Sequence[float] | np.ndarray,
    *,
    epsilon: float = 1e-6,
) -> np.ndarray:
    """Đổi PD thành log bad-to-good odds với epsilon clipping an toàn.

    PD 0 và 1 được clip vào ``[epsilon, 1 - epsilon]`` trước khi lấy log để
    không sinh ``inf`` hoặc ``nan``.
    """
    values = validate_probability_of_default(probabilities)
    validated_epsilon = _validate_epsilon(epsilon)
    clipped = np.clip(values, validated_epsilon, 1 - validated_epsilon)
    return np.log(clipped / (1 - clipped))


def log_odds_to_probability(log_odds: Sequence[float] | np.ndarray) -> np.ndarray:
    """Đổi log bad-to-good odds hữu hạn về PD bằng sigmoid ổn định số học."""
    values = _validate_finite_vector(log_odds, value_name="log_odds")
    positive = values >= 0
    probabilities = np.empty_like(values, dtype=float)
    probabilities[positive] = 1 / (1 + np.exp(-values[positive]))
    exp_values = np.exp(values[~positive])
    probabilities[~positive] = exp_values / (1 + exp_values)
    return probabilities


def probability_to_credit_score(
    probabilities: Sequence[float] | np.ndarray,
    *,
    config: CreditScoreConfig,
) -> np.ndarray:
    """Quy đổi PD thành credit score theo PDO scheme và boundary cấu hình.

    Đây không phải final business policy. Caller phải ghi công thức, giả định,
    epsilon và score boundary vào model card trước khi xuất CREDIT_SCORE.
    """
    return log_odds_to_credit_score(
        probability_to_log_odds(probabilities, epsilon=config.epsilon),
        config=config,
    )


def log_odds_to_credit_score(
    log_odds: Sequence[float] | np.ndarray,
    *,
    config: CreditScoreConfig,
) -> np.ndarray:
    """Áp dụng score = base_score - PDO/log(2) * log(odds/base_odds).

    ``log_odds`` phải dùng định nghĩa bad-to-good odds. Do ``pdo`` bắt buộc
    dương, log odds/PD tăng sẽ làm score giảm; score không thể bị đảo chiều.
    """
    _validate_score_config(config)
    values = _validate_finite_vector(log_odds, value_name="log_odds")
    factor = config.pdo / np.log(2)
    scores = config.base_score - factor * (values - np.log(config.base_odds))
    if config.min_score is not None:
        scores = np.maximum(scores, config.min_score)
    if config.max_score is not None:
        scores = np.minimum(scores, config.max_score)
    if not np.isfinite(scores).all():
        raise RuntimeError("Credit score phải hữu hạn sau khi áp dụng cấu hình.")
    return scores


def assign_risk_tier(
    scores: Sequence[float] | np.ndarray,
    *,
    score_thresholds: Sequence[float],
    tier_labels: Sequence[str],
) -> np.ndarray:
    """Gán tier từ score theo threshold/label do caller cấu hình.

    Threshold phải tăng dần và có đúng ``len(tier_labels) - 1`` phần tử. Labels
    tương ứng với score tăng dần; ví dụ generic ``HIGH, MEDIUM, LOW`` khi score
    cao hơn có nghĩa là rủi ro thấp hơn. Boundary bằng threshold thuộc tier thấp
    hơn theo thứ tự score, nhờ ``searchsorted(..., side='left')``.
    """
    score_values = _validate_finite_vector(scores, value_name="scores")
    thresholds = _validate_tier_config(score_thresholds, tier_labels)
    indexes = np.searchsorted(thresholds, score_values, side="left")
    return np.asarray(tier_labels, dtype=object)[indexes]


def _validate_score_config(config: CreditScoreConfig) -> None:
    """Kiểm tra cấu hình PDO và boundary trước khi tính score."""
    if not isinstance(config, CreditScoreConfig):
        raise ValueError("config phải là CreditScoreConfig.")
    for value, name in (
        (config.base_score, "base_score"),
        (config.base_odds, "base_odds"),
        (config.pdo, "pdo"),
    ):
        if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(value):
            raise ValueError(f"{name} phải là số hữu hạn.")
    if config.base_odds <= 0:
        raise ValueError("base_odds phải dương theo định nghĩa bad-to-good odds.")
    if config.pdo <= 0:
        raise ValueError("pdo phải dương để PD cao hơn luôn cho score thấp hơn.")
    _validate_epsilon(config.epsilon)

    for value, name in ((config.min_score, "min_score"), (config.max_score, "max_score")):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(value)
        ):
            raise ValueError(f"{name} phải là số hữu hạn hoặc None.")
    if config.min_score is not None and config.max_score is not None:
        if config.min_score > config.max_score:
            raise ValueError("min_score không được lớn hơn max_score.")


def _validate_epsilon(epsilon: float) -> float:
    """Kiểm tra epsilon clipping nằm trong (0, 0.5)."""
    if isinstance(epsilon, bool) or not isinstance(epsilon, Real):
        raise ValueError("epsilon phải là số trong khoảng (0, 0.5).")
    if not 0 < epsilon < 0.5:
        raise ValueError("epsilon phải nằm trong khoảng (0, 0.5).")
    return float(epsilon)


def _validate_finite_vector(
    values: Sequence[float] | np.ndarray,
    *,
    value_name: str,
) -> np.ndarray:
    """Chuẩn hóa một vector số hữu hạn."""
    try:
        vector = np.atleast_1d(np.asarray(values, dtype=float))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{value_name} phải là vector số hữu hạn.") from exc
    if vector.ndim != 1 or vector.size == 0 or not np.isfinite(vector).all():
        raise ValueError(f"{value_name} phải là vector số hữu hạn không rỗng.")
    return vector


def _validate_tier_config(
    score_thresholds: Sequence[float],
    tier_labels: Sequence[str],
) -> np.ndarray:
    """Kiểm tra threshold monotonic và labels tier rõ ràng."""
    thresholds = _validate_finite_vector(
        score_thresholds,
        value_name="score_thresholds",
    )
    labels = tuple(tier_labels)
    if len(labels) != len(thresholds) + 1:
        raise ValueError("tier_labels phải nhiều hơn score_thresholds đúng một phần tử.")
    if any(not isinstance(label, str) or not label.strip() for label in labels):
        raise ValueError("Mỗi tier label phải là chuỗi không rỗng.")
    if len(set(labels)) != len(labels):
        raise ValueError("tier_labels không được trùng nhau.")
    if not np.all(np.diff(thresholds) > 0):
        raise ValueError("score_thresholds phải tăng dần nghiêm ngặt.")
    return thresholds
