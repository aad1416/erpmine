# stores

## Purpose
The structural cornerstone of the multi-tenant architecture. It defines every distinct physical or logical business entity—such as a branch, warehouse, or facility—and serves as the primary partition for data isolation across the entire system.

---

## Retrieve This Table When The User Asks About

**Business locations and branches**
Retail shops, warehouses, or facilities. Searching for store contact information (email/phone) or physical addresses. Identifying the primary manager or owner of a branch.

**Tenant isolation and data partitioning**
The most critical filter for almost every query (store_id). Ensuring that data from one branch doesn't leak into another.

**External file integration and legacy data**
Fetching and displaying files (PDFs/Images) from the legacy Phocuss file manager. Using unique business numbers to map assets across different database formats (UUID vs ObjectID).

**Geographic distribution**
Finding stores with specific geographic coordinates (latitude/longitude) or within a certain city/state.

---

## Co-Retrieved Sibling Tables
- `store_configs` — the operational logic and default settings for the branch.
- `user_stores` — the staff members authorized to access the branch.
- `departments` — the internal functional teams within the store.
- `users` — the store owner or manager.
