# option_selector_destinations

## Purpose
The "Automatic Add-on" target. It defines the technical profile—category and specifications—of the physical component that the system should automatically attach to an order when an upgrade rule is triggered.

---

## Retrieve This Table When The User Asks About

**Automatic add-ons and configuration outputs**
Selection targets or mapping destinations for upgrades. Identifying the technical identity (profile) of a required add-on (e.g., "Category: Bracket Systems, Compatibility: Series-A").

**Dynamic product discovery**
Finding the correct, currently active product variant that matches an engineering requirement. Auditing the "Output" of the logic engine without relying on static (possibly discontinued) Item IDs.

---

## Co-Retrieved Sibling Tables
- `option_selectors` — the parent upgrade rule.
- `categories` — the target category for the add-on item.
- `specifications` — the technical attribute used to discover the correct item.
