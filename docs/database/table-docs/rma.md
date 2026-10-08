# `rma`

## Searchable Aliases
returns, return merchandise authorization, product returns, faulty items, customer refunds, credit notes

## Description
The `rma` (Return Merchandise Authorization) table is the cornerstone of the **Reverse Logistics** and **Warranty** modules in the **Lyndom** (the current PostgreSQL ERP) system. Unlike a simple warehouse receiving record, an RMA is a legal and technical authorization—it signifies that the business has approved a customer's request to return physical assets, typically inside a repair or field service context.

It manages the flow of defective units back to the warehouse and synchronizes the dispatch of replacement parts, ensuring that inventory and financial balances remain accurate during the service cycle.

## ⚙️ The RMA & Service Workflow
1.  **Issue Detection**: A Field Service Ticket (`ticket_id`) is created for a customer's technical issue.
2.  **Authorization**: If the unit needs to come back for repair, an RMA is issued. The system records the `status` as `OPEN`.
3.  **Cross-Shipment (Advance Exchange)**: The system uses the `are_parts_being_shipped` flag if a replacement is sent to the client immediately.
4.  **Arrival**: Once the defective part physically arrives, the `receive_date` is recorded, and the system updates the inventory ledger to account for the returned asset.
5.  **Warranty Claims**: If `is_warranty = true`, the system tags the transaction for future financial recovery from the manufacturer.

## ⚠️ SQL-Critical Behaviors
- **Mandatory Anchor**: This table is the absolute starting point for *any* query involving customer returns, refunds, or reverse logistics. Do not shortcut directly to shipment or payment tables when evaluating return events.
- **Field Service Anchor**: A link to a `ticket_id` is mandatory. This reinforces that RMAs in the current system are technically-driven rather than simple "Change of Mind" consumer returns.
- **Expiry Control**: The `expire_date` prevents customers from holding an authorization indefinitely, allowing the business to reclaim allocated inventory or void the RMA if the part isn't returned within a set window.
- **Identity of Authorization**: The `authorized_by_...` columns provide the audit trail of the manager or user who sanctioned the return.

## Columns (22 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the return. |
| ticket_id | uuid | no | — | **Service Link**: The specific technical ticket that triggered the return. |
| number | text | no | — | **RMA ID**: Human-readable serial number (e.g., RMA-9003). |
| date | int8 | no | — | The date the authorization was issued. |
| expire_date | int8 | yes | — | The deadline for the customer to return the goods. |
| status | enum | no | — | **Current State**: (Example of actual values includes: `OPEN`). |
| reason | text | no | — | Detailed explanation of the failure or return motivation. |
| customer_owned | bool | yes | false | If `true`, the asset belongs to the customer (Return for Repair) rather than the store (Return for Credit). |
| authorized_date | int8 | yes | — | When the return was officially approved. |
| authorized_by_id | uuid | yes | — | Link to the user who authorized the return. |
| authorized_by_name | text | yes | — | Name of the authorizing user for printed vouchers. |
| special_instructions | text | no | — | Specific packaging or shipping instructions for the client. |
| are_parts_being_shipped | bool | yes | false | If `true`, a replacement is being sent out as part of an exchange. |
| are_parts_being_returned | bool | yes | false | If `true`, the customer is physically returning their unit. |
| receive_date | int8 | yes | — | The date the defective asset arrived at the warehouse (Epoch). |
| sales_order_id | uuid | yes | — | Link to the original commercial contract. |
| is_warranty | bool | yes | false | If `true`, the return is covered under manufacturer/service warranty. |
| note | text | yes | — | Internal-only comments or failure analysis. |
| creator_id | uuid | no | — | The user who registered the RMA request. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| ticket_id | field_service_tickets | id | cascade |
| authorized_by_id | users | id | set null |
| sales_order_id | sales_orders | id | set null |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| rma_line_items | rma_id | The specific physical assets being returned under this authorization. |

## Common Query Patterns
```sql
-- Find all outstanding RMAs that have exceeded their expiry date
SELECT number, ticket_id, expire_date 
FROM rma 
WHERE status = 'OPEN' AND expire_date < EXTRACT(EPOCH FROM NOW());

-- Identify all warranty-related returns for a specific store branch
SELECT number, reason, authorized_by_name 
FROM rma 
WHERE is_warranty = true AND store_id = '<uuid>';
```

## Indexes
- *Relies on standard relational indexes on `ticket_id` and `store_id` for document generation.*
