# relationship_requests

## Purpose
The inter-store B2B network manager. It governs the formal "handshake" between branches, allowing one store to become a Client or Vendor of another to unlock cross-store purchasing and shared catalog browsing.

---

## Retrieve This Table When The User Asks About

**B2B connections and partner requests**
Store-to-store links or account linkages. Identifying formal partnership proposals between branches (e.g., Store A requesting to be a Vendor for Store B).

**Inter-store purchasing and catalog sharing**
Verifying if a B2B relationship is "ACCEPTED" to unlock cross-store orders. Finding authorized internal suppliers for a specific branch.

**Relationship status and governance**
Tracking the state of B2B proposals (Pending, Accepted, Rejected). Identifying the directional purpose (Client vs. Vendor) of a partner link.

**Cross-store account references**
Retrieving the "Local ID" or account number by which two stores recognize each other in their internal ledgers.

---

## Co-Retrieved Sibling Tables
- `stores` (Origin) — the branch initiating the partnership.
- `stores` (Target) — the branch receiving the proposal.
- `purchase_quotes` — cross-store transactions that rely on an accepted relationship.
