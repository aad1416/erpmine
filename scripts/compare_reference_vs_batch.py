"""
Compare DB-RAG batch SQL (from results.log) against hand-written reference SQL
grounded in table-docs + live schema knowledge.

Usage:
    python scripts/compare_reference_vs_batch.py results.log
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, text

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config.setting import settings

# Reference SQL written from docs/database/table-docs + live DB enums/schema.
REFERENCE_SQL: dict[int, str] = {
    1: """
        SELECT payments.issuer AS name, SUM(payments.amount) AS total_amount_paid
        FROM payments
        WHERE payments.issuer IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM purchase_order_payments pop
            WHERE pop.payment_id = payments.id
          )
        GROUP BY payments.issuer
        ORDER BY SUM(payments.amount) DESC
        LIMIT 1
    """,
    2: """
        SELECT u.full_name, u.username, u.email
        FROM users u
        JOIN users_roles ur ON u.id = ur.user_entity_id
        JOIN roles r ON r.id = ur.role_entity_id
        WHERE u.is_active = true AND r.is_active = true
          AND NOT EXISTS (SELECT 1 FROM user_stores us WHERE us.user_id = u.id)
          AND EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(r.accesses) AS ak(v)
            WHERE ak.v ILIKE '%APPROV%' AND ak.v ILIKE '%LARGE%' AND ak.v ILIKE '%EXPENSE%'
          )
        ORDER BY u.full_name
    """,
    3: """
        SELECT stores.name AS branch_name, SUM(sales_orders.discount_amount) AS total_discount
        FROM sales_orders
        JOIN stores ON sales_orders.store_id = stores.id
        WHERE stores.is_active = true
        GROUP BY stores.id, stores.name
        ORDER BY SUM(sales_orders.discount_amount) DESC
        LIMIT 1
    """,
    4: """
        SELECT DISTINCT clients.name AS company_name,
               clients.contact_info_name AS contact_name,
               clients.contact_info_phone AS phone_number
        FROM clients
        JOIN sales_orders ON sales_orders.client_id = clients.id
        WHERE sales_orders.invoice_due_date IS NOT NULL
          AND sales_orders.invoice_due_date < EXTRACT(EPOCH FROM NOW())
          AND sales_orders.status NOT IN ('CANCELLED', 'REVISED')
        ORDER BY clients.name
    """,
    5: """
        SELECT number AS estimate_number, freight_cost AS shipping_fee
        FROM quotes
        WHERE freight_cost > 0
        ORDER BY number
    """,
    6: """
        SELECT u.full_name AS staff_member, u.email,
               COUNT(DISTINCT s_other.id) AS other_office_count,
               array_agg(DISTINCT s_other.name ORDER BY s_other.name) AS other_offices
        FROM users u
        JOIN user_stores us_dspm ON u.id = us_dspm.user_id
        JOIN stores s_dspm ON s_dspm.id = us_dspm.store_id AND s_dspm.name ILIKE '%DSPM%'
        JOIN user_stores us_other ON u.id = us_other.user_id
        JOIN stores s_other ON s_other.id = us_other.store_id AND s_other.id <> s_dspm.id
        WHERE u.is_active = true
        GROUP BY u.id, u.full_name, u.email
        ORDER BY u.full_name
    """,
    7: """
        SELECT sales_orders.number, sales_orders.order_total,
               users.full_name AS salesperson
        FROM sales_orders
        LEFT JOIN users ON sales_orders.sales_person_id = users.id
        WHERE sales_orders.status = 'CANCELLED'
          AND sales_orders.date >= EXTRACT(EPOCH FROM TIMESTAMPTZ '2025-07-01 00:00:00+00')::bigint
          AND sales_orders.date < EXTRACT(EPOCH FROM TIMESTAMPTZ '2025-08-01 00:00:00+00')::bigint
        ORDER BY sales_orders.date, sales_orders.number
    """,
    8: """
        SELECT stores.name, store_configs.auto_generate_part_request
        FROM stores
        JOIN store_configs ON store_configs.store_id = stores.id
        WHERE stores.is_active = true AND stores.name ILIKE '%Lyndom%'
    """,
    9: """
        SELECT COALESCE(SUM(sales_orders.order_total), 0) AS total_sales_amount
        FROM sales_orders
        JOIN users ON users.id = sales_orders.sales_person_id
        WHERE users.is_active = true
          AND EXISTS (
            SELECT 1 FROM users_roles ur
            JOIN roles r ON r.id = ur.role_entity_id
            WHERE ur.user_entity_id = users.id
              AND r.is_active = true
              AND r.name ILIKE '%manager%'
          )
    """,
    10: """
        SELECT clients.name, clients.contact_info_email
        FROM clients
        WHERE clients.contact_info_email IS NULL
           OR btrim(clients.contact_info_email) = ''
        ORDER BY clients.name
    """,
    11: """
        SELECT roles.name AS job_title, COUNT(DISTINCT users.id) AS staff_count
        FROM users
        JOIN users_roles ON users.id = users_roles.user_entity_id
        JOIN roles ON roles.id = users_roles.role_entity_id
        WHERE users.is_active = true AND roles.is_active = true
        GROUP BY roles.name
        ORDER BY COUNT(DISTINCT users.id) DESC
        LIMIT 1
    """,
    12: """
        SELECT clients.name AS customer_name, sales_orders.number AS order_number,
               notes.note AS special_instruction
        FROM sales_orders
        JOIN clients ON sales_orders.client_id = clients.id
        JOIN notes ON notes.owner_id = sales_orders.id
                AND notes.owner_type = 'sales_order'
                AND notes.is_active = true
        WHERE sales_orders.invoice_due_date IS NOT NULL
          AND sales_orders.invoice_due_date < EXTRACT(EPOCH FROM NOW())::bigint
        ORDER BY sales_orders.invoice_due_date, notes.created_at
    """,
    13: """
        SELECT stores.name AS branch_name,
               COALESCE(SUM(sales_orders.order_total), 0) AS total_sales_amount
        FROM sales_orders
        JOIN stores ON sales_orders.store_id = stores.id
        JOIN users ON sales_orders.sales_person_id = users.id
        JOIN users_departments ON users.id = users_departments.user_entity_id
        JOIN departments ON users_departments.department_entity_id = departments.id
        WHERE stores.name ILIKE '%DSPM%' AND stores.is_active = true
          AND departments.name ILIKE '%Sales%'
        GROUP BY stores.id, stores.name
    """,
    14: """
        SELECT stores.name AS branch_name, COUNT(clients.id) AS customer_count
        FROM clients
        JOIN stores ON clients.store_id = stores.id
        WHERE clients.is_active = true AND stores.is_active = true
        GROUP BY stores.id, stores.name
        ORDER BY COUNT(clients.id) DESC
        LIMIT 1
    """,
    15: """
        SELECT n.date, u.full_name AS manager_name, n.title, n.text
        FROM notificaitons n
        JOIN notificaiton_user nu ON nu.notification_id = n.id
        JOIN users u ON nu.user_id = u.id
        JOIN users_roles ur ON u.id = ur.user_entity_id
        JOIN roles r ON r.id = ur.role_entity_id
        WHERE u.is_active = true AND r.is_active = true AND r.name ILIKE '%manager%'
          AND (n.title ILIKE '%import%' OR n.text ILIKE '%import%')
        ORDER BY n.date DESC
        LIMIT 50
    """,
    16: """
        SELECT users.full_name, users.email, stores.name AS branch_name
        FROM users
        JOIN user_stores ON users.id = user_stores.user_id
        JOIN stores ON stores.id = user_stores.store_id
        WHERE users.is_active = true AND stores.is_active = true
        ORDER BY users.full_name, stores.name
    """,
    17: """
        SELECT stores.name AS branch_name, COUNT(DISTINCT users.id) AS headcount
        FROM departments
        JOIN stores ON departments.store_id = stores.id
        JOIN users_departments ON departments.id = users_departments.department_entity_id
        JOIN users ON users_departments.user_entity_id = users.id
        WHERE departments.name ILIKE '%Sales%'
          AND users.is_active = true AND stores.is_active = true
        GROUP BY stores.id, stores.name
        ORDER BY COUNT(DISTINCT users.id) DESC
        LIMIT 1
    """,
    18: """
        SELECT users.full_name AS salesperson_name, SUM(sales_orders.order_total) AS total_value
        FROM sales_orders
        JOIN users ON sales_orders.sales_person_id = users.id
        JOIN stores ON sales_orders.store_id = stores.id
        WHERE stores.name ILIKE '%DSPM%' AND stores.is_active = true
          AND users.is_active = true
          AND sales_orders.status = 'COMPLETED'
          AND sales_orders.date >= EXTRACT(EPOCH FROM TIMESTAMPTZ '2026-01-01 00:00:00+00')::bigint
          AND sales_orders.date < EXTRACT(EPOCH FROM TIMESTAMPTZ '2027-01-01 00:00:00+00')::bigint
        GROUP BY users.id, users.full_name
        ORDER BY SUM(sales_orders.order_total) DESC
        LIMIT 1
    """,
    19: """
        SELECT barron.no AS barron_sku, barron.name AS product_name,
               (barron.on_hand_quantity - barron.allocated_quantity) AS barron_avail,
               dspm.no AS dspm_sku,
               (dspm.on_hand_quantity - dspm.allocated_quantity) AS dspm_avail
        FROM item_stores barron
        JOIN stores barron_store ON barron.store_id = barron_store.id
        JOIN item_stores dspm ON barron.item_id = dspm.item_id
        JOIN stores dspm_store ON dspm.store_id = dspm_store.id
        WHERE barron_store.name ILIKE '%Barron%'
          AND dspm_store.name ILIKE '%DSPM%'
          AND barron.is_active = true AND dspm.is_active = true
          AND barron.archived = false AND dspm.archived = false
          AND (barron.on_hand_quantity - barron.allocated_quantity) <= 0
          AND (dspm.on_hand_quantity - dspm.allocated_quantity) >= 10
        ORDER BY barron.name
    """,
    20: """
        SELECT stores.name AS branch_name, units.serial_number, production_tasks.number,
               production_tasks.status, production_tasks.created_at
        FROM production_tasks
        JOIN units ON production_tasks.unit_id = units.id
        JOIN stores ON production_tasks.store_id = stores.id
        WHERE production_tasks.status = 'PENDING'
          AND production_tasks.created_at < NOW() - INTERVAL '7 days'
          AND stores.name ILIKE '%DSPM%' AND stores.is_active = true
        ORDER BY production_tasks.created_at
    """,
    21: """
        SELECT AVG(item_stores.labor_time) AS average_labor_time
        FROM item_stores
        JOIN categories ON item_stores.category_id = categories.id
        WHERE categories.name = 'Three Phase- Eternalight-Online 3 (OE3A)'
          AND categories.is_active = true
          AND item_stores.is_active = true
          AND item_stores.archived = false
    """,
    22: """
        SELECT quotes.number, quotes.order_total, users.full_name AS creator_name
        FROM quotes
        JOIN users ON quotes.creator_id = users.id
        WHERE quotes.sales_order_id IS NULL
          AND users.is_active = true
          AND EXISTS (
            SELECT 1 FROM users_roles ur
            JOIN roles r ON r.id = ur.role_entity_id
            WHERE ur.user_entity_id = users.id
              AND r.name = 'Manager Full Access'
              AND r.is_active = true
          )
        ORDER BY quotes.created_at DESC
    """,
    23: """
        SELECT stores.name AS branch_name, COUNT(DISTINCT users.id) AS active_user_count
        FROM stores
        LEFT JOIN user_stores ON stores.id = user_stores.store_id
        LEFT JOIN users ON user_stores.user_id = users.id AND users.is_active = true
        WHERE stores.is_active = true
        GROUP BY stores.id, stores.name
        ORDER BY COUNT(DISTINCT users.id) DESC
        LIMIT 1
    """,
    24: """
        SELECT COALESCE(SUM(inventory_items.available_quantity * inventory_items.cost), 0)
               AS total_storage_value
        FROM inventory_items
        JOIN locations ON inventory_items.location_id = locations.id
        JOIN stores ON inventory_items.store_id = stores.id
        WHERE stores.name = 'DSPM' AND stores.is_active = true
          AND locations.name = 'STORAGE' AND locations.is_active = true
    """,
    25: """
        SELECT COUNT(production_tasks.id) AS pending_jobs
        FROM production_tasks
        JOIN stores ON production_tasks.store_id = stores.id
        WHERE production_tasks.status = 'PENDING'
          AND stores.name ILIKE '%DSPM%' AND stores.is_active = true
    """,
    26: """
        SELECT item_stores.no AS product_no, item_stores.name AS product_name,
               SUM(rma_line_items.quantity) AS total_returned_quantity
        FROM rma
        JOIN rma_line_items ON rma_line_items.rma_id = rma.id
        JOIN item_stores ON rma_line_items.item_store_id = item_stores.id
        JOIN categories ON item_stores.category_id = categories.id
        WHERE categories.name = 'Cat1' AND categories.is_active = true
          AND rma.date >= EXTRACT(EPOCH FROM date_trunc('year', CURRENT_DATE))::bigint
          AND rma.date < EXTRACT(EPOCH FROM (date_trunc('year', CURRENT_DATE) + INTERVAL '1 year'))::bigint
        GROUP BY item_stores.id, item_stores.no, item_stores.name
        ORDER BY SUM(rma_line_items.quantity) DESC
    """,
    27: """
        SELECT COALESCE(SUM(item_stores.labor_time), 0) AS total_labor_time
        FROM item_stores
        JOIN categories ON item_stores.category_id = categories.id
        WHERE item_stores.is_active = true AND categories.name = 'DE3'
    """,
    28: """
        SELECT users.full_name, users.email
        FROM users
        JOIN users_roles ur ON users.id = ur.user_entity_id
        JOIN roles r ON r.id = ur.role_entity_id
        WHERE users.is_active = true AND r.is_active = true
          AND r.type = 'MANAGEMENT'
          AND r.accesses::text ILIKE '%APPROV%'
          AND r.accesses::text ILIKE '%ORDER%'
          AND r.accesses::text ILIKE '%LARGE%'
          AND NOT EXISTS (
            SELECT 1 FROM sales_orders so
            WHERE so.creator_id = users.id
              AND so.date >= EXTRACT(EPOCH FROM TIMESTAMPTZ '2026-02-01 00:00:00+00')::bigint
              AND so.date < EXTRACT(EPOCH FROM TIMESTAMPTZ '2026-03-01 00:00:00+00')::bigint
          )
        ORDER BY users.full_name
    """,
    29: """
        SELECT stores.name AS branch_name, vendors.name AS vendor_name,
               COALESCE(SUM(fifo_reports.quantity * fifo_reports.value), 0) AS total_received_value
        FROM fifo_reports
        JOIN receives ON fifo_reports.receive_id = receives.id
        JOIN purchase_orders ON receives.purchase_order_id = purchase_orders.id
        JOIN vendors ON purchase_orders.vendor_id = vendors.id
        JOIN stores ON receives.store_id = stores.id
        WHERE fifo_reports.type = 'ADD'
          AND vendors.name = 'Mouser Electronics, Inc.'
          AND stores.name = 'DSPM' AND stores.is_active = true
        GROUP BY stores.name, vendors.name
    """,
}


def _normalize_value(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _row_key(row: dict) -> tuple:
    return tuple(str(_normalize_value(v)) for v in row.values())


def _execute(engine, sql: str) -> tuple[int, list[dict], str | None]:
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql.strip()))
            cols = list(result.keys())
            rows = [dict(zip(cols, r)) for r in result.fetchall()]
        return len(rows), rows, None
    except Exception as exc:
        return -1, [], str(exc)


def _compare_rows(ref_rows: list[dict], batch_rows: list[dict]) -> str:
    if len(ref_rows) != len(batch_rows):
        return "row_count_diff"
    if not ref_rows:
        return "both_empty"
    ref_keys = {_row_key(r) for r in ref_rows}
    batch_keys = {_row_key(r) for r in batch_rows}
    if ref_keys == batch_keys:
        return "exact_match"
    overlap = len(ref_keys & batch_keys)
    if len(ref_rows) == 1:
        return "single_row_value_diff"
    return f"partial_overlap_{overlap}/{len(ref_rows)}"


def _compare_scalar(ref_rows: list[dict], batch_rows: list[dict]) -> bool:
    if len(ref_rows) != 1 or len(batch_rows) != 1:
        return False
    r, b = ref_rows[0], batch_rows[0]
    for k in r:
        if k in b and _normalize_value(r[k]) == _normalize_value(b[k]):
            continue
        return False
    return True


def load_batch(log_path: str) -> dict[int, dict]:
    entries = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line.strip()))
    starts = [i for i, e in enumerate(entries) if e.get("event") == "batch_start"]
    batch_entries = entries[starts[-1] :] if starts else entries
    out: dict[int, dict] = {}
    for e in batch_entries:
        if e.get("event") == "query_result":
            gq = e["generated_queries"][0]
            out[e["index"]] = {
                "question": e["user_query"],
                "status": e["status"],
                "sql": gq.get("sql", ""),
                "valid": gq.get("is_valid", False),
                "error": gq.get("validation_error") or gq.get("error"),
                "logged_rows": gq.get("row_count"),
            }
    return out


def main() -> None:
    log_path = sys.argv[1] if len(sys.argv) > 1 else "results.log"
    if not settings.lyndom_db_url:
        print("lyndom_db_url not configured")
        sys.exit(1)

    engine = create_engine(settings.lyndom_db_url)
    batch = load_batch(log_path)

    print(f"Reference vs batch comparison ({log_path})\n")
    print(f"{'#':>3} {'verdict':<22} {'ref':>6} {'batch':>6}  question")
    print("-" * 90)

    summary: dict[str, int] = {}

    for idx in range(1, 30):
        ref_sql = REFERENCE_SQL.get(idx, "")
        b = batch.get(idx, {})
        question = (b.get("question") or "")[:50]

        if b.get("status") != "ok" or not b.get("valid"):
            ref_n, ref_rows, ref_err = _execute(engine, ref_sql) if ref_sql else (-1, [], "no ref")
            verdict = "batch_failed"
            if ref_err:
                verdict = "batch_failed_ref_err"
            summary[verdict] = summary.get(verdict, 0) + 1
            print(f"{idx:3d} {verdict:<22} {ref_n:6} {'—':>6}  {question}")
            if b.get("error"):
                print(f"     batch: {str(b['error'])[:120]}")
            if ref_n >= 0:
                print(f"     ref would return {ref_n} rows")
            continue

        batch_n, batch_rows, batch_err = _execute(engine, b["sql"])
        ref_n, ref_rows, ref_err = _execute(engine, ref_sql)

        if batch_err or ref_err:
            verdict = "exec_error"
            summary[verdict] = summary.get(verdict, 0) + 1
            print(f"{idx:3d} {verdict:<22} {ref_n:6} {batch_n:6}  {question}")
            if ref_err:
                print(f"     ref err: {ref_err[:100]}")
            if batch_err:
                print(f"     batch err: {batch_err[:100]}")
            continue

        cmp = _compare_rows(ref_rows, batch_rows)
        if cmp == "row_count_diff" and ref_n == batch_n:
            cmp = "same_count_diff_rows"
        if cmp == "single_row_value_diff" and _compare_scalar(ref_rows, batch_rows):
            cmp = "scalar_match"
        if ref_n == batch_n and cmp in ("exact_match", "both_empty", "scalar_match"):
            verdict = "aligned"
        elif ref_n == batch_n:
            verdict = cmp
        else:
            verdict = f"count_ref{ref_n}_batch{batch_n}"

        summary[verdict] = summary.get(verdict, 0) + 1
        print(f"{idx:3d} {verdict:<22} {ref_n:6} {batch_n:6}  {question}")
        if verdict not in ("aligned", "both_empty") and ref_rows and batch_rows:
            if len(ref_rows) == 1 and len(batch_rows) == 1:
                print(f"     ref:  {ref_rows[0]}")
                print(f"     batch:{batch_rows[0]}")

    print("\n--- Summary ---")
    for k, v in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
