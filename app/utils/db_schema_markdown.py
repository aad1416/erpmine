"""Parse Lyndom table-docs markdown into allowed table/column names for SQL validation."""

from __future__ import annotations

import re
from typing import Dict, Set

from app.utils.sql_store_guard import extract_cte_names

_TABLE_HEADER = re.compile(r"^#\s+`([^`]+)`\s*$")
_COLUMNS_SECTION = re.compile(r"^##\s+Columns\b", re.IGNORECASE)
_COLUMN_ROW = re.compile(r"^\|\s*([a-z_][a-z0-9_]*)\s*\|", re.IGNORECASE)
_SQL_KEYWORDS = frozenset(
    {
        "select", "from", "where", "join", "inner", "left", "right", "full",
        "outer", "on", "and", "or", "not", "null", "as", "asc", "desc",
        "order", "by", "group", "having", "limit", "offset", "distinct",
        "case", "when", "then", "else", "end", "between", "in", "is",
        "like", "ilike", "true", "false", "with", "union", "all",
        "exists", "cast", "coalesce", "sum", "count", "avg", "min", "max",
    }
)

# Tokens that can follow SQL FROM inside expressions (e.g. EXTRACT(EPOCH FROM NOW()))
_FROM_EXPRESSION_OPERANDS = frozenset(
    {
        "now", "current_timestamp", "current_date", "localtimestamp",
        "current_time", "timeofday", "epoch",
    }
)


def parse_allowed_schema(schema_markdown: str) -> Dict[str, Set[str]]:
    """
    Extract table → column names from docs/database/table-docs markdown.

    Reads table headers (# `table_name`) and the first column of each row under ## Columns.
    """
    allowed: Dict[str, Set[str]] = {}
    current_table: str | None = None
    in_column_table = False

    for line in schema_markdown.splitlines():
        table_match = _TABLE_HEADER.match(line.strip())
        if table_match:
            current_table = table_match.group(1)
            allowed[current_table] = set()
            in_column_table = False
            continue

        if current_table is None:
            continue

        if _COLUMNS_SECTION.match(line.strip()):
            in_column_table = False
            continue

        stripped = line.strip()
        if stripped.startswith("| Column"):
            in_column_table = True
            continue

        if not in_column_table:
            continue

        if stripped.startswith("|---") or stripped.startswith("| ---"):
            continue

        col_match = _COLUMN_ROW.match(stripped)
        if col_match:
            col_name = col_match.group(1)
            if col_name.lower() != "column":
                allowed[current_table].add(col_name)

    return allowed


def _resolve_table(name: str, allowed: Dict[str, Set[str]]) -> str | None:
    lower_map = {t.lower(): t for t in allowed}
    return lower_map.get(name.lower())


def _mask_parenthesized(sql: str) -> str:
    """Replace characters inside (...) with spaces so FROM/JOIN inside expressions are ignored."""
    result = list(sql)
    depth = 0
    in_single = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if in_single:
            if ch == "'" and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            if depth > 0:
                result[i] = " "
            i += 1
            continue
        if ch == ")":
            if depth > 0:
                result[i] = " "
                depth -= 1
            i += 1
            continue
        if depth > 0 and not ch.isspace():
            result[i] = " "
        i += 1
    return "".join(result)


def validate_sql_identifiers(sql: str, allowed: Dict[str, Set[str]]) -> None:
    """
    Reject SQL that references tables or qualified columns not present in parsed schema.

    Raises ValueError with a clear message when a hallucinated identifier is detected.
    """
    if not allowed:
        return

    cte_names = extract_cte_names(sql)
    sql_for_tables = _mask_parenthesized(sql)
    for match in re.finditer(
        r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)\b",
        sql_for_tables,
        re.IGNORECASE,
    ):
        table_ref = match.group(1)
        lower_ref = table_ref.lower()
        if lower_ref in _SQL_KEYWORDS or lower_ref in _FROM_EXPRESSION_OPERANDS or lower_ref in cte_names:
            continue
        if _resolve_table(table_ref, allowed) is None:
            known = ", ".join(sorted(allowed.keys())[:12])
            suffix = "…" if len(allowed) > 12 else ""
            raise ValueError(
                f"Unknown table '{table_ref}'. Use only tables documented in the "
                f"provided schemas (e.g. {known}{suffix})."
            )

    for match in re.finditer(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b", sql, re.IGNORECASE):
        table_ref, column_ref = match.group(1), match.group(2)
        if table_ref.lower() in _SQL_KEYWORDS or column_ref.lower() in _SQL_KEYWORDS:
            continue

        resolved_table = _resolve_table(table_ref, allowed)
        if resolved_table is None:
            continue

        columns = allowed[resolved_table]
        col_lower = {c.lower() for c in columns}
        if column_ref.lower() not in col_lower:
            similar = sorted(c for c in columns if column_ref.lower() in c.lower() or c.lower() in column_ref.lower())[:5]
            hint = f" Similar columns: {', '.join(similar)}." if similar else ""
            raise ValueError(
                f"Column '{table_ref}.{column_ref}' is not documented under `{resolved_table}` "
                f"in the ## Columns table.{hint} Map user phrases to existing column names — "
                f"do not invent identifiers from natural language."
            )
