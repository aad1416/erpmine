# `store_misc_settings`

## Searchable Aliases
specialized branch flags, local overrides, miscellaneous store data

## Description
The `store_misc_settings` table serves as a mini-CMS (Content Management System) for each store's digital storefront. While `store_configs` handles backend operational logic, `store_misc_settings` focus on the **frontend presentation** and **marketing curation**. It defines which product categories should be highlighted (e.g., "Popular Categories"), which items are on special offer, and which digital template is used for the store's web layout. All curation lists are stored as flexible JSONB arrays, allowing the storefront to display collections of items and categories that are manually selected by the store owner for promotional purposes.

## ⚠️ SQL-Critical Behaviors
- **Storefront Personalization**: This table is the primary source of truth for the store's homepage content.
- **Complex JSONB Structure**: The category lists (e.g., `popular_categories`) are not simple ID arrays. Live data shows they are **Arrays of Objects** containing metadata and IDs: `[{"name": "...", "title": "...", "categoryId": "uuid"}]`.
- **Relationship Overlap**: Many columns in this table reference `categories.id` and `item_stores.id` inside JSON strings, rather than as hard foreign keys. This means the system must handle referential integrity at the application level.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Update timestamp. |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| template_id | uuid | yes | — | Foreign key to `ds_templates.id` (Design/UI template used). |
| popular_categories | jsonb | no | `[]` | ⚠️ **Object Array**: `[{"name", "title", "categoryId"}]`. Categories featured on the homepage. |
| popular_categories2 | jsonb | no | `[]` | ⚠️ **Object Array**. Secondary featured category row. |
| selected_categories | jsonb | no | `[]` | ⚠️ **Object Array**. User-selected categories for navigation. |
| latest_categories | jsonb | no | `[]` | ⚠️ **Object Array**. Recently updated categories for display. |
| dynamic_categories | jsonb | no | `[]` | ⚠️ **Object Array**. Categories determined by dynamic filters. |
| popular_item_stores | jsonb | no | `[]` | ⚠️ **Flat UUID Array**: `["uuid1", "uuid2"]`. Curated list of featured `item_stores.id`. |
| special_offer_item_stores | jsonb | no | `[]` | ⚠️ **Flat UUID Array**. Reserved for promotional items. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| template_id | ds_templates | id | set null |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Retrieve the list of popular category IDs for a specific store's homepage
SELECT jsonb_path_query_array(popular_categories, '$[*].categoryId') as category_ids
FROM store_misc_settings 
WHERE store_id = '<store_uuid>';

-- Check which design template a store is using
SELECT s.name, ds.name as template_name
FROM stores s
JOIN store_misc_settings sms ON s.id = sms.store_id
JOIN ds_templates ds ON ds.id = sms.template_id
WHERE s.id = '<store_uuid>';
```

## Indexes
- *Uses default PK and FK constraints.*


