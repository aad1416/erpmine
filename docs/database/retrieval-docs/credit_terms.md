# credit_terms

## Purpose
The master policy registry for financial payment terms. It defines how many days a customer or vendor has to pay an invoice before it becomes overdue, governing accounts receivable (AR) and accounts payable (AP) logic.

---

## Retrieve This Table When The User Asks About

**Payment policies and deadlines**
Registry of credit terms, payment terms, or payment deadlines. Standard policies like Net 30, Net 60, COD (Cash on Delivery), or financing agreements.

**Financial enforcement and aging**
How many days a debtor has before an invoice is classified as overdue. Calculating "Days Past Due" (DPD) for aging reports and automated collections.

**Cash flow controls**
Policies used to block shipments or releases until financial conditions are met (e.g., Payment in Advance, COD).

**Branch-level credit policies**
Identifying which credit terms are active or authorized for use within a specific branch or store.

---

## Co-Retrieved Sibling Tables
- `clients` — the customers assigned these terms.
- `sales_orders` — the confirmed deals using these terms for due date calculation.
- `quotes` — the proposals offering these terms.
- `vendors` — the suppliers these terms apply to for payments.
- `stores` — the branch owning the policy.
