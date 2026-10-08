# addresses

## Purpose
A polymorphic registry for all physical location data. It centralizes street addresses, geographic coordinates, and contact labels for stores, clients, vendors, and any other entity requiring location tracking.

---

## Retrieve This Table When The User Asks About

**Physical locations and street addresses**
Street names, house numbers, suite/unit numbers, cities, states, and postal codes for any account or branch. Searchable labels like "Home", "Warehouse", or "Billing". 

**Geographic coordinates and mapping**
Latitude and longitude for entities. Geographic distance calculations or map-based logistics (e.g., finding the closest branch or customer).

**Entity-specific location data**
Shipping or billing addresses for a specific client, vendor, or store. Using owner IDs and owner types (e.g., client, vendor) to resolve where an entity is located.

**Logistics and document generation**
Data required for printing shipping labels, delivery manifests, or destination mapping. Identifying active vs inactive locations for an entity.

---

## Co-Retrieved Sibling Tables
- `clients` — customer entities linked to these addresses.
- `vendors` — supplier entities linked to these addresses.
- `stores` — branch entities linked to these addresses.
- `users` — the staff member who registered the location.
