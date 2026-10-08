# quote_line_items

## Purpose
The granular itemization of a sales proposal. It captures the negotiated products (SKUs), quantities, and prices for a specific bid before the commercials are finalized in a contract.

---

## Retrieve This Table When The User Asks About

**Proposed products and services**
Quoted parts, proposal items, or bid components. Identifying specific SKUs and their quantities in an estimate. Technical descriptions or scopes of supply for items in a proposal.

**Negotiated pricing and discounts**
Unit quote prices and line-level discount rates offered during a bid. Negotiated tax and tariff percentages for specific products. Total amount for an individual line in a proposal.

**Quote presentation and grouping**
Organizing a proposal into human-readable sections (e.g., Equipment vs Labor) using group and sort order. Identifying optional upgrades or project sections.

**Item-level approval and locking**
Which specific items the customer has greenlit or confirmed (is_confirmed flag). Locking in a price snapshot for a client during negotiation.

**Commission and shippability flags**
Excluding certain fees or pass-through costs from rep commissions (non_commissionable flag). Identifying physical goods that will require warehouse logistics (shippable flag).

---

## Co-Retrieved Sibling Tables
- `quotes` — the parent header for these proposal details.
- `item_stores` — the branch-specific product definition.
- `stores` — the branch managing the bid.
