# `ds_blog_posts`

## Searchable Aliases
articles, news, content, marketing, web updates, portal messages

## Description
The `ds_blog_posts` table is the **Content Marketing Engine** of the Digital Storefront (DS) domain. It acts as the central repository for articles, company news, and technical guides that appear on the public storefront.

This table allows each branch office to maintain a "Voice" by publishing regional news or technical blog content to their specific customers. It includes a built-in editorial workflow (Draft vs. Active) to ensure quality control before content hits the live web.

## ⚙️ The Editorial Content Workflow
1.  **Drafting**: A marketing user or subject matter expert creates a new record, setting `is_draft = true`.
2.  **Metadata Injection**: The user defines the `title`, a short `summary` (for list view teasers), and the `author`'s public name.
3.  **Content Authoring**: The actual body of the article is recorded in the `content` field.
4.  **Scheduling**: The `date` field is set to the intended public release date (which may be different from the physical creation date).
5.  **Activation**: Once approved, the `is_draft` toggle is cleared, making the post visible to customers on the storefront.

## ⚠️ SQL-Critical Behaviors
- **Editorial State Machine**: A post is only visible if `is_draft = false` AND `is_active = true`. This dual-lock ensures that a "Finished" post can still be globally toggled off for business reasons.
- **Independence of Identity**: The `author` field is a free-text field rather than a foreign key to the `users` table. This allows for authorship from external contributors or collective personas (e.g., "The Design Team").
- **Tenant Control**: Blog posts are owned by a specific `store_id`, ensuring that "Branch A's News" doesn't clutter the storefront of "Branch B."

## Columns (11 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this content. |
| date | int8 | no | — | **Public Publish Date**: The timestamp shown to the customer (Epoch). |
| title | text | no | — | **Post Heading**: The main title of the article. |
| content | text | no | — | **The Body**: The actual text/HTML content of the post. |
| summary | text | no | — | **Teaser Text**: A short summary displayed on listing pages. |
| is_draft | bool | no | true | **Editorial Status**: If `true`, the post is hidden from the public. |
| author | text | no | — | **The Byline**: The display name of the author (e.g., "Engineering Dept"). |
| is_active | bool | no | true | Global status toggle. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| ds_blog_posts_categories | dsblog_post_entity_id | Tagging system linking posts to product/informational categories. |

## Common Query Patterns
```sql
-- Retrieve all live blog posts for a store's public homepage
SELECT title, summary, author, date 
FROM ds_blog_posts 
WHERE store_id = '<uuid>' 
  AND is_draft = false 
  AND is_active = true 
ORDER BY date DESC;

-- Count active drafts currently waiting for publication
SELECT COUNT(id) 
FROM ds_blog_posts 
WHERE is_draft = true;
```

## Indexes
- *Relies on standard relational indexes on `store_id` and `date` for blog feed performance.*
