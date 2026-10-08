# `location_change_logs`

## Searchable Aliases
stock movement history, bin transfers, warehouse re-org, relocation audit, transfer logs

## Description
The `location_change_logs` table serves as the immutable "Chain of Custody" for physical inventory movement. Every time an item is moved from one warehouse bin to another, the **Lyndom** (the current PostgreSQL ERP) system creates a record here. 

This provides a detailed audit trail that allows managers to reconstruct the physical travel path of an item and identify which staff member was responsible for the movement.

## ⚙️ The Movement Workflow
1.  **Transfer Initiation**: A warehouse worker initiates a bin-to-bin move (either via a formal Stock Transfer or a manual location update).
2.  **Audit Capture**: The system identifies the current location (`before_location_id`) and the target location (`after_location_id`).
3.  **Timestamping**: The `time` (epoch) and `created_at` timestamps are generated to provide a precise chronological record of the transit.
4.  **Logging**: The record is saved, linking the **Mover** (`user_id`), the **SKU** (`item_store_id`), and the specific physical locations.

## ⚠️ SQL-Critical Behaviors
- **Immutable History**: Unlike the `inventory_items` table (which is updated to reflect current state), this table is an append-only ledger. You should never update or delete records here as they form the core of warehouse audit reporting.
- **Velocity Tracking**: By analyzing these logs, the system can determine how frequently an item is moved, which helps in "Warehouse Slotting" (placing high-velocity items in easier-to-access bins).

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Timestamp of the log entry creation. |
| updated_at | timestamptz | no | — | System metadata (logs are typically not updated). |
| store_id | uuid | no | — | **Tenant ID**: The branch where the movement occurred. |
| user_id | uuid | no | — | **The Mover**: Foreign key to `users.id` identifying the staff member who relocated the stock. |
| before_location_id | uuid | no | — | **Source Bin**: The location where the item was previously stored. |
| after_location_id | uuid | no | — | **Destination Bin**: The new location where the item was placed. |
| item_store_id | uuid | no | — | The specific SKU listing that was relocated. |
| time | int8 | no | — | Epoch timestamp for precise chronological sorting in forensic reports. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| user_id | users | id | cascade |
| before_location_id | locations | id | cascade |
| after_location_id | locations | id | cascade |
| item_store_id | item_stores | id | cascade |

## Common Query Patterns
```sql
-- Track the recent movement history of a specific SKU
SELECT u.username, l1.name as from_bin, l2.name as to_bin, scl.created_at
FROM location_change_logs scl
JOIN users u ON scl.user_id = u.id
JOIN locations l1 ON scl.before_location_id = l1.id
JOIN locations l2 ON scl.after_location_id = l2.id
WHERE item_store_id = '<uuid>'
ORDER BY scl.created_at DESC;
```

## Indexes
- *Relies on standard FK and PK indexing to support movement audit reporting.*
