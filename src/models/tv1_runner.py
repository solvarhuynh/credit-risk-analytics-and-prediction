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
    ML_LC_07_MANIFEST_PATH,
    ML_LC_07_THRESHOLD_TABLE_PATH,
    MODELING_DIR,
    REPORTS_DIR,
)
from src.models.data_split import (
    SplitValidationError,
    create_or_load_frozen_split,
)
from src.models.evaluation import (
    CANDIDATE_SIMPLICITY_ORDER,
    PR_AUC_CLOSE_GAP,
    ROC_AUC_CLOSE_GAP,
    align_validation_predictions,
    evaluate_binary_classifier,
    evaluate_validation_predictions,
    select_validation_threshold,
    select_validation_candidate,
)
from src.models.modeling_pipeline import (
    GateError,
    build_baseline_feature_selection,
    build_feature_schema,
    build_logistic_pipeline,
    build_xgboost_pipeline,
    load_canonical_input,
    FeatureSchema,
)
from src.models.scoring import ML_LC_10_STAGE, ML_LC_10_TITLE, run_ml_lc_10
from src.models.expected_loss import ML_LC_11_STAGE, ML_LC_11_TITLE, run_ml_lc_11
from src.models.final_model import ML_LC_12_STAGE, ML_LC_13_STAGE, run_ml_lc_12, run_ml_lc_13_audit


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
ML_LC_05_STAGE = "ml-lc-05"
ML_LC_05_TITLE = "Optional XGBoost candidate"
ML_LC_05_REFERENCE_THRESHOLD = 0.5
ML_LC_06_STAGE = "ml-lc-06"
ML_LC_06_TITLE = "Model Comparison & Candidate Lock"
ML_LC_07_STAGE = "ml-lc-07"
ML_LC_07_TITLE = "Validation Threshold Selection"
ML_LC_07_EXPECTED_VALIDATION_ROWS = 269070
ML_LC_08_STAGE = "ml-lc-08"
ML_LC_08_TITLE = "One-shot Frozen Test Evaluation"
ML_LC_09_STAGE = "ml-lc-09"
ML_LC_09_TITLE = "Model Explainability"


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


def _render_ml_lc_05_report(manifest: dict[str, Any]) -> str:
    """Trình bày kết quả XGBoost và hai Logistic trên cùng validation."""

    lines = [
        "# ML-LC-05 — Optional XGBoost candidate",
        "",
        "## Purpose and data",
        "",
        "Thử một mô hình cây phi tuyến để so sánh ranking trên validation; Logistic vẫn là baseline bắt buộc.",
        f"Frozen train: **{manifest['train_rows']:,}**; validation: **{manifest['validation_rows']:,}**; frozen test: **{manifest['frozen_test_rows']:,}** (sealed).",
        f"ML-LC-01 approved: **{manifest['approved_feature_count']}**; actual input: **{manifest['actual_feature_count']}**; transformed: **{manifest['transformed_feature_count']}**.",
        "",
        "## Feature policy and preprocessing",
        "",
        "Dùng đúng 103 feature ML-LC-03/04 đã duyệt; không có ID, target, policy-derived, geography hoặc POST_LOAN trong X.",
        "Ba raw date fields tiếp tục loại theo baseline audit. Numeric: median imputation; categorical: most-frequent imputation + sparse one-hot; không StandardScaler.",
        "Imputer/encoder được fit chỉ trên train trong sklearn Pipeline. Không target encoding, không resampling và không early stopping.",
        "",
        "## Fixed candidate configuration",
        "",
        f"`{manifest['model_parameters']}`",
        "",
        "## Validation results",
        "",
        "Threshold 0.5 chỉ để tham chiếu; chưa tối ưu threshold.",
        "",
        "| Metric | Logistic baseline | Logistic weighted | XGBoost |",
        "|---|---:|---:|---:|",
    ]
    for row in manifest["comparison"]:
        lines.append(
            f"| {row['metric']} | {row['logistic_baseline']:.6f} | "
            f"{row['logistic_weighted']:.6f} | {row['xgboost']:.6f} |"
        )
    lines.extend([
        "",
        f"XGBoost confusion matrix `[ [TN, FP], [FN, TP] ]`: `{manifest['validation_metrics']['confusion_matrix']}`.",
        "",
        "## Artifacts",
        "",
        f"Model with preprocessing: `{manifest['model_artifact_path']}`.",
        f"Validation predictions: `{manifest['validation_prediction_path']}`.",
        "",
        "## Limitations",
        "",
        "Đây là một candidate với cấu hình cố định. ML-LC-06 mới so sánh và khóa model; chưa chọn model cuối.",
        "Frozen test không được dùng để train, predict, evaluate hoặc select model. Không đưa ra kết luận nhân quả từ các metric.",
        "",
    ])
    return "\n".join(lines)


def run_ml_lc_05(
    *,
    canonical_path: Path = CANONICAL_DATASET_PATH,
    dictionary_path: Path = DATA_DICTIONARY_PATH,
    manifest_path: Path = DATASET_MANIFEST_PATH,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    """Fit đúng một XGBoost candidate trên frozen train và đánh giá validation."""

    output_dir = Path(output_dir)
    _require_ml_lc_02_pass(reports_dir)
    baseline_manifest = _require_ml_lc_03_pass(reports_dir, output_dir)
    weighted_marker = reports_dir / "tv1_stages" / "state" / "ml-lc-04.json"
    weighted_manifest_path = output_dir / "ml_lc_04_manifest.json"
    if not weighted_marker.is_file() or not weighted_manifest_path.is_file():
        raise GateError("ML-LC-04 weighted handoff chưa đủ marker/manifest.")
    weighted_state = json.loads(weighted_marker.read_text(encoding="utf-8"))
    weighted_manifest = json.loads(weighted_manifest_path.read_text(encoding="utf-8"))
    if weighted_state.get("status") != "PASS" or weighted_manifest.get("status") != "PASS":
        raise GateError("ML-LC-04 chưa PASS.")
    if (weighted_manifest.get("stage") != ML_LC_04_STAGE
            or weighted_manifest.get("dataset_id") != baseline_manifest.get("dataset_id")
            or weighted_manifest.get("train_rows") != baseline_manifest.get("train_rows")
            or weighted_manifest.get("validation_rows") != baseline_manifest.get("validation_rows")
            or weighted_manifest.get("weighted_class_weight") != ML_LC_04_CLASS_WEIGHT
            or weighted_manifest.get("threshold_selected") is not False):
        raise GateError("ML-LC-04 handoff không khớp frozen Logistic comparison.")
    dataset, dictionary, tv2_manifest = load_canonical_input(
        dataset_path=canonical_path, dictionary_path=dictionary_path, manifest_path=manifest_path,
    )
    if (
        tv2_manifest.get("dataset_id") != DATASET_ID
        or tv2_manifest.get("run_status") != "PASS"
        or tv2_manifest.get("quality_status") != "PASS"
        or tv2_manifest.get("leakage_gate") != "PASS"
        or tv2_manifest.get("labeled_rows") != len(dataset)
    ):
        raise GateError("TV2 canonical handoff chưa đạt model input gate.")
    schema = build_feature_schema(dataset, dictionary)
    if len(schema.approved_features) != baseline_manifest["approved_feature_count"]:
        raise GateError("ML-LC-01 approved schema không khớp ML-LC-03.")
    if len(schema.approved_features) != tv2_manifest.get("baseline_feature_count", len(schema.approved_features)):
        raise GateError("ML-LC-01 approved schema không khớp TV2 manifest.")
    frozen = create_or_load_frozen_split(
        dataset, output_dir=output_dir, canonical_path=canonical_path,
        dataset_id=DATASET_ID, expected_source_rows=len(dataset),
        random_state=42, test_size=0.20, validation_size=0.20,
    )
    if frozen.manifest.get("stage_status") != "PASS" or not frozen.manifest.get("frozen"):
        raise GateError("Frozen split ML-LC-02 chưa PASS.")
    train = _select_partition_rows(dataset, frozen.split.train.ids, frozen.split.train.y,
                                   id_column="loan_id", target_column="target")
    validation = _select_partition_rows(dataset, frozen.split.validation.ids, frozen.split.validation.y,
                                        id_column="loan_id", target_column="target")
    if (len(train), len(validation)) != (
        baseline_manifest["train_rows"], baseline_manifest["validation_rows"]
    ):
        raise GateError("Frozen train/validation row count không khớp ML-LC-03.")
    selection = build_baseline_feature_selection(dataset, schema, audit_frame=train)
    features = list(selection.baseline_features)
    if features != baseline_manifest["actual_baseline_features"] or features != weighted_manifest["actual_baseline_features"]:
        raise GateError("XGBoost feature list không khớp Logistic handoff.")
    if selection.audit.loc[selection.audit["used_in_baseline"] & selection.audit["cardinality_concern"]].shape[0]:
        raise GateError("Categorical cardinality vượt ngưỡng.")

    prior_paths = [
        output_dir / name for name in (
            "logistic_baseline.joblib", "logistic_weighted.joblib",
            "ml_lc_03_manifest.json", "ml_lc_04_manifest.json",
            "ml_lc_03_validation_predictions.parquet",
            "ml_lc_04_weighted_validation_predictions.parquet",
        )
    ]
    if any(not path.is_file() for path in prior_paths):
        raise GateError("Thiếu Logistic artifact cho comparison.")
    prior_hashes = {path.name: _sha256(path) for path in prior_paths}
    x_train, y_train = train.loc[:, features], train["target"].astype(int)
    x_validation, y_validation = validation.loc[:, features], validation["target"].astype(int)
    pipeline = build_xgboost_pipeline(dataset, schema, feature_columns=features)
    started = time.perf_counter()
    pipeline.fit(x_train, y_train)
    fit_seconds = time.perf_counter() - started
    probabilities = pipeline.predict_proba(x_validation)[:, 1]
    if len(probabilities) != len(validation) or not np.isfinite(probabilities).all() or not np.all((0 <= probabilities) & (probabilities <= 1)):
        raise GateError("XGBoost validation probabilities không hợp lệ.")
    if validation["loan_id"].isna().any() or not validation["loan_id"].is_unique:
        raise GateError("Frozen validation loan_id phải unique/non-null.")
    metrics = _metrics_payload(evaluate_binary_classifier(
        y_validation, probabilities, threshold=ML_LC_05_REFERENCE_THRESHOLD,
    ))
    if sum(map(sum, metrics["confusion_matrix"])) != len(validation):
        raise GateError("XGBoost confusion matrix không khớp validation rows.")
    baseline_metrics = baseline_manifest["validation_metrics"]
    weighted_metrics = weighted_manifest["weighted_metrics"]
    comparison = [
        {"metric": metric, "logistic_baseline": baseline_metrics[metric],
         "logistic_weighted": weighted_metrics[metric], "xgboost": metrics[metric]}
        for metric in ("roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy")
    ]
    model_path = output_dir / "xgboost_candidate.joblib"
    prediction_path = output_dir / "ml_lc_05_xgboost_validation_predictions.parquet"
    stage_manifest_path = output_dir / "ml_lc_05_manifest.json"
    model = pipeline.named_steps["model"]
    params = {key: model.get_params()[key] for key in (
        "n_estimators", "max_depth", "learning_rate", "subsample", "colsample_bytree",
        "random_state", "objective", "eval_metric", "tree_method", "n_jobs",
    )}
    stage_manifest = {
        "stage": ML_LC_05_STAGE, "status": "PASS", "dataset_id": DATASET_ID,
        "canonical_path": str(canonical_path), "split_manifest_path": str(output_dir / "split_manifest.json"),
        "train_rows": len(train), "validation_rows": len(validation),
        "frozen_test_rows": frozen.audit["partition_rows"]["test"],
        "approved_feature_count": len(schema.approved_features),
        "actual_feature_count": len(features), "actual_features": features,
        "excluded_safe_features": list(selection.excluded_safe_features),
        "transformed_feature_count": len(pipeline.named_steps["preprocess"].get_feature_names_out()),
        "sparse_output": bool(pipeline.named_steps["preprocess"].sparse_output_),
        "model_parameters": params, "fit_seconds": fit_seconds,
        "baseline_metrics": baseline_metrics, "weighted_metrics": weighted_metrics,
        "validation_metrics": metrics, "comparison": comparison,
        "model_artifact_path": str(model_path), "validation_prediction_path": str(prediction_path),
        "preprocessing_fit_partition": "train_only", "early_stopping_used": False,
        "frozen_test_used_for_training": False, "frozen_test_used_for_evaluation": False,
        "frozen_test_used_for_selection": False, "frozen_test_evaluation_rows": 0,
        "reference_threshold": ML_LC_05_REFERENCE_THRESHOLD,
        "threshold_selected": False, "final_model_selected": False,
        "prior_artifact_sha256": prior_hashes,
    }
    predictions = pd.DataFrame({
        "loan_id": validation["loan_id"].reset_index(drop=True),
        "target": y_validation.reset_index(drop=True), "predicted_pd": probabilities,
    })
    _atomic_joblib_dump(model_path, pipeline)
    _atomic_write_dataframe(prediction_path, predictions, format="parquet")
    if not np.allclose(joblib.load(model_path).predict_proba(x_validation)[:, 1], probabilities, rtol=1e-9, atol=1e-12):
        raise GateError("Reloaded XGBoost artifact không tái tạo validation probabilities.")
    if any(_sha256(path) != prior_hashes[path.name] for path in prior_paths):
        raise GateError("Logistic artifact bị thay đổi trong ML-LC-05.")
    _atomic_write_text(stage_manifest_path, json.dumps(stage_manifest, ensure_ascii=False, indent=2))
    report_path, _ = _stage_paths(reports_dir, ML_LC_05_STAGE)
    _write_stage_evidence(reports_dir, stage=ML_LC_05_STAGE, title=ML_LC_05_TITLE,
                          status="PASS", message="XGBoost candidate đã đánh giá trên validation.", payload=stage_manifest)
    report_path.write_text(_render_ml_lc_05_report(stage_manifest), encoding="utf-8")
    return stage_manifest


def _render_ml_lc_06_report(manifest: dict[str, Any]) -> str:
    """Trình bày so sánh validation và quyết định khóa candidate bằng tiếng Việt."""

    rows = []
    for row in manifest["comparison_table"]:
        matrix = row["confusion_matrix"]
        rows.append(
            f"| {row['model']} | {row['roc_auc']:.6f} | {row['pr_auc']:.6f} | "
            f"{row['log_loss']:.6f} | {row['brier_score']:.6f} | "
            f"{row['precision']:.6f} | {row['recall']:.6f} | {row['f1']:.6f} | "
            f"{row['accuracy']:.6f} | {matrix[0][0]} | {matrix[0][1]} | "
            f"{matrix[1][0]} | {matrix[1][1]} |"
        )
    delta_rows = [
        f"| {row['model']} | {row['delta_roc_auc']:+.6f} | {row['delta_pr_auc']:+.6f} | "
        f"{row['delta_log_loss']:+.6f} | {row['delta_brier_score']:+.6f} | "
        f"{row['delta_precision']:+.6f} | {row['delta_recall']:+.6f} |"
        for row in manifest["comparison_table"]
    ]
    rejected = "\n".join(
        f"- `{row['model']}`: {row['reason']}" for row in manifest["models_rejected"]
    )
    return "\n".join([
        "# ML-LC-06 — Model Comparison & Candidate Lock", "",
        "## 1. Mục tiêu", "",
        "ML-LC-03 tạo Logistic baseline bắt buộc; ML-LC-04 thử class weighting; "
        "ML-LC-05 thử XGBoost. Stage này so sánh công bằng ba candidate và khóa một "
        "candidate để chuyển sang chọn threshold.", "",
        "## 2. Dữ liệu dùng", "",
        f"Chỉ dùng **{manifest['validation_rows']:,}** dự đoán validation trên cùng loan_id/target. "
        "Frozen test vẫn sealed; chỉ xác nhận file test IDs tồn tại, không đọc nhãn hoặc features.", "",
        "## 3. Tiêu chí chọn", "",
        "ROC-AUC đo khả năng xếp người vỡ nợ cao hơn người không vỡ nợ; PR-AUC "
        "chú trọng lớp vỡ nợ ít gặp. Ưu tiên ROC-AUC; nếu chênh không quá 0.002, "
        "dùng PR-AUC; nếu PR-AUC cũng chênh không quá 0.005, ưu tiên model đơn giản hơn. "
        "Hai Logistic có cùng mức phức tạp thì xét Log Loss, rồi Brier Score.",
        "Log Loss và Brier Score càng thấp càng tốt cho chất lượng xác suất PD; "
        "chỉ là chẩn đoán ở stage này. Metrics tại threshold 0.5 không quyết định "
        "model vì ML-LC-07 mới chọn threshold. Không kiểm định ý nghĩa thống kê.", "",
        "## 4. Bảng so sánh", "",
        "| Model | ROC-AUC | PR-AUC | Log Loss | Brier | Precision @0.5 | Recall @0.5 | F1 @0.5 | Accuracy @0.5 | TN | FP | FN | TP |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *rows, "",
        "Chênh lệch so với Logistic baseline (Log Loss/Brier âm nghĩa là tốt hơn):", "",
        "| Model | Δ ROC-AUC | Δ PR-AUC | Δ Log Loss | Δ Brier | Δ Precision @0.5 | Δ Recall @0.5 |",
        "|---|---:|---:|---:|---:|---:|---:|", *delta_rows, "",
        "## 5. Diễn giải", "",
        "Logistic baseline đơn giản, dễ giải thích và là baseline bắt buộc. "
        "Weighted Logistic nhạy hơn với default tại ngưỡng 0.5 nhưng tạo nhiều false positives; "
        "recall cao tại ngưỡng này không đồng nghĩa ranking hay PD tốt hơn. "
        "XGBoost có thể học quan hệ phi tuyến/tương tác, nhưng phức tạp và khó giải thích trực tiếp hơn Logistic.", "",
        "## 6. Candidate đã khóa", "",
        f"**`{manifest['selected_candidate']}`** — {manifest['selection_reason']}", "",
        f"Model artifact: `{manifest['selected_model_artifact_path']}`. "
        f"Validation predictions: `{manifest['selected_validation_predictions_path']}`.", "",
        "## 7. Vì sao hai candidate còn lại không được chọn", "",
        rejected, "",
        "## 8. Những việc chưa thực hiện", "",
        "Chưa chọn threshold, chưa đánh giá frozen test, chưa công bố final model hoặc fit calibration. "
        "Chênh lệch validation là point estimates, không khẳng định có ý nghĩa thống kê.", "",
        "## 9. Bước tiếp theo", "",
        "ML-LC-07 — Threshold Selection trên validation cho duy nhất candidate đã khóa.", "",
    ])


def run_ml_lc_06(
    *,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    """Khóa một candidate từ ba prediction artifacts trên validation, không fit model."""

    output_dir = Path(output_dir)
    reports_dir = Path(reports_dir)
    _require_ml_lc_02_pass(reports_dir)
    split_path = output_dir / "split_manifest.json"
    validation_ids_path = output_dir / "validation_ids.parquet"
    test_ids_path = output_dir / "test_ids.parquet"
    if any(not path.is_file() for path in (split_path, validation_ids_path, test_ids_path)):
        raise GateError("Thiếu ML-LC-02 split manifest hoặc frozen partition IDs.")
    split = json.loads(split_path.read_text(encoding="utf-8"))
    if (split.get("stage_status") != "PASS" or split.get("frozen") is not True
            or split.get("dataset_id") != DATASET_ID):
        raise GateError("ML-LC-02 split chưa PASS/frozen hoặc dataset_id sai.")
    expected_rows = split.get("validation_rows")
    if not isinstance(expected_rows, int) or expected_rows <= 0:
        raise GateError("ML-LC-02 validation row count không hợp lệ.")

    specs = {
        "logistic_baseline": (ML_LC_03_STAGE, "ml_lc_03_manifest.json",
                              "logistic_baseline.joblib", "ml_lc_03_validation_predictions.parquet",
                              "validation_metrics", "model_artifact_path", "validation_prediction_path"),
        "logistic_weighted": (ML_LC_04_STAGE, "ml_lc_04_manifest.json",
                              "logistic_weighted.joblib", "ml_lc_04_weighted_validation_predictions.parquet",
                              "weighted_metrics", "weighted_model_artifact_path", "weighted_validation_prediction_path"),
        "xgboost_candidate": (ML_LC_05_STAGE, "ml_lc_05_manifest.json",
                              "xgboost_candidate.joblib", "ml_lc_05_xgboost_validation_predictions.parquet",
                              "validation_metrics", "model_artifact_path", "validation_prediction_path"),
    }
    manifests: dict[str, dict[str, Any]] = {}
    prediction_frames: dict[str, pd.DataFrame] = {}
    hashes: dict[str, str] = {}
    for name, (stage, manifest_name, model_name, prediction_name, _, model_key, prediction_key) in specs.items():
        marker_path = reports_dir / "tv1_stages" / "state" / f"{stage}.json"
        manifest_file = output_dir / manifest_name
        model_file = output_dir / model_name
        prediction_file = output_dir / prediction_name
        if any(not path.is_file() for path in (marker_path, manifest_file, model_file, prediction_file)):
            raise GateError(f"{stage}: thiếu marker, manifest, model hoặc validation predictions.")
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if (marker.get("stage") != stage or marker.get("status") != "PASS"
                or manifest.get("stage") != stage or manifest.get("status") != "PASS"
                or manifest.get("dataset_id") != DATASET_ID
                or manifest.get("train_rows") != split.get("train_rows")
                or manifest.get("validation_rows") != expected_rows
                or manifest.get("frozen_test_rows") != split.get("test_rows")
                or manifest.get("threshold_selected") is not False
                or manifest.get("frozen_test_used_for_training") is not False
                or manifest.get("frozen_test_used_for_evaluation") is not False
                or manifest.get("frozen_test_evaluation_rows") != 0):
            raise GateError(f"{stage}: metadata handoff không khớp frozen split.")
        if ("frozen_test_used_for_selection" in manifest
                and manifest["frozen_test_used_for_selection"] is not False):
            raise GateError(f"{stage}: frozen test đã dùng cho selection.")
        if (Path(manifest.get(model_key, "")).resolve() != model_file.resolve()
                or Path(manifest.get(prediction_key, "")).resolve() != prediction_file.resolve()):
            raise GateError(f"{stage}: artifact path không khớp canonical location.")
        try:
            loaded = joblib.load(model_file)
        except Exception as exc:
            raise GateError(f"{stage}: model artifact không load được.") from exc
        if not hasattr(loaded, "predict_proba"):
            raise GateError(f"{stage}: model artifact không hỗ trợ predict_proba.")
        del loaded
        manifests[name] = manifest
        prediction_frames[name] = pd.read_parquet(prediction_file)
        for path in (manifest_file, model_file, prediction_file):
            hashes[path.name] = _sha256(path)

    prior_hashes = manifests["xgboost_candidate"].get("prior_artifact_sha256", {})
    expected_prior = {
        "logistic_baseline.joblib", "logistic_weighted.joblib",
        "ml_lc_03_manifest.json", "ml_lc_04_manifest.json",
        "ml_lc_03_validation_predictions.parquet",
        "ml_lc_04_weighted_validation_predictions.parquet",
    }
    if not isinstance(prior_hashes, dict) or set(prior_hashes) != expected_prior:
        raise GateError("ML-LC-05 thiếu checksum handoff Logistic bắt buộc.")
    if any(hashes.get(name) != digest for name, digest in prior_hashes.items()):
        raise GateError("Artifact Logistic đã thay đổi sau ML-LC-05.")
    validation_ids = pd.read_parquet(validation_ids_path)
    if "split" in validation_ids and not validation_ids["split"].eq("validation").all():
        raise GateError("validation_ids.parquet có partition label sai.")
    aligned = align_validation_predictions(prediction_frames, validation_ids, expected_rows=expected_rows)
    metrics = {name: evaluate_validation_predictions(frame) for name, frame in aligned.items()}
    for name, spec in specs.items():
        original = manifests[name][spec[4]]
        for key in ("roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy"):
            if not np.isclose(metrics[name][key], original[key], rtol=1e-8, atol=1e-8):
                raise GateError(f"{name}: {key} không khớp manifest gốc.")
        if metrics[name]["confusion_matrix"] != original["confusion_matrix"]:
            raise GateError(f"{name}: confusion matrix không khớp manifest gốc.")

    selected = select_validation_candidate(metrics)
    baseline = metrics["logistic_baseline"]
    comparison = []
    for name in CANDIDATE_SIMPLICITY_ORDER:
        row = {"model": name, **metrics[name]}
        for key in ("roc_auc", "pr_auc", "log_loss", "brier_score", "precision", "recall"):
            row[f"delta_{key}"] = metrics[name][key] - baseline[key]
        comparison.append(row)
    roc_delta = metrics[selected]["roc_auc"] - baseline["roc_auc"]
    pr_delta = metrics[selected]["pr_auc"] - baseline["pr_auc"]
    selection_reason = (
        f"Theo quy tắc đã ghi trong model contract: ROC-AUC {metrics[selected]['roc_auc']:.6f} "
        f"(so với baseline {roc_delta:+.6f}), PR-AUC {metrics[selected]['pr_auc']:.6f} "
        f"(so với baseline {pr_delta:+.6f}); ngưỡng gần nhau lần lượt "
        f"{ROC_AUC_CLOSE_GAP:.3f}/{PR_AUC_CLOSE_GAP:.3f}. "
        "Quyết định dựa trên validation point estimates, chưa có kiểm định ý nghĩa thống kê."
    )
    rejected = []
    for name in CANDIDATE_SIMPLICITY_ORDER:
        if name == selected:
            continue
        reason = (
            f"ROC-AUC {metrics[name]['roc_auc']:.6f} (candidate khóa trừ model này: "
            f"{metrics[selected]['roc_auc'] - metrics[name]['roc_auc']:+.6f}); "
            f"PR-AUC {metrics[name]['pr_auc']:.6f} (candidate khóa trừ model này: "
            f"{metrics[selected]['pr_auc'] - metrics[name]['pr_auc']:+.6f})."
        )
        if name == "logistic_baseline":
            reason += " Model đơn giản, dễ giải thích và vẫn là baseline bắt buộc."
        elif name == "logistic_weighted":
            reason += (
                f" Recall @0.5 {metrics[name]['recall']:.6f} đi kèm "
                f"{metrics[name]['confusion_matrix'][0][1]:,} false positives; "
                "ngưỡng tham chiếu không được dùng để chọn model."
            )
        else:
            reason += " Độ phức tạp cao hơn không được bù bằng ranking theo quy tắc gần nhau."
        rejected.append({"model": name, "reason": reason})
    chosen_spec = specs[selected]
    payload = {
        "stage": ML_LC_06_STAGE, "status": "PASS", "dataset_id": DATASET_ID,
        "candidate_models": list(CANDIDATE_SIMPLICITY_ORDER),
        "selection_criteria": {
            "primary": "roc_auc", "secondary": "pr_auc",
            "roc_auc_close_gap": ROC_AUC_CLOSE_GAP, "pr_auc_close_gap": PR_AUC_CLOSE_GAP,
            "close_tie_breaker": "model complexity, then lower Log Loss/Brier, then stable name order",
            "probability_diagnostics": ["log_loss", "brier_score"],
            "reference_threshold_diagnostics_only": ["precision", "recall", "f1", "accuracy", "confusion_matrix"],
        },
        "validation_rows": expected_rows, "frozen_test_rows": split["test_rows"],
        "validation_alignment": "PASS", "metrics": metrics, "comparison_table": comparison,
        "selected_candidate": selected,
        "selected_model_artifact_path": str(output_dir / chosen_spec[2]),
        "selected_validation_predictions_path": str(output_dir / chosen_spec[3]),
        "selection_reason": selection_reason, "models_rejected": rejected,
        "metrics_used": ["roc_auc", "pr_auc", "log_loss", "brier_score"],
        "source_artifact_sha256": hashes,
        "threshold_selected": False, "reference_threshold": 0.5,
        "final_model_selected": False,
        "frozen_test_used_for_training": False,
        "frozen_test_used_for_evaluation": False,
        "frozen_test_used_for_selection": False,
        "next_stage": "ml-lc-07",
    }
    _atomic_write_text(output_dir / "ml_lc_06_manifest.json", json.dumps(payload, ensure_ascii=False, indent=2))
    report_path, marker_path = _stage_paths(reports_dir, ML_LC_06_STAGE)
    _atomic_write_text(report_path, _render_ml_lc_06_report(payload))
    marker = {
        "stage": ML_LC_06_STAGE, "title": ML_LC_06_TITLE, "status": "PASS",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_path": str(report_path), "manifest_path": str(output_dir / "ml_lc_06_manifest.json"),
    }
    _atomic_write_text(marker_path, json.dumps(marker, ensure_ascii=False, indent=2))
    return payload


def _render_ml_lc_07_report(manifest: dict[str, Any], table: pd.DataFrame) -> str:
    """Tạo báo cáo tiếng Việt về threshold validation đã chọn."""

    diagnostic_values = {0.10, 0.20, 0.30, 0.40, 0.50, 0.60,
                         float(manifest["selected_threshold"])}
    diagnostic = table.loc[table["threshold"].isin(diagnostic_values)]
    rows = [
        f"| {row.threshold:.12g} | {row.precision:.6f} | {row.recall:.6f} | "
        f"{row.f1:.6f} | {row.accuracy:.6f} | {int(row.fp)} | {int(row.fn)} | "
        f"{int(row.predicted_positive_count):,} |"
        for row in diagnostic.itertuples(index=False)
    ]
    selected = manifest["selected_metrics"]
    reference = manifest["reference_metrics"]
    delta = manifest["deltas_vs_reference"]
    return "\n".join([
        "# ML-LC-07 — Threshold Selection", "",
        "## 1. Threshold là gì?", "",
        "Model xuất xác suất vỡ nợ (PD). Quy tắc vận hành là `predicted_pd >= threshold` "
        "thì phân loại hồ sơ vào nhóm default-risk.", "",
        "## 2. Vì sao 0.5 chưa chắc phù hợp?", "",
        f"Với XGBoost, tại 0.5 validation recall là {reference['recall']:.6f}; "
        "ngưỡng đó bỏ sót nhiều khoản default. Thay threshold đổi precision/recall "
        "và số false positive/false negative, nhưng không đổi ROC-AUC/PR-AUC của cùng scores.", "",
        "## 3. Dữ liệu được dùng", "",
        f"Chỉ dùng **{manifest['validation_rows']:,}** validation predictions của `xgboost_candidate`; "
        "IDs và target khớp frozen validation population. Frozen test vẫn sealed; không đọc hoặc tính metric trên test.", "",
        "## 4. Quy tắc chọn", "",
        "Tối đa hóa F1 trên validation bằng tập ngưỡng chính xác lấy từ các prediction scores phân biệt. "
        "Nếu F1 cách mức cao nhất không quá `1e-12`, chọn recall cao hơn, sau đó precision cao hơn, "
        "cuối cùng chọn threshold cao hơn. Chưa có chi phí kinh doanh được duyệt; đây là operating threshold "
        "thống kê, không phải ngưỡng tối ưu cho Expected Loss hoặc lợi nhuận.", "",
        "## 5. Bảng trade-off tham khảo", "",
        "Bảng file CSV lưu tất cả score thresholds đã xét cùng các ngưỡng chẩn đoán. Bảng dưới rút gọn các mốc tham khảo và ngưỡng được chọn:", "",
        "| Threshold | Precision | Recall | F1 | Accuracy | FP | FN | Predicted positive |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|", *rows, "",
        "## 6. Threshold được chọn", "",
        f"**{manifest['selected_threshold']:.12g}** theo tiêu chí F1 validation.", "",
        f"Precision {selected['precision']:.6f}; recall {selected['recall']:.6f}; "
        f"F1 {selected['f1']:.6f}; accuracy {selected['accuracy']:.6f}.", "",
        f"Confusion `[ [TN, FP], [FN, TP] ]`: `[[{selected['tn']}, {selected['fp']}], "
        f"[{selected['fn']}, {selected['tp']}]]`.", "",
        "## 7. So với threshold 0.5", "",
        f"Precision {delta['precision']:+.6f}; recall {delta['recall']:+.6f}; "
        f"F1 {delta['f1']:+.6f}; accuracy {delta['accuracy']:+.6f}; "
        f"FP {delta['fp']:+,}; FN {delta['fn']:+,}.", "",
        "Ngưỡng thấp hơn thường tăng recall và giảm FN, đồng thời có thể giảm precision và tăng FP. "
        "Ngưỡng được chọn thể hiện trade-off quan sát được trên validation.", "",
        "## 8. Giới hạn", "",
        "Threshold này được chọn trên validation; không tối ưu frozen test, Expected Loss, lợi nhuận "
        "hoặc chi phí kinh doanh. Không phải cutoff đúng cho mọi tổ chức. Model không được retrain.", "",
        "## 9. Bước tiếp theo", "",
        "ML-LC-08 — Frozen Test, theo đúng quy trình đánh giá một lần.", "",
    ])


def run_ml_lc_07(
    *,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    """Chọn threshold F1 trên validation của candidate đã khóa, không train model."""

    output_dir, reports_dir = Path(output_dir), Path(reports_dir)
    ml06_marker_path = reports_dir / "tv1_stages" / "state" / f"{ML_LC_06_STAGE}.json"
    ml06_manifest_path = output_dir / "ml_lc_06_manifest.json"
    prediction_path = output_dir / "ml_lc_05_xgboost_validation_predictions.parquet"
    model_path = output_dir / "xgboost_candidate.joblib"
    validation_ids_path = output_dir / "validation_ids.parquet"
    if any(not path.is_file() for path in (ml06_marker_path, ml06_manifest_path,
                                           prediction_path, model_path, validation_ids_path)):
        raise GateError("ML-LC-07 thiếu ML-LC-06 handoff, model hoặc validation artifact.")
    marker = json.loads(ml06_marker_path.read_text(encoding="utf-8"))
    ml06_manifest = json.loads(ml06_manifest_path.read_text(encoding="utf-8"))
    if marker.get("stage") != ML_LC_06_STAGE or marker.get("status") != "PASS":
        raise GateError("ML-LC-06 marker chưa PASS.")
    if (ml06_manifest.get("stage") != ML_LC_06_STAGE
            or ml06_manifest.get("status") != "PASS"
            or ml06_manifest.get("selected_candidate") != "xgboost_candidate"
            or ml06_manifest.get("threshold_selected") is not False
            or ml06_manifest.get("final_model_selected") is not False
            or ml06_manifest.get("selected_model_artifact_path") != str(model_path)
            or ml06_manifest.get("selected_validation_predictions_path") != str(prediction_path)):
        raise GateError("ML-LC-06 locked candidate/manifest không hợp lệ hoặc đã thay đổi.")
    expected_rows = ml06_manifest.get("validation_rows")
    if (not isinstance(expected_rows, int)
            or expected_rows != ML_LC_07_EXPECTED_VALIDATION_ROWS):
        raise GateError("ML-LC-06 validation row count không khớp handoff.")
    model_hash_before = _sha256(model_path)
    prediction_hash_before = _sha256(prediction_path)
    ml06_hash_before = _sha256(ml06_manifest_path)
    locked_hashes = ml06_manifest.get("source_artifact_sha256", {})
    if (locked_hashes.get(model_path.name) != model_hash_before
            or locked_hashes.get(prediction_path.name) != prediction_hash_before):
        raise GateError("Model hoặc validation predictions không còn khớp ML-LC-06 locked evidence.")
    raw_predictions = pd.read_parquet(prediction_path)
    validation_ids = pd.read_parquet(validation_ids_path)
    if "split" in validation_ids and not validation_ids["split"].eq("validation").all():
        raise GateError("validation_ids.parquet chứa split label không hợp lệ.")
    try:
        aligned = align_validation_predictions(
            {"xgboost_candidate": raw_predictions}, validation_ids,
            expected_rows=expected_rows,
        )["xgboost_candidate"]
        selected = select_validation_threshold(
            aligned["target"], aligned["predicted_pd"], tie_tolerance=1e-12,
        )
    except ValueError as exc:
        raise GateError(f"ML-LC-07 validation gate/search failed: {exc}") from exc
    table = selected["threshold_table"]
    selected_rows = table.loc[table["selected"]]
    if len(selected_rows) != 1:
        raise GateError("Threshold table phải đánh dấu chính xác một selected row.")
    chosen_f1 = float(selected["selected_metrics"]["f1"])
    if abs(chosen_f1 - float(selected["max_f1"])) > 1e-12:
        raise GateError("Threshold được chọn không đạt maximum F1 trong tie tolerance.")
    threshold_path = output_dir / ML_LC_07_THRESHOLD_TABLE_PATH.name
    manifest_path = output_dir / ML_LC_07_MANIFEST_PATH.name
    reference, chosen = selected["reference_metrics"], selected["selected_metrics"]
    deltas = {
        key: chosen[key] - reference[key]
        for key in ("precision", "recall", "f1", "accuracy", "fp", "fn")
    }
    payload = {
        "stage": ML_LC_07_STAGE, "status": "PASS",
        "locked_candidate": "xgboost_candidate",
        "source_model_artifact": str(model_path),
        "source_validation_predictions": str(prediction_path),
        "source_model_sha256_before": model_hash_before,
        "source_validation_predictions_sha256_before": prediction_hash_before,
        "ml_lc_06_manifest_sha256_before": ml06_hash_before,
        "validation_rows": expected_rows, "selection_partition": "validation",
        "selection_rule": "maximize_f1",
        "tie_break_rule": {
            "f1_tolerance": 1e-12,
            "order": ["higher_recall", "higher_precision", "higher_threshold"],
        },
        "reference_threshold": 0.5, "reference_metrics": reference,
        "selected_threshold": selected["selected_threshold"],
        "selected_metrics": chosen, "deltas_vs_reference": deltas,
        "maximum_f1": selected["max_f1"],
        "threshold_table_path": str(threshold_path),
        "threshold_table_rows": len(table), "selected_threshold_rows": len(selected_rows),
        "threshold_selected": True, "candidate_changed": False,
        "model_retrained": False, "final_model_selected": False,
        "frozen_test_used_for_training": False,
        "frozen_test_used_for_threshold_selection": False,
        "frozen_test_used_for_evaluation": False,
        "frozen_test_threshold_selection_rows": 0,
        "frozen_test_evaluation_rows": 0,
        "next_stage": "ml-lc-08",
    }
    _atomic_write_dataframe(threshold_path, table, format="csv")
    if (int(pd.read_csv(threshold_path)["selected"].sum()) != 1
            or _sha256(model_path) != model_hash_before
            or _sha256(prediction_path) != prediction_hash_before
            or _sha256(ml06_manifest_path) != ml06_hash_before):
        raise GateError("ML-LC-07 không giữ nguyên candidate/model/predictions/ML-LC-06 artifacts.")
    payload["source_model_sha256_after"] = _sha256(model_path)
    payload["source_validation_predictions_sha256_after"] = _sha256(prediction_path)
    payload["ml_lc_06_manifest_sha256_after"] = _sha256(ml06_manifest_path)
    _atomic_write_text(manifest_path, json.dumps(payload, ensure_ascii=False, indent=2))
    report_path, marker_path = _stage_paths(reports_dir, ML_LC_07_STAGE)
    _atomic_write_text(report_path, _render_ml_lc_07_report(payload, table))
    state = {
        "stage": ML_LC_07_STAGE, "title": ML_LC_07_TITLE, "status": "PASS",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_path": str(report_path), "manifest_path": str(manifest_path),
        "selected_candidate": payload["locked_candidate"],
        "selected_threshold": payload["selected_threshold"],
    }
    _atomic_write_text(marker_path, json.dumps(state, ensure_ascii=False, indent=2))
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run TV1 Modeling stages.")
    parser.add_argument(
        "--stage",
        required=True,
        choices=[
            STAGE, ML_LC_03_STAGE, ML_LC_04_STAGE, ML_LC_05_STAGE,
            ML_LC_06_STAGE, ML_LC_07_STAGE, ML_LC_08_STAGE,
            ML_LC_09_STAGE, ML_LC_10_STAGE, ML_LC_11_STAGE,
            ML_LC_12_STAGE, ML_LC_13_STAGE,
        ],
    )
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
            elif args.stage == ML_LC_04_STAGE:
                payload = run_ml_lc_04(
                    canonical_path=Path(args.canonical_path),
                    dictionary_path=Path(args.dictionary_path),
                    manifest_path=Path(args.manifest_path),
                    output_dir=Path(args.output_dir),
                    reports_dir=Path(args.reports_dir),
                )
            elif args.stage == ML_LC_05_STAGE:
                payload = run_ml_lc_05(
                    canonical_path=Path(args.canonical_path),
                    dictionary_path=Path(args.dictionary_path),
                    manifest_path=Path(args.manifest_path),
                    output_dir=Path(args.output_dir),
                    reports_dir=Path(args.reports_dir),
                )
            elif args.stage == ML_LC_06_STAGE:
                payload = run_ml_lc_06(
                    output_dir=Path(args.output_dir),
                    reports_dir=Path(args.reports_dir),
                )
            elif args.stage == ML_LC_07_STAGE:
                payload = run_ml_lc_07(
                    output_dir=Path(args.output_dir),
                    reports_dir=Path(args.reports_dir),
                )
            else:
                if args.stage == ML_LC_08_STAGE:
                    from src.models.frozen_test import run_ml_lc_08
                    payload = run_ml_lc_08(
                        canonical_path=Path(args.canonical_path),
                        dictionary_path=Path(args.dictionary_path),
                        manifest_path=Path(args.manifest_path),
                        output_dir=Path(args.output_dir),
                        reports_dir=Path(args.reports_dir),
                    )
                else:
                    if args.stage == ML_LC_09_STAGE:
                        from src.models.explainability import run_ml_lc_09
                        payload = run_ml_lc_09(
                            canonical_path=Path(args.canonical_path),
                            dictionary_path=Path(args.dictionary_path),
                            output_dir=Path(args.output_dir),
                            reports_dir=Path(args.reports_dir),
                        )
                    else:
                        if args.stage == ML_LC_10_STAGE:
                            payload = run_ml_lc_10(
                                canonical_path=Path(args.canonical_path),
                                dictionary_path=Path(args.dictionary_path),
                                output_dir=Path(args.output_dir),
                                reports_dir=Path(args.reports_dir),
                            )
                        elif args.stage == ML_LC_11_STAGE:
                            payload = run_ml_lc_11(
                                output_dir=Path(args.output_dir),
                                reports_dir=Path(args.reports_dir),
                            )
                        elif args.stage == ML_LC_12_STAGE:
                            payload = run_ml_lc_12(
                                canonical_path=Path(args.canonical_path),
                                dictionary_path=Path(args.dictionary_path),
                                tv2_manifest_path=Path(args.manifest_path),
                                output_dir=Path(args.output_dir),
                                reports_dir=Path(args.reports_dir),
                            )
                        else:
                            payload = run_ml_lc_13_audit(
                                output_dir=Path(args.output_dir),
                                reports_dir=Path(args.reports_dir),
                            )
        status = payload.get("status", "PASS")
        print(json.dumps({"stage": args.stage, "status": status, "payload": payload}, ensure_ascii=False))
        return 0 if status == "PASS" else 1
    except (GateError, SplitValidationError, FileNotFoundError, ValueError, OSError) as exc:
        if args.stage == ML_LC_08_STAGE:
            # A rejected rerun must never replace a prior PASS report/state with FAIL.
            print(json.dumps({"stage": args.stage, "status": "FAIL", "message": str(exc)}, ensure_ascii=False))
            return 1
        result = _write_stage_evidence(
            Path(args.reports_dir),
            stage=args.stage,
            title=(
                STAGE_TITLE
                if args.stage == STAGE
                else ML_LC_03_TITLE
                if args.stage == ML_LC_03_STAGE
                else ML_LC_04_TITLE
                if args.stage == ML_LC_04_STAGE
                else ML_LC_05_TITLE
                if args.stage == ML_LC_05_STAGE
                else ML_LC_06_TITLE
                if args.stage == ML_LC_06_STAGE
                else ML_LC_08_TITLE
                if args.stage == ML_LC_08_STAGE
                else ML_LC_09_TITLE
                if args.stage == ML_LC_09_STAGE
                else ML_LC_10_TITLE
                if args.stage == ML_LC_10_STAGE
                else ML_LC_11_TITLE
                if args.stage == ML_LC_11_STAGE
                else "Full-data XGBoost refit"
                if args.stage == ML_LC_12_STAGE
                else "Conditional modeling-to-dashboard handoff audit"
                if args.stage == ML_LC_13_STAGE
                else ML_LC_07_TITLE
            ),
            status="FAIL",
            message=str(exc),
            payload={},
        )
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
