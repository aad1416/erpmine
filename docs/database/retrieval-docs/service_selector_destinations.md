# service_selector_destinations

## Purpose
The automated service result. It defines the technical profile—such as category and skill level—of the non-physical item that the system should automatically append to an order when a service rule is triggered.

---

## Retrieve This Table When The User Asks About

**Fee targets and labor mapping**
Automatic service selection or mapping destinations. Identifying the technical blueprint (e.g., Category: Labor, Skill: Installation) for a required service.

**Mandatory labor and safety services**
Identifying safety-critical services (e.g., Commissioning) that are flagged as "Mandatory" and cannot be removed from a sales order.

**Dynamic service matching**
Finding the correct service SKU that matches a technical profile without relying on hard-coded Item IDs.

---

## Co-Retrieved Sibling Tables
- `service_selectors` — the parent automation rule.
- `categories` — the target category for the service item.
- `specifications` — the technical attribute used for discovery.
