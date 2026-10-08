# purchase_quotes

## Purpose
The bridge for inter-store stock requests and internal trade. It manages the formal "Request to Buy" from one warehouse (Store A) to another (Target Store), synchronizing the linked buyer and seller orders across branch boundaries.

---

## Retrieve This Table When The User Asks About

**Inter-store stock requests and handoffs**
Internal branch-to-branch stock transfers or warehouse handoffs. Identifying requests to buy inventory from another internal location or warehouse.

**Internal trade and pricing**
Vendor bids or pricing requests from internal supplier stores. Tracking the negotiation between branches for stock availability and internal pricing.

**Linked order synchronization**
Managing the pair of linked contracts: the buyer's Purchase Order (originating store) and the seller's Sales Order (target store). Identifying if an internal request has been accepted or if it is still pending.

---

## Co-Retrieved Sibling Tables
- `stores` — the originating branch requesting stock.
- `stores` (target) — the supplier branch providing the goods.
- `purchase_orders` — the resulting buyer's contract.
- `sales_orders` — the resulting seller's contract.
