# `spec_rule_targets`

## Searchable Aliases
technical rule scope, spec validation targets, attribute rule mapping

## Description
The `spec_rule_targets` table defines the **Constraints or Automations** that are applied when a technical rule in the `spec_rules` table is triggered. It specifies which other attributes must be modified or mandated. For example, if the parent rule is triggered by "Voltage: 480V", a target entry might state: "Phase: 3-Phase". This ensures technical consistency across all fields of a product configuration.

## ⚠️ SQL-Critical Behaviors
- **Consequent Logic**: This table represents the "Then" part of an "If-Then" statement.
- **Multiple Targets**: A single rule in `spec_rules` can point to multiple records in this table, allowing one choice to ripple through many technical specifications.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| spec_rule_id | uuid | no | — | Foreign key to the parent rule in `spec_rules.id`. |
| specification_id | uuid | no | — | The attribute that is being mandated/suggested. |
| value | text | no | — | The value that must be applied. |
| unit | text | no | — | The unit associated with the target value. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| spec_rule_id | spec_rules | id | cascade |
| specification_id | specifications | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find all target constraints for a specific rule
SELECT s.name as spec_name, t.value, t.unit
FROM spec_rule_targets t
JOIN specifications s ON t.specification_id = s.id
WHERE t.spec_rule_id = '<rule_uuid>';
```

## Indexes
- *Uses default PK and FK constraints.*
