# `cycle_counts`

## Searchable Aliases
inventory audits, stock counting, reconciliation, warehouse audit, verification

## Description
The `cycle_counts` table manages the physical audit and reconciliation of inventory levels. It provides a formal workflow to compare the "System Reality" (what the ERP thinks is in stock) against the "Physical Reality" (what the warehouse staff actually counted on the shelves). 

By using cycle counts instead of a full warehouse shutdown, the **Lyndom** (the current PostgreSQL ERP) system allows for continuous inventory accuracy without stopping operations.

## ⚙️ The Reconciliation Workflow
1.  **Creation**: A count is initiated for a specific SKU (`item_store_id`). The system snapshots the current quantity in `item_on_hand_quantity`.
2.  **Assignment**: The count is assigned to a specific staff member (`assignee_first_name`, `assignee_last_name`) and given a tracking `tag_number`.
3.  **Reporting**: After physically counting the units, the staff member enters the actual number in `reported_count`.
4.  **Resolution**: A manager reviews the variance. If accepted, the `resolved_quantity` is finalized and the `resolved` flag is set to `true`, which updates the master `item_stores` inventory level.

## ⚠️ SQL-Critical Behaviors
- **Snapshot Logic**: The `item_on_hand_quantity` is a "frozen" value captured at the moment the count started. It must be compared against `reported_count` to determine the inventory variance.
- **Status Lifecycle**: A count remains in the `NEW` status until it is audited and finalized, at which point it moves to `COMPLETED`.
- **Audit Lead**: The `tag_number` acts as the physical link to a paper trail or shelf tag, ensuring that audit results can be traced back to a specific bin or pallet.

## Columns (16 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Timestamp when the audit event was registered. |
| updated_at | timestamptz | no | — | Timestamp of last activity on the count record. |
| store_id | uuid | no | — | **Tenant ID**: The branch conducting the audit. |
| item_store_id | uuid | no | — | The specific SKU listing being audited. |
| status | enum | no | — | Current state: `NEW` (Open) or `COMPLETED` (Reconciled). |
| date | int8 | no | — | Epoch timestamp of the scheduled count date. |
| reported_count | int4 | no | — | **Physical Reality**: The number of units physically found on the shelf. |
| item_on_hand_quantity | numeric(12,2) | no | — | **System Reality**: The stock level the ERP expected to find (snapshot). |
| resolved | bool | no | false | If `true`, the variance has been accepted and inventory updated. |
| resolved_quantity | numeric(12,2) | yes | — | The final quantity value committed to the inventory master. |
| assignee_first_name | text | no | — | First name of the employee performing the physical count. |
| assignee_last_name | text | no | — | Last name of the employee performing the physical count. |
| tag_number | text | no | — | The unique ID of the physical audit tag used in the warehouse. |
| direct | bool | no | false | If `true`, indicates a count initiated directly from a mobile device or scanner. |
| creator_id | uuid | no | — | The manager or supervisor who initiated the audit. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| item_store_id | item_stores | id | cascade |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Calculate the variance for all open (unresolved) cycle counts
SELECT 
    tag_number, 
    item_on_hand_quantity as system_qty, 
    reported_count as physical_qty,
    (reported_count - item_on_hand_quantity) as variance
FROM cycle_counts 
WHERE resolved = false;

-- Find all counts performed by a specific staff member
SELECT tag_number, status, date 
FROM cycle_counts 
WHERE assignee_last_name = 'Smith';
```

## Indexes
- *Includes indexes on `status`, `resolved`, and `item_store_id` to facilitate rapid reconciliation reporting.*
