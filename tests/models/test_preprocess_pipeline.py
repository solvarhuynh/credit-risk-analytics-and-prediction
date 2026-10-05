import pandas as pd
import pytest

from src.models.preprocess_pipeline import build_preprocessor, validate_modeling_columns


def test_preprocessor_accepts_only_approved_classes() -> None:
    frame = pd.DataFrame({"dti": [10.0, None], "purpose": ["car", "debt_consolidation"]})
    transformer = build_preprocessor(frame, ["dti", "purpose"])
    transformed = transformer.fit_transform(frame)
    assert transformed.shape[0] == 2


def test_preprocessor_rejects_raw_datetime_feature_instead_of_one_hot_encoding() -> None:
    frame = pd.DataFrame({"issue_d": pd.to_datetime(["2018-01-01", "2018-02-01"])})
    with pytest.raises(ValueError, match="Date-like feature"):
        build_preprocessor(frame, ["issue_d"])


@pytest.mark.parametrize("column", ["total_pymnt", "grade", "state_code", "unknown_field", "loan_id", "target"])
def test_forbidden_feature_is_rejected(column: str) -> None:
    frame = pd.DataFrame({column: [1, 2]})
    with pytest.raises(ValueError):
        validate_modeling_columns(frame, [column])
