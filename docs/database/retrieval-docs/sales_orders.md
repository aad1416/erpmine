# sales_orders

## Purpose
The authoritative commercial transaction record — the single confirmed deal header that anchors revenue, invoicing, profitability, commissions, and shipping dates for every outbound customer sale or repair order (SO).

---

## Retrieve This Table When The User Asks About

**Order status and lifecycle**
A confirmed customer order, SO, or deal — its current status (pending, in progress, shipped, delivered, cancelled, revised), when it was last updated, or how long it has been open.

**Revenue, totals, and financial summaries**
Total revenue, grand total, order total, gross sales for a branch, rep, time period. Aggregate sales figures. The full dollar value of a confirmed deal including tax, freight, and discounts at the header level.

**Profitability and margin**
Margin percentage, margin value, deal profitability, landed cost (parts + labor), total cost vs order total. Which deals are below a target margin. Profit analysis on a customer project.

**Invoicing and accounting**
Invoice number, invoice date, invoice due date, to-be-invoiced date. Overdue invoices, unpaid orders past their payment deadline. Orders cleared for billing. Credit terms applied to a deal. Customer purchase order number (customer PO) linked to an SO.

**Commission and sales rep performance**
Total commission earned or owed on a deal. Commission percentage, commission base amount, overage commission. Top performing sales rep by order volume or commission. Net revenue after commissions.

**Shipping dates at the deal level**
Estimated ship date, original promised ship date, actual ship date on a confirmed deal. Expedite flag or expedite fee for a rush order. Orders that require a 24-hour pre-delivery call. Will-call pickup orders.

**Billing and shipping address on a confirmed deal**
Billing address, shipping address, delivery destination, project location recorded on a finalized sales order.

**Project-level context**
Project name, project location, description, special instructions on a customer order. Orders tied to a field service ticket (repair orders). Orders linked back to a specific physical asset being repaired.

---

## Co-Retrieved Sibling Tables
- `sales_order_line_items` — the individual items/SKUs inside this order header.
- `clients` — the customer who owns this order.
- `quotes` — the upstream proposal this order was converted from.
- `payments` — money received against this order.
- `shipments` — the physical delivery records for this order.
- `stores` — the branch that owns this order.
- `users` — the sales rep (`sales_person_id`) or creator.
- `credit_terms` — the payment term policy applied.
