"""Column-type inference shared by `create_table` and (later) `export_excel`, so a
column formats identically inline and in an Export (map decision, ticket 07/06)."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Iterable, Literal, Optional

ColumnType = Literal["string", "number", "currency", "date"]

_DATE_RE = re.compile(r"date", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"total|value|spend|amount|cost", re.IGNORECASE)
_PERCENT_RE = re.compile(r"(^|_)pct$", re.IGNORECASE)


def _is_numeric(values: Iterable[Any]) -> bool:
    """True if the first non-null sample value is numeric (bool doesn't count)."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return False
        return isinstance(value, (int, float, Decimal))
    return False


def infer_column_type(column: str, values: Iterable[Any]) -> ColumnType:
    """`date` for `*date*` columns; `currency` for numeric `total|value|spend|amount|cost`
    columns; `number` for other numeric columns; `string` otherwise."""
    if _DATE_RE.search(column):
        return "date"
    if _is_numeric(values):
        return "currency" if _CURRENCY_RE.search(column) else "number"
    return "string"


def humanize_column_label(column: str) -> str:
    """`shipping_address_state` -> `Shipping Address State`."""
    return " ".join(word.capitalize() for word in column.replace("_", " ").split())


def is_percent_column(column: str) -> bool:
    """Transform `_pct` columns (`share_pct`, `change_pct`, bucket's `pct`) are
    already scaled 0-100, not 0-1 fractions (ticket 05/06)."""
    return bool(_PERCENT_RE.search(column))


def _has_decimals(values: Iterable[Any]) -> bool:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, (float, Decimal)) and float(value) != int(value):
            return True
    return False


def excel_number_format(
    column: str, col_type: ColumnType, values: Iterable[Any]
) -> Optional[str]:
    """`openpyxl` `number_format` for a column, from its shared inferred type (D14).
    `_pct` columns get a plain number format, never Excel's native `%`, because
    they're already scaled 0-100 — applying `%` would multiply by 100 again."""
    if is_percent_column(column):
        return "#,##0.0"
    if col_type == "currency":
        return "$#,##0.00"
    if col_type == "date":
        return "yyyy-mm-dd"
    if col_type == "number":
        return "#,##0.00" if _has_decimals(values) else "#,##0"
    return None
