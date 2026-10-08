# `shipping_service_types`

## Searchable Aliases
delivery methods, shipping speeds, courier service levels, transport types

## Description
The `shipping_service_types` table defines the specific service levels or shipping methods offered by each carrier (e.g., "Ground", "Next Day Air", "Best Way"). While the `carriers` table identifies the logistics company, this table identifies the speed and cost profile of the shipment. By separating service types from carriers, the ERP can provide users with a granular list of shipping options during the sales or procurement process. Examples of actual values include: `Best Way` and `Ground`.

## ⚠️ SQL-Critical Behaviors
- **Carrier Linkage**: Every service type must be linked to a valid `carriers.id`. You cannot select a "Ground" service without first identifying the carrier providing it.
- **Tenant Isolation**: Service types are scoped to a `store_id`, allowing branches to define only the shipping levels they have contracted or support.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Update timestamp. |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| carrier_id | uuid | no | — | Foreign key to `carriers.id`. |
| name | text | no | — | Service level name. Examples of actual values include: `Ground`, `Best Way`, `TMA`. |
| description | text | yes | — | Additional context about the service (e.g., "3-5 business days"). |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| creator_id | uuid | no | — | The user who registered this service type. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| carrier_id | carriers | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| shipments | shipping_service_type_id | (Optional) Specifies the exact speed/method selected for the shipment. |

## Common Query Patterns
```sql
-- Find all service levels offered by 'UPS' at a specific branch
SELECT sst.name 
FROM shipping_service_types sst
JOIN carriers c ON sst.carrier_id = c.id
WHERE c.name = 'Ups' AND sst.store_id = '<store_uuid>';
```

## Indexes
- *Uses default PK and FK constraints.*


