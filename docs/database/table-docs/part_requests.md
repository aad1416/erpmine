# `part_requests`

## Searchable Aliases
material requisitions, stock requests, part orders, procurement needs, internal requests

## Description
The `part_requests` table is the **Internal Demand Trigger** for the warehouse. It acts as a formal requisition document, allowing technicians, engineers, or production workers to request specific components from stock to satisfy a manufacturing build, a field service repair, or a general branch requirement.

In the **Lyndom** (the current PostgreSQL ERP) workflow, this is the "Shopping List" that precedes a physical move of goods. Once a part request is submitted, it is typically triaged by the warehouse team, who then perform the actual "Issuance" of parts.

## ⚙️ The Materials Request Workflow
1.  **Demand Generation**: A user on the shop floor or in the field identifies a need for materials and creates a `part_request` record.
2.  **Asset Linking**: The request is typically anchored to a specific `unit_id` (The machine being built/fixed) to ensure precise cost-tracking.
3.  **Warehouse Assignment**: The request can be assigned to a specific warehouse clerk (`assigned_to_id`) for picking.
4.  **Picking/Triage**: The clerk reviews the `part_request_line_items` to verify stock availability.
5.  **Fulfillment**: Upon successful picking, the status is updated, and the record typically triggers a `goods_issues` event to physically subtract the items from inventory.

## ⚠️ SQL-Critical Behaviors
- **Traceability Link**: This table is the "Conceptual Bridge" between a technical need (the Task) and a physical inventory change (the Issue). 
- **Operational Identity**: The `number` column provides the human-readable tracking ID used by technicians to check the status of their parts (e.g., "Where is my request PR-2001?").
- **Cost Pillar**: Although costs are primarily tracked in the `units` table, the `part_request` is the mandatory audit trail explaining *Why* a part was withdrawn from stock.

## Columns (14 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch making the request. |
| number | text | no | — | **Request ID**: Human-readable serial for tracking. |
| date | int8 | no | — | The date the request was initiated (Epoch). |
| sales_order_id | uuid | yes | — | Link to the customer contract necessitating the parts. |
| unit_id | uuid | yes | — | **Target Asset**: Link to the physical serial number being built or repaired. |
| description | text | yes | — | General notes regarding the urgency or purpose of the request. |
| assigned_to_id | uuid | yes | — | **The Fulfiller**: Link to the user (e.g., Warehouse Clerk) responsible for picking. |
| status | enum | no | — | **Current State**: (e.g., `PENDING`, `FULFILLED`). |
| requested_by_id | uuid | no | — | **The Requestor**: Link to the technician/user who needs the parts. |
| creator_id | uuid | no | — | The user who registered the request in the system. |
| is_active | bool | no | true | Global status flag. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| sales_order_id | sales_orders | id | set null |
| unit_id | units | id | set null |
| assigned_to_id | users | id | set null |
| requested_by_id | users | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| part_request_line_items | request_id | The specific SKU-level requirements for this materials request. |
| units | part_request_id | A link on the unit record to the request which satisfied its components. |

## Common Query Patterns
```sql
-- List all active part requests for the "Warehouse" team to fulfill
SELECT number, description, requested_by_id 
FROM part_requests 
WHERE status = 'PENDING' AND is_active = true 
ORDER BY date ASC;

-- Find all parts requested specifically for a high-priority Sales Order build
SELECT number, status, unit_id 
FROM part_requests 
WHERE sales_order_id = '<uuid>';
```

## Indexes
- *Uses a high-performance btree index on `unit_id` for rapid asset-level logistics auditing.*
