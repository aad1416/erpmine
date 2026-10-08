# `vendors`

## Searchable Aliases
suppliers, manufacturers, partners, wholesalers, procurement sources, accounts payable

## Description
The `vendors` table is the master repository for all suppliers, manufacturers, and subcontractors who provide goods and services to the **Lyndom** (the current PostgreSQL ERP) system. It manages the procurement life-cycle, ensuring that every purchase is linked to an approved entity with defined contact and tax location data.

Unlike the `clients` table, the `vendors` table focuses on procurement health—allowing the business to track sourcing history and manage technical service partners.

## ⚠️ SQL-Critical Behaviors
- **Technical Partners**: If `is_tech = true`, the vendor is classified as a technical service provider or subcontractor (e.g., HVAC technicians, specialist engineers). This flag is used to filter vendors in the Service and Maintenance modules.
- **Master Logistics Info**: The `address_info_...` columns store the primary warehouse or office location of the supplier. This is the **Source Address** for freight and lead-time calculations in new Purchase Orders.
- **Fulfillment Barrier**: If `is_active = false`, the vendor is blocked. The system will prevent any staff member from generating new Purchase Orders (POs) for this entity, effectively acting as a "Procurement Freeze."

## Columns (22 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Registration timestamp. |
| updated_at | timestamptz | no | — | Last profile update timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing this supplier relationship. |
| name | text | no | — | **Legal Company Name**: The primary name used on Purchase Orders and Checks. |
| website | text | yes | — | Vendor's corporate or ordering website URL. |
| is_active | bool | no | — | Status flag. If `false`, the vendor is barred from new procurement. |
| contact_info_name | text | yes | — | Name of the primary "Sales Representative" or "Account Manager" at the vendor. |
| contact_info_email | text | yes | — | Primary email for sending Purchase Orders (POs) and RFQs. |
| contact_info_phone | text | yes | — | Primary phone number for reaching the supplier. |
| address_info_city | text | no | — | City where the vendor is located. |
| address_info_address | text | no | — | Full street address of the supplier's headquarters or main warehouse. |
| address_info_latitude | numeric(12,2) | yes | — | Geographic latitude for logistics distance calculations. |
| address_info_longitude | numeric(12,2) | yes | — | Geographic longitude for logistics distance calculations. |
| address_info_postal_code | text | yes | — | ZIP/Postal code for logistics and tax zoning. |
| address_info_building_number | text | yes | — | Specific building or gate number of the supplier. |
| address_info_unit | text | yes | — | Suite or warehouse unit number. |
| is_tech | bool | no | — | **Specialist Flag**: If `true`, the vendor provides Labor/Services rather than physical goods. |
| creator_id | uuid | no | — | The procurement officer who registered this vendor. |
| reference_store_id | uuid | yes | — | Optional link to another internal branch if the vendor is a related entity. |
| address_info_state | text | no | — | State/Province where the vendor is located. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| reference_store_id | stores | id | set null |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| purchase_orders | vendor_id | The supplier providing the goods on this order. |
| vending | vendor_id | Sourcing data (SKUs and Costs) specific to this vendor. |
| contacts | owner_id | Individual people (Reps, Techs) linked to this vendor organization. |

## Common Query Patterns
```sql
-- Find all Technical Service Vendors (Contractors)
SELECT name, contact_info_name, contact_info_phone 
FROM vendors 
WHERE is_tech = true AND is_active = true;

-- List all vendors in a specific city for a localized logistics report
SELECT name, website 
FROM vendors 
WHERE address_info_city = 'New York';
```

## Indexes
- *Includes 4 btree indexes on `is_active`, `name`, `store_id`, and `created_at` for high-performance procurement searches.*
