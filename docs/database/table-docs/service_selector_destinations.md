# `service_selector_destinations`

## Searchable Aliases
fee targets, automatic service selection, labor mapping

## Description
The `service_selector_destinations` table defines the **Automated Service Result** that should be selected when a service rule is triggered. Instead of hard-coding a specific labor item, this table defines the **Technical Profile** of the service (e.g., "Category: Labor, Skill: Installation"). 

This allows the **Lyndom** (the current PostgreSQL ERP) logic engine to dynamically match the correct non-physical item—such as an extended warranty or installation fee—to a physical product based on their shared specifications.

## ⚙️ The Service Attachment Workflow
1.  **Selection**: A sales rep adds a physical product to a quote (e.g., a 10kW Generator).
2.  **Trigger (Source)**: The system checks `service_selector_sources`. Does this item match a rule? (e.g., "Is 10kW?").
3.  **Discovery (Destination)**: If yes, the system looks at this table to find the **Technical Blueprint** for the required service (e.g., "Category: Maintenance, Plan: Standard").
4.  **Auto-Select**: The system scans the current catalog for an active Service SKU that matches that technical blueprint and automatically appends it to the sales order as a new line item.

## ⚠️ SQL-Critical Behaviors
- **Flexible Maintenance**: By defining services via technical specs rather than specific IDs, a business can change its service pricing or item names without breaking the global selection logic.
- **Mandatory Labor**: Through the `is_mandatory` flag, the system can ensure that safety-critical services (like Commissioning) cannot be removed from an order by a sales rep.

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Rule registration timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| service_selector_id | uuid | no | — | Link to the parent rule header in `service_selectors.id`. |
| category_id | uuid | no | — | The target category where the system should look for the service item. |
| specification_id | uuid | no | — | The attribute used to identify the matching service item (e.g., "Service Level"). |
| spec_name | text | no | — | Denormalized attribute name for faster front-end rendering. |
| value | text | no | — | The required value the service item must possess to be selected. |
| unit | text | no | — | The technical unit associated with the service value (e.g., "Hours", "Years"). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| service_selector_id | service_selectors | id | cascade |
| category_id | categories | id | cascade |
| specification_id | specifications | id | cascade |

## Common Query Patterns
```sql
-- Discover which service profile is required for a triggered rule
SELECT category_id, specification_id, value 
FROM service_selector_destinations 
WHERE service_selector_id = '<uuid>';
```

## Indexes
- *Uses default PK and FK constraints, with optimized indexing on `service_selector_id` and `category_id`.*
