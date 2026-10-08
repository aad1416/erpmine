# carriers

## Purpose
The logistics provider registry. It stores the list of shipping companies and freight couriers used to deliver products to customers or receive procurement orders from vendors.

---

## Retrieve This Table When The User Asks About

**Shipping companies and courier services**
Logistics providers, transport companies, or freight carriers (e.g., FedEx, UPS). Identifying which company is responsible for a delivery or inbound procurement.

**Logistics reporting and tracking**
Associating tracking numbers and shipping costs with specific delivery services. Finding all shipments handled by a particular logistics partner.

---

## Co-Retrieved Sibling Tables
- `shipments` — outbound deliveries handled by the carrier.
- `purchase_orders` — inbound procurement transport.
- `shipping_service_types` — the specific speeds and methods offered by the carrier.
