# `ds_nav_bar`

## Searchable Aliases
website header, navigation menu, top bar, menu links, site navigation

## Description
The `ds_nav_bar` table is the **Header Configuration Registry** for the Digital Storefront (DS) domain. It controls the structure, features, and links displayed in the primary navigation header of the e-commerce site.

This table uses a "Multi-Zone" approach to navigation. By splitting the configuration into 5 distinct JSONB zones (Search, Login, Categories, Links, and Cart), the system allows administrators to customize specific functional areas of the header independently for each branch office.

## ⚙️ The Navigation Architecture Workflow
1.  **Zone Definition**: An administrator configures each of the 5 functional zones for the storefront.
2.  **Category Filtering**: The `categories` JSONB is typically used to define which parts of the product taxonomy are highlighted in the top-level menu.
3.  **Link Generation**: The `links` JSONB stores the custom URLs (e.g., "About Us", "Site Survey Request") that form the backbone of the site's pathing.
4.  **UI Feedback**: UI toggles in the `search_bar` and `cart` JSON objects determine if these features are physically rendered for the customer.
5.  **Runtime Handoff**: The front-end fetches this record to render the complete navigation experience for the current `store_id`.

## ⚠️ SQL-Critical Behaviors
- **Functional Isolation**: Because the configuration is split into multiple JSONB columns, a technician can update the "Login" logic without accidentally corrupting the "Custom Links" menu.
- **Tenant Specificity**: Navigation is strictly local. Branch A can have a "B2B Technical Support" link in their header while Branch B maintains a "Seasonal Clearance" link.
- **Dynamic Extensibility**: The JSONB format allows the system to support new header features (like a language switcher) by simply appending data to the existing schemas without altering the table structure.

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this navigation layout. |
| search_bar | jsonb | no | — | **Zone 1**: Config for the global search input and filters. |
| login | jsonb | no | — | **Zone 2**: Config for the user login/profile section of the header. |
| categories | jsonb | no | — | **Zone 3**: Definition of the hierarchical category menu. |
| links | jsonb | no | — | **Zone 4**: List of custom primary navigation URLs and labels. |
| cart | jsonb | no | — | **Zone 5**: Config for the shopping cart/briefcase visibility. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |

## Common Query Patterns
```sql
-- Retrieve the entire navigation schema for a branch office storefront
SELECT search_bar, login, categories, links, cart 
FROM ds_nav_bar 
WHERE store_id = '<uuid>';

-- Audit: Identify stores that have disabled the "Search Bar" UI feature
SELECT s.name 
FROM ds_nav_bar nb
JOIN stores s ON nb.store_id = s.id
WHERE (nb.search_bar->>'enabled')::boolean = false;
```

## Indexes
- *Relies on standard relational indexes on `store_id` for UI generation.*
