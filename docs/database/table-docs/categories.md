# `categories`

## Searchable Aliases
classification, types, groups, taxonomy, product family, department, sorting

## Description
The `categories` table is the hierarchical foundation of the **Lyndom** (the current PostgreSQL ERP) product catalog. It defines the tree-based taxonomy used to organize products, services, and technical components. ⚠️ **This table is strictly for product and item taxonomy; it does NOT categorize clients or customer membership levels.** Beyond simple grouping, categories in **Lyndom** (the current PostgreSQL ERP) carry heavy configuration logic: booleans like `item_config_is_assembly` or `item_config_is_warranty` determine the functional behavior of every item linked to that category. This table also supports sophisticated multi-tenant synchronization through `id_in_other_stores`, allowing a master category to be mapped to its "cloned" versions in different branches. Additionally, some categories originated from **Phocuss** (legacy MongoDB ERP) during migration. Examples of actual values include `Assembly`, `Central Emergency Lighting Systems`, and `Application-Specific & Compliance Products`.

## ⚠️ SQL-Critical Behaviors
- **Type Inheritance**: The `item_config_...` flags (e.g., `is_assembly`, `is_service`) drive application behavior. An item in a category where `item_config_is_assembly = true` will automatically be treated as a manufactured job record with a Bill of Materials.
- **Shadow Categories**: If `is_shadow = true`, the category is likely hidden from the public-facing storefront and used only for internal technical classification or system-level grouping.
- **Cross-Store Mapping**: The `id_in_other_stores` JSONB uses a `{ "store_id": "category_id" }` pattern. This is critical for synchronizing product catalog changes across the multi-tenant landscape.
- **Manufacturing Role**: If `manufacturing_category = true`, the category is explicitly identified as a production unit, often linked to specialized manufacturing instructions.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| store_id | uuid | yes | — | The branch this category belongs to (can be NULL for global/master categories). |
| name | text | no | — | Primary display name. Examples of actual values include: `Assembly`, `HI`, `EMB`. |
| alternative_name | text | no | '' | Secondary name (often used for internationalization or legacy aliases). |
| alternative_description | text | yes | — | Secondary description for technical or region-specific use. |
| description | text | yes | — | Main category description. |
| level | int4 | no | 0 | Depth in the tree (0 = Root). |
| parent_category_id | uuid | yes | — | Self-reference to `categories.id` for nesting. |
| parent_category_name | text | yes | — | Denormalized name of the parent for faster display. |
| reference_category_id | uuid | yes | — | Links a "cloned" category back to its original master definition. |
| creator_id | uuid | no | — | The user who registered this category. |
| product_line | bool | no | false | If `true`, this node represents a major commercial product family (e.g., "Lighting Systems"). |
| manufacturing_category | bool | no | false | If `true`, items here are treated as production units requiring job records and BOMs. |
| order | int4 | no | 1 | Numeric rank of the category among its immediate siblings. |
| display_order | text | no | '' | **WBS Path**: A dot-notated or hyphenated string (e.g., `1-2-1`) defining the category's exact position in the hierarchy. |
| is_shadow | bool | no | false | **Logistical Ghost Node**: If `true`, the category is used for internal classification/logic and is hidden from the storefront UI. |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| metadata | jsonb | no | `{}` | Extensible data including CMS assets (e.g., image URLs, banners). |
| id_in_other_stores | jsonb | no | `{}` | ⚠️ **Sync Map**: `{ "store_id": "category_id" }`. Maps this category to its counterparts in other branches. |
| item_config_is_option | bool | no | false | If `true`, items in this category are considered configurable upgrades/options. |
| item_config_is_service | bool | no | false | If `true`, items here are non-physical (e.g., Labor, Maintenance). |
| item_config_is_warranty | bool | no | false | If `true`, items here represent product guarantee periods. |
| item_config_is_assembly | bool | no | false | If `true`, items here are built from multiple parts (BOM required). |
| item_config_is_spare_parts | bool | no | false | If `true`, items here are individual components for repair/maintenance use. |
| pricing | jsonb | no | `[]` | Placeholder for category-level markup or discount rules. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | set null |
| parent_category_id | categories | id | set null |
| reference_category_id | categories | id | set null |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| items | category_id | The primary classification for an item master record. |
| specifications | category_id | Defines which technical specs apply to items in this category. |
| variants | category_id | Defines valid variations (e.g., Color, Size) for this category. |

## Common Query Patterns
```sql
-- List all top-level (root) categories for a specific store
SELECT name FROM categories WHERE level = 0 AND store_id = '<uuid>';

-- Find all sub-categories for a specific parent
SELECT name FROM categories WHERE parent_category_id = '<parent_uuid>';

-- Check for categories linked to a master category via sync maps
SELECT name FROM categories WHERE id_in_other_stores ? '926267f3-650e-4816-a1e8-1881cd8801eb';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| created_at | btree | Sorting by age. |
| name | btree | Searching/Suggesting categories in UI. |
| parent_category_id | btree | Expediting tree-traversal queries. |
