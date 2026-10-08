# `store_configs`

## Searchable Aliases
branch settings, store-level parameters, operational flags, local system settings

## Description
The `store_configs` table holds fine-grained operational parameters that control the business logic for each specific store. Instead of hard-coding values like warranty periods or quote expirations, the ERP retrieves these settings from this table at runtime. This allows the system to support a diverse set of tenants (e.g., one branch might offer a 90-day warranty while another offers a year) within the same technical framework. It also controls critical automation flags, such as whether part requests should be generated automatically during the production cycle.

## ⚠️ SQL-Critical Behaviors
- **1:1 Store Relationship**: Each `stores.id` typically corresponds to exactly one `store_configs` record. To find a store's settings, join on `store_configs.store_id = stores.id`.
- **Automation Flags**: The `auto_generate_part_request` column is a high-impact boolean. If enabled (`true`), the system's backend logic likely triggers the creation of `part_requests` whenever a job record or sales order reaches a certain state.
- **Financial/Legal Defaults**: Columns like `to_be_invoiced_date_days` and `standard_warranty_days` provide the default values for new transactions—users can often override these, but this table provides the starting point.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| default_quote_expiry_days | int4 | no | — | Number of days before a `quote` automatically expires. |
| inventory_item_serial_number_prefix | text | no | '' | Reserved for custom serial number generation (e.g., 'SN-'). |
| auto_generate_part_request | bool | no | false | If `true`, the system automates the inventory procurement request process. |
| to_be_invoiced_date_days | int4 | no | 30 | **Billing Grace Period**. The standard number of days allowed between order/shipment and the expected invoice date (Net Payment Term). |
| standard_warranty_enabled | bool | no | true | Global switch to enable/disable warranty tracking for the store. |
| standard_warranty_days | int4 | no | 365 | Default warranty duration in days (Default is 1 year). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find stores that have auto-generation of part requests enabled
SELECT s.name 
FROM stores s
JOIN store_configs sc ON s.id = sc.store_id
WHERE sc.auto_generate_part_request = true;

-- Check the default warranty period for a specific branch
SELECT standard_warranty_days 
FROM store_configs 
WHERE store_id = '<store_uuid>';
```

## Indexes
- *Uses default PK and FK constraints.*


