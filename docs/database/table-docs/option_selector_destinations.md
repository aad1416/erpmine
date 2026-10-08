# `option_selector_destinations`

## Searchable Aliases
selection targets, config outputs, mapping destinations

## Description
The `option_selector_destinations` table defines the **"Automatic Add-on"** result of a configuration rule. While `option_selector_sources` defines the "Trigger" (e.g., "If the product is for High Altitude"), this table defines the **Technical Identity** of the physical component that the **Lyndom** (the current PostgreSQL ERP) system should automatically attach to the order.

Instead of pointing to a static Item ID (which could be discontinued), this table points to a **Technical Profile** (Category + Specification + Value). This ensures that the engine always finds the correct, currently active product variant that matches the engineering requirements.

## ⚙️ The Configuration Workflow
1.  **Trigger**: A sales rep adds a "Base Item" to a quote (e.g., a Power Inverter).
2.  **Logic Match**: The system checks `option_selector_sources` and finds that a rule is triggered (e.g., "Mounting: Wall-Mount").
3.  **Technical Discovery**: The system looks at this table (`option_selector_destinations`) to find the **Technical Profile** of the required add-on (e.g., "Category: Bracket Systems, Compatibility: Series-A").
4.  **Auto-Append**: The system scans the warehouse for an item matching that profile and automatically appends it to the sales order.

## ⚠️ SQL-Critical Behaviors
- **Decoupled Identity**: This table is the "Output" of the logic engine. It does not contain Item IDs. It uses `category_id` and `specification_id` to discover the correct item at runtime.
- **Dynamic Catalog**: This design allows a business to replace an old part with a newer SKU without rewriting hundreds of selection rules, as long as the technical specifications on the new item match.

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Rule registration timestamp. |
| updated_at | timestamptz | no | — | Rule modification timestamp. |
| option_selector_id | uuid | no | — | Link to the parent rule header in `option_selectors.id`. |
| category_id | uuid | no | — | The target category where the system should look for the add-on item. |
| specification_id | uuid | no | — | The technical attribute used to identify the upgrade (e.g., "Enclosure Type"). |
| spec_name | text | no | — | Denormalized name of the attribute (redundant for fast UI display). |
| value | text | no | — | The required value the add-on item must have to be valid for this rule. |
| unit | text | no | — | The technical unit associated with the value (e.g., "VAC", "Watts"). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| option_selector_id | option_selectors | id | cascade |
| category_id | categories | id | cascade |
| specification_id | specifications | id | cascade |

## Common Query Patterns
```sql
-- Find the technical criteria for an automated upgrade add-on
SELECT category_id, specification_id, value 
FROM option_selector_destinations 
WHERE option_selector_id = '<uuid>';
```

## Indexes
- *Uses composite indexes on `option_selector_id` and `category_id` to expedite the "Discovery" phase of the configurator.*
