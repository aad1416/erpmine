# items

## Purpose
The global item master and product blueprint. It stores the static, cross-store characteristics of a product, serving as the "One Source of Truth" for what a product is, independently of branch-specific pricing or inventory levels.

---

## Retrieve This Table When The User Asks About

**Global product catalog and registry**
Master product list, generic items, or technical asset blueprints. Finding a product's global name, technical description, or physical dimensions (weight, height, length) for logistics planning.

**Cross-system mapping and legacy data**
Searching for products using their unique business number (the "no" column) to link Lyndom records to legacy Phocuss (MongoDB) files or external catalogs. Fetching global identifiers for integration.

**Product taxonomy and barcodes**
Finding products by their global barcode (UPC/EAN). Identifying which technical category or product family a blueprint belongs to. 

**Privacy and visibility**
Identifying private items excluded from the global catalog or restricted to specific branches. Tracking who registered the master record for a product.

---

## Co-Retrieved Sibling Tables
- `item_stores` — the branch-specific SKU listings derived from this blueprint.
- `categories` — the product taxonomy node.
- `item_specifications` — the technical datasheet (DNA) for the product.
- `item_types` — the high-level classification (e.g., Assembly vs Service).
