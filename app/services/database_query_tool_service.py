"""Shared database-query behavior behind the query_database agent tool."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from app.config.setting import settings
from app.utils.access_table_mapper import (
    CONTROLLED_TABLES,
    get_accessible_tables,
    get_mgmt_tables,
)
from app.utils.db_schema_markdown import parse_allowed_schema, validate_sql_identifiers
from app.utils.sql_store_guard import inject_store_id_filters, verify_store_scoping

if TYPE_CHECKING:
    from app.repositories.lyndom_db import LyndomDBRepository
    from app.services.db_rag_query_service import DBRagQueryService
    from app.services.db_rag_retrieval_service import DBRagRetrievalService

logger = logging.getLogger(__name__)

# Fixed per the spec's limits table: a result larger than this is refused, never
# silently truncated, so an Export can never claim completeness it doesn't have.
MAX_EXECUTION_ROWS = 20_000

_SQL_KEYWORDS: frozenset[str] = frozenset({
    "select", "from", "where", "join", "on", "and", "or", "not", "null", "as",
    "inner", "left", "right", "outer", "full", "cross", "lateral",
    "with", "union", "all", "now", "current_timestamp", "current_date", "epoch",
})


def _extract_sql_tables(sql: str) -> Set[str]:
    """Return lowercase table names referenced in FROM / JOIN clauses.
    Properly extracts identifiers even if they are quoted or schema-prefixed.
    """
    tables: Set[str] = set()
    # Matches: FROM table, FROM "table", FROM schema.table, FROM schema."table"
    for m in re.finditer(
        r"\b(?:FROM|JOIN)\s+(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?\"?([a-zA-Z_][a-zA-Z0-9_]*)\"?\b",
        sql,
        re.IGNORECASE
    ):
        name = m.group(1).lower()
        if name not in _SQL_KEYWORDS:
            tables.add(name)
    return tables


def _rows_preview(rows: List[dict], max_rows: Optional[int]) -> List[dict]:
    if max_rows is not None and max_rows > 0:
        return rows[:max_rows]
    return rows


@dataclass
class DatabaseQueryResult:
    content: str
    audit: List[dict] = field(default_factory=list)


@dataclass
class ExecutedQuery:
    """One executed (or refused) SQL statement, with the *full* result rows.

    `intent` is `None` only for a tool-level failure that never reached the
    per-query pipeline (service disabled, no schema found, ...) — there is no
    SQL to report on. Every other record has a real intent, the post-guard
    `sql`, and either `rows` (full, on success) or `error` (never both).
    """

    intent: Optional[str]
    sql: str
    rows: Optional[List[dict]]
    error: Optional[str]
    audit: dict


def _top_level_error(message: str) -> ExecutedQuery:
    return ExecutedQuery(intent=None, sql="", rows=None, error=message, audit={})


class DatabaseQueryToolService:
    """
    Owns the Lyndom ERP query pipeline for agent tools: schema retrieval, SQL
    generation, access validation, store scoping, and execution. Context-agnostic
    and reusable across runners.
    """

    def __init__(
        self,
        db_rag_retrieval_service: Optional["DBRagRetrievalService"],
        db_rag_query_service: Optional["DBRagQueryService"],
        lyndom_repo: Optional["LyndomDBRepository"] = None,
    ):
        self.db_rag_retrieval_service = db_rag_retrieval_service
        self.db_rag_query_service = db_rag_query_service
        self.lyndom_repo = lyndom_repo

    async def query_structured(
        self,
        *,
        question: str,
        feature_id: int,
        store_id: Optional[str],
        user_accesses: List[str],
        sql: Optional[str] = None,
    ) -> List[ExecutedQuery]:
        """Generate (or accept a caller-supplied) SQL and execute it, guarded.

        Guard order, same for a generated query and a `sql=` re-run: column-
        whitelist validation -> access-table check -> store-filter injection ->
        execute. Never raises; every failure comes back as a record with
        `error` set.
        """
        if not settings.DB_RAG_ENABLED:
            return [_top_level_error("Database querying is disabled (DB_RAG_ENABLED=false).")]

        if not self.lyndom_repo:
            return [_top_level_error("Lyndom database is not configured; cannot execute queries.")]

        if not self.db_rag_retrieval_service or not self.db_rag_query_service:
            return [_top_level_error("DB RAG services are not available.")]

        trimmed = question.strip()
        if not trimmed:
            return [_top_level_error("Error: empty question.")]

        # Derive access control sets from the user's token accesses.
        accessible = get_accessible_tables(user_accesses)   # None = unrestricted
        mgmt_tables = get_mgmt_tables(user_accesses)

        try:
            # Layer 2 — schema retrieval filtered to accessible tables.
            schema_result = await self.db_rag_retrieval_service.get_relevant_schemas(
                user_message=trimmed,
                feature_id=feature_id,
                accessible_tables=accessible,
            )
            schema_md = schema_result.get("schema_markdown") or ""
            if not schema_md.strip():
                return [_top_level_error("No relevant schema was found for this question.")]

            raw_sql = sql.strip() if sql else ""
            if raw_sql:
                # `sql=` re-run: skip generation, but still run the same static
                # column-whitelist validation a generated query would get.
                candidates = [self._validate_raw_sql(raw_sql, trimmed, schema_md)]
            else:
                # Layer 1 — pass accessible tables + mgmt exceptions into the SQL-gen prompt.
                sql_gen_result = await self.db_rag_query_service.generate_queries(
                    user_message=trimmed,
                    schema_markdown=schema_md,
                    store_id=store_id,
                    selected_tables=schema_result.get("selected_tables", []),
                    accessible_tables=accessible,
                    mgmt_tables=mgmt_tables if mgmt_tables else None,
                )
                candidates = sql_gen_result.get("queries") or []

            return [
                self._execute_candidate(candidate, accessible, mgmt_tables, store_id)
                for candidate in candidates
            ]
        except Exception as exc:  # noqa: BLE001
            logger.exception("query_database failed")
            return [_top_level_error(f"Database tool failed: {exc}")]

    def _validate_raw_sql(self, sql: str, intent: str, schema_markdown: str) -> dict:
        """Run the same column-whitelist check `generate_queries` runs, on
        model-supplied SQL that skipped generation entirely."""
        try:
            allowed = parse_allowed_schema(schema_markdown)
            if schema_markdown.strip() and not allowed:
                logger.warning(
                    "Schema markdown provided but no ## Columns tables parsed; "
                    "skipping column whitelist validation"
                )
            validate_sql_identifiers(sql, allowed)
            return {"intent": intent, "sql": sql, "is_valid": True, "validation_error": None}
        except ValueError as ve:
            logger.warning(f"Static SQL Validation Failed: {ve}\nSQL: {sql}")
            return {"intent": intent, "sql": sql, "is_valid": False, "validation_error": str(ve)}

    def _execute_candidate(
        self,
        q: dict,
        accessible: Optional[Set[str]],
        mgmt_tables: Set[str],
        store_id: Optional[str],
    ) -> ExecutedQuery:
        intent = q.get("intent", "Database query")
        sql_text = q.get("sql") or ""
        is_valid = bool(q.get("is_valid"))
        val_err = q.get("validation_error")
        audit: Dict[str, Any] = {
            "intent": intent,
            "sql": sql_text,
            "is_valid": is_valid,
            "validation_error": val_err,
            "rows_returned": 0,
            "preview_rows": [],
        }

        if not (is_valid and sql_text and sql_text != "N/A"):
            return ExecutedQuery(intent=intent, sql=sql_text, rows=None, error=val_err, audit=audit)

        # Layer 3 — verify generated SQL only touches accessible tables.
        if accessible is not None:
            referenced = _extract_sql_tables(sql_text)
            unauthorized = {
                t for t in referenced
                if t in CONTROLLED_TABLES and t not in accessible
            }
            if unauthorized:
                err = (
                    f"Access denied: query references restricted table(s): "
                    f"{', '.join(sorted(unauthorized))}"
                )
                audit["is_valid"] = False
                audit["execution_error"] = err
                logger.warning(
                    "Blocked SQL referencing unauthorized tables %s",
                    unauthorized,
                )
                return ExecutedQuery(intent=intent, sql=sql_text, rows=None, error=err, audit=audit)

        # Layer 4 — inject store_id filters for STORE_PANEL tables.
        if store_id:
            sql_text = inject_store_id_filters(sql_text, store_id, mgmt_tables)
            audit["sql"] = sql_text

        # Layer 5 — verify every store-scoped table referenced in each CTE
        # block (and the final query) carries its own filter inside that
        # block; refuse rather than run under-filtered SQL (ADR 0001).
        # Injection above has only one global insertion point, so it can't
        # place a filter inside the right CTE on multi-CTE SQL.
        if store_id:
            scoping_errors = verify_store_scoping(sql_text, store_id, mgmt_tables)
            if scoping_errors:
                err = "Store-scoping check failed: " + "; ".join(scoping_errors)
                audit["is_valid"] = False
                audit["execution_error"] = err
                logger.warning("Blocked under-filtered SQL: %s", scoping_errors)
                return ExecutedQuery(intent=intent, sql=sql_text, rows=None, error=err, audit=audit)

        try:
            rows = self.lyndom_repo.execute_query(sql_text)
        except Exception as sql_exc:  # noqa: BLE001
            audit["execution_error"] = str(sql_exc)
            logger.warning(
                "SQL execution failed: %s\nSQL:%s", sql_exc, sql_text
            )
            return ExecutedQuery(intent=intent, sql=sql_text, rows=None, error=str(sql_exc), audit=audit)

        if len(rows) > MAX_EXECUTION_ROWS:
            err = (
                f"Error: this query returned more than {MAX_EXECUTION_ROWS:,} rows; "
                "add a filter, aggregate further, or use analyze(top_n)."
            )
            audit["execution_error"] = err
            audit["rows_returned"] = len(rows)
            return ExecutedQuery(intent=intent, sql=sql_text, rows=None, error=err, audit=audit)

        preview = _rows_preview(rows, settings.DB_RAG_MAX_ROWS)
        audit["rows_returned"] = len(rows)
        audit["preview_rows"] = preview
        return ExecutedQuery(intent=intent, sql=sql_text, rows=rows, error=None, audit=audit)

    async def query(
        self,
        *,
        question: str,
        feature_id: int,
        store_id: Optional[str],
        user_accesses: List[str],
    ) -> DatabaseQueryResult:
        results = await self.query_structured(
            question=question,
            feature_id=feature_id,
            store_id=store_id,
            user_accesses=user_accesses,
        )

        if len(results) == 1 and results[0].intent is None:
            # Tool-level failure (disabled, unconfigured, no schema, empty
            # question) — same plain-string content query() has always returned.
            return DatabaseQueryResult(content=results[0].error or "")

        payloads = [r.audit for r in results]
        content = json.dumps(payloads, indent=2, default=str, ensure_ascii=True)
        return DatabaseQueryResult(content=content, audit=payloads)
