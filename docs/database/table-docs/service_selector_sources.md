# `service_selector_sources`

## Searchable Aliases
fee triggers, automated labor criteria, service mapping sources

## Description
The `service_selector_sources` table defines the **Technical Criteria** required to trigger a service selection rule. It specifies exactly which physical product specifications (e.g., "Power: 10kW") act as the source for an automation. When an item matching these specifications is added to a quote, the **Lyndom** (the current PostgreSQL ERP) logic engine uses this table to "match" against a valid `service_selector`.

## ⚠️ SQL-Critical Behaviors
- **Input Criteria**: To find which service rule applies to a product, the system queries this table for a record where the product's `category_id`, `specification_id`, and `value` all match.
- **Multiple Conditions**: Multiple source records can be linked to a single `service_selector_id`, typically requiring an "AND" match across all conditions to trigger the rule.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| service_selector_id | uuid | no | — | Foreign key to `service_selectors.id`. |
| category_id | uuid | no | — | The product category being monitored. |
| specification_id | uuid | no | — | The specific attribute being monitored (e.g., "Voltage"). |
| spec_name | text | no | — | Denormalized attribute name. |
| value | text | no | — | The value required to trigger the rule. |
| unit | text | no | — | The unit associated with the trigger value. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| service_selector_id | service_selectors | id | cascade |
| category_id | categories | id | cascade |
| specification_id | specifications | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find if a specific item (by specs) triggers any service selector
SELECT service_selector_id 
FROM service_selector_sources 
WHERE category_id = '<cat_uuid>' AND specification_id = '<spec_uuid>' AND value = '<val>';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| category_id | btree | Fast lookup by product branch. |
| service_selector_id | btree | Linking back to the header rule. |
| specification_id | btree | Finding rules that monitor a specific technical attribute. |
| value | btree | Searching for rules by their trigger value. |
