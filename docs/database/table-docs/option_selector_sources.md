# `option_selector_sources`

## Searchable Aliases
selection inputs, configuration sources, mapping origins

## Description
The `option_selector_sources` table defines the **Technical Criteria** required to trigger an automated product upgrade or option selection. It monitors the specifications of a "Base Item" (e.g., "Environment: Outdoor"). When a product matching these criteria is added to an order, the **Lyndom** (the current PostgreSQL ERP) logic engine uses this table to identify which `option_selector` should be activated.

## ⚠️ SQL-Critical Behaviors
- **Input Criteria**: Matches a base product's `category_id`, `specification_id`, and `value` to find a valid option rule.
- **Dependency Chains**: Like service selectors, this allows for technical selections to automatically drive the inclusion of necessary physical add-ons.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| option_selector_id | uuid | no | — | Foreign key to `option_selectors.id`. |
| category_id | uuid | no | — | The base product category being monitored. |
| specification_id | uuid | no | — | The specific attribute being monitored (e.g., "Mounting Type"). |
| spec_name | text | no | — | Denormalized attribute name. |
| value | text | no | — | The value required to trigger the upgrade rule. |
| unit | text | no | — | The unit associated with the trigger value. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| option_selector_id | option_selectors | id | cascade |
| category_id | categories | id | cascade |
| specification_id | specifications | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find if a specific item (by technical specs) triggers any option rule
SELECT option_selector_id 
FROM option_selector_sources 
WHERE category_id = '<cat_uuid>' AND specification_id = '<spec_uuid>' AND value = '<val>';
```

## Indexes
- *Includes indexes on category_id, selector_id, and specification_id for performance.*
