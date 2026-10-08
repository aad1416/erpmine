"""A Lyndom query the database cuts off (Postgres `statement_timeout`) must reach the
model as an ordinary per-query error record, exactly like any other failed SQL — never
as an exception out of the tool and never as a tool-level failure that hides the other
queries' results.

This file also covers the `query_structured` prefactor (ticket 02): the shared guard
pipeline (column-whitelist validation -> access-table check -> store-filter injection
-> execute) used by both `query_structured` and the legacy `query()`, the 20,000-row
execution cap, and the `sql=` re-run path.
"""

import json

import pytest
from sqlalchemy.exc import OperationalError

from app.config.setting import settings
from app.services.database_query_tool_service import (
    MAX_EXECUTION_ROWS,
    DatabaseQueryToolService,
)

_VENDORS_SCHEMA = """
# `vendors`

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| store_id | text | no | — | Owning store. |
| name | text | no | — | Vendor name. |
"""

_ITEMS_SCHEMA = """
# `items`

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| name | text | no | — | Item name. |
"""


class _StubRetrievalService:
    def __init__(self, schema_markdown="## sales_orders", selected_tables=None):
        self.schema_markdown = schema_markdown
        self.selected_tables = selected_tables or ["sales_orders"]

    async def get_relevant_schemas(self, *, user_message, feature_id, accessible_tables):
        return {"schema_markdown": self.schema_markdown, "selected_tables": self.selected_tables}


class _StubQueryService:
    def __init__(self, queries=None, forbid_generate=False):
        self._queries = queries or []
        self.forbid_generate = forbid_generate
        self.generate_calls = 0

    async def generate_queries(self, **kwargs):
        if self.forbid_generate:
            raise AssertionError("generate_queries should not be called for a sql= re-run")
        self.generate_calls += 1
        return {"queries": self._queries}


class _Repository:
    def __init__(self, rows_by_sql=None, default_rows=None):
        self.rows_by_sql = rows_by_sql or {}
        self.default_rows = default_rows if default_rows is not None else [{"n": 1}]
        self.executed = []

    def execute_query(self, query, params=None):
        self.executed.append(query)
        if query in self.rows_by_sql:
            return self.rows_by_sql[query]
        return self.default_rows


class _TimingOutRepository:
    """Stands in for LyndomDBRepository when Postgres cancels the statement."""

    def __init__(self, timeout_sql):
        self._timeout_sql = timeout_sql
        self.executed = []

    def execute_query(self, query, params=None):
        self.executed.append(query)
        if query == self._timeout_sql:
            # What SQLAlchemy raises for psycopg2.errors.QueryCanceled.
            raise OperationalError(
                query, {}, Exception("canceling statement due to statement timeout")
            )
        return [{"n": 1}]


@pytest.fixture()
def db_rag_enabled(monkeypatch):
    monkeypatch.setattr(settings, "DB_RAG_ENABLED", True)


async def test_timed_out_query_becomes_error_record_next_to_successful_ones(db_rag_enabled):
    slow_sql = "SELECT COUNT(*) FROM sales_orders"
    fast_sql = "SELECT 1 AS n"
    repo = _TimingOutRepository(timeout_sql=slow_sql)
    svc = DatabaseQueryToolService(
        db_rag_retrieval_service=_StubRetrievalService(),
        db_rag_query_service=_StubQueryService(
            [
                {"intent": "slow", "sql": slow_sql, "is_valid": True},
                {"intent": "fast", "sql": fast_sql, "is_valid": True},
            ]
        ),
        lyndom_repo=repo,
    )

    result = await svc.query(
        question="how many orders", feature_id=1, store_id=None, user_accesses=[]
    )

    assert repo.executed == [slow_sql, fast_sql]
    payloads = json.loads(result.content)
    assert [p["intent"] for p in payloads] == ["slow", "fast"]

    timed_out, succeeded = payloads
    assert "canceling statement due to statement timeout" in timed_out["execution_error"]
    assert timed_out["rows_returned"] == 0
    assert timed_out["preview_rows"] == []
    assert "execution_error" not in succeeded
    assert succeeded["rows_returned"] == 1

    assert result.audit == payloads


async def test_query_structured_returns_one_record_per_executed_sql(db_rag_enabled):
    queries = [
        {"intent": "Order count", "sql": "SELECT COUNT(*) FROM sales_orders", "is_valid": True, "validation_error": None},
        {"intent": "Order total", "sql": "SELECT SUM(order_total) FROM sales_orders", "is_valid": True, "validation_error": None},
    ]
    repo = _Repository(rows_by_sql={
        "SELECT COUNT(*) FROM sales_orders": [{"count": 3}],
        "SELECT SUM(order_total) FROM sales_orders": [{"sum": 42.5}],
    })
    svc = DatabaseQueryToolService(
        db_rag_retrieval_service=_StubRetrievalService(),
        db_rag_query_service=_StubQueryService(queries),
        lyndom_repo=repo,
    )

    results = await svc.query_structured(
        question="sales summary", feature_id=1, store_id=None, user_accesses=[]
    )

    assert len(results) == 2
    assert [r.intent for r in results] == ["Order count", "Order total"]
    assert results[0].rows == [{"count": 3}]
    assert results[0].error is None
    assert results[1].rows == [{"sum": 42.5}]
    assert results[1].error is None


async def test_query_content_and_audit_byte_identical_before_and_after_refactor(db_rag_enabled):
    """Pins query()'s JSON content and audit for a fixed generator/repository
    stub — one valid and one whitelist-invalid query, same shape the pipeline
    always produced."""
    queries = [
        {
            "intent": "Total orders",
            "sql": "SELECT COUNT(*) FROM sales_orders",
            "is_valid": True,
            "validation_error": None,
        },
        {
            "intent": "Bad query",
            "sql": "SELECT x FROM nope",
            "is_valid": False,
            "validation_error": "Unknown table 'nope'.",
        },
    ]
    repo = _Repository(rows_by_sql={"SELECT COUNT(*) FROM sales_orders": [{"n": 5}]})
    svc = DatabaseQueryToolService(
        db_rag_retrieval_service=_StubRetrievalService(),
        db_rag_query_service=_StubQueryService(queries),
        lyndom_repo=repo,
    )

    result = await svc.query(question="orders", feature_id=1, store_id=None, user_accesses=[])

    expected_payloads = [
        {
            "intent": "Total orders",
            "sql": "SELECT COUNT(*) FROM sales_orders",
            "is_valid": True,
            "validation_error": None,
            "rows_returned": 1,
            "preview_rows": [{"n": 5}],
        },
        {
            "intent": "Bad query",
            "sql": "SELECT x FROM nope",
            "is_valid": False,
            "validation_error": "Unknown table 'nope'.",
            "rows_returned": 0,
            "preview_rows": [],
        },
    ]
    assert result.audit == expected_payloads
    assert result.content == json.dumps(expected_payloads, indent=2, default=str, ensure_ascii=True)
    # Only the valid query reached the repository.
    assert repo.executed == ["SELECT COUNT(*) FROM sales_orders"]


async def test_query_top_level_failure_content_unchanged(db_rag_enabled, monkeypatch):
    monkeypatch.setattr(settings, "DB_RAG_ENABLED", False)
    svc = DatabaseQueryToolService(
        db_rag_retrieval_service=_StubRetrievalService(),
        db_rag_query_service=_StubQueryService([]),
        lyndom_repo=_Repository(),
    )

    result = await svc.query(question="orders", feature_id=1, store_id=None, user_accesses=[])

    assert result.content == "Database querying is disabled (DB_RAG_ENABLED=false)."
    assert result.audit == []


async def test_execution_row_cap_errors_instead_of_truncating(db_rag_enabled):
    oversized = [{"n": i} for i in range(MAX_EXECUTION_ROWS + 1)]
    repo = _Repository(default_rows=oversized)
    svc = DatabaseQueryToolService(
        db_rag_retrieval_service=_StubRetrievalService(),
        db_rag_query_service=_StubQueryService(
            [{"intent": "everything", "sql": "SELECT n FROM sales_orders", "is_valid": True, "validation_error": None}]
        ),
        lyndom_repo=repo,
    )

    results = await svc.query_structured(
        question="all rows", feature_id=1, store_id=None, user_accesses=[]
    )

    assert len(results) == 1
    record = results[0]
    assert record.rows is None
    assert record.error == (
        "Error: this query returned more than 20,000 rows; "
        "add a filter, aggregate further, or use analyze(top_n)."
    )
    assert record.audit["execution_error"] == record.error
    assert record.audit["rows_returned"] == MAX_EXECUTION_ROWS + 1
    # Not the D_RAG_MAX_ROWS preview trim's business — no preview is emitted on a cap error.
    assert record.audit["preview_rows"] == []


async def test_execution_cap_does_not_disturb_the_unrelated_preview_trim(db_rag_enabled, monkeypatch):
    monkeypatch.setattr(settings, "DB_RAG_MAX_ROWS", 1)
    repo = _Repository(default_rows=[{"n": 1}, {"n": 2}, {"n": 3}])
    svc = DatabaseQueryToolService(
        db_rag_retrieval_service=_StubRetrievalService(),
        db_rag_query_service=_StubQueryService(
            [{"intent": "three rows", "sql": "SELECT n FROM sales_orders", "is_valid": True, "validation_error": None}]
        ),
        lyndom_repo=repo,
    )

    results = await svc.query_structured(
        question="a few rows", feature_id=1, store_id=None, user_accesses=[]
    )

    record = results[0]
    # Full rows stay in the record...
    assert record.rows == [{"n": 1}, {"n": 2}, {"n": 3}]
    assert record.error is None
    # ...only the JSON-preview audit field is trimmed by DB_RAG_MAX_ROWS.
    assert record.audit["rows_returned"] == 3
    assert record.audit["preview_rows"] == [{"n": 1}]


async def test_sql_rerun_skips_generation_and_runs_validator_access_and_injection(db_rag_enabled):
    query_service = _StubQueryService(forbid_generate=True)
    repo = _Repository()
    svc = DatabaseQueryToolService(
        db_rag_retrieval_service=_StubRetrievalService(schema_markdown=_VENDORS_SCHEMA),
        db_rag_query_service=query_service,
        lyndom_repo=repo,
    )

    results = await svc.query_structured(
        question="vendor names",
        sql="SELECT v.name FROM vendors v",
        feature_id=1,
        store_id="store-42",
        user_accesses=["VENDOR_READ_STORE_PANEL"],
    )

    assert query_service.generate_calls == 0
    assert len(results) == 1
    record = results[0]
    assert record.error is None
    # Store-filter injection ran, and the post-injection SQL is what's recorded.
    assert "v.store_id = 'store-42'" in record.sql
    assert record.audit["sql"] == record.sql
    assert repo.executed == [record.sql]


async def test_sql_rerun_runs_column_whitelist_validator(db_rag_enabled):
    query_service = _StubQueryService(forbid_generate=True)
    repo = _Repository()
    svc = DatabaseQueryToolService(
        db_rag_retrieval_service=_StubRetrievalService(schema_markdown=_VENDORS_SCHEMA),
        db_rag_query_service=query_service,
        lyndom_repo=repo,
    )

    results = await svc.query_structured(
        # Unaliased table reference: the column-whitelist validator only
        # resolves `table.column`, not alias-qualified columns (accepted gap).
        question="vendor phone numbers",
        sql="SELECT vendors.phone_number FROM vendors",
        feature_id=1,
        store_id="store-42",
        user_accesses=["VENDOR_READ_STORE_PANEL"],
    )

    assert len(results) == 1
    record = results[0]
    assert record.rows is None
    assert "phone_number" in record.error
    # Never reached execution: the whitelist validator caught it first.
    assert repo.executed == []


async def test_access_denied_sql_never_reaches_execution(db_rag_enabled):
    query_service = _StubQueryService(forbid_generate=True)
    repo = _Repository()
    svc = DatabaseQueryToolService(
        db_rag_retrieval_service=_StubRetrievalService(schema_markdown=_VENDORS_SCHEMA),
        db_rag_query_service=query_service,
        lyndom_repo=repo,
    )

    # user only has access to items, not vendors — vendors is a CONTROLLED_TABLES entry.
    results = await svc.query_structured(
        question="vendor names",
        sql="SELECT v.name FROM vendors v",
        feature_id=1,
        store_id="store-42",
        user_accesses=["ITEM_READ_STORE_PANEL"],
    )

    assert len(results) == 1
    record = results[0]
    assert record.rows is None
    assert record.error.startswith("Access denied")
    assert repo.executed == []
    # Injection never ran either — the recorded sql is the pre-injection text.
    assert record.sql == "SELECT v.name FROM vendors v"


async def test_under_filtered_multi_cte_sql_is_refused_before_execution(db_rag_enabled):
    """ADR 0001: a generated query with two CTEs, each reading a different
    store-scoped table and neither carrying its own filter, must be refused
    by the store-scoping verification gate — even after best-effort injection
    runs — and never reach the repository.

    Uses the generated-candidate path (not `sql=`) since the pre-existing
    column-whitelist validator doesn't know about CTE names and would reject
    this SQL for an unrelated reason on the `sql=` re-run path."""
    repo = _Repository()
    multi_cte_sql = (
        "WITH sales_cte AS ("
        "  SELECT so.id, so.client_id, so.total FROM sales_orders so"
        "), vendor_cte AS ("
        "  SELECT v.id, v.name FROM vendors v"
        ") "
        "SELECT sales_cte.id, sales_cte.total, vendor_cte.name "
        "FROM sales_cte JOIN vendor_cte ON sales_cte.client_id = vendor_cte.id"
    )
    svc = DatabaseQueryToolService(
        db_rag_retrieval_service=_StubRetrievalService(),
        db_rag_query_service=_StubQueryService(
            [{"intent": "sales vs vendors", "sql": multi_cte_sql, "is_valid": True, "validation_error": None}]
        ),
        lyndom_repo=repo,
    )

    results = await svc.query_structured(
        question="sales vs vendors",
        feature_id=1,
        store_id="store-123",
        user_accesses=["VENDOR_READ_STORE_PANEL", "SALES_ORDER_READ_STORE_PANEL"],
    )

    assert len(results) == 1
    record = results[0]
    assert record.rows is None
    assert record.error.startswith("Store-scoping check failed")
    assert "sales_cte" in record.error
    assert "vendor_cte" in record.error
    assert repo.executed == []


async def test_guard_order_column_whitelist_runs_before_access_check(db_rag_enabled):
    """An unknown-table SQL that would *also* fail the access check must be
    reported as a whitelist failure, proving whitelist validation runs first."""
    query_service = _StubQueryService(forbid_generate=True)
    repo = _Repository()
    svc = DatabaseQueryToolService(
        # Only "items" is documented — "vendors" isn't in the schema at all.
        db_rag_retrieval_service=_StubRetrievalService(schema_markdown=_ITEMS_SCHEMA),
        db_rag_query_service=query_service,
        lyndom_repo=repo,
    )

    results = await svc.query_structured(
        question="vendor names",
        sql="SELECT v.name FROM vendors v",
        feature_id=1,
        store_id="store-42",
        user_accesses=["ITEM_READ_STORE_PANEL"],  # would also fail the access check
    )

    record = results[0]
    assert "Unknown table 'vendors'" in record.error
    assert not record.error.startswith("Access denied")
    assert repo.executed == []
