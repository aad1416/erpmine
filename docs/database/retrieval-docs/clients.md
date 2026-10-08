# clients

## Purpose
The master registry for all customer entities, including direct buyers and sales agency partners. It centralizes billing and shipping profiles, financial terms, and commissioning rules for every customer relationship.

---

## Retrieve This Table When The User Asks About

**Customer accounts and profiles**
Master registry of customers, buyers, accounts, or companies. Legal account names used on invoices and quotes. Identifying active vs inactive accounts or blocked clients.

**Contact and location information**
Primary point of contact for billing or general inquiries. Customer email addresses and phone numbers for document delivery. Default shipping addresses, cities, and states for client accounts.

**Financial terms and credit**
Accounts receivable profiles. Payment deadlines and credit policies (e.g., Net 30, Net 15) assigned to a customer. Who owns a client relationship at a branch level.

**Agency and rep commissioning**
Sales agency partners or dealerships that also act as commissioned sales representatives (also_rep flag). Standard commission rates or overage percentages awarded to an agency for facilitated deals.

**Migration and internal tracking**
Identifying clients migrated from the legacy Phocuss (MongoDB) system. Users who registered a particular client account.

---

## Co-Retrieved Sibling Tables
- `sales_orders` — orders placed by this client.
- `quotes` — proposals issued to this prospect.
- `contacts` — individual people linked to this client organization.
- `credit_terms` — the payment policy assigned to the account.
- `client_skus` — customer-specific part number mappings.
