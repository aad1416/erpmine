# `item_types`

## Searchable Aliases
product classification, component types, service vs product, material types

## Description
The `item_types` table categorizes products and services at a high organizational level. This classification determines how the system handles an item in transactions and inventory; for example, an "Assembly" likely requires a Bill of Materials (BOM), while a "Service" may bypass inventory tracking entirely. The system uses protected, predefined types to drive core business logic in the manufacturing and sales modules. Examples of actual values include `Option`, `Service`, and `Assembly`.

## ⚠️ SQL-Critical Behaviors
- **System-Default Logic**: Records where `protected = true` (e.g., `Assembly`, `Service`) are critical for application-level logic. Deleting or renaming these roles may break UI workflows that depend on these specific keys.
- **Tenant Isolation**: Even though types like `Service` are standard, they are defined per `store_id`, allowing branches to add their own custom classifications.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Update timestamp. |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| name | text | no | — | Human-readable category name. Examples of actual values include: `Assembly`, `Service`, `Option`. |
| description | text | yes | — | Additional context. |
| protected | bool | no | false | If `true`, this is a system-standard type with reserved logic. |
| creator_id | uuid | no | — | The user who registered this item type. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| items | item_type_id | Determines the functional behavior of the product. |

## Common Query Patterns
```sql
-- Find all physical assemblies that require production
SELECT i.name 
FROM items i
JOIN item_types it ON i.item_type_id = it.id
WHERE it.name = 'Assembly' AND it.store_id = '<store_uuid>';

-- List non-inventory service items (e.g., Labor, Shipping)
SELECT i.name 
FROM items i
JOIN item_types it ON i.item_type_id = it.id
WHERE it.name = 'Service';
```

## Indexes
- *Uses default PK and FK constraints.*


