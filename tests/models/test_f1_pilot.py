from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.sparse import issparse
import xgboost as xgb

from src.models.experiments.f1_pilot import fit_transform_in_batches
from src.models.preprocess_pipeline import NormalizePandasMissing, build_xgboost_preprocessor


def test_disk_backed_batched_preprocessing_matches_xgboost_input_precision(tmp_path) -> None:
    frame = pd.DataFrame({
        "loan_amnt": [1000.0, None, 2500.0, 3000.0, 5000.0],
        "purpose": ["debt", "home", "debt", None, "car"],
    })
    target = pd.Series([0, 1, 0, 1, 0], dtype="int8")
    normalizer = NormalizePandasMissing()
    normalized = normalizer.fit_transform(frame)
    reference = build_xgboost_preprocessor(normalized, normalized.columns.tolist())
    expected = reference.fit_transform(normalized, target)

    batched = build_xgboost_preprocessor(normalized, normalized.columns.tolist())
    actual = fit_transform_in_batches(
        batched, normalized, target, scratch_dir=tmp_path / "matrix-work", batch_rows=2,
    )

    assert issparse(actual)
    assert actual.shape == expected.shape
    assert actual.dtype == np.float32
    np.testing.assert_allclose(actual.toarray(), expected.astype(np.float32).toarray(), rtol=0, atol=0)
    expected_dmatrix = xgb.DMatrix(expected).get_data()
    actual_dmatrix = xgb.DMatrix(actual).get_data()
    np.testing.assert_array_equal(actual_dmatrix.toarray(), expected_dmatrix.toarray())
    assert actual.shape[0] == len(target)
