# production_default_task_set_specs

## Purpose
The intelligent dispatcher for manufacturing. It defines the conditional logic that automatically assigns standard tasks to a product build based on its specific technical characteristics or category.

---

## Retrieve This Table When The User Asks About

**Task assignment rules and presets**
Default assembly specs or manufacturingpresets. Identifying which technical requirements (e.g., "Material = Stainless Steel") trigger a specific assembly task.

**Automated shop-floor guidance**
Finding the rules that "Fire" to inject tasks into a unit's build-list. Auditing the connection between engineering specifications and factory-floor execution (SOP compliance).

---

## Co-Retrieved Sibling Tables
- `production_default_tasks` — the template work order being assigned.
- `categories` — the item category where the task is mandatory.
- `specifications` — the technical characteristic triggering the rule.
