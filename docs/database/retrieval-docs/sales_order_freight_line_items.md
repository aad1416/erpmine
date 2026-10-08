# sales_order_freight_line_items

## Purpose
The ledger for itemized shipping and handling charges billed to a customer. This table represents the revenue side of logistics, tracking exactly what the client is paying for transport services on a Sales Order.

---

## Retrieve This Table When The User Asks About

**Customer shipping fees and charges**
Outbound transport charges, delivery costs, and freight revenue billed on a finalized sales order. Total freight collected from a client.

**Carrier and service level assignments**
Specific transport companies (carriers) like UPS or FedEx and service levels (e.g., Ground, Air, LTL Truck) used for a shipment. Comparing customer-facing logistics descriptions with their price.

**Logistics revenue and recovery**
Analyzing freight profitability by comparing the price charged to the customer here against internal logistics costs. Identifying active vs voided shipping charges on an order.

---

## Co-Retrieved Sibling Tables
- `sales_orders` — the parent contract these charges apply to.
- `carriers` — the transport company performing the service.
- `shipping_service_types` — the specific speed or method of delivery.
