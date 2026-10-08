# spec_rule_targets

## Purpose
The "Then" part of engineering dependency logic. It defines the specific technical constraints or automations—such as mandating a specific phase or unit—that must be applied when a parent technical rule is triggered.

---

## Retrieve This Table When The User Asks About

**Technical rule scope and consequences**
Spec validation targets or attribute rule mapping. Identifying which attributes (e.g., "Phase: 3-Phase") must be modified or mandated based on a previous technical choice.

**Ripple effects in configuration**
Finding the target constraints that ensure technical consistency across multiple fields of a product configuration.

---

## Co-Retrieved Sibling Tables
- `spec_rules` — the parent "If" rule.
- `specifications` — the technical attribute being mandated or suggested.
