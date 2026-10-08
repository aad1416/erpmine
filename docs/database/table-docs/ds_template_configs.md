# `ds_template_configs`

## Searchable Aliases
storefront settings, website configuration, UI parameters, layout options

## Description
The `ds_template_configs` table is the **Storefront Personalization Engine** of the **Lyndom** (the current PostgreSQL ERP) system. It acts as the bridge that "applies" a global `ds_template` to a specific store branch.

While the master template defines where things go (the layout), this config record defines **what they look like** (the branding). It allows multiple stores to share the same high-quality code and design foundation while maintaining completely different color schemes, logos, and feature settings.

## ⚙️ The Personalization Workflow
1.  **Template Selection**: A store manager selects a master design from `ds_templates`.
2.  **Config Generation**: A record is created in this table, anchoring the `store_id` to the `template_id`.
3.  **Branding Injection**: The local store's specific settings (e.g., `primary_color: "#FF5733"`, `show_pricing: true`) are recorded in the `config` JSONB field.
4.  **Runtime Rendering**: When a customer visits the store's URL, the front-end fetches the global layout but injects these local config overrides to render a unique, branded experience.

## ⚠️ SQL-Critical Behaviors
- **Override Pattern**: The `config` JSONB columns act as a series of "CSS and Feature Overrides" on top of the master theme definition.
- **One-to-One Binding**: Typically, a store only has one active association in this table to determine its current web presence.
- **Tenant Isolation**: This table is the primary guardrail that prevents storefront designs from accidentally leaking across branches.

## Columns (6 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this storefront customization. |
| template_id | uuid | no | — | **The Base Design**: Link to the global layout in `ds_templates.id`. |
| config | jsonb | no | `[]` | **Branding Overrides**: JSON storing local styling and feature flags. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| template_id | ds_templates | id | cascade |

## Common Query Patterns
```sql
-- Retrieve the branding configuration for a specific store's storefront
SELECT tc.config, t.name as base_template_name
FROM ds_template_configs tc
JOIN ds_templates t ON tc.template_id = t.id
WHERE tc.store_id = '<uuid>';

-- Audit: Identify which branches are currently using the "Legacy" template
SELECT s.name as store_name
FROM ds_template_configs tc
JOIN stores s ON tc.store_id = s.id
WHERE tc.template_id = (SELECT id FROM ds_templates WHERE name = 'Legacy');
```

## Indexes
- *Relies on standard relational indexes on `store_id` and `template_id` for storefront generation.*
