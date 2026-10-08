# `units`

## Searchable Aliases
serialized products, individual machines, specific items, unit tracking, physical assets

## Description
The `units` table is the **As-Built Registry** and financial consolidation point for all physical assets within the **Lyndom** (the current PostgreSQL ERP) ecosystem. While the `items` table defines a general product, the `units` table defines a specific, unique physical machine (identified by a `serial_number`).

Beyond simple tracking, this table acts as a **Cost Accumulator**. It aggregates all manufacturing labor, material costs (parts), and overhead tariffs incurred during the production of a specific unit. This ensures that the ERP can report on the exact profitability of every single machine delivered to a customer.

## ⚙️ The Asset Lifecycle Workflow
1.  **Commitment**: When a Sales Order is placed, a "Placeholder" unit record is created in `ORDERED` status.
2.  **Production**: As technicians log time and parts against the machine, the `labor_cost` and `part_cost` columns are updated in real-time. The status moves to `IN_PROGRESS`.
3.  **Completion**: Once the build is finished, the system calculates the `initial_valuation`. The `ready_to_ship` flag is toggled to `true`.
4.  **Logistics**: The unit is assigned to a shipment, updating its status to `IN_SHIPPING_PROGRESS` and then `SHIPPED` upon carrier pickup.
5.  **Field Service**: Once `DELIVERED`, the unit record becomes the historical anchor for all future Field Service Tickets and Warranty claims.

## ⚠️ SQL-Critical Behaviors
- **Granular Financials**: This table stores the most precise cost data in the system. Columns like `sum_of_jobrecords_tariff` and `labor_cost` reflect the actual human effort expended on that specific serial number.
- **The Lead Time Audit**: The `actual_lead_time` (difference between order and ship date) allows the business to measure manufacturing efficiency against the quoted `lead_time`.
- **Identity Pair**: High-integrity lookups should always use the combination of `model_number` and `serial_number`.

## Columns (32 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that manufactured/sold the unit. |
| sales_order_id | uuid | no | — | **Contract Link**: The customer's purchase order for this machine. |
| sales_order_line_item_id | uuid | no | — | Link to the specific requirement line in the Sales Order. |
| item_store_id | uuid | no | — | **SKU Link**: The product category this physical asset belongs to. |
| status | enum | no | — | **Current State**: (e.g., `ORDERED`, `IN_PROGRESS`, `SHIPPED`, `DELIVERED`). |
| name | text | no | — | Short identifier (often matches the model name). |
| labor_cost_per_hour | numeric(12,2) | no | 0 | The hourly rate applied to labor on this specific unit build. |
| labor_cost | numeric(12,2) | no | 0 | **Accumulated Labor**: Total employee cost recorded for construction. |
| item_labor_cost | numeric(12,2) | no | 0 | Standard labor cost target defined by the item master. |
| lead_time | int4 | yes | — | The promised delivery window (Days). |
| actual_lead_time | int4 | yes | — | **Efficiency Metric**: The actual days taken to complete the unit. |
| sum_of_jobrecords_tariff | numeric(12,2) | no | 0 | Accumulated overhead/tariff costs from production jobs. |
| sum_of_jobrecords_overhead | numeric(12,2) | no | 0 | Accumulated indirect shop floor costs. |
| initial_valuation | numeric(12,2) | no | 0 | **Balance Sheet Value**: Total recorded value at the point of completion. |
| part_valuation | numeric(12,2) | no | 0 | Valuation based purely on the sub-components used. |
| part_cost | numeric(12,2) | no | 0 | **Total Material Cost**: Sum of current prices for all parts in the unit. |
| difference_between_part_cost_and_item_override | numeric(12,2) | no | 0 | Variance between estimated and actual material costs. |
| description | text | no | — | Detailed technical description of the specific asset. |
| model_number | text | no | — | **Engineering ID**: The product model code. |
| serial_number | text | no | — | **Unique ID**: The physical serial number plate ID. |
| ship_date | int8 | yes | — | The date the carrier picked up the unit (Epoch). |
| estimated_ship_date | int8 | yes | — | The target logistics date (Epoch). |
| number | text | no | — | Internal serial ID for the record. |
| is_active | bool | no | true | Global status flag. |
| creator_id | uuid | no | — | The user who registered the unit in the system. |
| has_part_request_generated | bool | no | false | If `true`, a purchase request has been issued for missing components. |
| is_issued | bool | no | false | **WIP Flag**: If `true`, the unit has been released to the production floor. |
| part_request_id | uuid | yes | — | Link to the specific procurement request in `part_requests.id`. |
| ready_to_ship | bool | no | false | **QC Gate**: If `true`, the machine is built, inspected, and waiting for logistics. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| sales_order_id | sales_orders | id | cascade |
| sales_order_line_item_id | sales_order_line_items | id | cascade |
| item_store_id | item_stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| field_service_tickets | unit_id | The technical service history for this specific machine. |
| unit_bom_records | unit_id | The "As-Built" bill of materials for this specific serial number. |
| individual_warranties | unit_id | The legal coverage dates and terms for this physical asset. |

## Common Query Patterns
```sql
-- Audit Unit Profitability: Difference between Sales Price and accumulated costs
SELECT u.serial_number, sol.price as sales_price, (u.labor_cost + u.part_cost) as total_cost
FROM units u
JOIN sales_order_line_items sol ON u.sales_order_line_item_id = sol.id
WHERE u.status = 'DELIVERED';

-- Find all units currently on the production floor (Issued but not ready to ship)
SELECT serial_number, model_number, created_at 
FROM units 
WHERE is_issued = true AND ready_to_ship = false;
```

## Indexes
- *Includes high-performance btree indexes on `item_store_id` and `sales_order_id` for fleet-level reporting.*
