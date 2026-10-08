# receives

## Purpose
The warehouse voucher for the physical arrival of goods. it acts as the audit bridge between a contractual purchase (PO) and the physical inventory added to the warehouse shelves.

---

## Retrieve This Table When The User Asks About

**Material receiving and stock intake**
Warehouse entry vouchers, goods received records, or inbound shipment acknowledgments. Tracking when stock physically arrived at the building (received_at date).

**Warehouse arrival verification**
Identifying the staff member who verified the counts and processed the receiving event (receive_by_name). Counting receiving volume or activity per employee or branch.

**Procurement fulfillment audit**
Cross-referencing receiving vouchers with their parent purchase order numbers. Identifying all physical deliveries related to a specific buy order. 

**Inventory and costLayer generation**
The triggering event for updating physical stock-on-hand balances and creating financial cost layers in FIFO reports.

---

## Co-Retrieved Sibling Tables
- `receive_line_items` — the individual products and quantities in the arrival.
- `purchase_orders` — the contract being fulfilled.
- `inventory_items` — the physical stock records created.
- `fifo_reports` — the cost layers generated for accounting.
- `users` — the staff member who registered or verified the receipt.
