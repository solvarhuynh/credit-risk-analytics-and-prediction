"""Create reproducible validation-only model evaluation figures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

from src.models.evaluation import align_validation_predictions


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "data" / "processed" / "modeling"
FIGURE_DIR = PROJECT_ROOT / "reports" / "figures" / "modeling"
EXPECTED_ROWS = 269_070
POSITIVE_CLASS = 1
MODEL_SOURCES = {
    "logistic_baseline": {
        "label": "Logistic Regression",
        "prediction_file": "ml_lc_03_validation_predictions.parquet",
        "manifest_file": "ml_lc_03_manifest.json",
        "metric_path": ("validation_metrics",),
        "artifact_path_key": "model_artifact_path",
        "color": "#64748B",
    },
    "logistic_weighted": {
        "label": "Weighted Logistic Regression",
        "prediction_file": "ml_lc_04_weighted_validation_predictions.parquet",
        "manifest_file": "ml_lc_04_manifest.json",
        "metric_path": ("weighted_metrics",),
        "artifact_path_key": "weighted_model_artifact_path",
        "color": "#D97706",
    },
    "xgboost_candidate": {
        "label": "XGBoost Candidate",
        "prediction_file": "ml_lc_05_xgboost_validation_predictions.parquet",
        "manifest_file": "ml_lc_05_manifest.json",
        "metric_path": ("validation_metrics",),
        "artifact_path_key": "model_artifact_path",
        "color": "#2563EB",
    },
}
OUTPUT_FILES = {
    "roc": "model_roc_curve.png",
    "precision_recall": "model_precision_recall_curve.png",
    "confusion": "model_confusion_matrix.png",
    "calibration": "model_calibration_curve.png",
}


@dataclass(frozen=True)
class EvaluationInputs:
    predictions: dict[str, pd.DataFrame]
    validation_ids: pd.DataFrame
    manifests: dict[str, dict[str, Any]]
    locked_threshold: float
    threshold_manifest: dict[str, Any]
    positive_prevalence: float


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Manifest phải là JSON object: {path}")
    return value


def _nested_value(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    for key in path:
        value = value[key]
    return value


def _validate_probability_metrics(
    model_name: str,
    predictions: pd.DataFrame,
    manifest: dict[str, Any],
    metric_path: tuple[str, ...],
) -> None:
    metrics = _nested_value(manifest, metric_path)
    labels = predictions["target"].to_numpy(dtype=np.int8)
    probability = predictions["predicted_pd"].to_numpy(dtype=float)
    observed = {
        "roc_auc": float(roc_auc_score(labels, probability)),
        "pr_auc": float(average_precision_score(labels, probability)),
    }
    for metric, calculated in observed.items():
        if metric not in metrics or not np.isclose(
            calculated, float(metrics[metric]), rtol=0, atol=1e-8
        ):
            raise ValueError(
                f"{model_name}: Validation {metric} không khớp manifest; "
                f"tính lại={calculated:.12f}, manifest={metrics.get(metric)}"
            )


def load_validation_inputs() -> EvaluationInputs:
    """Load and verify only saved Validation IDs, scores, and manifests."""
    ids_path = MODEL_DIR / "validation_ids.parquet"
    if not ids_path.is_file():
        raise FileNotFoundError(f"Thiếu Validation IDs: {ids_path}")
    ids = pd.read_parquet(ids_path, columns=["loan_id", "target"])
    if len(ids) != EXPECTED_ROWS:
        raise ValueError(f"Validation IDs phải có {EXPECTED_ROWS:,} dòng.")

    raw_predictions: dict[str, pd.DataFrame] = {}
    manifests: dict[str, dict[str, Any]] = {}
    for name, source in MODEL_SOURCES.items():
        pred_path = MODEL_DIR / source["prediction_file"]
        manifest_path = MODEL_DIR / source["manifest_file"]
        if not pred_path.is_file() or not manifest_path.is_file():
            raise FileNotFoundError(f"Thiếu artifact Validation cho {name}.")
        raw_predictions[name] = pd.read_parquet(
            pred_path, columns=["loan_id", "target", "predicted_pd"]
        )
        manifests[name] = _read_json(manifest_path)
        if manifests[name].get("status") != "PASS":
            raise ValueError(f"Manifest {name} không có trạng thái PASS.")
        if int(manifests[name].get("validation_rows", -1)) != EXPECTED_ROWS:
            raise ValueError(f"Manifest {name} không khẳng định cohort Validation chuẩn.")

    aligned = align_validation_predictions(
        raw_predictions, ids, expected_rows=EXPECTED_ROWS
    )
    for name, predictions in aligned.items():
        source = MODEL_SOURCES[name]
        _validate_probability_metrics(
            name, predictions, manifests[name], source["metric_path"]
        )

    threshold_manifest = _read_json(MODEL_DIR / "ml_lc_07_manifest.json")
    if (
        threshold_manifest.get("status") != "PASS"
        or threshold_manifest.get("selection_partition") != "validation"
        or threshold_manifest.get("locked_candidate") != "xgboost_candidate"
    ):
        raise ValueError("ML-LC-07 chưa xác nhận candidate/threshold từ Validation.")
    threshold = float(threshold_manifest["selected_threshold"])
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Threshold ML-LC-07 không hợp lệ.")

    xgb = aligned["xgboost_candidate"]
    matrix = confusion_matrix(
        xgb["target"],
        xgb["predicted_pd"] >= threshold,
        labels=[0, 1],
    ).astype(int).tolist()
    selected_metrics = threshold_manifest["selected_metrics"]
    if matrix != selected_metrics.get("confusion_matrix"):
        raise ValueError("Confusion Matrix tại threshold không khớp ML-LC-07.")

    return EvaluationInputs(
        predictions=aligned,
        validation_ids=ids,
        manifests=manifests,
        locked_threshold=threshold,
        threshold_manifest=threshold_manifest,
        positive_prevalence=float(ids["target"].mean()),
    )


def _save_figure(fig: plt.Figure, filename: str) -> Path:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    destination = FIGURE_DIR / filename
    fig.savefig(destination, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    if not destination.is_file() or destination.stat().st_size < 10_000:
        raise OSError(f"PNG đầu ra thiếu hoặc bất thường: {destination}")
    return destination


def create_roc_figure(inputs: EvaluationInputs) -> Path:
    fig, ax = plt.subplots(figsize=(9, 7))
    for name, predictions in inputs.predictions.items():
        source = MODEL_SOURCES[name]
        y_true = predictions["target"].to_numpy(dtype=np.int8)
        probability = predictions["predicted_pd"].to_numpy(dtype=float)
        fpr, tpr, _ = roc_curve(y_true, probability, pos_label=POSITIVE_CLASS)
        auc = roc_auc_score(y_true, probability)
        style = {"logistic_baseline": "--", "logistic_weighted": ":",
                 "xgboost_candidate": "-"}[name]
        ax.plot(fpr, tpr, color=source["color"], linewidth=2.2, linestyle=style,
                label=f"{source['label']} (AUC = {auc:.4f})")
    ax.plot([0, 1], [0, 1], linestyle="--", color="#9CA3AF", linewidth=1.5,
            label="Ngẫu nhiên (AUC = 0.5000)")
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="False Positive Rate",
           ylabel="True Positive Rate",
           title="ROC Curves — Validation (Default = 1)")
    ax.grid(True, color="#E5E7EB", linewidth=0.8)
    ax.legend(loc="lower right", frameon=True, fontsize=9)
    fig.tight_layout()
    return _save_figure(fig, OUTPUT_FILES["roc"])


def create_precision_recall_figure(inputs: EvaluationInputs) -> Path:
    fig, ax = plt.subplots(figsize=(9, 7))
    for name, predictions in inputs.predictions.items():
        source = MODEL_SOURCES[name]
        y_true = predictions["target"].to_numpy(dtype=np.int8)
        probability = predictions["predicted_pd"].to_numpy(dtype=float)
        precision, recall, _ = precision_recall_curve(
            y_true, probability, pos_label=POSITIVE_CLASS
        )
        ap = average_precision_score(y_true, probability)
        style = {"logistic_baseline": "--", "logistic_weighted": ":",
                 "xgboost_candidate": "-"}[name]
        ax.plot(recall, precision, color=source["color"], linewidth=2.2,
                linestyle=style,
                label=f"{source['label']} (AP = {ap:.4f})")
    ax.axhline(inputs.positive_prevalence, linestyle="--", color="#9CA3AF",
               linewidth=1.5,
               label=f"Tỷ lệ Default trong cohort = {inputs.positive_prevalence:.2%}")
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Recall",
           ylabel="Precision",
           title="Precision–Recall Curves — Validation (Default = 1)")
    ax.grid(True, color="#E5E7EB", linewidth=0.8)
    ax.legend(loc="upper right", frameon=True, fontsize=9)
    fig.tight_layout()
    return _save_figure(fig, OUTPUT_FILES["precision_recall"])


def create_confusion_figure(inputs: EvaluationInputs) -> Path:
    predictions = inputs.predictions["xgboost_candidate"]
    y_true = predictions["target"].to_numpy(dtype=np.int8)
    y_pred = (predictions["predicted_pd"].to_numpy(dtype=float)
              >= inputs.locked_threshold).astype(np.int8)
    matrix = confusion_matrix(y_true, y_pred, labels=[0, 1])
    row_totals = matrix.sum(axis=1, keepdims=True)
    row_rates = np.divide(matrix, row_totals, out=np.zeros_like(matrix, dtype=float),
                          where=row_totals != 0)
    fig, ax = plt.subplots(figsize=(8.5, 7))
    image = ax.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="Số khoản vay")
    names = (("TN", "FP"), ("FN", "TP"))
    for row in range(2):
        for col in range(2):
            ax.text(col, row,
                    f"{names[row][col]}\n{matrix[row, col]:,}\n{row_rates[row, col]:.1%} theo hàng",
                    ha="center", va="center", fontsize=12,
                    color="white" if matrix[row, col] > matrix.max() * 0.55 else "#111827")
    ax.set(xticks=[0, 1], yticks=[0, 1],
           xticklabels=["Predicted 0", "Predicted 1"],
           yticklabels=["Actual 0", "Actual 1"],
           xlabel="Predicted class", ylabel="Actual class",
           title=("XGBoost Candidate — Validation\n"
                  f"N = {len(predictions):,} | threshold = {inputs.locked_threshold:.12f} | TARGET=1: Default"))
    fig.tight_layout()
    return _save_figure(fig, OUTPUT_FILES["confusion"])


def create_calibration_figure(inputs: EvaluationInputs) -> tuple[Path, pd.DataFrame, dict[str, float]]:
    predictions = inputs.predictions["xgboost_candidate"]
    y_true = predictions["target"].to_numpy(dtype=np.int8)
    probability = predictions["predicted_pd"].to_numpy(dtype=float)
    bins = pd.qcut(probability, q=10, duplicates="drop")
    grouped = predictions.assign(_bin=bins).groupby("_bin", observed=True).agg(
        sample_count=("target", "size"),
        mean_predicted_pd=("predicted_pd", "mean"),
        observed_default_rate=("target", "mean"),
    ).reset_index(drop=True)
    if len(grouped) != 10 or (grouped["sample_count"] < 500).any():
        raise ValueError("Calibration quantile bins phải có 10 nhóm và ít nhất 500 mẫu/bin.")
    fraction_positive, mean_predicted = calibration_curve(
        y_true, probability, n_bins=10, strategy="quantile"
    )
    if len(fraction_positive) != len(grouped) or not np.allclose(
        fraction_positive, grouped["observed_default_rate"].to_numpy(), atol=1e-12
    ) or not np.allclose(mean_predicted, grouped["mean_predicted_pd"].to_numpy(), atol=1e-12):
        raise ValueError("Calibration aggregation differs from sklearn quantile calibration.")
    metrics = {
        "brier_score": float(brier_score_loss(y_true, probability)),
        "log_loss": float(log_loss(y_true, probability, labels=[0, 1])),
    }

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.plot([0, 1], [0, 1], linestyle="--", color="#9CA3AF", linewidth=1.5,
            label="Hiệu chỉnh hoàn hảo")
    ax.plot(mean_predicted, fraction_positive, marker="o", color="#2563EB",
            linewidth=2.3, markersize=7, label="XGBoost Candidate")
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean predicted probability per bin",
           ylabel="Observed default rate per bin",
           title="Calibration — XGBoost Candidate, Validation\n"
                 f"N = {len(predictions):,} | 10 quantile bins, n/bin = {int(grouped['sample_count'].iloc[0]):,} | TARGET=1: Default")
    ax.text(0.02, 0.98,
            f"Brier = {metrics['brier_score']:.4f}   Log Loss = {metrics['log_loss']:.4f}",
            transform=ax.transAxes, va="top", ha="left", fontsize=9,
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#D1D5DB"})
    ax.grid(True, color="#E5E7EB", linewidth=0.8)
    ax.legend(loc="lower right", frameon=True)
    fig.tight_layout()
    return _save_figure(fig, OUTPUT_FILES["calibration"]), grouped, metrics


def _figure_manifest(inputs: EvaluationInputs, calibration_bins: pd.DataFrame,
                     calibration_metrics: dict[str, float]) -> dict[str, Any]:
    shared = {
        "evaluation_split": "Validation",
        "sample_count": EXPECTED_ROWS,
        "positive_class": {"target": 1, "meaning": "Default"},
        "labels_source": "data/processed/modeling/validation_ids.parquet",
        "validation_cohort_verified": True,
        "source_predictions_verified_against_validation_ids": True,
    }
    result: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "src/models/evaluation_figures.py",
        "data_scope": "Saved Validation predictions only; no model loaded or fitted; no Frozen Test predictions read.",
        "precision_recall_definition": "Average Precision from sklearn.metrics.average_precision_score; matches repo pr_auc (not trapezoidal area).",
        "figures": [],
    }
    names = {
        "logistic_baseline": "Logistic Regression",
        "logistic_weighted": "Weighted Logistic Regression",
        "xgboost_candidate": "XGBoost Candidate",
    }
    for fid, key, chart, filename, metrics in [
        ("FIGURE-01", "all", "ROC curve", OUTPUT_FILES["roc"], {"roc_auc": "ROC AUC per model"}),
        ("FIGURE-02", "all", "Precision–Recall curve", OUTPUT_FILES["precision_recall"],
         {"average_precision": "Average Precision per model", "positive_prevalence": inputs.positive_prevalence}),
        ("FIGURE-03", "xgboost_candidate", "Confusion matrix heatmap", OUTPUT_FILES["confusion"],
         {"locked_threshold": inputs.locked_threshold, "matrix_order": "[[TN, FP], [FN, TP]]",
          "matrix": inputs.threshold_manifest["selected_metrics"]["confusion_matrix"]}),
        ("FIGURE-04", "xgboost_candidate", "Calibration plot", OUTPUT_FILES["calibration"],
         {**calibration_metrics, "bin_strategy": "quantile", "bin_count": len(calibration_bins),
          "bin_sample_counts": calibration_bins["sample_count"].astype(int).tolist()}),
    ]:
        model_keys = list(MODEL_SOURCES) if key == "all" else [key]
        result["figures"].append({
            "figure_id": fid,
            "filename": filename,
            "chart_type": chart,
            "models": [{
                "model_name": names[model_key],
                "model_artifact_path": manifests_path(
                    MODEL_SOURCES[model_key]["manifest_file"],
                    MODEL_SOURCES[model_key]["artifact_path_key"],
                ),
                "source_prediction_file": f"data/processed/modeling/{MODEL_SOURCES[model_key]['prediction_file']}",
                "validation_manifest": f"data/processed/modeling/{MODEL_SOURCES[model_key]['manifest_file']}",
            } for model_key in model_keys],
            **shared,
            "metrics_displayed": metrics,
            "script": "src/models/evaluation_figures.py",
            "verification_status": "PASS — source IDs, labels, metrics, and cohort verified against saved Validation artifacts",
        })
    return result


def manifests_path(manifest_file: str, key: str) -> str:
    manifest = _read_json(MODEL_DIR / manifest_file)
    value = manifest.get(key)
    if not value:
        raise ValueError(f"{manifest_file} thiếu {key}.")
    try:
        return str(Path(value).resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value)


def main() -> int:
    inputs = load_validation_inputs()
    generated = [create_roc_figure(inputs), create_precision_recall_figure(inputs),
                 create_confusion_figure(inputs)]
    calibration_path, bins, metrics = create_calibration_figure(inputs)
    generated.append(calibration_path)
    manifest = _figure_manifest(inputs, bins, metrics)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = FIGURE_DIR / "figures_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Generated validation-only figures:")
    for path in generated:
        print(f"{path.relative_to(PROJECT_ROOT)} ({path.stat().st_size:,} bytes)")
    print(f"{manifest_path.relative_to(PROJECT_ROOT)}")
    print(f"XGBoost Validation threshold: {inputs.locked_threshold:.17g}")
    print("Calibration bins:")
    print(bins.to_string(index=False))
    print(f"Calibration diagnostics: {metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
