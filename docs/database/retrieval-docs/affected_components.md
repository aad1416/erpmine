# affected_components

## Purpose
The part swap and repair history. It records the technical fate of physical components during machine upgrades or maintenance—documenting whether a part was newly installed, replaced, repaired, or discarded.

---

## Retrieve This Table When The User Asks About

**Part swap history and component impacts**
Assembly or repair logs. Identifying what happened to a physical part (inventory item) during a machine's lifecycle.

**Reliability engineering and component scrap auditing (during machine repair)**
Finding which specific component models are being discarded or replaced most frequently **during machine upgrades or maintenance events**. Auditing failure trends across a product category. NOTE: For general inventory waste or items thrown away from warehouse stock, use `goods_issues` instead.

**Unit internal "DNA" and maintenance**
Listing all components that have been replaced on a specific serial number (unit). Synchronizing part changes with the machine's "Build List" (unit_bom_records).

**Technical fate tracking**
Determining if a failed part was kept for testing (REPLACED), thrown away (DISCARDED), or fixed (REPAIRED).

---

## Co-Retrieved Sibling Tables
- `inventory_items` — the specific physical piece of hardware.
- `unit_bom_records` — the machine's build manual line being satisfied.
- `units` — the physical asset serial number being repaired.
- `users` — the technician who logged the part's fate.
