# bom_records

## Purpose
The component itemization ledger. It defines the specific constituent parts, ingredients, and materials required for a master assembly blueprint, ensuring technical integrity through data snapshots of the engineering intent.

---

## Retrieve This Table When The User Asks About

**Materials lists and ingredients**
Parts lists, component details, or sub-assembly ingredients. Identifying exactly what parts are needed for a specific version of a product. Finding the engineering quantity required per single build.

**Manufacturing scaling and batching**
Calculating total parts needed for a batch size. Identifying "Fixed Quantities" that do not scale with production volume (e.g., setup materials).

**Engineering impact and part usage**
Finding all assemblies that use a specific component or SKU (where-used analysis). Auditing the "As-Engineered" snapshot of a part (name/number/description) at the time the revision was created.

---

## Co-Retrieved Sibling Tables
- `boms` — the parent assembly header.
- `item_stores` — the component SKU being used.
- `users` — the engineer who added the part to the bill.
