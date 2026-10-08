# `ds_blog_posts_categories`

## Searchable Aliases
blog groups, article types, news classification, content tags

## Description
The `ds_blog_posts_categories` table is the **Content Tagging Junction** for the storefront blog engine. It acts as the bridge between technical marketing articles (`ds_blog_posts`) and the product taxonomy (`categories`).

By linking blog posts to categories, the **Lyndom** (the current PostgreSQL ERP) system enables **Contextual Content Marketing**. This allows the storefront to dynamically display relevant articles (e.g., "Installation Guides") on specific product category pages, improving the customer's technical journey.

## ⚙️ The Categorization Workflow
1.  **Tagging**: An administrator selects one or more categories that are relevant to a blog post.
2.  **Junction Entry**: A record is created in this table for every pairing of Post ID and Category ID.
3.  **Cross-Promotion**: When a customer browses a category on the storefront, the system queries this table to find and display related "Recommended Reading."

## ⚠️ SQL-Critical Behaviors
- **Many-to-Many Logic**: A single blog post can be tagged to multiple categories (e.g., a "Wiring Guide" could be linked to both 'Cables' and 'Enclosures').
- **Performance Optimization**: This table uses a Compound Primary Key on both IDs, ensuring rapid lookups during page rendering.
- **Dependency Control**: Deleting a category or a blog post will automatically clear the associated tagging records, maintaining a clean relationship ledger.

## Columns (2 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| dsblog_post_entity_id | uuid | no | — | Link to the article in `ds_blog_posts.id`. |
| category_entity_id | uuid | no | — | Link to the product/service category in `categories.id`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| dsblog_post_entity_id | ds_blog_posts | id | cascade |
| category_entity_id | categories | id | cascade |

## Common Query Patterns
```sql
-- Find all blog posts tagged to the "Safety Equipment" category
SELECT bp.title, bp.summary
FROM ds_blog_posts bp
JOIN ds_blog_posts_categories j ON bp.id = j.dsblog_post_entity_id
WHERE j.category_entity_id = '<cat_uuid>';

-- Audit: List all categories associated with a specific blog post
SELECT c.name 
FROM categories c
JOIN ds_blog_posts_categories j ON c.id = j.category_entity_id
WHERE j.dsblog_post_entity_id = '<post_uuid>';
```

## Indexes
- **PKEY**: (dsblog_post_entity_id, category_entity_id) [BTREE]
