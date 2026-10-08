# `ds_footers`

## Searchable Aliases
website bottom, page footer, contact info, site links, legal notices

## Description
The `ds_footers` table is the **Information Utility Registry** for the Digital Storefront (DS) domain. It controls the structure, legal links, and social credentials displayed in the bottom section (footer) of the e-commerce site.

This table follows a "Multi-Zone" strategy similar to the navigation bar, allowing administrators to customize the company description, social media profiles, and legal site-map independently for each branch office.

## ⚙️ The Footer Architecture Workflow
1.  **Identity Definition**: An administrator configures the `description` JSONB, which typically contains the store's "About Us" summary for the footer.
2.  **Legal & Utility Mapping**: The `links` JSONB stores the critical compliance URLs (e.g., "Privacy Policy", "Terms of Service", "Cookies").
3.  **Social Credentialing**: The `social_links` JSONB allows for the dynamic rendering of platform icons (LinkedIn, Twitter, etc.) and their respective branch-specific URLs.
4.  **Quick Catalog Access**: The `categories` JSONB is used to define a secondary "Mini-Map" of popular product categories for the bottom of the page.
5.  **Runtime Handoff**: The front-end fetches this record to ensure every page on the storefront ends with the correct, branch-specific legal and contact information.

## ⚠️ SQL-Critical Behaviors
- **Compliance Isolation**: Each store's legal links are stored independently. This is critical for companies operating across different jurisdictions (e.g., a "GDPR Policy" link in the EU store vs specialized "State Notices" in US branches).
- **Tenant Specificity**: Footers are strictly local. Branch A can highlight their "ISO Certification" while Branch B emphasizes their "Local Community Support."
- **JSONB Extensibility**: The use of JSONB allows the UI to support varied footer layouts (3-column vs 4-column) using a single schema.

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this footer layout. |
| description | jsonb | no | — | **Zone 1**: Config for the company bio/description text. |
| links | jsonb | no | — | **Zone 2**: Structured list of legal and utility URLs. |
| social_links | jsonb | no | — | **Zone 3**: Collection of social media platform links and icons. |
| categories | jsonb | no | — | **Zone 4**: List of highlighted category-level landing pages. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |

## Common Query Patterns
```sql
-- Retrieve the full footer configuration for a specific store branch
SELECT description, links, social_links, categories 
FROM ds_footers 
WHERE store_id = '<uuid>';

-- Audit: Find all stores that have configured a LinkedIn profile link
SELECT s.name 
FROM ds_footers f
JOIN stores s ON f.store_id = s.id
WHERE f.social_links @> '[{"platform": "linkedin"}]';
```

## Indexes
- *Relies on standard relational indexes on `store_id` for UI generation.*
