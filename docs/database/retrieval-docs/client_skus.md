# client_skus

## Purpose
A mapping layer for B2B product cross-references. It allows the system to store a customer's internal part numbers (SKUs) and names, ensuring they are displayed on transactional documents instead of or alongside internal SKU codes.

---

## Retrieve This Table When The User Asks About

**Customer part numbers and SKUs**
External codes, mappings, or customer-specific item numbers (client SKUs). What the client calls a particular product (item_name, item_no).

**B2B cross-referencing and resolution**
Resolving a customer's internal part number to a branch SKU code (item_store_id). Searching for orders or items using a client's own part number.

**Document localization**
Retrieving client-preferred part numbers for display on printed invoices, packing slips, or quotes for a specific account.

---

## Co-Retrieved Sibling Tables
- `clients` — the customer who owns these part number mappings.
- `item_stores` — the branch-specific product definition being cross-referenced.
