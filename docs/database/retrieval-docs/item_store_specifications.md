# item_store_specifications

## Purpose
The branch-specific technical profile for specific SKUs. It allows a store to define its own technical values or overrides for an item, ensuring that production and sales are based on the exact configuration sold at the branch level.

---

## Retrieve This Table When The User Asks About

**Branch-specific SKU technical details**
Local item attributes or store product details for a branch-specific SKU. Finding the exact technical configuration (e.g., "Input Voltage", "Frequency") sold by a specific store.

**Production and sales integration**
Providing the source of truth for an item's technical characteristics during the manufacturing and quoting phases. Ensuring the production team builds according to the branch-sold configuration.

**Granular technical filtering**
Searching for branch-specific items matching a technical attribute (e.g., "Find all 60Hz units in this branch").

---

## Co-Retrieved Sibling Tables
- `item_stores` — the branch SKU being specified.
- `specifications` — the technical attributes being answered.
- `item_specifications` — the global blueprint values (fallback).
