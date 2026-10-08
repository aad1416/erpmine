# `leadtimes`

## Searchable Aliases
delivery estimates, procurement delays, shipping times, vendor wait times, arrival dates

## Description
The `leadtimes` table is a reference lookup that stores standardized durations (in days) for various business processes inside **Lyndom** (Current ERP), such as production cycles or shipping windows. By using named leadtimes (e.g., "1 week"), the system can programmatically calculate expected completion dates. Examples of actual values include `1 week` (7 days) and `30` (30 days).

## ⚠️ SQL-Critical Behaviors
- **Date Arithmetic**: The `value` (integer) represents the number of days to be added to a start date (e.g., Order Date + Leadtime = Expected Delivery Date).
- **Phocuss Import**: The `isimported` flag indicates if the leadtime was migrated from the legacy **Phocuss** (Legacy MongoDB ERP) system during the initial setup of **Lyndom**.
- **Tenant Scoping**: Leadtimes are specific to each `store_id`, allowing different branches to define their own operational speeds.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Update timestamp. |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| name | text | no | — | Human-readable name. Examples of actual values include: `1 week`, `30`. |
| value | int4 | no | 1 | The duration in **days**. |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| creator_id | uuid | no | — | The user who registered this leadtime. |
| isimported | bool | no | false | If `true`, this record was migrated from the legacy **Phocuss** ERP. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| items | purchase_leadtime_id | Standard time needed to receive this item from a vendor. |
| items | production_leadtime_id | Standard time needed to manufacture this item. |

## Common Query Patterns
```sql
-- List all active leadtimes for a store
SELECT name, value 
FROM leadtimes 
WHERE store_id = '<store_uuid>' AND is_active = true;

-- Find the expected delivery date based on a specific leadtime
SELECT current_date + INTERVAL '1 day' * l.value as expected_date
FROM leadtimes l
WHERE l.name = '1 week';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| created_at | btree | Sorting by registration date. |
| is_active | btree | Filtering for active leadtimes. |
| name | btree | Lookup/Select leadtime by name. |


