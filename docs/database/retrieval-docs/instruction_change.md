# instruction_change

## Purpose
The engineering variance log for manufacturing. It captures deviations from master manuals—including additions, deletions, or updates to assembly steps—to ensure that the final "As-Built" documentation for a machine reflects its actual physical construction.

---

## Retrieve This Table When The User Asks About

**Procedure updates and manual revisions**
Technical changes or manufacturing deviations. Identifying modifications made to a standard assembly instruction for a specific product line or unit build.

**Engineering change logs and versioning**
Retrieving the self-contained historical record of a technical redesign. Auditing "As-Built" reality vs. the original master blueprint.

**Safety audits and failure investigations**
Finding the authorized text and technical arguments of a manufacturing step at the moment it was changed. Identifying who authorized a specific technical deviation (creator).

**Shop-floor pathing and sequence**
Identifying updated sequence IDs (e.g., 1.2.1) or technical measurement requirements for a modified build step.

---

## Co-Retrieved Sibling Tables
- `production_instruction_sets` — the master manual being modified.
- `instructions` — the original assembly step being updated or deleted.
- `item_stores` — the specific product variant affected by the change.
- `users` — the engineer who authorized the deviation.
