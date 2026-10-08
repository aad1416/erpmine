# option_selectors

## Purpose
The product logic engine for upgrades. It manages the high-level automation rules for appending optional modular components and physical system upgrades to a product configuration during the quoting process.

---

## Retrieve This Table When The User Asks About

**Automated product upgrades and add-ons**
Configuration rules or modular item mapping. Identifying the logic for adding optional physical parts (e.g., "Add Premium Enclosure") based on a base product's selection.

**Branch-specific upgrade logic**
Finding the active upgrade selectors defined for a specific branch or location.

---

## Co-Retrieved Sibling Tables
- `option_selector_sources` — the "If" triggers (base product specs).
- `option_selector_destinations` — the "Then" results (technical profile of the add-on).
- `stores` — the branch managing the upgrade rules.
