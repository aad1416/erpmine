# item_store_variants

## Purpose
The junction for assigning commercial variation values to a specific branch SKU. It records the exact selection (e.g., Color: Red) for an item listing, facilitating the creation of unique SKU identities based on finish, material, or color.

---

## Retrieve This Table When The User Asks About

**Product variations and SKU options**
Color/size variants or item model selections for a particular branch SKU. Identifying exactly which commercial version of a product was listed or sold.

**SKU identity and feature selection**
Establishing a unique commercial identity for an item based on its selected variants. Ensuring customers receive the exact commercial version (e.g., finish or material) they selected during quoting.

---

## Co-Retrieved Sibling Tables
- `item_stores` — the branch SKU being defined.
- `variants` — the available commercial options.
