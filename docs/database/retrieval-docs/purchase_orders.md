# purchase_orders

## Purpose
The authoritative header for the procurement of goods and services. It acts as a formal contract with a vendor (PO), tracking financial totals, shipping destinations, and the current lifecycle state of inbound fulfillment.

---

## Retrieve This Table When The User Asks About

**Order status and lifecycle**
A formal buy order, procurement contract, or vendor order — its current state (pending, acknowledged, staged, partially received, received, cancelled, or on hold). Tracking when an order was placed, acknowledged by the vendor, or fully received.

**Procurement totals and financial settlement**
Grand total, paid amount, or unpaid balance owed to a supplier. Tracking tax amounts, tariff fees, and discounts at the PO header level. Monitoring payment completion status (e.g., unpaid, paid). Identifying orders with manual price estimates or placeholders.

**Vendor and supplier information**
The specific vendor or supplier an order was placed with. Billing and shipping addresses for procurement transactions. Tracking vendor lead times and delivery performance.

**Tracking and delivery dates**
Carrier tracking numbers (FedEx, UPS) for inbound shipments. Vendor ETAs and estimated delivery dates. Identifying when the last item was physically received at the loading dock. Required-by dates for time-critical procurement.

**Approval and buying authority**
Who registered the buy order (the buyer) and who authorized the purchase (the manager). Identifying approved vs unapproved procurement contracts.

**Order classification and context**
The category or purpose of a purchase (e.g., blanket order, stocked parts, service order). Buy orders linked to field service tickets or customer sales orders. Identifying migrated records from legacy systems.

---

## Co-Retrieved Sibling Tables
- `purchase_order_line_items` — the individual items/SKUs ordered from the vendor.
- `vendors` — the supplier this order is for.
- `receives` — the warehouse vouchers for physical arrivals.
- `purchase_order_payments` — financial settlement records for the vendor.
- `purchase_order_types` — the workflow classification for the order.
- `users` — the buyer (`creator_id`) or manager (`approved_by_id`).
