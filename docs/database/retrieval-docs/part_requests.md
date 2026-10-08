# part_requests

## Purpose
The internal demand trigger. It acts as the formal requisition document (Shopping List) for technicians to request materials from stock for manufacturing builds, repairs, or branch needs.

---

## Retrieve This Table When The User Asks About

**Material requisitions and stock requests**
Part orders or internal procurement needs. Identifying "Who" requested "What" for "Which" machine build or repair. Finding the human-readable tracking ID (e.g., PR-2001) for a material request.

**Internal demand and triage**
Listing active part requests for the warehouse team to pick and fulfill. Finding parts requested specifically for a high-priority Sales Order.

**Request audit trail**
Explaining "Why" a part was withdrawn from stock. Identifying the technician (requestor) and the warehouse clerk (assigned picker) responsible for the movement.

---

## Co-Retrieved Sibling Tables
- `part_request_line_items` — the specific SKUs and quantities in the request.
- `units` — the physical serial number needing the parts.
- `sales_orders` — the commercial contract driving the demand.
- `users` — the requestor and the fulfiller.
- `goods_issues` — the final physical inventory subtraction.
