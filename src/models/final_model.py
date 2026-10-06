"""Full-data refit ML-LC-12 và audit handoff ML-LC-13."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.config import (
    CANONICAL_DATASET_PATH,
    DATA_DICTIONARY_PATH,
    DATASET_MANIFEST_PATH,
    ML_LC_05_MANIFEST_PATH,
    ML_LC_06_MANIFEST_PATH,
    ML_LC_07_MANIFEST_PATH,
    ML_LC_08_MANIFEST_PATH,
    ML_LC_09_MANIFEST_PATH,
    ML_LC_10_MANIFEST_PATH,
    ML_LC_11_MANIFEST_PATH,
    ML_LC_12_MANIFEST_PATH,
    ML_LC_12_SCORES_PATH,
    ML_LC_13_MANIFEST_PATH,
    ML_LC_10_SCORED_TEST_PATH,
    ML_LC_11_EXPECTED_LOSS_PATH,
    ML_LC_11_RISK_TIER_SUMMARY_PATH,
    ML_LC_09_GLOBAL_IMPORTANCE_PATH,
    ML_LC_09_LOCAL_EXPLANATIONS_PATH,
    ML_LC_09_SHAP_SAMPLE_PATH,
    MODELING_DIR,
    REPORTS_DIR,
    XGBOOST_CANDIDATE_PATH,
    XGBOOST_FULL_REFIT_PATH,
)
from src.data.column_policy import approved_model_features
from src.models.modeling_pipeline import GateError, build_feature_schema, load_canonical_input, build_xgboost_pipeline
from src.models.scoring import (
    ML_LC_10_CONTEXT_COLUMNS,
    ML_LC_10_LOCKED_THRESHOLD,
    build_ml_lc_10_scored_dataset,
)


ML_LC_12_STAGE = "ml-lc-12"
ML_LC_13_STAGE = "ml-lc-13"
EXPECTED_LABELED_ROWS = 1_345_350
EXPECTED_APPROVED_FEATURES = 106
EXPECTED_ACTUAL_FEATURES = 103
REFIT_MODEL_VERSION = "xgboost_full_refit_ml-lc-12"
PARAMETER_KEYS = (
    "n_estimators", "max_depth", "learning_rate", "subsample", "colsample_bytree",
    "random_state", "objective", "eval_metric", "tree_method", "n_jobs",
)
ML12_REQUIRED_SCORE_COLUMNS = (
    "loan_id", "target", "predicted_pd", "decision_threshold", "predicted_class",
    "risk_score", "credit_score", "risk_tier", "model_version",
)
STAGE_MANIFEST_FILES = (
    "ml_lc_05_manifest.json", "ml_lc_06_manifest.json", "ml_lc_07_manifest.json",
    "ml_lc_08_manifest.json", "ml_lc_09_manifest.json", "ml_lc_10_manifest.json",
    "ml_lc_11_manifest.json",
)
V05_PATHS = (
    "ml_lc_09_global_importance.csv",
    "ml_lc_09_local_explanations.csv",
    "ml_lc_09_shap_sample.parquet",
)


def _sha256(path: Path) -> str:
    """Tính SHA-256 theo luồng để bảo vệ artifacts đầu vào."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    """Đọc JSON stage object và fail closed nếu thiếu/sai format."""
    if not path.is_file():
        raise GateError(f"Thiếu prerequisite JSON: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GateError(f"Không đọc được prerequisite JSON: {path}") from exc
    if not isinstance(value, dict):
        raise GateError(f"Prerequisite JSON phải là object: {path}")
    return value


def _atomic_write(path: Path, callback: Any) -> None:
    """Tạo output qua file partial rồi atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    try:
        callback(partial)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Ghi JSON không chứa NaN/Infinity."""
    _atomic_write(path, lambda target: target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    ))


def _require_prior_pass(output_dir: Path, reports_dir: Path) -> dict[str, dict[str, Any]]:
    """Xác nhận ML-LC-05..11 manifest/state đều PASS."""
    manifests: dict[str, dict[str, Any]] = {}
    for filename in STAGE_MANIFEST_FILES:
        stage = filename.removesuffix("_manifest.json").replace("_", "-")
        data = _load_json(output_dir / filename)
        marker = _load_json(reports_dir / "tv1_stages/state" / f"{stage}.json")
        if data.get("stage") != stage or data.get("status") != "PASS":
            raise GateError(f"{stage} manifest chưa PASS.")
        if marker.get("stage") != stage or marker.get("status") != "PASS":
            raise GateError(f"{stage} state marker chưa PASS.")
        manifests[stage] = data
    return manifests


def _render_ml12_report(manifest: dict[str, Any]) -> str:
    """Render báo cáo ML-LC-12 dễ đọc, không gắn metrics test cho model refit."""
    counts = manifest["target_counts"]
    return "\n".join([
        "# ML-LC-12 — Full-data Refit",
        "",
        "## 1. Vì sao refit?",
        "",
        "Candidate và operating threshold đã được chọn trước đó; frozen test đã cung cấp đánh giá không thiên lệch ở ML-LC-08. Bước này fit cấu hình đã khóa trên toàn bộ labeled canonical rows để tạo artifact demo/inference dùng nhiều dữ liệu hơn.",
        "",
        "## 2. Model đã đánh giá và model refit",
        "",
        f"- **Evaluated model:** `{manifest['evaluated_model_artifact']}`; chỉ model này gắn với metrics frozen-test ML-LC-08.",
        f"- **Full-data refit model:** `{manifest['full_refit_model_artifact']}`; được fit trên toàn bộ labeled canonical population. Đây là model khác, không có unbiased test score mới.",
        "- ML-LC-08 test metrics không được tính lại hoặc gán cho full-data refit.",
        "",
        "## 3. Cấu hình đã khóa",
        "",
        "| Parameter | Value |",
        "|---|---:|",
        *[f"| `{name}` | `{value}` |" for name, value in manifest["locked_hyperparameters"].items()],
        "",
        f"Approved features: {manifest['approved_feature_count']}; actual model inputs: {manifest['actual_feature_count']}; transformed inputs: {manifest['transformed_feature_count']}.",
        "Preprocessing được fit trên `full_labeled_canonical`; feature list giữ nguyên từ ML-LC-05.",
        "",
        "## 4. Toàn bộ labeled data",
        "",
        f"Rows used: {manifest['full_refit_rows']:,}. Target 0 (non-default): {counts['0']:,}; target 1 (default): {counts['1']:,}.",
        f"Fit duration: {manifest['fit_duration_seconds']:.2f} seconds.",
        "",
        "## 5. Threshold carried forward",
        "",
        f"Threshold `{manifest['carried_forward_threshold']}` được chọn từ validation của evaluated candidate tại ML-LC-07. Không tìm hoặc tái xác nhận threshold trên full-data refit; score distribution của refit có thể khác.",
        "",
        "## 6. Output scores",
        "",
        f"`{manifest['full_refit_score_artifact']}` có một hàng mỗi loan_id, PD, predicted class, risk score, project credit score, risk tier và context dashboard được duyệt.",
        "Đây là **full-data refit scores / deployment-demo scoring output**, là dự đoán in-sample trên population đã dùng fit; không phải unbiased test predictions hay final evaluation predictions.",
        "",
        "## 7. Giới hạn quan trọng",
        "",
        "ML-LC-08 vẫn là nguồn duy nhất cho unbiased performance evidence: ROC-AUC 0.723186, PR-AUC 0.400000, precision 0.345877, recall 0.602960, F1 0.439590, accuracy 0.693065 trên frozen test của `xgboost_candidate`. Không diễn giải các chỉ số này như kết quả của refit.",
        "Không chọn lại model, không đổi features/hyperparameters/threshold, không dùng frozen test để select và không tính metrics trên full-refit in-sample scores.",
        "",
        "## 8. Tiếp theo",
        "",
        "ML-LC-13 — audit handoff sang dashboard/inference contract.",
        "",
    ])


def run_ml_lc_12(
    *,
    canonical_path: Path = CANONICAL_DATASET_PATH,
    dictionary_path: Path = DATA_DICTIONARY_PATH,
    tv2_manifest_path: Path = DATASET_MANIFEST_PATH,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
    expected_rows: int = EXPECTED_LABELED_ROWS,
    expected_approved_features: int = EXPECTED_APPROVED_FEATURES,
    expected_actual_features: int = EXPECTED_ACTUAL_FEATURES,
) -> dict[str, Any]:
    """Fit cấu hình XGBoost đã khóa trên tất cả labeled canonical rows."""
    canonical_path, dictionary_path = Path(canonical_path), Path(dictionary_path)
    tv2_manifest_path, output_dir, reports_dir = Path(tv2_manifest_path), Path(output_dir), Path(reports_dir)
    prior = _require_prior_pass(output_dir, reports_dir)
    ml05, ml06, ml07, ml08, ml09, ml10, ml11 = (
        prior[f"ml-lc-{number:02d}"] for number in range(5, 12)
    )
    if (ml06.get("selected_candidate") != "xgboost_candidate"
            or ml06.get("status") != "PASS"
            or ml07.get("locked_candidate") != "xgboost_candidate"
            or ml07.get("threshold_selected") is not True
            or ml07.get("selection_partition") != "validation"
            or ml07.get("selected_threshold") != ML_LC_10_LOCKED_THRESHOLD
            or ml08.get("selected_candidate") != "xgboost_candidate"
            or ml08.get("selected_threshold") != ML_LC_10_LOCKED_THRESHOLD
            or ml08.get("test_evaluated") is not True
            or ml08.get("frozen_test_used_for_model_selection") is not False
            or ml09.get("model_retrained") is not False
            or ml09.get("model_sha256_after") != _sha256(output_dir / XGBOOST_CANDIDATE_PATH.name)
            or ml10.get("model") != "xgboost_candidate"
            or ml10.get("decision_threshold") != ML_LC_10_LOCKED_THRESHOLD
            or ml10.get("threshold_changed") is not False
            or ml11.get("status") != "PASS"):
        raise GateError("ML-LC-06..11 candidate/threshold/evaluation locks are inconsistent.")
    if (not canonical_path.is_file() or not dictionary_path.is_file()
            or not tv2_manifest_path.is_file()):
        raise GateError("TV2 canonical handoff is incomplete.")

    protected_paths = {
        "xgboost_candidate.joblib": output_dir / XGBOOST_CANDIDATE_PATH.name,
        **{name: output_dir / name for name in STAGE_MANIFEST_FILES},
        "cleaned_dataset.parquet": canonical_path,
        "data_dictionary.csv": dictionary_path,
        "cleaned_dataset_manifest.json": tv2_manifest_path,
    }
    if any(not path.is_file() for path in protected_paths.values()):
        raise GateError("Missing model lock, manifest or canonical source for hash protection.")
    protected_before = {name: _sha256(path) for name, path in protected_paths.items()}
    m08_hashes = ml08.get("protected_sha256_before", {})
    m10_hashes = ml10.get("protected_sha256_before", {})
    if (ml07.get("source_model_sha256_after") != protected_before["xgboost_candidate.joblib"]
            or m08_hashes.get("xgboost_candidate.joblib") != protected_before["xgboost_candidate.joblib"]
            or m10_hashes.get("xgboost_candidate.joblib") != protected_before["xgboost_candidate.joblib"]
            or m08_hashes.get("ml_lc_07_manifest.json") != protected_before["ml_lc_07_manifest.json"]
            or ml08.get("input_sha256", {}).get("cleaned_dataset.parquet")
            != protected_before["cleaned_dataset.parquet"]):
        raise GateError("Current canonical/model lock hashes do not match the evaluated history.")

    dataset, dictionary, tv2_manifest = load_canonical_input(
        dataset_path=canonical_path, dictionary_path=dictionary_path, manifest_path=tv2_manifest_path,
    )
    if (tv2_manifest.get("dataset_id") != "lending_club_2007_2018"
            or tv2_manifest.get("run_status") != "PASS"
            or tv2_manifest.get("quality_status") != "PASS"
            or tv2_manifest.get("leakage_gate") != "PASS"
            or tv2_manifest.get("labeled_rows") != len(dataset)
            or len(dataset) != expected_rows):
        raise GateError("TV2 canonical labeled dataset status/row count is invalid.")
    if ("loan_id" not in dataset or "target" not in dataset
            or dataset["loan_id"].isna().any() or not dataset["loan_id"].is_unique
            or dataset["target"].isna().any() or not dataset["target"].isin([0, 1]).all()):
        raise GateError("Full refit requires unique loan_id and complete binary target.")
    schema = build_feature_schema(dataset, dictionary)
    actual_features = ml05.get("actual_features")
    if (len(schema.approved_features) != ml05.get("approved_feature_count")
            or len(schema.approved_features) != expected_approved_features
            or not isinstance(actual_features, list)
            or len(actual_features) != ml05.get("actual_feature_count")
            or len(actual_features) != expected_actual_features
            or not set(actual_features).issubset(set(schema.approved_features))
            or not set(actual_features).issubset(set(dataset.columns))):
        raise GateError("ML-LC-05 exact approved/actual feature schema does not match canonical input.")
    target_counts = dataset["target"].value_counts().sort_index().to_dict()
    manifest_counts = tv2_manifest.get("target_counts", {})
    if {str(key): int(value) for key, value in target_counts.items()} != {
        str(key): int(value) for key, value in manifest_counts.items()
    }:
        raise GateError("Canonical target counts do not match TV2 manifest.")

    candidate_path = protected_paths["xgboost_candidate.joblib"]
    candidate = joblib.load(candidate_path)
    if not hasattr(candidate, "named_steps") or not {"normalize_missing", "preprocess", "model"}.issubset(candidate.named_steps):
        raise GateError("Evaluated model artifact lacks expected fitted pipeline steps.")
    candidate_model = candidate.named_steps["model"]
    manifest_params = ml05.get("model_parameters", {})
    candidate_params = {name: candidate_model.get_params().get(name) for name in PARAMETER_KEYS}
    if candidate_params != {name: manifest_params.get(name) for name in PARAMETER_KEYS}:
        raise GateError("ML-LC-05 manifest hyperparameters do not match evaluated model artifact.")
    if (list(candidate.named_steps["normalize_missing"].feature_names_in_) != actual_features
            or len(candidate.named_steps["preprocess"].get_feature_names_out()) != ml05.get("transformed_feature_count")):
        raise GateError("Evaluated model's fitted feature/preprocessing contract differs from ML-LC-05.")

    input_frames = dataset.loc[:, actual_features]
    y = dataset["target"].astype(np.int8)
    pipeline = build_xgboost_pipeline(
        dataset,
        schema,
        feature_columns=actual_features,
        random_state=int(manifest_params["random_state"]),
        n_estimators=int(manifest_params["n_estimators"]),
        max_depth=int(manifest_params["max_depth"]),
        learning_rate=float(manifest_params["learning_rate"]),
        subsample=float(manifest_params["subsample"]),
        colsample_bytree=float(manifest_params["colsample_bytree"]),
    )
    started = time.perf_counter()
    pipeline.fit(input_frames, y)
    fit_seconds = time.perf_counter() - started
    transformed_count = len(pipeline.named_steps["preprocess"].get_feature_names_out())
    if transformed_count < len(actual_features):
        raise GateError("Full-data preprocessor produced fewer transformed columns than raw model features.")
    probabilities = pipeline.predict_proba(input_frames)[:, 1]
    if (len(probabilities) != len(dataset) or not np.isfinite(probabilities).all()
            or not np.all((probabilities >= 0) & (probabilities <= 1))):
        raise GateError("Full-data refit score probabilities are invalid.")
    predictions = pd.DataFrame({
        "loan_id": dataset["loan_id"].reset_index(drop=True),
        "target": y.reset_index(drop=True),
        "predicted_pd": probabilities,
        "predicted_class": (probabilities >= ML_LC_10_LOCKED_THRESHOLD).astype(np.int8),
    })
    context_columns = [name for name in ML_LC_10_CONTEXT_COLUMNS if name in dataset.columns]
    if set(context_columns) != set(ML_LC_10_CONTEXT_COLUMNS):
        raise GateError("Canonical source is missing an ML-LC-10-approved context field.")
    safe_classes = dictionary.set_index("column_name")["policy_class"].to_dict()
    if any(safe_classes.get(name) not in {"APPLICATION_TIME", "CREDIT_SNAPSHOT"} for name in context_columns):
        raise GateError("Dashboard context includes an ineligible policy class.")
    context = dataset[["loan_id", *context_columns]].copy()
    scored = build_ml_lc_10_scored_dataset(
        predictions, context,
        decision_threshold=ML_LC_10_LOCKED_THRESHOLD,
        model_version=REFIT_MODEL_VERSION,
    )
    if (len(scored) != expected_rows or scored["loan_id"].isna().any()
            or not scored["loan_id"].is_unique):
        raise GateError("Full refit score artifact must preserve one row per loan_id.")

    protected_after = {name: _sha256(path) for name, path in protected_paths.items()}
    if protected_after != protected_before:
        raise GateError("ML-LC-12 changed an evaluated model/source/lock artifact.")
    refit_path = output_dir / XGBOOST_FULL_REFIT_PATH.name
    if refit_path.resolve() == candidate_path.resolve():
        raise GateError("Full-data refit output must never overwrite the evaluated candidate.")
    score_path = output_dir / ML_LC_12_SCORES_PATH.name
    manifest_path = output_dir / ML_LC_12_MANIFEST_PATH.name
    report_path = reports_dir / "tv1_stages/ml-lc-12.md"
    state_path = reports_dir / "tv1_stages/state/ml-lc-12.json"
    _atomic_write(refit_path, lambda target: joblib.dump(pipeline, target))
    _atomic_write(score_path, lambda target: scored.to_parquet(target, index=False))
    refit_hash = _sha256(refit_path)
    if _sha256(candidate_path) != protected_before[candidate_path.name]:
        raise GateError("Evaluated xgboost_candidate.joblib was overwritten or changed.")
    manifest: dict[str, Any] = {
        "stage": ML_LC_12_STAGE, "status": "PASS",
        "canonical_dataset_path": str(canonical_path),
        "canonical_dataset_sha256": protected_before["cleaned_dataset.parquet"],
        "source_rows": len(dataset), "full_refit_rows": len(dataset),
        "source_model": "xgboost_candidate", "refit_model": "xgboost_full_refit",
        "target_counts": {str(key): int(value) for key, value in target_counts.items()},
        "preprocessing_fit_partition": "full_labeled_canonical",
        "locked_hyperparameters": candidate_params,
        "approved_feature_count": len(schema.approved_features),
        "actual_feature_count": len(actual_features),
        "actual_features": actual_features,
        "transformed_feature_count": transformed_count,
        "excluded_safe_features": ml05.get("excluded_safe_features", []),
        "fit_duration_seconds": fit_seconds,
        "refit_model_sha256": refit_hash,
        "threshold_source": "ml-lc-07 validation predictions of the evaluated candidate",
        "carried_forward_threshold": ML_LC_10_LOCKED_THRESHOLD,
        "threshold_retuned": False, "model_selection_changed": False,
        "hyperparameters_changed": False, "feature_policy_changed": False,
        "frozen_test_reused_for_selection": False,
        "frozen_test_metrics_recomputed": False,
        "unbiased_performance_source": "ml-lc-08 evaluated candidate",
        "unbiased_performance_model": "xgboost_candidate",
        "unbiased_performance_source_path": str(output_dir / "ml_lc_08_manifest.json"),
        "evaluated_model_artifact": str(candidate_path),
        "evaluated_model_sha256": protected_before[candidate_path.name],
        "full_refit_model_artifact": str(refit_path),
        "full_refit_model_sha256": refit_hash,
        "full_refit_score_artifact": str(score_path),
        "score_population_type": "full-data refit scores; in-sample deployment/demo output, not unbiased test predictions",
        "score_rows": len(scored),
        "score_model_version": REFIT_MODEL_VERSION,
        "score_policy_source": "reused ML-LC-10 functions and locked threshold",
        "expected_loss_included": False,
        "expected_loss_source": "existing ML-LC-11 artifact; not duplicated on refit rows",
        "protected_sha256_before": protected_before,
        "protected_sha256_after": protected_after,
        "next_stage": ML_LC_13_STAGE,
    }
    _write_json(manifest_path, manifest)
    _atomic_write(report_path, lambda target: target.write_text(
        _render_ml12_report(manifest), encoding="utf-8"
    ))
    state = {
        "stage": ML_LC_12_STAGE, "title": "Full-data XGBoost refit", "status": "PASS",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path), "report_path": str(report_path),
        "full_refit_model_artifact": str(refit_path), "score_artifact": str(score_path),
        "full_refit_rows": len(dataset),
    }
    _write_json(state_path, state)
    return manifest


def _render_ml13_report(manifest: dict[str, Any]) -> str:
    """Render kết quả audit handoff không lặp lại data artifacts."""
    lines = [
        "# ML-LC-13 — Dashboard / Inference Handoff Audit",
        "",
        "**Status: PASS — satisfied by existing handoff artifacts**",
        "",
        "## 1. Kết luận audit",
        "",
        "ML-LC-12 scores, ML-LC-10 scoring contract, ML-LC-09 explainability outputs và ML-LC-11 Expected Loss artifacts đã cung cấp các đầu ra modeling cần thiết. Không tạo parquet handoff mới để tránh bản sao không cần thiết.",
        "Dashboard data readiness không đồng nghĩa Power BI đã được xây dựng hoặc TV3 đã tích hợp/duyệt Master PBIX.",
        "",
        "## 2. Artifact mapping",
        "",
        "| Consumer | Existing source | Audit result |",
        "|---|---|---|",
        *[f"| {item['visual']} | `{item['source']}` | READY; Power BI integration remains TV3 responsibility |" for item in manifest["dashboard_sources"]],
        "",
        "`V05` tiếp tục đọc các file explainability riêng ML-LC-09; SHAP không bị flatten vào score dataset. `V06` tiếp tục dùng ML-LC-11 scenario source; nó vẫn mô tả evaluated frozen-test population, không phải full portfolio.",
        "",
        "## 3. Scoring contract",
        "",
        f"Full-refit model: `{manifest['refit_model_artifact']}`; input schema gồm {manifest['actual_feature_count']} actual features (trong {manifest['approved_feature_count']} policy-approved features). Preprocessing nằm trong pipeline của model. Inference helper/UI không được tạo trong task này.",
        "Input một borrower phải có đúng named fields của `actual_features` trong ML-LC-12 manifest, theo schema/dtypes canonical; không truyền `loan_id`, `target`, post-loan hay unknown fields vào model. Pipeline đã gồm missing-value normalization, imputation và one-hot encoding.",
        "Output contract: `predicted_pd`; `predicted_class = (PD >= carried_forward_threshold)`; `risk_score = 100 × PD`; `credit_score = round_half_to_even(1000 × (1 − PD))`; risk tier theo ML-LC-10 boundaries. Project credit score không phải FICO. Threshold được carry từ ML-LC-07, chưa revalidated trên refit.",
        "",
        "## 4. Provenance / limitations",
        "",
        "Frozen-test metrics vẫn thuộc `xgboost_candidate` ở ML-LC-08; không gắn các metrics này vào full-data refit. Full-refit scores là in-sample. LGD/EAD scenario không được tự ghép vào score output; V06 dùng policy/artifacts ML-LC-11.",
        "",
    ]
    return "\n".join(lines)


def run_ml_lc_13_audit(
    *,
    output_dir: Path = MODELING_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> dict[str, Any]:
    """Audit existing TV1→TV3 handoff and write evidence without duplicate data."""
    output_dir, reports_dir = Path(output_dir), Path(reports_dir)
    ml12_path = output_dir / ML_LC_12_MANIFEST_PATH.name
    ml12 = _load_json(ml12_path)
    state12 = _load_json(reports_dir / "tv1_stages/state/ml-lc-12.json")
    if ml12.get("status") != "PASS" or state12.get("status") != "PASS":
        raise GateError("ML-LC-12 must PASS before ML-LC-13 handoff audit.")
    stage_manifests = {
        stage: _load_json(output_dir / f"ml_lc_{stage[-2:]}_manifest.json")
        for stage in ("ml-lc-09", "ml-lc-10", "ml-lc-11")
    }
    if any(value.get("status") != "PASS" for value in stage_manifests.values()):
        raise GateError("ML-LC-09/10/11 source manifests must remain PASS for the handoff.")
    sources = [
        ("V02", output_dir / ML_LC_10_SCORED_TEST_PATH.name),
        ("V03", output_dir / ML_LC_10_SCORED_TEST_PATH.name),
        ("V04", output_dir / ML_LC_10_SCORED_TEST_PATH.name),
        ("V05", output_dir / ML_LC_09_GLOBAL_IMPORTANCE_PATH.name),
        ("V06", output_dir / ML_LC_11_RISK_TIER_SUMMARY_PATH.name),
    ]
    required_files = [path for _, path in sources] + [
        output_dir / ML_LC_09_LOCAL_EXPLANATIONS_PATH.name,
        output_dir / ML_LC_09_SHAP_SAMPLE_PATH.name,
        output_dir / ML_LC_11_EXPECTED_LOSS_PATH.name,
        Path(ml12["full_refit_model_artifact"]),
        Path(ml12["full_refit_score_artifact"]),
    ]
    if any(not path.is_file() for path in required_files):
        raise GateError("Required existing dashboard/explainability/refit handoff artifact is missing.")
    scored = pd.read_parquet(Path(ml12["full_refit_score_artifact"]))
    missing_columns = sorted(set(ML12_REQUIRED_SCORE_COLUMNS) - set(scored.columns))
    if missing_columns or scored["loan_id"].isna().any() or not scored["loan_id"].is_unique:
        raise GateError(f"ML-LC-12 scored handoff schema/key validation failed: {missing_columns}.")
    evaluated_columns = ["loan_id", "predicted_pd", "risk_score", "credit_score", "risk_tier"]
    evaluated = pd.read_parquet(sources[0][1], columns=evaluated_columns)
    if evaluated["loan_id"].isna().any() or not evaluated["loan_id"].is_unique:
        raise GateError("ML-LC-10 evaluated-scoring source keys are not unique/non-null.")
    importance = pd.read_csv(sources[3][1])
    if not {"feature", "mean_abs_shap", "xgboost_gain"}.issubset(importance.columns):
        raise GateError("ML-LC-09 global importance source lacks dashboard fields.")
    el_fields = pd.read_parquet(output_dir / ML_LC_11_EXPECTED_LOSS_PATH.name,
                                columns=["loan_id", "expected_loss", "risk_tier"])
    if el_fields["loan_id"].isna().any() or not el_fields["loan_id"].is_unique:
        raise GateError("ML-LC-11 Expected Loss source keys are not unique/non-null.")
    required_features = ml12.get("actual_features")
    model = joblib.load(Path(ml12["full_refit_model_artifact"]))
    if (not isinstance(required_features, list)
            or list(model.named_steps["normalize_missing"].feature_names_in_) != required_features
            or not {"preprocess", "model"}.issubset(model.named_steps)):
        raise GateError("Refit artifact is not loadable with the documented inference feature contract.")
    inference_sample = pd.read_parquet(
        Path(ml12["canonical_dataset_path"]), columns=required_features
    ).head(1)
    inference_pd = model.predict_proba(inference_sample)[:, 1]
    if len(inference_pd) != 1 or not np.isfinite(inference_pd).all() or not 0 <= inference_pd[0] <= 1:
        raise GateError("Single-borrower inference smoke check did not return a finite PD in [0,1].")
    manifest = {
        "stage": ML_LC_13_STAGE,
        "status": "PASS",
        "audit_outcome": "PASS — satisfied by existing handoff artifacts",
        "handoff_artifact_created": False,
        "handoff_artifact_reason": "Existing ML-LC-10/11/12 scores and ML-LC-09 explainability sources satisfy handoff without duplicate combined parquet.",
        "dashboard_sources": [
            {"visual": visual, "source": str(path)} for visual, path in sources
        ],
        "ml_lc_10_contract_source": str(output_dir / ML_LC_10_MANIFEST_PATH.name),
        "ml_lc_11_expected_loss_source": str(output_dir / ML_LC_11_EXPECTED_LOSS_PATH.name),
        "refit_model_artifact": ml12["full_refit_model_artifact"],
        "refit_score_artifact": ml12["full_refit_score_artifact"],
        "approved_feature_count": ml12["approved_feature_count"],
        "actual_feature_count": len(ml12["actual_features"]),
        "individual_prediction_contract_ready": True,
        "individual_prediction_input_features": ml12["actual_features"],
        "preprocessing_included_in_model_pipeline": True,
        "individual_prediction_smoke_check": "one canonical feature row; no outcome or metric evaluation",
        "individual_prediction_output_fields": list(ML12_REQUIRED_SCORE_COLUMNS[2:8]),
        "dashboard_readiness": {f"V{number:02}": True for number in range(2, 7)},
        "power_bi_dashboard_built_or_reviewed": False,
        "frozen_test_metrics_source": "ml-lc-08 evaluated xgboost_candidate only",
        "v05_preserves_explainability_specific_artifacts": True,
        "ml_lc_11_scenario_population_note": "evaluated frozen-test population; not full portfolio",
        "next_stage": "TV3 Power BI integration/review; no ML-LC-14 started",
    }
    manifest_path = output_dir / ML_LC_13_MANIFEST_PATH.name
    report_path = reports_dir / "tv1_stages/ml-lc-13.md"
    state_path = reports_dir / "tv1_stages/state/ml-lc-13.json"
    _write_json(manifest_path, manifest)
    _atomic_write(report_path, lambda target: target.write_text(_render_ml13_report(manifest), encoding="utf-8"))
    _write_json(state_path, {
        "stage": ML_LC_13_STAGE, "title": "Conditional modeling-to-dashboard handoff audit",
        "status": "PASS", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path), "report_path": str(report_path),
        "handoff_artifact_created": False,
    })
    return manifest
