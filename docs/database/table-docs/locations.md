# `locations`

## Searchable Aliases
bins, aisles, warehouse zones, storage areas, shelf names, inventory addresses

## Description
The `locations` table defines parallel physical zones within **Lyndom** (the current ERP). These range from broad areas like a "Warehouse" to granular bin codes like "G1-4 2025". This table is a critical anchor for inventory and production; every movement of goods is tracked against a `location_id`. Additionally, many records contain the description "Add From Phocuss", highlighting that these zones were migrated from the legacy **Phocuss** (Legacy MongoDB ERP) environment during the system transition. Examples of actual values include: `Default-Location`, `SHIPPING 2025`.

## ⚠️ SQL-Critical Behaviors
- **Tenant Isolation**: Locations are strictly scoped to a `store_id`. You cannot move inventory to a location belonging to a different store.
- **Hierarchy Support**: The table contains `parent_location_id` and `parent_location_name` to support nested structures (e.g., Bin "A1" inside "Warehouse 1"), though current production data primarily utilizes a flat structure.
- **Inventory Tracking**: To calculate the stock levels for a store, you must aggregate inventory quantities across all `locations` linked to that `store_id`.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| name | text | no | — | Human-readable name or code. Examples of actual values include: `Default-Location`, `SHIPPING 2025`. |
| description | text | yes | — | Additional context. Examples of actual values include: `Add From Phocuss`. |
| parent_location_name | text | yes | — | Name of the parent zone (denormalized for display). |
| parent_location_id | uuid | yes | — | Foreign key to `locations.id` (self-reference for hierarchy). |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| creator_id | uuid | no | — | The user who defined this location. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| parent_location_id | locations | id | set null |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| item_inventories | location_id | Tracks which specific bin/zone holds the stock. |
| stock_transfers | from_location_id | The source of an inventory move. |
| stock_transfers | to_location_id | The destination of an inventory move. |

## Common Query Patterns
```sql
-- List all active storage bins/locations for a specific store
SELECT name, description 
FROM locations 
WHERE store_id = '<store_uuid>' AND is_active = true;

-- Find inventory levels specifically in the Shipping area
SELECT i.quantity, it.name 
FROM item_inventories i
JOIN locations l ON i.location_id = l.id
JOIN items it ON i.item_id = it.id
WHERE l.name LIKE 'SHIPPING%';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| created_at | btree | Sorting locations by age. |
| is_active | btree | Filtering for active zones. |
| name | btree | Searching/Suggesting locations in UI. |
| parent_location_id | btree | Building hierarchical location trees. |
| store_id | btree | Primary partitioning by business branch. |


