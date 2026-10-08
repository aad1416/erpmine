# variants

## Purpose
The commercial variation registry for product categories. It defines the available feature selections (e.g., Color, Size, Finish) that lead to unique SKU listings, allowing different branches to offer different commercial options for the same category.

---

## Retrieve This Table When The User Asks About

**Commercial choices and attribute options**
Feature selections or product types available for a specific category at a branch. Identifying the global list of valid "Answers" (e.g., Red, Blue, Steel) for a variation question (e.g., Color, Material).

**Commercial divergence and pricing**
Identifying commercial distinctions that drive price differences between otherwise identical products. Finding valid picklists for commercial options within a store.

---

## Co-Retrieved Sibling Tables
- `categories` — the product taxonomy these variations apply to.
- `stores` — the branch offering the variations.
- `item_store_variants` — the specific selection made for a branch SKU.
