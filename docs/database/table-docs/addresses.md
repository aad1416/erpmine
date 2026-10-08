# `addresses`

## Searchable Aliases
location, shipping, billing, street, coordinates, geography, maps, destination

## Description
The `addresses` table is a polymorphic lookup used to store physical location data for various entities across the ERP, including stores, clients, and vendors. By using a polymorphic model (`owner_id` paired with `owner_type`), the system centralizes all geographic and street-level data into a single structure. This enables shared logic for address validation, mapping (via latitude/longitude), and document generation (e.g., printing shipping labels). 

## ⚠️ SQL-Critical Behaviors
- **Polymorphic Joins**: To find the address for a specific entity, you must filter by both `owner_id` and `owner_type`. **Examples of actual values for `owner_type`** (inferred from system patterns) include: `client`, `vendor`, and `store`.
- **Nullable Context**: The `store_id` is optional (`nullable`), as some addresses (like those of global vendors) may exist outside the scope of a specific branch.
- **Geolocation Support**: The `latitude` and `longitude` columns allow the frontend to display entity locations on a map or calculate shipping distances.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Update timestamp. |
| store_id | uuid | yes | — | Foreign key to `stores.id`. |
| state | text | no | '' | State or Province code. |
| city | text | no | — | City name. |
| address | text | no | — | Full street address. |
| latitude | numeric(9,6) | yes | — | Geographic latitude for mapping. |
| longitude | numeric(9,6) | yes | — | Geographic longitude for mapping. |
| postal_code | text | yes | — | ZIP/Postal code. |
| building_number | text | yes | — | Specific building or house number. |
| unit | text | yes | — | Suite, Apartment, or Unit number. |
| name | text | no | — | Label for the address (e.g., "Home", "Warehouse", "Billing"). |
| owner_id | uuid | no | — | Foreign key to the parent entity's ID (e.g., `clients.id`). |
| owner_type | text | no | — | Discriminator for the parent entity type (Examples of actual values include: `client`, `vendor`). |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| creator_id | uuid | no | — | The user who registered this address. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
- *Referenced polymorphically by most transactional entities requiring shipping/billing info.*

## Common Query Patterns
```sql
-- Retrieve all shipping addresses for a specific client
SELECT name, address, city, state 
FROM addresses 
WHERE owner_id = '<client_uuid>' AND owner_type = 'client';

-- Find all vendors located in a specific city
SELECT owner_id 
FROM addresses 
WHERE owner_type = 'vendor' AND city = 'New York';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| city | btree | Filtering by city. |
| created_at | btree | Sorting by age. |
| is_active | btree | Filtering active addresses. |
| latitude | btree | Geographic distance queries. |
| longitude | btree | Geographic distance queries. |
| owner_id | btree | Finding addresses for a specific parent. |
| owner_type | btree | Scoping to a specific parent category. |
| state | btree | Filtering by state. |
| store_id | btree | Branch-level partitioning. |


