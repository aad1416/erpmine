"""Deterministic pandas Transforms for `analyze` (map decision D10, ticket 05):
`pivot`, `top_n`, `period_trend`, `bucket`. SQL does all filtering, joining and
aggregation (including running totals); Transforms only reshape or derive, and run
on the *full* stored rows, never the <=30-row preview.

One Pydantic params model per transform, carrying a `transform` discriminator so the
`analyze` tool's schema documents every parameter. `run(df, params)` is pure and never
raises for a bad column/type — it returns an "Error: ..." string instead, same
convention as the rest of the tool surface.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class TransformResult(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Params models
# ---------------------------------------------------------------------------


class PivotParams(BaseModel):
    transform: Literal["pivot"] = "pivot"
    index_col: str
    columns_col: str
    value_col: str
    fill: Optional[float] = 0


class TopNParams(BaseModel):
    transform: Literal["top_n"] = "top_n"
    label_col: str
    value_col: str
    n: int = 10
    other: bool = True
    ascending: bool = False


class PeriodTrendParams(BaseModel):
    transform: Literal["period_trend"] = "period_trend"
    entity_col: str
    period_col: str
    value_col: str
    fill_missing: float = 0
    flat_threshold_pct: float = 5
    direction: Optional[Literal["up", "flat", "down"]] = None


BucketPreset = Literal["days_late", "age_days"]

_PRESET_EDGES: Dict[str, List[float]] = {
    "days_late": [0, 7, 30],
    "age_days": [90, 180, 365],
}


class BucketParams(BaseModel):
    transform: Literal["bucket"] = "bucket"
    value_col: str
    edges: Optional[List[float]] = None
    preset: Optional[BucketPreset] = None
    labels: Optional[List[str]] = None
    sum_col: Optional[str] = None
    group_by: Optional[str] = None


AnalyzeParams = Annotated[
    Union[PivotParams, TopNParams, PeriodTrendParams, BucketParams],
    Field(discriminator="transform"),
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _missing_columns(df: pd.DataFrame, *cols: Optional[str]) -> List[str]:
    return [c for c in cols if c and c not in df.columns]


def _unknown_column_error(missing: List[str]) -> str:
    names = ", ".join(repr(c) for c in missing)
    return f"Error: unknown column(s): {names}."


def _numeric_or_error(df: pd.DataFrame, col: str) -> Union[pd.Series, str]:
    series = df[col]
    coerced = pd.to_numeric(series, errors="coerce")
    if (series.notna() & coerced.isna()).any():
        return f"Error: '{col}' is not numeric."
    return coerced


def _native(value: Any) -> Any:
    """Rows must be JSON-safe python primitives (D5); pandas/numpy scalars aren't."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    return [{k: _native(v) for k, v in rec.items()} for rec in df.to_dict(orient="records")]


def _round1(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(float(value), 1)


# ---------------------------------------------------------------------------
# pivot
# ---------------------------------------------------------------------------


def _run_pivot(df: pd.DataFrame, params: PivotParams) -> Union[TransformResult, str]:
    missing = _missing_columns(df, params.index_col, params.columns_col, params.value_col)
    if missing:
        return _unknown_column_error(missing)

    numeric = _numeric_or_error(df, params.value_col)
    if isinstance(numeric, str):
        return numeric

    work = df[[params.index_col, params.columns_col]].copy()
    work["_value"] = numeric

    pivoted = pd.pivot_table(
        work,
        index=params.index_col,
        columns=params.columns_col,
        values="_value",
        aggfunc="sum",
        fill_value=params.fill,
        dropna=False,
    )
    filled_cells = 0
    if params.fill is not None:
        # cells with no source (index, key) row were filled by pivot_table's fill_value;
        # count them before the reset_index below flattens the frame.
        counts = pd.pivot_table(
            work,
            index=params.index_col,
            columns=params.columns_col,
            values="_value",
            aggfunc="count",
            fill_value=0,
            dropna=False,
        )
        filled_cells = int((counts == 0).sum().sum())

    pivoted.columns = [str(c) for c in pivoted.columns]
    result_df = pivoted.reset_index()

    notes: List[str] = []
    if filled_cells:
        fill_label = "null" if params.fill is None else params.fill
        notes.append(
            f"{filled_cells} (index, key) cell(s) had no source row -> filled with {fill_label}"
        )

    return TransformResult(columns=list(result_df.columns), rows=_records(result_df), notes=notes)


# ---------------------------------------------------------------------------
# top_n
# ---------------------------------------------------------------------------


def _run_top_n(df: pd.DataFrame, params: TopNParams) -> Union[TransformResult, str]:
    missing = _missing_columns(df, params.label_col, params.value_col)
    if missing:
        return _unknown_column_error(missing)

    numeric = _numeric_or_error(df, params.value_col)
    if isinstance(numeric, str):
        return numeric

    work = df[[params.label_col]].copy()
    work["_value"] = numeric
    sorted_work = work.sort_values("_value", ascending=params.ascending, kind="stable").reset_index(
        drop=True
    )
    total = float(sorted_work["_value"].sum())

    head = sorted_work.iloc[: params.n]
    tail = sorted_work.iloc[params.n :]

    rows: List[Dict[str, Any]] = []
    for rank, (_, r) in enumerate(head.iterrows(), start=1):
        value = float(r["_value"])
        rows.append(
            {
                "rank": rank,
                params.label_col: r[params.label_col],
                params.value_col: value,
                "share_pct": _round1(value / total * 100) if total else None,
            }
        )

    notes: List[str] = []
    if len(tail) > 0:
        if params.other:
            other_value = float(tail["_value"].sum())
            rows.append(
                {
                    "rank": None,
                    params.label_col: f"Other ({len(tail)})",
                    params.value_col: other_value,
                    "share_pct": _round1(other_value / total * 100) if total else None,
                }
            )
            notes.append(f"{len(tail)} row(s) rolled into Other")
        else:
            notes.append(f"{len(tail)} row(s) dropped (other=false)")

    if df[params.label_col].isna().any() or (df[params.label_col] == "").any():
        notes.append(f"blank {params.label_col} values present - reported as-is, no normalisation")

    columns = ["rank", params.label_col, params.value_col, "share_pct"]
    result_df = pd.DataFrame(rows, columns=columns)
    return TransformResult(columns=columns, rows=_records(result_df), notes=notes)


# ---------------------------------------------------------------------------
# period_trend
# ---------------------------------------------------------------------------


def _classify_direction(
    change_pct: Optional[float], change_abs: float, flat_threshold_pct: float
) -> str:
    if change_pct is None:
        if change_abs == 0:
            return "flat"
        return "up" if change_abs > 0 else "down"
    if abs(change_pct) <= flat_threshold_pct:
        return "flat"
    return "up" if change_pct > 0 else "down"


def _run_period_trend(df: pd.DataFrame, params: PeriodTrendParams) -> Union[TransformResult, str]:
    missing = _missing_columns(df, params.entity_col, params.period_col, params.value_col)
    if missing:
        return _unknown_column_error(missing)

    numeric = _numeric_or_error(df, params.value_col)
    if isinstance(numeric, str):
        return numeric

    work = df[[params.entity_col, params.period_col]].copy()
    work["_value"] = numeric

    pivoted = pd.pivot_table(
        work,
        index=params.entity_col,
        columns=params.period_col,
        values="_value",
        aggfunc="sum",
        fill_value=params.fill_missing,
        dropna=False,
    )
    period_cols = list(pivoted.columns)
    if len(period_cols) < 2:
        return f"Error: period_trend needs at least 2 distinct '{params.period_col}' values."

    period_col_labels = [str(c) for c in period_cols]

    rows: List[Dict[str, Any]] = []
    for entity, series in pivoted.iterrows():
        values = [float(series[c]) for c in period_cols]
        first_value, last_value = values[0], values[-1]
        change_abs = last_value - first_value
        change_pct = None if first_value == 0 else (change_abs / first_value * 100)

        down_periods = 0
        max_consecutive = 0
        current = 0
        for i in range(1, len(values)):
            if values[i] < values[i - 1]:
                down_periods += 1
                current += 1
                max_consecutive = max(max_consecutive, current)
            else:
                current = 0

        direction = _classify_direction(change_pct, change_abs, params.flat_threshold_pct)

        row: Dict[str, Any] = {params.entity_col: entity}
        row.update(dict(zip(period_col_labels, values)))
        row.update(
            {
                "first_value": first_value,
                "last_value": last_value,
                "change_abs": change_abs,
                "change_pct": _round1(change_pct),
                "down_periods": down_periods,
                "max_consecutive_down": max_consecutive,
                "direction": direction,
            }
        )
        rows.append(row)

    if params.direction is not None:
        rows = [r for r in rows if r["direction"] == params.direction]

    rows.sort(
        key=lambda r: (
            r["change_pct"] is None,
            r["change_pct"] if r["change_pct"] is not None else 0.0,
            r[params.entity_col],
        )
    )

    columns = (
        [params.entity_col]
        + period_col_labels
        + [
            "first_value",
            "last_value",
            "change_abs",
            "change_pct",
            "down_periods",
            "max_consecutive_down",
            "direction",
        ]
    )
    result_df = pd.DataFrame(rows, columns=columns)
    return TransformResult(columns=columns, rows=_records(result_df), notes=[])


# ---------------------------------------------------------------------------
# bucket
# ---------------------------------------------------------------------------


def _fmt_edge(edge: float) -> str:
    return str(int(edge)) if float(edge).is_integer() else str(edge)


def _bucket_labels(edges: List[float]) -> List[str]:
    labels = [f"≤ {_fmt_edge(edges[0])}"]
    for i in range(1, len(edges)):
        labels.append(f"{_fmt_edge(edges[i - 1] + 1)}–{_fmt_edge(edges[i])}")
    labels.append(f"> {_fmt_edge(edges[-1])}")
    return labels


def _run_bucket(df: pd.DataFrame, params: BucketParams) -> Union[TransformResult, str]:
    missing = _missing_columns(df, params.value_col, params.sum_col, params.group_by)
    if missing:
        return _unknown_column_error(missing)

    edges = params.edges if params.edges is not None else _PRESET_EDGES.get(params.preset or "")
    if edges is None:
        return "Error: bucket needs 'edges' or a known 'preset' (days_late, age_days)."
    edges = sorted(float(e) for e in edges)

    numeric = _numeric_or_error(df, params.value_col)
    if isinstance(numeric, str):
        return numeric

    labels = params.labels if params.labels else _bucket_labels(edges)
    if len(labels) != len(edges) + 1:
        return f"Error: 'labels' must have {len(edges) + 1} entries for {len(edges)} edges."

    sum_series: Optional[pd.Series] = None
    if params.sum_col:
        sum_numeric = _numeric_or_error(df, params.sum_col)
        if isinstance(sum_numeric, str):
            return sum_numeric
        sum_series = sum_numeric

    bins = [float("-inf")] + edges + [float("inf")]
    cut = pd.cut(numeric, bins=bins, right=True, labels=labels, ordered=True)

    has_null = numeric.isna().any()
    all_labels: List[str] = list(labels) + (["Unknown"] if has_null else [])

    work = pd.DataFrame(index=df.index)
    work["bucket"] = cut.astype(object)
    work.loc[numeric.isna(), "bucket"] = "Unknown"
    if sum_series is not None:
        work["_sum"] = sum_series
    if params.group_by:
        work[params.group_by] = df[params.group_by]

    notes: List[str] = []
    if has_null:
        null_count = int(numeric.isna().sum())
        notes.append(f"{null_count} row(s) had null {params.value_col} -> Unknown")

    if params.group_by:
        unique_groups = [g for g in work[params.group_by].unique().tolist() if pd.notna(g)]
        try:
            groups: List[Any] = sorted(unique_groups)
        except TypeError:
            groups = sorted(unique_groups, key=str)
    else:
        groups = [None]

    rows: List[Dict[str, Any]] = []
    for group in groups:
        subset = work if group is None else work[work[params.group_by] == group]
        total = len(subset)
        for label in all_labels:
            in_bucket = subset[subset["bucket"] == label]
            count = len(in_bucket)
            row: Dict[str, Any] = {}
            if params.group_by:
                row[params.group_by] = group
            row["bucket"] = label
            row["count"] = count
            row["pct"] = _round1(count / total * 100) if total else None
            if sum_series is not None:
                row[f"sum_{params.sum_col}"] = float(in_bucket["_sum"].sum())
            rows.append(row)

    columns = (([params.group_by] if params.group_by else [])) + ["bucket", "count", "pct"]
    if params.sum_col:
        columns.append(f"sum_{params.sum_col}")

    result_df = pd.DataFrame(rows, columns=columns)
    return TransformResult(columns=columns, rows=_records(result_df), notes=notes)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TRANSFORMS = {
    "pivot": _run_pivot,
    "top_n": _run_top_n,
    "period_trend": _run_period_trend,
    "bucket": _run_bucket,
}


def run(df: pd.DataFrame, params: AnalyzeParams) -> Union[TransformResult, str]:
    """Dispatch to the transform named by `params.transform`. Pure; returns an
    "Error: ..." string instead of raising for a bad column or non-numeric value."""
    handler = TRANSFORMS[params.transform]
    return handler(df, params)
