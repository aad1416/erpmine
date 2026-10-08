# `instructions`

## Searchable Aliases
manuals, procedures, standard operating guidelines, steps, assembly guides, technical documentation

## Description
The `instructions` table is the **Content Repository** for the individual manual steps within a methodology. While the `production_instruction_sets` table acts as the folder, this table contains the actual "Pages" of the technical manual. 

Each record defines a specific action (e.g., "Step 1.2: Check grounding wire continuity") that the system will clone into the `production_steps` table when a unit is released to the assembly line.

## ⚙️ The Methodology Definition Workflow
1.  **Template Writing**: An engineer defines the `title`, `subtitle`, and `content` (the actual instructions) for a process step.
2.  **Structural Pathing**: The `instruction_info_step` field is used to define the logical order (e.g., `1`, `1.1`, `1.2`) of the instruction within the set.
3.  **Variable Configuration**: Using the `instruction_info_args` JSONB, the engineer can define expected parameters or data-entry fields that the technician must fill out (e.g., target voltage range).
4.  **Deployment**: When manufacturing begins, the content of these records is copied to the `production_steps` table, creating an active checklist for the shop floor worker.

## ⚠️ SQL-Critical Behaviors
- **Structured Info Grouping**: The table uses an `instruction_info_...` prefix for its core content columns. This grouping suggests a logical sub-object used for form rendering in the UI.
- **Instruction vs. Remark**: The `instruction_info_type` enum (e.g., `INSTRUCTION`, `WARNING`, `NOTE`) determines how the step is visually presented to the technician—ensuring critical safety warnings are highlighted.
- **Immutable Templates**: Once an instruction is used in `production_steps`, modifying the original `instructions` record will **not** change the already-issued build steps, preserving the historical integrity of "As-Built" units.

## Columns (14 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this procedure. |
| set_id | uuid | no | — | Link to the parent blueprint in `production_instruction_sets.id`. |
| instruction_info_title | text | no | — | **Heading**: The short name of the task. |
| instruction_info_subtitle | text | no | — | Sub-heading or instructional category. |
| instruction_info_content | text | no | — | **The "How-To"**: Detailed technical methodology/description. |
| instruction_info_step | text | no | — | **Sequence Number**: (e.g., `1.0`, `2.1`). |
| instruction_info_args | jsonb | no | — | **Schema Definition**: JSON defining the input fields for the tech. |
| instruction_info_checkboxes | jsonb | no | — | **Checklist Schema**: JSON defining required verification boxes. |
| is_active | bool | no | true | Status flag. If `false`, the step is hidden from new builds. |
| creator_id | uuid | no | — | The engineer/administrator who authored the content. |
| instruction_info_type | enum | no | 'INSTRUCTION' | **Display Role**: (e.g., `INSTRUCTION`, `WARNING`). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| set_id | production_instruction_sets | id | cascade |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Reconstruct the full manual for a specific Instruction Set
SELECT instruction_info_step, instruction_info_title, instruction_info_content
FROM instructions 
WHERE set_id = '<uuid>' AND is_active = true
ORDER BY instruction_info_step ASC;

-- Audit: Find all instruction templates that include critical Safety Warnings
SELECT instruction_info_title, instruction_info_content
FROM instructions 
WHERE instruction_info_type = 'WARNING';
```

## Indexes
- *Relies on standard relational indexes on `set_id` and `store_id` for methodology management.*
