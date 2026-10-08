# shipment_line_items

## Purpose
The granular record of physical assets inside a shipment. It identifies every unique physical unit (serial number) dispatched to a customer, providing permanent legal proof of exactly which equipment was delivered.

---

## Retrieve This Table When The User Asks About

**Packed items and manifested parts**
Granular lists of parts inside a parcel or container. Identifying exactly which serialized units were dispatched to a customer. Tracking delivery units at the individual serial number level.

**Serialized fulfillment and traceability**
Finding the specific serial number or physical asset record (unit) linked to a shipment. Proving exactly which unit was delivered for future warranty or maintenance claims. 

**Warehouse inspection and quality progress**
Identifying the technical check progress for a specific physical unit before it was shipped. Tracking the warehouse clerk responsible for packing a particular part.

---

## Co-Retrieved Sibling Tables
- `shipments` — the parent parcel or delivery voucher.
- `units` — the physical serialized asset dispatched.
- `item_stores` — the branch SKU being fulfilled.
- `sales_order_line_items` — the commercial contract line being satisfied.
- `shipment_checklists` — the individual QC steps performed for the unit.
