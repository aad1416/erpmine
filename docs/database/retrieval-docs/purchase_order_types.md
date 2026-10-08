# purchase_order_types

## Purpose
The classification registry for procurement workflows. It defines the categories of buy orders (e.g., Blanket, Sales Order fulfillment, Service) available to a branch, determining the mandatory fields and logic for each order type.

---

## Retrieve This Table When The User Asks About

**Order classification and categories**
Procurement categories, po classification, or procurement models available at a branch. Identifying if a purchase is for a blanket contract, field service, or specific customer order (SO).

**Workflow rules and protected logic**
Identifying system-standard types with reserved logic (e.g., SO-type orders requiring a parent sales order). Determining which workflow rules apply to a purchase based on its type name.

---

## Co-Retrieved Sibling Tables
- `purchase_orders` — the actual buy orders using these classifications.
- `stores` — the branch where these workflows are enabled.
