# purchase_order_freight_line_items

## Purpose
The logistics ledger for procurement. It itemizes the shipping, handling, and transport costs that the business must pay to vendors or carriers for inbound deliveries on a Purchase Order (PO).

---

## Retrieve This Table When The User Asks About

**Procurement shipping and freight costs**
Inbound transport fees, delivery surcharges, or po freight costs we pay to suppliers or third-party carriers. Total freight spend on a specific buy order.

**Inbound logistics and carriers**
Carriers (e.g., FedEx, UPS) and shipping service types (e.g., Ground, Express) used for vendor deliveries. Tracking which logistics providers are used for inbound stock.

**Landed cost and valuation**
Separating shipping charges from item costs to calculate accurate inventory landed costs. Identifying fuel surcharges or handling fees on a procurement contract.

---

## Co-Retrieved Sibling Tables
- `purchase_orders` — the buy order these costs apply to.
- `carriers` — the transport provider.
- `stores` — the branch paying for the transport.
- `shipping_service_types` — the method or speed of delivery.
