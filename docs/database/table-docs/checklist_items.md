# `checklist_items`

## Searchable Aliases
tasks, steps, requirements, points, verification, inspection details

## Description
The `checklist_items` table defines the individual, actionable steps within a Quality Control or Procedural Blueprint. Each record represent a specific task (e.g., "Check for physical damage", "Verify all cables included") that must be performed as part of a larger `checklists` template.

By breaking procedures into these granular items, the **Lyndom** (the current PostgreSQL ERP) system allows for precise tracking of Quality Assurance (QA) progress during critical events such as receiving or shipping.

## ⚙️ The Verification Item Workflow
1.  **Item Definition**: A manager adds a specific `title` and `description` to a parent checklist template.
2.  **Logic Linkage**: When the parent template is triggered (e.g., during a shipment), these individual items are presented to the operator.
3.  **Completion Tracking**: As each item is performed, the system creates a record in a corresponding event table (like `shipment_checklists`) to mark the task as complete.
4.  **Operational Integrity**: The `is_active` flag ensures that only current, valid tasks are presented to workers, preventing the use of outdated or obsolete procedures.

## ⚠️ SQL-Critical Behaviors
- **Mandatory Alignment**: Every item must be linked to a `checklist_id`. This maintains the relational integrity of the quality control system, ensuring no "Orphan Tasks" exist without a parent procedure.
- **Content Continuity**: The `title` serves as the primary label in the UI, while the `description` provides the detailed "How-To" instructions for the employee performing the check.

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this verification step. |
| checklist_id | uuid | no | — | Link to the parent blueprint in `checklists.id`. |
| title | text | no | — | **Task Title**: (e.g., "Verify Oil Level", "Check Tracking Label"). |
| description | text | yes | — | Specialized instructions or criteria for the task. |
| is_active | bool | no | true | If `false`, the step is disabled for all future inspections. |
| creator_id | uuid | no | — | The user or manager who defined the specific task. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| checklist_id | checklists | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| shipment_checklists | checklist_item_id | Tracks the successful completion of this specific task for a shipment unit. |

## Common Query Patterns
```sql
-- List all specific tasks required for a "Pre-Shipping" checklist
SELECT title, description 
FROM checklist_items 
WHERE checklist_id = '<template_uuid>' AND is_active = true;

-- Find all unique tasks created by a specific quality manager
SELECT title, created_at 
FROM checklist_items 
WHERE creator_id = '<user_uuid>';
```

## Indexes
- *Relies on standard relational indexes on `checklist_id` and `store_id` for document generation.*
