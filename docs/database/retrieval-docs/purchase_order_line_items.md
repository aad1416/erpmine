# purchase_order_line_items

## Purpose
The itemized requirement record for a Purchase Order. It details the specific products (SKUs), quantities, and unit costs being procured from a vendor, acting as the primary input for warehouse receiving and inventory costing.

---

## Retrieve This Table When The User Asks About

**Purchased products and ordered parts**
Bought items, po components, or procurement list details. Identifying specific internal SKUs or vendor-SKUs being bought. Technical descriptions or part names for items in an inbound shipment.

**Fulfillment progress and backorders**
Tracking how much of a product has been received vs how much was originally ordered. Identifying short-ships or vendor backorders. Monitoring units that are in-transit from a supplier.

**Unit costs and landed totals**
Negotiated unit prices for specific products in a buy order. Calculating the landed total for a line by including tariffs, overhead, and tax. Identifying discount rates or tax amounts for individual items.

**Warehouse staging and timing**
Identifying incoming units reserved (staged) for a specific production job or customer order. Tracking required-by dates and vendor promised lead times at the line-item level.

**Unit of measure and conversion**
Purchase-to-stock unit conversion (e.g., buying a box, stocking as 12 units) using coefficients and UOM names.

---

## Co-Retrieved Sibling Tables
- `purchase_orders` — the parent header for these requirements.
- `item_stores` — the branch-specific product definition.
- `vending` — the vendor-SKU relationship and sourcing route.
- `receive_line_items` — the actual arrival events for these items.
