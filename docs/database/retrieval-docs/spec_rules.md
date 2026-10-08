# spec_rules

## Purpose
The validation and auto-configuration engine for engineering. It defines the dependency logic between technical attributes, ensuring that product configurations are technical compatible and compliant with safety standards.

---

## Retrieve This Table When The User Asks About

**Technical constraints and attribute validation**
Engineering rules or specification logic. Identifying the "If-Then" relationships between technical specs (e.g., "If Voltage is 480V, then Breaker must be 100A").

**Automated configuration and quoting**
Auto-appending related parts or mandating specific technical selections during the quoting phase. Finding rules that prevent configuration errors or ensure safety compliance.

**Rule triggers and enforcement**
Identifying the "Trigger" attribute (source specification) and value that activates a rule. Checking if a rule is "Strict" (cannot be overridden) or "Suggested".

---

## Co-Retrieved Sibling Tables
- `spec_rule_targets` — the resulting constraints (the "Then" part).
- `specifications` — the technical attributes being monitored.
- `item_stores` — the SKUs linked to automated selection rules.
- `categories` — the product domain where the rule applies.
