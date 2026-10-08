# payments

## Purpose
The general financial ledger and voucher registry. It records standalone cash-flow events, including cash receipts, cheque deposits, and bank transfers, independently of specific sales or purchase orders.

---

## Retrieve This Table When The User Asks About

**Cash flow and monetary transactions**
Financial transactions, ledger entries, or vouchers for money moving in or out of a branch. Monetary events explanatory descriptions.

**Payment types and instruments**
Cash receipts, bank transfers, cheques, or POS payments. Tracking the issuer of funds and the receiver. Instrument-specific details like bank transaction IDs or physical cheque reference numbers.

**Governance and identity verification**
Regulatory compliance for high-value audit trails. Capturing receiver national IDs or identifying the employee (creator) who accepted the funds.

**Payment lifecycle and reconciliation**
Cheque status (pending, cleared, bounced). When a payment occurred (transaction date). Reconciling open balances or miscellaneous income.

**Financial locations**
Target bank accounts or internal cash-drawer locations (destination).

---

## Co-Retrieved Sibling Tables
- `stores` — the branch receiving or issuing the payment.
- `users` — the staff member who registered the transaction.
- `sales_order_payments` — the link between these vouchers and specific orders.
- `purchase_order_payments` — the link between these vouchers and vendor orders.
