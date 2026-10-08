# `production_instruction_sets`

## Searchable Aliases
technical manuals, assembly procedures, instruction folders, manufacturing guides

## Description
The `production_instruction_sets` table is the **Methodology Blueprint** for the manufacturing organization. It acts as the container for standardized engineering procedures and assembly-line manuals. 

Rather than redefining instructions for every unit, the business defines a single Instruction Set (e.g., "L-Series PCB Assembly") and then links it to relevant items. When a job is created, the system uses these templates to generate the active `production_steps` that technicians follow on the floor.

## ⚙️ The Standardization Workflow
1.  **Procedure Design**: An engineer creates a new Instruction Set, defining the high-level category of work.
2.  **Item Linking**: The set is mapped to specific categories or SKUs via specification rules.
3.  **Auto-Generation**: If `auto_generate = true`, the system automatically injects these instructions into every new manufacturing task created for that SKU, enforcing a company-wide "Standard Operating Procedure" (SOP).
4.  **Governance**: The `department_id` link ensures that instructions are filtered correctly (e.g., only the "Electrical" department sees the "Wiring" instructions).

## ⚠️ SQL-Critical Behaviors
- **Template Inheritance**: This table is the "Parent" of the `instructions` table. Deleting a set will remove all its constituent steps.
- **State Control**: The `is_active` toggle allows old assembly methodologies to be retired without affecting the history of units built under those standards.
- **Manufacturing Engine**: This table bridges the gap between static engineering manuals and dynamic shop-floor execution.

## Columns (10 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this SOP. |
| name | text | no | — | **SOP Name**: (e.g., "Final Quality Audit"). |
| description | text | no | — | Detailed summary of the methodology and scope. |
| auto_generate | bool | no | false | If `true`, the system automatically assigns this set to new builds. |
| is_active | bool | no | true | Status flag. If `false`, the template is retired. |
| creator_id | uuid | no | — | The engineer or administrator who designed the SOP. |
| department_id | uuid | yes | — | Link to `departments.id` for role-based instruction filtering. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |
| department_id | departments | id | set null |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| instructions | set_id | The specific task-level manual steps inside this blueprint. |
| production_instruction_set_specs | set_id | The technical rules that determine which items receive this instruction set. |

## Common Query Patterns
```sql
-- Find all auto-generating instructions for the "Quality Control" department
SELECT name, description 
FROM production_instruction_sets 
WHERE auto_generate = true AND department_id = '<dept_uuid>';

-- Audit: List all active SOPs for a specific store branch
SELECT name, is_active 
FROM production_instruction_sets 
WHERE store_id = '<uuid>' AND is_active = true;
```

## Indexes
- *Uses standard relational indexes on `store_id` and `department_id` for document generation.*
