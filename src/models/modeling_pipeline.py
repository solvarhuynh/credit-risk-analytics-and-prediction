"""Leakage-safe, gated TV1 credit-risk modeling workflow.

The module keeps development-model selection separate from the one-time frozen
test evaluation and the later full-labeled-data production refit.  It is a
reusable script, not a notebook: all paths are repository-relative and all
randomness is explicit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import joblib
import matplotlib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from src.data.load_data import project_root
from src.models.cost_optimization import (
    ThresholdPolicySummary,
    calculate_expected_loss,
    evaluate_threshold_policy,
)
from src.models.data_split import FrozenTestSplitResult, create_frozen_test_split
from src.models.evaluation import (
    BinaryEvaluationResult,
    build_validation_threshold_table,
    evaluate_binary_classifier,
)
from src.models.preprocess_pipeline import (
    DEFAULT_FORBIDDEN_FEATURE_COLUMNS,
    build_preprocessor,
    validate_modeling_columns,
)
from src.models.scoring import CreditScoreConfig, assign_risk_tier, probability_to_credit_score


matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402  (backend must be selected first)


CANONICAL_DATASET_PATH = Path("data/processed/cleaned_dataset.parquet")
CANONICAL_DICTIONARY_PATH = Path("data/processed/data_dictionary.csv")
CANONICAL_MANIFEST_PATH = Path("data/processed/cleaned_dataset_manifest.json")
MODEL_ARTIFACT_PATH = Path("models/full_inference_pipeline.joblib")
FROZEN_TEST_RECORD_PATH = Path("reports/frozen_test_evaluation_record.json")
SCORED_DATASET_PATH = Path("data/processed/scored_dataset.parquet")
MODEL_CARD_PATH = Path("reports/model_card.md")
INTEGRATION_PROFILE_PATH = Path("reports/model_integration_profiles.csv")
FIGURE_DIRECTORY = Path("reports/figures/modeling")


class GateError(RuntimeError):
    """Raised when a workflow gate cannot safely pass."""

    def __init__(self, gate: str, message: str) -> None:
        super().__init__(message)
        self.gate = gate


@dataclass(frozen=True)
class RunConfig:
    """Frozen technical configuration for a single canonical dataset snapshot."""

    random_state: int = 20260922
    frozen_test_size: float = 0.20
    cv_splits: int = 3
    n_jobs: int = 4
    threshold_grid: tuple[float, ...] = tuple(np.round(np.arange(0.05, 0.51, 0.01), 2))
    model_version_prefix: str = "TV1-MASTER-20260922"
    lgd_assumption: float = 0.45
    ead_proxy_column: str = "AMT_CREDIT"
    score_config: CreditScoreConfig = field(
        default_factory=lambda: CreditScoreConfig(
            base_score=600.0,
            base_odds=0.05,
            pdo=20.0,
            min_score=300.0,
            max_score=850.0,
        )
    )
    risk_tier_thresholds: tuple[float, ...] = (550.0, 650.0)
    risk_tier_labels: tuple[str, ...] = ("HIGH_RISK", "MEDIUM_RISK", "LOW_RISK")


@dataclass(frozen=True)
class DatasetFingerprint:
    """Identity and acceptance evidence for the exact modeling input snapshot."""

    dataset_sha256: str
    manifest_output_sha256: str
    row_count: int
    column_count: int
    target_distribution: dict[str, int]
    manifest_branch: str | None
    manifest_commit: str | None


@dataclass(frozen=True)
class FeatureSchema:
    """Explicit model-input boundary derived from the accepted snapshot."""

    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]
    excluded_features: tuple[str, ...]
    review_only_features: tuple[str, ...]

    @property
    def all_features(self) -> tuple[str, ...]:
        return self.numeric_features + self.categorical_features


@dataclass(frozen=True)
class CandidateDefinition:
    """A bounded, reproducible development candidate."""

    name: str
    family: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class FoldMetric:
    """Development-CV metrics for one validation fold."""

    fold: int
    roc_auc: float
    pr_auc: float
    precision: float
    recall: float
    f1: float


@dataclass
class CandidateCVResult:
    """Out-of-fold evidence for selecting a candidate without frozen-test use."""

    definition: CandidateDefinition
    fold_metrics: list[FoldMetric]
    oof_probabilities: np.ndarray

    def summary(self) -> dict[str, float]:
        metrics = pd.DataFrame([asdict(metric) for metric in self.fold_metrics])
        return {
            "mean_roc_auc": float(metrics["roc_auc"].mean()),
            "std_roc_auc": float(metrics["roc_auc"].std(ddof=0)),
            "mean_pr_auc": float(metrics["pr_auc"].mean()),
            "std_pr_auc": float(metrics["pr_auc"].std(ddof=0)),
            "mean_precision": float(metrics["precision"].mean()),
            "mean_recall": float(metrics["recall"].mean()),
            "mean_f1": float(metrics["f1"].mean()),
        }


@dataclass(frozen=True)
class SelectionDecision:
    """A documented development-only selection decision."""

    selected_name: str
    selected_family: str
    rationale: str
    needs_human_decision: bool


@dataclass(frozen=True)
class ProductionValidation:
    """Evidence that a serialized production artifact can be used downstream."""

    probability_min: float
    probability_max: float
    deterministic: bool
    unknown_category_safe: bool
    scored_rows: int


@dataclass(frozen=True)
class WorkflowResult:
    """Material results emitted by a completed TV1 modeling run."""

    fingerprint: DatasetFingerprint
    schema: FeatureSchema
    split: FrozenTestSplitResult
    candidate_results: tuple[CandidateCVResult, ...]
    selection: SelectionDecision
    threshold: float
    threshold_table: pd.DataFrame
    frozen_test_evaluation: BinaryEvaluationResult
    frozen_test_pr_auc: float
    policy_summary: ThresholdPolicySummary
    full_portfolio_expected_loss: float
    model_version: str
    explanation_paths: tuple[str, ...]
    validation: ProductionValidation


def sha256_file(path: Path) -> str:
    """Return a file SHA-256 without loading a potentially large file at once."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_ids_hash(ids: pd.Series) -> str:
    """Fingerprint an unordered ID set deterministically for split audit."""
    payload = "\n".join(map(str, sorted(ids.astype(int).tolist()))).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def load_canonical_input(root: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], DatasetFingerprint]:
    """Load and independently validate the canonical TV2 model-input snapshot."""
    root = Path(root) if root is not None else project_root()
    dataset_path = root / CANONICAL_DATASET_PATH
    dictionary_path = root / CANONICAL_DICTIONARY_PATH
    manifest_path = root / CANONICAL_MANIFEST_PATH
    missing = [str(path) for path in (dataset_path, dictionary_path, manifest_path) if not path.is_file()]
    if missing:
        raise GateError("A", "Thiếu canonical model-input artifact: " + ", ".join(missing))

    dataset = pd.read_parquet(dataset_path)
    dictionary = pd.read_csv(dictionary_path, encoding="utf-8-sig")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset_hash = sha256_file(dataset_path)
    required = {
        "SK_ID_CURR",
        "TARGET",
        "AMT_INCOME_TOTAL",
        "AMT_CREDIT",
        "AMT_ANNUITY",
        "AMT_GOODS_PRICE",
        "CODE_GENDER",
        "NAME_CONTRACT_TYPE",
        "AGE_YEARS",
        "AGE_GROUP",
        "ANNUITY_TO_INCOME_RATIO",
        "CREDIT_TO_INCOME_RATIO",
        "EMPLOYED_YEARS",
        "DAYS_EMPLOYED_ANOM",
    }
    numeric = dataset.select_dtypes(include=[np.number])
    actual_schema = {column: str(dtype) for column, dtype in dataset.dtypes.items()}
    errors: list[str] = []
    if dataset.empty:
        errors.append("dataset rỗng")
    if "SK_ID_CURR" not in dataset.columns:
        errors.append("dataset thiếu SK_ID_CURR")
    elif dataset["SK_ID_CURR"].isna().any() or not dataset["SK_ID_CURR"].is_unique:
        errors.append("SK_ID_CURR phải non-null và unique")
    if "TARGET" not in dataset.columns:
        errors.append("dataset thiếu TARGET")
    elif dataset["TARGET"].isna().any() or set(dataset["TARGET"].unique()) != {0, 1}:
        errors.append("TARGET phải non-null và chứa đúng hai lớp {0, 1}")
    if np.isinf(numeric.to_numpy(dtype="float64", na_value=np.nan)).any():
        errors.append("dataset chứa infinity")
    missing_required = sorted(required.difference(dataset.columns))
    if missing_required:
        errors.append("thiếu required columns: " + ", ".join(missing_required))
    if "column_name" not in dictionary.columns or len(dictionary) != len(dataset.columns):
        errors.append("data dictionary không phủ đúng số cột")
    elif dictionary["column_name"].duplicated().any() or set(dictionary["column_name"]) != set(dataset.columns):
        errors.append("data dictionary không khớp chính xác schema dataset")
    if manifest.get("row_count") != len(dataset) or manifest.get("column_count") != len(dataset.columns):
        errors.append("manifest row/column count không khớp dataset")
    if manifest.get("output_sha256") != dataset_hash:
        errors.append("manifest output hash không khớp dataset")
    if manifest.get("output_schema") != actual_schema:
        errors.append("manifest schema không khớp Parquet read-back")
    if errors:
        raise GateError("A", "; ".join(errors))

    fingerprint = DatasetFingerprint(
        dataset_sha256=dataset_hash,
        manifest_output_sha256=str(manifest["output_sha256"]),
        row_count=int(len(dataset)),
        column_count=int(len(dataset.columns)),
        target_distribution={
            str(key): int(value) for key, value in dataset["TARGET"].value_counts().sort_index().items()
        },
        manifest_branch=manifest.get("git_branch"),
        manifest_commit=manifest.get("base_commit"),
    )
    return dataset, dictionary, manifest, fingerprint


def build_feature_schema(dataset: pd.DataFrame, dictionary: pd.DataFrame) -> FeatureSchema:
    """Create an explicit feature boundary using dtypes and dictionary roles."""
    forbidden = set(DEFAULT_FORBIDDEN_FEATURE_COLUMNS)
    excluded = tuple(sorted(forbidden))
    candidate_features = [column for column in dataset.columns if column not in forbidden]
    if not candidate_features:
        raise GateError("B", "Không còn predictive feature nào sau exclusion.")
    if "column_name" not in dictionary.columns or "role" not in dictionary.columns:
        raise GateError("B", "Data dictionary thiếu column_name hoặc role để kiểm tra feature boundary.")
    roles = dictionary.set_index("column_name")["role"]
    non_features = [column for column in candidate_features if roles.get(column) != "feature"]
    if non_features:
        raise GateError("B", "Feature không có dictionary role=feature: " + ", ".join(non_features))
    categorical = [
        column
        for column in candidate_features
        if str(dataset[column].dtype) in {"object", "category", "string"}
    ]
    numeric = [column for column in candidate_features if column not in categorical]
    try:
        valid_numeric, valid_categorical = validate_modeling_columns(
            numeric,
            categorical,
            available_columns=dataset.columns,
        )
    except ValueError as exc:
        raise GateError("B", str(exc)) from exc
    review_only = tuple(
        column
        for column in (
            "CREDIT_TO_INCOME_RATIO",
            "INSTAL_PAYMENT_RATIO_MEAN",
            "CC_UTILIZATION_MEAN",
        )
        if column in candidate_features
    )
    return FeatureSchema(
        numeric_features=valid_numeric,
        categorical_features=valid_categorical,
        excluded_features=excluded,
        review_only_features=review_only,
    )


def candidate_definitions() -> tuple[CandidateDefinition, ...]:
    """Return the intentionally small, predeclared candidate search space."""
    return (
        CandidateDefinition("logistic_baseline", "logistic", {"class_weight": None}),
        CandidateDefinition("logistic_balanced", "logistic", {"class_weight": "balanced"}),
        CandidateDefinition(
            "xgboost_depth4",
            "xgboost",
            {
                "n_estimators": 180,
                "max_depth": 4,
                "learning_rate": 0.05,
                "min_child_weight": 20,
                "subsample": 0.80,
                "colsample_bytree": 0.80,
                "reg_lambda": 5.0,
            },
        ),
        CandidateDefinition(
            "xgboost_depth6",
            "xgboost",
            {
                "n_estimators": 240,
                "max_depth": 6,
                "learning_rate": 0.04,
                "min_child_weight": 30,
                "subsample": 0.80,
                "colsample_bytree": 0.80,
                "reg_lambda": 8.0,
            },
        ),
    )


def build_candidate_pipeline(
    definition: CandidateDefinition,
    schema: FeatureSchema,
    *,
    available_columns: Sequence[str],
    config: RunConfig,
) -> Pipeline:
    """Build an unfitted candidate with preprocessing inside the sklearn pipeline."""
    scale_numeric = definition.family == "logistic"
    preprocessor = build_preprocessor(
        schema.numeric_features,
        schema.categorical_features,
        scale_numeric=scale_numeric,
        available_columns=available_columns,
    )
    if definition.family == "logistic":
        classifier: Any = LogisticRegression(
            C=1.0,
            solver="saga",
            max_iter=800,
            tol=1e-3,
            class_weight=definition.parameters["class_weight"],
            random_state=config.random_state,
        )
    elif definition.family == "xgboost":
        classifier = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            random_state=config.random_state,
            n_jobs=config.n_jobs,
            verbosity=0,
            **definition.parameters,
        )
    else:
        raise ValueError(f"Unsupported candidate family: {definition.family}")
    return Pipeline(steps=[("preprocessor", preprocessor), ("classifier", classifier)])


def run_candidate_cv(
    definition: CandidateDefinition,
    development_X: pd.DataFrame,
    development_y: pd.Series,
    schema: FeatureSchema,
    *,
    config: RunConfig,
) -> CandidateCVResult:
    """Fit a candidate only inside CV training folds and retain OOF probabilities."""
    if len(development_X) != len(development_y):
        raise GateError("E", "Development X/y có length khác nhau.")
    folds = StratifiedKFold(
        n_splits=config.cv_splits,
        shuffle=True,
        random_state=config.random_state,
    )
    probabilities = np.full(len(development_y), np.nan, dtype=float)
    metrics: list[FoldMetric] = []
    for fold_number, (train_idx, validation_idx) in enumerate(
        folds.split(development_X, development_y),
        start=1,
    ):
        pipeline = build_candidate_pipeline(
            definition,
            schema,
            available_columns=development_X.columns,
            config=config,
        )
        pipeline.fit(development_X.iloc[train_idx], development_y.iloc[train_idx])
        fold_probabilities = pipeline.predict_proba(development_X.iloc[validation_idx])[:, 1]
        evaluation = evaluate_binary_classifier(
            development_y.iloc[validation_idx],
            fold_probabilities,
            threshold=0.50,
        )
        probabilities[validation_idx] = fold_probabilities
        metrics.append(
            FoldMetric(
                fold=fold_number,
                roc_auc=evaluation.roc_auc,
                pr_auc=float(average_precision_score(development_y.iloc[validation_idx], fold_probabilities)),
                precision=evaluation.precision,
                recall=evaluation.recall,
                f1=evaluation.f1,
            )
        )
    if not np.isfinite(probabilities).all() or not np.all((probabilities >= 0) & (probabilities <= 1)):
        raise GateError("E", f"{definition.name} không tạo OOF probability hợp lệ.")
    return CandidateCVResult(definition=definition, fold_metrics=metrics, oof_probabilities=probabilities)


def select_candidate(results: Sequence[CandidateCVResult]) -> SelectionDecision:
    """Select solely from CV evidence, with an explicit ambiguity safeguard."""
    if not results:
        raise GateError("H", "Không có candidate CV result để lựa chọn model.")
    ranked = sorted(
        results,
        key=lambda result: (
            result.summary()["mean_roc_auc"],
            result.summary()["mean_pr_auc"],
            result.summary()["mean_f1"],
            -result.summary()["std_roc_auc"],
        ),
        reverse=True,
    )
    top = ranked[0]
    top_summary = top.summary()
    if len(ranked) > 1:
        second = ranked[1]
        second_summary = second.summary()
        if (
            top.definition.family != second.definition.family
            and abs(top_summary["mean_roc_auc"] - second_summary["mean_roc_auc"]) < 0.0005
            and abs(top_summary["mean_pr_auc"] - second_summary["mean_pr_auc"]) < 0.0005
        ):
            return SelectionDecision(
                selected_name=top.definition.name,
                selected_family=top.definition.family,
                rationale=(
                    "Hai họ model dẫn đầu gần như hòa nhau trên cả ROC-AUC và PR-AUC; "
                    "cần quyết định của con người về interpretability/complexity."
                ),
                needs_human_decision=True,
            )
    return SelectionDecision(
        selected_name=top.definition.name,
        selected_family=top.definition.family,
        rationale=(
            "Selected from development-only 3-fold CV by highest mean ROC-AUC, "
            "then mean PR-AUC, mean F1, and lower ROC-AUC variability."
        ),
        needs_human_decision=False,
    )


def choose_threshold_from_oof(
    development_y: pd.Series,
    probabilities: np.ndarray,
    *,
    config: RunConfig,
) -> tuple[float, pd.DataFrame]:
    """Freeze a technical F1-maximising threshold from development OOF predictions."""
    table = build_validation_threshold_table(
        development_y,
        probabilities,
        thresholds=config.threshold_grid,
    )
    ranked = table.sort_values(
        ["f1", "precision", "recall", "threshold"],
        ascending=[False, False, False, True],
        kind="stable",
    ).reset_index(drop=True)
    if ranked.empty or not np.isfinite(ranked.loc[0, "f1"]):
        raise GateError("I", "Không thể chọn threshold từ OOF development predictions.")
    return float(ranked.loc[0, "threshold"]), table


def evaluate_frozen_test(
    pipeline: Pipeline,
    frozen_X: pd.DataFrame,
    frozen_y: pd.Series,
    *,
    threshold: float,
) -> tuple[BinaryEvaluationResult, float, np.ndarray]:
    """Run the one-time evaluation of the already locked configuration."""
    probabilities = pipeline.predict_proba(frozen_X)[:, 1]
    evaluation = evaluate_binary_classifier(frozen_y, probabilities, threshold=threshold)
    pr_auc = float(average_precision_score(frozen_y, probabilities))
    return evaluation, pr_auc, probabilities


def _atomic_joblib_dump(value: Any, path: Path) -> None:
    """Atomically publish a serialized artifact after successful serialization."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        joblib.dump(value, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_parquet_write(frame: pd.DataFrame, path: Path) -> None:
    """Atomically publish scored data after a read-back schema/row check."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        frame.to_parquet(temporary, index=False)
        readback = pd.read_parquet(temporary)
        if len(readback) != len(frame) or list(readback.columns) != list(frame.columns):
            raise RuntimeError("Scored dataset read-back validation failed.")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_text_write(text: str, path: Path) -> None:
    """Atomically publish a UTF-8 text report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json_write(payload: dict[str, Any], path: Path) -> None:
    """Atomically publish a small, auditable JSON control record."""
    _atomic_text_write(json.dumps(payload, indent=2, sort_keys=True) + "\n", path)


def _assert_frozen_test_unused(
    root: Path,
    *,
    fingerprint: DatasetFingerprint,
    split: FrozenTestSplitResult,
) -> None:
    """Prevent accidental reuse of a frozen test for the same output namespace."""
    record_path = root / FROZEN_TEST_RECORD_PATH
    if not record_path.is_file():
        return
    try:
        prior = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError("J", f"Frozen-test control record cannot be read: {exc}") from exc
    same_snapshot = prior.get("dataset_sha256") == fingerprint.dataset_sha256
    same_frozen_ids = prior.get("frozen_test_ids_sha256") == stable_ids_hash(split.frozen_test.ids)
    if same_snapshot and same_frozen_ids:
        raise GateError(
            "J",
            "Frozen test đã được đánh giá cho snapshot/split này. Không được chạy lại full workflow "
            "hoặc retune theo frozen test; dùng --verify-only hoặc bắt đầu modeling run mới có namespace mới.",
        )
    raise GateError(
        "J",
        "Tồn tại frozen-test control record của một modeling run khác trong output namespace hiện tại. "
        "Không ghi đè run cũ; tạo namespace/run mới có chủ đích trước khi đánh giá frozen test.",
    )


def _write_frozen_test_record(
    root: Path,
    *,
    fingerprint: DatasetFingerprint,
    split: FrozenTestSplitResult,
    definition: CandidateDefinition,
    threshold: float,
    evaluation: BinaryEvaluationResult,
    pr_auc: float,
) -> None:
    """Record the one-time frozen-test result before downstream production work."""
    record = {
        "dataset_sha256": fingerprint.dataset_sha256,
        "manifest_output_sha256": fingerprint.manifest_output_sha256,
        "random_state": split.random_state,
        "frozen_test_size": split.test_size,
        "development_ids_sha256": stable_ids_hash(split.development.ids),
        "frozen_test_ids_sha256": stable_ids_hash(split.frozen_test.ids),
        "selected_candidate": definition.name,
        "selected_family": definition.family,
        "selected_parameters": definition.parameters,
        "threshold": threshold,
        "metrics": {
            **evaluation.metrics_dict(),
            "pr_auc": pr_auc,
            "confusion_matrix": evaluation.confusion.astype(int).tolist(),
        },
    }
    _atomic_json_write(record, root / FROZEN_TEST_RECORD_PATH)


def _record_production_artifacts(
    root: Path,
    *,
    model_version: str,
) -> None:
    """Bind the frozen-test record to the exact exported production artifacts."""
    record_path = root / FROZEN_TEST_RECORD_PATH
    artifact_path = root / MODEL_ARTIFACT_PATH
    scored_path = root / SCORED_DATASET_PATH
    if not record_path.is_file() or not artifact_path.is_file() or not scored_path.is_file():
        raise GateError("P", "Không thể bind frozen-test record với production artifacts bị thiếu.")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError("P", f"Frozen-test record không thể đọc để bind artifacts: {exc}") from exc
    scored = pd.read_parquet(scored_path)
    record["production_artifacts"] = {
        "model_artifact_sha256": sha256_file(artifact_path),
        "scored_dataset_sha256": sha256_file(scored_path),
        "model_version": model_version,
        "scored_row_count": int(len(scored)),
    }
    _atomic_json_write(record, record_path)


def _atomic_csv_write(frame: pd.DataFrame, path: Path) -> None:
    """Atomically publish a small CSV after an exact read-back row/column check."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        frame.to_csv(temporary, index=False, lineterminator="\n")
        readback = pd.read_csv(temporary)
        if len(readback) != len(frame) or list(readback.columns) != list(frame.columns):
            raise RuntimeError("Integration-profile CSV read-back validation failed.")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def create_integration_profile_reference(
    scored: pd.DataFrame,
    *,
    path: Path,
) -> pd.DataFrame:
    """Publish two stable, anonymized scored-record references for TV3 checks."""
    required = {
        "SK_ID_CURR",
        "PREDICTED_PD",
        "DECISION_THRESHOLD",
        "RECOMMENDATION",
        "MODEL_VERSION",
        "CREDIT_SCORE",
        "RISK_TIER",
        "EXPECTED_LOSS",
    }
    if not required.issubset(scored.columns):
        raise GateError("P", "Scored dataset thiếu cột để tạo integration profile reference.")
    low = scored.nsmallest(1, "PREDICTED_PD", keep="first").copy()
    high = scored.nlargest(1, "PREDICTED_PD", keep="first").copy()
    reference = pd.concat([low, high], ignore_index=True).loc[:, sorted(required)]
    reference.insert(0, "PROFILE_CASE", ("LOW_PD_REFERENCE", "HIGH_PD_REFERENCE"))
    _atomic_csv_write(reference, path)
    return reference


def _save_roc_pr_curves(
    evaluation: BinaryEvaluationResult,
    *,
    directory: Path,
) -> tuple[str, str]:
    """Save final frozen-test ROC and PR curves for the model card consumer."""
    directory.mkdir(parents=True, exist_ok=True)
    roc_path = directory / "frozen_test_roc_curve.png"
    pr_path = directory / "frozen_test_precision_recall_curve.png"

    fig, axis = plt.subplots(figsize=(6, 5))
    axis.plot(evaluation.roc_curve.x, evaluation.roc_curve.y, label=f"ROC-AUC = {evaluation.roc_auc:.4f}")
    axis.plot([0, 1], [0, 1], linestyle="--", color="grey", label="No-discrimination baseline")
    axis.set_xlabel("False positive rate")
    axis.set_ylabel("True positive rate (recall)")
    axis.set_title("Frozen-test ROC curve")
    axis.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(roc_path, dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(6, 5))
    axis.plot(
        evaluation.precision_recall_curve.x,
        evaluation.precision_recall_curve.y,
        label="Precision–recall curve",
    )
    axis.set_xlabel("Recall")
    axis.set_ylabel("Precision")
    axis.set_title("Frozen-test precision–recall curve")
    axis.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(pr_path, dpi=160)
    plt.close(fig)
    return str(roc_path), str(pr_path)


def explain_locked_pipeline(
    pipeline: Pipeline,
    definition: CandidateDefinition,
    sample_X: pd.DataFrame,
    *,
    directory: Path,
) -> tuple[str, ...]:
    """Create global and representative local explanations without causal claims."""
    directory.mkdir(parents=True, exist_ok=True)
    preprocessor = pipeline.named_steps["preprocessor"]
    classifier = pipeline.named_steps["classifier"]
    feature_names = np.asarray(preprocessor.get_feature_names_out(), dtype=object)
    sample = sample_X.iloc[: min(len(sample_X), 512)].copy()
    transformed = preprocessor.transform(sample)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    transformed = np.asarray(transformed)
    if transformed.shape[1] != len(feature_names):
        raise GateError("K", "Không map được transformed feature names cho explainability.")

    if definition.family == "logistic":
        coefficients = np.asarray(classifier.coef_).ravel()
        importance = pd.DataFrame(
            {"feature": feature_names, "coefficient": coefficients, "abs_coefficient": np.abs(coefficients)}
        ).nlargest(20, "abs_coefficient").sort_values("coefficient")
        global_path = directory / "logistic_global_coefficients.png"
        fig, axis = plt.subplots(figsize=(9, 7))
        axis.barh(importance["feature"], importance["coefficient"])
        axis.set_xlabel("Logistic regression coefficient")
        axis.set_ylabel("Transformed feature")
        axis.set_title("Global logistic coefficients (non-causal association)")
        fig.tight_layout()
        fig.savefig(global_path, dpi=160)
        plt.close(fig)
        return (str(global_path),)

    if definition.family != "xgboost":
        raise GateError("K", f"Không có explainability strategy cho {definition.family}.")
    try:
        import shap
    except ImportError as exc:
        raise GateError("K", "SHAP không khả dụng cho selected XGBoost model.") from exc

    try:
        explainer = shap.TreeExplainer(classifier)
        shap_values = explainer.shap_values(transformed)
        if isinstance(shap_values, list):
            shap_values = shap_values[-1]
        shap_values = np.asarray(shap_values)
        if shap_values.ndim != 2 or shap_values.shape != transformed.shape:
            raise ValueError("SHAP values không cùng shape với transformed features.")
        mean_abs = np.abs(shap_values).mean(axis=0)
        importance = pd.DataFrame({"feature": feature_names, "mean_abs_shap": mean_abs}).nlargest(
            20, "mean_abs_shap"
        ).sort_values("mean_abs_shap")
        global_path = directory / "xgboost_shap_global_importance.png"
        fig, axis = plt.subplots(figsize=(9, 7))
        axis.barh(importance["feature"], importance["mean_abs_shap"])
        axis.set_xlabel("Mean absolute SHAP value")
        axis.set_ylabel("Transformed feature")
        axis.set_title("Global XGBoost SHAP importance (non-causal contribution)")
        fig.tight_layout()
        fig.savefig(global_path, dpi=160)
        plt.close(fig)

        expected_value = np.asarray(explainer.expected_value).reshape(-1)[-1]
        local_paths: list[str] = [str(global_path)]
        representative_indexes = (0, len(sample) // 2, len(sample) - 1)
        for ordinal, row_index in enumerate(representative_indexes, start=1):
            explanation = shap.Explanation(
                values=shap_values[row_index],
                base_values=expected_value,
                data=transformed[row_index],
                feature_names=feature_names,
            )
            shap.plots.waterfall(explanation, max_display=15, show=False)
            local_path = directory / f"xgboost_shap_local_{ordinal}.png"
            plt.gcf().set_size_inches(9, 6)
            plt.tight_layout()
            plt.savefig(local_path, dpi=160, bbox_inches="tight")
            plt.close()
            local_paths.append(str(local_path))
        return tuple(local_paths)
    except GateError:
        raise
    except Exception as exc:
        raise GateError("K", f"SHAP explainability failed: {exc}") from exc


def create_scored_dataset(
    dataset: pd.DataFrame,
    schema: FeatureSchema,
    pipeline: Pipeline,
    *,
    threshold: float,
    config: RunConfig,
    model_version: str,
) -> pd.DataFrame:
    """Score the full labeled canonical population with explicit policy assumptions."""
    probabilities = pipeline.predict_proba(dataset.loc[:, schema.all_features])[:, 1]
    if not np.isfinite(probabilities).all() or not np.all((probabilities >= 0) & (probabilities <= 1)):
        raise GateError("P", "Full-refit pipeline tạo probability ngoài [0, 1] hoặc không hữu hạn.")
    if config.ead_proxy_column not in dataset.columns:
        raise GateError("M", f"Không có EAD proxy column {config.ead_proxy_column}.")
    ead = pd.to_numeric(dataset[config.ead_proxy_column], errors="coerce")
    if ead.isna().any() or (ead < 0).any():
        raise GateError("M", f"EAD proxy {config.ead_proxy_column} phải non-null và không âm.")
    scores = probability_to_credit_score(probabilities, config=config.score_config)
    tiers = assign_risk_tier(
        scores,
        score_thresholds=config.risk_tier_thresholds,
        tier_labels=config.risk_tier_labels,
    )
    expected_loss = calculate_expected_loss(probabilities, config.lgd_assumption, ead.to_numpy())
    recommendation = np.where(probabilities < threshold, "APPROVE", "REJECT")
    return pd.DataFrame(
        {
            "SK_ID_CURR": dataset["SK_ID_CURR"].to_numpy(),
            "TARGET": dataset["TARGET"].to_numpy(),
            "PREDICTED_PD": probabilities,
            "DECISION_THRESHOLD": np.full(len(dataset), threshold),
            "RECOMMENDATION": recommendation,
            "MODEL_VERSION": np.full(len(dataset), model_version),
            "CREDIT_SCORE": scores,
            "RISK_TIER": tiers,
            "EXPECTED_LOSS": expected_loss,
        }
    )


def validate_production_artifacts(
    root: Path | None = None,
    *,
    schema: FeatureSchema | None = None,
) -> ProductionValidation:
    """Load the serialized artifact and test inference/schema behavior."""
    root = Path(root) if root is not None else project_root()
    dataset, dictionary, _, fingerprint = load_canonical_input(root)
    schema = schema if schema is not None else build_feature_schema(dataset, dictionary)
    artifact_path = root / MODEL_ARTIFACT_PATH
    scored_path = root / SCORED_DATASET_PATH
    record_path = root / FROZEN_TEST_RECORD_PATH
    if not artifact_path.is_file() or not scored_path.is_file() or not record_path.is_file():
        raise GateError("Q", "Thiếu production model artifact, scored dataset hoặc frozen-test record.")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError("Q", f"Frozen-test record không thể đọc: {exc}") from exc
    if record.get("dataset_sha256") != fingerprint.dataset_sha256:
        raise GateError("Q", "Frozen-test record không khớp canonical dataset snapshot.")
    production_artifacts = record.get("production_artifacts")
    if not isinstance(production_artifacts, dict):
        raise GateError("Q", "Frozen-test record thiếu binding đến production artifacts.")
    if production_artifacts.get("model_artifact_sha256") != sha256_file(artifact_path):
        raise GateError("Q", "Model artifact không khớp frozen-test record.")
    if production_artifacts.get("scored_dataset_sha256") != sha256_file(scored_path):
        raise GateError("Q", "Scored dataset không khớp frozen-test record.")
    pipeline = joblib.load(artifact_path)
    sample = dataset.loc[:31, schema.all_features].copy()
    first = pipeline.predict_proba(sample)[:, 1]
    second = pipeline.predict_proba(sample)[:, 1]
    if not np.isfinite(first).all() or not np.all((first >= 0) & (first <= 1)):
        raise GateError("Q", "Loaded artifact không tạo finite PD trong [0, 1].")
    deterministic = bool(np.array_equal(first, second))
    if not deterministic:
        raise GateError("Q", "Loaded artifact không cho repeated inference deterministic.")
    categorical = schema.categorical_features[0] if schema.categorical_features else None
    unknown_safe = True
    if categorical is not None:
        unknown_sample = sample.copy()
        unknown_sample.loc[unknown_sample.index[0], categorical] = "__TV1_UNKNOWN_CATEGORY__"
        try:
            pipeline.predict_proba(unknown_sample)
        except Exception as exc:
            raise GateError("Q", f"Unknown categorical inference failed: {exc}") from exc
    scored = pd.read_parquet(scored_path)
    required_columns = {
        "SK_ID_CURR",
        "TARGET",
        "PREDICTED_PD",
        "DECISION_THRESHOLD",
        "RECOMMENDATION",
        "MODEL_VERSION",
        "CREDIT_SCORE",
        "RISK_TIER",
        "EXPECTED_LOSS",
    }
    if len(scored) != len(dataset) or set(scored.columns) != required_columns:
        raise GateError("Q", "Scored dataset không khớp required model-contract schema.")
    if not scored["SK_ID_CURR"].equals(dataset["SK_ID_CURR"]):
        raise GateError("Q", "Scored dataset không giữ đúng SK_ID_CURR ordering/correspondence.")
    if not scored["TARGET"].equals(dataset["TARGET"]):
        raise GateError("Q", "Scored dataset không giữ đúng TARGET correspondence.")
    if not np.isfinite(scored["PREDICTED_PD"]).all() or not scored["PREDICTED_PD"].between(0, 1).all():
        raise GateError("Q", "Scored dataset có PREDICTED_PD không hợp lệ.")
    full_probabilities = pipeline.predict_proba(dataset.loc[:, schema.all_features])[:, 1]
    if not np.isfinite(full_probabilities).all() or not np.all(
        (full_probabilities >= 0) & (full_probabilities <= 1)
    ):
        raise GateError("Q", "Loaded artifact không tạo finite full-population PD trong [0, 1].")
    if not np.allclose(
        full_probabilities,
        scored["PREDICTED_PD"].to_numpy(dtype=float),
        rtol=1e-7,
        atol=1e-9,
    ):
        raise GateError("Q", "Scored dataset PD không khớp prediction từ loaded artifact.")
    threshold = record.get("threshold")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        raise GateError("Q", "Frozen-test record chứa threshold không hợp lệ.")
    if not np.allclose(scored["DECISION_THRESHOLD"].to_numpy(dtype=float), float(threshold)):
        raise GateError("Q", "Scored dataset không dùng threshold đã khóa trong frozen-test record.")
    expected_recommendation = np.where(full_probabilities < float(threshold), "APPROVE", "REJECT")
    if not np.array_equal(scored["RECOMMENDATION"].to_numpy(), expected_recommendation):
        raise GateError("Q", "Scored dataset recommendation không khớp locked threshold policy.")
    expected_version = production_artifacts.get("model_version")
    if not isinstance(expected_version, str) or scored["MODEL_VERSION"].nunique() != 1:
        raise GateError("Q", "Frozen-test record hoặc scored dataset có MODEL_VERSION không hợp lệ.")
    if scored["MODEL_VERSION"].iloc[0] != expected_version:
        raise GateError("Q", "Scored dataset MODEL_VERSION không khớp frozen-test record.")
    return ProductionValidation(
        probability_min=float(first.min()),
        probability_max=float(first.max()),
        deterministic=deterministic,
        unknown_category_safe=unknown_safe,
        scored_rows=int(len(scored)),
    )


def _candidate_summary_table(results: Sequence[CandidateCVResult]) -> pd.DataFrame:
    """Render comparable development-only metrics for reports and selection."""
    rows = []
    for result in results:
        rows.append(
            {
                "candidate": result.definition.name,
                "family": result.definition.family,
                **result.summary(),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_roc_auc", ascending=False, kind="stable")


def _markdown_table(frame: pd.DataFrame, *, decimal_places: int = 6) -> str:
    """Format report data without external tabulation dependencies."""
    if frame.empty:
        return ""
    visible = frame.copy()
    for column in visible.columns:
        if pd.api.types.is_float_dtype(visible[column]):
            visible[column] = visible[column].map(lambda value: f"{value:.{decimal_places}f}")
    headers = list(visible.columns)
    rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    rows.extend("| " + " | ".join(map(str, row)) + " |" for row in visible.itertuples(index=False, name=None))
    return "\n".join(rows)


def render_model_card(
    result: WorkflowResult,
    *,
    selected_definition: CandidateDefinition,
    root: Path,
    config: RunConfig,
) -> str:
    """Create the human-readable, contract-oriented model card."""
    cv_table = _candidate_summary_table(result.candidate_results)
    threshold_table = result.threshold_table.sort_values("threshold", kind="stable")
    confusion = result.frozen_test_evaluation.confusion
    split = result.split
    return f"""# TV1 Model Card — {result.model_version}

## Dataset fingerprint

- Canonical dataset: `{CANONICAL_DATASET_PATH.as_posix()}`
- SHA-256: `{result.fingerprint.dataset_sha256}`
- Manifest output hash: `{result.fingerprint.manifest_output_sha256}`
- Shape: {result.fingerprint.row_count:,} rows × {result.fingerprint.column_count} columns
- TARGET distribution: 0 = {result.fingerprint.target_distribution['0']:,}; 1 = {result.fingerprint.target_distribution['1']:,}
- Manifest provenance: branch `{result.fingerprint.manifest_branch}`, commit `{result.fingerprint.manifest_commit}`

## Leakage-safe feature and split policy

- `y = TARGET`; `SK_ID_CURR` and downstream scoring/output columns are excluded from X.
- Features: {len(result.schema.numeric_features)} numeric and {len(result.schema.categorical_features)} categorical ({len(result.schema.all_features)} total).
- Review-only distribution features retained without automatic removal: {", ".join(result.schema.review_only_features)}.
- Fixed seed: `{split.random_state}`; development = {split.row_counts['development']:,} rows ({split.target_rates['development']:.4%} default), frozen test = {split.row_counts['frozen_test']:,} rows ({split.target_rates['frozen_test']:.4%} default).
- Development-ID SHA-256: `{stable_ids_hash(split.development.ids)}`
- Frozen-test-ID SHA-256: `{stable_ids_hash(split.frozen_test.ids)}`
- No ID overlap: verified before any preprocessing/model fit.
- Imputation, scaling and categorical encoding are inside each CV/model pipeline. No transformer was fit on the frozen test set.

## Development-only candidate comparison

{_markdown_table(cv_table)}

SMOTE was intentionally not used: class-weight comparison is sufficient for this controlled run, while ordinary SMOTE over sparse one-hot categorical features is not an appropriate default. No frozen-test result was used for selection.

## Locked model configuration

- `MODEL_CONFIG_FROZEN = TRUE`
- Selected candidate: `{selected_definition.name}` ({selected_definition.family})
- Parameters: `{json.dumps(selected_definition.parameters, sort_keys=True)}`
- Selection rule: {result.selection.rationale}
- Threshold-selection source: development-only out-of-fold probabilities.
- Locked technical threshold: `{result.threshold:.2f}`, selected by maximum F1; this is not an approved business-cost threshold.

## Development threshold trade-off table

{_markdown_table(threshold_table)}

## One-time frozen-test evaluation

- ROC-AUC: `{result.frozen_test_evaluation.roc_auc:.6f}`
- PR-AUC: `{result.frozen_test_pr_auc:.6f}`
- Precision: `{result.frozen_test_evaluation.precision:.6f}`
- Recall: `{result.frozen_test_evaluation.recall:.6f}`
- F1: `{result.frozen_test_evaluation.f1:.6f}`
- Accuracy (supplementary only): `{result.frozen_test_evaluation.accuracy:.6f}`
- Confusion matrix at locked threshold `{result.threshold:.2f}`: TN={int(confusion[0, 0]):,}, FP={int(confusion[0, 1]):,}, FN={int(confusion[1, 0]):,}, TP={int(confusion[1, 1]):,}.

This is the single unbiased frozen-test evaluation. The configuration must not be retuned from this result.
The local control record `{FROZEN_TEST_RECORD_PATH.as_posix()}` prevents an accidental rerun against the same frozen IDs.

## Explainability

Artifacts: {", ".join(f"`{path}`" for path in result.explanation_paths)}.

These explanations describe how features contribute to model predictions; they do not establish that any feature causes default.

## Scoring and Expected-Loss assumptions

- PD-to-score uses bad-to-good odds with base score 600, base odds 0.05, PDO 20, clipped to [300, 850]. Higher PD produces lower score.
- Risk tiers by score: `HIGH_RISK` ≤ 550, `MEDIUM_RISK` ≤ 650, `LOW_RISK` > 650. This is a technical presentation policy, not an approved lending policy.
- Recommendation is technical only: `APPROVE` when PD < locked threshold; otherwise `REJECT`.
- Expected Loss is the scenario `PD × LGD × EAD`, with LGD assumed at {config.lgd_assumption:.2f} and `{config.ead_proxy_column}` used only as an EAD proxy, not claimed to be true EAD.
- Frozen-test scenario: approved={result.policy_summary.approved_count:,}, rejected={result.policy_summary.rejected_count:,}, observed defaults among approved={result.policy_summary.observed_defaults_approved:,}, expected loss of approved portfolio={result.policy_summary.expected_loss_approved:,.2f}.
- Full scored portfolio scenario expected loss={result.full_portfolio_expected_loss:,.2f}; this is not profit, realised loss, or a causal business-benefit claim.

## Production refit and handoff

- `FINAL_CONFIGURATION_FROZEN = TRUE`
- The locked pipeline was refit once on all {result.fingerprint.row_count:,} labeled canonical rows only after frozen-test evaluation. No full-training metric is presented as generalization evidence.
- Artifact: `{MODEL_ARTIFACT_PATH.as_posix()}`
- Scored dataset: `{SCORED_DATASET_PATH.as_posix()}`
- TV3 integration reference cases: `{INTEGRATION_PROFILE_PATH.as_posix()}` (two anonymized `SK_ID_CURR` cases with expected scored output).
- Reproducibility verification: deterministic={result.validation.deterministic}, unknown-category-safe={result.validation.unknown_category_safe}, PD range on fresh load=[{result.validation.probability_min:.6f}, {result.validation.probability_max:.6f}].
- Re-run command: `& .\\.venv\\Scripts\\python.exe -m src.models.modeling_pipeline`
"""


def run_full_workflow(root: Path | None = None, *, config: RunConfig | None = None) -> WorkflowResult:
    """Execute Gates A–Q in order; raises ``GateError`` at the first failure."""
    root = Path(root) if root is not None else project_root()
    config = config or RunConfig()
    dataset, dictionary, _, fingerprint = load_canonical_input(root)
    schema = build_feature_schema(dataset, dictionary)

    try:
        split = create_frozen_test_split(
            dataset,
            random_state=config.random_state,
            test_size=config.frozen_test_size,
        )
    except (ValueError, RuntimeError) as exc:
        raise GateError("C", str(exc)) from exc
    # Fail before any development work if this output namespace has already
    # consumed the same frozen test; this prevents an expensive accidental rerun.
    _assert_frozen_test_unused(root, fingerprint=fingerprint, split=split)

    # Gate D is structural: every candidate calls this factory inside each CV fold.
    try:
        build_preprocessor(
            schema.numeric_features,
            schema.categorical_features,
            available_columns=split.development.X.columns,
        )
    except ValueError as exc:
        raise GateError("D", str(exc)) from exc

    definitions = candidate_definitions()
    results: list[CandidateCVResult] = []
    for definition in definitions:
        gate = "E" if definition.family == "logistic" else "G"
        try:
            results.append(
                run_candidate_cv(
                    definition,
                    split.development.X,
                    split.development.y,
                    schema,
                    config=config,
                )
            )
        except GateError:
            raise
        except Exception as exc:
            raise GateError(gate, f"{definition.name} CV failed: {exc}") from exc

    selection = select_candidate(results)
    if selection.needs_human_decision:
        raise GateError("H", "NEEDS_HUMAN_DECISION: " + selection.rationale)
    selected_result = next(result for result in results if result.definition.name == selection.selected_name)
    selected_definition = selected_result.definition
    threshold, threshold_table = choose_threshold_from_oof(
        split.development.y,
        selected_result.oof_probabilities,
        config=config,
    )

    locked_development_pipeline = build_candidate_pipeline(
        selected_definition,
        schema,
        available_columns=split.development.X.columns,
        config=config,
    )
    try:
        locked_development_pipeline.fit(split.development.X, split.development.y)
        frozen_evaluation, frozen_pr_auc, frozen_probabilities = evaluate_frozen_test(
            locked_development_pipeline,
            split.frozen_test.X,
            split.frozen_test.y,
            threshold=threshold,
        )
    except Exception as exc:
        raise GateError("J", f"Frozen-test evaluation failed: {exc}") from exc
    _write_frozen_test_record(
        root,
        fingerprint=fingerprint,
        split=split,
        definition=selected_definition,
        threshold=threshold,
        evaluation=frozen_evaluation,
        pr_auc=frozen_pr_auc,
    )

    figure_directory = root / FIGURE_DIRECTORY
    curve_paths = _save_roc_pr_curves(frozen_evaluation, directory=figure_directory)
    explanation_paths = explain_locked_pipeline(
        locked_development_pipeline,
        selected_definition,
        split.development.X,
        directory=figure_directory,
    )

    if config.ead_proxy_column not in split.frozen_test.X.columns:
        raise GateError("M", f"Frozen test lacks EAD proxy {config.ead_proxy_column}.")
    frozen_ead = pd.to_numeric(split.frozen_test.X[config.ead_proxy_column], errors="coerce")
    if frozen_ead.isna().any() or (frozen_ead < 0).any():
        raise GateError("M", "Frozen-test EAD proxy contains missing or negative values.")
    policy_summary = evaluate_threshold_policy(
        split.frozen_test.y,
        frozen_probabilities,
        config.lgd_assumption,
        frozen_ead.to_numpy(),
        threshold=threshold,
    )

    # Gates N/O: configuration is now fixed, then refit once on all labeled rows.
    model_version = f"{config.model_version_prefix}-{fingerprint.dataset_sha256[:8]}"
    final_pipeline = build_candidate_pipeline(
        selected_definition,
        schema,
        available_columns=dataset.loc[:, schema.all_features].columns,
        config=config,
    )
    try:
        final_pipeline.fit(dataset.loc[:, schema.all_features], dataset["TARGET"])
    except Exception as exc:
        raise GateError("O", f"Full-labeled-data refit failed: {exc}") from exc

    scored = create_scored_dataset(
        dataset,
        schema,
        final_pipeline,
        threshold=threshold,
        config=config,
        model_version=model_version,
    )
    full_portfolio_expected_loss = float(scored["EXPECTED_LOSS"].sum())
    _atomic_joblib_dump(final_pipeline, root / MODEL_ARTIFACT_PATH)
    _atomic_parquet_write(scored, root / SCORED_DATASET_PATH)
    create_integration_profile_reference(scored, path=root / INTEGRATION_PROFILE_PATH)
    _record_production_artifacts(root, model_version=model_version)

    provisional_result = WorkflowResult(
        fingerprint=fingerprint,
        schema=schema,
        split=split,
        candidate_results=tuple(results),
        selection=selection,
        threshold=threshold,
        threshold_table=threshold_table,
        frozen_test_evaluation=frozen_evaluation,
        frozen_test_pr_auc=frozen_pr_auc,
        policy_summary=policy_summary,
        full_portfolio_expected_loss=full_portfolio_expected_loss,
        model_version=model_version,
        explanation_paths=curve_paths + explanation_paths,
        validation=ProductionValidation(0.0, 0.0, False, False, 0),
    )
    validation = validate_production_artifacts(root, schema=schema)
    result = WorkflowResult(
        fingerprint=provisional_result.fingerprint,
        schema=provisional_result.schema,
        split=provisional_result.split,
        candidate_results=provisional_result.candidate_results,
        selection=provisional_result.selection,
        threshold=provisional_result.threshold,
        threshold_table=provisional_result.threshold_table,
        frozen_test_evaluation=provisional_result.frozen_test_evaluation,
        frozen_test_pr_auc=provisional_result.frozen_test_pr_auc,
        policy_summary=provisional_result.policy_summary,
        full_portfolio_expected_loss=provisional_result.full_portfolio_expected_loss,
        model_version=provisional_result.model_version,
        explanation_paths=provisional_result.explanation_paths,
        validation=validation,
    )
    _atomic_text_write(
        render_model_card(
            result,
            selected_definition=selected_definition,
            root=root,
            config=config,
        ),
        root / MODEL_CARD_PATH,
    )
    return result


def _result_summary(result: WorkflowResult) -> dict[str, Any]:
    """Produce compact machine-readable CLI output without serialising arrays."""
    return {
        "status": "SUCCESS",
        "model_version": result.model_version,
        "dataset_sha256": result.fingerprint.dataset_sha256,
        "selected_candidate": result.selection.selected_name,
        "threshold": result.threshold,
        "frozen_test_metrics": {
            **result.frozen_test_evaluation.metrics_dict(),
            "pr_auc": result.frozen_test_pr_auc,
        },
        "artifact": str(MODEL_ARTIFACT_PATH),
        "scored_dataset": str(SCORED_DATASET_PATH),
        "model_card": str(MODEL_CARD_PATH),
        "figures": list(result.explanation_paths),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI for the one-command gated TV1 run and fresh-load verification."""
    parser = argparse.ArgumentParser(description="Run the gated TV1 modeling pipeline.")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Load and verify existing production artifacts without training.",
    )
    args = parser.parse_args(argv)
    try:
        if args.verify_only:
            validation = validate_production_artifacts()
            print(json.dumps({"status": "SUCCESS", "verification": asdict(validation)}, indent=2))
        else:
            print(json.dumps(_result_summary(run_full_workflow()), indent=2))
    except GateError as exc:
        print(json.dumps({"status": "FAILED", "gate": exc.gate, "error": str(exc)}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
