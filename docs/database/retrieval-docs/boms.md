# boms

## Purpose
The master manufacturing recipe and assembly blueprint. It defines the structural versioning of a product, serving as the version-controlled container for components required to build a finished good.

---

## Retrieve This Table When The User Asks About

**Assembly blueprints and recipes**
Bill of materials, product design, or engineering recipes. Identifying how a finished product is structured. Finding the active engineering version (Revision A, B, etc.) for a manufactured SKU.

**BOM versioning and revisions**
Tracking design iterations and history. Finding "Revision NR" or "Revision A" for a product. Identifying the current active recipe used for new production jobs.

**Manufacturing cost rollups**
Finding the total material cost of an assembly based on its constituent parts. Identifying the number of component lines (record count) in a design.

**Parametric and variable assemblies**
Identifying parametric templates (matrices) where component quantities scale based on custom engineering inputs (e.g., enclosure height).

---

## Co-Retrieved Sibling Tables
- `bom_records` — the individual parts and quantities in the recipe.
- `item_stores` — the specific branch SKU produced by the BOM.
- `units` — physical machines built using this blueprint.
- `users` — the engineer who defined the design.
