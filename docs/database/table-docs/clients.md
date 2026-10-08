# `clients`

## Searchable Aliases
customers, buyers, accounts, accounts receivable, agencies, partners, companies

## Description
The `clients` table is the master registry for all customer entities within the **Lyndom** (the current PostgreSQL ERP) system. It serves two distinct commercial roles: 
1.  **Direct Customers**: Entities that purchase products and services.
2.  **Sales Agencies**: Partners (dealerships, agencies) that may also act as sales representatives.

The table centralizes the primary billing/shipping profile and financial terms for each customer, acting as the root anchor for all Sales Orders, Quotes, and Invoices.

## ⚠️ SQL-Critical Behaviors
- **The Agency Logic**: If `also_rep = true`, the client is also treated as a sales representative. They are eligible for commissions on orders they facilitate, using the `regular_commission_percentage` and `overage` fields.
- **Embedded Shipping Profile**: The `address_info_...` columns store the primary physical location for the client. This data is the "Default Shipping Address" for all new orders unless overridden.
- **Mandatory Terms**: The `credit_terms_id` defines the payment deadline (e.g., Net 30). This is critical for the **Accounts Receivable** module to calculate overdue invoices.
- **Migration Fingerprint**: If `is_imported = true`, the record originated from the **Phocuss** (legacy MongoDB ERP) system during the initial data migration.

## Columns (26 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Registration timestamp. |
| updated_at | timestamptz | no | — | Last profile update timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this client relationship. |
| name | text | no | — | **Legal Account Name**: The primary name used on invoices and quotes. |
| contact_info_name | text | yes | — | Name of the primary "Point of Contact" for billing/general inquiries. |
| contact_info_email | text | yes | — | Primary email address for document delivery. |
| contact_info_phone | text | yes | — | Primary phone number for the account. |
| address_info_city | text | no | — | City for shipping destination. |
| address_info_address | text | no | — | Full street address for shipping destination. |
| address_info_latitude | numeric(12,2) | yes | — | Geographic latitude for map-based logistics. |
| address_info_longitude | numeric(12,2) | yes | — | Geographic longitude for map-based logistics. |
| address_info_postal_code | text | yes | — | ZIP/Postal code for shipping destination. |
| address_info_building_number | text | yes | — | Specific building or gate number. |
| address_info_unit | text | yes | — | Suite or unit number. |
| also_rep | bool | no | — | **Agency Toggle**: If `true`, this client also serves as a Commissioned Sales Rep. |
| regular_commission_percentage | int4 | yes | — | Standard commission rate awarded for facilitated sales. |
| overage_commission_percentage | int4 | yes | — | Higher-tier commission rate for "Overage" or beyond-quota pricing. |
| is_active | bool | no | — | Status flag. If `false`, the client is blocked from new orders. |
| creator_id | uuid | no | — | The user who registered this client account. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |
| reference_store_id | uuid | yes | — | Optional link to another store if the client is a related business entity. |
| credit_terms_id | uuid | yes | — | Link to `credit_terms.id` defining the payment schedule (e.g., Net 30). |
| address_info_state | text | no | — | State/Province for shipping destination. |
| username | text | yes | — | Client-panel login name. **Credential — never surface in report output.** |
| password | text | yes | — | Client-panel password hash. **Credential — never surface in report output.** |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| reference_store_id | stores | id | set null |
| credit_terms_id | credit_terms | id | set null |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| sales_orders | client_id | The customer purchasing the goods. |
| quotes | client_id | The prospect for the technical proposal. |
| contacts | owner_id | Individual people linked to this client organization. |

## Common Query Patterns
```sql
-- Find all Sales Agency partners (Clients who are also Reps)
SELECT name, regular_commission_percentage 
FROM clients 
WHERE also_rep = true;

-- List clients with specific credit terms for a billing report
SELECT c.name, t.name as term_name 
FROM clients c
JOIN credit_terms t ON c.credit_terms_id = t.id
WHERE t.name = 'Net 30';
```

## Indexes
- *Uses 3 btree indexes on `name`, `is_active`, and `created_at` for high-performance CRM searching.*
