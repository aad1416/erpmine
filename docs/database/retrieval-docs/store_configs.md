# store_configs

## Purpose
The operational logic and system parameters for a branch. It stores fine-grained settings—such as warranty durations, billing grace periods, and automation flags—that control how the system behaves for a specific tenant at runtime.

---

## Retrieve This Table When The User Asks About

**Branch settings and local system parameters**
Operational flags or store-level configuration. Identifying the default values for new transactions (e.g., Net 30 payment terms or 1-year warranty).

**Automation and procurement triggers**
Checking if the store automates the inventory procurement process (auto-generate part requests). Identifying custom serial number prefixes (e.g., 'SN-') for inventory items.

**Financial and legal defaults**
Finding the default quote expiry window or the standard number of days allowed before invoicing.

---

## Co-Retrieved Sibling Tables
- `stores` — the branch these settings apply to.
