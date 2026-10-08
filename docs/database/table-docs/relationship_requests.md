# `relationship_requests`

## Searchable Aliases
B2B connections, partner requests, store-to-store links, account linkages

## Description
The `relationship_requests` table governs the **Inter-Store B2B Network** within the **Lyndom** (the current PostgreSQL ERP) ecosystem. In a multi-tenant or multi-branch organization, stores do not have automatic access to each other's catalogs. This table manages the formal handshake where one store (the Originator) requests to become a Client or Vendor of another store (the Target).

An `ACCEPTED` relationship in this table is the technical prerequisite that unlocks the **Inter-Store Purchasing** module.

## ⚙️ The Relationship Workflow
1.  **Request**: Store A (Origin) sends a request to Store B (Target). They specify the `purpose` (e.g., they want to become a `CLIENT` of Store B).
2.  **Notification**: The request enters the system as `PENDING`. The Target Store is notified of the new B2B proposal.
3.  **Governance**: Store B can either `ACCEPT` or `REJECT` the relationship.
4.  **Activation**: Once `ACCEPTED`, Store A can now browse Store B's product catalog and issue **Purchase Quotes** to them.

## ⚠️ SQL-Critical Behaviors
- **Functional Gatekeeper**: Inter-store logic (such as creating cross-store purchase orders) must always verify that an active, accepted record exists here before allowing the transaction.
- **Directional Logic**: If Store A is a `CLIENT` of Store B, it does **not** automatically mean Store B is a client of Store A. Relationships are directional and purpose-specific.
- **Local Identity**: The `local_id` stores the specific account or cross-reference name by which the stores recognize each other in their respective internal ledgers.

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Timestamp of the relationship proposal. |
| updated_at | timestamptz | no | — | Timestamp of the last status change. |
| store_id | uuid | no | — | **Originating Store**: The branch initiating the partnership request. |
| target_store_id | uuid | no | — | **Target Store**: The branch receiving the partnership request. |
| purpose | enum | no | — | **Link Type**: Either `CLIENT` or `VENDOR`. |
| status | enum | no | — | **State of Approval**: (`PENDING`, `ACCEPTED`, `REJECTED`). |
| local_id | text | no | — | The cross-store reference ID or account number for the partnership. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| target_store_id | stores | id | cascade |

## Common Query Patterns
```sql
-- Find all authorized internal suppliers (Vendors) for my branch
SELECT target_store_id, local_id 
FROM relationship_requests 
WHERE store_id = '<my_branch_uuid>' AND purpose = 'VENDOR' AND status = 'ACCEPTED';

-- List pending partnership requests awaiting my store's approval
SELECT store_id, purpose, local_id 
FROM relationship_requests 
WHERE target_store_id = '<my_branch_uuid>' AND status = 'PENDING';
```

## Indexes
- *Relies on standard PK and FK constraints for store-to-store relational integrity.*
