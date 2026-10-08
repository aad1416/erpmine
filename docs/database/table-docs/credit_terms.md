# `credit_terms`

## Searchable Aliases
payment terms, net 30, net 60, financing, payment deadlines, interest

## Description
The `credit_terms` table defines the financial payment policies governing the relationship between the business and its Clients/Vendors. These terms (e.g., `Net 30`, `COD`, `1% 10 Net 30`) are the primary input for the **Accounts Receivable (AR)** and **Accounts Payable (AP)** modules, determining how many days a debtor has to pay their invoice before it is classified as "Overdue."

By centralizing these policies, the **Lyndom** (the current PostgreSQL ERP) system ensures that commercial agreements are automatically enforced across all transactional documents.

## ⚙️ The Financial Workflow
1.  **Agreement**: A credit term is established for an entity (e.g., a Client is granted "Net 45" terms).
2.  **Order Entry**: When a Quote or Sales Order is created, the `credit_term_id` is pulled from the parent record.
3.  **Invoice Generation**: When an invoice is finalized, the system uses the `name` (e.g., "Net 30") to calculate the `due_date` by adding the term days to the issue date.
4.  **Aging Reports**: The system scans these terms to calculate "Days Past Due" (DPD) for aging reports and automated collections.

## ⚠️ SQL-Critical Behaviors
- **Policy Enforcement**: Every invoice record in the system typically relies on the definitions stored here to calculate financial liability.
- **Cash Flow Control**: Terms like "Payment In Advance" or "COD" are used to block the release of shipments until the financial conditions defined here are met.

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Timestamp of policy registration. |
| updated_at | timestamptz | no | — | Last modification of the policy description. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns or utilizes this credit policy. |
| name | text | no | — | **Policy Name**: The code or name used on documents (e.g., "Net 30", "Net 15"). |
| description | text | yes | — | Detailed explanation of the term for staff reference. |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| creator_id | uuid | no | — | The administrator who defined the credit term. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| clients | credit_terms_id | The default payment schedule for the customer. |
| quotes | credit_terms_id | The proposed payment terms for the technical project. |
| sales_orders | credit_terms_id | The finalized payment terms for the order. |

## Common Query Patterns
```sql
-- Find all active credit policies for a specific branch
SELECT name, description 
FROM credit_terms 
WHERE store_id = '<uuid>' AND is_active = true;

-- List all clients who are on 'Cash on Delivery' (COD) terms
SELECT c.name 
FROM clients c
JOIN credit_terms t ON c.credit_terms_id = t.id
WHERE t.name = 'COD';
```

## Indexes
- *Relies on standard PK and FK constraints for relational integrity.*
