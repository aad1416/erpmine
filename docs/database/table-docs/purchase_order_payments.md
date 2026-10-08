# `purchase_order_payments`

## Searchable Aliases
vendor payments, po settlement, accounts payable ledger, procurement finance

## Description
The `purchase_order_payments` table acts as the financial settlement ledger for the procurement module. It creates a formal link between a physical **Payment Record** (Check, Wire, or Credit Card transaction) and the **Purchase Order** (PO) it intended to satisfy. 

Because one payment can be split across multiple POs, this table allows for precise "Balance Tracking" at the itemized order level.

## ⚙️ The Settlement Workflow
1.  **Fund Disbursement**: The accounting department creates a global `payment` record (line-item in the general ledger).
2.  **Allocation**: A user allocates all or part of that payment to a specific `purchase_order_id`.
3.  **Balance Sync**: The system adds the `amount` from this record to the `paid_amount` field on the parent `purchase_orders` header.
4.  **Closing**: If the total of all payments here matches the PO total, the PO status is updated to `PAID`.

## ⚠️ SQL-Critical Behaviors
- **Accounts Payable Ledger**: These records provide the authoritative proof of payment to a vendor. Summing these records for a specific vendor provides the "Total Spend" or "Paid Balance."
- **Voiding Logic**: If a check is voided or a wire is reversed, the `is_active` flag is set to `false`. The system immediately subtracts that amount from the PO's `paid_amount`, reopening the balance for future settlement.

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch issuing the payment. |
| amount | numeric(12,2) | no | — | **The Allocation**: The specific dollar amount applied to this PO from the master payment. |
| purchase_order_id | uuid | no | — | Link to the parent contract in `purchase_orders.id`. |
| payment_id | uuid | no | — | Link to the master financial transaction in `payments.id`. |
| is_active | bool | no | true | Status flag. If `false`, the payment allocation is voided. |
| creator_id | uuid | no | — | The accountant or user who authorized the payment allocation. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| purchase_order_id | purchase_orders | id | cascade |
| payment_id | payments | id | cascade |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- List all cash allocations to a specific Purchase Order
SELECT amount, created_at, is_active 
FROM purchase_order_payments 
WHERE purchase_order_id = '<uuid>';

-- Find the master payment transaction ID for a PO allocation
SELECT payment_id 
FROM purchase_order_payments 
WHERE purchase_order_id = '<uuid>' AND is_active = true;
```

## Indexes
- *Relies on standard PK/FK constraints to support rapid accounts payable auditing.*
