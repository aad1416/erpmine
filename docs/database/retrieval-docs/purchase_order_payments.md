# purchase_order_payments

## Purpose
The financial settlement ledger for the procurement module. it links global payment records (checks, wires) to specific Purchase Orders (POs) to satisfy vendor liabilities and track the paid balance of each order.

---

## Retrieve This Table When The User Asks About

**Vendor payments and settlement**
Procurement finance, po settlement, or proof of payment for a buy order. Identifying how much has been paid (allocated) to a specific vendor order.

**Accounts payable auditing**
Authoritative records of cash allocations to suppliers. Summing payment history to calculate total spend or outstanding paid balances for a vendor.

**Payment allocation and voiding**
Tracking which master financial transaction (ledger entry) was used to pay a PO. Identifying voided or reversed payment allocations.

---

## Co-Retrieved Sibling Tables
- `purchase_orders` — the contract being settled.
- `payments` — the global financial voucher (check/wire).
- `stores` — the branch issuing the payment.
- `users` — the accountant who authorized the allocation.
