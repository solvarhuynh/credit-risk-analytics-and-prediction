"""Unit tests for the Exploratory Data Analysis module (src/data/eda.py).

All tests execute against small synthetic fixtures only; the full 64 MB canonical
dataset is never loaded during unit testing.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.eda import (
    AGE_GROUP_BINS,
    AGE_GROUP_LABELS,
    FIGURE_FILENAMES,
    SENTINEL_DAYS_EMPLOYED,
    SPEARMAN_SELECTED_COLUMNS,
    compute_age_group_summary,
    compute_categorical_default_rate,
    compute_days_employed_audit,
    compute_income_summary,
    compute_spearman_correlation,
    compute_target_distribution,
    generate_all_eda_figures,
    plot_days_employed_before_after,
    plot_default_rate_by_age_group,
    plot_default_rate_by_occupation_and_contract,
    plot_income_distribution_by_target,
    plot_key_numeric_spearman_heatmap,
    render_eda_report,
    run_eda_pipeline,
    validate_eda_input_dataframe,
    write_eda_report_atomic,
)


@pytest.fixture
def synthetic_clean_dataset() -> pd.DataFrame:
    """Create a minimal synthetic canonical dataset covering all roles and EDA features."""
    n_rows = 20
    data: dict[str, list[object]] = {
        "SK_ID_CURR": list(range(100001, 100001 + n_rows)),
        "TARGET": [0 if i % 4 != 0 else 1 for i in range(n_rows)],  # 15 zeros, 5 ones
        "AMT_INCOME_TOTAL": [50000.0 + i * 10000.0 for i in range(n_rows)],
        "AMT_CREDIT": [100000.0 + i * 20000.0 for i in range(n_rows)],
        "AMT_ANNUITY": [5000.0 + i * 1000.0 for i in range(n_rows)],
        "AMT_GOODS_PRICE": [90000.0 + i * 18000.0 for i in range(n_rows)],
        "AGE_YEARS": [20.0 + i * 2.5 for i in range(n_rows)],  # 20.0 to 67.5
        "DAYS_EMPLOYED": [-500 - i * 100 if i >= 4 else np.nan for i in range(n_rows)],
        "DAYS_EMPLOYED_ANOM": [1 if i < 4 else 0 for i in range(n_rows)],
        "EMPLOYED_YEARS": [1.5 + i * 0.3 if i >= 4 else np.nan for i in range(n_rows)],
        "CREDIT_TO_INCOME_RATIO": [2.0 + (i % 3) * 0.5 for i in range(n_rows)],
        "ANNUITY_TO_INCOME_RATIO": [0.1 + (i % 2) * 0.05 for i in range(n_rows)],
        "EXT_SOURCE_2": [0.3 + (i % 5) * 0.1 for i in range(n_rows)],
        "EXT_SOURCE_3": [0.4 + (i % 4) * 0.1 for i in range(n_rows)],
        "BUREAU_CREDIT_COUNT": [i % 6 for i in range(n_rows)],
        "PREV_APPLICATION_COUNT": [i % 4 for i in range(n_rows)],
        "OCCUPATION_TYPE": ["Laborers" if i % 3 == 0 else ("Sales staff" if i % 3 == 1 else None) for i in range(n_rows)],
        "NAME_CONTRACT_TYPE": ["Cash loans" if i < 16 else "Revolving loans" for i in range(n_rows)],
    }
    df = pd.DataFrame(data)
    df["AGE_GROUP"] = pd.cut(
        df["AGE_YEARS"],
        bins=list(AGE_GROUP_BINS),
        labels=list(AGE_GROUP_LABELS),
        right=False,
    )
    return df


@pytest.fixture
def synthetic_raw_dataset(synthetic_clean_dataset: pd.DataFrame) -> pd.DataFrame:
    """Create corresponding synthetic raw application dataset with sentinels."""
    clean_df = synthetic_clean_dataset
    raw_data = {
        "SK_ID_CURR": clean_df["SK_ID_CURR"].tolist(),
        "DAYS_EMPLOYED": [
            SENTINEL_DAYS_EMPLOYED if clean_df.loc[i, "DAYS_EMPLOYED_ANOM"] == 1 else clean_df.loc[i, "DAYS_EMPLOYED"]
            for i in range(len(clean_df))
        ],
    }
    return pd.DataFrame(raw_data)


# ---------------------------------------------------------------------------
# 1. Input Validation Tests
# ---------------------------------------------------------------------------


def test_validate_eda_input_dataframe_valid(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Valid canonical DataFrame passes validation without error."""
    validate_eda_input_dataframe(synthetic_clean_dataset)


def test_validate_eda_input_dataframe_empty() -> None:
    """Reject empty DataFrame."""
    with pytest.raises(ValueError, match="empty DataFrame"):
        validate_eda_input_dataframe(pd.DataFrame())


def test_validate_eda_input_dataframe_missing_identifier(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Reject DataFrame missing SK_ID_CURR."""
    bad_df = synthetic_clean_dataset.drop(columns=["SK_ID_CURR"])
    with pytest.raises(ValueError, match="Missing primary identifier"):
        validate_eda_input_dataframe(bad_df)


def test_validate_eda_input_dataframe_duplicate_identifier(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Reject DataFrame with duplicate SK_ID_CURR."""
    bad_df = synthetic_clean_dataset.copy()
    bad_df.loc[1, "SK_ID_CURR"] = bad_df.loc[0, "SK_ID_CURR"]
    with pytest.raises(ValueError, match="duplicate values"):
        validate_eda_input_dataframe(bad_df)


def test_validate_eda_input_dataframe_non_binary_target(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Reject DataFrame with non-binary TARGET."""
    bad_df = synthetic_clean_dataset.copy()
    bad_df.loc[0, "TARGET"] = 2
    with pytest.raises(ValueError, match="TARGET must be binary"):
        validate_eda_input_dataframe(bad_df)


def test_validate_eda_input_dataframe_null_target(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Reject DataFrame with null TARGET."""
    bad_df = synthetic_clean_dataset.copy()
    bad_df.loc[0, "TARGET"] = np.nan
    with pytest.raises(ValueError, match="TARGET contains null values"):
        validate_eda_input_dataframe(bad_df)


# ---------------------------------------------------------------------------
# 2. Statistical Metric Calculation Tests
# ---------------------------------------------------------------------------


def test_compute_target_distribution(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Verify target distribution counts and percentages."""
    dist = compute_target_distribution(synthetic_clean_dataset)
    assert dist["total_count"] == 20
    assert dist["count_0"] == 15
    assert dist["count_1"] == 5
    assert dist["default_rate"] == 0.25
    assert dist["default_rate_pct"] == 25.0


def test_compute_income_summary(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Verify income metrics, medians, IQRs, and clipping stats."""
    summary = compute_income_summary(synthetic_clean_dataset, clip_quantile=0.90)

    assert summary["target_0"]["count"] == 15
    assert summary["target_1"]["count"] == 5
    assert summary["target_0"]["missing_count"] == 0
    assert summary["target_1"]["missing_count"] == 0
    assert summary["target_0"]["iqr"] > 0
    assert summary["target_1"]["iqr"] > 0
    assert summary["clipped_observation_count"] >= 1
    assert summary["clip_threshold"] > 0


def test_compute_age_group_summary_fixed_bins(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Verify fixed age bin boundaries, counts, non-defaults, and default rates."""
    agg = compute_age_group_summary(synthetic_clean_dataset)

    assert list(agg["age_group"]) == list(AGE_GROUP_LABELS)
    assert agg["customer_count"].sum() == len(synthetic_clean_dataset)
    assert agg["default_count"].sum() == synthetic_clean_dataset["TARGET"].sum()
    assert agg["non_default_count"].sum() == (synthetic_clean_dataset["TARGET"] == 0).sum()
    assert (agg["customer_count"] == agg["default_count"] + agg["non_default_count"]).all()
    assert (agg["default_rate"] >= 0.0).all()
    assert (agg["default_rate"] <= 1.0).all()
    for _, row in agg.iterrows():
        if row["customer_count"] > 0:
            expected_rate = row["default_count"] / row["customer_count"]
            assert abs(row["default_rate"] - expected_rate) < 1e-6


def test_canonical_age_group_agrees_with_derived(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Verify canonical persisted AGE_GROUP agrees 100% with deterministic grouping derived from AGE_YEARS."""
    agg_canonical = compute_age_group_summary(synthetic_clean_dataset)
    agg_derived = compute_age_group_summary(synthetic_clean_dataset.drop(columns=["AGE_GROUP"]))
    pd.testing.assert_frame_equal(agg_canonical, agg_derived)


def test_age_group_derived_without_input_column(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Verify AGE_GROUP is derived from AGE_YEARS as a valid fallback/validation when absent."""
    df_no_age_group = synthetic_clean_dataset.drop(columns=["AGE_GROUP"])
    agg = compute_age_group_summary(df_no_age_group)

    assert "age_group" in agg.columns
    assert agg["customer_count"].sum() == len(df_no_age_group)
    assert agg["default_count"].sum() == df_no_age_group["TARGET"].sum()
    assert agg["non_default_count"].sum() == (df_no_age_group["TARGET"] == 0).sum()
    assert (agg["customer_count"] == agg["default_count"] + agg["non_default_count"]).all()


def test_age_group_boundary_and_out_of_range() -> None:
    """Verify exact boundary mapping and explicit handling of missing/out-of-range ages."""
    test_data = pd.DataFrame({
        "SK_ID_CURR": list(range(1, 15)),
        "TARGET": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        "AGE_YEARS": [
            0.0,    # Under 25
            24.99,  # Under 25
            25.0,   # 25-34
            34.99,  # 25-34
            35.0,   # 35-44
            44.99,  # 35-44
            45.0,   # 45-54
            54.99,  # 45-54
            55.0,   # 55-64
            64.99,  # 55-64
            65.0,   # 65+
            119.9,  # 65+
            -1.0,   # Out-of-range (<0) -> Missing/Out-of-Range
            np.nan, # NaN -> Missing/Out-of-Range
        ],
    })
    agg = compute_age_group_summary(test_data)

    # Reconciliation checks
    assert agg["customer_count"].sum() == len(test_data)
    assert agg["default_count"].sum() == test_data["TARGET"].sum()
    assert agg["non_default_count"].sum() == (test_data["TARGET"] == 0).sum()
    assert (agg["customer_count"] == agg["default_count"] + agg["non_default_count"]).all()

    # Verify group counts
    row_map = agg.set_index("age_group")["customer_count"].to_dict()
    assert row_map["Under 25"] == 2
    assert row_map["25-34"] == 2
    assert row_map["35-44"] == 2
    assert row_map["45-54"] == 2
    assert row_map["55-64"] == 2
    assert row_map["65+"] == 2
    assert row_map["Missing/Out-of-Range"] == 2


def test_compute_categorical_default_rate_with_missing(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Verify categorical aggregation preserves missing values as explicit category without demographic inference."""
    agg = compute_categorical_default_rate(synthetic_clean_dataset, "OCCUPATION_TYPE")

    categories = list(agg["category"])
    assert "Missing/Unknown" in categories
    assert "Laborers" in categories
    assert "Sales staff" in categories
    assert agg["total_count"].sum() == len(synthetic_clean_dataset)

    # Verify no demographic or social identity is inferred from missingness alone
    forbidden_terms = {"retire", "retired", "retirement", "pension", "pensioner", "unemployed", "dependent"}
    for cat in categories:
        cat_lower = str(cat).lower()
        for term in forbidden_terms:
            assert term not in cat_lower, f"Unsupported demographic proxy '{term}' inferred in category '{cat}'"

    # Verify deterministic sorting (default_rate desc, category asc)
    rates = list(agg["default_rate"])
    assert all(rates[i] >= rates[i + 1] for i in range(len(rates) - 1))


def test_compute_spearman_correlation_properties(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Verify Spearman matrix shape, symmetry, and diagonal properties."""
    corr = compute_spearman_correlation(synthetic_clean_dataset, SPEARMAN_SELECTED_COLUMNS)

    assert corr.shape == (len(SPEARMAN_SELECTED_COLUMNS), len(SPEARMAN_SELECTED_COLUMNS))
    # Symmetric
    np.testing.assert_allclose(corr.values, corr.values.T, atol=1e-8)
    # Diagonal is exactly 1.0
    np.testing.assert_allclose(np.diag(corr.values), np.ones(len(SPEARMAN_SELECTED_COLUMNS)), atol=1e-8)
    # All values bounded in [-1.0, 1.0]
    assert (corr.values >= -1.0 - 1e-8).all()
    assert (corr.values <= 1.0 + 1e-8).all()


def test_compute_days_employed_audit(
    synthetic_clean_dataset: pd.DataFrame,
    synthetic_raw_dataset: pd.DataFrame,
) -> None:
    """Verify days employed audit captures raw sentinels, cleaned NaNs, and leaves non-sentinels intact."""
    audit = compute_days_employed_audit(synthetic_raw_dataset, synthetic_clean_dataset)

    assert audit["raw_sentinel_count"] == 4
    assert audit["clean_sentinel_count"] == 0
    assert audit["clean_nan_count"] == 4
    assert audit["anom_flag_count"] == 4
    assert audit["raw_sentinel_count"] == audit["anom_flag_count"]
    assert audit["is_cleaning_valid"] is True

    # Non-sentinel values in raw must remain identical in cleaned DataFrame
    non_sentinel_mask = synthetic_raw_dataset["DAYS_EMPLOYED"] != SENTINEL_DAYS_EMPLOYED
    raw_valid = synthetic_raw_dataset.loc[non_sentinel_mask, "DAYS_EMPLOYED"].values
    clean_valid = synthetic_clean_dataset.loc[non_sentinel_mask, "DAYS_EMPLOYED"].values
    np.testing.assert_array_equal(raw_valid, clean_valid)


def test_no_input_dataframe_mutation(synthetic_clean_dataset: pd.DataFrame) -> None:
    """Ensure calculation functions do not mutate or modify the input DataFrame."""
    original_copy = synthetic_clean_dataset.copy(deep=True)

    _ = compute_target_distribution(synthetic_clean_dataset)
    _ = compute_income_summary(synthetic_clean_dataset)
    _ = compute_age_group_summary(synthetic_clean_dataset)
    _ = compute_categorical_default_rate(synthetic_clean_dataset, "OCCUPATION_TYPE")
    _ = compute_spearman_correlation(synthetic_clean_dataset)

    pd.testing.assert_frame_equal(synthetic_clean_dataset, original_copy)


# ---------------------------------------------------------------------------
# 3. Figure Generation Tests
# ---------------------------------------------------------------------------


def test_figure_generation_all_five(
    synthetic_clean_dataset: pd.DataFrame,
    synthetic_raw_dataset: pd.DataFrame,
    tmp_path: Path,
) -> None:
    """Generate all five canonical figures in a temporary directory and verify output files."""
    fig_dir = tmp_path / "figures"
    fig_paths = generate_all_eda_figures(synthetic_clean_dataset, synthetic_raw_dataset, fig_dir)

    assert len(fig_paths) == 5
    assert set(fig_paths.keys()) == set(FIGURE_FILENAMES)

    for fname, p in fig_paths.items():
        assert p.is_file(), f"Missing figure file: {fname}"
        assert p.stat().st_size > 5000, f"Figure {fname} is unexpectedly small ({p.stat().st_size} bytes)"


# ---------------------------------------------------------------------------
# 4. Report Rendering & Atomic Writing Tests
# ---------------------------------------------------------------------------


def test_render_and_write_eda_report(
    synthetic_clean_dataset: pd.DataFrame,
    synthetic_raw_dataset: pd.DataFrame,
    tmp_path: Path,
) -> None:
    """Render and write EDA report atomically, then verify section headings and contents."""
    target_dist = compute_target_distribution(synthetic_clean_dataset)
    inc_summary = compute_income_summary(synthetic_clean_dataset)
    age_agg = compute_age_group_summary(synthetic_clean_dataset)
    occ_agg = compute_categorical_default_rate(synthetic_clean_dataset, "OCCUPATION_TYPE")
    contract_agg = compute_categorical_default_rate(synthetic_clean_dataset, "NAME_CONTRACT_TYPE")
    spearman_corr = compute_spearman_correlation(synthetic_clean_dataset)
    sentinel_audit = compute_days_employed_audit(synthetic_raw_dataset, synthetic_clean_dataset)

    bundle = {
        "dataset_shape": synthetic_clean_dataset.shape,
        "target_distribution": target_dist,
        "income_summary": inc_summary,
        "age_group_summary": age_agg,
        "occupation_summary": occ_agg,
        "contract_summary": contract_agg,
        "spearman_correlation": spearman_corr,
        "sentinel_audit": sentinel_audit,
        "dataset_sha256": "mock_dataset_sha256",
        "manifest_sha256": "mock_manifest_sha256",
        "dictionary_sha256": "mock_dictionary_sha256",
    }

    report_text = render_eda_report(bundle)
    assert "# Canonical Exploratory Data Analysis (EDA) Report" in report_text
    assert "## 1. Scope and Data Source" in report_text
    assert "## 2. Canonical Dataset Invariance and Shape" in report_text
    assert "## 3. TARGET Distribution and Class Imbalance" in report_text
    assert "## 5. Detailed Visualizations and Empirical Findings" in report_text
    assert "## 7. Limitations and Non-Causality Statement" in report_text
    assert "## 10. Handoff Readiness Status" in report_text

    # Write atomically
    out_file = tmp_path / "eda_report.md"
    written_path = write_eda_report_atomic(report_text, out_file)
    assert written_path.is_file()
    assert written_path.stat().st_size > 1000

    # Verify LF line endings
    raw_bytes = written_path.read_bytes()
    assert b"\r\n" not in raw_bytes, "Found CRLF line endings in eda_report.md"


# ---------------------------------------------------------------------------
# 5. CLI & Pipeline Orchestration Tests
# ---------------------------------------------------------------------------


def test_run_eda_pipeline_temp_environment(
    synthetic_clean_dataset: pd.DataFrame,
    synthetic_raw_dataset: pd.DataFrame,
    tmp_path: Path,
) -> None:
    """Execute run_eda_pipeline with temporary input and output paths."""
    ds_path = tmp_path / "cleaned_dataset.parquet"
    synthetic_clean_dataset.to_parquet(ds_path)

    raw_path = tmp_path / "application_train.csv"
    synthetic_raw_dataset.to_csv(raw_path, index=False)

    fig_dir = tmp_path / "figures"
    rep_path = tmp_path / "eda_report.md"

    res = run_eda_pipeline(
        dataset_path=ds_path,
        raw_train_path=raw_path,
        figures_dir=fig_dir,
        report_path=rep_path,
    )

    assert res["status"] == "PASS"
    assert res["figures_generated"] == 5
    assert rep_path.is_file()
    for fname in FIGURE_FILENAMES:
        assert (fig_dir / fname).is_file()


def test_run_eda_pipeline_missing_file_fails(tmp_path: Path) -> None:
    """Fail clearly when required canonical dataset does not exist."""
    non_existent = tmp_path / "does_not_exist.parquet"
    with pytest.raises(FileNotFoundError, match="Canonical dataset not found"):
        run_eda_pipeline(dataset_path=non_existent)
