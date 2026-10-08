# `departments`

## Searchable Aliases
business units, divisions, teams, internal groups, cost centers

## Description
The `departments` table represents the functional organization of labor and processes within a store. While a store is a legal and physical entity, departments like "Assembly", "Sales", or "Electrical" represent the internal teams that carry out day-to-day operations. This classification is primarily used to scope and filter specialized workflows. For example, manufacturing instructions (Instruction Sets) are often linked to a department, ensuring that personnel on the "Welding" team only sees procedures relevant to their area of expertise. ⚠️ **Do NOT use this table for job titles (e.g., Technician, Manager). Use the `roles` table for job titles.** Examples of actual values for protected departments include: "Production", "Engineering", and "Sales".

## ⚠️ SQL-Critical Behaviors
- **Functional Scope**: When identifying which teams can perform a certain task, join through `users_departments` to find users matching the task's required department.
- **Store-Level Scoping**: Unlike roles, departments are always specific to a `store_id`. There are no global departments in this schema.
- **Protected Departments**: Use `WHERE protected = true` to identify system-standard departments like "Production" or "Engineering" that are reserved for core business logic.

## Columns

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | uuid | no | Primary key. |
| created_at | timestamptz | no | Creation timestamp. |
| updated_at | timestamptz | no | Update timestamp. |
| store_id | uuid | no | The store this department belongs to. |
| name | text | no | Human-readable name (e.g., "Quality Assurance"). |
| creator_id | uuid | no | The user who created this department. |
| protected | bool | no | If `true`, deletion is restricted due to system dependencies. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| users_departments | department_entity_id | Maps users to their specific functional teams. |
| production_instruction_sets | department_id | Determines which instructions belong to which functional area. |

## Common Query Patterns
```sql
-- List all active departments for a specific store
SELECT name, protected FROM departments WHERE store_id = '<store_uuid>';

-- Find the department name for a specific user
SELECT d.name 
FROM departments d
JOIN users_departments ud ON d.id = ud.department_entity_id
WHERE ud.user_entity_id = '<user_uuid>';
```

## Indexes
- *Uses default PK and FK constraints for indexing logic.*


