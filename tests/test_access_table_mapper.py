"""Regression test for a defect the acceptance probes (build ticket 11) found:
STORE_ID_TABLES listed a table under the wrong (camelCase) name, which was
copy-pasted from a stale table-doc filename. Because the store-scoping
injection guard (`inject_store_id_filters`) and the verification gate
(`verify_store_scoping`) both key off STORE_ID_TABLES membership, this silently
meant a query against the *real* table name (`purchase_order_freight_line_items`)
was never recognized as store-scoped -- no automatic store_id filter injected,
and the verification gate wouldn't have flagged it as under-filtered either.
"""

from app.utils.access_table_mapper import STORE_ID_TABLES


def test_purchase_order_freight_line_items_is_listed_under_its_real_name():
    assert "purchase_order_freight_line_items" in STORE_ID_TABLES
    assert "purchaseOrder_freight_line_items" not in STORE_ID_TABLES
