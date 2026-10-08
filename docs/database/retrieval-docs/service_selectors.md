# service_selectors

## Purpose
The logic engine for automated fees and labor. It manages the rules for automatically appending non-physical services—such as installation, commissioning, or extended warranties—to sales orders based on the technical specifications of the products being sold.

---

## Retrieve This Table When The User Asks About

**Automated fees and service logic**
Non-physical add-ons or labor rules. Identifying the selection logic used to suggest corresponding service items during quoting.

**Branch-specific service automation**
Finding the active service selection rules (labels) for a specific store or branch.

---

## Co-Retrieved Sibling Tables
- `service_selector_sources` — the "If" conditions (product criteria).
- `service_selector_destinations` — the "Then" results (technical service profile).
- `stores` — the branch managing the automation rules.
