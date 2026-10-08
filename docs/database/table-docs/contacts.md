# `contacts`

## Searchable Aliases
people, individuals, representatives, stakeholders, phone numbers, emails, addresses

## Description
The `contacts` table is the universal registry for individual people within the **Lyndom** (the current PostgreSQL ERP) ecosystem. While the `clients` and `vendors` tables representing organizations, the `contacts` table represents the **human beings**—such as Sales Representatives, Technicians, and Billing Clerks—who work for those organizations.

It uses a **Polymorphic Ownership** model, allowing a single structure to manage people across multiple business domains (Sales and Purchasing) without duplicating logic.

## ⚠️ SQL-Critical Behaviors
- **Polymorphic Linkage**: To find the person associated with a client or vendor, you must filter by both `owner_id` (the UUID of the organization) and `owner_type` (the string literal `client` or `vendor`).
- **Contact Hub**: This table is the "Communication Nexus." Any notification, email automation, or CRM task that targets a human being should query this table to retrieve the most recent `email` and `phone` data.
- **Tenant Scope**: Like most entities, contacts are scoped to a `store_id`, ensuring that customer contacts for one branch aren't visible or editable by users at another branch.

## Columns (11 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Date the person was added to the CRM. |
| updated_at | timestamptz | no | — | Date of last contact info update. |
| store_id | uuid | yes | — | **Tenant ID**: The branch managing this contact relationship. |
| name | varchar(255) | no | — | **Full Name**: The human-readable name of the individual. |
| email | text | yes | — | Primary email address for direct communication. |
| phone | text | yes | — | Direct phone number or extension. |
| owner_id | uuid | no | — | **Parent UUID**: The ID of the Client or Vendor this person works for. |
| owner_type | text | no | — | **Parent Type**: Discriminator flag (Examples of actual values include: `client`, `vendor`). |
| is_active | bool | no | true | Status flag. If `false`, the person has likely left the organization and is no longer a valid contact. |
| creator_id | uuid | no | — | The user who registered this individual in the system. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Owner Mapping (Polymorphic)
| `owner_type` Value | Parent Table | Relationship |
|--------------------|--------------|--------------|
| `client` | `clients` | Represents an individual staff member at a Customer organization. |
| `vendor` | `vendors` | Represents a Rep or Tech at a Supplier organization. |

## Common Query Patterns
```sql
-- List all active contacts for a specific Client organization
SELECT name, email, phone 
FROM contacts 
WHERE owner_id = '<client_uuid>' AND owner_type = 'client' AND is_active = true;

-- Find a person by their email address across the whole system
SELECT name, owner_type 
FROM contacts 
WHERE email = 'john.doe@example.com';
```

## Indexes
- *Includes btree indexes on `email`, `phone`, and the polymorphic pair `owner_id` + `owner_type` for high-speed CRM searching.*
