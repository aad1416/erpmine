"""Tests for the store-id filter injection guard and the store-scoping
verification gate (ADR 0001)."""

from app.utils.sql_store_guard import (
    _extract_table_aliases,
    inject_store_id_filters,
    verify_store_scoping,
)


def test_simple_join_gets_both_tables_filtered():
    sql = "SELECT sales_orders.number FROM sales_orders JOIN clients ON clients.id = sales_orders.client_id;"
    out = inject_store_id_filters(sql, "store-123", set())
    assert "sales_orders.store_id = 'store-123'" in out
    assert "clients.store_id = 'store-123'" in out


def test_unaliased_table_immediately_followed_by_join_is_not_swallowed():
    """Regression: an unaliased FROM/JOIN target immediately followed by another
    JOIN used to have its alias-capture group consume the next JOIN keyword,
    which advanced the regex scan past it and made the following table
    invisible to alias extraction — silently dropping its store_id filter.
    """
    sql = """
    WITH agg AS (
        SELECT vendor_id, SUM(order_total) AS total FROM purchase_orders GROUP BY vendor_id
    )
    SELECT v.name, agg.total FROM agg JOIN vendors v ON v.id = agg.vendor_id ORDER BY agg.total DESC
    """
    aliases = _extract_table_aliases(sql)
    assert aliases.get("v") == "vendors"
    assert aliases.get("purchase_orders") == "purchase_orders"

    out = inject_store_id_filters(sql, "store-123", set())
    assert "purchase_orders.store_id = 'store-123'" in out
    assert "v.store_id = 'store-123'" in out


def test_mgmt_tables_are_not_filtered():
    sql = "SELECT id FROM stores;"
    out = inject_store_id_filters(sql, "store-123", {"stores"})
    assert out == sql


def test_existing_filter_is_not_duplicated():
    sql = "SELECT id FROM sales_orders WHERE sales_orders.store_id = 'store-123';"
    out = inject_store_id_filters(sql, "store-123", set())
    assert out.count("store_id = 'store-123'") == 1


# --- verify_store_scoping (ADR 0001) --------------------------------------

# The ADR's live repro: two CTEs, each reading a different store-scoped table,
# with no WHERE clause anywhere. `inject_store_id_filters` has only one global
# insertion point, so after "best-effort injection" the filters it adds land in
# the final query — not inside either CTE — leaving both CTEs unfiltered.
_UNFILTERED_CTE_SQL = """
WITH sales_cte AS (
    SELECT so.id, so.client_id, so.total FROM sales_orders so
),
vendor_cte AS (
    SELECT v.id, v.name FROM vendors v
)
SELECT sales_cte.id, sales_cte.total, vendor_cte.name
FROM sales_cte
JOIN vendor_cte ON sales_cte.client_id = vendor_cte.id
ORDER BY sales_cte.total DESC
"""

_FILTERED_CTE_SQL = """
WITH sales_cte AS (
    SELECT so.id, so.client_id, so.total FROM sales_orders so WHERE so.store_id = 'store-123'
),
vendor_cte AS (
    SELECT v.id, v.name FROM vendors v WHERE v.store_id = 'store-123'
)
SELECT sales_cte.id, sales_cte.total, vendor_cte.name
FROM sales_cte
JOIN vendor_cte ON sales_cte.client_id = vendor_cte.id
ORDER BY sales_cte.total DESC
"""


def test_adr_repro_sql_is_refused_after_best_effort_injection():
    # Simulate the pipeline: generate, then run best-effort injection, then verify.
    injected = inject_store_id_filters(_UNFILTERED_CTE_SQL, "store-123", set())

    errors = verify_store_scoping(injected, "store-123")

    assert len(errors) == 2
    assert any("sales_cte" in e and "sales_orders" in e for e in errors)
    assert any("vendor_cte" in e and "vendors" in e for e in errors)


def test_same_sql_with_both_ctes_filtered_is_clean():
    assert verify_store_scoping(_FILTERED_CTE_SQL, "store-123") == []


def test_one_filtered_cte_and_one_unfiltered_cte_flags_only_the_bad_block():
    sql = """
    WITH a AS (SELECT id FROM vendors v WHERE v.store_id = 'store-123'),
    b AS (SELECT id FROM sales_orders so)
    SELECT * FROM a JOIN b ON a.id = b.id
    """
    errors = verify_store_scoping(sql, "store-123")
    assert len(errors) == 1
    assert "'b'" in errors[0]
    assert "sales_orders" in errors[0]


def test_single_block_query_with_filter_passes():
    sql = "SELECT id FROM sales_orders so WHERE so.store_id = 'store-123'"
    assert verify_store_scoping(sql, "store-123") == []


def test_single_block_query_without_filter_is_refused():
    sql = "SELECT id FROM sales_orders so"
    errors = verify_store_scoping(sql, "store-123")
    assert len(errors) == 1
    assert "final query" in errors[0]
    assert "sales_orders" in errors[0]


def test_uncontrolled_table_without_store_id_column_passes():
    sql = "WITH x AS (SELECT id FROM users) SELECT * FROM x"
    assert verify_store_scoping(sql, "store-123") == []


def test_management_table_is_exempt_via_mgmt_tables():
    sql = "WITH s AS (SELECT id FROM stores) SELECT * FROM s"
    assert verify_store_scoping(sql, "store-123", {"stores"}) == []


def test_filter_via_bare_table_name_alias_passes():
    sql = (
        "WITH s AS (SELECT id FROM vendors WHERE vendors.store_id = 'store-123') "
        "SELECT * FROM s"
    )
    assert verify_store_scoping(sql, "store-123") == []


def test_no_store_id_means_no_checks():
    assert verify_store_scoping(_UNFILTERED_CTE_SQL, "") == []
