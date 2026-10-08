# `specifications`

## Searchable Aliases
attribute registry, technical fields, engineering parameters, datasheet keys

## Description
The `specifications` table defines the technical attributes (e.g., "Voltage", "Frequency", "Power Rating") that can be assigned to items within a specific category. While the `categories` table provides the hierarchy, `specifications` provide the technical "schema" for items. Each specification is tied to a data type (String, Number, or Boolean) and can optionally store a list of valid values or units (e.g., `VAC`, `Hz`) in the `values` JSONB field. Examples of actual values include `Power Rating`, `Secondary Voltage`, and `Frequency`.

## ⚠️ SQL-Critical Behaviors
- **Attribute Scoping**: Specifications are linked to a `category_id`. When querying for an item's technical datasheet, you must first resolve which specifications are active for its category.
- **Unit Management**: The `values` JSONB column often stores an array of available options with units (e.g., `[{"unit": "VAC", "value": "277"}]`). This ensures that technical values are entered consistently across items.
- **Primary Attributes**: If `is_primary = true`, the specification is likely used for high-level filtering, search results, or summary displays in the UI.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| scope | enum | no | — | **Specification Scope**. Examples of actual values include: `STORE`, `GLOBAL`. |
| store_id | uuid | yes | — | Foreign key to `stores.id` (if scope is STORE). |
| name | text | no | — | Technical attribute name. Examples of actual values include: `Power Rating`, `Secondary Voltage`, `Frequency`. |
| description | text | yes | — | Optional context for the attribute (e.g., "Automatically Created"). |
| type | enum | no | — | **Type**: `STRING`, `NUMBER`, `BOOLEAN`. |
| values | jsonb | yes | — | ⚠️ **Picklist/Units**: Stores an array of valid options and their units. Examples of actual values include: `[{"unit": "VAC", "value": "277"}]`. |
| category_id | uuid | no | — | Foreign key to `categories.id`. |
| is_primary | bool | no | false | If `true`, this is a key attribute for search and filtering. |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| creator_id | uuid | no | — | The user who registered this specification. |

## Enums Used

### `specification_scope_enum`
- `GLOBAL`: Specification available system-wide.
- `STORE`: Specification scoped to a specific branch.

### `specification_type_enum`
- `STRING`: Alphanumeric text.
- `NUMBER`: Numeric value (useful for range filtering).
- `BOOLEAN`: Yes/No flag.

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | set null |
| category_id | categories | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| item_specifications | specification_id | Links a specific value to an item master record. |
| item_store_specifications | specification_id | Links a specific value to a store-local SKU record. |

## Common Query Patterns
```sql
-- Find all specifications defined for a specific category
SELECT name, type, "values" 
FROM specifications 
WHERE category_id = '<category_uuid>' AND is_active = true;

-- List all "primary" technical attributes for a store
SELECT name 
FROM specifications 
WHERE store_id = '<store_uuid>' AND is_primary = true;
```

## Indexes
- *Uses default PK and FK constraints.*
