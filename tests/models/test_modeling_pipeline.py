import pandas as pd
import pytest

from src.models.modeling_pipeline import (
    GateError,
    build_baseline_feature_selection,
    build_feature_schema,
    build_logistic_pipeline,
)


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
    assert pipeline.named_steps["model"].class_weight is None


def test_date_like_model_safe_features_are_audited_and_excluded_from_baseline() -> None:
    dataset = pd.DataFrame({
        "loan_id": ["1", "2"],
        "target": [0, 1],
        "issue_d": pd.to_datetime(["2018-01-01", "2018-02-01"]),
        "earliest_cr_line": pd.to_datetime(["2008-01-01", "2010-02-01"]),
        "credit_history_months": [120, 96],
        "issue_year": [2018, 2018],
        "purpose": ["car", "medical"],
    })
    dictionary = pd.DataFrame({
        "column_name": dataset.columns,
        "policy_class": ["IDENTIFIER", "ANALYTICS_ONLY", "APPLICATION_TIME", "CREDIT_SNAPSHOT", "CREDIT_SNAPSHOT", "APPLICATION_TIME", "APPLICATION_TIME"],
        "model_eligible_default": [False, False, True, True, True, True, True],
    })
    schema = build_feature_schema(dataset, dictionary)
    selection = build_baseline_feature_selection(dataset, schema)

    assert selection.baseline_features == (
        "credit_history_months", "issue_year", "purpose",
    )
    assert set(selection.excluded_safe_features) == {"issue_d", "earliest_cr_line"}
    assert set(selection.audit["feature_name"]) == set(schema.approved_features)
    assert selection.audit.loc[
        selection.audit["feature_name"] == "issue_d", "is_datetime_like"
    ].iloc[0]


def test_unknown_column_blocks_handoff() -> None:
    dataset = pd.DataFrame({"loan_id": ["1", "2"], "target": [0, 1], "mystery": [1, 2]})
    dictionary = pd.DataFrame({"column_name": dataset.columns, "policy_class": ["IDENTIFIER", "ANALYTICS_ONLY", "UNKNOWN_REVIEW_REQUIRED"], "model_eligible_default": [False, False, False]})
    with pytest.raises(GateError):
        build_feature_schema(dataset, dictionary)
