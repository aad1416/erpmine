# `production_instruction_set_specs`

## Searchable Aliases
manual parameters, instruction template details, technical guide specs

## Description
The `production_instruction_set_specs` table is the **Automated Rule Engine** for manufacturing methodology. It allows the **Lyndom** (the current PostgreSQL ERP) system to intelligently assign technical manuals and assembly procedures to products based on their physical specifications.

Instead of manually assigning a manual to every SKU, engineers define rules (e.g., "All products in the Enclosures category with a Height of 72 inches receive the Height-Safety Instruction Set"). This ensures that technicians always receive the exact technical guidance required for the specific item variant they are building.

## ⚙️ The Auto-Assignment Logic Workflow
1.  **Rule Definition**: An engineer creates a record in this table linking an `instruction_set_id` to a specific `category_id` and a technical `value` (e.g., "Voltage = 480V").
2.  **Item Analysis**: When a manufacturing job is initiated, the system analyzes the technical specifications of the target product.
3.  **Pattern Matching**: The system searches this table for any rules that match the product's attributes.
4.  **Injection**: For every match found, the system automatically clones the instructions from that set into the unit's active `production_steps` ledger.

## ⚠️ SQL-Critical Behaviors
- **Multi-Factor Logic**: Multiple rules from this table can apply to a single product. A unit may receive one instruction set because of its "Category" and another because of a specific "Technical Spec Value."
- **Data Preservation**: The `spec_name` and `unit` are denormalized from the master specifications table to ensure the logic remains readable for historical audit purposes.
- **Direct Automation Trigger**: This table is the "Brain" behind the `auto_generate` flag in the `production_instruction_sets` header.

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| instruction_set_id | uuid | no | — | Link to the technical manual in `production_instruction_sets.id`. |
| category_id | uuid | no | — | **The Scope**: The item category where this rule applies. |
| spec_id | uuid | no | — | Link to the technical characteristic in `specifications.id`. |
| spec_name | text | no | — | Denormalized name of the specification (e.g., "Voltage"). |
| value | text | no | — | **The Trigger Value**: The specific attribute that fires the rule. |
| unit | text | no | — | The unit of measure for the trigger value (e.g., "Volts", "Inches"). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| instruction_set_id | production_instruction_sets | id | cascade |
| category_id | categories | id | cascade |
| spec_id | specifications | id | cascade |

## Common Query Patterns
```sql
-- List all rules that trigger the "High Voltage Safety" instruction set
SELECT spec_name, value, unit 
FROM production_instruction_set_specs 
WHERE instruction_set_id = '<uuid>';

-- Audit: Find all instruction sets assigned to the "Outdoor Lighting" category
SELECT s.name as set_name, r.spec_name, r.value
FROM production_instruction_set_specs r
JOIN production_instruction_sets s ON r.instruction_set_id = s.id
WHERE r.category_id = '<cat_uuid>';
```

## Indexes
- *Relies on standard relational indexes on `instruction_set_id` and `category_id` for rule execution.*
