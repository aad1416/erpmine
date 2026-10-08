# `cost_estimate_specs`

## Searchable Aliases
quotation details, pricing variables, estimate parameters, bid specs

## Description
The `cost_estimate_specs` table is the **Parametric Calculation Engine** for project budgeting. While the header defines the overall project name and total price, these line items define the technical "Drivers" or "Specifications" that justify that cost.

In the **Lyndom** (the current PostgreSQL ERP) estimation module, costs are often modeled based on technical attributes (e.g., "Weight > 500kg", "Voltage = 480V") rather than a simple bill of parts. This table captures those specific technical requirements for a given budget model.

## ⚙️ The Parametric Estimation Workflow
1.  **Requirement Entry**: An estimator adds a technical rule to the `cost_estimate_id`.
2.  **Attribute Targeting**: The estimator selects a specific `category_id` (The product family) and a `spec_id` (The technical characteristic).
3.  **Value Definition**: The specific target value is recorded (e.g., "Stainless Steel").
4.  **Pricing Impact**: The system uses these specification matches to lookup known cost benchmarks for that category-spec combination.
5.  **Validation**: These specs ensure that the estimate is technically grounded and consistent with company engineering standards.

## ⚠️ SQL-Critical Behaviors
- **Spec-Centric Pricing**: Unlike the active Sales domain which uses items and variants, this table allows for "General Cost Modeling" by targeting high-level specifications.
- **Data Denormalization**: The `spec_name` is stored as text to ensure the estimate remains readable and technically clear even if the master specification definitions are modified later.
- **Logical Filter**: Every record is a surgical constraint that defines a portion of the project's total financial value.

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Business Description |
|--------|------|----------|---------|-------------------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| cost_estimate_id | uuid | no | — | Link to the parent header in `cost_estimates.id`. |
| category_id | uuid | no | — | **Product Context**: The category of gear being modeled. |
| spec_id | uuid | no | — | Link to the technical characteristic in `specifications.id`. |
| spec_name | text | no | — | **Attribute Name**: Denormalized name of the spec (e.g., "Load Capacity"). |
| value | text | no | — | **Technical Requirement**: The specific value driving the cost (e.g., "1000kg"). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| cost_estimate_id | cost_estimates | id | cascade |
| category_id | categories | id | cascade |
| spec_id | specifications | id | cascade |

## Common Query Patterns
```sql
-- List all technical drivers contributing to the cost of a specific estimate
SELECT spec_name, value 
FROM cost_estimate_specs 
WHERE cost_estimate_id = '<uuid>';

-- Audit: Identify estimates that modeled requirements for the "High Voltage" spec
SELECT ce.label, ces.value 
FROM cost_estimate_specs ces
JOIN cost_estimates ce ON ces.cost_estimate_id = ce.id
WHERE ces.spec_name = 'Voltage';
```

## Indexes
- *Relies on standard relational indexes on `cost_estimate_id` and `spec_id` for parametric reporting.*
