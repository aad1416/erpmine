# job_records_issue_line_items

## Purpose
The global traceability bridge. It provides high-precision linkage between a physical inventory consumption event and the engineering requirement on a machine's Bill of Materials (BOM), ensuring 100% accountability from vendor batch to finished product.

---

## Retrieve This Table When The User Asks About

**Production issuance and traceability chains**
Work order parts or job material consumption. Identifying exactly "Where did this component come from?" for a specific machine.

**Vendor batch and receipt auditing**
Tracing a physical part inside a machine back to its original vendor receipt (receive_id) or purchase order (commercial link). Auditing physical receipt dates for all internal components of a unit.

**Technical and financial accountability**
Identifying the "Actual Consumption Amount" of materials used to satisfy an assembly step. Marrying logistics (Goods Issues) with engineering (Unit BOMs) and assets (Units).

---

## Co-Retrieved Sibling Tables
- `unit_bom_records` — the "As-Built" BOM line being satisfied.
- `units` — the machine receiving the part.
- `inventory_items` — the specific physical stock record.
- `goods_issue_line_items` — the logistics withdrawal event.
- `purchase_orders` — the commercial contract used to buy the material.
- `receives` — the vendor receipt where the part arrived.
