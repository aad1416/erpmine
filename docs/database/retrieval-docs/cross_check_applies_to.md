# cross_check_applies_to

## Purpose
The filter logic engine for verification. It defines the surgical technical criteria—such as category and spec values—used to cross-check an uploaded design file against the internal product catalog to find invalid configurations.

---

## Retrieve This Table When The User Asks About

**Validation rules and rule scope**
Dependency mapping or technical filtering logic for design audits. Identifying the "Benchmark" values (e.g., "Voltage = 480V") used to sift through uploaded file data.

**Design discrepancy highlighting**
Surgical rules used to identify if a customer’s design file contains invalid technical configurations or unavailable items within a specific category (e.g., "Transformers").

---

## Co-Retrieved Sibling Tables
- `cross_checks` — the parent audit header.
- `categories` — the product family being validated.
- `specifications` — the technical characteristic used as a benchmark.
