# receive_line_items

## Purpose
The itemized record of specific products and quantities that physically arrived during a receiving event. it provides the granular evidence needed to update warehouse stock levels and close out procurement contract lines.

---

## Retrieve This Table When The User Asks About

**Received items and incoming parts**
Stock intake details, warehouse arrival specifics, or shipment receipt details for a particular SKU. Identifying exactly what arrived in a specific receiving voucher or box.

**Fulfillment accuracy and short-ships**
Identifying if the physical count (quantity) matches the purchase order requirement. Detecting vendor delivery inaccuracies or short-ships.

**Arrival history and stock transformation**
Finding all arrival dates and quantities for a specific product. Tracking the transformation of receiving info into new physical stock records in inventory.

---

## Co-Retrieved Sibling Tables
- `receives` — the parent warehouse voucher header.
- `purchase_order_line_items` — the source requirement being satisfied.
- `item_stores` — the branch SKU being incremented.
- `inventory_items` — the resulting stock-on-hand records.
