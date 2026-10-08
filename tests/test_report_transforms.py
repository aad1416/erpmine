"""Pure-function tests for the four report Transforms (map decision D10, ticket 05):
pivot, top_n, period_trend, bucket. Fixture DataFrames cover all 7 client examples'
transform steps (prior art: tests/test_column_typing.py) plus the edge cases the
ticket calls out: empty buckets kept, unknown column, non-numeric value column.

`run(df, params)` never raises for a bad column/type; it returns an "Error: ..."
string instead (checked directly rather than via the `analyze` tool)."""

import pandas as pd
import pytest

from app.utils.report_transforms import (
    BucketParams,
    PeriodTrendParams,
    PivotParams,
    TopNParams,
    run,
)


# ---------------------------------------------------------------------------
# Example 3 — monthly sales over two years: SQL (month, year, total) -> pivot
# ---------------------------------------------------------------------------


def test_pivot_monthly_sales_by_month_and_year():
    df = pd.DataFrame(
        [
            {"month": 1, "year": 2024, "total": 100},
            {"month": 1, "year": 2024, "total": 50},  # duplicate (index, key) pair
            {"month": 1, "year": 2025, "total": 120},
            {"month": 2, "year": 2024, "total": 80},
            {"month": 2, "year": 2025, "total": 90},
            {"month": 3, "year": 2024, "total": 200},  # no month=3/year=2025 row
        ]
    )
    result = run(df, PivotParams(index_col="month", columns_col="year", value_col="total"))

    assert result.columns == ["month", "2024", "2025"]
    assert result.rows == [
        {"month": 1, "2024": 150.0, "2025": 120.0},
        {"month": 2, "2024": 80.0, "2025": 90.0},
        {"month": 3, "2024": 200.0, "2025": 0.0},
    ]
    assert "1 (index, key) cell(s)" in result.notes[0]


def test_pivot_no_totals_column_or_row():
    df = pd.DataFrame([{"a": "x", "b": "p", "v": 1}, {"a": "y", "b": "q", "v": 2}])
    result = run(df, PivotParams(index_col="a", columns_col="b", value_col="v"))
    assert "total" not in [c.lower() for c in result.columns]
    assert {r["a"] for r in result.rows} == {"x", "y"}


def test_pivot_fill_none_leaves_missing_cells_null():
    df = pd.DataFrame([{"a": "x", "b": "p", "v": 1}, {"a": "y", "b": "q", "v": 2}])
    result = run(df, PivotParams(index_col="a", columns_col="b", value_col="v", fill=None))
    by_a = {r["a"]: r for r in result.rows}
    assert by_a["x"]["q"] is None
    assert by_a["y"]["p"] is None


# ---------------------------------------------------------------------------
# Example 4 — declining customers over five years:
# SQL (client, year, revenue) -> period_trend(direction='down') -> top_n
# ---------------------------------------------------------------------------


def _example_4_rows():
    return pd.DataFrame(
        [
            {"client": "Acme", "year": 2021, "revenue": 500},
            {"client": "Acme", "year": 2022, "revenue": 400},
            {"client": "Acme", "year": 2023, "revenue": 300},
            {"client": "Acme", "year": 2024, "revenue": 200},
            {"client": "Acme", "year": 2025, "revenue": 100},
            {"client": "Globex", "year": 2021, "revenue": 100},
            {"client": "Globex", "year": 2022, "revenue": 120},
            {"client": "Globex", "year": 2023, "revenue": 150},
            {"client": "Globex", "year": 2024, "revenue": 180},
            {"client": "Globex", "year": 2025, "revenue": 200},
            {"client": "Initech", "year": 2021, "revenue": 300},
            {"client": "Initech", "year": 2025, "revenue": 305},  # ~flat
        ]
    )


def test_period_trend_computes_change_and_direction():
    result = run(
        _example_4_rows(),
        PeriodTrendParams(entity_col="client", period_col="year", value_col="revenue"),
    )
    by_client = {r["client"]: r for r in result.rows}

    acme = by_client["Acme"]
    assert acme["first_value"] == 500.0
    assert acme["last_value"] == 100.0
    assert acme["change_abs"] == -400.0
    assert acme["change_pct"] == -80.0
    assert acme["down_periods"] == 4
    assert acme["max_consecutive_down"] == 4
    assert acme["direction"] == "down"

    globex = by_client["Globex"]
    assert globex["direction"] == "up"
    assert globex["down_periods"] == 0

    initech = by_client["Initech"]
    assert initech["direction"] == "flat"

    # sorted change_pct ascending (most negative first)
    assert [r["client"] for r in result.rows] == ["Acme", "Initech", "Globex"]


def test_period_trend_direction_filter_keeps_only_matching_entities():
    result = run(
        _example_4_rows(),
        PeriodTrendParams(
            entity_col="client", period_col="year", value_col="revenue", direction="down"
        ),
    )
    assert [r["client"] for r in result.rows] == ["Acme"]


def test_period_trend_then_top_n_declining_customers():
    trend = run(
        _example_4_rows(),
        PeriodTrendParams(
            entity_col="client", period_col="year", value_col="revenue", direction="down"
        ),
    )
    trend_df = pd.DataFrame(trend.rows, columns=trend.columns)

    top = run(
        trend_df,
        TopNParams(label_col="client", value_col="change_pct", n=1, other=False, ascending=True),
    )
    assert top.rows[0]["client"] == "Acme"
    assert top.rows[0]["change_pct"] == -80.0  # value_col copied verbatim, not re-derived


def test_period_trend_errors_with_fewer_than_two_periods():
    df = pd.DataFrame([{"client": "Acme", "year": 2024, "revenue": 100}])
    result = run(df, PeriodTrendParams(entity_col="client", period_col="year", value_col="revenue"))
    assert isinstance(result, str) and result.startswith("Error:")


# ---------------------------------------------------------------------------
# Example 5 — top vendors: top_n
# ---------------------------------------------------------------------------


def test_top_n_vendors_with_other_rollup():
    df = pd.DataFrame(
        [
            {"vendor": "V1", "total": 500},
            {"vendor": "V2", "total": 400},
            {"vendor": "V3", "total": 300},
            {"vendor": "V4", "total": 200},
            {"vendor": "V5", "total": 100},
        ]
    )
    result = run(df, TopNParams(label_col="vendor", value_col="total", n=3))

    assert result.columns == ["rank", "vendor", "total", "share_pct"]
    ranked = [r["vendor"] for r in result.rows]
    assert ranked == ["V1", "V2", "V3", "Other (2)"]

    other = result.rows[-1]
    assert other["rank"] is None
    assert other["total"] == 300.0  # 200 + 100
    assert other["share_pct"] == pytest.approx(20.0)
    assert "rolled into Other" in result.notes[0]

    top1 = result.rows[0]
    assert top1["rank"] == 1
    assert top1["share_pct"] == pytest.approx(500 / 1500 * 100, abs=0.1)


def test_top_n_other_false_drops_remainder():
    df = pd.DataFrame([{"vendor": f"V{i}", "total": i} for i in range(1, 6)])
    result = run(df, TopNParams(label_col="vendor", value_col="total", n=2, other=False))
    assert [r["vendor"] for r in result.rows] == ["V5", "V4"]
    assert "dropped (other=false)" in result.notes[0]


def test_top_n_ascending_is_bottom_n():
    df = pd.DataFrame([{"vendor": f"V{i}", "total": i} for i in range(1, 6)])
    result = run(
        df, TopNParams(label_col="vendor", value_col="total", n=2, other=False, ascending=True)
    )
    assert [r["vendor"] for r in result.rows] == ["V1", "V2"]


def test_top_n_notes_blank_label_values():
    df = pd.DataFrame(
        [{"vendor": "V1", "total": 10}, {"vendor": None, "total": 5}, {"vendor": "", "total": 1}]
    )
    result = run(df, TopNParams(label_col="vendor", value_col="total", n=10, other=False))
    assert any("blank vendor values" in note for note in result.notes)


# ---------------------------------------------------------------------------
# Example 6 — vendor lead time: SQL per PO with days_late -> bucket(preset='days_late',
# group_by=vendor) -> pivot
# ---------------------------------------------------------------------------


def test_bucket_days_late_grouped_then_pivot():
    df = pd.DataFrame(
        [
            {"vendor": "V1", "days_late": -2},
            {"vendor": "V1", "days_late": 5},
            {"vendor": "V1", "days_late": 5},
            {"vendor": "V1", "days_late": 40},
            {"vendor": "V2", "days_late": 0},
            {"vendor": "V2", "days_late": 0},
        ]
    )
    bucketed = run(df, BucketParams(value_col="days_late", preset="days_late", group_by="vendor"))

    assert bucketed.columns == ["vendor", "bucket", "count", "pct"]
    # long output: one row per (vendor, bucket)
    v1_rows = {r["bucket"]: r for r in bucketed.rows if r["vendor"] == "V1"}
    assert v1_rows["≤ 0"]["count"] == 1  # -2
    assert v1_rows["1–7"]["count"] == 2  # 5, 5
    assert v1_rows["8–30"]["count"] == 0  # empty bucket kept
    assert v1_rows["> 30"]["count"] == 1  # 40
    assert v1_rows["1–7"]["pct"] == pytest.approx(50.0)

    v2_rows = {r["bucket"]: r for r in bucketed.rows if r["vendor"] == "V2"}
    assert v2_rows["≤ 0"]["count"] == 2
    assert v2_rows["1–7"]["count"] == 0  # empty bucket kept for V2 too

    bucketed_df = pd.DataFrame(bucketed.rows, columns=bucketed.columns)
    pivoted = run(
        bucketed_df, PivotParams(index_col="vendor", columns_col="bucket", value_col="count")
    )
    by_vendor = {r["vendor"]: r for r in pivoted.rows}
    assert by_vendor["V1"]["≤ 0"] == 1.0
    assert by_vendor["V1"]["1–7"] == 2.0
    assert by_vendor["V2"]["≤ 0"] == 2.0


# ---------------------------------------------------------------------------
# Example 7 — slow-moving inventory: SQL per item with age_days -> bucket(preset=
# 'age_days', sum_col=value)
# ---------------------------------------------------------------------------


def test_bucket_age_days_with_sum_col():
    df = pd.DataFrame(
        [
            {"sku": "A", "age_days": 50, "value": 10.0},
            {"sku": "B", "age_days": 100, "value": 20.0},
            {"sku": "C", "age_days": 200, "value": 30.0},
            {"sku": "D", "age_days": 400, "value": 40.0},
            {"sku": "E", "age_days": None, "value": 5.0},
        ]
    )
    result = run(df, BucketParams(value_col="age_days", preset="age_days", sum_col="value"))

    assert result.columns == ["bucket", "count", "pct", "sum_value"]
    by_bucket = {r["bucket"]: r for r in result.rows}
    assert by_bucket["≤ 90"]["count"] == 1
    assert by_bucket["≤ 90"]["sum_value"] == 10.0
    assert by_bucket["91–180"]["count"] == 1
    assert by_bucket["181–365"]["count"] == 1
    assert by_bucket["> 365"]["count"] == 1
    assert by_bucket["Unknown"]["count"] == 1
    assert by_bucket["Unknown"]["sum_value"] == 5.0
    assert any("null age_days" in note for note in result.notes)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_bucket_empty_bucket_kept_when_ungrouped():
    df = pd.DataFrame([{"v": -5}, {"v": 40}])  # nothing lands in the middle buckets
    result = run(df, BucketParams(value_col="v", preset="days_late"))
    by_bucket = {r["bucket"]: r["count"] for r in result.rows}
    assert by_bucket["1–7"] == 0
    assert by_bucket["8–30"] == 0
    assert len(result.rows) == 4  # all 4 buckets present even though 2 are empty


@pytest.mark.parametrize(
    "params",
    [
        PivotParams(index_col="missing", columns_col="b", value_col="v"),
        TopNParams(label_col="missing", value_col="v"),
        PeriodTrendParams(entity_col="missing", period_col="p", value_col="v"),
        BucketParams(value_col="missing", preset="days_late"),
    ],
)
def test_unknown_column_returns_error_string(params):
    df = pd.DataFrame([{"a": 1, "b": "x", "v": 1, "p": 1}])
    result = run(df, params)
    assert isinstance(result, str)
    assert result.startswith("Error:")
    assert "unknown column" in result


@pytest.mark.parametrize(
    "params",
    [
        PivotParams(index_col="a", columns_col="b", value_col="text"),
        TopNParams(label_col="a", value_col="text"),
        PeriodTrendParams(entity_col="a", period_col="p", value_col="text"),
        BucketParams(value_col="text", preset="days_late"),
    ],
)
def test_non_numeric_value_column_returns_error_string(params):
    df = pd.DataFrame(
        [
            {"a": "x", "b": "p", "p": 1, "text": "not-a-number"},
            {"a": "y", "b": "q", "p": 2, "text": "also-not-a-number"},
        ]
    )
    result = run(df, params)
    assert isinstance(result, str)
    assert result.startswith("Error:")
    assert "not numeric" in result


def test_bucket_requires_edges_or_preset():
    df = pd.DataFrame([{"v": 1}])
    result = run(df, BucketParams(value_col="v"))
    assert result == "Error: bucket needs 'edges' or a known 'preset' (days_late, age_days)."


def test_bucket_explicit_edges_win_over_preset():
    df = pd.DataFrame([{"v": 15}])
    result = run(df, BucketParams(value_col="v", edges=[10, 20], preset="days_late"))
    assert result.columns == ["bucket", "count", "pct"]
    assert [r["bucket"] for r in result.rows] == ["≤ 10", "11–20", "> 20"]
