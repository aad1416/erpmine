"""Post-generation SQL store-id injection guard, plus the store-scoping
verification gate (ADR 0001).

Programmatically injects `alias.store_id = 'X'` filters into LLM-generated SQL
for every table that:
  - Has a store_id column (in STORE_ID_TABLES), AND
  - Is NOT accessed via a MGMT permission (mgmt_tables), AND
  - Does not already have a store_id filter for that alias.

This is a defence-in-depth layer: the SQL generation prompt already instructs the
LLM to add store_id filters, but this guard guarantees enforcement even when the
LLM omits them.

`inject_store_id_filters` has exactly one global insertion point per query, so it
cannot place a filter inside the correct CTE block on multi-CTE SQL — see ADR 0001
(`docs/adr/0001-verify-not-rewrite-store-scoping-on-cte-sql.md`). `verify_store_scoping`
below is the backstop: it splits the (already generated + injected) SQL into its
named CTE blocks and the final query, and refuses anything where a store-scoped
table is referenced in a block without its own filter inside that same block.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from app.utils.access_table_mapper import STORE_ID_TABLES

# SQL keywords that can appear as FROM/JOIN targets but aren't table names.
_SQL_KEYWORDS: frozenset[str] = frozenset({
    "select", "from", "where", "join", "on", "and", "or", "not", "null", "as",
    "inner", "left", "right", "outer", "full", "cross", "lateral",
    "with", "union", "all", "distinct", "exists",
    "case", "when", "then", "else", "end",
    "order", "by", "group", "having", "limit", "offset", "asc", "desc",
    "in", "is", "like", "ilike", "between", "true", "false",
    "now", "current_timestamp", "current_date", "epoch",
})


def _extract_table_aliases(sql: str) -> Dict[str, str]:
    """Extract {alias_lower: table_name_lower} from all FROM/JOIN clauses.

    The alias group excludes SQL keywords via a negative lookahead rather than
    matching-then-discarding them: an unaliased table immediately followed by
    another FROM/JOIN (e.g. `FROM agg JOIN vendors v ON ...`) would otherwise
    have its regex match consume the following JOIN keyword as a rejected
    "alias", which advances finditer's scan position past it and makes the
    next JOIN clause invisible to this function — silently dropping that
    table's store_id filter.
    """
    aliases: Dict[str, str] = {}
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?\"?([a-zA-Z_][a-zA-Z0-9_]*)\"?"
        r"(?:\s+(?:AS\s+)?(?!(?:FROM|JOIN|WHERE|ON|GROUP|ORDER|HAVING|LIMIT|UNION)\b)"
        r"([a-zA-Z_][a-zA-Z0-9_]*))?",
        re.IGNORECASE,
    )
    for m in pattern.finditer(sql):
        table_name = m.group(1)
        raw_alias = m.group(2)
        # Discard the matched "alias" if it's really a SQL keyword (e.g. ORDER, WHERE, ON)
        if raw_alias and raw_alias.lower() in _SQL_KEYWORDS:
            raw_alias = None
        alias = raw_alias or table_name
        tbl_lower = table_name.lower()
        alias_lower = alias.lower()
        if tbl_lower not in _SQL_KEYWORDS:
            aliases[alias_lower] = tbl_lower
    return aliases


def _has_store_id_filter(sql: str, alias: str) -> bool:
    """Return True if the SQL already contains a store_id filter for this alias."""
    pattern = re.compile(
        rf"\b{re.escape(alias)}\.store_id\s*=\s*",
        re.IGNORECASE,
    )
    return bool(pattern.search(sql))


def inject_store_id_filters(
    sql: str,
    store_id: str,
    mgmt_tables: Set[str],
) -> str:
    """Inject missing store_id filters into a generated SQL statement.

    Only modifies tables that:
      1. Have a store_id column (STORE_ID_TABLES).
      2. Are NOT in mgmt_tables (MGMT access = cross-store visibility).
      3. Do not already have a `alias.store_id = '...'` filter in the SQL.

    Returns the (possibly modified) SQL string unchanged if no injection is needed.
    """
    if not store_id or not sql.strip():
        return sql

    alias_map = _extract_table_aliases(sql)
    mgmt_lower = {t.lower() for t in mgmt_tables}

    conditions: list[str] = []
    for alias, table_name in alias_map.items():
        if table_name in STORE_ID_TABLES and table_name not in mgmt_lower:
            if not _has_store_id_filter(sql, alias):
                conditions.append(f"{alias}.store_id = '{store_id}'")

    if not conditions:
        return sql

    extra = " AND ".join(conditions)
    sql = sql.rstrip()
    trailing_semi = sql.endswith(";")
    if trailing_semi:
        sql = sql[:-1].rstrip()

    # Find natural injection point: before ORDER BY / GROUP BY / HAVING / LIMIT
    # so the filter lands inside the WHERE scope, not after sorting/grouping keywords.
    clause_pattern = re.compile(
        r"\b(ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT)\b",
        re.IGNORECASE,
    )
    clause_match = clause_pattern.search(sql)

    if re.search(r"\bWHERE\b", sql, re.IGNORECASE):
        # Append to existing WHERE conditions, before any sort/group/limit clauses.
        if clause_match:
            pos = clause_match.start()
            sql = sql[:pos].rstrip() + f" AND {extra} " + sql[pos:]
        else:
            sql = sql + f" AND {extra}"
    else:
        # No WHERE yet — insert one.
        if clause_match:
            pos = clause_match.start()
            sql = sql[:pos].rstrip() + f" WHERE {extra} " + sql[pos:]
        else:
            sql = sql + f" WHERE {extra}"

    if trailing_semi:
        sql = sql.rstrip() + ";"

    return sql


# --- Store-scoping verification gate (ADR 0001) --------------------------------

FINAL_QUERY_BLOCK = "final query"


def _skip_ws(sql: str, i: int) -> int:
    while i < len(sql) and sql[i].isspace():
        i += 1
    return i


def _read_identifier(sql: str, i: int) -> Tuple[str, int]:
    """Read a (possibly double-quoted) identifier starting at i."""
    if i < len(sql) and sql[i] == '"':
        end = sql.find('"', i + 1)
        if end == -1:
            return "", i
        return sql[i + 1:end], end + 1
    j = i
    while j < len(sql) and (sql[j].isalnum() or sql[j] == "_"):
        j += 1
    return sql[i:j], j


def _find_matching_paren(sql: str, open_idx: int) -> int:
    """Return the index of the ')' matching the '(' at open_idx.

    String-aware: parentheses inside single-quoted string literals (including
    doubled `''` escapes) don't affect depth. Mirrors the scanning technique
    `db_schema_markdown._mask_parenthesized` uses for identifier validation.
    """
    depth = 0
    in_single = False
    i = open_idx
    n = len(sql)
    while i < n:
        ch = sql[i]
        if in_single:
            if ch == "'" and i + 1 < n and sql[i + 1] == "'":
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
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n - 1  # unmatched: treat end of string as the close


def _split_sql_blocks(sql: str) -> List[Tuple[str, str]]:
    """Split SQL into its named CTE blocks plus the final query.

    Returns `[(block_name, block_sql), ...]` in source order. SQL that doesn't
    open with `WITH` comes back as a single `(FINAL_QUERY_BLOCK, sql)` block.
    """
    stripped = sql.strip()
    n = len(stripped)

    with_match = re.match(r"with\s+", stripped, re.IGNORECASE)
    if not with_match:
        return [(FINAL_QUERY_BLOCK, stripped)]

    i = with_match.end()
    recursive_match = re.match(r"recursive\s+", stripped[i:], re.IGNORECASE)
    if recursive_match:
        i += recursive_match.end()

    blocks: List[Tuple[str, str]] = []
    while True:
        i = _skip_ws(stripped, i)
        name, i = _read_identifier(stripped, i)
        if not name:
            break
        i = _skip_ws(stripped, i)

        # Optional column-alias list: name(col1, col2) AS (...)
        if i < n and stripped[i] == "(":
            close = _find_matching_paren(stripped, i)
            i = _skip_ws(stripped, close + 1)

        as_match = re.match(r"as\s*", stripped[i:], re.IGNORECASE)
        if as_match:
            i += as_match.end()
        i = _skip_ws(stripped, i)

        if i >= n or stripped[i] != "(":
            # Malformed / unexpected shape — bail out and let the rest of the
            # string be checked as the final query rather than mis-splitting it.
            break

        open_idx = i
        close_idx = _find_matching_paren(stripped, open_idx)
        blocks.append((name, stripped[open_idx + 1:close_idx]))
        i = _skip_ws(stripped, close_idx + 1)

        if i < n and stripped[i] == ",":
            i += 1
            continue
        break

    blocks.append((FINAL_QUERY_BLOCK, stripped[i:].strip()))
    return blocks


def extract_cte_names(sql: str) -> Set[str]:
    """Lowercased names of every CTE a `WITH` clause defines (empty for SQL that
    doesn't open with `WITH`). Shared with the column-whitelist validator
    (`db_schema_markdown.validate_sql_identifiers`) so a query's own CTE names —
    valid `FROM`/`JOIN` targets in its final SELECT and in later CTEs — aren't
    mistaken for hallucinated real-table references."""
    return {name.lower() for name, _ in _split_sql_blocks(sql) if name != FINAL_QUERY_BLOCK}


def _scoped_filter_present(block_sql: str, alias: str, store_id: str) -> bool:
    pattern = re.compile(
        rf"\b{re.escape(alias)}\.store_id\s*=\s*'{re.escape(store_id)}'",
        re.IGNORECASE,
    )
    return bool(pattern.search(block_sql))


def verify_store_scoping(
    sql: str,
    store_id: str,
    mgmt_tables: Optional[Set[str]] = None,
) -> List[str]:
    """Return one message per CTE/final-query block that reads a store-scoped
    table without filtering it by `store_id` inside that same block.

    Runs after generation and best-effort injection (`inject_store_id_filters`),
    which has only one global insertion point and so cannot correctly place a
    filter inside the right CTE on multi-CTE SQL (ADR 0001). This is the
    verify-don't-rewrite backstop: it never edits the SQL, it only refuses to
    run SQL it can't prove is filtered. Returns `[]` for compliant SQL,
    including single-block SQL and SQL touching only management/uncontrolled
    tables.
    """
    if not store_id or not sql.strip():
        return []

    mgmt_lower = {t.lower() for t in (mgmt_tables or set())}
    errors: List[str] = []

    for block_name, block_sql in _split_sql_blocks(sql):
        if not block_sql.strip():
            continue
        alias_map = _extract_table_aliases(block_sql)
        for alias, table_name in alias_map.items():
            if table_name not in STORE_ID_TABLES or table_name in mgmt_lower:
                continue
            if not _scoped_filter_present(block_sql, alias, store_id):
                errors.append(
                    f"block '{block_name}' reads '{table_name}' (as '{alias}') "
                    f"without its own {alias}.store_id = '{store_id}' filter in that block"
                )

    return errors
