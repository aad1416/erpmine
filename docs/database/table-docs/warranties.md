# `warranties`

## Searchable Aliases
protection plans, service contracts, guarantee details, warranty tracking

## Description
The `warranties` table is the legal and technical record of coverage for physical assets in the field. Every high-value machine registered in the `units` table typically has a corresponding `warranties` record that defines the duration and specific terms of the company's guarantee.

In the **Lyndom** (the current PostgreSQL ERP) service module, this table provides warranty coverage data. When a technician opens a Field Service Ticket, the system joins through the `units` table to determine if the labor and parts costs should be billed to the client or absorbed as a warranty expense by the business.

> [!IMPORTANT]
> **No Direct `store_id` or `client_id` Column**: This table does **not** contain a `store_id`. It is strictly a child of `unit_id`. Tenant isolation is inherited by joining `warranties` → `units` → `store_id`. Never query this table alone to determine branch ownership.

## ⚙️ The Coverage Lifecycle Workflow
1.  **Registration**: Upon shipment or delivery of a physical unit, a warranty record is generated.
2.  **Clock Start**: The `start` timestamp (Epoch) is typically set to the `units.ship_date` or `actual_delivery_date`.
3.  **Clock End**: The `end` timestamp is calculated based on the product's predefined coverage period (e.g., +365 days).
4.  **Verification**: During a service call, the system compares the current date against the `start` and `end` window. If the ticket date falls within the range and the status is `ACTIVE`, the repair is flagged as "Covered."
5.  **Expiration**: Once the `end` date passes, the system automatically treats the machine as "Out of Warranty" for all future service requests.

## ⚠️ SQL-Critical Behaviors
- **Asset Specificity**: Warranties are linked 1-to-1 with a `unit_id`. This allows the business to extend or modify terms for a specific serial number without affecting other machines of the same model.
- **Status Control**: The `status` enum (e.g., `ACTIVE`, `VOIDED`, `EXPIRED`) allows managers to manually terminate coverage if a unit has been tampered with or if the service contract has been breached.
- **Audit Number**: The `number` column provides a human-readable identifier (e.g., WAR-10022) for use in customer communications and printed certificates.

## Columns (11 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| number | text | no | — | **Warranty ID**: Human-readable serial number. |
| start | int8 | no | — | **Coverage Start**: The exact timestamp when protection begins (Epoch). |
| end | int8 | no | — | **Coverage End**: The exact timestamp when protection expires (Epoch). |
| name | text | no | — | Name of the warranty plan (e.g., "Full Parts & Labor - 2 Year"). |
| notes | text | yes | — | Internal notes regarding the coverage status or exceptions. |
| terms | text | yes | — | **Legal Terms**: The specific contractual language governing the coverage. |
| status | enum | no | — | **State**: (e.g., `ACTIVE`, `EXPIRED`, `VOIDED`). |
| unit_id | uuid | no | — | **The Protected Asset**: Link to the unique physical unit in `units.id`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| unit_id | units | id | cascade |

## Common Query Patterns
```sql
-- Identify all units whose warranty will expire in the next 30 days
SELECT number, unit_id, "end" 
FROM warranties 
WHERE status = 'ACTIVE' 
  AND "end" BETWEEN EXTRACT(EPOCH FROM NOW()) AND (EXTRACT(EPOCH FROM NOW()) + 2592000);

-- Verify coverage for a specific serial number
SELECT w.status, w.start, w.end 
FROM warranties w
JOIN units u ON w.unit_id = u.id
WHERE u.serial_number = 'SN-882291';
```

## Indexes
- *Uses standard relational indexes on `unit_id` and `number` for rapid coverage verification.*
