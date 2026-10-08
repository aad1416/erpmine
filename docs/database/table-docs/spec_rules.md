# `spec_rules`

## Searchable Aliases
technical constraints, attribute validation, engineering rules, specification logic

## Description
The `spec_rules` table defines the dependency logic between different technical attributes within a product category. These rules act as a "Validation and Auto-Configuration Engine" for complex engineering products. For example, a rule might state: *"If **Voltage** is **480V**, then the **Breaker Size** must be at least **100A**."* By establishing these relationships, the **Lyndom** (the current PostgreSQL ERP) system prevents configuration errors during the quoting phase and ensures that technical specifications across a system are compatible.

## ⚠️ SQL-Critical Behaviors
- **Configuration Logic**: The `source_specification_id` and `source_value` define the "Trigger". When a user selects this value in a configuration UI, the rule activates.
- **Strict Enforcement**: If `strict = true`, the system may prevent the user from completing a quote or order if the target specifications are not met.
- **Item Selection**: SKUs in the `item_stores` table can be linked to a specific rule via the `spec_rule_id` column, allowing the system to suggest or mandate a specific part based on a technical selection.
- **Workflow Automation**: The `type` enum determines how the rule is applied (e.g., automatically appending a related part vs. simply validating a choice).

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| name | text | no | '' | Human-readable rule name. |
| source_specification_id | uuid | no | — | The attribute that triggers the rule (e.g., "Voltage"). |
| source_value | text | no | — | The specific value that activates the rule (e.g., "480"). |
| source_unit | text | no | — | The unit associated with the source value (e.g., "VAC"). |
| reason | text | no | — | Descriptive text explaining *why* the rule exists (e.g., "Safety Compliance"). |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| category_id | uuid | no | — | Primary category this rule applies to. |
| strict | bool | no | false | If `true`, the rule cannot be overridden by the user. |
| type | enum | no | — | **Rule Action Type**. Examples of actual values include: `AUTO_APPEND`, `MANDATORY`. |
| creator_id | uuid | no | — | The user who created this configuration rule. |

## Enums Used

### `spec_rule_type_enum`
*(Values inferred from typical ERP logic rules)*
- `AUTO_APPEND`: Automatically adds a specific part or value when the trigger matches.
- `MANDATORY`: Requires the user to select the target value before proceeding.
- `SUGGESTED`: Recommends a value but allows an override.

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| source_specification_id | specifications | id | cascade |
| category_id | categories | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| spec_rule_targets | spec_rule_id | Defines the "Resulting Constraints" of the rule. |
| item_stores | spec_rule_id | Links a specific SKU to this automated selection rule. |

## Common Query Patterns
```sql
-- Find all rules that apply to a specific item category
SELECT name, source_value, reason 
FROM spec_rules 
WHERE category_id = '<category_uuid>' AND is_active = true;
```

## Indexes
- *Uses default PK and FK constraints.*
