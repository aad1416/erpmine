# `variants`

## Searchable Aliases
attribute options, commercial choices, product types, feature selections

## Description
The `variants` table defines the commercial variations (e.g., "Color", "Size", "Material") available for items within a specific category. While `specifications` track technical and engineering data, `variants` are typically used for commercial distinctions that might lead to different SKU listings at the store level. This table manages the "Question" (e.g., Color), while the `values` JSONB field stores the global list of "Answers" (e.g., Red, Blue, Green) available for that category in a specific branch.

## ⚠️ SQL-Critical Behaviors
- **Store Scoping**: Unlike master categories, variants are strictly scoped to a `store_id`. This allows different branches to offer different variation sets for the same product category (e.g., Branch A offers a product in "Steel", while Branch B offers it in "Aluminum").
- **Commercial Divergence**: Variations are often the key factor in price differences between otherwise identical item masters.
- **Dynamic Options**: The `values` JSONB column stores the valid picklist for the variation.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| category_id | uuid | no | — | Foreign key to `categories.id`. |
| name | text | no | — | The name of the variation (e.g., "Color", "Finish"). |
| values | jsonb | no | — | ⚠️ **Global Options**: A JSON array of valid variations for this category (e.g., `["Red", "Blue", "Black"]`). |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| creator_id | uuid | no | — | The user who registered this variation definition. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| category_id | categories | id | cascade |
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| item_store_variants | variant_id | Assigns a specific value from the variation list to a store SKU. |

## Common Query Patterns
```sql
-- Find all valid variations defined for a category in a specific store
SELECT name, "values" 
FROM variants 
WHERE category_id = '<category_uuid>' AND store_id = '<store_uuid>';
```

## Indexes
- *Uses default PK and FK constraints.*
