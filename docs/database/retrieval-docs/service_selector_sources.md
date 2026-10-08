# service_selector_sources

## Purpose
The technical criteria for automated labor and fee rules. It defines the specific product specifications—such as power, voltage, or material—that act as the "If" conditions to trigger the automated suggestion of non-physical services.

---

## Retrieve This Table When The User Asks About

**Fee triggers and automated labor criteria**
Service mapping sources or trigger specs. Identifying the technical requirements (e.g., "Power: 10kW") that must be met to append a service to an order.

**Service rule matching**
Finding which service selector applies to a specific product category or technical attribute.

---

## Co-Retrieved Sibling Tables
- `service_selectors` — the parent automation rule.
- `categories` — the product family being monitored for triggers.
- `specifications` — the technical attribute being monitored.
