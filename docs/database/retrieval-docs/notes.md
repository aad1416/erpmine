# notes

## Purpose
The universal polymorphic annotation hub. It serves as a commenting engine that can be attached to any record—such as Sales Orders, Units, or Clients—to capture human context, special instructions, and internal communication history.

---

## Retrieve This Table When The User Asks About

**Internal comments and reminders**
Sticky notes, annotations, or record logs. Retrieving the chronological conversation history or audit trail for a specific entity (e.g., a Sales Order or Client).

**Special instructions and human context**
Finding unstructured notes or reminders attached to a physical machine (unit) or a technician's assignment.

**Audit of staff commentary**
Finding all notes created by a specific staff member (author) across the entire system. Filtering for branch-specific internal comments (store_id).

---

## Co-Retrieved Sibling Tables
- `stores` — the branch that owns the internal comment.
- `users` — the author who wrote the note.
- `sales_orders` / `units` / `clients` — the records being annotated (polymorphic).
