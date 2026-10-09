"""Thang percentile tương đối cho các model demo 5-input và 6-input.

Risk Index chỉ là thang trình bày 0–100. Nó được tính từ phân bố PD của
validation partition riêng từng model, không thay thế PD, classification,
risk tier, SHAP hay Expected Loss.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from functools import lru_cache
import os
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from src.config import (
    CANONICAL_DATASET_PATH,
    FIVE_INPUT_RISK_INDEX_REFERENCE_MANIFEST_PATH,
    FIVE_INPUT_RISK_INDEX_REFERENCE_PATH,
    LOGISTIC_5INPUT_DEMO_PATH,
    LOGISTIC_6INPUT_DEMO_MANIFEST_PATH,
    LOGISTIC_6INPUT_DEMO_PATH,
    LOGISTIC_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
    MODELING_DIR,
    XGBOOST_5INPUT_DEMO_PATH,
    XGBOOST_6INPUT_DEMO_MANIFEST_PATH,
    XGBOOST_6INPUT_DEMO_PATH,
    XGBOOST_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
)
from src.models.demo_6input import DEMO_6_FEATURES
from src.models.scoring import validate_probability_of_default


REFERENCE_MODELS = ("xgboost", "logistic")
REFERENCE_PARTITION = "validation"
REFERENCE_METHOD = (
    "100 * count(reference_predicted_pd <= applicant_pd) / reference_rows; "
    "searchsorted(side='right') on sorted validation predictions"
)
SIX_INPUT_REFERENCE_FILES = {
    "xgboost": (
        XGBOOST_6INPUT_DEMO_PATH,
        XGBOOST_6INPUT_DEMO_MANIFEST_PATH,
        XGBOOST_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
    ),
    "logistic": (
        LOGISTIC_6INPUT_DEMO_PATH,
        LOGISTIC_6INPUT_DEMO_MANIFEST_PATH,
        LOGISTIC_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
    ),
}


def _sha256(path: Path) -> str:
    """Tính SHA-256 theo luồng cho artifact provenance."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    """Ghi manifest JSON nguyên tử."""
    path = Path(path)
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        partial.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def _write_npz_atomic(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    """Ghi mảng PD nén nguyên tử, tránh file reference dở dang."""
    path = Path(path)
    partial = path.with_name(f"{path.stem}.partial{path.suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        np.savez_compressed(partial, **arrays)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def _read_json(path: Path) -> dict:
    """Đọc manifest object và fail closed nếu nội dung sai."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Không đọc được Risk Index manifest: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("Risk Index manifest phải là JSON object.")
    return value


def _validate_sorted_reference(values: np.ndarray, *, name: str) -> np.ndarray:
    """Kiểm tra phân bố PD đã sort, hữu hạn và không rỗng."""
    validated = validate_probability_of_default(np.asarray(values, dtype=float))
    if validated.size < 2 or not np.all(validated[:-1] <= validated[1:]):
        raise ValueError(f"Risk Index reference {name} phải được sort tăng dần.")
    return validated


def _validate_reference_arrays(arrays: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Kiểm tra mỗi model có phân bố PD hợp lệ."""
    validated: dict[str, np.ndarray] = {}
    for model_key in REFERENCE_MODELS:
        if model_key not in arrays:
            raise ValueError(f"Thiếu Risk Index reference cho model: {model_key}")
        validated[model_key] = _validate_sorted_reference(arrays[model_key], name=model_key)
    return validated


def _load_reference_npz(path: Path) -> dict[str, np.ndarray]:
    """Đọc mảng reference từ NPZ rồi đóng file container."""
    try:
        with np.load(path, allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
    except (OSError, ValueError) as exc:
        raise ValueError(f"Không đọc được Risk Index reference: {path}") from exc
    return _validate_reference_arrays(arrays)


def build_risk_index_reference(
    *,
    output_path: Path = FIVE_INPUT_RISK_INDEX_REFERENCE_PATH,
    manifest_path: Path = FIVE_INPUT_RISK_INDEX_REFERENCE_MANIFEST_PATH,
) -> dict:
    """Tạo reference PD từ validation, không train và không đọc frozen test.

    Hàm này chỉ chạy một lần sau khi hai model demo đã tồn tại. Validation
    predictions được tính từ artifact đã khóa rồi lưu thành NPZ để app không
    phải nạp canonical dataset hay tính lại trên mỗi click.
    """
    output_path, manifest_path = Path(output_path), Path(manifest_path)
    if output_path.exists() or manifest_path.exists():
        raise FileExistsError("Risk Index reference đã tồn tại; không ghi đè artifact.")

    from src.models.demo_5input import (
        DEMO_FEATURES,
        _read_canonical_rows,
        _read_partition_ids,
        get_demo_model,
    )
    from src.models.logistic_5input_demo import get_logistic_demo

    validation_ids = _read_partition_ids(MODELING_DIR / "validation_ids.parquet", "validation")
    test_ids = _read_partition_ids(MODELING_DIR / "test_ids.parquet", "test")
    validation_set = set(validation_ids["loan_id"])
    if len(validation_ids) < 2 or not validation_ids["loan_id"].is_unique:
        raise ValueError("Validation IDs phải unique và không rỗng.")
    if validation_set.intersection(set(test_ids["loan_id"])):
        raise ValueError("Risk Index reference không được overlap frozen test.")

    frame = _read_canonical_rows(CANONICAL_DATASET_PATH, validation_ids)
    features = frame.loc[:, list(DEMO_FEATURES)]
    xgb_model, _ = get_demo_model()
    logistic_model, _ = get_logistic_demo()
    predictions = {
        "xgboost": np.sort(validate_probability_of_default(
            xgb_model.predict_proba(features)[:, 1],
        )),
        "logistic": np.sort(validate_probability_of_default(
            logistic_model.predict_proba(features)[:, 1],
        )),
    }
    _validate_reference_arrays(predictions)
    _write_npz_atomic(output_path, predictions)

    manifest = {
        "stage": "five-input-risk-index-reference",
        "status": "PASS",
        "reference_partition": REFERENCE_PARTITION,
        "reference_method": REFERENCE_METHOD,
        "reference_rows": int(len(frame)),
        "canonical_dataset_sha256": _sha256(CANONICAL_DATASET_PATH),
        "validation_ids_sha256": _sha256(MODELING_DIR / "validation_ids.parquet"),
        "frozen_test_used": False,
        "models": {
            key: {
                "rows": int(values.size),
                "min_pd": float(values[0]),
                "median_pd": float(np.median(values)),
                "max_pd": float(values[-1]),
                "model_artifact": str(path),
                "model_sha256": _sha256(path),
            }
            for key, values, path in (
                ("xgboost", predictions["xgboost"], XGBOOST_5INPUT_DEMO_PATH),
                ("logistic", predictions["logistic"], LOGISTIC_5INPUT_DEMO_PATH),
            )
        },
        "reference_artifact": str(output_path.resolve()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _load_reference(signature: tuple[int, int, int, int]) -> dict[str, np.ndarray]:
    """Nạp reference một lần và kiểm tra provenance model/artifact."""
    del signature
    manifest = _read_json(FIVE_INPUT_RISK_INDEX_REFERENCE_MANIFEST_PATH)
    if (manifest.get("status") != "PASS"
            or manifest.get("reference_partition") != REFERENCE_PARTITION
            or manifest.get("frozen_test_used") is not False
            or manifest.get("reference_method") != REFERENCE_METHOD):
        raise ValueError("Risk Index reference manifest không đạt policy validation.")
    models = manifest.get("models")
    if not isinstance(models, dict) or set(models) != set(REFERENCE_MODELS):
        raise ValueError("Risk Index reference phải có đúng hai model demo.")
    for key, path in (("xgboost", XGBOOST_5INPUT_DEMO_PATH), ("logistic", LOGISTIC_5INPUT_DEMO_PATH)):
        if models[key].get("model_sha256") != _sha256(path):
            raise ValueError(f"Risk Index reference {key} không khớp model artifact hiện tại.")
    return _load_reference_npz(FIVE_INPUT_RISK_INDEX_REFERENCE_PATH)


@lru_cache(maxsize=1)
def _load_reference_cached(signature: tuple[int, int, int, int]) -> dict[str, np.ndarray]:
    """Cache nội bộ theo signature file."""
    return _load_reference(signature)


def get_reference_distribution() -> dict[str, np.ndarray]:
    """Lấy reference đã cache; không đọc canonical dataset ở mỗi click."""
    paths = (FIVE_INPUT_RISK_INDEX_REFERENCE_PATH, FIVE_INPUT_RISK_INDEX_REFERENCE_MANIFEST_PATH)
    if any(not path.is_file() for path in paths):
        raise FileNotFoundError(
            "Thiếu Risk Index reference. Chạy `python -m src.models.risk_index --build`."
        )
    signature = tuple(value for path in paths for value in (path.stat().st_size, path.stat().st_mtime_ns))
    return _load_reference_cached(signature)


@lru_cache(maxsize=1)
def _load_six_input_references_cached(
    signature: tuple[tuple[int, int], ...],
) -> dict[str, np.ndarray]:
    """Nạp một lần PD validation của hai model 6-input và kiểm provenance."""
    del signature
    validation_path = MODELING_DIR / "validation_ids.parquet"
    validation_hash = _sha256(validation_path)
    validation_ids = pd.read_parquet(validation_path, columns=["loan_id"])["loan_id"]
    if len(validation_ids) < 2 or validation_ids.isna().any() or not validation_ids.is_unique:
        raise ValueError("Validation loan IDs không hợp lệ cho điểm rủi ro cá nhân.")

    references: dict[str, np.ndarray] = {}
    for model_key, (model_path, manifest_path, predictions_path) in SIX_INPUT_REFERENCE_FILES.items():
        manifest = _read_json(manifest_path)
        split_hashes = manifest.get("split_artifact_sha256")
        if (manifest.get("status") != "PASS"
                or manifest.get("stage") != f"{model_key}-6input-demo-validation-candidate"
                or manifest.get("features") != list(DEMO_6_FEATURES)
                or manifest.get("frozen_test_accessed") is not False
                or not isinstance(split_hashes, dict)
                or split_hashes.get("validation") != validation_hash
                or manifest.get("validation_rows") != len(validation_ids)
                or manifest.get("model_sha256") != _sha256(model_path)
                or manifest.get("validation_prediction_sha256") != _sha256(predictions_path)):
            raise ValueError(f"Reference validation của {model_key} không khớp model/split đã lưu.")

        predictions = pd.read_parquet(predictions_path, columns=["loan_id", "predicted_pd"])
        if (len(predictions) != len(validation_ids)
                or predictions.loan_id.isna().any()
                or not predictions.loan_id.is_unique
                or not np.array_equal(predictions.loan_id.to_numpy(), validation_ids.to_numpy())):
            raise ValueError(f"Reference {model_key} không khớp loan IDs của validation.")
        probabilities = validate_probability_of_default(predictions.predicted_pd.to_numpy())
        references[model_key] = _validate_sorted_reference(
            np.sort(probabilities), name=f"{model_key}-6input-validation",
        )
    return references


def get_six_input_reference_distributions() -> dict[str, np.ndarray]:
    """Lấy hai phân bố PD validation đã lưu; không rescore khi bấm dự đoán."""
    validation_path = MODELING_DIR / "validation_ids.parquet"
    paths = (validation_path, *(
        path for files in SIX_INPUT_REFERENCE_FILES.values() for path in files
    ))
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Thiếu artifact validation cho điểm rủi ro cá nhân: {path}.")
    signature = tuple((path.stat().st_size, path.stat().st_mtime_ns) for path in paths)
    return _load_six_input_references_cached(signature)


def personal_risk_percentile_for_model(model_key: str, probability: float) -> float:
    """Tỷ lệ PD validation của đúng model thấp hơn hoặc bằng PD hồ sơ."""
    if model_key not in REFERENCE_MODELS:
        raise ValueError(f"Model không hợp lệ cho điểm rủi ro cá nhân: {model_key}")
    return percentile_risk_index(
        probability, get_six_input_reference_distributions()[model_key],
    )


def percentile_risk_index(
    probability: float,
    reference_predictions: np.ndarray,
) -> float:
    """Tính vị trí tương đối 0–100 theo tỷ lệ reference PD <= applicant PD."""
    value = float(validate_probability_of_default([probability])[0])
    reference = _validate_sorted_reference(reference_predictions, name="inline")
    rank = int(np.searchsorted(reference, value, side="right"))
    return float(100.0 * rank / reference.size)


def risk_index_for_model(model_key: str, probability: float) -> float:
    """Tính Risk Index theo reference riêng của model được chọn."""
    if model_key not in REFERENCE_MODELS:
        raise ValueError(f"Model không hợp lệ cho Risk Index: {model_key}")
    return percentile_risk_index(probability, get_reference_distribution()[model_key])


def display_risk_index(value: float) -> int:
    """Đổi percentile thành nhãn nguyên 0–100, dùng round half-to-even."""
    if not np.isfinite(value) or not 0 <= value <= 100:
        raise ValueError("Risk Index phải nằm trong [0, 100].")
    return int(np.rint(float(value)))


def main() -> int:
    """CLI dựng reference validation một lần, không train model."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Tạo reference từ validation predictions.")
    args = parser.parse_args()
    if not args.build:
        parser.error("Cần chỉ định --build để tạo Risk Index reference.")
    manifest = build_risk_index_reference()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
