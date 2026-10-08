# `job_records_issue_line_items`

## Searchable Aliases
production issuance, work order parts, job material consumption, assembly line parts

## Description
The `job_records_issue_line_items` table is the **Global Traceability Bridge** of the **Lyndom** (the current PostgreSQL ERP) system. It represents the high-precision linkage between a physical inventory consumption event and a specific engineering requirement on a machine's Bill of Materials (BOM).

In industries requiring high reliability (e.g., Lighting, Aerospace, Energy), it is not enough to know *that* a part was issued; one must know *which specific vendor batch* or *which specific receipt* satisfied that exact line item on the blueprint. This table is the "DNA Link" that provides that level of technical and financial accountability.

## ⚙️ The Traceability Chain Workflow
1.  **Issuance**: A part is physically withdrawn from stock, creating a `goods_issue_line_items` record.
2.  **Assignment**: The system identifies which line in the unit's **"As-Built" BOM** (`unit_bom_records`, referenced here as `jobrecord_id`) this part is satisfying.
3.  **Back-Tracing**: To ensure 100% auditability, the system also captures the original **Receipt** (`receive_id`) and **Purchase Order** (`purchase_order_id`) associated with that physical piece of inventory.
4.  **Marrying the Data**: This record is created to "Glue" all these identifiers together. 
5.  **Audit Capability**: A user can now query a physical serial number and find the exact vendor source for every internal screw, board, and motor.

## ⚠️ SQL-Critical Behaviors
- **The Ultimate Multi-Join Hub**: This table is the only place in the ERP where **Purchasing** (POs), **Logistics** (Receives/Issues), **Inventory** (Items), **Manufacturing** (Unit BOMs), and **Assets** (Units) all intersect.
- **Job Record Clarification**: The `jobrecord_id` consistently refers to the `unit_bom_records` table, which represents a specific line entry on a unique machine's build manual.
- **Financial Baseline**: The `quantity` here is the "Actual Consumption Amount" that drives the final technical valuation of the unit.

## Columns (11 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| jobrecord_id | uuid | no | — | **Engineering Link**: The specific line in `unit_bom_records.id` being satisfied. |
| unit_id | uuid | no | — | **Asset Link**: The physical machine serial number receiving the part. |
| issue_line_item_id | uuid | no | — | **Logistics Link**: The inventory withdrawal event in `goods_issue_line_items.id`. |
| inventory_item_id | uuid | no | — | **Material Link**: The specific physical stock record in `inventory_items.id`. |
| receive_id | uuid | yes | — | **Origin Link (Header)**: The vendor receipt where this part originally arrived. |
| receive_line_item_id | uuid | yes | — | **Origin Link (Line)**: The specific line of the vendor receipt. |
| purchase_order_id | uuid | yes | — | **Commercial Link**: The contract in `purchase_orders.id` used to buy the part. |
| quantity | numeric(12,2) | no | — | **Consumed Amount**: The count of parts physically applied to this assembly step. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| jobrecord_id | unit_bom_records | id | cascade |
| unit_id | units | id | cascade |
| issue_line_item_id | goods_issue_line_items | id | cascade |
| inventory_item_id | inventory_items | id | cascade |
| receive_id | receives | id | set null |
| receive_line_item_id | receive_line_items | id | set null |
| purchase_order_id | purchase_orders | id | set null |

## Common Query Patterns
```sql
-- "Where did this component come from?": Find the PO for a part on a specific unit
SELECT po.number as po_no, v.name as vendor_name
FROM job_records_issue_line_items jril
JOIN purchase_orders po ON jril.purchase_order_id = po.id
JOIN vendors v ON po.vendor_id = v.id
WHERE jril.unit_id = '<unit_uuid>' AND jril.inventory_item_id = '<item_uuid>';

-- Assembly Audit: List all physical receipt dates for parts inside a machine
SELECT r.date as received_on, ubr.item_no
FROM job_records_issue_line_items jril
JOIN receives r ON jril.receive_id = r.id
JOIN unit_bom_records ubr ON jril.jobrecord_id = ubr.id
WHERE jril.unit_id = '<unit_uuid>';
```

## Indexes
- *Relies on standard relational indexes on `unit_id` and `jobrecord_id` for technical bill-of-materials auditing.*
