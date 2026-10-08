# ds_template_configs

## Purpose
The storefront personalization engine. It acts as the bridge that applies a global design template to a specific branch, defining the local branding—such as colors, logos, and feature flags—that makes each store unique.

---

## Retrieve This Table When The User Asks About

**Storefront settings and website configuration**
UI parameters or layout options. Retrieving the branding overrides (config) for a specific store’s web presence.

**Branch personalization**
Identifying which branches are currently using a specific base design or "Legacy" template. Auditing local styling and feature flags (e.g., "Show Pricing") for a branch.

---

## Co-Retrieved Sibling Tables
- `stores` — the branch that owns the personalization.
- `ds_templates` — the global layout being customized.
