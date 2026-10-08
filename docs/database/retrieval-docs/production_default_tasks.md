# production_default_tasks

## Purpose
The job-template registry. It defines the standardized types of assembly work orders (e.g., "Quality Control Audit", "Core Assembly") that occur repeatedly across product builds, ensuring consistent manufacturing workflows.

---

## Retrieve This Table When The User Asks About

**Standard assembly tasks and manufacturing templates**
Blueprint tasks or shop-floor work templates. Identifying the "Available Services" or standard procedural work defined for the factory floor.

**Workflow standardization**
Finding the master list of task titles and descriptions used to auto-generate active production tasks for new builds. Auditing who is responsible for maintaining the shop-floor work templates.

---

## Co-Retrieved Sibling Tables
- `production_tasks` — the active, unique work orders generated from these templates.
- `production_default_task_set_specs` — the rules that auto-assign these tasks to products.
- `users` — the production manager who defined the template.
