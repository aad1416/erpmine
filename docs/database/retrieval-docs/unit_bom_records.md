# unit_bom_records

## Purpose
The "As-Built" bill of materials. It provides the permanent technical DNA of a specific physical machine, documenting exactly which parts and serial numbers are inside a unique unit, even if the master template changes later.

---

## Retrieve This Table When The User Asks About

**Internal configuration and unit ingredients**
As-built components, specific unit ingredients, or build history. Identifying exactly which parts were installed in a particular serial number.

**Technical traceability and quality audits**
Finding all field units containing parts from a specific vendor Purchase Order. Linking physical assets to their procurement history (PO numbers). Tracking the "Deep Traceability" of components across the fleet.

**Complex sub-assemblies (Systems within Systems)**
Navigating hierarchical build records where components have their own sub-parts (parent/child relationships).

**Service and repair reference**
Providing the source of truth for technicians to identify compatible replacement parts for a specific machine in the field. Tracking "Warehouse Consumption" (issued quantity) vs "Engineering Requirement".

---

## Co-Retrieved Sibling Tables
- `units` — the physical serial number being documented.
- `item_stores` — the branch SKU of the internal component.
- `purchase_orders` — the sourcing history for the parts.
