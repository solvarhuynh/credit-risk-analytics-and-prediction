import pandas as pd
import pytest

from src.models.preprocess_pipeline import build_preprocessor, validate_modeling_columns


def test_preprocessor_accepts_only_approved_classes() -> None:
    frame = pd.DataFrame({"dti": [10.0, None], "purpose": ["car", "debt_consolidation"]})
    transformer = build_preprocessor(frame, ["dti", "purpose"])
    transformed = transformer.fit_transform(frame)
    assert transformed.shape[0] == 2


@pytest.mark.parametrize("column", ["total_pymnt", "grade", "state_code", "unknown_field", "loan_id", "target"])
def test_forbidden_feature_is_rejected(column: str) -> None:
    frame = pd.DataFrame({column: [1, 2]})
    with pytest.raises(ValueError):
        validate_modeling_columns(frame, [column])
