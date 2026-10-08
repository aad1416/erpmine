# `goods_issues`

## Searchable Aliases
material release, stock withdrawal, warehouse exit, component issuance, parts release

## Description
The `goods_issues` table is the **Official Consumption Registry** of the **Lyndom** (the current PostgreSQL ERP) system. It records the irreversible physical removal of inventory from the warehouse shelf to satisfy an internal need. 

While a `part_request` is the declaration of a "Need," the `goods_issue` is the confirmation of the "Fulfillment." This table is the primary driver for updating stock levels, adjusting the financial value of the warehouse, and assigning material costs to specific manufacturing jobs or field service events.

## ⚙️ The Goods Withdrawal Workflow
1.  **Requisition Reference**: A warehouse clerk selects an approved `part_request`.
2.  **Physical Picking**: The clerk retrieves the physical components from the shelf.
3.  **Issue Registration**: The `goods_issues` header is created, linking to either a **Sales Order** (if for a build) or a **Field Service Ticket** (if for a repair).
4.  **Security Sign-off**: The system captures the `issuer_id` (The picker) and the `creator_id` (The registrar), creating an audit trail of responsibility.
5.  **Inventory Decrement**: Once the line items are recorded, the system subtracts the quantities from the `inventory_items` balance.

## ⚠️ SQL-Critical Behaviors
- **Mandatory Request Link**: Every issue must reference an originating `part_request_id`. This prevents "Invisible Inventory Loss" by ensuring every exit has a documented justification.
- **Polymorphic Billing Target**: The table can point to a `sales_order_id` or a `field_service_ticket_id`. This allows a single logistics workflow to serve both the Production Floor and the Service Technician.
- **Financial Baseline**: The `date` on this record is the "Date of Consumption," which is the benchmark used by Finance for monthly COGS (Cost of Goods Sold) calculations.

## Columns (13 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| part_request_id | uuid | no | — | **Trigger Link**: The formal requisition in `part_requests.id` being satisfied. |
| store_id | uuid | no | — | **Tenant ID**: The branch issuing the goods. |
| number | text | no | — | **Issue ID**: Human-readable serial for logistics tracking. |
| date | int8 | no | — | The date the withdrawal occurred (Epoch). |
| description | text | no | — | General notes about the issuance event. |
| sales_order_id | uuid | yes | — | **Commercial Target**: Used when parts are issued for a build or sales contract. |
| issuer_id | uuid | no | — | **The Picker**: Link to the user who physically removed the parts. |
| creator_id | uuid | no | — | The user who registered the issue record. |
| field_service_ticket_id | uuid | yes | — | **Service Target**: Used when parts are issued for a Field Service repair. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| part_request_id | part_requests | id | cascade |
| sales_order_id | sales_orders | id | set null |
| field_service_ticket_id | field_service_tickets | id | set null |
| issuer_id | users | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| goods_issue_line_items | goods_issue_id | The specific SKU and Serial numbers withdrawn in this event. |
| goods_issue_line_item_returns | goods_issue_id | Handles the return of unused parts from a technician back to the warehouse. |

## Common Query Patterns
```sql
-- Audit: Find all goods issued to a specific Field Service Ticket (FST)
SELECT number, description, date 
FROM goods_issues 
WHERE field_service_ticket_id = '<uuid>';

-- Track Logistics Velocity: Average time between Request and Issue
SELECT AVG(gi.date - pr.date) as fulfillment_seconds
FROM goods_issues gi
JOIN part_requests pr ON gi.part_request_id = pr.id;
```

## Indexes
- *Uses a high-performance btree index on `created_at` for monthly financial reporting.*
