import json

import pandas as pd
import pytest

from src.models.data_split import (
    SplitValidationError,
    create_development_split,
    create_or_load_frozen_split,
    validate_split_result,
)


def _dataset(rows: int = 200) -> pd.DataFrame:
    negative = int(rows * 0.75)
    return pd.DataFrame({
        "loan_id": [f"loan-{index}" for index in range(rows)],
        "target": [0] * negative + [1] * (rows - negative),
        "dti": [float(index % 40) for index in range(rows)],
        "annual_inc": [50000 + index for index in range(rows)],
    })


def test_split_is_deterministic_and_does_not_infer_model_features() -> None:
    frame = _dataset(100)
    first = create_development_split(frame)
    second = create_development_split(frame)

    for name in ("train", "validation", "test"):
        first_partition = getattr(first, name)
        second_partition = getattr(second, name)
        assert first_partition.ids.tolist() == second_partition.ids.tolist()
        assert first_partition.y.tolist() == second_partition.y.tolist()
        assert list(first_partition.X.columns) == []
        assert len(first_partition.X) == len(first_partition.ids)


def test_split_reconciles_rows_has_no_overlap_and_covers_source() -> None:
    frame = _dataset()
    result = create_development_split(frame)
    audit = validate_split_result(frame, result)

    assert sum(audit["partition_rows"].values()) == len(frame)
    assert audit["overlap_counts"] == {
        "train_validation": 0,
        "train_test": 0,
        "validation_test": 0,
    }
    assert audit["union_rows"] == len(frame)
    assert audit["coverage_status"] == "PASS"


def test_split_preserves_target_stratification_with_tolerance() -> None:
    frame = _dataset()
    result = create_development_split(frame)
    audit = validate_split_result(frame, result, stratification_tolerance=0.005)

    assert audit["default_rates"]["full"] == pytest.approx(0.25)
    assert all(
        difference <= 0.005
        for difference in audit["stratification_rate_differences"].values()
    )


def test_explicit_features_are_kept_separate_from_row_membership() -> None:
    frame = _dataset(100)
    result = create_development_split(frame, feature_columns=["dti"])

    assert list(result.train.X.columns) == ["dti"]
    assert "loan_id" not in result.train.X
    assert "target" not in result.train.X

    with pytest.raises(SplitValidationError, match="ID/target"):
        create_development_split(frame, feature_columns=["loan_id"])


def test_duplicate_id_rejects_input() -> None:
    frame = _dataset(20)
    frame.loc[1, "loan_id"] = frame.loc[0, "loan_id"]

    with pytest.raises(SplitValidationError, match="non-null và unique"):
        create_development_split(frame)


def test_null_id_rejects_input() -> None:
    frame = _dataset(20)
    frame.loc[0, "loan_id"] = None

    with pytest.raises(SplitValidationError, match="non-null và unique"):
        create_development_split(frame)


def test_non_binary_or_null_target_rejects_input() -> None:
    frame = _dataset(20)
    frame.loc[0, "target"] = 2
    with pytest.raises(SplitValidationError, match="đủ hai lớp"):
        create_development_split(frame)

    frame = _dataset(20)
    frame.loc[0, "target"] = None
    with pytest.raises(SplitValidationError, match="đủ hai lớp"):
        create_development_split(frame)


@pytest.mark.parametrize(
    "test_size,validation_size",
    [(0, 0.2), (1, 0.2), (0.2, 0), (0.2, 1), (0.6, 0.4)],
)
def test_invalid_split_proportions_reject_input(test_size: float, validation_size: float) -> None:
    with pytest.raises(SplitValidationError, match="Tỷ lệ"):
        create_development_split(_dataset(), test_size=test_size, validation_size=validation_size)


def test_frozen_artifact_creation_writes_membership_only_and_manifest(tmp_path) -> None:
    frame = _dataset()
    artifacts = create_or_load_frozen_split(
        frame,
        output_dir=tmp_path / "modeling",
        canonical_path=tmp_path / "cleaned_dataset.parquet",
        dataset_id="fixture",
        expected_source_rows=len(frame),
    )

    assert artifacts.reused is False
    assert artifacts.manifest["random_state"] == 42
    assert artifacts.manifest["train_fraction"] == pytest.approx(0.6)
    assert artifacts.manifest["validation_fraction"] == pytest.approx(0.2)
    assert artifacts.manifest["test_fraction"] == pytest.approx(0.2)
    assert artifacts.manifest["stratified"] is True
    assert artifacts.manifest["frozen"] is True
    assert artifacts.manifest["stage_status"] == "PASS"
    assert artifacts.manifest["source_rows"] == len(frame)
    assert artifacts.manifest["total_rows"] == len(frame)
    assert artifacts.manifest["overlap_checks"] == {
        "train_validation": 0,
        "train_test": 0,
        "validation_test": 0,
    }
    assert all(path.is_file() for path in artifacts.artifact_paths.values())
    assert not list((tmp_path / "modeling").glob("*.partial.parquet"))

    for key in ("train", "validation", "test"):
        persisted = pd.read_parquet(artifacts.artifact_paths[key])
        assert set(persisted.columns) == {"loan_id", "target", "split"}
        assert persisted["loan_id"].notna().all()
        assert persisted["loan_id"].is_unique
        assert set(persisted["target"].unique()) == {0, 1}


def test_frozen_artifact_rerun_reuses_identical_membership(tmp_path) -> None:
    frame = _dataset()
    output_dir = tmp_path / "modeling"
    first = create_or_load_frozen_split(
        frame,
        output_dir=output_dir,
        canonical_path=tmp_path / "cleaned_dataset.parquet",
        dataset_id="fixture",
        expected_source_rows=len(frame),
    )
    first_ids = {
        key: pd.read_parquet(first.artifact_paths[key])["loan_id"].tolist()
        for key in ("train", "validation", "test")
    }

    second = create_or_load_frozen_split(
        frame,
        output_dir=output_dir,
        canonical_path=tmp_path / "cleaned_dataset.parquet",
        dataset_id="fixture",
        expected_source_rows=len(frame),
    )
    second_ids = {
        key: pd.read_parquet(second.artifact_paths[key])["loan_id"].tolist()
        for key in ("train", "validation", "test")
    }

    assert second.reused is True
    assert first_ids == second_ids
    assert json.loads(first.artifact_paths["manifest"].read_text())["frozen"] is True


def test_existing_frozen_split_fails_closed_for_changed_source(tmp_path) -> None:
    frame = _dataset()
    output_dir = tmp_path / "modeling"
    create_or_load_frozen_split(
        frame,
        output_dir=output_dir,
        canonical_path=tmp_path / "cleaned_dataset.parquet",
        dataset_id="fixture",
        expected_source_rows=len(frame),
    )
    changed = frame.copy()
    changed.loc[0, "loan_id"] = "changed-loan"

    with pytest.raises(SplitValidationError, match="coverage|source"):
        create_or_load_frozen_split(
            changed,
            output_dir=output_dir,
            canonical_path=tmp_path / "cleaned_dataset.parquet",
            dataset_id="fixture",
            expected_source_rows=len(changed),
        )


def test_existing_manifest_missing_required_field_fails_closed(tmp_path) -> None:
    frame = _dataset()
    output_dir = tmp_path / "modeling"
    artifacts = create_or_load_frozen_split(
        frame,
        output_dir=output_dir,
        canonical_path=tmp_path / "cleaned_dataset.parquet",
        dataset_id="fixture",
        expected_source_rows=len(frame),
    )
    manifest = json.loads(artifacts.artifact_paths["manifest"].read_text())
    manifest.pop("random_state")
    artifacts.artifact_paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SplitValidationError, match="manifest thiếu fields"):
        create_or_load_frozen_split(
            frame,
            output_dir=output_dir,
            canonical_path=tmp_path / "cleaned_dataset.parquet",
            dataset_id="fixture",
            expected_source_rows=len(frame),
        )


def test_incompatible_source_count_fails_closed(tmp_path) -> None:
    with pytest.raises(SplitValidationError, match="row count"):
        create_or_load_frozen_split(
            _dataset(20),
            output_dir=tmp_path / "modeling",
            canonical_path=tmp_path / "cleaned_dataset.parquet",
            dataset_id="fixture",
            expected_source_rows=21,
        )
