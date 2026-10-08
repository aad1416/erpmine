# rma_line_items

## Purpose
The SKU-level itemization of a return authorization. It provides the warehouse with the exact pick-list of products, quantities, or unique physical units expected in a customer's incoming return package.

---

## Retrieve This Table When The User Asks About

**Returned parts and defective components**
Itemized list of products (SKUs) being returned. Historical part names and SKU codes at the time of authorization. Detailed technical conditions or failure descriptions for specific items.

**Modular vs whole unit returns**
Identifying if an entire equipment assembly is returning (whole_unit = true) or just a specific sub-component or part for repair.

**Serialized asset tracking**
Unique physical units or machines (serial numbers) being returned to the warehouse. Linking return items to their specific asset records (unit_id).

**Warehouse verification and counts**
The authorized quantity or count of items approved for return. Providing a template for warehouse staff to verify physical package contents against legal authorizations.

---

## Co-Retrieved Sibling Tables
- `rma` — the parent authorization header.
- `item_stores` — the branch product definition for stock incrementing.
- `units` — the specific serialized assets being returned.
- `users` — the staff member who registered the return line.
