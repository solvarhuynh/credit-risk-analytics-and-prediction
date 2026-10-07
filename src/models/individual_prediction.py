"""Dự đoán What-if trên một hồ sơ nền bằng model ML-LC-12 đã khóa."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.config import CANONICAL_DATASET_PATH, ML_LC_12_MANIFEST_PATH, PROCESSED_DIR, XGBOOST_FULL_REFIT_PATH
from src.features.engineering import engineer_lending_club_features
from src.models.cost_optimization import calculate_expected_loss
from src.models.explainability import aggregate_shap_by_original, transformed_feature_mapping
from src.models.scoring import (
    ML_LC_10_LOCKED_THRESHOLD,
    assign_pd_risk_tier,
    probability_to_project_credit_score,
    probability_to_risk_score,
)


OUTPUT_DIR = PROCESSED_DIR / "dashboard" / "individual_prediction"
EDITABLE_FIELDS = frozenset({"loan_amnt", "annual_inc", "dti", "term_months"})
LGD_CHOICES = (0.30, 0.45, 0.60)
SOURCE_COLUMNS = ("issue_d", "earliest_cr_line")
DEPENDENCIES = {
    "loan_amnt": ("loan_to_income_ratio", "loan_amount_band"),
    "annual_inc": ("loan_to_income_ratio", "income_band"),
    "dti": ("dti_band",),
    "term_months": (),
}


def _sha256(path: Path) -> str:
    """Tính hash theo luồng, không nạp toàn bộ artifact vào RAM."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_final_model(
    model_path: Path = XGBOOST_FULL_REFIT_PATH,
    manifest_path: Path = ML_LC_12_MANIFEST_PATH,
) -> tuple[Any, dict[str, Any], str]:
    """Nạp đúng full-refit pipeline, kiểm hash và schema đã khóa."""
    model_path, manifest_path = Path(model_path), Path(manifest_path)
    if not model_path.is_file() or not manifest_path.is_file():
        raise ValueError("Thiếu full-refit model hoặc ML-LC-12 manifest.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    features = manifest.get("actual_features")
    if (manifest.get("stage") != "ml-lc-12" or manifest.get("status") != "PASS"
            or manifest.get("refit_model") != "xgboost_full_refit"
            or not isinstance(features, list) or len(features) != 103
            or len(features) != len(set(features))
            or manifest.get("actual_feature_count") != 103
            or manifest.get("transformed_feature_count") != 151
            or manifest.get("carried_forward_threshold") != ML_LC_10_LOCKED_THRESHOLD):
        raise ValueError("ML-LC-12 manifest/schema/threshold không khớp contract.")
    model_hash = _sha256(model_path)
    if model_hash != manifest.get("refit_model_sha256") or model_hash != manifest.get("full_refit_model_sha256"):
        raise ValueError("Full-refit model hash không khớp ML-LC-12 manifest.")
    pipeline = joblib.load(model_path)
    steps = getattr(pipeline, "named_steps", {})
    if not {"normalize_missing", "preprocess", "model"}.issubset(steps):
        raise ValueError("Full-refit artifact thiếu pipeline preprocessing/model.")
    if (list(getattr(pipeline, "feature_names_in_", [])) != features
            or list(getattr(steps["normalize_missing"], "feature_names_in_", [])) != features
            or len(steps["preprocess"].get_feature_names_out()) != 151):
        raise ValueError("Tên/thứ tự 103 input hoặc 151 transformed features không khớp.")
    return pipeline, manifest, model_hash


def fetch_baseline(
    loan_id: str,
    features: Sequence[str],
    canonical_path: Path = CANONICAL_DATASET_PATH,
) -> pd.DataFrame:
    """Tìm đúng một loan_id qua từng row group, không load full canonical DataFrame."""
    if not isinstance(loan_id, str) or not loan_id.strip():
        raise ValueError("loan_id phải là chuỗi không rỗng.")
    parquet = pq.ParquetFile(canonical_path)
    requested = ["loan_id", *features, *SOURCE_COLUMNS]
    if len(features) != 103 or len(set(features)) != 103 or len(set(requested)) != len(requested):
        raise ValueError("Schema input phải có đúng 103 field khác nhau, không chứa ID/ngày nguồn.")
    absent = sorted(set(requested) - set(parquet.schema_arrow.names))
    if absent:
        raise ValueError(f"Canonical dataset thiếu schema inference: {absent}")
    matches: list[tuple[int, int]] = []
    for group in range(parquet.num_row_groups):
        ids = parquet.read_row_group(group, columns=["loan_id"]).column(0).to_pylist()
        matches.extend((group, index) for index, value in enumerate(ids) if str(value) == loan_id)
        if len(matches) > 1:
            raise ValueError(f"loan_id trùng trong canonical dataset: {loan_id}")
    if not matches:
        raise ValueError(f"Không tìm thấy loan_id trong canonical dataset: {loan_id}")
    group, index = matches[0]
    baseline = parquet.read_row_group(group, columns=requested).slice(index, 1).to_pandas()
    if list(baseline.columns) != requested or len(baseline) != 1:
        raise ValueError("Không đọc được đúng một baseline theo schema đã khóa.")
    return baseline.reset_index(drop=True)


def validate_overrides(overrides: Mapping[str, Any]) -> dict[str, float | int]:
    """Fail-closed với bốn field được duyệt; không clamp/coerce input sai."""
    unknown = sorted(set(overrides) - EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"Field What-if chưa được duyệt: {unknown}")
    cleaned: dict[str, float | int] = {}
    for field, raw in overrides.items():
        if isinstance(raw, (bool, str)):
            raise ValueError(f"{field} phải là số hữu hạn, không phải chuỗi/bool.")
        try:
            value = float(raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{field} phải là số hữu hạn.") from exc
        if not math.isfinite(value):
            raise ValueError(f"{field} phải là số hữu hạn.")
        if field == "loan_amnt" and not 500 <= value <= 40000:
            raise ValueError("loan_amnt phải trong [500, 40000].")
        if field == "annual_inc" and not 0 < value <= 10999200:
            raise ValueError("annual_inc phải trong (0, 10999200].")
        if field == "dti" and not 0 <= value <= 999:
            raise ValueError("dti phải trong [0, 999].")
        if field == "term_months":
            if value not in (36.0, 60.0):
                raise ValueError("term_months chỉ nhận 36 hoặc 60.")
            cleaned[field] = int(value)
        else:
            cleaned[field] = value
    return cleaned


def prepare_scenario(
    baseline: pd.DataFrame,
    features: Sequence[str],
    overrides: Mapping[str, Any],
) -> tuple[pd.DataFrame, dict[str, float | int], list[str]]:
    """Giữ baseline, cập nhật field duyệt và tính lại dependency bằng TV2 engineering."""
    if len(baseline) != 1 or not set([*features, *SOURCE_COLUMNS, "loan_id"]).issubset(baseline.columns):
        raise ValueError("Baseline thiếu 103 input hoặc nguồn ngày/ID để engineering.")
    if len(features) != 103 or len(set(features)) != 103 or any(f not in baseline for f in features):
        raise ValueError("Thiếu hoặc trùng input trong schema 103 field.")
    applied = validate_overrides(overrides)
    scenario = baseline.copy()
    for field, value in applied.items():
        scenario.loc[scenario.index[0], field] = value
    recomputed = sorted({dependency for field in applied for dependency in DEPENDENCIES[field]})
    if recomputed:
        engineered, _ = engineer_lending_club_features(scenario)
        for field in recomputed:
            scenario[field] = engineered[field]
    model_input = scenario.loc[:, list(features)].copy()
    if list(model_input.columns) != list(features) or len(model_input.columns) != 103:
        raise ValueError("Tên/thứ tự input sau override không khớp model.")
    return model_input, applied, recomputed


def explain_scenario(
    pipeline: Any,
    model_input: pd.DataFrame,
    features: Sequence[str],
    *,
    scenario_id: str,
    loan_id: str,
    top_n: int = 10,
) -> tuple[pd.DataFrame, float]:
    """SHAP của đúng bản ghi vừa infer, gộp one-hot về feature gốc."""
    import shap

    normalizer = pipeline.named_steps["normalize_missing"]
    preprocessor = pipeline.named_steps["preprocess"]
    estimator = pipeline.named_steps["model"]
    matrix = preprocessor.transform(normalizer.transform(model_input))
    names = list(preprocessor.get_feature_names_out())
    if len(names) != 151 or estimator.get_booster().num_features() != 151:
        raise ValueError("SHAP transformed feature schema không khớp 151 columns.")
    original = transformed_feature_mapping(names, features)
    explainer = shap.TreeExplainer(estimator, model_output="raw")
    values = explainer.shap_values(matrix, check_additivity=False)
    if isinstance(values, list):
        if len(values) != 1:
            raise ValueError("SHAP trả về nhiều output không mong đợi.")
        values = values[0]
    values = np.asarray(values, dtype=float)
    if values.shape != (1, 151) or not np.isfinite(values).all():
        raise ValueError("SHAP shape/giá trị không hợp lệ.")
    base = float(np.asarray(explainer.expected_value, dtype=float).reshape(-1)[0])
    margin = float(np.asarray(estimator.predict(matrix, output_margin=True), dtype=float)[0])
    error = abs(base + float(values.sum()) - margin)
    if not all(map(math.isfinite, (base, margin, error))) or error > 1e-3:
        raise ValueError("SHAP additivity trên raw margin không đạt.")
    grouped = aggregate_shap_by_original(values, names, original).iloc[0]
    if set(grouped.index) != set(features):
        raise ValueError("SHAP original feature mapping không bao phủ 103 input.")
    rows = []
    for field, contribution in grouped.items():
        value = model_input.iloc[0][field]
        rows.append({
            "scenario_id": scenario_id, "loan_id": loan_id, "feature": field,
            "feature_value": "" if pd.isna(value) else str(value),
            "shap_value": float(contribution), "abs_shap_value": abs(float(contribution)),
            "direction": ("neutral" if abs(contribution) <= 1e-12 else
                          "risk_increasing" if contribution > 0 else "risk_decreasing"),
        })
    table = pd.DataFrame(rows).sort_values(
        ["abs_shap_value", "feature"], ascending=[False, True], kind="mergesort",
    ).head(top_n).reset_index(drop=True)
    table.insert(3, "rank_by_abs_shap", np.arange(1, len(table) + 1))
    return table, error


def _scenario_id(loan_id: str, overrides: Mapping[str, float | int], lgd: float, model_hash: str) -> str:
    """ID ổn định cho cùng baseline, override, LGD và version model."""
    payload = json.dumps(
        {"loan_id": loan_id, "overrides": overrides, "lgd": lgd, "model_sha256": model_hash},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def run_prediction(
    loan_id: str,
    overrides: Mapping[str, Any] | None = None,
    *,
    lgd: float = 0.45,
    canonical_path: Path = CANONICAL_DATASET_PATH,
    model_path: Path = XGBOOST_FULL_REFIT_PATH,
    manifest_path: Path = ML_LC_12_MANIFEST_PATH,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Chạy một baseline/What-if thật; chưa ghi output cho tới khi mọi gate PASS."""
    if isinstance(lgd, bool) or not isinstance(lgd, (int, float)) or not math.isfinite(lgd) or lgd not in LGD_CHOICES:
        raise ValueError("LGD chỉ nhận 0.30, 0.45 hoặc 0.60.")
    applied = validate_overrides(overrides or {})
    pipeline, manifest, model_hash = load_final_model(model_path, manifest_path)
    canonical_path = Path(canonical_path)
    expected_hash = manifest.get("canonical_dataset_sha256")
    if not canonical_path.is_file() or not expected_hash or _sha256(canonical_path) != expected_hash:
        raise ValueError("Canonical dataset hash không khớp ML-LC-12 manifest.")
    features = manifest["actual_features"]
    baseline = fetch_baseline(loan_id, features, canonical_path)
    model_input, applied, recomputed = prepare_scenario(baseline, features, applied)
    probability = float(pipeline.predict_proba(model_input)[0, 1])
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("predicted_pd nằm ngoài [0,1] hoặc không hữu hạn.")
    amount = float(model_input.iloc[0]["loan_amnt"])
    if not math.isfinite(amount) or amount < 0:
        raise ValueError("loan_amnt baseline/EAD proxy không hợp lệ.")
    scenario_id = _scenario_id(loan_id, applied, float(lgd), model_hash)
    shap_table, shap_error = explain_scenario(
        pipeline, model_input, features, scenario_id=scenario_id, loan_id=loan_id,
    )
    result = {
        "loan_id": loan_id, "scenario_id": scenario_id,
        "scenario_type": "what_if" if applied else "baseline",
        "input_overrides": json.dumps(applied, sort_keys=True, ensure_ascii=False),
        "predicted_pd": probability,
        "predicted_class": int(probability >= ML_LC_10_LOCKED_THRESHOLD),
        "risk_score": float(probability_to_risk_score([probability])[0]),
        "project_credit_score": int(probability_to_project_credit_score([probability])[0]),
        "risk_tier": str(assign_pd_risk_tier([probability], decision_threshold=ML_LC_10_LOCKED_THRESHOLD)[0]),
        "ead_proxy": amount, "ead_proxy_units": "source units",
        "lgd_selected": float(lgd),
        "expected_loss": float(calculate_expected_loss([probability], lgd, [amount])[0]),
        **{
            f"expected_loss_lgd_{int(round(choice * 100))}": float(
                calculate_expected_loss([probability], choice, [amount])[0]
            ) for choice in LGD_CHOICES
        },
        "threshold": ML_LC_10_LOCKED_THRESHOLD,
        "model_version": "xgboost_full_refit_ml-lc-12", "model_sha256": model_hash,
    }
    input_rows = []
    for kind, row in (("baseline", baseline.iloc[0]), ("current", model_input.iloc[0])):
        input_rows.append({
            "scenario_id": scenario_id, "loan_id": loan_id, "input_role": kind,
            **{field: row[field] for field in sorted(EDITABLE_FIELDS)},
            **{field: row[field] for field in sorted(set().union(*DEPENDENCIES.values()))},
        })
    inputs = pd.DataFrame(input_rows)
    metadata = {
        "stage": "individual-prediction-prototype", "status": "PASS",
        "scenario_id": scenario_id, "scenario_type": result["scenario_type"],
        "loan_id": loan_id, "overrides": applied,
        "dependency_recomputation": recomputed,
        "model_artifact": str(Path(model_path).resolve()), "model_sha256": model_hash,
        "canonical_artifact": str(canonical_path.resolve()), "canonical_sha256": expected_hash,
        "input_schema_source": str(Path(manifest_path).resolve()),
        "input_schema_sha256": hashlib.sha256(json.dumps(features, separators=(",", ":")).encode()).hexdigest(),
        "input_count": len(features), "transformed_count": 151,
        "threshold": ML_LC_10_LOCKED_THRESHOLD,
        "output_definitions": {
            "predicted_pd": "full-refit predict_proba class 1",
            "predicted_class": "1 if PD >= locked threshold else 0",
            "risk_score": "100 * PD",
            "project_credit_score": "np.rint(1000 * (1 - PD)); NOT FICO",
            "risk_tier": "src.models.scoring.assign_pd_risk_tier",
            "ead_proxy": "loan_amnt, source units; NOT observed EAD at default",
            "expected_loss": "PD * selected LGD * loan_amnt",
        },
        "lgd_policy": {"selected": float(lgd), "sensitivity": list(LGD_CHOICES)},
        "shap_output_space": "raw margin/log-odds; NOT percent PD or causal effect",
        "shap_additivity_abs_error": shap_error,
        "shap_top_n": len(shap_table),
        "prototype_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "population_note": "existing labeled borrower baseline; full-refit model; not unbiased test evaluation",
    }
    return result, shap_table, inputs, metadata


def _atomic_write(path: Path, writer: Any) -> None:
    """Ghi file nhỏ bằng temp cùng thư mục rồi thay nguyên tử."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.stem}-", suffix=path.suffix, delete=False) as temp:
        partial = Path(temp.name)
    try:
        writer(partial)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def export_power_bi_artifacts(
    result: Mapping[str, Any],
    shap_table: pd.DataFrame,
    inputs: pd.DataFrame,
    metadata: Mapping[str, Any],
    *,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Path]:
    """Ghi bốn CURRENT files; manifest được ghi cuối như commit marker."""
    output_dir = Path(output_dir)
    paths = {
        "result": output_dir / "individual_prediction_result.csv",
        "shap": output_dir / "individual_prediction_shap.csv",
        "inputs": output_dir / "individual_prediction_inputs.csv",
        "manifest": output_dir / "individual_prediction_manifest.json",
    }
    if len(shap_table) != 10 or len(inputs) != 2:
        raise ValueError("Output cần đúng 10 SHAP rows và 2 input rows.")
    if (shap_table["scenario_id"].nunique() != 1
            or shap_table["scenario_id"].iloc[0] != result["scenario_id"]
            or not inputs["scenario_id"].eq(result["scenario_id"]).all()):
        raise ValueError("Scenario ID không nhất quán giữa output tables.")
    _atomic_write(paths["result"], lambda p: pd.DataFrame([result]).to_csv(p, index=False, encoding="utf-8-sig"))
    _atomic_write(paths["shap"], lambda p: shap_table.to_csv(p, index=False, encoding="utf-8-sig"))
    _atomic_write(paths["inputs"], lambda p: inputs.to_csv(p, index=False, encoding="utf-8-sig"))
    payload = {**metadata, "output_files": {key: str(value.resolve()) for key, value in paths.items() if key != "manifest"}}
    _atomic_write(paths["manifest"], lambda p: p.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8",
    ))
    return paths


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dự đoán What-if thật trên hồ sơ nền Lending Club.")
    parser.add_argument("--loan-id", required=True)
    for name in sorted(EDITABLE_FIELDS):
        parser.add_argument("--" + name.replace("_", "-"), type=float)
    parser.add_argument("--lgd", type=float, default=0.45, choices=LGD_CHOICES)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: chỉ flag được cấp mới thay baseline; không đụng dữ liệu nguồn."""
    args = _parser().parse_args(argv)
    overrides = {name: getattr(args, name) for name in EDITABLE_FIELDS if getattr(args, name) is not None}
    try:
        result, shap_table, inputs, metadata = run_prediction(args.loan_id, overrides, lgd=args.lgd)
        paths = export_power_bi_artifacts(result, shap_table, inputs, metadata)
    except (ValueError, OSError, ImportError) as exc:
        raise SystemExit(f"BLOCKED: {exc}") from exc
    print(
        f"{result['scenario_type']} {result['scenario_id']} | PD={result['predicted_pd']:.6f} | "
        f"class={result['predicted_class']} | risk_score={result['risk_score']:.4f} | "
        f"project_credit_score={result['project_credit_score']} | {result['risk_tier']} | "
        f"EL@LGD{result['lgd_selected']:.0%}={result['expected_loss']:.4f} source units"
    )
    print(f"Power BI-ready CURRENT files: {paths['result'].parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
