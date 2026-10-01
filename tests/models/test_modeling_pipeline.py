import pandas as pd
import pytest

from src.models.modeling_pipeline import GateError, build_feature_schema, build_logistic_pipeline


def test_feature_schema_and_mandatory_logistic() -> None:
    dataset = pd.DataFrame({"loan_id": ["1", "2"], "target": [0, 1], "dti": [10.0, 20.0], "purpose": ["car", "medical"]})
    dictionary = pd.DataFrame({
        "column_name": dataset.columns,
        "policy_class": ["IDENTIFIER", "ANALYTICS_ONLY", "CREDIT_SNAPSHOT", "APPLICATION_TIME"],
        "model_eligible_default": [False, False, True, True],
    })
    schema = build_feature_schema(dataset, dictionary)
    pipeline = build_logistic_pipeline(dataset, schema)
    assert set(schema.approved_features) == {"dti", "purpose"}
    assert pipeline.named_steps["model"].__class__.__name__ == "LogisticRegression"


def test_unknown_column_blocks_handoff() -> None:
    dataset = pd.DataFrame({"loan_id": ["1", "2"], "target": [0, 1], "mystery": [1, 2]})
    dictionary = pd.DataFrame({"column_name": dataset.columns, "policy_class": ["IDENTIFIER", "ANALYTICS_ONLY", "UNKNOWN_REVIEW_REQUIRED"], "model_eligible_default": [False, False, False]})
    with pytest.raises(GateError):
        build_feature_schema(dataset, dictionary)
