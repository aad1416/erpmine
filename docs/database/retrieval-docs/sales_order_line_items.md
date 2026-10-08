# sales_order_line_items

## Purpose
The itemized fulfillment record for a Sales Order. Every record is a unique SKU commitment, defining the quantity, unit price, and physical fulfillment status of a specific product or service sold to a customer.

---

## Retrieve This Table When The User Asks About

**Product-level fulfillment and backorders**
Details on sold items, order details, and sales components. Which items are on backorder or partially shipped. Comparing ordered quantity against shipped quantity or delivered quantity for specific SKUs.

**SKU-specific pricing and discounts**
Unit sales price, line-level discount rate, or discount amount for a particular item in an order. Tax and tariff rates applied to specific products. Total amount for a single line item.

**Warehouse and logistics execution**
Picking, packing, and shipping status of individual order parts. Identifying shippable items that require warehouse packaging. Items marked with a do-not-split flag for logistics. Sales-to-warehouse unit conversion using coefficients and UOM names (e.g., cases, pallets).

**Asset generation and tracking**
Items that trigger the creation of a physical asset or unit record upon shipment (generate_unit flag). Tracking which serial-tracked machines were sold to a client.

**Invoice structure and grouping**
How items are sorted and grouped on a customer's final invoice. Identifying non-commissionable fees or pass-through costs at the line level.

---

## Co-Retrieved Sibling Tables
- `sales_orders` — the parent header for these line items.
- `item_stores` — the branch-specific product definition.
- `shipment_line_items` — the specific parcel allocations for fulfillment.
- `uoms` — unit of measure definitions.
