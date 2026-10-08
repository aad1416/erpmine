# shipping_service_types

## Purpose
The delivery method and speed registry. It defines the specific service levels offered by carriers (e.g., Ground, Next Day Air), allowing the business to select the appropriate cost and speed profile for each shipment.

---

## Retrieve This Table When The User Asks About

**Delivery methods and shipping speeds**
Courier service levels, transport methods, or shipping speed profiles (e.g., "Ground", "Express"). Identifying the available delivery options for a particular carrier.

**Transport cost and time profiles**
Finding the standardized shipping methods supported by a branch. Identifying the specific service level (e.g., "Best Way") selected for a logistics transaction.

---

## Co-Retrieved Sibling Tables
- `carriers` — the logistics company providing the service.
- `shipments` — the physical parcel using the service.
- `stores` — the branch that supports or contracts the service level.
