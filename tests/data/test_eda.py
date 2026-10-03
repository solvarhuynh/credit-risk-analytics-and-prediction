import pandas as pd

from src.data.tv2_runner import (
    DTI_BAND_ORDER,
    EDA_02_DTI_Y_LABEL,
    EDA_FIGURE_NAMES,
    FICO_MIN_GROUP_COUNT,
    FICO_BAND_ORDER,
    HEATMAP_MIN_CELL_COUNT,
    aggregate_accepted_volume_metrics,
    aggregate_time_metrics,
    mask_sparse_fico_groups,
    mask_sparse_heatmap_cells,
    ordered_eda_categories,
    prepare_dti_boxplot_data,
)


def test_eda_categories_keep_logical_fico_and_dti_order() -> None:
    fico = ordered_eda_categories(pd.Series(["750+", "<650"]), FICO_BAND_ORDER)
    dti = ordered_eda_categories(pd.Series([">30", "<=10"]), DTI_BAND_ORDER)

    assert list(fico.categories) == list(FICO_BAND_ORDER)
    assert list(dti.categories) == list(DTI_BAND_ORDER)
    assert fico.ordered and dti.ordered


def test_dti_display_cap_does_not_mutate_source_values() -> None:
    source = pd.DataFrame({"dti": [5.0, 10.0, 20.0, 1000.0], "target": [0, 0, 1, 1]})
    original = source.copy(deep=True)

    plot_data, cap = prepare_dti_boxplot_data(source)

    assert source.equals(original)
    assert cap < 1000.0
    assert plot_data["dti"].max() == 1000.0


def test_heatmap_masks_cells_below_minimum_count() -> None:
    rates = pd.DataFrame([[0.1, 0.2], [0.3, 0.4]], index=["<650", "650-699"], columns=["<=10", "10-20"])
    counts = pd.DataFrame([[HEATMAP_MIN_CELL_COUNT, HEATMAP_MIN_CELL_COUNT - 1], [200, 300]], index=rates.index, columns=rates.columns)

    masked = mask_sparse_heatmap_cells(rates, counts)

    assert masked.loc["<650", "<=10"] == 0.1
    assert pd.isna(masked.loc["<650", "10-20"])


def test_fico_groups_below_minimum_count_are_na_but_category_is_kept() -> None:
    table = pd.DataFrame({
        "band": ["<650", "650-699", "700-749", "750+"],
        "count": [2, 820825, 417917, 106606],
        "default_rate": [0.0, 0.1, 0.2, 0.3],
    })

    masked = mask_sparse_fico_groups(table)

    assert masked["band"].tolist() == list(FICO_BAND_ORDER)
    assert bool(masked.loc[masked["band"].eq("<650"), "insufficient_sample"].iloc[0])
    assert pd.isna(masked.loc[masked["band"].eq("<650"), "display_rate"].iloc[0])
    assert masked.loc[masked["band"].eq("650-699"), "display_rate"].iloc[0] == 0.1
    assert FICO_MIN_GROUP_COUNT == 100


def test_dti_axis_semantics_are_percentage_points() -> None:
    assert EDA_02_DTI_Y_LABEL == "DTI (%)"


def test_accepted_volume_aggregation_uses_all_rows_without_target() -> None:
    frame = pd.DataFrame({
        "issue_d": ["Feb-2018", "Jan-2018", "Feb-2018", "Mar-2018", None],
    })

    result = aggregate_accepted_volume_metrics(frame)

    assert result["year_month"].tolist() == [
        pd.Timestamp("2018-01-01"),
        pd.Timestamp("2018-02-01"),
        pd.Timestamp("2018-03-01"),
    ]
    assert result["accepted_loan_count"].tolist() == [1, 2, 1]
    assert list(result.columns) == ["year_month", "accepted_loan_count"]
    assert "default_rate" not in result


def test_time_aggregation_is_chronological_and_deterministic() -> None:
    frame = pd.DataFrame({
        "issue_d": ["Feb-2020", "Jan-2020", "Feb-2020", "Mar-2020"],
        "target": [1, 0, 0, pd.NA],
    })

    result = aggregate_time_metrics(frame)

    assert result["year_month"].tolist() == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-01")]
    assert result["loan_count"].tolist() == [1, 2]
    assert result["default_count"].tolist() == [0, 1]


def test_de10_has_exactly_the_intended_five_figure_identifiers() -> None:
    assert EDA_FIGURE_NAMES == (
        "eda_01_loan_amount_distribution.png",
        "eda_02_dti_by_target.png",
        "eda_03_default_by_fico.png",
        "eda_04_fico_dti_heatmap.png",
        "eda_05_accepted_loan_volume_over_time.png",
    )
