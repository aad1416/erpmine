# `stores`

## Searchable Aliases
branches, locations, warehouses, retail shops, tenants, facilities, site information

## Description
The `stores` table is the structural cornerstone of the **Lyndom** (the current PostgreSQL ERP) multi-tenant architecture. Each record represents a distinct physical or logical business entity—such as a retail branch or warehouse. An important feature of this table is its support for a hybrid file management system. Because **Lyndom** (current) and **Phocuss** (legacy MongoDB ERP) use different primary key formats (UUID vs. ObjectID), the system maps assets using shared **Unique Business Numbers**. This allows **Lyndom** to fetch and display files (like PDFs and images) from both its local storage and the legacy **Phocuss** file manager API.

## ⚠️ SQL-Critical Behaviors
- **Tenant Isolation**: This is the most critical filter in the system. Almost every SQL query must include `WHERE store_id = '<uuid>'` to ensure data from one store doesn't leak into another.
- **External File Integration**: The `external_file_manager_url` is a base API endpoint for the **Phocuss** (Legacy ERP) storage system. To retrieve legacy files, the system does not use IDs; instead, it queries this URL using the entity's unique business number (e.g., `item_stores.number`).
- **Soft Deletes**: Use `WHERE is_active = true` to filter out closed or inactive branches.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Timestamp of creation. |
| updated_at | timestamptz | no | — | Timestamp of last update. |
| name | text | no | — | The display name of the store. |
| contact_info_name | text | yes | — | Name of the primary contact person. |
| contact_info_email | text | yes | — | Primary contact email for the branch. |
| contact_info_phone | text | yes | — | Primary contact phone numner. |
| address_info_state | text | no | '' | State/Province. |
| address_info_city | text | no | — | City. |
| address_info_address | text | no | — | Street address. |
| address_info_latitude | numeric(9,6) | yes | — | Geographic latitude. |
| address_info_longitude | numeric(9,6) | yes | — | Geographic longitude. |
| address_info_postal_code | text | yes | — | ZIP/Postal code. |
| address_info_building_number | text | yes | — | Building/Street number. |
| address_info_unit | text | yes | — | Unit/Suite number. |
| website | text | yes | — | Store's website URL. |
| owner_id | uuid | yes | — | Foreign key to `users.id` (Store Manager/Owner). |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| external_file_manager_url | text | yes | — | Base API endpoint for the **Phocuss** (Legacy) file manager. Entries are mapped via unique numbers since Database IDs differ. |
| external_file_manager_token | text | yes | — | Static environment-based authentication token used for authorizing requests to the **Phocuss** storage API. |
| creator_id | uuid | no | — | The user who registered this store. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| owner_id | users | id | set null |
| creator_id | users | id | cascade |

### Referenced By (FK In)

#### 1. Configuration & Access (Functional)
| Table | Column | Meaning |
|-------|--------|---------|
| store_configs | store_id | Detailed operational settings (e.g., invoice days). |
| user_stores | store_id | Defines which users have permission to view this store. |
| departments | store_id | Organizational units within this branch. |

#### 2. Transactional & Data Partitioning (Global)
*The `stores` table is referenced by **90+ other tables** to enforce multi-tenancy. Examples include:*
- `item_stores` (Inventory), `sales_orders`, `purchase_orders`, `shipments`, `invoices`, `clients`, etc.

## Common Query Patterns
```sql
-- Find all active stores with their file manager tokens
SELECT name, external_file_manager_token FROM stores WHERE is_active = true;

-- List stores with missing geographic coordinates
SELECT name, contact_info_email 
FROM stores 
WHERE address_info_latitude IS NULL OR address_info_longitude IS NULL;
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| created_at | btree | Sorting stores by registration date. |
| is_active | btree | Filtering for active branches. |
| name | btree | Search/Filter by store name. |
| owner_id | btree | Finding stores managed by a specific user. |


