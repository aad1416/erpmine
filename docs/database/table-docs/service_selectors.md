# `service_selectors`

## Searchable Aliases
automated fees, non-physical add-ons, labor rules, service logic

## Description
The `service_selectors` table manages the automation rules for appending non-physical services (e.g., labor, installation, extended warranties) to a sales order or quote. It acts as the "Header" for a logic engine that monitors the technical specifications of physical products being sold. If a product's specifications match the criteria defined in the "Source" tables, the selector automatically identifies and suggests a corresponding service item defined in the "Destination" tables. 

## ⚠️ SQL-Critical Behaviors
- **Service Discovery Header**: This table itself stores only metadata (`label`, `description`). The actual matching logic is stored in its child tables: `service_selector_sources` (The Criteria) and `service_selector_destinations` (The Resulting Service).
- **Rule Scoping**: Each selector is scoped to a `store_id`, allowing branches to automate their own service-attachment rules.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| label | text | no | — | Human-readable name for the selector rule (e.g., "Standard Installation Matcher"). |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| description | text | yes | — | Optional context for the service selection logic. |
| creator_id | uuid | no | — | The user who registered this selector. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| service_selector_sources | service_selector_id | Defines the "If" conditions (Source Specs). |
| service_selector_destinations | service_selector_id | Defines the "Then" result (Destination Specs for a Service Item). |

## Common Query Patterns
```sql
-- List all service selection rules for a store
SELECT label, description FROM service_selectors WHERE store_id = '<uuid>';
```

## Indexes
- *Uses default PK and FK constraints.*
