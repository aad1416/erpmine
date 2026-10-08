# vending

## Purpose
The Vendor-Specific Item registry. It manages the relationship between branch SKUs and their various supply sources, tracking the supplier's part numbers, quoted costs, and replenishment lead times for procurement automation.

---

## Retrieve This Table When The User Asks About

**Sourcing details and vendor SKUs**
Supplier-specific part numbers and quoted purchase costs for a product. Finding the expected replenishment delay (lead time) for a vendor source.

**Multi-sourcing and vendor comparison**
Comparing different suppliers for the same internal SKU based on price and delivery speed. Identifying approved vs inactive sources for a product.

**Preferred supplier selection**
Identifying the primary (preferred) source for automated reordering. Using vendor data to suggest where to buy stock when a shortage occurs.

**Active supplier contracts and agreements**
Counting or listing active sourcing relationships with a supplier (is_active = true records). Identifying which vendors currently have approved, active supply agreements for a branch. Checking whether a supplier is a currently active or inactive source.

---

## Co-Retrieved Sibling Tables
- `item_stores` — the internal branch SKU being sourced.
- `vendors` — the global supplier providing the goods.
- `vending_cost` — the historical log of purchase prices for this source.
- `users` — the procurement officer managing the link.
