from __future__ import annotations

import numpy as np

from src.models.experiments.f1_oof import choose_oof_threshold


def test_oof_threshold_uses_f1_then_recall_precision_and_higher_threshold_tiebreaks() -> None:
    target = np.array([0, 0, 1, 1], dtype=np.int8)
    probabilities = np.array([0.1, 0.4, 0.6, 0.9], dtype=np.float32)

    result = choose_oof_threshold(target, probabilities)

    assert np.isclose(result["threshold"], 0.6)
    assert result["f1"] == 1.0
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert "selection-biased" in result["selection_note"]
