# `payments`

## Searchable Aliases
financial transactions, cash receipts, bank transfers, cheques, POS payments, vouchers, ledger, monetary events

## Description
The `payments` table is the **General Financial Ledger** of the **Lyndom** (the current PostgreSQL ERP) system. It acts as a centralized "Voucher Registry" for physical and digital monetary transactions, including cash receipts, cheque deposits, and bank transfers.

This table is designed as a standalone utility, allowing the ERP to record cash-flow events independently of specific sales or purchase orders. This flexibility is essential for handling miscellaneous income, overhead expenses, or multi-order payment allocations. **Note:** This is the primary ledger for *customer* payments and *customer* refunds. It should not be confused with `purchase_order_payments`, which is strictly for outbound vendor payouts.

## ⚙️ The Financial Transaction Workflow
1.  **Payment Event**: A transaction occurs (e.g., a customer delivers a physical cheque or a cash deposit is made at a branch).
2.  **Voucher Creation**: An administrator creates a `payments` record, defining the `payment_type` (e.g., `CHEQUE`, `CASH`, `TRANSFER`).
3.  **Governance Recording**: For high-risk payments (like cheques), the system captures the `reference_number`, the `issuer` name, and the `receiver_national_id` for legal compliance.
4.  **Balance Reconciliation**: Other system modules (like `purchase_order_payments`) can link to these records to reconcile open invoices against the recorded cash-flow.
5.  **Audit trail**: The `creator_id` and `date` ensure that every monetary movement is traced back to a specific authorized employee and event window.

## ⚠️ SQL-Critical Behaviors
- **Regulated Instrument Tracking**: The inclusion of `receiver_national_id` and `cheque_status` indicates that the ERP handles bank-draft and cheque lifecycles which require strict identity verification.
- **Precision Accounting**: The `amount` column uses `numeric(12,2)`, ensuring the database can handle multi-million dollar transactions down to the cent without rounding errors.
- **Flexible Reference**: The `destination` and `reference_number` fields provide the "Paper Trail" needed to link the ERP record to physical bank statements or manual paperwork.

## Columns (16 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch receiving or issuing the payment. |
| amount | numeric(12,2) | no | — | **The Value**: The exact monetary amount of the transaction. |
| description | text | no | — | Human-readable notes explaining the nature of the payment. |
| date | int8 | no | — | The authoritative date of the transaction (Epoch). |
| payment_type | enum | no | — | **Payment instrument** (`payment_type_enum`): `CASH`, `ONLINE`, `CHEQUE`. |
| cheque_status | enum | yes | — | **Cheque instrument lifecycle** (`cheque_status_enum`): `NOT_REGISTERED`, `REGISTERED_BY_ISSUER`, `CONFIRMED_BY_RECEIVER`, `CASHED`. Use `CASHED` for cleared/settled cheques — not `CLEARED`. |
| destination | text | yes | — | The target bank account or internal cash-drawer location. |
| reference_number | text | yes | — | The bank transaction ID or physical cheque number. |
| issuer | text | yes | — | The name of the entity who provided the funds. |
| receiver | text | yes | — | The name of the person or entity who accepted the funds. |
| receiver_national_id | text | yes | — | Regulatory ID of the receiver (used for high-value audit compliance). |
| creator_id | uuid | no | — | The employee who entered the payment into the system. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |

## Enums Used

### `cheque_status_enum`
(Live DB values): `NOT_REGISTERED`, `REGISTERED_BY_ISSUER`, `CONFIRMED_BY_RECEIVER`, `CASHED`.

### `payment_type_enum`
(Live DB values): `CASH`, `ONLINE`, `CHEQUE`.

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- List all cleared cheques received by a specific store branch
SELECT amount, issuer, date 
FROM payments 
WHERE store_id = '<uuid>' 
  AND payment_type = 'CHEQUE' 
  AND cheque_status = 'CASHED';

-- Calculate the total cash-on-hand received by a specific employee today
SELECT SUM(amount) 
FROM payments 
WHERE creator_id = '<user_uuid>' 
  AND payment_type = 'CASH' 
  AND created_at > CURRENT_DATE;
```

## Indexes
- **amount**: [BTREE] Optimizes financial range reporting.
- **cheque_status**: [BTREE] For managing payment lifecycles.
- **date**: [BTREE] For chronological fiscal auditing.
- **payment_type**: [BTREE] Speeds up cash-flow classification.
- **store_id**: [BTREE] Essential for multi-tenant accounting.
