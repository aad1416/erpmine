# quote_freight_line_items

## Purpose
The ledger for estimated shipping and handling charges included in a sales proposal. It allows sales teams to provide precise logistics cost estimates to prospects before a deal is closed.

---

## Retrieve This Table When The User Asks About

**Estimated shipping and transport fees**
Freight quotes, delivery estimates, or outbound transport fees included in a customer's sales proposal. The dollar amount a client is quoted for logistics.

**Carrier and service level projections**
Proposed transport companies (e.g., FedEx, UPS) and service methods (e.g., Ground, LTL Truck) for a future shipment. 

**Logistics verification and status**
Identifying which shipping estimates have been reviewed and greenlit by a logistics manager (is_confirmed flag). Active vs inactive freight scenarios (e.g., Sea vs Air) presented to a customer.

---

## Co-Retrieved Sibling Tables
- `quotes` — the parent proposal these estimates apply to.
- `carriers` — the transport company perform the service.
- `shipping_service_types` — the specific method or speed of delivery.
- `sales_order_freight_line_items` — the destination table once the quote is sold.
