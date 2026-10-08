# goods_issues

## Purpose
The official consumption registry for inventory. It records the physical removal (issuance) of parts from the warehouse to satisfy an internal demand, such as a manufacturing build or a field service repair.

---

## Retrieve This Table When The User Asks About

**Inventory waste, disposal, and scrap write-offs**
Items thrown away, scrapped, written off, or discarded from warehouse stock. General inventory disposal events not related to machine repair. Monthly waste totals and reasons given for discarding items.

**Material release and stock withdrawal**
Warehouse exit events, parts release, or component issuance. Recording the physical removal of inventory from the shelf for consumption.

**Fulfillment of part requests**
Identifying which formal requisition (part request) was satisfied by an issuance. Tracking the time elapsed between a request and the actual fulfillment (issuance).

**Service and commercial consumption targets**
Identifying if parts were issued for a specific sales order (e.g., for a unit build) or a field service ticket (e.g., for a repair). Tracking material consumption against specific customer projects or service events.

**Issuance responsibility and auditing**
Identifying the staff member who physically picked the parts (the picker/issuer) and the user who registered the digital record. Providing an audit trail for inventory depletion.

**Financial COGS baseline**
Establishing the official "Date of Consumption" used for monthly financial Cost of Goods Sold (COGS) reporting and valuation.

---

## Co-Retrieved Sibling Tables
- `goods_issue_line_items` — the individual SKUs and serial numbers withdrawn.
- `part_requests` — the formal requisition that triggered the issue.
- `sales_orders` — the commercial contract parts were issued for.
- `field_service_tickets` — the repair job parts were issued for.
- `users` — the picker (`issuer_id`) or the creator of the record.
