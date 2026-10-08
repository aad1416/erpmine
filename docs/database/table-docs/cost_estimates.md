# `cost_estimates`

## Searchable Aliases
quotes, bids, pricing, proposals, financial projections, budget

## Description
The `cost_estimates` table is the **Pre-Sales Financial Sandbox** of the **Lyndom** (the current PostgreSQL ERP) system. It allows engineers, estimators, and project managers to model the total expected cost of a project or complex assembly before a formal Quote is generated.

This table is functionally a "Standalone Ledger." It does not bind to a Sales Order or Quote, which makes it an ideal tool for "What-If" scenarios, internal budgeting, and initial feasibility studies. Once an estimate is approved, its data is typically used as the basis for a commercial proposal.

## ⚙️ The Estimation & Budgeting Workflow
1.  **Drafting**: An estimator creates a new record, giving it a descriptive `label` (e.g., "Site Expansion - Phase 1 Revision B").
2.  **Logic Injection**: The estimator adds granular technical requirements to the `cost_estimate_specs` table, which drive the final price.
3.  **Cost Rollup**: The system summarizes the technical lines into a single master `cost` value on this header.
4.  **Review**: Multiple versions of an estimate can be maintained to track changes in project scope or material pricing.
5.  **Conversion**: High-quality estimates are used as a technical reference during the creation of a formal `quotes` record.

## ⚠️ SQL-Critical Behaviors
- **Standalone Flexibility**: Because there is no mandatory FK to the Sales domain, this table can be used for internal plant maintenance or overhead budgeting as well as customer-facing work.
- **Calculated Integrity**: The `cost` column is typically a summary field. In high-integrity environments, this should match the sum of the linked `cost_estimate_specs`.
- **Tenant Segregation**: Estimates are strictly owned by a specific `store_id`, ensuring that sensitive project pricing remains private to the originating branch.

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| label | text | no | — | **Estimate Name**: (e.g., "Municipal Lighting Bid - 2026"). |
| cost | numeric | no | — | **Total Modeled Cost**: The final calculated dollar value of the project. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the project model. |
| description | text | yes | — | Detailed internal notes regarding the scope of the estimate. |
| creator_id | uuid | no | — | The estimator or manager who developed the cost model. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| cost_estimate_specs | cost_estimate_id | The technical specification lines that drive the total cost. |

## Common Query Patterns
```sql
-- List all active budgets created by a specific estimator
SELECT label, cost, created_at 
FROM cost_estimates 
WHERE creator_id = '<user_uuid>' 
ORDER BY created_at DESC;

-- Identify high-value "draft" projects exceeding $100k
SELECT label, cost, store_id 
FROM cost_estimates 
WHERE cost > 100000;
```

## Indexes
- *Uses standard relational indexes on `store_id` and `creator_id` for document management.*
