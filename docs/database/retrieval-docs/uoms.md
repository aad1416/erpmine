# uoms

## Purpose
The management system for units of measure and quantity conversion. It defines how products are counted, packaged, and billed, ensuring accurate inventory balances when buying and selling in different increments (e.g., each, box, pair).

---

## Retrieve This Table When The User Asks About

**Units of measure and quantity types**
Measurement units or billing increments for a specific branch SKU. Identifying the "Main" (base) unit of measure for an item's core inventory balance.

**Unit conversion and packaging**
Calculating quantities across different buying and selling units (e.g., converting boxes to pieces) using numeric coefficients. Finding valid packaging options (e.g., Roll, Case) for a product.

**Default transaction units**
Identifying the pre-selected or default unit of measure used in purchasing or sales forms for a particular item.

---

## Co-Retrieved Sibling Tables
- `item_stores` — the specific branch SKU these units apply to.
- `sales_order_line_items` — the unit used in a customer sale.
- `purchase_order_line_items` — the unit used in a vendor purchase.
