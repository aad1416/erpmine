# locations

## Purpose
The physical zone registry for the warehouse. It defines everything from broad storage areas to granular bin codes, providing the physical addresses required for tracking inventory movements and production activity.

---

## Retrieve This Table When The User Asks About

**Warehouse zones and bin codes**
Aisles, bins, shelf names, or inventory addresses. Defining storage areas like "Shipping 2025" or "Warehouse 1". Identifying granular shelf codes (e.g., G1-4) where items are kept.

**Storage hierarchy and layout**
Parent zones or nested warehouse structures (e.g., Bin A1 inside Main Warehouse). Organizing the warehouse into logical storage areas for better logistics.

**Branch-level storage maps**
Active storage locations and bins available for a specific store or branch. Identifying which zones are reserved for physical stock vs shipping prep.

---

## Co-Retrieved Sibling Tables
- `inventory_items` — the actual stock sitting in these locations.
- `location_change_logs` — the history of movements between these bins.
- `stores` — the branch that owns these physical zones.
