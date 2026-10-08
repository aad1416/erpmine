# item_stores

## Purpose
The operational SKU registry for specific branches. It manages the business logic for a product at a particular store or warehouse, including pricing, inventory availability, replenishment rules, and manufacturing costs.

---

## Retrieve This Table When The User Asks About

**Branch-specific catalog and SKUs**
Local products, store items, or branch inventory listings. Searching for items using their local warehouse part number (SKU number). Tracking display names and descriptions localized for a specific branch.

**Inventory availability and stock levels**
Total physical stock (on-hand quantity) vs available stock ready for sale (on-hand minus allocated). Monitoring reserved stock (allocated quantity) and incoming stock on order from vendors. Identifying low-stock alerts and replenishment triggers.

**Selling prices and promotions**
List prices, tiered pricing rules, or promotional sale prices for a branch item. Identifying which items are currently on sale or marked for promo.

**Inventory valuation and costing**
FIFO inventory asset values and total dollar value of physical stock. Calculating gross margin basis by comparing list price against total cost (parts + labor + overhead). Identifying manual cost overrides.

**Replenishment and sourcing**
Lead time estimates for stock arrival. Reorder quantities and trigger levels for automated procurement. Identifying the preferred vendor and their specific catalog SKU for a branch product.

**Lifecycle and approval gates**
Soft-deleted or archived SKUs. Commercial gates like sales approval or shipping approval (Quality Control). Identifying obsolete or R&D-only items.

**Functional classification and behavior**
Identifying labor vs physical goods (not shippable flag). Finding items used in field service or those that generate physical asset records (units) upon sale. Tracking if an item has a Bill of Materials (BOM) for manufacturing.

---

## Co-Retrieved Sibling Tables
- `items` — the global blueprint for this branch SKU.
- `inventory_items` — the physical units sitting on the shelf.
- `vendors` — the supplier used for replenishment.
- `uoms` — the primary and secondary units of measure.
- `categories` — the taxonomy governing the item's rules.
- `locations` — the default warehouse bin for the product.
