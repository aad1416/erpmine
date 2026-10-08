# required_items

## Purpose
The shortage intelligence engine. It acts as the central "To-Buy" or "To-Build" launchpad, identifying inventory deficits where available stock is insufficient to meet customer commitments or reorder thresholds.

---

## Retrieve This Table When The User Asks About

**Inventory shortages and missing parts**
Needed components, stock requirements, or procurement triggers. Identifying SKUs that have fallen below their reorder point (trigger quantity) or have more allocated units than on-hand stock.

**Procurement prioritization**
Generating a prioritized list of items that need to be ordered from vendors or built in production to satisfy customer demand. Identifying the required quantity (deficit) for a branch SKU.

**Demand traceability and impact**
Identifying which specific Sales Orders or customers are waiting for a particular shortage. Tracking technical details of specific production units causing the demand.

**Sourcing for shortages**
Finding the preferred vendor and lead time for required items to facilitate fast Purchase Order generation.

---

## Co-Retrieved Sibling Tables
- `item_stores` — the branch SKU with the shortage.
- `sales_orders` — the customer contracts driving the demand.
- `vendors` — the supplier who can provide the missing parts.
- `uoms` — the packaging units for the requirement.
