# `carriers`

## Searchable Aliases
shipping companies, logistics, courier, delivery service, transport, freight, FedEx, UPS

## Description
The `carriers` table stores the list of shipping and freight providers used by the store to deliver products or receive procurement orders. This lookup table allows the ERP to categorize logic around tracking numbers, shipping costs, and delivery times by associating transactional records (like `shipments` or `purchase_orders`) with a specific logistics company. Examples of actual values include: `post`, `TMA`, `Ups`, and `BEST WAY OVERNIGHT`.

## ⚠️ SQL-Critical Behaviors
- **Logistics Association**: Every shipment is theoretically linked to a carrier. When generating shipping reports or customer tracking links, this table provides the carrier's name.
- **Tenant Isolation**: Carriers are scoped to a `store_id`. This allows different branches to manage their own local contracts with shipping companies. 

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Update timestamp. |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| name | text | no | — | Carrier name. Examples of actual values include: `post`, `Ups`, `TMA`, `BEST WAY OVERNIGHT`. |
| description | text | yes | — | Additional details about the carrier or account terms. |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| creator_id | uuid | no | — | The user who registered this carrier. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| shipments | carrier_id | Identifies which company is transporting the goods. |
| purchase_orders | carrier_id | (Optional) Specifies the preferred carrier for inbound procurement. |

## Common Query Patterns
```sql
-- Find all active carriers for the current store
SELECT name 
FROM carriers 
WHERE store_id = '<store_uuid>' AND is_active = true;

-- List shipments handled by a specific carrier
SELECT s.tracking_number, s.ship_date
FROM shipments s
JOIN carriers c ON s.carrier_id = c.id
WHERE c.name = 'Ups';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| created_at | btree | Sorting by age. |
| is_active | btree | Filtering active carriers. |
| name | btree | Lookup/Search by name. |


