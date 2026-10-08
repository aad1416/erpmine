# `guilds_categories`

## Searchable Aliases
guild groups, community classification, interest categories

## Description
The `guilds_categories` table is a many-to-many junction that defines the visibility of product categories for specific industry guilds. By linking a `guild.id` to a `category.id`, the system controls which taxonomies are available to a store based on its guild membership. This allows the **Lyndom** (the current PostgreSQL ERP) system to provide a tailored catalog experience: for example, a store in a "Power Systems" guild will see high-voltage equipment categories, while a general branch in a different guild might not. 

## ⚠️ SQL-Critical Behaviors
- **Catalog Filtering**: This junction is used by the UI to filter the category tree. If a store belongs to a guild, the system may restrict its catalog to only the categories registered in this table.
- **Composite Primary Key**: Uses `(guild_entity_id, category_entity_id)` to ensure unique assignments.

## Columns

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| guild_entity_id | uuid | no | Foreign key to `guilds.id`. |
| category_entity_id | uuid | no | Foreign key to `categories.id`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| guild_entity_id | guilds | id | cascade |
| category_entity_id | categories | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find all categories accessible to a specific guild
SELECT c.name 
FROM categories c
JOIN guilds_categories gc ON c.id = gc.category_entity_id
WHERE gc.guild_entity_id = '<guild_uuid>';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| (guild_entity_id, category_entity_id) | btree (PK) | Ensures uniqueness and optimizes catalog filtering queries. |
