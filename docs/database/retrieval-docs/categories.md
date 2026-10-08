# categories

## Purpose
The hierarchical foundation of the product catalog. It defines the tree-based taxonomy (Product Families) and carries the configuration logic that determines the functional behavior (e.g., manufacturing vs service) of every item in the system.

---

## Retrieve This Table When The User Asks About

**Product taxonomy and classification**
Product types, groups, or families. Navigating the hierarchy of categories and sub-categories (WBS paths). Finding all categories under a specific parent or branch.

**Configuration logic and behavioral rules**
Identifying categories that require manufacturing (is_assembly flag) or those representing non-physical items like labor and warranties (is_service/is_warranty flags). Determining if items in a category are considered configurable upgrades or spare parts.

**Commercial product lines and storefront layout**
Identifying major commercial product lines (e.g., Lighting Systems). Finding "shadow" categories used for internal technical classification but hidden from the public storefront. 

**Multi-store synchronization**
Mapping categories across different branches using synchronization maps (id_in_other_stores). Tracking master category definitions vs branch-specific clones.

---

## Co-Retrieved Sibling Tables
- `items` — product masters classified under these nodes.
- `specifications` — the technical attributes valid for this category.
- `variants` — the commercial options (e.g., Color/Size) available in this category.
- `stores` — the branch that owns or uses the category.
