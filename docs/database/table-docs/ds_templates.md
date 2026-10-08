# `ds_templates`

## Searchable Aliases
website themes, storefront layouts, UI blueprints, site styles

## Description
The `ds_templates` table is the **Global Design Blueprint** for the Digital Storefront (DS) domain. It acts as the master repository for "Themes" or "Layout Packages" that define the visual and structural identity of the public-facing e-commerce site.

Rather than hard-coding a website for each store, the system uses these templates. A template defines the core page structure (B2B portal, retail shop, etc.), which the individual stores then "Subscribe" to and customize via configurations.

## ⚙️ The Storefront Blueprinting Workflow
1.  **Template Design**: A designer or technical administrator defines a master template, including its `name` and `description`.
2.  **Page Manifesting**: The structure of the entire site (Home, Catalog, Product, Checkout) is stored in the `pages` JSONB column. 
3.  **Thematic Selection**: Individual stores choose a template from this list based on their business `type` (e.g., a "Service Portal" vs a "Bulk Order" theme).
4.  **Local Implementation**: Once a template is selected, the specific store's branding and content are applied via the `ds_template_configs` table.

## ⚠️ SQL-Critical Behaviors
- **Component Hub**: The `pages` JSONB column is the primary driver for front-end rendering. It contains the list of mandatory UI widgets and logical blocks for each page in the theme.
- **Inheritance Infrastructure**: This table is the "Parent" of all storefront designs. Modifying a master template here can potentially update the layout for dozens of "Subscribing" stores simultaneously.
- **Global Availability**: Unlike most tables in the ERP, `ds_templates` lacks a `store_id`, implying these are **Global Assets** managed by the head office.

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| name | text | no | — | **Theme Name**: (e.g., "Modern Fluid B2B", "Classic Retail"). |
| is_active | bool | no | true | Global status flag. If `false`, the theme is hidden for new store sign-ups. |
| type | text | no | '' | **Category**: Classification (e.g., 'RETAIL', 'WHOLESALE'). |
| description | text | no | — | Summarized notes on the theme's features and audience. |
| pages | jsonb | no | `[]` | **The Page Blueprint**: A JSON manifest of the layout hierarchy. |

## Relationships

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| ds_template_configs | template_id | The link where a specific store "Adopts" this global design. |

## Common Query Patterns
```sql
-- List all active "B2B" style templates available for store adoption
SELECT name, description 
FROM ds_templates 
WHERE type = 'B2B' AND is_active = true;

-- System Audit: Identify the most complex templates based on page count (JSON length)
SELECT name, jsonb_array_length(pages) as page_count
FROM ds_templates 
ORDER BY page_count DESC;
```

## Indexes
- *Uses standard relational indexes for document management.*
