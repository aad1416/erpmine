# item_types

## Purpose
The high-level ERP classification registry. It determines the functional behavior of products and services—such as whether they require a Bill of Materials (BOM) or bypass inventory tracking—at a fundamental organizational level.

---

## Retrieve This Table When The User Asks About

**Product classification and behavior**
Component types or material types. Identifying if an item is an Assembly (requiring production), a Service (bypassing stock), or an Option (configurable upgrade).

**Workflow rules and system defaults**
Identifying system-protected types with reserved application logic. Scoping classification rules to specific branches or stores.

---

## Co-Retrieved Sibling Tables
- `items` — the product masters assigned these types.
- `stores` — the branch where these classifications are active.
