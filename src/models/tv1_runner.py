"""Stage runner nhỏ cho workflow Modeling của TV1."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

from src.config import (
    CANONICAL_DATASET_PATH,
    DATA_DICTIONARY_PATH,
    DATASET_ID,
    DATASET_MANIFEST_PATH,
    MODELING_DIR,
    REPORTS_DIR,
)
from src.models.data_split import (
    SplitValidationError,
    create_or_load_frozen_split,
)
from src.models.evaluation import evaluate_binary_classifier
from src.models.modeling_pipeline import (
    GateError,
    build_baseline_feature_selection,
    build_feature_schema,
    build_logistic_pipeline,
    load_canonical_input,
    FeatureSchema,
)


STAGE = "ml-lc-02"
STAGE_TITLE = "Freeze deterministic train/validation/frozen-test split"
ML_LC_03_STAGE = "ml-lc-03"
ML_LC_03_TITLE = "Logistic Regression baseline"
ML_LC_03_REFERENCE_THRESHOLD = 0.5
ML_LC_03_MAX_ITER = 1000
ML_LC_03_SOLVER = "lbfgs"
ML_LC_03_PENALTY = "l2"
ML_LC_04_STAGE = "ml-lc-04"
ML_LC_04_TITLE = "Logistic Regression imbalance experiment"
ML_LC_04_REFERENCE_THRESHOLD = 0.5
ML_LC_04_CLASS_WEIGHT = "balanced"


def _stage_paths(reports_dir: Path, stage: str) -> tuple[Path, Path]:
    stage_dir = reports_dir / "tv1_stages"
    return stage_dir / f"{stage}.md", stage_dir / "state" / f"{stage}.json"


def _write_stage_evidence(
    reports_dir: Path,
    *,
    stage: str,
    title: str,
    status: str,
    message: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    report_path, marker_path = _stage_paths(reports_dir, stage)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker = {
        "stage": stage,
        "title": title,
        "status": status,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_path": str(report_path),
        "payload": payload,
    }
    marker_path.write_text(json.dumps(marker, indent=2, ensure_ascii=False), encoding="utf-8")
    report = "\n".join([
        f"# {stage.upper()} — {title}",
        "",
        f"**Status: {status}**",
        "",
        message,
        "",
        "```json",
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        "```",
        "",
    ])
    report_path.write_text(report, encoding="utf-8")
    return {
        "status": status,
        "report_path": str(report_path),
        "marker_path": str(marker_path),
        "message": message,
    }


def run_ml_lc_02(
    *,
    canonical_path: Path = CANONICAL_DATASET_PATH,
    dictionary_path: Path = DATA_DICTIONARY_PATH,
    manifest_path: Path = DATASET_MANIFEST_PATH,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
    random_state: int = 42,
    test_size: float = 0.20,
    validation_size: float = 0.20,
) -> dict[str, Any]:
    """Run ML-LC-02 without fitting preprocessing or a model."""

    dataset, dictionary, tv2_manifest = load_canonical_input(
        dataset_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
    )
    if tv2_manifest.get("dataset_id") != DATASET_ID:
        raise GateError("TV2 manifest dataset_id không khớp Lending Club dataset.")
    if tv2_manifest.get("run_status") != "PASS" or tv2_manifest.get("quality_status") != "PASS":
        raise GateError("TV2 handoff manifest chưa có run_status/quality_status PASS.")
    if tv2_manifest.get("leakage_gate") != "PASS":
        raise GateError("TV2 handoff manifest leakage_gate chưa PASS.")
    expected_rows = tv2_manifest.get("labeled_rows")
    if not isinstance(expected_rows, int) or expected_rows != len(dataset):
        raise GateError("TV2 manifest labeled_rows không khớp canonical dataset.")

    feature_schema = build_feature_schema(dataset, dictionary)
    if not feature_schema.approved_features:
        raise GateError("ML-LC-01 không trả về approved model features.")

    frozen = create_or_load_frozen_split(
        dataset,
        output_dir=output_dir,
        canonical_path=canonical_path,
        dataset_id=DATASET_ID,
        expected_source_rows=expected_rows,
        random_state=random_state,
        test_size=test_size,
        validation_size=validation_size,
    )
    audit = frozen.audit
    payload = {
        "source_artifact": str(canonical_path),
        "source_rows": audit["source_rows"],
        "approved_feature_count_from_ml_lc_01": len(feature_schema.approved_features),
        "split_ratios": {
            "train": 1 - test_size - validation_size,
            "validation": validation_size,
            "frozen_test": test_size,
        },
        "random_state": random_state,
        "stratified": True,
        "train_rows": audit["partition_rows"]["train"],
        "validation_rows": audit["partition_rows"]["validation"],
        "frozen_test_rows": audit["partition_rows"]["test"],
        "target_counts": audit["target_counts"],
        "full_target_counts": audit["full_target_counts"],
        "default_rates": audit["default_rates"],
        "overlap_checks": audit["overlap_counts"],
        "union_rows": audit["union_rows"],
        "coverage_status": audit["coverage_status"],
        "stratification_rate_differences": audit["stratification_rate_differences"],
        "deterministic": frozen.manifest["deterministic"],
        "frozen": frozen.manifest["frozen"],
        "reused_existing_artifacts": frozen.reused,
        "artifact_paths": {key: str(path) for key, path in frozen.artifact_paths.items()},
        "preprocessing_fitted": False,
        "model_trained": False,
    }
    _write_stage_evidence(
        reports_dir,
        stage=STAGE,
        title=STAGE_TITLE,
        status="PASS",
        message="ML-LC-02 hoàn tất; split đã được validate và persist/reuse an toàn.",
        payload=payload,
    )
    return payload


def _require_ml_lc_02_pass(reports_dir: Path) -> None:
    marker_path = reports_dir / "tv1_stages" / "state" / f"{STAGE}.json"
    if not marker_path.is_file():
        raise GateError(f"ML-LC-02 marker chưa tồn tại: {marker_path}")
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GateError(f"ML-LC-02 marker không đọc được: {marker_path}") from exc
    if marker.get("status") != "PASS":
        raise GateError(f"ML-LC-02 chưa PASS: {marker.get('status')}")


def _require_ml_lc_03_pass(
    reports_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Load and validate the canonical ML-LC-03 baseline handoff."""

    marker_path = reports_dir / "tv1_stages" / "state" / f"{ML_LC_03_STAGE}.json"
    if not marker_path.is_file():
        raise GateError(f"ML-LC-03 marker chưa tồn tại: {marker_path}")
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GateError(f"ML-LC-03 marker không đọc được: {marker_path}") from exc
    if marker.get("status") != "PASS":
        raise GateError(f"ML-LC-03 chưa PASS: {marker.get('status')}")

    manifest_path = output_dir / "ml_lc_03_manifest.json"
    model_path = output_dir / "logistic_baseline.joblib"
    if not manifest_path.is_file() or not model_path.is_file():
        raise GateError(
            "ML-LC-03 PASS marker tồn tại nhưng canonical baseline artifact thiếu: "
            f"{manifest_path}, {model_path}"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GateError(f"ML-LC-03 manifest không đọc được: {manifest_path}") from exc
    if manifest.get("stage") != ML_LC_03_STAGE or manifest.get("status") != "PASS":
        raise GateError("ML-LC-03 manifest không ở trạng thái PASS.")
    if manifest.get("class_weight") is not None:
        raise GateError("ML-LC-03 baseline phải giữ class_weight=None.")
    if manifest.get("threshold_selected") is not False:
        raise GateError("ML-LC-03 không được chọn threshold.")
    return manifest


def _sha256(path: Path) -> str:
    """Return a stable digest for an artifact-preservation check."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _select_partition_rows(
    dataset: pd.DataFrame,
    ids: pd.Series,
    target: pd.Series,
    *,
    id_column: str,
    target_column: str,
) -> pd.DataFrame:
    """Select rows in frozen-artifact order and verify target preservation."""

    indexed = dataset.set_index(id_column, drop=True)
    selected = indexed.loc[ids.tolist()].copy()
    selected.insert(0, id_column, selected.index)
    selected.reset_index(drop=True, inplace=True)
    if selected[target_column].astype(int).tolist() != target.astype(int).tolist():
        raise GateError("Target của partition không khớp canonical dataset.")
    return selected


def _atomic_write_text(path: Path, content: str) -> None:
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        partial.write_text(content, encoding="utf-8")
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def _atomic_write_dataframe(path: Path, frame: pd.DataFrame, *, format: str) -> None:
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if format == "parquet":
            frame.to_parquet(partial, index=False)
        elif format == "csv":
            frame.to_csv(partial, index=False)
        else:  # pragma: no cover - private helper guard
            raise ValueError(f"Unsupported dataframe format: {format}")
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def _atomic_joblib_dump(path: Path, value: Any) -> None:
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        joblib.dump(value, partial)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def _fit_logistic_experiment(
    dataset: pd.DataFrame,
    selection: Any,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    *,
    class_weight: str | dict[str, float] | None,
    max_iter: int,
    solver: str,
    penalty: str,
    random_state: int,
) -> tuple[Any, dict[str, Any]]:
    """Fit one Logistic experiment with one explicit convergence fallback."""

    initial_max_iter = max_iter
    fallback_used = False
    convergence_messages: list[str] = []
    started = time.perf_counter()
    while True:
        pipeline = build_logistic_pipeline(
            dataset,
            FeatureSchema(
                approved_features=tuple(selection.approved_features),
                excluded_features=(),
            ),
            feature_columns=selection.baseline_features,
            class_weight=class_weight,
            max_iter=max_iter,
            solver=solver,
            penalty=penalty,
            random_state=random_state,
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pipeline.fit(x_train, y_train)
        convergence = [warning for warning in caught if issubclass(warning.category, ConvergenceWarning)]
        convergence_messages = [str(warning.message) for warning in convergence]
        model = pipeline.named_steps["model"]
        n_iter = np.asarray(getattr(model, "n_iter_", []), dtype=int)
        converged = not convergence and (n_iter.size == 0 or bool(np.all(n_iter < max_iter)))
        if converged:
            duration = time.perf_counter() - started
            return pipeline, {
                "max_iter": max_iter,
                "n_iter": n_iter.tolist(),
                "converged": True,
                "convergence_warnings": convergence_messages,
                "fallback_used": fallback_used,
                "fit_seconds": duration,
            }
        if fallback_used:
            raise GateError(
                "Logistic experiment không hội tụ sau max_iter fallback: "
                f"{convergence_messages}"
            )
        convergence_messages.append(
            f"Initial max_iter={initial_max_iter} did not converge; retrying once at max_iter=2000."
        )
        max_iter = 2000
        fallback_used = True


def _fit_logistic_baseline(
    dataset: pd.DataFrame,
    selection: Any,
    x_train: pd.DataFrame,
    y_train: pd.Series,
) -> tuple[Any, dict[str, Any]]:
    """Fit the untreated ML-LC-03 baseline without changing its contract."""

    return _fit_logistic_experiment(
        dataset,
        selection,
        x_train,
        y_train,
        class_weight=None,
        max_iter=ML_LC_03_MAX_ITER,
        solver=ML_LC_03_SOLVER,
        penalty=ML_LC_03_PENALTY,
        random_state=42,
    )


def _metrics_payload(result: Any) -> dict[str, Any]:
    return {
        "roc_auc": float(result.roc_auc),
        "pr_auc": float(result.pr_auc),
        "precision": float(result.precision),
        "recall": float(result.recall),
        "f1": float(result.f1),
        "accuracy": float(result.accuracy),
        "reference_threshold": float(result.threshold),
        "confusion_matrix": result.confusion.astype(int).tolist(),
    }


def _render_ml_lc_03_report(manifest: dict[str, Any]) -> str:
    metrics = manifest["validation_metrics"]
    confusion = metrics["confusion_matrix"]
    excluded = manifest["excluded_safe_features"]
    reasons = manifest["excluded_safe_feature_reasons"]
    excluded_lines = "\n".join(
        f"- `{feature}`: {reasons[feature]}" for feature in excluded
    ) or "- Không có feature safe nào bị loại khỏi baseline."
    return f"""# ML-LC-03 Logistic Regression Baseline

## Purpose

Huấn luyện baseline Logistic Regression bắt buộc trên train partition đã frozen,
đánh giá một lần trên validation và giữ frozen test chưa mở cho đánh giá.

## Data used

- Canonical source: `{manifest['canonical_path']}`
- Train: **{manifest['train_rows']:,}** dòng
- Validation: **{manifest['validation_rows']:,}** dòng
- Frozen test: **{manifest['frozen_test_rows']:,}** dòng chỉ ghi metadata; không dùng để train/evaluate
- Train/validation không overlap; frozen test evaluation rows: **0**

## Features

- ML-LC-01 approved model-safe features: **{manifest['approved_feature_count']}**
- Actual Logistic baseline input features: **{manifest['actual_baseline_feature_count']}**
- Forbidden feature list: `[]`
- Feature audit: `{manifest['feature_audit_path']}`

Các cột model-safe nhưng không đưa trực tiếp vào baseline:

{excluded_lines}

## Preprocessing

- Numeric: median imputation + `StandardScaler`.
- Categorical: most-frequent imputation + `OneHotEncoder(handle_unknown='ignore')`.
- Date-like raw fields không one-hot trực tiếp; dùng feature engineered số đã có hoặc loại khỏi baseline theo audit.
- Toàn bộ preprocessing được fit qua pipeline trên **train only**; không fit validation/test.
- Transformed feature count: **{manifest['transformed_feature_count']}**; sparse output: **{manifest['sparse_output']}**.

## Model

- Model: Logistic Regression
- Solver: `{manifest['solver']}`
- Penalty: `{manifest['penalty']}`
- `class_weight`: **{manifest['class_weight']}**
- `random_state`: **{manifest['random_state']}**
- `max_iter`: **{manifest['max_iter']}**
- Convergence: **{manifest['converged']}**
- Fit duration: **{manifest['fit_seconds']:.2f} seconds**

## Validation results

Reference threshold = **0.5**. Đây chưa phải final threshold; ML-LC-07 mới được chọn threshold.

- ROC-AUC: **{metrics['roc_auc']:.6f}**
- PR-AUC / Average Precision: **{metrics['pr_auc']:.6f}**
- Precision: **{metrics['precision']:.6f}**
- Recall: **{metrics['recall']:.6f}**
- F1: **{metrics['f1']:.6f}**
- Accuracy: **{metrics['accuracy']:.6f}**
- Confusion matrix `[ [TN, FP], [FN, TP] ]`: `{confusion}`

Validation predictions: `{manifest['validation_prediction_path']}`

## Leakage safeguards

- Feature list lấy từ `build_feature_schema()` và shared column policy của ML-LC-01.
- Không dùng `loan_id`, `target`, `loan_status`, policy-derived, geography hoặc POST_LOAN fields.
- Không dùng frozen-test outcomes/probabilities.
- Không resampling, không `class_weight='balanced'`, không XGBoost và không threshold search.

## Limitations

- Đây chỉ là untreated Logistic Regression baseline, chưa phải model cuối.
- Chưa có imbalance treatment hoặc threshold optimization.
- Frozen test vẫn sealed cho các stage sau.
- Association/prediction không phải causal effect.
"""


def _render_ml_lc_04_report(manifest: dict[str, Any]) -> str:
    """Render the beginner-readable ML-LC-04 comparison report."""

    comparison_lines = "\n".join(
        f"| {row['metric']} | {row['baseline']:.6f} | "
        f"{row['weighted']:.6f} | {row['difference']:+.6f} |"
        for row in manifest["metric_comparison"]
    )
    confusion = manifest["confusion_matrix_comparison"]
    confusion_lines = "\n".join(
        f"| {name} | {confusion[name]['baseline']} | "
        f"{confusion[name]['weighted']} | {confusion[name]['difference']:+d} |"
        for name in ("TN", "FP", "FN", "TP")
    )
    interpretation = manifest["interpretation"]
    return f"""# ML-LC-04 — Imbalance Experiment

## Why this experiment exists

Target `default` không cân bằng (xấp xỉ 80/20) và baseline ở threshold
tham chiếu 0.5 có recall thấp. Stage này kiểm tra riêng liệu
`class_weight='balanced'` có thay đổi khả năng phát hiện default trên
**validation** hay không.

## Controlled experiment

- Baseline: ML-LC-03 Logistic Regression với `class_weight=None`.
- Weighted: Logistic Regression với `class_weight='balanced'`.
- Giữ nguyên train/validation membership, feature list, preprocessing,
  solver, penalty, `max_iter` và `random_state`.
- Không SMOTE, resampling, threshold search, XGBoost hoặc model selection
  bằng frozen test.

## Data

- Train: **{manifest['train_rows']:,}** dòng
- Validation: **{manifest['validation_rows']:,}** dòng
- Frozen test: **{manifest['frozen_test_rows']:,}** dòng, sealed; không train,
  predict hoặc tính metric.
- Approved features: **{manifest['approved_feature_count']}**
- Actual baseline/weighted input features: **{manifest['actual_feature_count']}**
- Transformed features: **{manifest['transformed_feature_count']}**, sparse output:
  **{manifest['sparse_output']}**

## Results

Reference threshold = **{manifest['reference_threshold']}**; đây không phải
threshold cuối và chưa có threshold nào được chọn.

| Metric | Baseline | Weighted | Difference (Weighted - Baseline) |
|---|---:|---:|---:|
{comparison_lines}

## Confusion matrix comparison

| Cell | Baseline | Weighted | Difference |
|---|---:|---:|---:|
{confusion_lines}

Baseline matrix `[ [TN, FP], [FN, TP] ]`:
`{manifest['baseline_metrics']['confusion_matrix']}`

Weighted matrix `[ [TN, FP], [FN, TP] ]`:
`{manifest['weighted_metrics']['confusion_matrix']}`

## Weighted model

- Solver: `{manifest['solver']}`
- Penalty: `{manifest['penalty']}`
- `max_iter`: **{manifest['max_iter']}**
- `class_weight`: **{manifest['weighted_class_weight']}**
- `random_state`: **{manifest['random_state']}**
- Convergence: **{manifest['weighted_converged']}**, `n_iter={manifest['weighted_n_iter']}`
- Preprocessing fit: **train only**

Weighted validation predictions:
`{manifest['weighted_validation_prediction_path']}`

Weighted model artifact:
`{manifest['weighted_model_artifact_path']}`

## Interpretation

{interpretation}

Đây là trade-off quan sát được trên validation, không phải kết luận nhân quả.

## Decision

ML-LC-04 chỉ là experiment. Chưa tuyên bố weighted model là final model.
ML-LC-06 mới thực hiện candidate selection theo tiêu chí được khóa trước.

## Leakage and frozen-test safeguards

- Feature schema tiếp tục lấy từ ML-LC-01; không thêm feature mới.
- Raw date fields vẫn không được one-hot trực tiếp.
- `frozen_test_used_for_training = false`.
- `frozen_test_used_for_evaluation = false`.
- `frozen_test_used_for_selection = false`.
- `threshold_selected = false`.

## Limitations

- Threshold 0.5 chỉ là reference.
- Chưa threshold optimization, resampling, XGBoost, frozen-test evaluation,
  explainability hoặc scoring/risk tier.
- Kết quả validation không tự quyết định model cuối.
"""


def run_ml_lc_03(
    *,
    canonical_path: Path = CANONICAL_DATASET_PATH,
    dictionary_path: Path = DATA_DICTIONARY_PATH,
    manifest_path: Path = DATASET_MANIFEST_PATH,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
    model_artifact_path: Path | None = None,
    validation_prediction_path: Path | None = None,
    feature_audit_path: Path | None = None,
    baseline_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Train and evaluate the untreated ML-LC-03 Logistic baseline."""

    _require_ml_lc_02_pass(reports_dir)
    dataset, dictionary, tv2_manifest = load_canonical_input(
        dataset_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
    )
    if tv2_manifest.get("dataset_id") != DATASET_ID:
        raise GateError("TV2 manifest dataset_id không khớp Lending Club dataset.")
    if tv2_manifest.get("run_status") != "PASS" or tv2_manifest.get("quality_status") != "PASS":
        raise GateError("TV2 handoff manifest chưa có run_status/quality_status PASS.")
    if tv2_manifest.get("leakage_gate") != "PASS":
        raise GateError("TV2 handoff manifest leakage_gate chưa PASS.")
    expected_rows = tv2_manifest.get("labeled_rows")
    if not isinstance(expected_rows, int) or expected_rows != len(dataset):
        raise GateError("TV2 manifest labeled_rows không khớp canonical dataset.")

    schema = build_feature_schema(dataset, dictionary)
    if len(schema.approved_features) != int(tv2_manifest.get("baseline_feature_count", len(schema.approved_features))):
        raise GateError("Approved feature count không khớp TV2 handoff manifest.")

    frozen = create_or_load_frozen_split(
        dataset,
        output_dir=output_dir,
        canonical_path=canonical_path,
        dataset_id=DATASET_ID,
        expected_source_rows=expected_rows,
        random_state=42,
        test_size=0.20,
        validation_size=0.20,
    )
    if not frozen.manifest.get("frozen") or frozen.manifest.get("stage_status") != "PASS":
        raise GateError("ML-LC-02 frozen split chưa PASS/frozen.")

    train_frame = _select_partition_rows(
        dataset,
        frozen.split.train.ids,
        frozen.split.train.y,
        id_column="loan_id",
        target_column="target",
    )
    validation_frame = _select_partition_rows(
        dataset,
        frozen.split.validation.ids,
        frozen.split.validation.y,
        id_column="loan_id",
        target_column="target",
    )
    selection = build_baseline_feature_selection(dataset, schema, audit_frame=train_frame)
    if not selection.baseline_features:
        raise GateError("Actual Logistic baseline feature list đang rỗng.")
    categorical_concerns = selection.audit.loc[
        selection.audit["used_in_baseline"] & selection.audit["cardinality_concern"],
        "feature_name",
    ].tolist()
    if categorical_concerns:
        raise GateError(
            "Categorical cardinality vượt ngưỡng, không one-hot mù: "
            f"{categorical_concerns}"
        )

    output_dir = Path(output_dir)
    model_path = Path(model_artifact_path or output_dir / "logistic_baseline.joblib")
    prediction_path = Path(validation_prediction_path or output_dir / "ml_lc_03_validation_predictions.parquet")
    audit_path = Path(feature_audit_path or output_dir / "ml_lc_03_feature_audit.csv")
    baseline_manifest_path = Path(baseline_manifest_path or output_dir / "ml_lc_03_manifest.json")

    x_train = train_frame.loc[:, list(selection.baseline_features)]
    y_train = train_frame["target"].astype(int)
    x_validation = validation_frame.loc[:, list(selection.baseline_features)]
    y_validation = validation_frame["target"].astype(int)

    pipeline, fit_info = _fit_logistic_baseline(dataset, selection, x_train, y_train)
    probabilities = pipeline.predict_proba(x_validation)[:, 1]
    if len(probabilities) != len(validation_frame):
        raise GateError("Validation prediction row count không khớp validation partition.")
    if not np.isfinite(probabilities).all() or not np.all((probabilities >= 0) & (probabilities <= 1)):
        raise GateError("Validation predicted_pd phải hữu hạn và nằm trong [0, 1].")
    if validation_frame["loan_id"].isna().any() or not validation_frame["loan_id"].is_unique:
        raise GateError("Validation prediction loan_id phải non-null và unique.")

    evaluation = evaluate_binary_classifier(
        y_validation,
        probabilities,
        threshold=ML_LC_03_REFERENCE_THRESHOLD,
    )
    metrics = _metrics_payload(evaluation)
    if not all(np.isfinite(value) for value in metrics.values() if isinstance(value, float)):
        raise GateError("Validation metrics chứa giá trị không hữu hạn.")

    preprocessor = pipeline.named_steps["preprocess"]
    transformed_feature_names = preprocessor.get_feature_names_out()
    transformed_feature_count = len(transformed_feature_names)
    sparse_output = bool(getattr(preprocessor, "sparse_output_", False))
    model = pipeline.named_steps["model"]

    validation_predictions = pd.DataFrame({
        "loan_id": validation_frame["loan_id"].reset_index(drop=True),
        "target": y_validation.reset_index(drop=True),
        "predicted_pd": probabilities,
    })
    if validation_predictions["loan_id"].isna().any() or not validation_predictions["loan_id"].is_unique:
        raise GateError("Validation prediction artifact loan_id không hợp lệ.")

    manifest = {
        "stage": ML_LC_03_STAGE,
        "status": "PASS",
        "dataset_id": DATASET_ID,
        "canonical_path": str(canonical_path),
        "split_manifest_path": str(output_dir / "split_manifest.json"),
        "train_rows": len(train_frame),
        "validation_rows": len(validation_frame),
        "frozen_test_rows": frozen.audit["partition_rows"]["test"],
        "frozen_test_used_for_training": False,
        "frozen_test_used_for_evaluation": False,
        "frozen_test_evaluation_rows": 0,
        "approved_feature_count": len(schema.approved_features),
        "actual_baseline_feature_count": len(selection.baseline_features),
        "actual_baseline_features": list(selection.baseline_features),
        "excluded_safe_features": list(selection.excluded_safe_features),
        "excluded_safe_feature_reasons": selection.exclusion_reasons,
        "feature_audit_path": str(audit_path),
        "transformed_feature_count": transformed_feature_count,
        "sparse_output": sparse_output,
        "model_type": "LogisticRegression",
        "solver": model.solver,
        "penalty": model.penalty,
        "max_iter": model.max_iter,
        "class_weight": model.class_weight,
        "random_state": model.random_state,
        "n_iter": fit_info["n_iter"],
        "converged": fit_info["converged"],
        "convergence_warnings": fit_info["convergence_warnings"],
        "convergence_fallback_used": fit_info["fallback_used"],
        "fit_seconds": fit_info["fit_seconds"],
        "reference_threshold": ML_LC_03_REFERENCE_THRESHOLD,
        "threshold_selected": False,
        "imbalance_treatment": "none",
        "validation_metrics": metrics,
        "validation_prediction_path": str(prediction_path),
        "model_artifact_path": str(model_path),
        "preprocessing_fit_partition": "train_only",
        "preprocessing_fitted": True,
        "model_trained": True,
        "provenance": {
            "runner": "src.models.tv1_runner.run_ml_lc_03",
            "feature_schema_source": "ML-LC-01 build_feature_schema",
            "split_source": str(output_dir / "split_manifest.json"),
            "frozen_test_access": "membership validation only; no prediction/metric",
            "threshold_policy": "0.5 reference only; final selection belongs to ML-LC-07",
        },
    }

    audit_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_dataframe(audit_path, selection.audit, format="csv")
    _atomic_joblib_dump(model_path, pipeline)
    _atomic_write_dataframe(prediction_path, validation_predictions, format="parquet")
    _atomic_write_text(baseline_manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False, default=str))

    loaded_pipeline = joblib.load(model_path)
    loaded_probabilities = loaded_pipeline.predict_proba(x_validation)[:, 1]
    if not np.allclose(probabilities, loaded_probabilities, rtol=1e-10, atol=1e-12):
        raise GateError("Model artifact reload không tái tạo validation probabilities.")

    report_path, _ = _stage_paths(reports_dir, ML_LC_03_STAGE)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_stage_evidence(
        reports_dir,
        stage=ML_LC_03_STAGE,
        title=ML_LC_03_TITLE,
        status="PASS",
        message="ML-LC-03 hoàn tất; Logistic baseline chỉ fit trên train và đánh giá trên validation.",
        payload=manifest,
    )
    report_path.write_text(_render_ml_lc_03_report(manifest), encoding="utf-8")
    return manifest


def run_ml_lc_04(
    *,
    canonical_path: Path = CANONICAL_DATASET_PATH,
    dictionary_path: Path = DATA_DICTIONARY_PATH,
    manifest_path: Path = DATASET_MANIFEST_PATH,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
    weighted_model_artifact_path: Path | None = None,
    weighted_validation_prediction_path: Path | None = None,
    experiment_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Compare ML-LC-03 with a train-only balanced Logistic experiment."""

    output_dir = Path(output_dir)
    _require_ml_lc_02_pass(reports_dir)
    baseline_manifest = _require_ml_lc_03_pass(reports_dir, output_dir)
    dataset, dictionary, tv2_manifest = load_canonical_input(
        dataset_path=canonical_path,
        dictionary_path=dictionary_path,
        manifest_path=manifest_path,
    )
    if tv2_manifest.get("dataset_id") != DATASET_ID:
        raise GateError("TV2 manifest dataset_id không khớp Lending Club dataset.")
    if tv2_manifest.get("run_status") != "PASS" or tv2_manifest.get("quality_status") != "PASS":
        raise GateError("TV2 handoff manifest chưa có run_status/quality_status PASS.")
    if tv2_manifest.get("leakage_gate") != "PASS":
        raise GateError("TV2 handoff manifest leakage_gate chưa PASS.")
    expected_rows = tv2_manifest.get("labeled_rows")
    if not isinstance(expected_rows, int) or expected_rows != len(dataset):
        raise GateError("TV2 manifest labeled_rows không khớp canonical dataset.")

    schema = build_feature_schema(dataset, dictionary)
    if len(schema.approved_features) != int(baseline_manifest["approved_feature_count"]):
        raise GateError("ML-LC-04 approved feature count không khớp ML-LC-03.")
    if len(schema.approved_features) != int(
        tv2_manifest.get("baseline_feature_count", len(schema.approved_features))
    ):
        raise GateError("Approved feature count không khớp TV2 handoff manifest.")

    frozen = create_or_load_frozen_split(
        dataset,
        output_dir=output_dir,
        canonical_path=canonical_path,
        dataset_id=DATASET_ID,
        expected_source_rows=expected_rows,
        random_state=42,
        test_size=0.20,
        validation_size=0.20,
    )
    if not frozen.manifest.get("frozen") or frozen.manifest.get("stage_status") != "PASS":
        raise GateError("ML-LC-02 frozen split chưa PASS/frozen.")

    train_frame = _select_partition_rows(
        dataset,
        frozen.split.train.ids,
        frozen.split.train.y,
        id_column="loan_id",
        target_column="target",
    )
    validation_frame = _select_partition_rows(
        dataset,
        frozen.split.validation.ids,
        frozen.split.validation.y,
        id_column="loan_id",
        target_column="target",
    )
    expected_train_rows = int(baseline_manifest["train_rows"])
    expected_validation_rows = int(baseline_manifest["validation_rows"])
    if len(train_frame) != expected_train_rows or len(validation_frame) != expected_validation_rows:
        raise GateError("ML-LC-04 train/validation row count không khớp ML-LC-03.")

    selection = build_baseline_feature_selection(dataset, schema, audit_frame=train_frame)
    baseline_features = list(baseline_manifest["actual_baseline_features"])
    if list(selection.baseline_features) != baseline_features:
        raise GateError("ML-LC-04 actual feature list không khớp ML-LC-03.")
    if list(selection.excluded_safe_features) != list(baseline_manifest["excluded_safe_features"]):
        raise GateError("ML-LC-04 excluded-safe feature list không khớp ML-LC-03.")
    categorical_concerns = selection.audit.loc[
        selection.audit["used_in_baseline"] & selection.audit["cardinality_concern"],
        "feature_name",
    ].tolist()
    if categorical_concerns:
        raise GateError(
            "Categorical cardinality vượt ngưỡng, không one-hot mù: "
            f"{categorical_concerns}"
        )

    baseline_model_path = output_dir / "logistic_baseline.joblib"
    baseline_prediction_path = output_dir / "ml_lc_03_validation_predictions.parquet"
    baseline_manifest_path = output_dir / "ml_lc_03_manifest.json"
    baseline_hash_before = _sha256(baseline_model_path)
    try:
        baseline_pipeline = joblib.load(baseline_model_path)
    except (OSError, ValueError, EOFError) as exc:
        raise GateError(f"Không load được ML-LC-03 baseline artifact: {baseline_model_path}") from exc
    if not hasattr(baseline_pipeline, "named_steps"):
        raise GateError("ML-LC-03 artifact không phải sklearn Pipeline.")
    baseline_model = baseline_pipeline.named_steps.get("model")
    baseline_preprocessor = baseline_pipeline.named_steps.get("preprocess")
    if baseline_model is None or baseline_preprocessor is None:
        raise GateError("ML-LC-03 artifact thiếu preprocessing hoặc model.")
    if baseline_model.class_weight is not None:
        raise GateError("ML-LC-03 baseline artifact đã bị thay đổi class_weight.")
    if not baseline_prediction_path.is_file() or not baseline_manifest_path.is_file():
        raise GateError("ML-LC-03 validation artifact/manifest canonical bị thiếu.")

    x_train = train_frame.loc[:, baseline_features]
    y_train = train_frame["target"].astype(int)
    x_validation = validation_frame.loc[:, baseline_features]
    y_validation = validation_frame["target"].astype(int)

    baseline_probabilities = baseline_pipeline.predict_proba(x_validation)[:, 1]
    if len(baseline_probabilities) != len(validation_frame):
        raise GateError("ML-LC-03 validation prediction row count không khớp.")
    if not np.isfinite(baseline_probabilities).all() or not np.all(
        (baseline_probabilities >= 0) & (baseline_probabilities <= 1)
    ):
        raise GateError("ML-LC-03 validation probabilities không hợp lệ.")
    baseline_evaluation = evaluate_binary_classifier(
        y_validation,
        baseline_probabilities,
        threshold=ML_LC_04_REFERENCE_THRESHOLD,
    )
    baseline_metrics = _metrics_payload(baseline_evaluation)
    expected_baseline_metrics = baseline_manifest["validation_metrics"]
    for metric in ("roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy"):
        if not np.isclose(
            baseline_metrics[metric],
            float(expected_baseline_metrics[metric]),
            rtol=1e-10,
            atol=1e-12,
        ):
            raise GateError(f"ML-LC-03 baseline metric không khớp manifest: {metric}")
    if baseline_metrics["confusion_matrix"] != expected_baseline_metrics["confusion_matrix"]:
        raise GateError("ML-LC-03 baseline confusion matrix không khớp manifest.")

    baseline_predictions = pd.read_parquet(baseline_prediction_path)
    expected_prediction_columns = ["loan_id", "target", "predicted_pd"]
    if baseline_predictions.columns.tolist() != expected_prediction_columns:
        raise GateError("ML-LC-03 validation prediction schema không đúng.")
    if len(baseline_predictions) != expected_validation_rows:
        raise GateError("ML-LC-03 validation prediction row count không đúng.")
    if baseline_predictions["loan_id"].tolist() != validation_frame["loan_id"].tolist():
        raise GateError("ML-LC-03 validation IDs không khớp frozen validation membership.")
    if baseline_predictions["target"].astype(int).tolist() != y_validation.tolist():
        raise GateError("ML-LC-03 validation targets không khớp canonical target.")

    solver = str(baseline_manifest["solver"])
    penalty = str(baseline_manifest["penalty"])
    max_iter = int(baseline_manifest["max_iter"])
    random_state = int(baseline_manifest["random_state"])
    weighted_pipeline, fit_info = _fit_logistic_experiment(
        dataset,
        selection,
        x_train,
        y_train,
        class_weight=ML_LC_04_CLASS_WEIGHT,
        max_iter=max_iter,
        solver=solver,
        penalty=penalty,
        random_state=random_state,
    )
    weighted_probabilities = weighted_pipeline.predict_proba(x_validation)[:, 1]
    if len(weighted_probabilities) != expected_validation_rows:
        raise GateError("Weighted validation prediction row count không khớp.")
    if not np.isfinite(weighted_probabilities).all() or not np.all(
        (weighted_probabilities >= 0) & (weighted_probabilities <= 1)
    ):
        raise GateError("Weighted validation probabilities phải hữu hạn và nằm trong [0, 1].")
    weighted_evaluation = evaluate_binary_classifier(
        y_validation,
        weighted_probabilities,
        threshold=ML_LC_04_REFERENCE_THRESHOLD,
    )
    weighted_metrics = _metrics_payload(weighted_evaluation)
    if not all(
        np.isfinite(value)
        for metrics in (baseline_metrics, weighted_metrics)
        for value in metrics.values()
        if isinstance(value, float)
    ):
        raise GateError("ML-LC-04 metrics chứa giá trị không hữu hạn.")

    weighted_preprocessor = weighted_pipeline.named_steps["preprocess"]
    baseline_feature_names = baseline_preprocessor.get_feature_names_out().tolist()
    weighted_feature_names = weighted_preprocessor.get_feature_names_out().tolist()
    if weighted_feature_names != baseline_feature_names:
        raise GateError("Weighted preprocessing không tạo cùng transformed feature schema.")
    transformed_feature_count = len(weighted_feature_names)
    if transformed_feature_count != int(baseline_manifest["transformed_feature_count"]):
        raise GateError("Weighted transformed feature count không khớp ML-LC-03.")
    weighted_model = weighted_pipeline.named_steps["model"]
    if weighted_model.class_weight != ML_LC_04_CLASS_WEIGHT:
        raise GateError("Weighted Logistic chưa dùng class_weight='balanced'.")

    metric_names = ("roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy")
    metric_comparison = [
        {
            "metric": metric,
            "baseline": baseline_metrics[metric],
            "weighted": weighted_metrics[metric],
            "difference": weighted_metrics[metric] - baseline_metrics[metric],
        }
        for metric in metric_names
    ]
    cell_names = ("TN", "FP", "FN", "TP")
    baseline_confusion = np.asarray(baseline_metrics["confusion_matrix"], dtype=int).ravel()
    weighted_confusion = np.asarray(weighted_metrics["confusion_matrix"], dtype=int).ravel()
    if int(baseline_confusion.sum()) != expected_validation_rows:
        raise GateError("ML-LC-03 confusion matrix không reconcile validation rows.")
    if int(weighted_confusion.sum()) != expected_validation_rows:
        raise GateError("Weighted confusion matrix không reconcile validation rows.")
    confusion_matrix_comparison = {
        name: {
            "baseline": int(baseline_confusion[index]),
            "weighted": int(weighted_confusion[index]),
            "difference": int(weighted_confusion[index] - baseline_confusion[index]),
        }
        for index, name in enumerate(cell_names)
    }

    recall_difference = weighted_metrics["recall"] - baseline_metrics["recall"]
    precision_difference = weighted_metrics["precision"] - baseline_metrics["precision"]
    f1_difference = weighted_metrics["f1"] - baseline_metrics["f1"]
    roc_auc_difference = weighted_metrics["roc_auc"] - baseline_metrics["roc_auc"]
    pr_auc_difference = weighted_metrics["pr_auc"] - baseline_metrics["pr_auc"]
    false_negative_difference = confusion_matrix_comparison["FN"]["difference"]
    false_positive_difference = confusion_matrix_comparison["FP"]["difference"]
    if recall_difference > 0:
        recall_sentence = f"Recall tăng {recall_difference:+.6f} trên validation."
    elif recall_difference < 0:
        recall_sentence = f"Recall giảm {recall_difference:+.6f} trên validation."
    else:
        recall_sentence = "Recall không thay đổi trên validation."
    interpretation = " ".join([
        recall_sentence,
        f"False negatives thay đổi {false_negative_difference:+d}; false positives thay đổi {false_positive_difference:+d}.",
        f"Precision thay đổi {precision_difference:+.6f}; F1 thay đổi {f1_difference:+.6f}.",
        f"ROC-AUC thay đổi {roc_auc_difference:+.6f}; PR-AUC thay đổi {pr_auc_difference:+.6f}.",
        (
            "Trade-off quan sát được là weighted model nhạy hơn với default nhưng tạo thêm cảnh báo false positive."
            if recall_difference > 0 and false_positive_difference > 0
            else "Trade-off cần được đọc cùng recall, precision, false negatives và false positives; chưa có cơ sở tuyên bố model nào cuối cùng tốt hơn."
        ),
    ])

    weighted_model_path = Path(
        weighted_model_artifact_path or output_dir / "logistic_weighted.joblib"
    )
    weighted_prediction_path = Path(
        weighted_validation_prediction_path
        or output_dir / "ml_lc_04_weighted_validation_predictions.parquet"
    )
    experiment_manifest_path = Path(
        experiment_manifest_path or output_dir / "ml_lc_04_manifest.json"
    )
    if weighted_model_path.resolve() == baseline_model_path.resolve():
        raise GateError("Weighted artifact không được ghi đè ML-LC-03 baseline.")

    manifest = {
        "stage": ML_LC_04_STAGE,
        "status": "PASS",
        "dataset_id": DATASET_ID,
        "canonical_path": str(canonical_path),
        "split_manifest_path": str(output_dir / "split_manifest.json"),
        "train_rows": len(train_frame),
        "validation_rows": len(validation_frame),
        "frozen_test_rows": frozen.audit["partition_rows"]["test"],
        "frozen_test_used_for_training": False,
        "frozen_test_used_for_evaluation": False,
        "frozen_test_used_for_selection": False,
        "frozen_test_evaluation_rows": 0,
        "approved_feature_count": len(schema.approved_features),
        "actual_feature_count": len(selection.baseline_features),
        "actual_baseline_feature_count": len(selection.baseline_features),
        "actual_baseline_features": baseline_features,
        "excluded_safe_features": list(selection.excluded_safe_features),
        "excluded_safe_feature_reasons": selection.exclusion_reasons,
        "transformed_feature_count": transformed_feature_count,
        "sparse_output": bool(getattr(weighted_preprocessor, "sparse_output_", False)),
        "baseline_manifest_path": str(baseline_manifest_path),
        "baseline_model_artifact_path": str(baseline_model_path),
        "baseline_validation_prediction_path": str(baseline_prediction_path),
        "baseline_class_weight": baseline_model.class_weight,
        "baseline_metrics": baseline_metrics,
        "weighted_model_artifact_path": str(weighted_model_path),
        "weighted_validation_prediction_path": str(weighted_prediction_path),
        "weighted_class_weight": weighted_model.class_weight,
        "weighted_metrics": weighted_metrics,
        "metric_comparison": metric_comparison,
        "confusion_matrix_comparison": confusion_matrix_comparison,
        "solver": solver,
        "penalty": penalty,
        "max_iter": fit_info["max_iter"],
        "random_state": random_state,
        "weighted_n_iter": fit_info["n_iter"],
        "weighted_converged": fit_info["converged"],
        "weighted_convergence_warnings": fit_info["convergence_warnings"],
        "weighted_convergence_fallback_used": fit_info["fallback_used"],
        "weighted_fit_seconds": fit_info["fit_seconds"],
        "reference_threshold": ML_LC_04_REFERENCE_THRESHOLD,
        "threshold_selected": False,
        "imbalance_treatment": "class_weight_balanced",
        "resampling": "none",
        "preprocessing_fit_partition": "train_only",
        "preprocessing_fitted": True,
        "model_trained": True,
        "baseline_artifact_sha256_before": baseline_hash_before,
        "interpretation": interpretation,
        "provenance": {
            "runner": "src.models.tv1_runner.run_ml_lc_04",
            "feature_schema_source": "ML-LC-01 build_feature_schema",
            "baseline_source": str(baseline_manifest_path),
            "split_source": str(output_dir / "split_manifest.json"),
            "frozen_test_access": "membership validation only; no prediction/metric/selection",
            "threshold_policy": "0.5 reference only; final selection belongs to ML-LC-07",
        },
    }

    _atomic_joblib_dump(weighted_model_path, weighted_pipeline)
    weighted_predictions = pd.DataFrame({
        "loan_id": validation_frame["loan_id"].reset_index(drop=True),
        "target": y_validation.reset_index(drop=True),
        "predicted_pd": weighted_probabilities,
    })
    if weighted_predictions["loan_id"].isna().any() or not weighted_predictions["loan_id"].is_unique:
        raise GateError("Weighted validation prediction loan_id không hợp lệ.")
    _atomic_write_dataframe(weighted_prediction_path, weighted_predictions, format="parquet")

    loaded_weighted_pipeline = joblib.load(weighted_model_path)
    loaded_weighted_probabilities = loaded_weighted_pipeline.predict_proba(x_validation)[:, 1]
    if not np.allclose(weighted_probabilities, loaded_weighted_probabilities, rtol=1e-10, atol=1e-12):
        raise GateError("Weighted model artifact reload không tái tạo validation probabilities.")
    if _sha256(baseline_model_path) != baseline_hash_before:
        raise GateError("ML-LC-03 baseline artifact đã bị thay đổi trong ML-LC-04.")
    manifest["baseline_artifact_sha256_after"] = _sha256(baseline_model_path)
    manifest["baseline_artifact_preserved"] = True
    _atomic_write_text(
        experiment_manifest_path,
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
    )

    report_path, _ = _stage_paths(reports_dir, ML_LC_04_STAGE)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_stage_evidence(
        reports_dir,
        stage=ML_LC_04_STAGE,
        title=ML_LC_04_TITLE,
        status="PASS",
        message="ML-LC-04 hoàn tất; weighted Logistic được fit trên train và so sánh với baseline trên validation.",
        payload=manifest,
    )
    report_path.write_text(_render_ml_lc_04_report(manifest), encoding="utf-8")
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run TV1 Modeling stages.")
    parser.add_argument("--stage", required=True, choices=[STAGE, ML_LC_03_STAGE, ML_LC_04_STAGE])
    parser.add_argument("--canonical-path", default=str(CANONICAL_DATASET_PATH))
    parser.add_argument("--dictionary-path", default=str(DATA_DICTIONARY_PATH))
    parser.add_argument("--manifest-path", default=str(DATASET_MANIFEST_PATH))
    parser.add_argument("--output-dir", default=str(MODELING_DIR))
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.20)
    parser.add_argument("--validation-size", type=float, default=0.20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.stage == STAGE:
            payload = run_ml_lc_02(
                canonical_path=Path(args.canonical_path),
                dictionary_path=Path(args.dictionary_path),
                manifest_path=Path(args.manifest_path),
                output_dir=Path(args.output_dir),
                reports_dir=Path(args.reports_dir),
                random_state=args.random_state,
                test_size=args.test_size,
                validation_size=args.validation_size,
            )
        else:
            if args.stage == ML_LC_03_STAGE:
                payload = run_ml_lc_03(
                    canonical_path=Path(args.canonical_path),
                    dictionary_path=Path(args.dictionary_path),
                    manifest_path=Path(args.manifest_path),
                    output_dir=Path(args.output_dir),
                    reports_dir=Path(args.reports_dir),
                )
            else:
                payload = run_ml_lc_04(
                    canonical_path=Path(args.canonical_path),
                    dictionary_path=Path(args.dictionary_path),
                    manifest_path=Path(args.manifest_path),
                    output_dir=Path(args.output_dir),
                    reports_dir=Path(args.reports_dir),
                )
        print(json.dumps({"stage": args.stage, "status": "PASS", "payload": payload}, ensure_ascii=False))
        return 0
    except (GateError, SplitValidationError, FileNotFoundError, ValueError, OSError) as exc:
        result = _write_stage_evidence(
            Path(args.reports_dir),
            stage=args.stage,
            title=(
                STAGE_TITLE
                if args.stage == STAGE
                else ML_LC_03_TITLE
                if args.stage == ML_LC_03_STAGE
                else ML_LC_04_TITLE
            ),
            status="FAIL",
            message=str(exc),
            payload={},
        )
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
