"""Tests for SQL identifier validation against table-docs markdown."""

from app.utils.db_schema_markdown import parse_allowed_schema, validate_sql_identifiers

_SALES_ORDERS_SCHEMA = """
# `sales_orders`

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| number | text | no | — | Order number. |
| date | int8 | no | — | Contract date. |
| status | enum | no | — | Lifecycle state. |
"""


def test_extract_epoch_from_timestamptz_not_treated_as_table():
    allowed = parse_allowed_schema(_SALES_ORDERS_SCHEMA)
    sql = """
    SELECT number FROM sales_orders
    WHERE status = 'CANCELLED'
      AND date >= EXTRACT(EPOCH FROM TIMESTAMPTZ '2025-07-01 00:00:00+00')
      AND date < EXTRACT(EPOCH FROM TIMESTAMPTZ '2025-08-01 00:00:00+00');
    """
    validate_sql_identifiers(sql, allowed)


def test_extract_epoch_from_date_trunc_not_treated_as_table():
    allowed = {"rma": {"id", "receive_date"}, "item_stores": {"id", "no", "name", "category_id"}, "categories": {"id", "name", "is_active"}, "rma_line_items": {"rma_id", "item_store_id", "quantity"}}
    sql = """
    SELECT item_stores.no FROM rma
    JOIN rma_line_items ON rma_line_items.rma_id = rma.id
    WHERE rma.receive_date >= EXTRACT(EPOCH FROM date_trunc('year', CURRENT_DATE))::bigint;
    """
    validate_sql_identifiers(sql, allowed)


def test_unknown_table_still_rejected():
    allowed = parse_allowed_schema(_SALES_ORDERS_SCHEMA)
    sql = "SELECT id FROM not_a_real_table;"
    try:
        validate_sql_identifiers(sql, allowed)
    except ValueError as exc:
        assert "Unknown table 'not_a_real_table'" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_real_from_join_still_validated():
    allowed = parse_allowed_schema(_SALES_ORDERS_SCHEMA)
    sql = "SELECT sales_orders.number FROM sales_orders JOIN clients ON clients.id = sales_orders.client_id;"
    try:
        validate_sql_identifiers(sql, allowed)
    except ValueError as exc:
        assert "Unknown table 'clients'" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cte_name_referenced_in_final_query_is_not_an_unknown_table():
    """Acceptance probe 11 (probe 4, "declining customers over 5 years") found
    this exact shape rejected live: a query_database call built a two-CTE trend
    query, and the final SELECT's `FROM trend t JOIN declining_customers dc`
    was flagged as referencing unknown tables 'trend' and 'declining_customers'
    -- a false positive, since both are CTE names the query defines itself, not
    hallucinated real tables. The model recovered by falling back to a simpler
    query, but the validator itself needs to recognise a query's own CTEs."""
    allowed = {
        "sales_orders": {"id", "client_id", "date", "status", "order_total", "store_id"},
        "clients": {"id", "name", "store_id"},
    }
    sql = """
    WITH yearly_sales AS (
      SELECT s.client_id, c.name AS customer_name,
             EXTRACT(YEAR FROM to_timestamp(s.date / 1000.0))::int AS sales_year,
             SUM(s.order_total) AS total_sales_value
      FROM sales_orders s
      JOIN clients c ON c.id = s.client_id
      WHERE s.status NOT IN ('CANCELLED', 'REVISED')
      GROUP BY s.client_id, c.name, EXTRACT(YEAR FROM to_timestamp(s.date / 1000.0))
    ), trend AS (
      SELECT ys.*,
             LAG(ys.total_sales_value) OVER (PARTITION BY ys.client_id ORDER BY ys.sales_year) AS prior_year_sales
      FROM yearly_sales ys
    ), declining_customers AS (
      SELECT DISTINCT client_id FROM trend WHERE prior_year_sales IS NOT NULL
    )
    SELECT t.customer_name, t.sales_year
    FROM trend t
    JOIN declining_customers dc ON dc.client_id = t.client_id
    ORDER BY t.customer_name, t.sales_year;
    """
    validate_sql_identifiers(sql, allowed)  # must not raise


def test_cte_name_does_not_shadow_a_real_table_check():
    """A CTE happening to share a real table's name doesn't hide a genuinely
    unknown table referenced elsewhere in the query."""
    allowed = parse_allowed_schema(_SALES_ORDERS_SCHEMA)
    sql = """
    WITH recent AS (SELECT id FROM sales_orders)
    SELECT recent.id FROM recent JOIN not_a_real_table nt ON nt.id = recent.id;
    """
    try:
        validate_sql_identifiers(sql, allowed)
    except ValueError as exc:
        assert "Unknown table 'not_a_real_table'" in str(exc)
    else:
        raise AssertionError("expected ValueError")
