# `ds_sliders`

## Searchable Aliases
banners, carousels, home page images, promotional slideshow, web graphics

## Description
The `ds_sliders` table is the **Promotional Carousel Registry** for the Digital Storefront (DS). It manages the high-impact "Hero Banners" that appear on the homepage of the public e-commerce site.

By defining individual slides with custom names, links, and ordering, the **Lyndom** (the current PostgreSQL ERP) system allows marketing teams to curate the first thing a customer sees when visiting the branch storefront. 

## ⚙️ The Slider Presentation Workflow
1.  **Slide Design**: A marketing user defines a slide with a descriptive `name` (e.g., "Spring 2026 Cooling Systems Promo").
2.  **Pathing**: The user provides a `related_link`, which is the destination URL (internal or external) the customer reaches when clicking the slide.
3.  **Prioritization**: The `order` field determines the sequence of rotation in the carousel (e.g., `Order 1` is the first slide seen).
4.  **Operational Scheduling**: Administrators use the `is_active` toggle to enable or disable seasonal promotions without deleting the underlying record.

## ⚠️ SQL-Critical Behaviors
- **Logical Anchoring**: Every slide is associated with a specific `store_id`. This allows Branch A to promote "Solar Solutions" while Branch B promotes "Backup Generators" on their respective homepages.
- **Visual Mapping**: While this table stores the metadata and links, the actual graphic assets are typically identified by the `name` or referenced in the `description` field, depending on the front-end implementation.
- **Sequence Integrity**: The `order` integer is the authoritative value for the front-end "Sort" command when fetching the carousel manifest.

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this promotional slider. |
| name | text | no | — | **Slide Heading**: The internal or public title of the promotion. |
| order | int4 | no | 0 | **Priority**: Determines the position in the carousel rotation. |
| description | text | yes | — | Sub-text or marketing copy displayed on the slide. |
| related_link | text | yes | — | **Call to Action**: The URL the user is redirected to upon click. |
| is_active | bool | no | true | Global status toggle for the slide. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |

## Common Query Patterns
```sql
-- Retrieve the active carousel manifest for a specific store, in order
SELECT name, related_link, description 
FROM ds_sliders 
WHERE store_id = '<uuid>' AND is_active = true 
ORDER BY "order" ASC;

-- Audit: Identify all stores that currently have no active homepage banners
SELECT name 
FROM stores s 
WHERE NOT EXISTS (SELECT 1 FROM ds_sliders ds WHERE ds.store_id = s.id AND ds.is_active = true);
```

## Indexes
- *Relies on standard relational indexes on `store_id` for UI generation.*
