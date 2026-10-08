# shipments

## Purpose
The physical logistics voucher for outbound movement. It records the act of picking, packing, and dispatching goods from the warehouse to the customer, acting as the bridge between the warehouse dock and the shipping carrier.

---

## Retrieve This Table When The User Asks About

**Outbound logistics, fulfillment, and imports**
Delivery vouchers, manifests, outbound shipments, or physical overseas imports. Tracking the physical dispatch of items, containers, customs clearance, and duties. Identifying the specific act of pick-pack-and-ship vs the commercial agreement (sales order).

**Logistics status and tracking**
Tracking numbers, carrier assignments, and shipping statuses (Pending, Picked, Shipped, Cancelled). Finding the actual ship date when the carrier physically took the goods. Identifying if a shipment is a standard delivery or a rush order.

**Parcel details and surcharges**
Handling charges for specialized packing or crating. Additional weights from packaging or pallets. Identifying the legal point of handover (FOB origin vs destination) for ownership transfer.

**Partial fulfillment and backorders**
Tracking multiple shipments linked to a single sales order. Identifying if an order was shipped in installments or if specific items are still pending.

**Warehouse auditing and workload**
Current logistics workload, pick-lists, or shipments pending warehouse action. Auditing the history of transport events for a branch.

---

## Co-Retrieved Sibling Tables
- `shipment_line_items` — the specific physical assets packed in the shipment.
- `sales_orders` — the parent contract being fulfilled.
- `carriers` — the shipping company (e.g., FedEx, UPS).
- `shipping_service_types` — the selected delivery speed or method.
- `users` — the warehouse clerk who registered or packed the shipment.
