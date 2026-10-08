"""Maps ERP access permission strings to the DB tables they gate.

Access format: [ENTITY]_READ_STORE_PANEL | [ENTITY]_READ_MGMT
               [ENTITY]_GET_STORE_PANEL  | [ENTITY]_GET_MGMT

Only READ/GET accesses matter for the DB-RAG pipeline (read-only queries).
"""
from __future__ import annotations

from typing import List, Optional, Set

# Maps the access prefix (everything before _READ_/_GET_ + panel suffix)
# to the set of DB table names that permission covers.
ACCESS_TO_TABLES: dict[str, list[str]] = {
    # --- Shipment ---
    "SHIPMENT": ["shipments"],
    "SHIPMENT_LINE_ITEM": ["shipment_line_items"],
    "SHIPPING_SERVICE_TYPE": ["shipping_service_types"],
    # --- Category ---
    "CATEGORY": ["categories"],
    # --- Address / Contact ---
    "ADDRESS": ["addresses"],
    "CONTACT": ["contacts"],
    # --- Role ---
    "ROLE": ["roles", "users_roles"],
    # --- File ---
    "FILE": ["files"],
    # --- Specification ---
    "SPECIFICATION": ["specifications", "item_specifications", "item_store_specifications"],
    # --- Item / Variant ---
    "ITEM": ["items"],
    "VARIANT": ["variants", "item_store_variants"],
    "ITEM_STORE": ["item_stores"],
    # --- Note ---
    "NOTE": ["notes"],
    # --- Location ---
    "LOCATION": ["locations"],
    # --- Vendor / Vending ---
    "VENDOR": ["vendors"],
    "VENDING": ["vending", "vending_cost"],
    # --- Credit Terms ---
    "CREDIT_TERMS": ["credit_terms"],
    # --- Client ---
    "CLIENT": ["clients"],
    "CLIENT_SKU": ["client_skus"],
    # --- Carrier ---
    "CARRIER": ["carriers"],
    # --- User ---
    "USER": ["users", "user_stores", "user_types"],
    # --- Inventory ---
    "INVENTORY_ITEM": ["inventory_items", "location_change_logs"],
    # --- Purchase Order ---
    "PURCHASE_ORDER": ["purchase_orders", "purchase_orders_sales_orders"],
    "PURCHASE_ORDER_PAYMENT": ["purchase_order_payments"],
    "PURCHASE_ORDER_LINE_ITEM": ["purchase_order_line_items"],
    # --- Receive ---
    "RECEIVE": ["receives", "receive_line_items"],
    # --- Cycle Count ---
    "CYCLE_COUNT": ["cycle_counts"],
    # --- UOM ---
    "UOM": ["uoms"],
    # --- Quote ---
    "QUOTE": ["quotes", "quote_line_items", "quote_freight_line_items"],
    "QUOTE_LINE_ITEM": ["quote_line_items"],
    "QUOTE_FREIGHT_LINE_ITEM": ["quote_freight_line_items"],
    # --- Issue (DB table is goods_issues) ---
    "ISSUE": ["goods_issues", "goods_issue_line_items"],
    # --- Store / Custom Config ---
    "STORE_CONFIG": ["store_configs"],
    "CUSTOM_CONFIG": ["store_misc_settings"],
    # --- Sales Order ---
    "SALES_ORDER": ["sales_orders", "sales_order_line_items", "sales_order_freight_line_items"],
    "SALES_ORDER_LINE_ITEM": ["sales_order_line_items"],
    "SALES_ORDER_FREIGHT_LINE_ITEM": ["sales_order_freight_line_items"],
    # --- Part Request ---
    "PART_REQUEST": ["part_requests", "part_request_line_items"],
    "PART_REQUEST_LINE_ITEM": ["part_request_line_items"],
    # --- Management-panel only ---
    "STORE": ["stores", "stores_guilds"],
    "GUILD": ["guilds", "guilds_categories", "stores_guilds"],
    "PROJECT_CONFIG": ["project_configs"],
}

# Flat set of every table that requires an explicit access grant.
# Tables NOT in this set are considered uncontrolled and always readable.
CONTROLLED_TABLES: frozenset[str] = frozenset(
    t for tables in ACCESS_TO_TABLES.values() for t in tables
)

# Tables that have a `store_id` column (confirmed from docs/database/table-docs).
# Used by the store-scoping injection layer.
STORE_ID_TABLES: frozenset[str] = frozenset({
    "addresses",
    "affected_components",
    "bom_records",
    "boms",
    "carriers",
    "categories",
    "checklist_items",
    "checklists",
    "clients",
    "contacts",
    "cost_estimates",
    "credit_terms",
    "cross_checks",
    "cycle_counts",
    "departments",
    "ds_blog_posts",
    "ds_footers",
    "ds_nav_bar",
    "ds_sliders",
    "ds_template_configs",
    "field_service_tasks",
    "field_service_tickets",
    "files",
    "goods_issue_line_item_returns",
    "goods_issue_line_items",
    "goods_issues",
    "google_drive_files",
    "import_reports",
    "instruction_change",
    "instructions",
    "inventory_items",
    "item_stores",
    "item_types",
    "items",
    "leadtimes",
    "location_change_logs",
    "locations",
    "news_letter_files",
    "news_letter_view_reports",
    "news_letters",
    "notes",
    "option_selectors",
    "part_request_line_items",
    "part_requests",
    "payments",
    "production_default_tasks",
    "production_instruction_sets",
    "production_steps",
    "production_tasks",
    "purchase_order_freight_line_items",
    "purchase_order_line_items",
    "purchase_order_payments",
    "purchase_order_types",
    "purchase_orders",
    "purchase_quotes",
    "quote_freight_line_items",
    "quote_line_items",
    "quotes",
    "receive_line_items",
    "receives",
    "relationship_requests",
    "rma",
    "rma_line_items",
    "roles",
    "sales_order_freight_line_items",
    "sales_order_line_items",
    "sales_orders",
    "service_selectors",
    "shipment_line_items",
    "shipments",
    "shipping_service_types",
    "spec_rules",
    "specifications",
    "store_configs",
    "store_misc_settings",
    "timelogs",
    "unit_bom_records",
    "units",
    "uoms",
    "user_stores",
    "variants",
    "vending",
    "vendors",
})

_READ_SUFFIXES = (
    "_READ_STORE_PANEL",
    "_READ_MGMT",
    "_GET_STORE_PANEL",
    "_GET_MGMT",
)

_MGMT_SUFFIXES = (
    "_READ_MGMT",
    "_GET_MGMT",
)


def get_accessible_tables(accesses: Optional[List[str]]) -> Optional[Set[str]]:
    """Derive the set of accessible DB tables from a user's access list.

    Returns ``None`` when no restriction should be applied (empty / absent accesses).
    Returns a ``set`` of table names when access must be enforced; tables in
    ``CONTROLLED_TABLES`` that are absent from the set are off-limits.
    """
    if not accesses:
        return None

    accessible: Set[str] = set()
    for access in accesses:
        upper = access.upper()
        for suffix in _READ_SUFFIXES:
            if upper.endswith(suffix):
                prefix = upper[: -len(suffix)]
                for tbl in ACCESS_TO_TABLES.get(prefix, []):
                    accessible.add(tbl)
                break

    return accessible if accessible else None


def get_mgmt_tables(accesses: Optional[List[str]]) -> Set[str]:
    """Tables the user reaches via a _MGMT access — exempt from store_id row filtering."""
    if not accesses:
        return set()

    mgmt: Set[str] = set()
    for access in accesses:
        upper = access.upper()
        for suffix in _MGMT_SUFFIXES:
            if upper.endswith(suffix):
                prefix = upper[: -len(suffix)]
                for tbl in ACCESS_TO_TABLES.get(prefix, []):
                    mgmt.add(tbl)
                break

    return mgmt


def filter_tables_by_access(
    tables: List[str],
    accessible: Optional[Set[str]],
) -> List[str]:
    """Return only tables the user may see.

    Uncontrolled tables (not in ``CONTROLLED_TABLES``) always pass through.
    """
    if accessible is None:
        return tables
    return [
        t for t in tables
        if t not in CONTROLLED_TABLES or t in accessible
    ]
