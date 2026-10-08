# `items`

## Searchable Aliases
global catalog, master product list, generic items, sku registry, technical assets

## Description
The `items` table serves as the global **Item Master (Blueprint)** for the **Lyndom** (the current PostgreSQL ERP) system. It stores the static, cross-store characteristics of a product—such as its name, technical description, physical dimensions, and barcode. Crucially, this table contains the `no` column (Unique Business Number), which acts as the primary integration key for mapping **Lyndom** (the current PostgreSQL ERP) entities to the legacy **Phocuss** (legacy MongoDB ERP) file manager and external catalogs. Unlike `item_stores`, which handles branch-specific pricing and inventory, the `items` table maintains the "One Source of Truth" for what the product *is*.

## ⚠️ SQL-Critical Behaviors
- **Blueprint vs. SKU**: This table does NOT store cost, price, or inventory levels. Those are stored in the child `item_stores` table.
- **Unique Mapping Key**: The `no` column is the bridge between **Lyndom** (the current PostgreSQL ERP) and **Phocuss** (legacy MongoDB ERP). It is used to fetch external documentation and images from the legacy storage system.
- **Privacy Controls**: If `is_private = true`, the item master may be restricted to the originating store or specific user groups, preventing it from appearing in the global catalog.
- **Physical Metadata**: Columns like `weight` and `length` are essential for calculating freight costs in the Sales and Purchasing modules.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| store_id | uuid | yes | — | The store that originally registered this master record. |
| no | text | no | — | ⚠️ **Unique Business Number**: The global identifier used for cross-system mapping between **Lyndom** (the current PostgreSQL ERP) and **Phocuss** (legacy MongoDB ERP). |
| name | text | no | — | Global product name. |
| description | text | no | — | Detailed technical description. |
| category_id | uuid | yes | — | Foreign key to `categories.id`. |
| barcode | text | no | — | Standard UPC/EAN or internal barcode string. |
| length | numeric(10,2) | yes | — | Physical length. |
| width | numeric(10,2) | yes | — | Physical width. |
| height | numeric(10,2) | yes | — | Physical height. |
| length_unit | text | yes | — | Unit of measure for dimensions (e.g., "in", "cm"). |
| weight | numeric(10,2) | yes | — | Physical weight. |
| weight_unit | text | yes | — | Unit of measure for weight (e.g., "lb", "kg"). |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| is_private | bool | no | false | If `true`, the item is excluded from the global catalog. |
| creator_id | uuid | no | — | The user who created this master record. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | set null |
| category_id | categories | id | set null |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| item_stores | item_id | Links the global blueprint to a store-specific SKU. |
| item_specifications | item_id | Assigns technical spec values to this global master. |

## Common Query Patterns
```sql
-- Search for a product by its unique business number
SELECT name, description FROM items WHERE no = 'VPI-a-a';

-- Find all items belonging to a specific category
SELECT name FROM items WHERE category_id = '<category_uuid>';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| barcode | btree | Fast lookup via scanning. |
| category_id | btree | Grouping items by taxonomy. |
| is_active | btree | Filtering out discontinued blueprints. |
| name | btree | UI search by product name. |
| no | btree | Core lookup by unique business ID. |
| store_id | btree | Filtering items by their origin branch. |
