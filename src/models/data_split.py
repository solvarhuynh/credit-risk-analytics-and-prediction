"""Chia và đóng băng train/validation/frozen-test cho Lending Club."""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
from sklearn.model_selection import train_test_split

from src.config import ID_COLUMN, MODELING_DIR, TARGET_COLUMN


DEFAULT_STRATIFICATION_TOLERANCE = 0.005


class SplitValidationError(ValueError):
    """Split hoặc frozen artifact không đạt contract."""


@dataclass(frozen=True)
class ModelingPartition:
    X: pd.DataFrame
    y: pd.Series
    ids: pd.Series


@dataclass(frozen=True)
class DevelopmentSplitResult:
    train: ModelingPartition
    validation: ModelingPartition
    test: ModelingPartition
    random_state: int


@dataclass(frozen=True)
class FrozenSplitArtifacts:
    split: DevelopmentSplitResult
    manifest: dict[str, Any]
    audit: dict[str, Any]
    artifact_paths: dict[str, Path]
    reused: bool


def _validate(frame: pd.DataFrame, target_column: str, id_column: str) -> None:
    missing = {target_column, id_column} - set(frame.columns)
    if missing:
        raise SplitValidationError(f"Thiếu cột bắt buộc: {sorted(missing)}")
    if frame[id_column].isna().any() or not frame[id_column].is_unique:
        raise SplitValidationError(f"{id_column} phải non-null và unique.")
    if frame[target_column].isna().any() or set(frame[target_column].unique()) != {0, 1}:
        raise SplitValidationError(f"{target_column} phải chứa đủ hai lớp 0/1 và không null.")


def _validate_feature_columns(
    frame: pd.DataFrame,
    feature_columns: Sequence[str] | None,
    target_column: str,
    id_column: str,
) -> None:
    if feature_columns is None:
        return
    features = list(feature_columns)
    missing = sorted(set(features) - set(frame.columns))
    if missing:
        raise SplitValidationError(f"Thiếu feature columns được chỉ định: {missing}")
    forbidden = sorted({target_column, id_column}.intersection(features))
    if forbidden:
        raise SplitValidationError(f"Feature columns không được chứa ID/target: {forbidden}")
    if len(features) != len(set(features)):
        raise SplitValidationError("Feature columns bị trùng.")


def _partition(
    frame: pd.DataFrame,
    target_column: str,
    id_column: str,
    feature_columns: Sequence[str] | None = None,
) -> ModelingPartition:
    if feature_columns is None:
        features = pd.DataFrame(index=frame.index)
    else:
        features = frame.loc[:, list(feature_columns)].copy()
    return ModelingPartition(
        X=features,
        y=frame[target_column].astype(int).copy(),
        ids=frame[id_column].copy(),
    )


def create_development_split(
    dataset: pd.DataFrame,
    *,
    target_column: str = TARGET_COLUMN,
    id_column: str = ID_COLUMN,
    test_size: float = 0.20,
    validation_size: float = 0.20,
    random_state: int = 42,
    feature_columns: Sequence[str] | None = None,
) -> DevelopmentSplitResult:
    """Tạo split stratified deterministic mà không fit model/preprocessing."""

    _validate(dataset, target_column, id_column)
    _validate_feature_columns(dataset, feature_columns, target_column, id_column)
    if not 0 < test_size < 1 or not 0 < validation_size < 1 or test_size + validation_size >= 1:
        raise SplitValidationError("Tỷ lệ validation/test không hợp lệ.")

    development, test = train_test_split(
        dataset,
        test_size=test_size,
        random_state=random_state,
        stratify=dataset[target_column],
    )
    relative_validation = validation_size / (1 - test_size)
    train, validation = train_test_split(
        development,
        test_size=relative_validation,
        random_state=random_state,
        stratify=development[target_column],
    )
    return DevelopmentSplitResult(
        train=_partition(train, target_column, id_column, feature_columns),
        validation=_partition(validation, target_column, id_column, feature_columns),
        test=_partition(test, target_column, id_column, feature_columns),
        random_state=random_state,
    )


def _partition_items(result: DevelopmentSplitResult) -> tuple[tuple[str, ModelingPartition], ...]:
    return (
        ("train", result.train),
        ("validation", result.validation),
        ("test", result.test),
    )


def _target_counts(values: pd.Series) -> dict[str, int]:
    counts = Counter(str(value) for value in values.tolist())
    return {str(label): int(counts.get(str(label), 0)) for label in (0, 1)}


def validate_split_result(
    dataset: pd.DataFrame,
    result: DevelopmentSplitResult,
    *,
    target_column: str = TARGET_COLUMN,
    id_column: str = ID_COLUMN,
    expected_source_rows: int | None = None,
    stratification_tolerance: float = DEFAULT_STRATIFICATION_TOLERANCE,
) -> dict[str, Any]:
    """Validate coverage, exclusivity, target integrity and stratification."""

    _validate(dataset, target_column, id_column)
    if expected_source_rows is not None and len(dataset) != expected_source_rows:
        raise SplitValidationError(
            f"Canonical source row count không khớp: expected={expected_source_rows}, actual={len(dataset)}"
        )
    if stratification_tolerance <= 0:
        raise SplitValidationError("stratification_tolerance phải lớn hơn 0.")

    source_ids = set(dataset[id_column].tolist())
    source_lookup = dataset.set_index(id_column)[target_column]
    partition_sets: dict[str, set[Any]] = {}
    partition_counts: dict[str, int] = {}
    partition_target_counts: dict[str, dict[str, int]] = {}
    default_rates: dict[str, float] = {}

    for name, partition in _partition_items(result):
        ids = partition.ids
        target = partition.y
        if ids.isna().any() or not ids.is_unique:
            raise SplitValidationError(f"{name} có loan_id null hoặc duplicate.")
        if target.isna().any() or not set(target.unique()).issubset({0, 1}):
            raise SplitValidationError(f"{name} có target null hoặc ngoài {{0, 1}}.")
        if len(ids) != len(target) or len(partition.X) != len(ids):
            raise SplitValidationError(f"{name} có kích thước X/y/ids không đồng nhất.")

        ids_set = set(ids.tolist())
        if not ids_set.issubset(source_ids):
            raise SplitValidationError(f"{name} chứa loan_id không có trong canonical source.")
        expected_target = source_lookup.reindex(ids.tolist())
        if expected_target.isna().any() or not expected_target.astype(int).reset_index(drop=True).equals(
            target.astype(int).reset_index(drop=True)
        ):
            raise SplitValidationError(f"{name} target không khớp canonical source.")

        partition_sets[name] = ids_set
        partition_counts[name] = len(ids)
        partition_target_counts[name] = _target_counts(target)
        default_rates[name] = float(target.mean())

    overlap_counts = {
        "train_validation": len(partition_sets["train"] & partition_sets["validation"]),
        "train_test": len(partition_sets["train"] & partition_sets["test"]),
        "validation_test": len(partition_sets["validation"] & partition_sets["test"]),
    }
    if any(overlap_counts.values()):
        raise SplitValidationError(f"Split có overlap: {overlap_counts}")

    union_ids = set().union(*partition_sets.values())
    if union_ids != source_ids:
        missing = len(source_ids - union_ids)
        extra = len(union_ids - source_ids)
        raise SplitValidationError(f"Split coverage không khớp source: missing={missing}, extra={extra}")

    full_target_counts = _target_counts(dataset[target_column])
    full_rate = float(dataset[target_column].mean())
    rate_differences = {
        name: abs(rate - full_rate) for name, rate in default_rates.items()
    }
    if any(difference > stratification_tolerance for difference in rate_differences.values()):
        raise SplitValidationError(
            f"Target prevalence lệch quá tolerance: differences={rate_differences}, "
            f"tolerance={stratification_tolerance}"
        )

    total_rows = sum(partition_counts.values())
    if total_rows != len(dataset):
        raise SplitValidationError(
            f"Partition rows không exhaustive: partitions={total_rows}, source={len(dataset)}"
        )

    return {
        "source_rows": len(dataset),
        "partition_rows": partition_counts,
        "total_rows": total_rows,
        "full_target_counts": full_target_counts,
        "target_counts": partition_target_counts,
        "default_rates": {"full": full_rate, **default_rates},
        "stratification_rate_differences": rate_differences,
        "stratification_tolerance": stratification_tolerance,
        "overlap_counts": overlap_counts,
        "union_rows": len(union_ids),
        "coverage_status": "PASS",
    }


def _assert_deterministic(
    dataset: pd.DataFrame,
    result: DevelopmentSplitResult,
    *,
    target_column: str,
    id_column: str,
    test_size: float,
    validation_size: float,
    random_state: int,
) -> None:
    repeated = create_development_split(
        dataset,
        target_column=target_column,
        id_column=id_column,
        test_size=test_size,
        validation_size=validation_size,
        random_state=random_state,
    )
    repeated_partitions = dict(_partition_items(repeated))
    for name, first in _partition_items(result):
        second = repeated_partitions[name]
        if first.ids.tolist() != second.ids.tolist() or first.y.tolist() != second.y.tolist():
            raise SplitValidationError(f"Split không deterministic ở partition {name}.")


def _artifact_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "train": output_dir / "train_ids.parquet",
        "validation": output_dir / "validation_ids.parquet",
        "test": output_dir / "test_ids.parquet",
        "manifest": output_dir / "split_manifest.json",
    }


def _partial_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}.partial{path.suffix}")


def _split_frame(partition: ModelingPartition, split_name: str, id_column: str, target_column: str) -> pd.DataFrame:
    return pd.DataFrame({
        id_column: partition.ids.reset_index(drop=True),
        target_column: partition.y.astype(int).reset_index(drop=True),
        "split": split_name,
    })


def _read_partition(
    path: Path,
    id_column: str,
    target_column: str,
    expected_split: str,
) -> ModelingPartition:
    if not path.is_file():
        raise SplitValidationError(f"Thiếu frozen split artifact: {path}")
    frame = pd.read_parquet(path)
    expected = {id_column, target_column}
    if not expected.issubset(frame.columns):
        raise SplitValidationError(f"Artifact {path.name} thiếu ID/target columns.")
    extra = set(frame.columns) - expected - {"split"}
    if extra:
        raise SplitValidationError(f"Artifact {path.name} chứa feature columns ngoài scope: {sorted(extra)}")
    if "split" in frame and set(frame["split"].dropna().unique()) != {expected_split}:
        raise SplitValidationError(f"Artifact {path.name} có split label không đúng: {expected_split}")
    return ModelingPartition(
        X=pd.DataFrame(index=frame.index),
        y=frame[target_column].copy(),
        ids=frame[id_column].copy(),
    )


def _split_from_artifacts(paths: dict[str, Path], id_column: str, target_column: str) -> DevelopmentSplitResult:
    return DevelopmentSplitResult(
        train=_read_partition(paths["train"], id_column, target_column, "train"),
        validation=_read_partition(paths["validation"], id_column, target_column, "validation"),
        test=_read_partition(paths["test"], id_column, target_column, "test"),
        random_state=-1,
    )


def _manifest_from_audit(
    audit: dict[str, Any],
    *,
    dataset: pd.DataFrame,
    dataset_id: str,
    canonical_path: Path,
    id_column: str,
    target_column: str,
    random_state: int,
    test_size: float,
    validation_size: float,
    paths: dict[str, Path],
) -> dict[str, Any]:
    train_fraction = 1 - test_size - validation_size
    return {
        "dataset_id": dataset_id,
        "canonical_path": str(canonical_path),
        "source_rows": int(audit["source_rows"]),
        "source_columns": list(dataset.columns),
        "id_column": id_column,
        "target_column": target_column,
        "random_state": random_state,
        "train_fraction": train_fraction,
        "validation_fraction": validation_size,
        "test_fraction": test_size,
        "stratified": True,
        "train_rows": int(audit["partition_rows"]["train"]),
        "validation_rows": int(audit["partition_rows"]["validation"]),
        "test_rows": int(audit["partition_rows"]["test"]),
        "total_rows": int(audit["total_rows"]),
        "train_target_counts": audit["target_counts"]["train"],
        "validation_target_counts": audit["target_counts"]["validation"],
        "test_target_counts": audit["target_counts"]["test"],
        "full_target_counts": audit["full_target_counts"],
        "default_rates": audit["default_rates"],
        "stratification_rate_differences": audit["stratification_rate_differences"],
        "stratification_tolerance": audit["stratification_tolerance"],
        "overlap_checks": audit["overlap_counts"],
        "union_rows": int(audit["union_rows"]),
        "coverage_status": audit["coverage_status"],
        "deterministic": True,
        "frozen": True,
        "stage": "ml-lc-02",
        "stage_status": "PASS",
        "artifact_paths": {
            "train_ids": str(paths["train"]),
            "validation_ids": str(paths["validation"]),
            "test_ids": str(paths["test"]),
            "manifest": str(paths["manifest"]),
        },
        "provenance": {
            "splitter": "src.models.data_split.create_development_split",
            "membership_columns_only": [id_column, target_column],
            "feature_schema_source": "ML-LC-01",
            "preprocessing_fitted": False,
            "model_trained": False,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    }


def _validate_existing_manifest(
    manifest: dict[str, Any],
    *,
    dataset: pd.DataFrame,
    dataset_id: str,
    canonical_path: Path,
    id_column: str,
    target_column: str,
    random_state: int,
    test_size: float,
    validation_size: float,
    paths: dict[str, Path],
    audit: dict[str, Any],
) -> None:
    required = {
        "dataset_id", "canonical_path", "source_rows", "source_columns", "id_column", "target_column",
        "random_state", "train_fraction", "validation_fraction", "test_fraction", "stratified",
        "train_rows", "validation_rows", "test_rows", "total_rows", "train_target_counts",
        "validation_target_counts", "test_target_counts", "full_target_counts", "overlap_checks",
        "union_rows", "coverage_status", "deterministic", "frozen", "stage", "stage_status",
        "artifact_paths", "provenance",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise SplitValidationError(f"Frozen split manifest thiếu fields: {missing}")
    expected = {
        "dataset_id": dataset_id,
        "id_column": id_column,
        "target_column": target_column,
        "random_state": random_state,
        "train_fraction": 1 - test_size - validation_size,
        "validation_fraction": validation_size,
        "test_fraction": test_size,
        "stratified": True,
        "source_rows": len(dataset),
        "source_columns": list(dataset.columns),
        "stage": "ml-lc-02",
        "stage_status": "PASS",
        "coverage_status": "PASS",
        "deterministic": True,
        "frozen": True,
    }
    for field, value in expected.items():
        if manifest[field] != value:
            raise SplitValidationError(
                f"Frozen split manifest không khớp {field}: expected={value}, actual={manifest[field]}"
            )
    if Path(manifest["canonical_path"]).resolve() != canonical_path.resolve():
        raise SplitValidationError("Frozen split canonical_path không khớp source hiện tại.")
    manifest_artifacts = manifest["artifact_paths"]
    expected_artifacts = {
        "train_ids": paths["train"],
        "validation_ids": paths["validation"],
        "test_ids": paths["test"],
        "manifest": paths["manifest"],
    }
    for key, path in expected_artifacts.items():
        if Path(manifest_artifacts[key]).name != path.name:
            raise SplitValidationError(f"Frozen split artifact path không khớp: {key}")
    if manifest["train_rows"] != audit["partition_rows"]["train"]:
        raise SplitValidationError("Manifest train_rows không khớp artifact.")
    if manifest["validation_rows"] != audit["partition_rows"]["validation"]:
        raise SplitValidationError("Manifest validation_rows không khớp artifact.")
    if manifest["test_rows"] != audit["partition_rows"]["test"]:
        raise SplitValidationError("Manifest test_rows không khớp artifact.")
    if manifest["total_rows"] != audit["total_rows"] or manifest["union_rows"] != audit["union_rows"]:
        raise SplitValidationError("Manifest total/union rows không khớp artifact.")
    if manifest["overlap_checks"] != audit["overlap_counts"]:
        raise SplitValidationError("Manifest overlap checks không khớp artifact.")
    for field, key in (
        ("train_target_counts", "train"),
        ("validation_target_counts", "validation"),
        ("test_target_counts", "test"),
    ):
        if manifest[field] != audit["target_counts"][key]:
            raise SplitValidationError(f"Manifest {field} không khớp artifact.")
    if manifest["full_target_counts"] != audit["full_target_counts"]:
        raise SplitValidationError("Manifest full_target_counts không khớp source.")


def create_or_load_frozen_split(
    dataset: pd.DataFrame,
    *,
    output_dir: Path = MODELING_DIR,
    canonical_path: Path,
    dataset_id: str,
    target_column: str = TARGET_COLUMN,
    id_column: str = ID_COLUMN,
    test_size: float = 0.20,
    validation_size: float = 0.20,
    random_state: int = 42,
    expected_source_rows: int | None = None,
    stratification_tolerance: float = DEFAULT_STRATIFICATION_TOLERANCE,
) -> FrozenSplitArtifacts:
    """Create once, then reuse and validate the frozen split artifacts."""

    _validate(dataset, target_column, id_column)
    if expected_source_rows is not None and len(dataset) != expected_source_rows:
        raise SplitValidationError(
            f"Canonical source row count không khớp: expected={expected_source_rows}, actual={len(dataset)}"
        )
    if not 0 < test_size < 1 or not 0 < validation_size < 1 or test_size + validation_size >= 1:
        raise SplitValidationError("Tỷ lệ validation/test không hợp lệ.")
    output_dir = Path(output_dir)
    paths = _artifact_paths(output_dir)
    partial_paths = [_partial_path(path) for path in paths.values()]
    existing_finals = [path for path in paths.values() if path.exists()]
    partials = [path for path in partial_paths if path.exists()]
    if existing_finals:
        if len(existing_finals) != len(paths):
            raise SplitValidationError("Frozen split artifacts không đầy đủ; không tự overwrite.")
        if partials:
            raise SplitValidationError("Tồn tại partial frozen split cùng với artifact final.")
        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        split = _split_from_artifacts(paths, id_column, target_column)
        manifest_random_state = manifest.get("random_state", -1)
        if not isinstance(manifest_random_state, int):
            raise SplitValidationError("Frozen split manifest random_state không hợp lệ.")
        split = DevelopmentSplitResult(split.train, split.validation, split.test, manifest_random_state)
        audit = validate_split_result(
            dataset,
            split,
            target_column=target_column,
            id_column=id_column,
            expected_source_rows=expected_source_rows,
            stratification_tolerance=stratification_tolerance,
        )
        _validate_existing_manifest(
            manifest,
            dataset=dataset,
            dataset_id=dataset_id,
            canonical_path=Path(canonical_path),
            id_column=id_column,
            target_column=target_column,
            random_state=random_state,
            test_size=test_size,
            validation_size=validation_size,
            paths=paths,
            audit=audit,
        )
        return FrozenSplitArtifacts(split, manifest, audit, paths, reused=True)

    if partials:
        raise SplitValidationError("Tồn tại partial frozen split; cần kiểm tra và dọn có chủ đích trước khi chạy lại.")

    split = create_development_split(
        dataset,
        target_column=target_column,
        id_column=id_column,
        test_size=test_size,
        validation_size=validation_size,
        random_state=random_state,
    )
    audit = validate_split_result(
        dataset,
        split,
        target_column=target_column,
        id_column=id_column,
        expected_source_rows=expected_source_rows,
        stratification_tolerance=stratification_tolerance,
    )
    _assert_deterministic(
        dataset,
        split,
        target_column=target_column,
        id_column=id_column,
        test_size=test_size,
        validation_size=validation_size,
        random_state=random_state,
    )
    manifest = _manifest_from_audit(
        audit,
        dataset=dataset,
        dataset_id=dataset_id,
        canonical_path=Path(canonical_path),
        id_column=id_column,
        target_column=target_column,
        random_state=random_state,
        test_size=test_size,
        validation_size=validation_size,
        paths=paths,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    promoted: list[Path] = []
    try:
        frames = {
            "train": _split_frame(split.train, "train", id_column, target_column),
            "validation": _split_frame(split.validation, "validation", id_column, target_column),
            "test": _split_frame(split.test, "test", id_column, target_column),
        }
        for key, frame in frames.items():
            frame.to_parquet(_partial_path(paths[key]), index=False)
        json_partial = _partial_path(paths["manifest"])
        json_partial.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        for key in ("train", "validation", "test"):
            os.replace(_partial_path(paths[key]), paths[key])
            promoted.append(paths[key])
        os.replace(json_partial, paths["manifest"])
        promoted.append(paths["manifest"])

        persisted = _split_from_artifacts(paths, id_column, target_column)
        persisted = DevelopmentSplitResult(persisted.train, persisted.validation, persisted.test, random_state)
        persisted_audit = validate_split_result(
            dataset,
            persisted,
            target_column=target_column,
            id_column=id_column,
            expected_source_rows=expected_source_rows,
            stratification_tolerance=stratification_tolerance,
        )
        _validate_existing_manifest(
            manifest,
            dataset=dataset,
            dataset_id=dataset_id,
            canonical_path=Path(canonical_path),
            id_column=id_column,
            target_column=target_column,
            random_state=random_state,
            test_size=test_size,
            validation_size=validation_size,
            paths=paths,
            audit=persisted_audit,
        )
    except BaseException:
        for path in promoted:
            path.unlink(missing_ok=True)
        for path in partial_paths:
            path.unlink(missing_ok=True)
        raise

    return FrozenSplitArtifacts(persisted, manifest, persisted_audit, paths, reused=False)
