# purchase_orders_sales_orders

## Purpose
A junction entity for hard allocation between supply and demand. It binds a vendor Purchase Order (PO) directly to the customer Sales Order (SO) that triggered it, ensuring incoming stock is immediately earmarked for a specific commitment.

---

## Retrieve This Table When The User Asks About

**Back-to-back orders and drop shipments**
Linking vendor shipments directly to customer demands. Earmarking incoming parts for a specific sales contract before they even arrive at the warehouse.

**Order traceability and allocation**
Searching for which vendor PO is fulfilling a specific customer order. Identifying which customer orders are waiting on a particular supplier shipment or tracking number.

**Just-in-time (JIT) procurement**
Just-in-time purchasing links or back-to-back order cross-references. Ensuring stock received at the dock is allocated to the correct customer instead of general inventory.

---

## Co-Retrieved Sibling Tables
- `purchase_orders` — the vendor order providing the supply.
- `sales_orders` — the customer order creating the demand.
