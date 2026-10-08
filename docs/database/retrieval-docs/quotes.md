# quotes

## Purpose
The negotiation hub for formal technical and commercial proposals (bids). It stores preliminary, non-binding estimates defining project scope, pricing, and quantities before they are converted into a legally binding Sales Order.

---

## Retrieve This Table When The User Asks About

**Quoting lifecycle and status**
Sales proposals, bids, or estimates in different stages: new, pending, revised, expired, or sold. Tracking quote revisions and original source IDs. When a proposal expires (guarantee window).

**Sales pipeline and forecasting**
Pending bids, open estimates, or prospective project names (e.g., HVAC Tower A). Aggregating total order value of the sales pipeline for revenue forecasting. Success rate of quotes converted to sold orders.

**Proposal confirmation and approval**
Customer verification of billing/shipping profiles and total price before signing. Who authorized or approved a proposal and when the formal confirmation was received.

**Preliminary financial estimates**
Estimated grand totals, taxes, tariffs, and discount amounts offered to a prospect. Projected commissions and overage earned by sales reps on a potential deal. 

**Logistics planning for bids**
Initial will-call pickup flags, lead time estimates, and freight cost projections for a proposed project.

**Customer and project context**
The prospect (client or agency) for a technical proposal. Quotes related to field service tickets or specific machines (repair estimates). Site locations and descriptions for a proposed job.

---

## Co-Retrieved Sibling Tables
- `quote_line_items` — the individual products and services inside the proposal.
- `clients` — the prospect or account this proposal is for.
- `sales_orders` — the resulting order if the quote is converted (sold).
- `users` — the salesperson or creator of the bid.
- `credit_terms` — the proposed payment schedule.
