"""Explain a locked XGBoost pipeline on a deterministic validation sample."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from pathlib import Path

from src.models.modeling_pipeline import GateError

LOCKED_THRESHOLD = 0.22009515762329102


@dataclass(frozen=True)
class ExplainabilitySample:
    """Aligned validation rows and previously generated model predictions."""

    frame: pd.DataFrame
    predictions: pd.DataFrame
    sample: pd.DataFrame
    sample_predictions: pd.DataFrame


def transformed_feature_mapping(
    names: Sequence[str], original_features: Sequence[str],
) -> list[str]:
    """Map fitted ColumnTransformer names back to original input columns."""
    mapping: list[str] = []
    features = sorted(original_features, key=len, reverse=True)
    for name in names:
        if name.startswith("numeric__"):
            original = name.removeprefix("numeric__")
            if original not in original_features:
                raise GateError(f"Transformed numeric feature has no source: {name}")
        elif name.startswith("categorical__"):
            tail = name.removeprefix("categorical__")
            matches = [feature for feature in features if tail.startswith(feature + "_")]
            if not matches:
                raise GateError(f"Transformed categorical feature has no source: {name}")
            original = matches[0]
        else:
            raise GateError(f"Unexpected transformed feature prefix: {name}")
        mapping.append(original)
    if len(mapping) != len(names):
        raise GateError("Transformed feature mapping size mismatch.")
    return mapping


def deterministic_validation_sample(
    validation: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    sample_size: int = 5000,
    random_state: int = 42,
) -> ExplainabilitySample:
    """Validate validation-only inputs and choose a deterministic stratified sample."""
    from sklearn.model_selection import train_test_split

    required_prediction_columns = ["loan_id", "target", "predicted_pd"]
    if predictions.columns.tolist() != required_prediction_columns:
        raise GateError("ML-LC-05 validation prediction schema is invalid.")
    if (validation["loan_id"].isna().any() or not validation["loan_id"].is_unique
            or validation["target"].isna().any() or not validation["target"].isin([0, 1]).all()):
        raise GateError("Validation IDs/targets must be unique, non-null and binary.")
    if (predictions["loan_id"].isna().any() or not predictions["loan_id"].is_unique
            or predictions["target"].isna().any() or not predictions["target"].isin([0, 1]).all()):
        raise GateError("Validation prediction IDs/targets are invalid.")
    if set(validation["loan_id"]) != set(predictions["loan_id"]):
        raise GateError("Validation predictions do not match frozen validation membership.")
    ordered_predictions = predictions.set_index("loan_id").loc[validation["loan_id"]].reset_index()
    if not ordered_predictions["target"].eq(validation["target"].reset_index(drop=True)).all():
        raise GateError("Validation prediction targets differ from frozen validation IDs.")
    try:
        probability = ordered_predictions["predicted_pd"].to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise GateError("Validation predicted_pd must be numeric.") from exc
    if (not np.isfinite(probability).all() or np.any(probability < 0)
            or np.any(probability > 1)):
        raise GateError("Validation predicted_pd must be finite and in [0,1].")
    if len(validation) < 2 or validation["target"].nunique() != 2:
        raise GateError("Validation needs both classes to stratify the explainability sample.")
    actual_size = min(sample_size, len(validation))
    if actual_size < 2:
        raise GateError("Explainability sample must contain both target classes.")
    chosen, _ = train_test_split(
        np.arange(len(validation)), train_size=actual_size, random_state=random_state,
        stratify=validation["target"].to_numpy(),
    )
    chosen.sort()
    sample = validation.iloc[chosen].reset_index(drop=True)
    sample_predictions = ordered_predictions.iloc[chosen].reset_index(drop=True)
    if not {0, 1}.issubset(set(sample["target"].unique())):
        raise GateError("Stratified sample did not preserve both target classes.")
    return ExplainabilitySample(validation.reset_index(drop=True), ordered_predictions, sample, sample_predictions)


def native_gain_tables(booster: Any, transformed_names: Sequence[str], original_names: Sequence[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build truthful transformed gain and aggregated original feature views."""
    if booster.num_features() != len(transformed_names) or len(transformed_names) != len(original_names):
        raise GateError("XGBoost input dimension does not match fitted transformed feature names.")
    position_by_name = {f"f{index}": index for index in range(len(transformed_names))}
    gain = booster.get_score(importance_type="gain")
    weight = booster.get_score(importance_type="weight")
    cover = booster.get_score(importance_type="cover")
    unknown = (set(gain) | set(weight) | set(cover)) - set(position_by_name)
    if unknown:
        raise GateError(f"XGBoost returned unmapped feature IDs: {sorted(unknown)}")
    table = pd.DataFrame({
        "transformed_feature": list(transformed_names),
        "original_feature": list(original_names),
        "importance_gain": [float(gain.get(f"f{i}", 0.0)) for i in range(len(transformed_names))],
        "importance_weight": [int(weight.get(f"f{i}", 0)) for i in range(len(transformed_names))],
        "importance_cover": [float(cover.get(f"f{i}", 0.0)) for i in range(len(transformed_names))],
    })
    table["total_gain"] = table["importance_gain"] * table["importance_weight"]
    aggregate = table.groupby("original_feature", sort=False).agg(
        xgboost_total_gain=("total_gain", "sum"),
        transformed_feature_count=("transformed_feature", "size"),
    ).reset_index()
    denominator = float(aggregate["xgboost_total_gain"].sum())
    aggregate["xgboost_gain"] = aggregate["xgboost_total_gain"] / denominator if denominator else 0.0
    table = table.drop(columns="total_gain").sort_values(
        ["importance_gain", "transformed_feature"], ascending=[False, True], kind="mergesort",
    ).reset_index(drop=True)
    table.insert(0, "rank", np.arange(1, len(table) + 1))
    return table, aggregate.drop(columns="xgboost_total_gain")


def aggregate_shap_by_original(shap_values: np.ndarray, names: Sequence[str], original_names: Sequence[str]) -> pd.DataFrame:
    """Sum one-hot contributions per source feature before taking absolute means."""
    values = np.asarray(shap_values, dtype=float)
    if values.ndim != 2 or values.shape[1] != len(names) or len(names) != len(original_names):
        raise GateError("SHAP matrix dimensions differ from transformed feature schema.")
    if not np.isfinite(values).all():
        raise GateError("SHAP matrix contains non-finite values.")
    grouped: dict[str, np.ndarray] = {}
    for index, feature in enumerate(original_names):
        if feature not in grouped:
            grouped[feature] = np.zeros(values.shape[0], dtype=float)
        grouped[feature] += values[:, index]
    result = pd.DataFrame(grouped)
    return result


def select_local_examples(probabilities: Sequence[float], loan_ids: Sequence[Any]) -> list[tuple[str, int]]:
    """Pick three distinct validation rows nearest PD deciles 10/50/90."""
    values = np.asarray(probabilities, dtype=float)
    ids = np.asarray(loan_ids)
    if values.ndim != 1 or len(values) != len(ids) or not np.isfinite(values).all():
        raise GateError("Local example probabilities/IDs are invalid.")
    if not len(values):
        raise GateError("No rows available for local explanations.")
    selected: list[tuple[str, int]] = []
    used: set[int] = set()
    for kind, quantile in (("low", 0.1), ("medium", 0.5), ("high", 0.9)):
        target_pd = float(np.quantile(values, quantile))
        order = sorted(range(len(values)), key=lambda i: (abs(values[i] - target_pd), str(ids[i])))
        chosen = next((index for index in order if index not in used), None)
        if chosen is None:
            break
        selected.append((kind, chosen))
        used.add(chosen)
    return selected


def numeric_direction_summary(feature_values: pd.Series, shap_values: Sequence[float]) -> str:
    """Describe validation-sample association in SHAP margin space, without causality."""
    from scipy.stats import spearmanr

    numeric = pd.to_numeric(feature_values, errors="coerce")
    shap_series = pd.Series(np.asarray(shap_values, dtype=float), index=numeric.index)
    valid = numeric.notna() & shap_series.notna()
    if int(valid.sum()) < 30 or numeric.loc[valid].nunique() < 3:
        return "Không đủ biến thiên để tóm tắt chiều."
    if shap_series.loc[valid].nunique() < 2:
        return "SHAP contribution gần như không đổi trong sample; chưa thể mô tả chiều."
    rho = float(spearmanr(numeric.loc[valid], shap_series.loc[valid]).statistic)
    bins = pd.qcut(numeric.loc[valid].rank(method="first"), q=3, labels=False)
    medians = shap_series.loc[valid].groupby(bins, observed=True).median().to_numpy()
    if len(medians) >= 3 and np.all(np.diff(medians) > 0):
        direction = "Giá trị cao hơn gắn với SHAP dương hơn (đồng biến)."
    elif len(medians) >= 3 and np.all(np.diff(medians) < 0):
        direction = "Giá trị cao hơn gắn với SHAP âm hơn (nghịch biến)."
    else:
        direction = "Quan hệ không đơn điệu hoặc không rõ theo các tam phân vị."
    return f"{direction} Spearman ρ={rho:.3f}; SHAP ở raw margin/log-odds, không phải điểm phần trăm PD."


def run_ml_lc_09(
    *,
    canonical_path: Path,
    dictionary_path: Path,
    output_dir: Path,
    reports_dir: Path,
    sample_size: int = 5000,
    random_state: int = 42,
    top_n: int = 15,
) -> dict[str, Any]:
    """Create global/local explanations for the locked model using validation rows only."""
    import json
    from datetime import datetime, timezone

    import joblib

    from src.models.tv1_runner import _atomic_write_dataframe, _atomic_write_text, _sha256

    output_dir, reports_dir = Path(output_dir), Path(reports_dir)
    ml05 = json.loads((output_dir / "ml_lc_05_manifest.json").read_text(encoding="utf-8"))
    ml06 = json.loads((output_dir / "ml_lc_06_manifest.json").read_text(encoding="utf-8"))
    ml07 = json.loads((output_dir / "ml_lc_07_manifest.json").read_text(encoding="utf-8"))
    ml08 = json.loads((output_dir / "ml_lc_08_manifest.json").read_text(encoding="utf-8"))
    for stage, payload in (("ml-lc-06", ml06), ("ml-lc-07", ml07), ("ml-lc-08", ml08)):
        if payload.get("stage") != stage or payload.get("status") != "PASS":
            raise GateError(f"Prerequisite {stage} chưa PASS.")
    model_path = output_dir / "xgboost_candidate.joblib"
    threshold = LOCKED_THRESHOLD
    if (ml06.get("selected_candidate") != "xgboost_candidate"
            or ml07.get("locked_candidate") != "xgboost_candidate"
            or ml07.get("selected_threshold") != threshold
            or ml08.get("selected_candidate") != "xgboost_candidate"
            or ml08.get("selected_threshold") != threshold
            or ml08.get("frozen_test_used_for_model_selection") is not False
            or ml08.get("frozen_test_used_for_threshold_selection") is not False
            or ml08.get("test_evaluated") is not True):
        raise GateError("Candidate/threshold/frozen evaluation lock does not match ML-LC-08.")
    if _sha256(model_path) != ml08.get("protected_sha256_after", {}).get(model_path.name):
        raise GateError("Model SHA-256 no longer matches completed ML-LC-08.")
    if (not (output_dir / "ml_lc_08_one_shot.lock").is_file()
            or not model_path.is_file()):
        raise GateError("ML-LC-08 one-shot lock or locked model artifact is missing.")

    features = ml05.get("actual_features")
    if (not isinstance(features, list) or len(features) != ml05.get("actual_feature_count")
            or ml05.get("status") != "PASS"):
        raise GateError("ML-LC-05 fitted feature list is invalid.")
    dictionary = pd.read_csv(dictionary_path).set_index("column_name")
    if (not set(features).issubset(dictionary.index)
            or not dictionary.loc[features, "policy_class"].isin(["APPLICATION_TIME", "CREDIT_SNAPSHOT"]).all()
            or not dictionary.loc[features, "model_eligible_default"].astype(str).str.lower().eq("true").all()):
        raise GateError("Locked model features conflict with current dictionary policy.")

    validation_ids_path = output_dir / "validation_ids.parquet"
    validation_ids = pd.read_parquet(validation_ids_path)
    if (validation_ids.columns.tolist() != ["loan_id", "target", "split"]
            or len(validation_ids) != ml05.get("validation_rows")
            or len(validation_ids) != ml06.get("validation_rows")
            or len(validation_ids) != ml07.get("validation_rows")
            or validation_ids["loan_id"].isna().any()
            or not validation_ids["loan_id"].is_unique
            or validation_ids["target"].isna().any()
            or not validation_ids["target"].isin([0, 1]).all()
            or not validation_ids["split"].eq("validation").all()):
        raise GateError("Frozen validation IDs/schema/partition are invalid.")
    predictions_path = output_dir / "ml_lc_05_xgboost_validation_predictions.parquet"
    predictions = pd.read_parquet(predictions_path)
    canonical_columns = ["loan_id", "target", *features]
    canonical = pd.read_parquet(
        canonical_path, columns=canonical_columns,
        filters=[("loan_id", "in", validation_ids["loan_id"].tolist())],
    )
    if (len(canonical) != len(validation_ids)
            or canonical["loan_id"].isna().any() or not canonical["loan_id"].is_unique
            or set(canonical["loan_id"]) != set(validation_ids["loan_id"])):
        raise GateError("Canonical validation rows do not match frozen validation IDs.")
    canonical = canonical.set_index("loan_id").loc[validation_ids["loan_id"].tolist()].reset_index()
    if not canonical["target"].astype(int).eq(validation_ids["target"].astype(int).reset_index(drop=True)).all():
        raise GateError("Canonical validation target differs from frozen validation IDs.")
    sampled = deterministic_validation_sample(
        canonical, predictions, sample_size=sample_size, random_state=random_state,
    )

    model_hash_before = _sha256(model_path)
    pipeline = joblib.load(model_path)
    if not hasattr(pipeline, "named_steps") or not {"preprocess", "model"}.issubset(pipeline.named_steps):
        raise GateError("Locked XGBoost artifact lacks preprocess/model pipeline steps.")
    preprocessor = pipeline.named_steps["preprocess"]
    estimator = pipeline.named_steps["model"]
    transformed_names = list(preprocessor.get_feature_names_out())
    booster = estimator.get_booster()
    original_names = transformed_feature_mapping(transformed_names, features)
    if (len(transformed_names) != ml05.get("transformed_feature_count")
            or booster.num_features() != len(transformed_names)):
        raise GateError("Transformed feature schema does not align with fitted XGBoost inputs.")

    gain_transformed, gain_original = native_gain_tables(booster, transformed_names, original_names)
    sample_x = sampled.sample.loc[:, features]
    normalized = pipeline.named_steps.get("normalize_missing")
    model_frame = normalized.transform(sample_x) if normalized is not None else sample_x
    transformed_x = preprocessor.transform(model_frame)
    sample_pd = np.asarray(pipeline.predict_proba(sample_x)[:, 1], dtype=float)
    expected_pd = sampled.sample_predictions["predicted_pd"].to_numpy(dtype=float)
    if not np.allclose(sample_pd, expected_pd, rtol=1e-6, atol=1e-7):
        raise GateError("Locked model sample PDs disagree with ML-LC-05 validation predictions.")

    try:
        import shap
    except Exception as exc:
        shap = None
        shap_error = f"{type(exc).__name__}: {exc}"
    else:
        shap_error = None
    if shap is not None:
        try:
            explainer = shap.TreeExplainer(estimator, model_output="raw")
            shap_values = explainer.shap_values(transformed_x, check_additivity=False)
            if isinstance(shap_values, list):
                if len(shap_values) != 1:
                    raise GateError("Unexpected multi-output SHAP values for binary XGBoost.")
                shap_values = shap_values[0]
            shap_values = np.asarray(shap_values, dtype=float)
            if shap_values.shape != (len(sampled.sample), len(transformed_names)):
                raise GateError("SHAP row/feature dimensions do not match sampled transformed input.")
            if not np.isfinite(shap_values).all():
                raise GateError("SHAP values contain non-finite values.")
            expected_value = np.asarray(explainer.expected_value, dtype=float)
            if not np.isfinite(expected_value).all():
                raise GateError("SHAP expected/base value is not finite.")
            base_value = float(expected_value.reshape(-1)[0])
            margins = np.asarray(estimator.predict(transformed_x, output_margin=True), dtype=float)
            additive_error = np.abs(base_value + shap_values.sum(axis=1) - margins)
            if not np.isfinite(margins).all() or float(additive_error.max(initial=0)) > 1e-3:
                raise GateError("SHAP additivity check failed in raw margin/log-odds output space.")
            shap_error = None
        except Exception as exc:
            shap_values = None
            shap_error = f"{type(exc).__name__}: {exc}"
    else:
        shap_values = None

    modeling_dir = output_dir
    global_path = modeling_dir / "ml_lc_09_global_importance.csv"
    transformed_path = modeling_dir / "ml_lc_09_transformed_importance.csv"
    local_path = modeling_dir / "ml_lc_09_local_explanations.csv"
    shap_sample_path = modeling_dir / "ml_lc_09_shap_sample.parquet"
    figure_dir = reports_dir / "figures" / "modeling"
    global_figure = figure_dir / "ml_lc_09_global_importance.png"
    summary_figure = figure_dir / "ml_lc_09_shap_summary.png"

    if shap_values is None:
        global_table = gain_original.rename(columns={"xgboost_gain": "xgboost_gain"})
        global_table["mean_abs_shap"] = np.nan
        global_table["direction_summary"] = "SHAP BLOCKED; no directional summary produced."
        global_table["feature"] = global_table["original_feature"]
        global_table = global_table.sort_values(
            ["xgboost_gain", "original_feature"], ascending=[False, True], kind="mergesort",
        ).reset_index(drop=True)
        global_table.insert(0, "rank", np.arange(1, len(global_table) + 1))
        _atomic_write_dataframe(global_path, global_table, format="csv")
        _plot_gain(global_table, global_figure)
        status = "BLOCKED"
        top_features: list[dict[str, Any]] = []
        local_rows: list[dict[str, Any]] = []
        transformed_table = gain_transformed
        figures = [str(global_figure)]
    else:
        grouped_shap = aggregate_shap_by_original(shap_values, transformed_names, original_names)
        mean_abs = grouped_shap.abs().mean(axis=0)
        gain_by_source = gain_original.set_index("original_feature")["xgboost_gain"]
        transformed_count = pd.Series(original_names).value_counts()
        direction = {}
        numeric_features = set(sampled.sample.select_dtypes(include=[np.number]).columns) - {"loan_id", "target"}
        for feature in mean_abs.index:
            direction[feature] = (numeric_direction_summary(sampled.sample[feature], grouped_shap[feature])
                                  if feature in numeric_features else
                                  "Các nhóm category có contribution khác nhau; xem local/sample, không suy ra chiều chung.")
        global_table = pd.DataFrame({
            "original_feature": mean_abs.index,
            "mean_abs_shap": mean_abs.values,
            "xgboost_gain": [float(gain_by_source.get(name, 0.0)) for name in mean_abs.index],
            "transformed_feature_count": [int(transformed_count.get(name, 0)) for name in mean_abs.index],
            "direction_summary": [direction[name] for name in mean_abs.index],
        }).sort_values(["mean_abs_shap", "original_feature"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
        global_table.insert(0, "rank", np.arange(1, len(global_table) + 1))
        global_table.insert(2, "feature", global_table["original_feature"])
        transformed_shap = np.abs(shap_values).mean(axis=0)
        transformed_table = gain_transformed.merge(
            pd.DataFrame({"transformed_feature": transformed_names, "mean_abs_shap": transformed_shap}),
            on="transformed_feature", validate="one_to_one",
        ).sort_values(["mean_abs_shap", "transformed_feature"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
        transformed_table.drop(columns="rank", inplace=True)
        transformed_table.insert(0, "rank", np.arange(1, len(transformed_table) + 1))
        top_features = global_table.head(top_n).to_dict(orient="records")
        local_rows = _local_explanation_rows(sampled.sample, sample_pd, grouped_shap, threshold)
        sample_table = _shap_long_sample(sampled.sample, sample_pd, grouped_shap, global_table.head(top_n)["original_feature"].tolist())
        _atomic_write_dataframe(global_path, global_table, format="csv")
        _atomic_write_dataframe(transformed_path, transformed_table, format="csv")
        _atomic_write_dataframe(local_path, pd.DataFrame(local_rows), format="csv")
        _atomic_write_dataframe(shap_sample_path, sample_table, format="parquet")
        _plot_gain(global_table, global_figure)
        _plot_shap_summary(shap, shap_values, transformed_x, transformed_names, transformed_table, summary_figure)
        status = "PASS"
        figures = [str(global_figure), str(summary_figure)]

    if _sha256(model_path) != model_hash_before:
        raise GateError("Model artifact changed during explainability.")
    sample_target_counts = {str(int(label)): int(count) for label, count in sampled.sample["target"].value_counts().sort_index().items()}
    manifest = {
        "stage": "ml-lc-09", "status": status, "model": "xgboost_candidate",
        "model_artifact_path": str(model_path), "model_sha256_before": model_hash_before,
        "model_sha256_after": _sha256(model_path), "selected_threshold": threshold,
        "explainability_partition": "validation", "validation_rows": len(canonical),
        "shap_sample_rows": len(sampled.sample), "shap_random_state": random_state,
        "shap_sampling_method": "stratified random sample without replacement from validation IDs; sklearn train_test_split",
        "shap_sample_target_counts": sample_target_counts,
        "original_feature_count": len(features), "transformed_feature_count": len(transformed_names),
        "importance_method": ["xgboost_gain", "mean_abs_shap"] if shap_values is not None else ["xgboost_gain"],
        "xgboost_gain_type": "gain; transformed mean gain, original source normalized total_gain share",
        "top_features": top_features, "global_importance_path": str(global_path),
        "transformed_importance_path": str(transformed_path) if shap_values is not None else None,
        "local_explanations_path": str(local_path) if shap_values is not None else None,
        "shap_sample_path": str(shap_sample_path) if shap_values is not None else None,
        "figure_paths": figures, "shap_available": shap_values is not None,
        "shap_method": "shap.TreeExplainer(model_output='raw')" if shap_values is not None else None,
        "shap_dependency_available": shap is not None,
        "shap_error": shap_error,
        "shap_output_space": "raw margin/log-odds; positive contribution increases model margin and generally PD",
        "shap_expected_value": base_value if shap_values is not None else None,
        "shap_additivity_max_abs_error": float(additive_error.max(initial=0)) if shap_values is not None else None,
        "aggregation_method": "sum encoded-column SHAP values per source feature per row, then mean absolute value; original XGBoost gain aggregates transformed total_gain and normalizes to share",
        "model_retrained": False, "candidate_changed": False, "threshold_changed": False,
        "frozen_test_used_for_explainability": False, "next_stage": "ml-lc-10",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = output_dir / "ml_lc_09_manifest.json"
    report_path = reports_dir / "tv1_stages" / "ml-lc-09.md"
    state_path = reports_dir / "tv1_stages" / "state" / "ml-lc-09.json"
    _atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    _atomic_write_text(report_path, _render_report(manifest, global_table, local_rows))
    _atomic_write_text(state_path, json.dumps({
        "stage": "ml-lc-09", "title": "Model Explainability", "status": status,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path), "report_path": str(report_path),
    }, ensure_ascii=False, indent=2))
    return manifest


def _local_explanation_rows(
    sample: pd.DataFrame, probabilities: np.ndarray, grouped_shap: pd.DataFrame, threshold: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, index in select_local_examples(probabilities, sample["loan_id"].tolist()):
        values = grouped_shap.iloc[index]
        selected = [("risk_increasing", feature) for feature in values[values > 0].nlargest(5).index]
        selected += [("risk_decreasing", feature) for feature in values[values < 0].nsmallest(5).index]
        for direction, feature in selected:
            rows.append({
                "loan_id": sample.iloc[index]["loan_id"], "target": int(sample.iloc[index]["target"]),
                "predicted_pd": float(probabilities[index]),
                "predicted_class": int(probabilities[index] >= threshold),
                "risk_example_type": kind, "feature": feature,
                "feature_value": str(sample.iloc[index][feature]),
                "shap_value": float(values[feature]), "direction": direction,
                "rank": len([row for row in rows if row["risk_example_type"] == kind and row["direction"] == direction]) + 1,
            })
    if {row["risk_example_type"] for row in rows} != {"low", "medium", "high"}:
        raise GateError("Expected low/medium/high local examples were not produced.")
    return rows


def _shap_long_sample(sample: pd.DataFrame, probabilities: np.ndarray, grouped_shap: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    parts = []
    for feature in features:
        parts.append(pd.DataFrame({
            "loan_id": sample["loan_id"].to_numpy(), "target": sample["target"].astype(int).to_numpy(),
            "predicted_pd": probabilities, "feature": feature,
            "feature_value": sample[feature].astype("string").fillna("<NA>").to_numpy(),
            "shap_value": grouped_shap[feature].to_numpy(),
        }))
    return pd.concat(parts, ignore_index=True)


def _plot_gain(table: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    shown = table.nlargest(15, "mean_abs_shap" if table["mean_abs_shap"].notna().any() else "xgboost_gain").sort_values(
        "mean_abs_shap" if table["mean_abs_shap"].notna().any() else "xgboost_gain",
    )
    value_column = "mean_abs_shap" if table["mean_abs_shap"].notna().any() else "xgboost_gain"
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(shown["original_feature"], shown[value_column], color="#2867A0")
    ax.set_title("Global feature importance — validation")
    ax.set_xlabel("Mean absolute SHAP (raw margin)" if value_column == "mean_abs_shap" else "Normalized XGBoost gain share")
    ax.set_ylabel("Original feature")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_shap_summary(shap_module: Any, shap_values: np.ndarray, transformed: Any,
                       transformed_names: list[str], importance: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = importance.nlargest(20, "mean_abs_shap")["transformed_feature"].tolist()
    indices = [transformed_names.index(name) for name in names]
    dense = transformed[:, indices].toarray() if hasattr(transformed, "toarray") else np.asarray(transformed)[:, indices]
    shap_module.summary_plot(shap_values[:, indices], dense, feature_names=names, show=False,
                             plot_type="dot", max_display=min(20, len(names)))
    plt.title("SHAP summary — validation sample (raw margin/log-odds)")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close("all")


def _render_report(manifest: dict[str, Any], global_table: pd.DataFrame,
                   local_rows: list[dict[str, Any]]) -> str:
    top = global_table.head(10)
    if manifest["shap_available"]:
        top_lines = [f"| {int(row.rank)} | {row.original_feature} | {row.mean_abs_shap:.6f} | {row.direction_summary} |"
                     for row in top.itertuples(index=False)]
    else:
        top_lines = [f"| {int(row.rank)} | {row.original_feature} | gain share {row.xgboost_gain:.6f} | SHAP BLOCKED |"
                     for row in top.itertuples(index=False)]
    local_ids = {}
    for row in local_rows:
        local_ids[row["risk_example_type"]] = row["loan_id"]
    status_sentence = ("SHAP đã chạy và qua kiểm tra additivity trong raw margin/log-odds."
                       if manifest["shap_available"] else
                       f"SHAP bị BLOCKED: {manifest['shap_error']}. Native gain vẫn có; SHAP chưa được tạo.")
    return "\n".join([
        "# ML-LC-09 — Explainability", "",
        "## 1. Mục tiêu", "", "Giải thích hành vi của XGBoost đã khóa; không thay đổi model hoặc threshold.", "",
        "## 2. Dữ liệu", "", f"Explainability dùng riêng validation: {manifest['validation_rows']:,} dòng; SHAP sample {manifest['shap_sample_rows']:,} dòng, random_state={manifest['shap_random_state']}, phân tầng theo target.", "Frozen test không được dùng cho explainability.", "",
        "## 3. Feature importance", "", "Importance toàn cục cho biết model dựa vào feature nào; native XGBoost gain là đóng góp trung bình mỗi lần split, còn bảng original gộp total_gain rồi chuẩn hóa thành tỷ trọng.", "",
        "## 4. SHAP", "", "SHAP ước lượng contribution của feature cho dự đoán. Global mean(|SHAP|) mô tả mức contribution trung bình; local SHAP giải thích một loan cụ thể. SHAP mô tả model, không chứng minh quan hệ nhân quả.", status_sentence,
        (f"SHAP output space là raw margin/log-odds; max additivity error={manifest['shap_additivity_max_abs_error']:.3g}. Positive SHAP đẩy margin lên và thường tăng PD; không phải mức tăng phần trăm PD." if manifest["shap_available"] else ""), "",
        "## 5. Top 10 feature gốc", "", "| Rank | Feature | Mean absolute SHAP / gain | Diễn giải trên sample |", "|---:|---|---:|---|", *top_lines, "",
        "## 6. Ví dụ local", "", f"Đã chọn loan validation theo PD decile thấp/trung vị/cao; IDs low={local_ids.get('low')}, medium={local_ids.get('medium')}, high={local_ids.get('high')}. Contributor dương/âm nằm trong CSV local.", "",
        "## 7. V05 dashboard", "",
        "**BUSINESS QUESTION:** Model dựa vào những biến nào và chúng gắn với hướng contribution ra sao?",
        "**WHY THIS VISUAL:** Bar xếp hạng mean(|SHAP|) giúp so sánh mức quan trọng; beeswarm bổ sung độ phân tán, giá trị feature và dấu contribution.",
        f"**INSIGHT:** Trong validation sample, các feature đứng đầu là {', '.join(global_table.head(5)['original_feature'].tolist())}; hướng được mô tả là association trong không gian model, không phải nguyên nhân.",
        "**STORY CONNECTION:** V05 nằm sau portfolio overview/segmentation/risk prediction để giải thích vì sao model đưa ra PD, trước business impact.",
        f"Global artifact: `{manifest['global_importance_path']}`. Dùng cột `feature` với tên gốc, `mean_abs_shap`, `xgboost_gain`, `direction_summary`; tránh tên one-hot nội bộ.", "",
        "## 8. Giới hạn", "", "Validation sample 5.000 dòng đại diện theo target; direction là association với contribution của model, không phải causality. Gộp one-hot về feature gốc làm mất chi tiết từng category. PD là dự đoán, không phải xác suất đã hiệu chuẩn hay nguyên nhân thực tế.", "",
        "## 9. Bước tiếp theo", "", "ML-LC-10 — PD → Credit Score / Risk Tier; chưa bắt đầu.", "",
    ])
