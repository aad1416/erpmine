# `instruction_change`

## Searchable Aliases
procedure updates, manual revisions, technical changes, versioning, change log

## Description
The `instruction_change` table is the **Engineering Variance Log** for the manufacturing department. In an industrial environment, the "Master Manual" (`instructions`) must often be deviated from due to part shortages, custom engineering requests, or mid-build technical redesigns. 

This table captures every modification—Additions, Deletions, or Updates—made to the technical guidance of a production job record. It ensures that the final "As-Built" documentation for a serialized unit accurately reflects the physical reality of its construction, even if that reality differs from the original blueprint.

## ⚙️ The Change-Control Workflow
1.  **Deviation Identified**: An engineer or senior technician determines that a standard assembly step must be modified for a specific product line or unit build.
2.  **Registration**: A record is created in this table, identifying the target `item_store_id` (The product) and the specific `instruction_id` (if modifying an existing step).
3.  **Content Encapsulation**: The system stores the **Complete New Content** (`instruction_info_...`) directly in this record. This ensures that the historical record is self-contained and not dependent on external templates that might change later.
4.  **Application**: When a new unit is manufactured, the system merges the master `instructions` with the active `instruction_change` records to produce the final, accurate `production_steps`.

## ⚠️ SQL-Critical Behaviors
- **State Preservation**: Because this table captures the text and arguments of the instruction at the *moment of the change*, it provides the mandatory legal and technical evidence for safety audits and failure investigations.
- **Set Context**: While the change is often triggered for a specific SKU (`item_store_id`), it is anchored to an `instruction_set_id` to maintain the integrity of the departmental methodology.
- **Active Filter**: Only records with `is_active = true` are applied during the generation of the unit-level work orders.

## Columns (17 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Time the change was registered. |
| updated_at | timestamptz | no | — | Last modification to the change record. |
| set_id | uuid | no | — | Link to the parent technical manual being modified (`production_instruction_sets.id`). |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the change. |
| item_store_id | uuid | no | — | **The Target SKU**: The product variant affected by this change. |
| instruction_id | uuid | yes | — | Link to the original master instruction being updated/deleted. |
| type | enum | no | — | **Modification Logic**: (e.g., `ADD`, `MODIFY`, `DELETE`). |
| instruction_info_title | text | no | — | The new or updated heading for the instruction step. |
| instruction_info_subtitle | text | no | — | The new subtitling for technical context. |
| instruction_info_content | text | no | — | **The New Manual**: The updated technical instructions. |
| instruction_info_step | text | no | — | The updated sequence ID (e.g., `1.2.1`) for shop-floor pathing. |
| instruction_info_type | enum | no | 'INSTRUCTION' | The updated display role (e.g., `WARNING`, `NOTE`). |
| instruction_info_args | jsonb | no | — | The updated technical measurement requirements. |
| instruction_info_checkboxes | jsonb | no | — | The updated verification checklist schema. |
| creator_id | uuid | no | — | The engineer or administrator who authorized the deviation. |
| is_active | bool | no | true | Global status flag. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| set_id | production_instruction_sets | id | cascade |
| item_store_id | item_stores | id | cascade |
| instruction_id | instructions | id | set null |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Audit: Find all technical assembly changes made to a specific product line
SELECT instruction_info_title, type, created_at, instruction_info_content
FROM instruction_change 
WHERE item_store_id = '<uuid>' 
ORDER BY created_at DESC;

-- Identify all "Safety Warnings" added to a set after its original release
SELECT instruction_info_title, instruction_info_content 
FROM instruction_change 
WHERE set_id = '<uuid>' 
  AND instruction_info_type = 'WARNING' 
  AND type = 'ADD';
```

## Indexes
- *Uses standard relational indexes on `item_store_id` and `set_id` for engineering change management.*
